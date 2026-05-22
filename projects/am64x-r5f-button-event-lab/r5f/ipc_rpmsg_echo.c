/* SPDX-License-Identifier: BSD-3-Clause */

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
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

#define APP_LOG_PREFIX              "[AM64X R5F PHASE3]"
#define APP_SERVICE_NAME            "rpmsg_chrdev"
#define APP_SERVICE_ENDPOINT        (14U)
#define APP_MAX_MSG_SIZE            (496U)
#define APP_RECV_TASK_PRI           (4U)
#define APP_EVENT_TASK_PRI          (5U)
#define APP_TASK_STACK_SIZE         (16U * 1024U)
#define APP_INPUT_GPIO_ID           "mcu_gpio0_6"
#define APP_INPUT_GPIO_SIGNAL       "MCU_GPIO0_6"
#define APP_INPUT_GPIO_NAME         "phase2_sw1"
#define APP_INPUT_SOURCE            "SW1"
#define APP_OUTPUT_GPIO_ID          "mcu_gpio0_8"
#define APP_OUTPUT_GPIO_SIGNAL      "MCU_GPIO0_8"
#define APP_OUTPUT_GPIO_NAME        "phase1_out"
#define APP_FIRMWARE_VERSION        "0.3.0"
#define APP_BUTTON_DEBOUNCE_US      (30000U)
#define APP_BUTTON_POLL_US          (5000U)
#define APP_BUTTON_WAIT_DEFAULT_MS  (5000U)
#define APP_BUTTON_WAIT_MAX_MS      (60000U)

enum
{
    APP_EVENT_NONE = 0,
    APP_EVENT_GPIO_RISING = 1,
    APP_EVENT_GPIO_FALLING = 2,
    APP_EVENT_GPIO_CHANGED = 3,
};

typedef enum
{
    APP_STATUS_OK = 0,
    APP_STATUS_ERR_UNKNOWN_CMD = 1,
    APP_STATUS_ERR_BAD_ARG = 2,
    APP_STATUS_ERR_BUSY = 3,
    APP_STATUS_ERR_HW_FAIL = 4,
    APP_STATUS_ERR_TIMEOUT = 5,
} app_status_code_t;

typedef struct
{
    uint32_t magic;
    uint32_t uptime_ms;
    uint32_t output_gpio_state;
    uint32_t input_gpio_state;
    uint32_t event_count;
    uint32_t last_event_type;
    uint32_t last_event_gpio_id;
    uint64_t last_event_timestamp_us;
    uint32_t last_command_id;
    uint32_t last_error;
} app_state_t;

static RPMessage_Object gRecvMsgObject;
static uint8_t gRecvTaskStack[APP_TASK_STACK_SIZE] __attribute__((aligned(32)));
static uint8_t gEventTaskStack[APP_TASK_STACK_SIZE] __attribute__((aligned(32)));
static TaskP_Object gRecvTask;
static TaskP_Object gEventTask;
static HwiP_Object gButtonHwiObject;

static uint32_t gButtonBaseAddr;
static uint32_t gButtonPinNum;
static volatile uint32_t gButtonIsrSeq;
static volatile uint32_t gButtonIsrValue;
static volatile uint64_t gButtonIsrTimestampUs;

static uint32_t gOutputBaseAddr;
static uint32_t gOutputPinNum;
static uint32_t gOutputConfigured;

static uint16_t gSubscriberCoreId;
static uint16_t gSubscriberEndPt;
static uint32_t gSubscriberActive;
static app_state_t gState;

static const char *app_input_state_name(uint32_t value)
{
    return value == 0U ? "pressed" : "released";
}

static const char *app_event_type_name(uint32_t event_type)
{
    switch (event_type) {
    case APP_EVENT_GPIO_RISING:
        return "rising";
    case APP_EVENT_GPIO_FALLING:
        return "falling";
    case APP_EVENT_GPIO_CHANGED:
        return "changed";
    default:
        return "none";
    }
}

