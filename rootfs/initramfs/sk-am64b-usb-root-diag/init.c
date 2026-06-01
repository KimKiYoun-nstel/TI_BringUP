#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <dirent.h>

#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))

static const char *diag_prefix = "N17DIAG";
static const char *root_device = "/dev/sda3";
static const char *root_fstype = "ext4";
static unsigned int timeout_secs = 120;
static unsigned int poll_secs = 1;

static void log_line(const char *fmt, ...)
{
    char body[1024];
    char line[1152];
    va_list ap;
    int console_fd;
    int kmsg_fd;
    size_t len;

    va_start(ap, fmt);
    vsnprintf(body, sizeof(body), fmt, ap);
    va_end(ap);

    snprintf(line, sizeof(line), "%s: %s\n", diag_prefix, body);
    len = strlen(line);

    console_fd = open("/dev/console", O_WRONLY | O_CLOEXEC);
    if (console_fd >= 0) {
        ssize_t written = write(console_fd, line, len);
        (void)written;
        close(console_fd);
    }

    kmsg_fd = open("/dev/kmsg", O_WRONLY | O_CLOEXEC);
    if (kmsg_fd >= 0) {
        ssize_t written = write(kmsg_fd, line, len);
        (void)written;
        close(kmsg_fd);
    }
}

static void ensure_dir(const char *path, mode_t mode)
{
    struct stat st;

    if (stat(path, &st) == 0) {
        return;
    }

    if (mkdir(path, mode) < 0 && errno != EEXIST) {
        log_line("mkdir failed for %s: %s", path, strerror(errno));
    }
}

static void parse_cmdline(void)
{
    FILE *fp;
    char buf[2048];
    char *tok;

    fp = fopen("/proc/cmdline", "r");
    if (!fp) {
        log_line("failed to open /proc/cmdline: %s", strerror(errno));
        return;
    }

    if (!fgets(buf, sizeof(buf), fp)) {
        fclose(fp);
        return;
    }
    fclose(fp);

    tok = strtok(buf, " \t\r\n");
    while (tok) {
        if (strncmp(tok, "diag.rootdev=", 13) == 0) {
            root_device = tok + 13;
        } else if (strncmp(tok, "diag.timeout=", 13) == 0) {
            timeout_secs = (unsigned int)strtoul(tok + 13, NULL, 10);
        } else if (strncmp(tok, "diag.poll=", 10) == 0) {
            poll_secs = (unsigned int)strtoul(tok + 10, NULL, 10);
        } else if (strncmp(tok, "diag.rootfstype=", 16) == 0) {
            root_fstype = tok + 16;
        }
        tok = strtok(NULL, " \t\r\n");
    }

    if (poll_secs == 0) {
        poll_secs = 1;
    }
}

static void mount_basics(void)
{
    ensure_dir("/proc", 0555);
    ensure_dir("/sys", 0555);
    ensure_dir("/dev", 0755);
    ensure_dir("/run", 0755);
    ensure_dir("/tmp", 01777);
    ensure_dir("/sys/kernel", 0555);
    ensure_dir("/sys/kernel/debug", 0555);
    ensure_dir("/newroot", 0755);

    if (mount("proc", "/proc", "proc", 0, "") < 0 && errno != EBUSY) {
        log_line("mount proc failed: %s", strerror(errno));
    }
    if (mount("sysfs", "/sys", "sysfs", 0, "") < 0 && errno != EBUSY) {
        log_line("mount sysfs failed: %s", strerror(errno));
    }
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, "mode=0755") < 0 && errno != EBUSY) {
        log_line("mount devtmpfs failed: %s", strerror(errno));
    }
    if (mount("tmpfs", "/run", "tmpfs", 0, "mode=0755") < 0 && errno != EBUSY) {
        log_line("mount run tmpfs failed: %s", strerror(errno));
    }
    if (mount("debugfs", "/sys/kernel/debug", "debugfs", 0, "") < 0 && errno != EBUSY) {
        log_line("mount debugfs failed: %s", strerror(errno));
    }
}

static void dump_file_lines(const char *path, unsigned int max_lines)
{
    FILE *fp;
    char buf[256];
    unsigned int count = 0;

    fp = fopen(path, "r");
    if (!fp) {
        log_line("open %s failed: %s", path, strerror(errno));
        return;
    }

    while (fgets(buf, sizeof(buf), fp) && count < max_lines) {
        size_t len = strlen(buf);
        if (len > 0 && buf[len - 1] == '\n') {
            buf[len - 1] = '\0';
        }
        log_line("%s: %s", path, buf);
        count++;
    }
    fclose(fp);
}

