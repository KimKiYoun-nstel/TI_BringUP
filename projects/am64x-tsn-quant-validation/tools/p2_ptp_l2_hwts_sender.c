// Native P2 critical sender: P2_VLAN_PCP selects the on-wire PCP (default: 2).
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/if_packet.h>
#include <linux/net_tstamp.h>
#include <net/if.h>
#include <netinet/ether.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define SOL_PACKET 263
#define PACKET_IGNORE_OUTGOING 23
#define SCM_TIMESTAMPING SO_TIMESTAMPING

struct row {
    unsigned sequence;
    long long planned;
    long long enqueue_due;
    long long enqueue_actual;
    long long timestamp;
    int seen;
};

static long long monotonic_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static long long clock_ns(clockid_t clock) {
    struct timespec ts;
    clock_gettime(clock, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static int wait_until(clockid_t clock, long long ns) {
    long long now = clock_ns(clock);
    long long remaining = ns - now;
    if (remaining <= 0) return 0;
    long long monotonic_target = monotonic_ns() + remaining;
    struct timespec target = { .tv_sec = monotonic_target / 1000000000LL, .tv_nsec = monotonic_target % 1000000000LL };
    int error;
    do {
        error = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &target, NULL);
    } while (error == EINTR);
    if (error) {
        errno = error;
        return -1;
    }
    while (clock_ns(clock) < ns) { }
    return 0;
}

static int configure_realtime(void) {
    const char *priority_text = getenv("P2_SCHED_FIFO_PRIORITY");
    if (!priority_text || !*priority_text) return 0;
    char *end;
    long priority = strtol(priority_text, &end, 0);
    if (*end || priority < 1 || priority > 99) {
        fprintf(stderr, "P2_SCHED_FIFO_PRIORITY must be in 1..99\n");
        return -1;
    }
    struct sched_param param = { .sched_priority = (int)priority };
    if (sched_setscheduler(0, SCHED_FIFO, &param) < 0) {
        perror("sched_setscheduler");
        return -1;
    }
    return 1;
}

static int restore_normal_policy(void) {
    struct sched_param param = { .sched_priority = 0 };
    if (sched_setscheduler(0, SCHED_OTHER, &param) < 0) {
        perror("sched_setscheduler(SCHED_OTHER)");
        return -1;
    }
    return 0;
}

static void make_frame(unsigned char *frame, const unsigned char *mac, unsigned sequence,
                       unsigned pcp) {
    static const unsigned char dst[6] = {0x01, 0x1b, 0x19, 0, 0, 0};
    memset(frame, 0, 128);
    memcpy(frame, dst, 6); memcpy(frame + 6, mac, 6);
    unsigned tci = (pcp << 13) | 311;
    frame[12] = 0x81; frame[13] = 0x00; frame[14] = tci >> 8; frame[15] = tci;
    frame[16] = 0x88; frame[17] = 0xf7;
    frame[18] = 0x00; frame[19] = 0x02; frame[20] = 0x00; frame[21] = 44;
    frame[22] = 127; frame[24] = 0x02;
    frame[38] = mac[0]; frame[39] = mac[1]; frame[40] = mac[2]; frame[41] = 0xff;
    frame[42] = 0xfe; frame[43] = mac[3]; frame[44] = mac[4]; frame[45] = mac[5];
    frame[46] = 0; frame[47] = 1;
    frame[48] = sequence >> 8; frame[49] = sequence;
    frame[51] = 0x7f;
    frame[58] = sequence >> 24; frame[59] = sequence >> 16;
    frame[60] = sequence >> 8; frame[61] = sequence;
}

static void drain_errors(int fd, struct row *rows, unsigned first, unsigned count) {
    for (;;) {
        unsigned char data[256], control[256];
        struct iovec iov = { data, sizeof(data) };
        struct msghdr msg = { .msg_iov = &iov, .msg_iovlen = 1, .msg_control = control, .msg_controllen = sizeof(control) };
        if (recvmsg(fd, &msg, MSG_ERRQUEUE | MSG_DONTWAIT) < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) return;
            return;
        }
        if (msg.msg_iov->iov_len < 64) continue;
        unsigned sequence = ((unsigned)data[58] << 24) | ((unsigned)data[59] << 16) | ((unsigned)data[60] << 8) | data[61];
        if (sequence < first || sequence >= first + count) continue;
        for (struct cmsghdr *c = CMSG_FIRSTHDR(&msg); c; c = CMSG_NXTHDR(&msg, c)) {
            if (c->cmsg_level != SOL_SOCKET || c->cmsg_type != SCM_TIMESTAMPING) continue;
            struct timespec *ts = (struct timespec *)CMSG_DATA(c);
            if (ts[2].tv_sec || ts[2].tv_nsec) { rows[sequence - first].timestamp = (long long)ts[2].tv_sec * 1000000000LL + ts[2].tv_nsec; rows[sequence - first].seen = 1; }
        }
    }
}

