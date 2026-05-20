/* SPDX-License-Identifier: BSD-3-Clause */

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <kernel/dpl/ClockP.h>
#include <kernel/dpl/AddrTranslateP.h>
#include <kernel/dpl/DebugP.h>
#include <kernel/dpl/TaskP.h>
#include <drivers/gpio.h>
#include <drivers/ipc_notify.h>
#include <drivers/ipc_rpmsg.h>
#include "ti_drivers_config.h"
#include "ti_drivers_open_close.h"
#include "ti_board_open_close.h"

#define APP_LOG_PREFIX           "[AM64X R5F HWLAB]"
#define APP_SERVICE_NAME         "rpmsg_chrdev"
#define APP_SERVICE_ENDPOINT     (14U)
#define APP_MAX_MSG_SIZE         (496U)
#define APP_TASK_PRI             (4U)
#define APP_TASK_STACK_SIZE      (16U * 1024U)
#define APP_GPIO_NAME            "MCU_GPIO0_8"
#define APP_BLINK_DELAY_USEC     (200000U)
#define APP_BLINK_MAX_COUNT      (100U)

static RPMessage_Object gRecvMsgObject;
static uint8_t gRecvTaskStack[APP_TASK_STACK_SIZE] __attribute__((aligned(32)));
static TaskP_Object gRecvTask;
static uint32_t gGpioValue;
static uint32_t gGpioConfigured;
static uint32_t gGpioBaseAddr;
static uint32_t gGpioPinNum;

static void app_gpio_configure_if_needed(void)
{
    if (gGpioConfigured != 0U) {
        return;
    }

    gGpioBaseAddr = (uint32_t)AddrTranslateP_getLocalAddr(GPIO_LAB_OUT_BASE_ADDR);
    gGpioPinNum = GPIO_LAB_OUT_PIN;
    GPIO_setDirMode(gGpioBaseAddr, gGpioPinNum, GPIO_LAB_OUT_DIR);
    gGpioConfigured = 1U;
    DebugP_log(APP_LOG_PREFIX " gpio configured candidate=%s base=0x%08" PRIx32 " pin=%u\r\n",
               APP_GPIO_NAME,
               gGpioBaseAddr,
               gGpioPinNum);
}

static void app_gpio_apply(uint32_t value)
{
    app_gpio_configure_if_needed();

    if (value != 0U) {
        GPIO_pinWriteHigh(gGpioBaseAddr, gGpioPinNum);
        gGpioValue = 1U;
    } else {
        GPIO_pinWriteLow(gGpioBaseAddr, gGpioPinNum);
        gGpioValue = 0U;
    }

    DebugP_log(APP_LOG_PREFIX " gpio candidate=%s value=%u\r\n", APP_GPIO_NAME, gGpioValue);
}

static void app_gpio_init(void)
{
    gGpioValue = 0U;
    gGpioConfigured = 0U;
    gGpioBaseAddr = 0U;
    gGpioPinNum = 0U;
    DebugP_log(APP_LOG_PREFIX " gpio hook candidate=%s base=0x%08" PRIx32 " pin=%u state=deferred\r\n",
               APP_GPIO_NAME,
               (uint32_t)GPIO_LAB_OUT_BASE_ADDR,
               (uint32_t)GPIO_LAB_OUT_PIN);
}

static void app_make_status(char *response, size_t response_size)
{
    uint64_t uptime_ms = ClockP_getTimeUsec() / 1000U;

    snprintf(response,
             response_size,
             "OK STATUS core=78000000.r5f service=%s endpoint=%u gpio=%u gpio_candidate=%s uptime_ms=%" PRIu64,
             APP_SERVICE_NAME,
             APP_SERVICE_ENDPOINT,
             gGpioValue,
             APP_GPIO_NAME,
             uptime_ms);
}

static int32_t app_parse_u32(const char *text, uint32_t *value)
{
    char *end = NULL;
    unsigned long parsed;

    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed > UINT_MAX) {
        return SystemP_FAILURE;
    }

    *value = (uint32_t)parsed;
    return SystemP_SUCCESS;
}

