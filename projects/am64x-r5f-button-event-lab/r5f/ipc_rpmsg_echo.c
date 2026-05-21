/* SPDX-License-Identifier: BSD-3-Clause */

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <kernel/dpl/AddrTranslateP.h>
#include <kernel/dpl/ClockP.h>
#include <kernel/dpl/DebugP.h>
#include <kernel/dpl/HwiP.h>
#include <kernel/dpl/TaskP.h>
#include <drivers/gpio.h>
#include <drivers/ipc_notify.h>
#include <drivers/ipc_rpmsg.h>
#include "ti_drivers_config.h"
#include "ti_drivers_open_close.h"
#include "ti_board_open_close.h"

extern void Board_gpioInit(void);

#define APP_LOG_PREFIX              "[AM64X R5F BUTTON]"
#define APP_SERVICE_NAME            "rpmsg_chrdev"
#define APP_SERVICE_ENDPOINT        (14U)
#define APP_MAX_MSG_SIZE            (496U)
#define APP_RECV_TASK_PRI           (4U)
#define APP_BUTTON_TASK_PRI         (5U)
#define APP_TASK_STACK_SIZE         (16U * 1024U)
#define APP_BUTTON_NAME             "MCU_GPIO0_6"
#define APP_BUTTON_SOURCE           "SW1"
#define APP_BUTTON_DEBOUNCE_US      (30000U)
#define APP_BUTTON_POLL_US          (5000U)
#define APP_BUTTON_WAIT_DEFAULT_MS  (5000U)
#define APP_BUTTON_WAIT_MAX_MS      (60000U)

static RPMessage_Object gRecvMsgObject;
static uint8_t gRecvTaskStack[APP_TASK_STACK_SIZE] __attribute__((aligned(32)));
static uint8_t gButtonTaskStack[APP_TASK_STACK_SIZE] __attribute__((aligned(32)));
static TaskP_Object gRecvTask;
static TaskP_Object gButtonTask;
static HwiP_Object gButtonHwiObject;

static uint32_t gButtonBaseAddr;
static uint32_t gButtonPinNum;
static volatile uint32_t gButtonIsrSeq;
static volatile uint32_t gButtonIsrValue;
static volatile uint64_t gButtonIsrTimestampUs;
static uint32_t gButtonStableValue;
static uint32_t gButtonEventCount;
static uint64_t gButtonLastEventTimestampUs;
static uint16_t gSubscriberCoreId;
static uint16_t gSubscriberEndPt;
static uint32_t gSubscriberActive;

static void app_button_bank_isr(void *args)
{
    uint32_t pinNum = (uint32_t)args;
    uint32_t bankNum = GPIO_GET_BANK_INDEX(pinNum);
    uint32_t pinMask = GPIO_GET_BANK_BIT_MASK(pinNum);
    uint32_t intrStatus;

    intrStatus = GPIO_getBankIntrStatus(gButtonBaseAddr, bankNum);
    GPIO_clearBankIntrStatus(gButtonBaseAddr, bankNum, intrStatus);

    if ((intrStatus & pinMask) != 0U) {
        gButtonIsrValue = GPIO_pinRead(gButtonBaseAddr, pinNum) & 1U;
        gButtonIsrTimestampUs = ClockP_getTimeUsec();
        gButtonIsrSeq++;
    }
}

static const char *app_button_state(uint32_t value)
{
    return value == 0U ? "pressed" : "released";
}

static const char *app_button_edge(uint32_t value)
{
    return value == 0U ? "falling" : "rising";
}

static void app_get_button_snapshot(uint32_t *value, uint32_t *count, uint64_t *timestamp_us)
{
    uintptr_t key = HwiP_disable();

    *value = gButtonStableValue;
    *count = gButtonEventCount;
    *timestamp_us = gButtonLastEventTimestampUs;

    HwiP_restore(key);
}

static void app_format_button_event(char *response,
                                    size_t response_size,
                                    uint32_t value,
                                    uint32_t count,
                                    uint64_t timestamp_us)
{
    snprintf(response,
             response_size,
             "BUTTON_EVENT source=%s gpio=%s value=%u state=%s edge=%s count=%u timestamp_us=%" PRIu64,
             APP_BUTTON_SOURCE,
             APP_BUTTON_NAME,
             value,
             app_button_state(value),
             app_button_edge(value),
             count,
             timestamp_us);
}