static const char *app_last_error_name(uint32_t status)
{
    switch ((app_status_code_t)status) {
    case APP_STATUS_OK:
        return "OK";
    case APP_STATUS_ERR_UNKNOWN_CMD:
        return "ERR_UNKNOWN_CMD";
    case APP_STATUS_ERR_BAD_ARG:
        return "ERR_BAD_ARG";
    case APP_STATUS_ERR_BUSY:
        return "ERR_BUSY";
    case APP_STATUS_ERR_HW_FAIL:
        return "ERR_HW_FAIL";
    case APP_STATUS_ERR_TIMEOUT:
        return "ERR_TIMEOUT";
    default:
        return "ERR_UNKNOWN";
    }
}

static void app_set_last_error(app_status_code_t status)
{
    uintptr_t key = HwiP_disable();
    gState.last_error = (uint32_t)status;
    HwiP_restore(key);
}

static void app_set_last_command(uint32_t command_id)
{
    uintptr_t key = HwiP_disable();
    gState.last_command_id = command_id;
    HwiP_restore(key);
}

static void app_output_configure_if_needed(void)
{
    if (gOutputConfigured != 0U) {
        return;
    }

    gOutputBaseAddr = (uint32_t)AddrTranslateP_getLocalAddr(GPIO_LAB_OUT_BASE_ADDR);
    gOutputPinNum = GPIO_LAB_OUT_PIN;
    GPIO_setDirMode(gOutputBaseAddr, gOutputPinNum, GPIO_LAB_OUT_DIR);
    gOutputConfigured = 1U;
    DebugP_log(APP_LOG_PREFIX " output gpio configured signal=%s base=0x%08" PRIx32 " pin=%u\r\n",
               APP_OUTPUT_GPIO_SIGNAL,
               gOutputBaseAddr,
               gOutputPinNum);
}

static void app_output_apply(uint32_t value)
{
    uintptr_t key;

    app_output_configure_if_needed();
    if (value != 0U) {
        GPIO_pinWriteHigh(gOutputBaseAddr, gOutputPinNum);
        value = 1U;
    } else {
        GPIO_pinWriteLow(gOutputBaseAddr, gOutputPinNum);
        value = 0U;
    }

    key = HwiP_disable();
    gState.output_gpio_state = value;
    HwiP_restore(key);
}

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

static void app_get_input_snapshot(uint32_t *value, uint32_t *count, uint64_t *timestamp_us, uint32_t *last_event_type)
{
    uintptr_t key = HwiP_disable();

    *value = gState.input_gpio_state;
    *count = gState.event_count;
    *timestamp_us = gState.last_event_timestamp_us;
    *last_event_type = gState.last_event_type;

    HwiP_restore(key);
}

static void app_format_event(char *response,
                             size_t response_size,
                             uint32_t value,
                             uint32_t count,
                             uint64_t timestamp_us,
                             uint32_t event_type)
{
    snprintf(response,
             response_size,
             "GPIO_EVENT source=%s gpio_id=%s signal=%s name=%s value=%u state=%s edge=%s count=%u timestamp_us=%" PRIu64,
             APP_INPUT_SOURCE,
             APP_INPUT_GPIO_ID,
             APP_INPUT_GPIO_SIGNAL,
             APP_INPUT_GPIO_NAME,
             value,
             app_input_state_name(value),
             app_event_type_name(event_type),
             count,
             timestamp_us);
}

static void app_make_last_event(char *response, size_t response_size)
{
    uint32_t value;
    uint32_t count;
    uint32_t event_type;
    uint64_t timestamp_us;

    app_get_input_snapshot(&value, &count, &timestamp_us, &event_type);
    if (count == 0U || event_type == APP_EVENT_NONE) {
        snprintf(response, response_size, "OK EVENT_GET event=none count=0");
        return;
    }

    app_format_event(response, response_size, value, count, timestamp_us, event_type);
}

