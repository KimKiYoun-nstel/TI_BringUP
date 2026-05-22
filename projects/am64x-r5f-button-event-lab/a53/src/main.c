// SPDX-License-Identifier: BSD-3-Clause

#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <unistd.h>

#include "../../include/r5f_status_shm.h"

#include <rproc_id.h>
#include <ti_rpmsg_char.h>

#define APP_SERVICE_NAME     "rpmsg_chrdev"
#define APP_SERVICE_ENDPOINT 14U
#define APP_EPT_NAME         "am64x-r5ctl"
#define APP_BUF_SIZE         496U
#define TRACE_BUF_SIZE       512U
#define APP_REPLY_TIMEOUT_MS 3000
#define APP_WAIT_DEFAULT_MS  5000
#define APP_WAIT_MAX_MS      60000
#define REMOTEPROC_GLOB      "/sys/class/remoteproc/remoteproc*/name"
#define DEBUGFS_PREFIX       "/sys/kernel/debug/remoteproc/"
#define TRACE_SUFFIX         "/trace0"
#define TARGET_R5F_NAME      "78000000.r5f"
#define DEVMEM_PATH          "/dev/mem"
#define SHM_READ_RETRIES     16U

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage:\n"
            "  %s ping\n"
            "  %s status\n"
            "  %s gpio list\n"
            "  %s gpio get <id>\n"
            "  %s gpio set <id> <0|1>\n"
            "  %s event get\n"
            "  %s event monitor\n"
            "  %s button status\n"
            "  %s button wait [timeout_ms]\n"
            "  %s button monitor\n"
            "  %s shm-status\n"
            "  %s trace\n",
            prog, prog, prog, prog, prog, prog, prog, prog, prog, prog, prog, prog);
}

static const char *event_type_name(uint32_t event_type)
{
    switch (event_type) {
    case 1U:
        return "rising";
    case 2U:
        return "falling";
    case 3U:
        return "changed";
    default:
        return "none";
    }
}

static const char *last_error_name(uint32_t status)
{
    switch (status) {
    case 0U:
        return "OK";
    case 1U:
        return "ERR_UNKNOWN_CMD";
    case 2U:
        return "ERR_BAD_ARG";
    case 3U:
        return "ERR_BUSY";
    case 4U:
        return "ERR_HW_FAIL";
    case 5U:
        return "ERR_TIMEOUT";
    default:
        return "ERR_UNKNOWN";
    }
}

static const char *temperature_error_name(uint32_t error)
{
    switch (error) {
    case R5F_STATUS_SHM_TEMP_ERR_NONE:
        return "OK";
    case R5F_STATUS_SHM_TEMP_ERR_UNAVAIL:
        return "UNAVAILABLE";
    case R5F_STATUS_SHM_TEMP_ERR_RANGE:
        return "RANGE";
    default:
        return "UNKNOWN";
    }
}

typedef struct
{
    int found;
    int temp_millicelsius;
} hwmon_ref_t;

static int read_first_line(const char *path, char *buf, size_t buf_size)
{
    FILE *fp;

    if (buf_size == 0U) {
        return -1;
    }

    fp = fopen(path, "r");
    if (fp == NULL) {
        return -1;
    }
    if (fgets(buf, buf_size, fp) == NULL) {
        fclose(fp);
        return -1;
    }
    fclose(fp);

    buf[strcspn(buf, "\r\n")] = '\0';
    return 0;
}

static hwmon_ref_t print_hwmon_reference(const char *thermal_name)
{
    glob_t matches;
    size_t i;
    hwmon_ref_t ref = {0, 0};

    if (glob("/sys/class/hwmon/hwmon*", 0, NULL, &matches) != 0) {
        printf("linux_hwmon name=%s status=not_found\n", thermal_name);
        return ref;
    }

    for (i = 0; i < matches.gl_pathc; i++) {
        char name_path[PATH_MAX];
        char temp_path[PATH_MAX];
        char name[64];
        char temp[64];

        if (snprintf(name_path, sizeof(name_path), "%s/name", matches.gl_pathv[i]) >= (int)sizeof(name_path)) {
            continue;
        }
        if (read_first_line(name_path, name, sizeof(name)) != 0 || strcmp(name, thermal_name) != 0) {
            continue;
        }

        ref.found = 1;
        if (snprintf(temp_path, sizeof(temp_path), "%s/temp1_input", matches.gl_pathv[i]) >= (int)sizeof(temp_path) ||
            read_first_line(temp_path, temp, sizeof(temp)) != 0) {
            printf("linux_hwmon name=%s path=%s status=temp_unavailable\n", thermal_name, matches.gl_pathv[i]);
        } else {
            ref.temp_millicelsius = atoi(temp);
            printf("linux_hwmon name=%s path=%s temp1_input_millicelsius=%s\n",
                   thermal_name,
                   matches.gl_pathv[i],
                   temp);
        }
        break;
    }

    if (ref.found == 0) {
        printf("linux_hwmon name=%s status=not_found\n", thermal_name);
    }

    globfree(&matches);
    return ref;
}

