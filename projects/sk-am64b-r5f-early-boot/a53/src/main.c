// SPDX-License-Identifier: BSD-3-Clause

#define _POSIX_C_SOURCE 199309L

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <unistd.h>

#include "../../r5f/draft/early_heartbeat_status.h"

#define DEVMEM_PATH "/dev/mem"
#define SNAPSHOT_RETRIES 16U
#define DEFAULT_VERIFY_INTERVAL_MS 250U
#define MAX_VERIFY_INTERVAL_MS 10000U

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage:\n"
            "  %s status\n"
            "  %s verify [interval_ms]\n",
            prog,
            prog);
}

static int parse_interval_ms(const char *arg, unsigned int *interval_ms)
{
    char *end;
    unsigned long value;

    errno = 0;
    value = strtoul(arg, &end, 10);
    if (errno != 0 || end == arg || *end != '\0' || value == 0UL || value > MAX_VERIFY_INTERVAL_MS)
        return -1;

    *interval_ms = (unsigned int)value;
    return 0;
}

static int snapshot_looks_valid(const EarlyHeartbeatStatus *snapshot)
{
    return snapshot->magic == EARLY_HEARTBEAT_SHM_MAGIC &&
           snapshot->version == EARLY_HEARTBEAT_SHM_VERSION &&
           snapshot->abi_size == (uint32_t)sizeof(*snapshot) &&
           snapshot->core == EARLY_HEARTBEAT_CORE_ID_MAIN0_0;
}

static void sleep_ms(unsigned int delay_ms)
{
    struct timespec req;

    req.tv_sec = (time_t)(delay_ms / 1000U);
    req.tv_nsec = (long)((delay_ms % 1000U) * 1000000U);
    nanosleep(&req, NULL);
}

static int read_snapshot(EarlyHeartbeatStatus *snapshot)
{
    long page_size;
    off_t page_base;
    off_t page_offset;
    size_t map_size;
    int fd;
    void *mapping;
    volatile const EarlyHeartbeatStatus *status;
    unsigned int attempt;

    page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0) {
        fprintf(stderr, "failed to determine page size\n");
        return -1;
    }

    page_base = (off_t)(EARLY_HEARTBEAT_SHM_BASE_ADDR & ~((uint64_t)page_size - 1ULL));
    page_offset = (off_t)(EARLY_HEARTBEAT_SHM_BASE_ADDR - (uint64_t)page_base);
    map_size = (size_t)page_offset + sizeof(*snapshot);

    fd = open(DEVMEM_PATH, O_RDONLY | O_SYNC);
    if (fd < 0) {
        perror(DEVMEM_PATH);
        return -1;
    }

    mapping = mmap(NULL, map_size, PROT_READ, MAP_SHARED, fd, page_base);
    if (mapping == MAP_FAILED) {
        perror("mmap");
        close(fd);
        return -1;
    }

    status = (volatile const EarlyHeartbeatStatus *)((const char *)mapping + page_offset);
    for (attempt = 0U; attempt < SNAPSHOT_RETRIES; attempt++) {
        *snapshot = *status;
        if (snapshot_looks_valid(snapshot)) {
            munmap(mapping, map_size);
            close(fd);
            return 0;
        }

        sleep_ms(1U);
    }

    fprintf(stderr,
            "failed to read a valid SHM snapshot at 0x%08" PRIx32 "\n",
            EARLY_HEARTBEAT_SHM_BASE_ADDR);
    munmap(mapping, map_size);
    close(fd);
    return -1;
}

static void print_snapshot(const char *label, const EarlyHeartbeatStatus *snapshot)
{
    printf("[%s]\n", label);
    printf("base=0x%08" PRIx32 "\n", EARLY_HEARTBEAT_SHM_BASE_ADDR);
    printf("size_bytes=0x%08" PRIx32 "\n", EARLY_HEARTBEAT_SHM_SIZE_BYTES);
    printf("magic=0x%08" PRIx32 "\n", snapshot->magic);
    printf("version=0x%08" PRIx32 "\n", snapshot->version);
    printf("abi_size=%" PRIu32 "\n", snapshot->abi_size);
    printf("seq=%" PRIu32 "\n", snapshot->seq);
    printf("uptime_ms=%" PRIu32 "\n", snapshot->uptime_ms);
    printf("heartbeat=%" PRIu32 "\n", snapshot->heartbeat);
    printf("shm_update_count=%" PRIu32 "\n", snapshot->shm_update_count);
    printf("shm_update_period_ms=%" PRIu32 "\n", snapshot->shm_update_period_ms);
    printf("core=0x%08" PRIx32 "\n", snapshot->core);
}

static int command_status(void)
{
    EarlyHeartbeatStatus snapshot;

    if (read_snapshot(&snapshot) != 0)
        return 1;

    print_snapshot("snapshot", &snapshot);
    printf("STATUS: PASS\n");
    return 0;
}

static int command_verify(unsigned int interval_ms)
{
    EarlyHeartbeatStatus first;
    EarlyHeartbeatStatus second;

    if (read_snapshot(&first) != 0)
        return 1;

    sleep_ms(interval_ms);

    if (read_snapshot(&second) != 0)
        return 1;

    print_snapshot("snapshot-1", &first);
    print_snapshot("snapshot-2", &second);

    if (second.seq <= first.seq ||
        second.heartbeat <= first.heartbeat ||
        second.shm_update_count <= first.shm_update_count) {
        fprintf(stderr,
                "heartbeat did not advance across %u ms interval\n",
                interval_ms);
        printf("STATUS: FAIL\n");
        return 2;
    }

    printf("verify_interval_ms=%u\n", interval_ms);
    printf("seq_delta=%" PRIu32 "\n", second.seq - first.seq);
    printf("heartbeat_delta=%" PRIu32 "\n", second.heartbeat - first.heartbeat);
    printf("shm_update_count_delta=%" PRIu32 "\n", second.shm_update_count - first.shm_update_count);
    printf("STATUS: PASS\n");
    return 0;
}

int main(int argc, char **argv)
{
    unsigned int interval_ms = DEFAULT_VERIFY_INTERVAL_MS;

    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "status") == 0) {
        return command_status();
    }

    if (strcmp(argv[1], "verify") == 0) {
        if (argc >= 3 && parse_interval_ms(argv[2], &interval_ms) != 0) {
            fprintf(stderr, "invalid interval_ms: %s\n", argv[2]);
            return 1;
        }

        return command_verify(interval_ms);
    }

    usage(argv[0]);
    return 1;
}