static void app_make_status(char *response, size_t response_size)
{
    uint32_t value;
    uint32_t count;
    uint32_t event_type;
    uint64_t timestamp_us;
    uint64_t uptime_ms = ClockP_getTimeUsec() / 1000U;

    app_get_input_snapshot(&value, &count, &timestamp_us, &event_type);
    snprintf(response,
             response_size,
             "OK STATUS\n"
             "firmware_version=%s\n"
             "core=78000000.r5f\n"
             "service=%s\n"
             "endpoint=%u\n"
             "uptime_ms=%" PRIu64 "\n"
             "output_gpio_id=%s\n"
             "output_gpio_signal=%s\n"
             "output_gpio_name=%s\n"
             "output_state=%u\n"
             "input_gpio_id=%s\n"
             "input_gpio_signal=%s\n"
             "input_gpio_name=%s\n"
             "input_state=%u\n"
             "input_state_name=%s\n"
             "event_count=%u\n"
             "last_event_type=%s\n"
             "last_event_timestamp_us=%" PRIu64 "\n"
             "last_error=%s",
             APP_FIRMWARE_VERSION,
             APP_SERVICE_NAME,
             APP_SERVICE_ENDPOINT,
             uptime_ms,
             APP_OUTPUT_GPIO_ID,
             APP_OUTPUT_GPIO_SIGNAL,
             APP_OUTPUT_GPIO_NAME,
             gState.output_gpio_state,
             APP_INPUT_GPIO_ID,
             APP_INPUT_GPIO_SIGNAL,
             APP_INPUT_GPIO_NAME,
             value,
             app_input_state_name(value),
             count,
             app_event_type_name(event_type),
             timestamp_us,
             app_last_error_name(gState.last_error));
}

static void app_make_gpio_list(char *response, size_t response_size)
{
    snprintf(response,
             response_size,
             "OK GPIO_LIST\n"
             "id=%s direction=output signal=%s name=%s\n"
             "id=%s direction=input signal=%s name=%s",
             APP_OUTPUT_GPIO_ID,
             APP_OUTPUT_GPIO_SIGNAL,
             APP_OUTPUT_GPIO_NAME,
             APP_INPUT_GPIO_ID,
             APP_INPUT_GPIO_SIGNAL,
             APP_INPUT_GPIO_NAME);
}

static void app_make_gpio_get(char *response, size_t response_size, const char *gpio_id)
{
    uint32_t value;
    uint32_t count;
    uint32_t event_type;
    uint64_t timestamp_us;

    if (strcmp(gpio_id, APP_OUTPUT_GPIO_ID) == 0) {
        snprintf(response,
                 response_size,
                 "OK GPIO_GET\n"
                 "id=%s\n"
                 "direction=output\n"
                 "signal=%s\n"
                 "name=%s\n"
                 "value=%u",
                 APP_OUTPUT_GPIO_ID,
                 APP_OUTPUT_GPIO_SIGNAL,
                 APP_OUTPUT_GPIO_NAME,
                 gState.output_gpio_state);
        return;
    }

    if (strcmp(gpio_id, APP_INPUT_GPIO_ID) != 0) {
        snprintf(response, response_size, "ERR INVALID_GPIO_ID id=%s", gpio_id);
        app_set_last_error(APP_STATUS_ERR_BAD_ARG);
        return;
    }

    app_get_input_snapshot(&value, &count, &timestamp_us, &event_type);
    snprintf(response,
             response_size,
             "OK GPIO_GET\n"
             "id=%s\n"
             "direction=input\n"
             "signal=%s\n"
             "name=%s\n"
             "value=%u\n"
             "state=%s\n"
             "event_count=%u",
             APP_INPUT_GPIO_ID,
             APP_INPUT_GPIO_SIGNAL,
             APP_INPUT_GPIO_NAME,
             value,
             app_input_state_name(value),
             count);
}

