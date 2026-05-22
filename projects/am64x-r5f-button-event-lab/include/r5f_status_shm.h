/* SPDX-License-Identifier: BSD-3-Clause */

#ifndef R5F_STATUS_SHM_H_
#define R5F_STATUS_SHM_H_

#include <stdint.h>

#define R5F_STATUS_SHM_BASE            (0xa5800000ULL)
#define R5F_STATUS_SHM_SIZE            (0x00001000ULL)
#define R5F_STATUS_SHM_MAGIC           (0x52354653U)
#define R5F_STATUS_SHM_VERSION         (0x00010000U)
#define R5F_STATUS_SHM_ABI_SIZE        (sizeof(r5f_status_shm_t))

#define R5F_STATUS_SHM_CORE_MAIN_R5F0_0 (0x78000000U)
#define R5F_STATUS_SHM_RPMSG_ENDPOINT   (14U)
#define R5F_STATUS_SHM_GPIO_OUTPUT_ID   (0U)
#define R5F_STATUS_SHM_GPIO_INPUT_ID    (1U)

#define R5F_STATUS_SHM_TEMP_VALID       (1U)
#define R5F_STATUS_SHM_TEMP_INVALID     (0U)
#define R5F_STATUS_SHM_TEMP_RAW_INVALID (0xffffffffU)
#define R5F_STATUS_SHM_TEMP_MC_INVALID  ((int32_t)-2147483647 - 1)
#define R5F_STATUS_SHM_TEMP_ERR_NONE    (0U)
#define R5F_STATUS_SHM_TEMP_ERR_UNAVAIL (1U)
#define R5F_STATUS_SHM_TEMP_ERR_RANGE   (2U)

typedef struct
{
    uint32_t magic;
    uint32_t version;
    uint32_t size;
    uint32_t seq_begin;

    uint32_t uptime_ms;
    uint32_t heartbeat;
    uint32_t shm_update_count;
    uint32_t main_loop_count;

    uint32_t core_id;
    uint32_t rpmsg_endpoint;
    uint32_t rpmsg_rx_count;
    uint32_t rpmsg_tx_count;
    uint32_t rpmsg_error_count;
    uint32_t last_command_id;
    uint32_t last_error;

    uint32_t output_gpio_id;
    uint32_t output_gpio_state;
    uint32_t input_gpio_id;
    uint32_t input_gpio_state;
    uint32_t gpio_event_count;
    uint32_t last_event_type;
    uint32_t last_event_gpio_id;
    uint64_t last_event_timestamp_us;

    uint32_t last_loop_period_us;
    uint32_t max_loop_period_us;
    uint32_t shm_update_period_ms;

    uint32_t soc_temp0_valid;
    uint32_t soc_temp0_raw;
    int32_t soc_temp0_milli_celsius;
    uint32_t soc_temp0_last_error;

    uint32_t soc_temp1_valid;
    uint32_t soc_temp1_raw;
    int32_t soc_temp1_milli_celsius;
    uint32_t soc_temp1_last_error;

    uint32_t seq_end;
} r5f_status_shm_t;

#endif
