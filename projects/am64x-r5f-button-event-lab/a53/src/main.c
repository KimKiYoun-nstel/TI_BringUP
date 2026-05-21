// SPDX-License-Identifier: BSD-3-Clause

#include <errno.h>
#include <fcntl.h>
#include <glob.h>
#include <limits.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

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

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage:\n"
            "  %s ping\n"
            "  %s status\n"
            "  %s button status\n"
            "  %s button wait [timeout_ms]\n"
            "  %s button monitor\n"
            "  %s event monitor\n"
            "  %s trace\n",
            prog, prog, prog, prog, prog, prog, prog);
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

    if (strncmp(rx, "OK", 2U) != 0 && strncmp(rx, "BUTTON_EVENT", 12U) != 0) {
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

    printf("# monitoring BUTTON_EVENT lines; press Ctrl-C to stop\n");
    while (1) {
        if (poll_read_response(dev, rx, sizeof(rx), -1) != 0) {
            rc = 1;
            goto out;
        }
        if (strncmp(rx, "BUTTON_EVENT", 12U) == 0) {
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