static void app_make_button_status(char *response, size_t response_size)
{
    uint32_t value;
    uint32_t count;
    uint32_t event_type;
    uint64_t timestamp_us;

    app_get_input_snapshot(&value, &count, &timestamp_us, &event_type);
    (void)event_type;
    snprintf(response,
             response_size,
             "OK BUTTON_STATUS source=%s gpio=%s value=%u state=%s count=%u timestamp_us=%" PRIu64,
             APP_INPUT_SOURCE,
             APP_INPUT_GPIO_SIGNAL,
             value,
             app_input_state_name(value),
             count,
             timestamp_us);
}

static void app_set_subscriber(uint16_t remoteCoreId, uint16_t remoteCoreEndPt)
{
    uintptr_t key = HwiP_disable();

    gSubscriberCoreId = remoteCoreId;
    gSubscriberEndPt = remoteCoreEndPt;
    gSubscriberActive = 1U;

    HwiP_restore(key);
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

static void app_send_event_to_subscriber(RPMessage_Object *obj, char *event)
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

static int32_t app_parse_u32(const char *text, uint32_t *value)
{
    char *end = NULL;
    unsigned long parsed;

    if (text == NULL || *text == '\0') {
        return SystemP_FAILURE;
    }

    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || parsed > UINT_MAX) {
        return SystemP_FAILURE;
    }

    *value = (uint32_t)parsed;
    return SystemP_SUCCESS;
}

static int32_t app_parse_wait_ms(const char *text, uint32_t *timeout_ms)
{
    if (text == NULL || *text == '\0') {
        *timeout_ms = APP_BUTTON_WAIT_DEFAULT_MS;
        return SystemP_SUCCESS;
    }

    return app_parse_u32(text, timeout_ms) == SystemP_SUCCESS && *timeout_ms <= APP_BUTTON_WAIT_MAX_MS
               ? SystemP_SUCCESS
               : SystemP_FAILURE;
}