static void app_make_button_event(char *response, size_t response_size)
{
    uint32_t value;
    uint32_t count;
    uint64_t timestamp_us;

    app_get_button_snapshot(&value, &count, &timestamp_us);
    app_format_button_event(response, response_size, value, count, timestamp_us);
}

static void app_make_status(char *response, size_t response_size)
{
    uint32_t value;
    uint32_t count;
    uint64_t timestamp_us;
    uint64_t uptime_ms = ClockP_getTimeUsec() / 1000U;

    (void)timestamp_us;
    app_get_button_snapshot(&value, &count, &timestamp_us);

    snprintf(response,
             response_size,
             "OK STATUS core=78000000.r5f service=%s endpoint=%u button_gpio=%s button_value=%u button_state=%s event_count=%u uptime_ms=%" PRIu64,
             APP_SERVICE_NAME,
             APP_SERVICE_ENDPOINT,
             APP_BUTTON_NAME,
             value,
             app_button_state(value),
             count,
             uptime_ms);
}

static void app_make_button_status(char *response, size_t response_size)
{
    uint32_t value;
    uint32_t count;
    uint64_t timestamp_us;

    app_get_button_snapshot(&value, &count, &timestamp_us);

    snprintf(response,
             response_size,
             "OK BUTTON_STATUS source=%s gpio=%s value=%u state=%s count=%u timestamp_us=%" PRIu64,
             APP_BUTTON_SOURCE,
             APP_BUTTON_NAME,
             value,
             app_button_state(value),
             count,
             timestamp_us);
}

static uint32_t app_get_button_event_count(void)
{
    uint32_t count;
    uintptr_t key = HwiP_disable();

    count = gButtonEventCount;

    HwiP_restore(key);
    return count;
}

static void app_set_subscriber(uint16_t remoteCoreId, uint16_t remoteCoreEndPt)
{
    uintptr_t key = HwiP_disable();

    gSubscriberCoreId = remoteCoreId;
    gSubscriberEndPt = remoteCoreEndPt;
    gSubscriberActive = 1U;

    HwiP_restore(key);
}

static int32_t app_parse_wait_ms(const char *text, uint32_t *timeout_ms)
{
    char *end = NULL;
    unsigned long parsed;

    if (text == NULL || *text == '\0') {
        *timeout_ms = APP_BUTTON_WAIT_DEFAULT_MS;
        return SystemP_SUCCESS;
    }

    parsed = strtoul(text, &end, 10);
    if (end == text || *end != '\0' || parsed > APP_BUTTON_WAIT_MAX_MS) {
        return SystemP_FAILURE;
    }

    *timeout_ms = (uint32_t)parsed;
    return SystemP_SUCCESS;
}

static int32_t app_wait_for_button_event(uint32_t start_count, uint32_t timeout_ms)
{
    uint64_t start_us = ClockP_getTimeUsec();
    uint64_t timeout_us = (uint64_t)timeout_ms * 1000U;

    while ((ClockP_getTimeUsec() - start_us) <= timeout_us) {
        if (app_get_button_event_count() != start_count) {
            return SystemP_SUCCESS;
        }
        ClockP_usleep(APP_BUTTON_POLL_US);
    }

    return SystemP_TIMEOUT;
}