int main(int argc, char **argv) {
    if (argc != 6 && argc != 9 && argc != 10) { fprintf(stderr, "usage: %s iface count start-seq interval-us csv [base-time-ns release-phase-ns cycle-ns enqueue-advance-ns]\n", argv[0]); return 2; }
    const char *iface = argv[1], *csv = argv[5], *pcp_env = getenv("P2_VLAN_PCP");
    unsigned count = strtoul(argv[2], 0, 0), first = strtoul(argv[3], 0, 0), interval_us = strtoul(argv[4], 0, 0);
    unsigned pcp = pcp_env ? strtoul(pcp_env, 0, 0) : 2;
    if (pcp > 7) { fprintf(stderr, "P2_VLAN_PCP must be in 0..7\n"); return 2; }
    long long base_time = argc >= 9 ? strtoll(argv[6], 0, 0) : 0, phase = argc >= 9 ? strtoll(argv[7], 0, 0) : 0, cycle = argc >= 9 ? strtoll(argv[8], 0, 0) : 0;
    long long enqueue_advance = argc == 10 ? strtoll(argv[9], 0, 0) : 0;
    if (enqueue_advance < 0) { fprintf(stderr, "enqueue-advance-ns must not be negative\n"); return 2; }
    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_1588)); if (fd < 0) { perror("socket"); return 1; }
    struct ifreq ifr = {0}; strncpy(ifr.ifr_name, iface, IFNAMSIZ - 1); if (ioctl(fd, SIOCGIFHWADDR, &ifr) < 0) { perror("SIOCGIFHWADDR"); return 1; }
    struct sockaddr_ll bind_addr = { .sll_family = AF_PACKET, .sll_ifindex = if_nametoindex(iface), .sll_protocol = htons(ETH_P_1588) };
    if (bind(fd, (struct sockaddr *)&bind_addr, sizeof(bind_addr)) < 0) { perror("bind"); return 1; }
    int flags = SOF_TIMESTAMPING_TX_HARDWARE | SOF_TIMESTAMPING_TX_SOFTWARE | SOF_TIMESTAMPING_SOFTWARE | SOF_TIMESTAMPING_RAW_HARDWARE, priority = 3, ignore = 1, rcvbuf = 4 * 1024 * 1024;
    setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rcvbuf, sizeof(rcvbuf));
    setsockopt(fd, SOL_SOCKET, SO_TIMESTAMPING, &flags, sizeof(flags)); setsockopt(fd, SOL_SOCKET, SO_PRIORITY, &priority, sizeof(priority)); setsockopt(fd, SOL_PACKET, PACKET_IGNORE_OUTGOING, &ignore, sizeof(ignore)); fcntl(fd, F_SETFL, O_NONBLOCK);
    int phc = argc >= 9 ? open("/dev/ptp0", O_RDONLY) : -1;
    clockid_t phc_clock = phc < 0 ? CLOCK_MONOTONIC : ((~(clockid_t)phc << 3) | 3);
    if (argc >= 9 && base_time == 0) base_time = (clock_ns(phc_clock) + 2000000000LL + cycle - 1) / cycle * cycle;
    int realtime = configure_realtime();
    if (realtime < 0) return 1;
    struct row *rows = calloc(count, sizeof(*rows)); unsigned char frame[128]; long long start = monotonic_ns();
    for (unsigned i = 0; i < count; i++) {
        long long release = argc >= 9 ? base_time + phase + (long long)i * interval_us * 1000LL : 0;
        long long enqueue_due = argc >= 9 ? release - enqueue_advance : start + (long long)i * interval_us * 1000LL;
        if (wait_until(phc_clock, enqueue_due)) { perror("clock_nanosleep"); return 1; }
        rows[i].planned = release;
        rows[i].enqueue_due = argc >= 9 ? enqueue_due : 0;
        rows[i].enqueue_actual = argc >= 9 ? clock_ns(phc_clock) : 0;
        make_frame(frame, (unsigned char *)ifr.ifr_hwaddr.sa_data, first + i, pcp);
        if (send(fd, frame, sizeof(frame), 0) < 0) perror("send");
        drain_errors(fd, rows, first, count);
    }
    // Do not let the timestamp collection loop delay same-core gPTP service.
    if (realtime && restore_normal_policy()) return 1;
    long long deadline = monotonic_ns() + 3000000000LL; while (monotonic_ns() < deadline) { drain_errors(fd, rows, first, count); unsigned seen = 0; for (unsigned i = 0; i < count; i++) seen += rows[i].seen; if (seen == count) break; }
    FILE *out = fopen(csv, "w"); fprintf(out, "sequence,planned_phc_ns,enqueue_due_phc_ns,enqueue_actual_phc_ns,timestamp_source,timestamp_ns\n"); unsigned seen = 0; for (unsigned i = 0; i < count; i++) { fprintf(out, "%u,%lld,%lld,%lld,%s,%lld\n", first + i, rows[i].planned, rows[i].enqueue_due, rows[i].enqueue_actual, rows[i].seen ? "raw_hw" : "none", rows[i].timestamp); seen += rows[i].seen; } fclose(out); printf("{\"count\":%u,\"pcp\":%u,\"raw_hw\":%u,\"enqueue_advance_ns\":%lld}\n", count, pcp, seen, enqueue_advance);
    return seen == count ? 0 : 1;
}
