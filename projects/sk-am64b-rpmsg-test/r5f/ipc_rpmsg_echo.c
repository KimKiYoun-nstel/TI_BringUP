/* SPDX-License-Identifier: BSD-3-Clause */

#include <string.h>
#include <inttypes.h>
#include <kernel/dpl/ClockP.h>
#include <kernel/dpl/DebugP.h>
#include <kernel/dpl/TaskP.h>
#include <drivers/ipc_notify.h>
#include <drivers/ipc_rpmsg.h>
#include "ti_drivers_open_close.h"
#include "ti_board_open_close.h"

#define APP_SERVICE_NAME          "rpmsg_chrdev"
#define APP_SERVICE_ENDPOINT      (14U)
#define APP_MAX_MSG_SIZE          (496U)
#define APP_TASK_PRI              (4U)
#define APP_TASK_STACK_SIZE       (16U * 1024U)

static RPMessage_Object gRecvMsgObject;
static uint8_t gRecvTaskStack[APP_TASK_STACK_SIZE] __attribute__((aligned(32)));
static TaskP_Object gRecvTask;

static void app_recv_task_main(void *args)
{
    RPMessage_Object *obj = (RPMessage_Object *)args;
    char recvMsg[APP_MAX_MSG_SIZE];
    uint16_t recvMsgSize;
    uint16_t remoteCoreId, remoteCoreEndPt;
    int32_t status;

    DebugP_log("[SK-AM64B RPMSG TEST] waiting at endpoint %u\r\n",
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

        status = RPMessage_send(recvMsg,
                                recvMsgSize,
                                remoteCoreId,
                                remoteCoreEndPt,
                                RPMessage_getLocalEndPt(obj),
                                SystemP_WAIT_FOREVER);
        DebugP_assert(status == SystemP_SUCCESS);
    }
}

void sk_r5f_rpmsg_test_main(void *args)
{
    RPMessage_CreateParams createParams;
    TaskP_Params taskParams;
    int32_t status;

    Drivers_open();
    Board_driversOpen();

    DebugP_log("[SK-AM64B RPMSG TEST] %s %s\r\n", __DATE__, __TIME__);

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
    taskParams.name = "SK_RPMSG_RECV";
    taskParams.stackSize = APP_TASK_STACK_SIZE;
    taskParams.stack = gRecvTaskStack;
    taskParams.priority = APP_TASK_PRI;
    taskParams.args = &gRecvMsgObject;
    taskParams.taskMain = app_recv_task_main;

    status = TaskP_construct(&gRecvTask, &taskParams);
    DebugP_assert(status == SystemP_SUCCESS);

    DebugP_log("[SK-AM64B RPMSG TEST] announced service %s endpoint %u\r\n",
               APP_SERVICE_NAME,
               APP_SERVICE_ENDPOINT);

    vTaskDelete(NULL);
}
