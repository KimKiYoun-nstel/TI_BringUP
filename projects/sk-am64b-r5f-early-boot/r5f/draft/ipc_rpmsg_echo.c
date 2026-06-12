/* SPDX-License-Identifier: BSD-3-Clause */

/*
 * Early-boot heartbeat first draft.
 *
 * This draft intentionally does not wait for Linux readiness and does not
 * create an RPMsg endpoint yet. The immediate goal is periodic SHM heartbeat
 * publication that can survive until A53 Linux boots.
 */

#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>

#include "early_heartbeat_status.h"

#ifdef EARLY_HEARTBEAT_REAL_MCU_BUILD
#include <kernel/dpl/AddrTranslateP.h>
#include <kernel/dpl/ClockP.h>
#include <kernel/dpl/TaskP.h>
#include "ti_drivers_open_close.h"
#include "ti_board_open_close.h"
#else
typedef struct { uint32_t reserved; } TaskP_Object;
typedef struct {
    const char *name;
    uint32_t stackSize;
    uint8_t *stack;
    uint32_t priority;
    void *args;
    void (*taskMain)(void *);
} TaskP_Params;

extern uintptr_t AddrTranslateP_getLocalAddr(uintptr_t addr);
extern uint64_t ClockP_getTimeUsec(void);
extern void ClockP_usleep(uint32_t usec);
extern void Drivers_open(void);
extern void Board_driversOpen(void);
extern void TaskP_Params_init(TaskP_Params *params);
extern int32_t TaskP_construct(TaskP_Object *obj, const TaskP_Params *params);
extern void vTaskDelete(void *task_to_delete);

#define SystemP_SUCCESS (0)
#define DebugP_assert(expr) do { if (!(expr)) { for (;;) { } } } while (0)
#endif

#define APP_TASK_PRI               (4U)
#define APP_TASK_STACK_SIZE        (8U * 1024U)
static uint8_t gHeartbeatTaskStack[APP_TASK_STACK_SIZE] __attribute__((aligned(32)));
static TaskP_Object gHeartbeatTask;

static volatile EarlyHeartbeatStatus *app_get_status_block(void)
{
    uintptr_t local_addr;

    local_addr = (uintptr_t)AddrTranslateP_getLocalAddr(EARLY_HEARTBEAT_SHM_BASE_ADDR);
    return (volatile EarlyHeartbeatStatus *)local_addr;
}

static void app_publish_status(volatile EarlyHeartbeatStatus *status)
{
    uint32_t uptime_ms;

    uptime_ms = (uint32_t)(ClockP_getTimeUsec() / 1000U);

    status->magic = EARLY_HEARTBEAT_SHM_MAGIC;
    status->version = EARLY_HEARTBEAT_SHM_VERSION;
    status->abi_size = (uint32_t)sizeof(EarlyHeartbeatStatus);
    status->seq++;
    status->uptime_ms = uptime_ms;
    status->heartbeat++;
    status->shm_update_count++;
    status->shm_update_period_ms = (EARLY_HEARTBEAT_PERIOD_USEC / 1000U);
    status->core = EARLY_HEARTBEAT_CORE_ID_MAIN0_0;
}

static void app_heartbeat_task_main(void *args)
{
    volatile EarlyHeartbeatStatus *status;

    (void)args;

    status = app_get_status_block();

    status->magic = 0U;
    status->version = 0U;
    status->abi_size = 0U;
    status->seq = 0U;
    status->uptime_ms = 0U;
    status->heartbeat = 0U;
    status->shm_update_count = 0U;
    status->shm_update_period_ms = 0U;
    status->core = EARLY_HEARTBEAT_CORE_ID_MAIN0_0;

    while (1)
    {
        app_publish_status(status);
        ClockP_usleep(EARLY_HEARTBEAT_PERIOD_USEC);
    }
}

void early_boot_heartbeat_main(void *args)
{
    TaskP_Params taskParams;
    int32_t status;

    (void)args;

    Drivers_open();
    Board_driversOpen();

    TaskP_Params_init(&taskParams);
    taskParams.name = "R5F_EARLY_HB";
    taskParams.stackSize = APP_TASK_STACK_SIZE;
    taskParams.stack = gHeartbeatTaskStack;
    taskParams.priority = APP_TASK_PRI;
    taskParams.taskMain = app_heartbeat_task_main;

    status = TaskP_construct(&gHeartbeatTask, &taskParams);
    DebugP_assert(status == SystemP_SUCCESS);

    vTaskDelete(NULL);
}