static void print_temperature_field(const char *name,
                                    uint32_t valid,
                                    uint32_t raw,
                                    int32_t milli_celsius,
                                    uint32_t last_error)
{
    if (valid == R5F_STATUS_SHM_TEMP_VALID) {
        printf("%s_valid=1\n", name);
        printf("%s_raw=%" PRIu32 "\n", name, raw);
        printf("%s_millicelsius=%" PRId32 "\n", name, milli_celsius);
    } else {
        printf("%s_valid=0\n", name);
        printf("%s_raw=unavailable\n", name);
        printf("%s_millicelsius=unavailable\n", name);
    }
    printf("%s_last_error=%s\n", name, temperature_error_name(last_error));
}

static int read_shm_snapshot(r5f_status_shm_t *snapshot)
{
    long page_size = sysconf(_SC_PAGESIZE);
    off_t page_base;
    off_t page_offset;
    size_t map_size;
    int fd;
    void *mapping;
    volatile const r5f_status_shm_t *shm;
    unsigned int attempt;

    if (page_size <= 0) {
        fprintf(stderr, "failed to determine page size\n");
        return -1;
    }

    page_base = (off_t)(R5F_STATUS_SHM_BASE & ~((uint64_t)page_size - 1ULL));
    page_offset = (off_t)(R5F_STATUS_SHM_BASE - (uint64_t)page_base);
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

    shm = (volatile const r5f_status_shm_t *)((const char *)mapping + page_offset);
    for (attempt = 0U; attempt < SHM_READ_RETRIES; attempt++) {
        uint32_t seq_begin = shm->seq_begin;
        uint32_t seq_end;

        *snapshot = *shm;
        seq_end = shm->seq_end;
        if (seq_begin == snapshot->seq_begin &&
            seq_end == snapshot->seq_end &&
            snapshot->seq_begin == snapshot->seq_end &&
            snapshot->magic == R5F_STATUS_SHM_MAGIC &&
            snapshot->version == R5F_STATUS_SHM_VERSION &&
            snapshot->size == sizeof(*snapshot)) {
            munmap(mapping, map_size);
            close(fd);
            return 0;
        }

        usleep(1000U);
    }

    fprintf(stderr, "failed to read a consistent SHM snapshot at 0x%" PRIx64 "\n", (uint64_t)R5F_STATUS_SHM_BASE);
    munmap(mapping, map_size);
    close(fd);
    return -1;
}

