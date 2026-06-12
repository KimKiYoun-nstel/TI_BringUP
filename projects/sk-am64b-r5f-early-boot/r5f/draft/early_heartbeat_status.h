/* SPDX-License-Identifier: BSD-3-Clause */

#ifndef EARLY_HEARTBEAT_STATUS_H_
#define EARLY_HEARTBEAT_STATUS_H_

#include <stdint.h>

#define EARLY_HEARTBEAT_SHM_BASE_ADDR      (0xA5800000U)
#define EARLY_HEARTBEAT_SHM_SIZE_BYTES     (0x1000U)
#define EARLY_HEARTBEAT_SHM_MAGIC          (0x52354653U)
#define EARLY_HEARTBEAT_SHM_VERSION        (0x00010000U)
#define EARLY_HEARTBEAT_CORE_ID_MAIN0_0    (0x78000000U)
#define EARLY_HEARTBEAT_PERIOD_USEC        (100000U)

typedef struct
{
    uint32_t magic;
    uint32_t version;
    uint32_t abi_size;
    uint32_t seq;
    uint32_t uptime_ms;
    uint32_t heartbeat;
    uint32_t shm_update_count;
    uint32_t shm_update_period_ms;
    uint32_t core;
} EarlyHeartbeatStatus;

#endif