static void app_dispatch_command(const char *cmd,
                                 uint16_t remoteCoreId,
                                 uint16_t remoteCoreEndPt,
                                 char *response,
                                 size_t response_size)
{
    uint32_t timeout_ms;
    uint32_t start_count;

    DebugP_log(APP_LOG_PREFIX " rx cmd=%s\r\n", cmd);

    if (strcmp(cmd, "PING") == 0) {
        snprintf(response, response_size, "OK PONG");
    } else if (strcmp(cmd, "STATUS") == 0) {
        app_make_status(response, response_size);
    } else if (strcmp(cmd, "BUTTON_STATUS") == 0) {
        app_make_button_status(response, response_size);
    } else if (strcmp(cmd, "BUTTON_MONITOR") == 0 || strcmp(cmd, "EVENT_MONITOR") == 0) {
        app_set_subscriber(remoteCoreId, remoteCoreEndPt);
        snprintf(response, response_size, "OK BUTTON_MONITOR subscribed=1");
    } else if (strncmp(cmd, "BUTTON_WAIT", 11U) == 0) {
        if (cmd[11] == ' ') {
            if (app_parse_wait_ms(&cmd[12], &timeout_ms) != SystemP_SUCCESS) {
                snprintf(response, response_size, "ERR INVALID_ARG");
                return;
            }
        } else if (cmd[11] == '\0') {
            timeout_ms = APP_BUTTON_WAIT_DEFAULT_MS;
        } else {
            snprintf(response, response_size, "ERR UNKNOWN_CMD");
            return;
        }
        start_count = app_get_button_event_count();
        if (app_wait_for_button_event(start_count, timeout_ms) == SystemP_SUCCESS) {
            app_make_button_event(response, response_size);
        } else {
            snprintf(response, response_size, "OK BUTTON_WAIT timeout_ms=%u event=none", timeout_ms);
        }
    } else if (strncmp(cmd, "GPIO_", 5U) == 0) {
        snprintf(response, response_size, "ERR UNSUPPORTED_CMD phase=button_event_lab");
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

    while (1) {
        recvMsgSize = APP_MAX_MSG_SIZE;
        status = RPMessage_recv(obj,
                                recvMsg,
                                &recvMsgSize,
                                &remoteCoreId,
                                &remoteCoreEndPt,
                                SystemP_WAIT_FOREVER);
        DebugP_assert(status == SystemP_SUCCESS);

        recvMsg[recvMsgSize] = '\0';
        app_dispatch_command(recvMsg,
                             remoteCoreId,
                             remoteCoreEndPt,
                             response,
                             sizeof(response));

        status = RPMessage_send(response,
                                (uint16_t)strlen(response),
                                remoteCoreId,
                                remoteCoreEndPt,
                                RPMessage_getLocalEndPt(obj),
                                SystemP_WAIT_FOREVER);
        DebugP_assert(status == SystemP_SUCCESS);
    }
}

static void app_clear_subscriber(uint16_t remoteCoreId, uint16_t remoteEndPt)
{
    uintptr_t key = HwiP_disable();

    if (gSubscriberActive != 0U &&
        gSubscriberCoreId == remoteCoreId &&
        gSubscriberEndPt == remoteEndPt) {
        gSubscriberActive = 0U;
    }

    HwiP_restore(key);
}

static uint32_t app_get_subscriber(uint16_t *remoteCoreId, uint16_t *remoteEndPt)
{
    uint32_t active;
    uintptr_t key = HwiP_disable();

    active = gSubscriberActive;
    *remoteCoreId = gSubscriberCoreId;
    *remoteEndPt = gSubscriberEndPt;

    HwiP_restore(key);
    return active;
}

static void app_send_button_event_to_subscriber(RPMessage_Object *obj, char *event)
{
    int32_t status;
    uint16_t remoteCoreId;
    uint16_t remoteEndPt;

    if (app_get_subscriber(&remoteCoreId, &remoteEndPt) == 0U) {
        return;
    }

    status = RPMessage_send(event,
                            (uint16_t)strlen(event),
                            remoteCoreId,
                            remoteEndPt,
                            RPMessage_getLocalEndPt(obj),
                            SystemP_NO_WAIT);
    if (status != SystemP_SUCCESS) {
        app_clear_subscriber(remoteCoreId, remoteEndPt);
        DebugP_log(APP_LOG_PREFIX " event send failed, subscriber cleared\r\n");
    }
}

static void app_button_task_main(void *args)
{
    RPMessage_Object *obj = (RPMessage_Object *)args;
    char event[APP_MAX_MSG_SIZE];
    uint32_t handled_seq = 0U;

    while (1) {
        uint32_t irq_seq;
        uint32_t irq_value;
        uint64_t irq_ts;
        uintptr_t key;

        key = HwiP_disable();
        irq_seq = gButtonIsrSeq;
        irq_value = gButtonIsrValue;
        irq_ts = gButtonIsrTimestampUs;
        HwiP_restore(key);

        if (irq_seq != handled_seq &&
            (ClockP_getTimeUsec() - irq_ts) >= APP_BUTTON_DEBOUNCE_US) {
            uint32_t stable_value = GPIO_pinRead(gButtonBaseAddr, gButtonPinNum) & 1U;
            uint32_t event_count;
            uint64_t event_ts;

            key = HwiP_disable();
            if (gButtonIsrSeq == irq_seq) {
                handled_seq = irq_seq;
                if (stable_value == irq_value && stable_value != gButtonStableValue) {
                    gButtonStableValue = stable_value;
                    gButtonEventCount++;
                    gButtonLastEventTimestampUs = ClockP_getTimeUsec();
                    event_count = gButtonEventCount;
                    event_ts = gButtonLastEventTimestampUs;
                    HwiP_restore(key);

                    app_format_button_event(event, sizeof(event), stable_value, event_count, event_ts);
                    DebugP_log(APP_LOG_PREFIX " %s\r\n", event);
                    app_send_button_event_to_subscriber(obj, event);
                } else {
                    HwiP_restore(key);
                }
            } else {
                HwiP_restore(key);
            }
        }
        ClockP_usleep(APP_BUTTON_POLL_US);
    }
}

static void app_button_init(void)
{
    HwiP_Params hwiPrms;
    int32_t status;

    gButtonBaseAddr = (uint32_t)AddrTranslateP_getLocalAddr(GPIO_BUTTON_IN_BASE_ADDR);
    gButtonPinNum = GPIO_BUTTON_IN_PIN;
    gButtonIsrSeq = 0U;
    gButtonStableValue = GPIO_pinRead(gButtonBaseAddr, gButtonPinNum) & 1U;
    gButtonEventCount = 0U;
    gButtonLastEventTimestampUs = ClockP_getTimeUsec();
    gSubscriberActive = 0U;

    Board_gpioInit();

    GPIO_setDirMode(gButtonBaseAddr, gButtonPinNum, GPIO_DIRECTION_INPUT);
    GPIO_setTrigType(gButtonBaseAddr, gButtonPinNum, GPIO_TRIG_TYPE_BOTH_EDGE);
    GPIO_bankIntrEnable(gButtonBaseAddr, GPIO_GET_BANK_INDEX(gButtonPinNum));

    HwiP_Params_init(&hwiPrms);
    hwiPrms.intNum = GPIO_BUTTON_IN_INTR_NUM;
    hwiPrms.callback = &app_button_bank_isr;
    hwiPrms.args = (void *)gButtonPinNum;
    hwiPrms.isPulse = TRUE;
    status = HwiP_construct(&gButtonHwiObject, &hwiPrms);
    DebugP_assert(status == SystemP_SUCCESS);

    DebugP_log(APP_LOG_PREFIX " button input init source=%s gpio=%s base=0x%08" PRIx32 " pin=%u value=%u state=%s\r\n",
               APP_BUTTON_SOURCE,
               APP_BUTTON_NAME,
               gButtonBaseAddr,
               gButtonPinNum,
               gButtonStableValue,
               app_button_state(gButtonStableValue));
}

void am64x_r5f_button_event_lab_main(void *args)
{
    RPMessage_CreateParams createParams;
    TaskP_Params taskParams;
    int32_t status;

    (void)args;

    Drivers_open();
    Board_driversOpen();

    DebugP_log(APP_LOG_PREFIX " Phase 2 button event lab %s %s\r\n", __DATE__, __TIME__);
    app_button_init();

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
    taskParams.name = "AM64X_BUTTON_RECV";
    taskParams.stackSize = APP_TASK_STACK_SIZE;
    taskParams.stack = gRecvTaskStack;
    taskParams.priority = APP_RECV_TASK_PRI;
    taskParams.args = &gRecvMsgObject;
    taskParams.taskMain = app_recv_task_main;
    status = TaskP_construct(&gRecvTask, &taskParams);
    DebugP_assert(status == SystemP_SUCCESS);

    TaskP_Params_init(&taskParams);
    taskParams.name = "AM64X_BUTTON_EVT";
    taskParams.stackSize = APP_TASK_STACK_SIZE;
    taskParams.stack = gButtonTaskStack;
    taskParams.priority = APP_BUTTON_TASK_PRI;
    taskParams.args = &gRecvMsgObject;
    taskParams.taskMain = app_button_task_main;
    status = TaskP_construct(&gButtonTask, &taskParams);
    DebugP_assert(status == SystemP_SUCCESS);

    DebugP_log(APP_LOG_PREFIX " service=%s endpoint=%u ready\r\n",
               APP_SERVICE_NAME,
               APP_SERVICE_ENDPOINT);

    while (1) {
        ClockP_sleep(60U);
    }
}