static int show_shm_status(void)
{
    r5f_status_shm_t snapshot;
    hwmon_ref_t main0_ref;
    hwmon_ref_t main1_ref;

    if (read_shm_snapshot(&snapshot) != 0) {
        return 1;
    }

    printf("SHM status base=0x%" PRIx64 " size=0x%" PRIx64 "\n",
           (uint64_t)R5F_STATUS_SHM_BASE,
           (uint64_t)R5F_STATUS_SHM_SIZE);
    printf("magic=0x%08" PRIx32 "\n", snapshot.magic);
    printf("version=0x%08" PRIx32 "\n", snapshot.version);
    printf("abi_size=%" PRIu32 "\n", snapshot.size);
    printf("seq=%" PRIu32 "\n", snapshot.seq_end);
    printf("uptime_ms=%" PRIu32 "\n", snapshot.uptime_ms);
    printf("heartbeat=%" PRIu32 "\n", snapshot.heartbeat);
    printf("shm_update_count=%" PRIu32 "\n", snapshot.shm_update_count);
    printf("main_loop_count=%" PRIu32 "\n", snapshot.main_loop_count);
    printf("core=0x%08" PRIx32 "\n", snapshot.core_id);
    printf("rpmsg_endpoint=%" PRIu32 "\n", snapshot.rpmsg_endpoint);
    printf("rpmsg_rx_count=%" PRIu32 "\n", snapshot.rpmsg_rx_count);
    printf("rpmsg_tx_count=%" PRIu32 "\n", snapshot.rpmsg_tx_count);
    printf("rpmsg_error_count=%" PRIu32 "\n", snapshot.rpmsg_error_count);
    printf("last_command_id=0x%04" PRIx32 "\n", snapshot.last_command_id);
    printf("last_error=%s\n", last_error_name(snapshot.last_error));
    printf("output_gpio_id=mcu_gpio0_8\n");
    printf("output_state=%" PRIu32 "\n", snapshot.output_gpio_state);
    printf("input_gpio_id=mcu_gpio0_6\n");
    printf("input_state=%" PRIu32 "\n", snapshot.input_gpio_state);
    printf("event_count=%" PRIu32 "\n", snapshot.gpio_event_count);
    printf("last_event_type=%s\n", event_type_name(snapshot.last_event_type));
    printf("last_event_gpio_id=%" PRIu32 "\n", snapshot.last_event_gpio_id);
    printf("last_event_timestamp_us=%" PRIu64 "\n", snapshot.last_event_timestamp_us);
    printf("shm_update_period_ms=%" PRIu32 "\n", snapshot.shm_update_period_ms);
    print_temperature_field("soc_temp0", snapshot.soc_temp0_valid, snapshot.soc_temp0_raw,
                            snapshot.soc_temp0_milli_celsius, snapshot.soc_temp0_last_error);
    print_temperature_field("soc_temp1", snapshot.soc_temp1_valid, snapshot.soc_temp1_raw,
                            snapshot.soc_temp1_milli_celsius, snapshot.soc_temp1_last_error);
    main0_ref = print_hwmon_reference("main0_thermal");
    main1_ref = print_hwmon_reference("main1_thermal");
    if (snapshot.soc_temp0_valid == R5F_STATUS_SHM_TEMP_VALID && main0_ref.found != 0) {
        printf("soc_temp0_delta_millicelsius=%d\n",
               snapshot.soc_temp0_milli_celsius - main0_ref.temp_millicelsius);
    }
    if (snapshot.soc_temp1_valid == R5F_STATUS_SHM_TEMP_VALID && main1_ref.found != 0) {
        printf("soc_temp1_delta_millicelsius=%d\n",
               snapshot.soc_temp1_milli_celsius - main1_ref.temp_millicelsius);
    }

    return 0;
}

static int parse_timeout_ms(const char *text, long *timeout_ms)
{
    char *end = NULL;

    errno = 0;
    *timeout_ms = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' ||
        *timeout_ms < 0 || *timeout_ms > APP_WAIT_MAX_MS) {
        return -1;
    }

    return 0;
}

static int build_command(int argc, char **argv, char *tx, size_t tx_size)
{
    int written = -1;

    if (argc < 2) {
        return -1;
    }

    if (strcmp(argv[1], "ping") == 0 && argc == 2) {
        written = snprintf(tx, tx_size, "PING");
    } else if (strcmp(argv[1], "status") == 0 && argc == 2) {
        written = snprintf(tx, tx_size, "STATUS");
    } else if (strcmp(argv[1], "gpio") == 0 && argc >= 3) {
        if (strcmp(argv[2], "list") == 0 && argc == 3) {
            written = snprintf(tx, tx_size, "GPIO_LIST");
        } else if (strcmp(argv[2], "get") == 0 && argc == 4) {
            written = snprintf(tx, tx_size, "GPIO_GET %s", argv[3]);
        } else if (strcmp(argv[2], "set") == 0 && argc == 5 &&
                   (strcmp(argv[4], "0") == 0 || strcmp(argv[4], "1") == 0)) {
            written = snprintf(tx, tx_size, "GPIO_SET %s %s", argv[3], argv[4]);
        } else {
            return -1;
        }
    } else if (strcmp(argv[1], "event") == 0 && argc >= 3) {
        if (strcmp(argv[2], "get") == 0 && argc == 3) {
            written = snprintf(tx, tx_size, "EVENT_GET");
        } else {
            return -1;
        }
    } else if (strcmp(argv[1], "button") == 0 && argc >= 3) {
        if (strcmp(argv[2], "status") == 0 && argc == 3) {
            written = snprintf(tx, tx_size, "BUTTON_STATUS");
        } else if (strcmp(argv[2], "wait") == 0 && (argc == 3 || argc == 4)) {
            long timeout_ms = APP_WAIT_DEFAULT_MS;

            if (argc == 4 && parse_timeout_ms(argv[3], &timeout_ms) != 0) {
                return -1;
            }
            written = snprintf(tx, tx_size, "BUTTON_WAIT %ld", timeout_ms);
        } else {
            return -1;
        }
    } else {
        return -1;
    }

    if (written < 0 || (size_t)written >= tx_size) {
        return -1;
    }

    return 0;
}