static void dump_dir_names(const char *path, unsigned int max_entries)
{
    DIR *dir;
    struct dirent *de;
    unsigned int count = 0;

    dir = opendir(path);
    if (!dir) {
        log_line("opendir %s failed: %s", path, strerror(errno));
        return;
    }

    while ((de = readdir(dir)) != NULL && count < max_entries) {
        if (strcmp(de->d_name, ".") == 0 || strcmp(de->d_name, "..") == 0) {
            continue;
        }
        log_line("%s entry: %s", path, de->d_name);
        count++;
    }

    closedir(dir);
}

static bool file_exists(const char *path)
{
    return access(path, F_OK) == 0;
}

static int try_switch_root(void)
{
    char *const argv[] = { "/sbin/init", NULL };

    ensure_dir("/newroot/proc", 0555);
    ensure_dir("/newroot/sys", 0555);
    ensure_dir("/newroot/dev", 0755);
    ensure_dir("/newroot/run", 0755);

    if (mount("/proc", "/newroot/proc", NULL, MS_MOVE, NULL) < 0) {
        log_line("move /proc failed: %s", strerror(errno));
        return -1;
    }
    if (mount("/sys", "/newroot/sys", NULL, MS_MOVE, NULL) < 0) {
        log_line("move /sys failed: %s", strerror(errno));
        return -1;
    }
    if (mount("/dev", "/newroot/dev", NULL, MS_MOVE, NULL) < 0) {
        log_line("move /dev failed: %s", strerror(errno));
        return -1;
    }
    if (mount("/run", "/newroot/run", NULL, MS_MOVE, NULL) < 0) {
        log_line("move /run failed: %s", strerror(errno));
        return -1;
    }

    if (chdir("/newroot") < 0) {
        log_line("chdir /newroot failed: %s", strerror(errno));
        return -1;
    }
    if (chroot(".") < 0) {
        log_line("chroot failed: %s", strerror(errno));
        return -1;
    }
    if (chdir("/") < 0) {
        log_line("chdir / failed after chroot: %s", strerror(errno));
        return -1;
    }

    log_line("executing /sbin/init from switched root");
    execv("/sbin/init", argv);
    log_line("exec /sbin/init failed: %s", strerror(errno));
    return -1;
}

static int try_mount_root(void)
{
    if (mount(root_device, "/newroot", root_fstype, 0, "") < 0) {
        log_line("mount %s on /newroot failed: %s", root_device, strerror(errno));
        return -1;
    }

    log_line("mounted %s on /newroot", root_device);

    if (!file_exists("/newroot/sbin/init")) {
        log_line("/newroot/sbin/init not found after mount");
        return -1;
    }

    return try_switch_root();
}

static void snapshot(unsigned int elapsed)
{
    log_line("snapshot t=%u rootdev=%s", elapsed, root_device);
    dump_file_lines("/proc/cmdline", 1);
    dump_file_lines("/sys/kernel/debug/devices_deferred", 32);
    dump_dir_names("/sys/bus/usb/devices", 32);
    dump_dir_names("/sys/class/block", 32);
}

int main(void)
{
    unsigned int elapsed = 0;
    const unsigned int checkpoints[] = {0, 5, 10, 20, 30, 60, 90, 120};
    size_t checkpoint_idx = 0;

    mount_basics();
    parse_cmdline();

    log_line("start rootdev=%s rootfstype=%s timeout=%u poll=%u", root_device, root_fstype, timeout_secs, poll_secs);

    for (;;) {
        bool do_snapshot = false;

        if (checkpoint_idx < ARRAY_SIZE(checkpoints) && elapsed >= checkpoints[checkpoint_idx]) {
            do_snapshot = true;
            checkpoint_idx++;
        }
        if (do_snapshot) {
            snapshot(elapsed);
        }

        if (file_exists(root_device)) {
            log_line("root device present: %s", root_device);
            snapshot(elapsed);
            if (try_mount_root() == 0) {
                return 0;
            }
        }

        if (elapsed >= timeout_secs) {
            log_line("timeout waiting for %s; leaving system to watchdog reset", root_device);
            snapshot(elapsed);
            for (;;) {
                pause();
            }
        }

        sleep(poll_secs);
        elapsed += poll_secs;
    }
}