static int32_t app_wait_for_button_event(uint32_t start_count, uint32_t timeout_ms)
{
    uint64_t start_us = ClockP_getTimeUsec();
    uint64_t timeout_us = (uint64_t)timeout_ms * 1000U;

    while ((ClockP_getTimeUsec() - start_us) <= timeout_us) {
        if (gState.event_count != start_count) {
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
    uint32_t value;

    DebugP_log(APP_LOG_PREFIX " rx cmd=%s\r\n", cmd);

    if (strcmp(cmd, "PING") == 0) {
        app_set_last_command(0x0001U);
        app_set_last_error(APP_STATUS_OK);
        snprintf(response, response_size, "OK PONG");
    } else if (strcmp(cmd, "STATUS") == 0) {
        app_set_last_command(0x0003U);
        app_set_last_error(APP_STATUS_OK);
        app_make_status(response, response_size);
    } else if (strcmp(cmd, "GPIO_LIST") == 0) {
        app_set_last_command(0x0100U);
        app_set_last_error(APP_STATUS_OK);
        app_make_gpio_list(response, response_size);
    } else if (strncmp(cmd, "GPIO_GET ", 9U) == 0) {
        app_set_last_command(0x0101U);
        app_make_gpio_get(response, response_size, &cmd[9]);
        if (strncmp(response, "OK", 2U) == 0) {
            app_set_last_error(APP_STATUS_OK);
        }
    } else if (strncmp(cmd, "GPIO_SET ", 9U) == 0) {
        char gpio_id[32];
        const char *arg = &cmd[9];
        const char *space = strchr(arg, ' ');

        app_set_last_command(0x0102U);
        if (space == NULL) {
            app_set_last_error(APP_STATUS_ERR_BAD_ARG);
            snprintf(response, response_size, "ERR INVALID_ARG");
            return;
        }
        if ((size_t)(space - arg) >= sizeof(gpio_id)) {
            app_set_last_error(APP_STATUS_ERR_BAD_ARG);
            snprintf(response, response_size, "ERR INVALID_ARG");
            return;
        }

        memcpy(gpio_id, arg, (size_t)(space - arg));
        gpio_id[space - arg] = '\0';
        if (strcmp(gpio_id, APP_OUTPUT_GPIO_ID) != 0 || app_parse_u32(space + 1, &value) != SystemP_SUCCESS || value > 1U) {
            app_set_last_error(APP_STATUS_ERR_BAD_ARG);
            snprintf(response, response_size, "ERR INVALID_ARG");
            return;
        }

        app_output_apply(value);
        app_set_last_error(APP_STATUS_OK);
        snprintf(response,
                 response_size,
                 "OK GPIO_SET gpio_id=%s signal=%s value=%u",
                 APP_OUTPUT_GPIO_ID,
                 APP_OUTPUT_GPIO_SIGNAL,
                 gState.output_gpio_state);
    } else if (strcmp(cmd, "EVENT_GET") == 0) {
        app_set_last_command(0x0200U);
        app_set_last_error(APP_STATUS_OK);
        app_make_last_event(response, response_size);
    } else if (strcmp(cmd, "EVENT_MONITOR") == 0 || strcmp(cmd, "BUTTON_MONITOR") == 0) {
        app_set_last_command(0x0201U);
        app_set_subscriber(remoteCoreId, remoteCoreEndPt);
        app_set_last_error(APP_STATUS_OK);
        snprintf(response,
                 response_size,
                 "OK EVENT_MONITOR subscribed=1 gpio_id=%s signal=%s",
                 APP_INPUT_GPIO_ID,
                 APP_INPUT_GPIO_SIGNAL);
    } else if (strcmp(cmd, "BUTTON_STATUS") == 0) {
        app_set_last_command(0x0202U);
        app_set_last_error(APP_STATUS_OK);
        app_make_button_status(response, response_size);
    } else if (strncmp(cmd, "BUTTON_WAIT", 11U) == 0) {
        app_set_last_command(0x0203U);
        if (cmd[11] == ' ') {
            if (app_parse_wait_ms(&cmd[12], &timeout_ms) != SystemP_SUCCESS) {
                app_set_last_error(APP_STATUS_ERR_BAD_ARG);
                snprintf(response, response_size, "ERR INVALID_ARG");
                return;
            }
        } else if (cmd[11] == '\0') {
            timeout_ms = APP_BUTTON_WAIT_DEFAULT_MS;
        } else {
            app_set_last_error(APP_STATUS_ERR_UNKNOWN_CMD);
            snprintf(response, response_size, "ERR UNKNOWN_CMD");
            return;
        }

        start_count = gState.event_count;
        if (app_wait_for_button_event(start_count, timeout_ms) == SystemP_SUCCESS) {
            app_set_last_error(APP_STATUS_OK);
            app_make_last_event(response, response_size);
        } else {
            app_set_last_error(APP_STATUS_ERR_TIMEOUT);
            snprintf(response, response_size, "OK BUTTON_WAIT timeout_ms=%u event=none", timeout_ms);
        }
    } else {
        app_set_last_error(APP_STATUS_ERR_UNKNOWN_CMD);
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

static void app_event_task_main(void *args)
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

            key = HwiP_disable();
            if (gButtonIsrSeq == irq_seq) {
                handled_seq = irq_seq;
                if (stable_value == irq_value && stable_value != gState.input_gpio_state) {
                    gState.input_gpio_state = stable_value;
                    gState.event_count++;
                    gState.last_event_type = stable_value == 0U ? APP_EVENT_GPIO_FALLING : APP_EVENT_GPIO_RISING;
                    gState.last_event_gpio_id = 1U;
                    gState.last_event_timestamp_us = ClockP_getTimeUsec();
                    HwiP_restore(key);

                    app_format_event(event,
                                     sizeof(event),
                                     gState.input_gpio_state,
                                     gState.event_count,
                                     gState.last_event_timestamp_us,
                                     gState.last_event_type);
                    DebugP_log(APP_LOG_PREFIX " %s\r\n", event);
                    app_send_event_to_subscriber(obj, event);
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

static void app_state_init(void)
{
    memset(&gState, 0, sizeof(gState));
    gState.magic = 0x52354354U;
    gState.input_gpio_state = 1U;
    gState.last_error = APP_STATUS_OK;
}

static void app_gpio_init(void)
{
    HwiP_Params hwiPrms;
    int32_t status;

    Board_gpioInit();

    gOutputConfigured = 0U;
    gOutputBaseAddr = 0U;
    gOutputPinNum = 0U;
    gButtonBaseAddr = (uint32_t)AddrTranslateP_getLocalAddr(GPIO_BUTTON_IN_BASE_ADDR);
    gButtonPinNum = GPIO_BUTTON_IN_PIN;
    gButtonIsrSeq = 0U;
    gButtonIsrValue = 0U;
    gButtonIsrTimestampUs = 0U;
    gSubscriberActive = 0U;

    app_state_init();
    app_output_apply(0U);

    GPIO_setDirMode(gButtonBaseAddr, gButtonPinNum, GPIO_DIRECTION_INPUT);
    GPIO_setTrigType(gButtonBaseAddr, gButtonPinNum, GPIO_TRIG_TYPE_BOTH_EDGE);
    GPIO_bankIntrEnable(gButtonBaseAddr, GPIO_GET_BANK_INDEX(gButtonPinNum));
    gState.input_gpio_state = GPIO_pinRead(gButtonBaseAddr, gButtonPinNum) & 1U;
    gState.last_event_timestamp_us = ClockP_getTimeUsec();

    HwiP_Params_init(&hwiPrms);
    hwiPrms.intNum = GPIO_BUTTON_IN_INTR_NUM;
    hwiPrms.callback = &app_button_bank_isr;
    hwiPrms.args = (void *)gButtonPinNum;
    hwiPrms.isPulse = TRUE;
    status = HwiP_construct(&gButtonHwiObject, &hwiPrms);
    DebugP_assert(status == SystemP_SUCCESS);

    DebugP_log(APP_LOG_PREFIX " input init source=%s signal=%s base=0x%08" PRIx32 " pin=%u value=%u state=%s\r\n",
               APP_INPUT_SOURCE,
               APP_INPUT_GPIO_SIGNAL,
               gButtonBaseAddr,
               gButtonPinNum,
               gState.input_gpio_state,
               app_input_state_name(gState.input_gpio_state));
}

void am64x_r5f_button_event_lab_main(void *args)
{
    RPMessage_CreateParams createParams;
    TaskP_Params taskParams;
    int32_t status;

    (void)args;

    Drivers_open();
    Board_driversOpen();

    DebugP_log(APP_LOG_PREFIX " Phase 3 firmware %s %s\r\n", __DATE__, __TIME__);
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
    taskParams.name = "AM64X_PHASE3_RECV";
    taskParams.stackSize = APP_TASK_STACK_SIZE;
    taskParams.stack = gRecvTaskStack;
    taskParams.priority = APP_RECV_TASK_PRI;
    taskParams.args = &gRecvMsgObject;
    taskParams.taskMain = app_recv_task_main;
    status = TaskP_construct(&gRecvTask, &taskParams);
    DebugP_assert(status == SystemP_SUCCESS);

    TaskP_Params_init(&taskParams);
    taskParams.name = "AM64X_PHASE3_EVT";
    taskParams.stackSize = APP_TASK_STACK_SIZE;
    taskParams.stack = gEventTaskStack;
    taskParams.priority = APP_EVENT_TASK_PRI;
    taskParams.args = &gRecvMsgObject;
    taskParams.taskMain = app_event_task_main;
    status = TaskP_construct(&gEventTask, &taskParams);
    DebugP_assert(status == SystemP_SUCCESS);

    DebugP_log(APP_LOG_PREFIX " service=%s endpoint=%u ready output=%s input=%s\r\n",
               APP_SERVICE_NAME,
               APP_SERVICE_ENDPOINT,
               APP_OUTPUT_GPIO_SIGNAL,
               APP_INPUT_GPIO_SIGNAL);

    while (1) {
        ClockP_sleep(60U);
    }
}