static int copy_fd_to_stdout(int fd)
{
    char buf[TRACE_BUF_SIZE];
    ssize_t len;
    int saw_data = 0;

    while ((len = read(fd, buf, sizeof(buf))) > 0) {
        const char *cursor = buf;
        ssize_t remaining = len;
        saw_data = 1;

        while (remaining > 0) {
            ssize_t written = write(STDOUT_FILENO, cursor, (size_t)remaining);
            if (written < 0) {
                return -1;
            }
            cursor += written;
            remaining -= written;
        }
    }

    if (len < 0 && saw_data == 0) {
        return -1;
    }

    return 0;
}

static int show_first_trace_match(const char *pattern)
{
    glob_t matches;
    size_t i;
    int rc;

    rc = glob(pattern, 0, NULL, &matches);
    if (rc != 0) {
        return -1;
    }

    for (i = 0; i < matches.gl_pathc; i++) {
        int fd = open(matches.gl_pathv[i], O_RDONLY);
        if (fd < 0) {
            continue;
        }

        printf("# %s\n", matches.gl_pathv[i]);
        rc = copy_fd_to_stdout(fd);
        close(fd);
        globfree(&matches);
        return rc;
    }

    globfree(&matches);
    return -1;
}

static int show_named_remoteproc_trace(void)
{
    glob_t matches;
    size_t i;
    int rc;

    rc = glob(REMOTEPROC_GLOB, 0, NULL, &matches);
    if (rc != 0) {
        return -1;
    }

    for (i = 0; i < matches.gl_pathc; i++) {
        FILE *fp;
        char name[64];
        char trace_path[256];
        const char *name_path = matches.gl_pathv[i];
        const char *suffix;
        const char *dir_start;
        const char *dir_end;
        size_t prefix_len;
        size_t dir_len;

        fp = fopen(name_path, "r");
        if (fp == NULL) {
            continue;
        }
        if (fgets(name, sizeof(name), fp) == NULL) {
            fclose(fp);
            continue;
        }
        fclose(fp);

        name[strcspn(name, "\r\n")] = '\0';
        if (strcmp(name, TARGET_R5F_NAME) != 0) {
            continue;
        }

        suffix = strstr(name_path, "/name");
        if (suffix == NULL) {
            continue;
        }

        prefix_len = (size_t)(suffix - name_path);
        if (prefix_len == 0U) {
            continue;
        }

        dir_end = name_path + prefix_len;
        dir_start = dir_end;
        while (dir_start > name_path && *(dir_start - 1) != '/') {
            dir_start--;
        }
        if (dir_start == dir_end) {
            continue;
        }

        dir_len = (size_t)(dir_end - dir_start);
        if (strlen(DEBUGFS_PREFIX) + dir_len + strlen(TRACE_SUFFIX) + 1U > sizeof(trace_path)) {
            continue;
        }

        strcpy(trace_path, DEBUGFS_PREFIX);
        memcpy(trace_path + strlen(DEBUGFS_PREFIX), dir_start, dir_len);
        strcpy(trace_path + strlen(DEBUGFS_PREFIX) + dir_len, TRACE_SUFFIX);

        printf("# %s\n", trace_path);
        {
            int fd = open(trace_path, O_RDONLY);
            if (fd < 0) {
                globfree(&matches);
                return -1;
            }
            rc = copy_fd_to_stdout(fd);
            close(fd);
            globfree(&matches);
            return rc;
        }
    }

    globfree(&matches);
    return -1;
}

static int show_trace(void)
{
    if (show_named_remoteproc_trace() == 0) {
        return 0;
    }
    if (show_first_trace_match("/sys/bus/platform/devices/78000000.r5f/remoteproc/remoteproc*/trace0") == 0) {
        return 0;
    }
    if (show_first_trace_match("/sys/kernel/debug/remoteproc/remoteproc*/trace0") == 0) {
        return 0;
    }

    fprintf(stderr, "trace0 not found; check debugfs mount and the 78000000.r5f remoteproc instance\n");
    return 1;
}

static rpmsg_char_dev_t *open_rpmsg_device(void)
{
    rpmsg_char_dev_t *dev;

    if (rpmsg_char_init(NULL) < 0) {
        fprintf(stderr, "rpmsg_char_init failed\n");
        return NULL;
    }

    dev = rpmsg_char_open(R5F_MAIN0_0,
                          APP_SERVICE_NAME,
                          RPMSG_ADDR_ANY,
                          APP_SERVICE_ENDPOINT,
                          APP_EPT_NAME,
                          O_RDWR);
    if (dev == NULL) {
        fprintf(stderr, "rpmsg_char_open failed for service %s endpoint %u\n",
                APP_SERVICE_NAME,
                APP_SERVICE_ENDPOINT);
        rpmsg_char_exit();
        return NULL;
    }

    return dev;
}

