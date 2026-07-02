/*
 * board_hal.h -- thin hardware-abstraction layer for the MSP432E401Y.
 *
 * Keeps the firmware logic (main.c) free of vendor register details, so the
 * SAME logic can be unit-tested on a laptop with a fake HAL. On the real board
 * these are implemented with TivaWare / the MSP432E driverlib.
 */
#ifndef BOARD_HAL_H
#define BOARD_HAL_H

#include <stdint.h>
#include <stddef.h>

/* One raw reading from the node's sensors / link counters. */
typedef struct {
    uint32_t pkt_count;     /* packets seen since last sample            */
    uint32_t byte_count;    /* bytes seen since last sample              */
    uint32_t last_seq;      /* last observed upstream sequence number    */
    uint32_t iat_us_sum;    /* sum of inter-arrival times (microseconds) */
    uint32_t iat_us_sumsq;  /* sum of squares, for variance              */
} sensor_sample_t;

void     board_init(void);                 /* clocks, GPIO, UART, etc.       */
uint32_t board_millis(void);               /* monotonic milliseconds         */
void     board_sample_sensors(sensor_sample_t *out);  /* read link counters  */
void     board_uart_write(const uint8_t *data, size_t len);  /* send bytes    */

/* On the real node, hardware AES/SHA + TRNG live here (secure-telemetry path):
 *   void board_hw_sha256(const uint8_t *in, size_t n, uint8_t out[32]);
 *   void board_hw_aes_gcm_seal(...);
 * Left out of the v1 frame to keep the first integration simple. */

#endif /* BOARD_HAL_H */