static void app_dispatch_command(const char *cmd, char *response, size_t response_size)
{
    uint32_t value;
    uint32_t count;
    uint32_t i;

    DebugP_log(APP_LOG_PREFIX " rx cmd=%s\r\n", cmd);

    if (strcmp(cmd, "PING") == 0) {
        snprintf(response, response_size, "OK PONG");
    } else if (strcmp(cmd, "STATUS") == 0) {
        app_make_status(response, response_size);
    } else if (strncmp(cmd, "GPIO_SET ", 9U) == 0) {
        if (app_parse_u32(&cmd[9], &value) != SystemP_SUCCESS || value > 1U) {
            snprintf(response, response_size, "ERR INVALID_ARG");
            return;
        }
        app_gpio_apply(value);
        snprintf(response, response_size, "OK GPIO_SET value=%u", gGpioValue);
    } else if (strcmp(cmd, "GPIO_TOGGLE") == 0) {
        app_gpio_apply(gGpioValue == 0U ? 1U : 0U);
        snprintf(response, response_size, "OK GPIO_TOGGLE value=%u", gGpioValue);
    } else if (strncmp(cmd, "GPIO_BLINK ", 11U) == 0) {
        if (app_parse_u32(&cmd[11], &count) != SystemP_SUCCESS || count == 0U || count > APP_BLINK_MAX_COUNT) {
            snprintf(response, response_size, "ERR INVALID_ARG");
            return;
        }
        for (i = 0; i < count; i++) {
            app_gpio_apply(1U);
            ClockP_usleep(APP_BLINK_DELAY_USEC);
            app_gpio_apply(0U);
            ClockP_usleep(APP_BLINK_DELAY_USEC);
        }
        snprintf(response, response_size, "OK GPIO_BLINK count=%u value=%u", count, gGpioValue);
    } else {
        snprintf(response, response_size, "ERR UNKNOWN_CMD");
    }

    DebugP_log(APP_LOG_PREFIX " tx rsp=%s\r\n", response);
}

static void app_recv_task_main(void *args)
{
    RPMessage_Object *obj = (RPMessage_Object *)args;
    char recvMsg[APP_MAX_MSG_SIZE + 1U];
    char response[APP_MAX_MSG_SIZE];
    uint16_t recvMsgSize;
    uint16_t remoteCoreId, remoteCoreEndPt;
    int32_t status;

    DebugP_log(APP_LOG_PREFIX " waiting at endpoint %u\r\n",
               RPMessage_getLocalEndPt(obj));

    while (1)
    {
        recvMsgSize = APP_MAX_MSG_SIZE;
        status = RPMessage_recv(obj,
                                recvMsg,
                                &recvMsgSize,
                                &remoteCoreId,
                                &remoteCoreEndPt,
                                SystemP_WAIT_FOREVER);
        DebugP_assert(status == SystemP_SUCCESS);

        recvMsg[recvMsgSize] = '\0';
        app_dispatch_command(recvMsg, response, sizeof(response));

        status = RPMessage_send(response,
                                (uint16_t)strlen(response),
                                remoteCoreId,
                                remoteCoreEndPt,
                                RPMessage_getLocalEndPt(obj),
                                SystemP_WAIT_FOREVER);
        DebugP_assert(status == SystemP_SUCCESS);
    }
}

void am64x_r5f_hw_control_lab_main(void *args)
{
    RPMessage_CreateParams createParams;
    TaskP_Params taskParams;
    int32_t status;

    (void)args;

    Drivers_open();
    Board_driversOpen();

    DebugP_log(APP_LOG_PREFIX " Phase 1 control lab %s %s\r\n", __DATE__, __TIME__);
    app_gpio_init();

    status = RPMessage_waitForLinuxReady(SystemP_WAIT_FOREVER);
    DebugP_assert(status == SystemP_SUCCESS);

    RPMessage_CreateParams_init(&createParams);
    createParams.localEndPt = APP_SERVICE_ENDPOINT;
    status = RPMessage_construct(&gRecvMsgObject, &createParams);
    DebugP_assert(status == SystemP_SUCCESS);

    status = RPMessage_announce(CSL_CORE_ID_A53SS0_0,
                                APP_SERVICE_ENDPOINT,
                                APP_SERVICE_NAME);
    DebugP_assert(status == SystemP_SUCCESS);

    TaskP_Params_init(&taskParams);
    taskParams.name = "AM64X_HWLAB_RECV";
    taskParams.stackSize = APP_TASK_STACK_SIZE;
    taskParams.stack = gRecvTaskStack;
    taskParams.priority = APP_TASK_PRI;
    taskParams.args = &gRecvMsgObject;
    taskParams.taskMain = app_recv_task_main;

    status = TaskP_construct(&gRecvTask, &taskParams);
    DebugP_assert(status == SystemP_SUCCESS);

    DebugP_log(APP_LOG_PREFIX " announced service %s endpoint %u\r\n",
               APP_SERVICE_NAME,
               APP_SERVICE_ENDPOINT);

    vTaskDelete(NULL);
}