static int poll_read_response(rpmsg_char_dev_t *dev, char *rx, size_t rx_size, int timeout_ms)
{
    struct pollfd pfd;
    ssize_t rx_len;
    int poll_rc;

    pfd.fd = dev->fd;
    pfd.events = POLLIN;
    pfd.revents = 0;

    poll_rc = poll(&pfd, 1, timeout_ms);
    if (poll_rc == 0) {
        fprintf(stderr, "timeout waiting for R5F response (%d ms)\n", timeout_ms);
        return -1;
    }
    if (poll_rc < 0) {
        perror("poll");
        return -1;
    }

    rx_len = read(dev->fd, rx, rx_size - 1U);
    if (rx_len < 0) {
        perror("read");
        return -1;
    }

    rx[rx_len] = '\0';
    return 0;
}

static int write_payload(rpmsg_char_dev_t *dev, const char *payload)
{
    ssize_t tx_len = (ssize_t)strlen(payload);

    if (write(dev->fd, payload, (size_t)tx_len) != tx_len) {
        perror("write");
        return -1;
    }

    return 0;
}

static int is_event_message(const char *rx)
{
    return strncmp(rx, "GPIO_EVENT", 10U) == 0 || strncmp(rx, "BUTTON_EVENT", 12U) == 0;
}

static int send_command(const char *payload)
{
    rpmsg_char_dev_t *dev;
    char rx[APP_BUF_SIZE + 1U];
    int rc = 0;
    int timeout_ms = APP_REPLY_TIMEOUT_MS;

    if (strncmp(payload, "BUTTON_WAIT ", 12U) == 0) {
        long wait_ms;
        if (parse_timeout_ms(payload + 12, &wait_ms) == 0) {
            timeout_ms = (int)wait_ms + APP_REPLY_TIMEOUT_MS;
        }
    }

    dev = open_rpmsg_device();
    if (dev == NULL) {
        return 1;
    }

    if (write_payload(dev, payload) != 0) {
        rc = 1;
        goto out;
    }

    if (poll_read_response(dev, rx, sizeof(rx), timeout_ms) != 0) {
        rc = 1;
        goto out;
    }

    printf("TX: %s\n", payload);
    printf("RX: %s\n", rx);

    if (strncmp(rx, "OK", 2U) != 0 && !is_event_message(rx)) {
        rc = 2;
    }

out:
    rpmsg_char_close(dev);
    rpmsg_char_exit();
    return rc;
}

static int monitor_events(const char *payload)
{
    rpmsg_char_dev_t *dev;
    char rx[APP_BUF_SIZE + 1U];
    unsigned long seq = 0;
    int rc = 0;

    dev = open_rpmsg_device();
    if (dev == NULL) {
        return 1;
    }

    if (write_payload(dev, payload) != 0) {
        rc = 1;
        goto out;
    }

    if (poll_read_response(dev, rx, sizeof(rx), APP_REPLY_TIMEOUT_MS) != 0) {
        rc = 1;
        goto out;
    }
    printf("RX: %s\n", rx);
    if (strncmp(rx, "OK", 2U) != 0) {
        rc = 2;
        goto out;
    }

    printf("# monitoring GPIO_EVENT lines; press Ctrl-C to stop\n");
    while (1) {
        if (poll_read_response(dev, rx, sizeof(rx), -1) != 0) {
            rc = 1;
            goto out;
        }
        if (is_event_message(rx)) {
            seq++;
            printf("[%03lu] %s\n", seq, rx);
            fflush(stdout);
        } else {
            printf("# %s\n", rx);
            fflush(stdout);
        }
    }

out:
    rpmsg_char_close(dev);
    rpmsg_char_exit();
    return rc;
}

int main(int argc, char **argv)
{
    char tx[APP_BUF_SIZE];

    if (argc == 2 && strcmp(argv[1], "trace") == 0) {
        return show_trace();
    }

    if (argc == 2 && strcmp(argv[1], "shm-status") == 0) {
        return show_shm_status();
    }

    if (argc == 3 && strcmp(argv[1], "button") == 0 && strcmp(argv[2], "monitor") == 0) {
        return monitor_events("BUTTON_MONITOR");
    }

    if (argc == 3 && strcmp(argv[1], "event") == 0 && strcmp(argv[2], "monitor") == 0) {
        return monitor_events("EVENT_MONITOR");
    }

    if (build_command(argc, argv, tx, sizeof(tx)) != 0) {
        usage(argv[0]);
        return 1;
    }

    return send_command(tx);
}
