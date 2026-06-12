/* SPDX-License-Identifier: BSD-3-Clause */

/*
 * Early-boot heartbeat first draft.
 *
 * This file is intentionally kept close to the canonical R5F project entry
 * shell, but it is not yet declared build-validated in this repo.
 */

#include <stddef.h>
#include <stdint.h>

#ifdef EARLY_HEARTBEAT_REAL_MCU_BUILD
#include <kernel/dpl/DebugP.h>
#include "ti_drivers_config.h"
#include "ti_board_config.h"
#include "FreeRTOS.h"
#include "task.h"
#else
/* Draft-local stand-ins so the source remains parseable in this repo. */
typedef uint32_t StackType_t;
typedef uint32_t configSTACK_DEPTH_TYPE;
typedef struct { uint32_t reserved; } StaticTask_t;
typedef void *TaskHandle_t;

#define configMAX_PRIORITIES (8U)

extern void System_init(void);
extern void Board_init(void);
extern TaskHandle_t xTaskCreateStatic(void (*task_code)(void *),
                                      const char * const name,
                                      uint32_t stack_depth,
                                      void *parameters,
                                      uint32_t priority,
                                      StackType_t *stack_buffer,
                                      StaticTask_t *task_buffer);
extern void vTaskStartScheduler(void);
extern void vTaskDelete(void *task_to_delete);

#define configASSERT(expr) do { if (!(expr)) { for (;;) { } } } while (0)
#endif

#define MAIN_TASK_PRI  (configMAX_PRIORITIES - 1)
#define MAIN_TASK_SIZE (16384U / sizeof(configSTACK_DEPTH_TYPE))

StackType_t gMainTaskStack[MAIN_TASK_SIZE] __attribute__((aligned(32)));
StaticTask_t gMainTaskObj;
TaskHandle_t gMainTask;

void early_boot_heartbeat_main(void *args);

static void freertos_main(void *args)
{
    early_boot_heartbeat_main(args);
    vTaskDelete(NULL);
}

int main(void)
{
    System_init();
    Board_init();

    gMainTask = xTaskCreateStatic(freertos_main,
                                  "freertos_main",
                                  MAIN_TASK_SIZE,
                                  NULL,
                                  MAIN_TASK_PRI,
                                  gMainTaskStack,
                                  &gMainTaskObj);
    configASSERT(gMainTask != NULL);

    vTaskStartScheduler();

    return 0;
}
