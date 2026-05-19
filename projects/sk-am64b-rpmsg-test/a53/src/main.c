// SPDX-License-Identifier: BSD-3-Clause

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <rproc_id.h>
#include <ti_rpmsg_char.h>

#define APP_SERVICE_NAME     "rpmsg_chrdev"
#define APP_SERVICE_ENDPOINT 14U
#define APP_EPT_NAME         "sk-am64b-a53-rpmsg"
#define APP_BUF_SIZE         496U

static void die(const char *what)
{
    perror(what);
    exit(1);
}

int main(int argc, char **argv)
{
    const char *payload = argc > 1 ? argv[1] : "hello-from-a53";
    rpmsg_char_dev_t *dev;
    char rx[APP_BUF_SIZE + 1];
    ssize_t tx_len;
    ssize_t rx_len;

    if (rpmsg_char_init(NULL) < 0) {
        fprintf(stderr, "rpmsg_char_init failed\n");
        return 1;
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
        return 1;
    }

    tx_len = (ssize_t)strlen(payload);
    if (write(dev->fd, payload, (size_t)tx_len) != tx_len) {
        rpmsg_char_close(dev);
        rpmsg_char_exit();
        die("write");
    }

    rx_len = read(dev->fd, rx, APP_BUF_SIZE);
    if (rx_len < 0) {
        rpmsg_char_close(dev);
        rpmsg_char_exit();
        die("read");
    }

    rx[rx_len] = '\0';
    printf("TX: %s\n", payload);
    printf("RX: %s\n", rx);

    if ((size_t)rx_len != (size_t)tx_len || memcmp(payload, rx, (size_t)tx_len) != 0) {
        fprintf(stderr, "payload mismatch\n");
        rpmsg_char_close(dev);
        rpmsg_char_exit();
        return 2;
    }

    printf("STATUS: PASS\n");

    rpmsg_char_close(dev);
    rpmsg_char_exit();
    return 0;
}
