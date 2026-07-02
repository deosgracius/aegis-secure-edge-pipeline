/*
 * main.c -- MSP432E401Y sensor-node firmware (skeleton for the real board).
 *
 * Loop: sample the link counters -> compute the 4 features -> tx-scale them to
 * uint16 -> build an AEGIS frame (length prefix, seq, CRC) -> send over UART to
 * the Raspberry Pi gateway. Periodic, deterministic, no dynamic allocation.
 *
 * This file targets the board (it calls the HAL in board_hal.h), so it is NOT
 * compiled on the laptop. The portable framing it relies on (aegis_frame.c) IS
 * laptop-tested via host_test.c, so the byte format is already proven.
 *
 * Stretch (already scoped in the project plan): replace the raw UART send with
 * lwIP + MQTT-over-TCP, and wrap each frame with the on-chip AES/SHA engine for
 * authenticated, encrypted telemetry + remote attestation.
 */
#include "aegis_frame.h"
#include "board_hal.h"

/* Must match TX_SCALE in ../PROTOCOL.md and the Python bridge. */
static const uint32_t TX_SCALE[AEGIS_N_FEATURES] = {1u, 1u, 100u, 100u};

#define SAMPLE_PERIOD_MS 100u   /* publish telemetry at 10 Hz */

static uint16_t clamp_u16(uint32_t v)
{
    return (v > 0xFFFFu) ? 0xFFFFu : (uint16_t)v;
}

/*
 * Turn one raw sensor sample into the 4 tx-scaled feature integers.
 *   f0 pkt_rate : packets per second
 *   f1 pkt_size : mean bytes per packet
 *   f2 seq_gap  : jump in upstream sequence number  (x100 fixed-point)
 *   f3 iat_var  : variance of inter-arrival time    (x100 fixed-point)
 */
static void compute_features(const sensor_sample_t *s, uint32_t dt_ms,
                             uint16_t feats[AEGIS_N_FEATURES],
                             uint32_t prev_seq)
{
    uint32_t pkts = s->pkt_count;
    uint32_t pkt_rate = (dt_ms > 0) ? (pkts * 1000u) / dt_ms : 0u;
    uint32_t pkt_size = (pkts > 0) ? s->byte_count / pkts : 0u;
    uint32_t seq_gap  = (s->last_seq >= prev_seq) ? (s->last_seq - prev_seq) : 0u;

    /* variance = E[x^2] - E[x]^2, in (microseconds^2); scaled to keep range sane */
    uint32_t iat_var = 0u;
    if (pkts > 0) {
        uint32_t mean = s->iat_us_sum / pkts;
        uint32_t meansq = s->iat_us_sumsq / pkts;
        iat_var = (meansq > mean * mean) ? (meansq - mean * mean) : 0u;
        iat_var /= 1000u;  /* down-scale us^2 into the model's expected range */
    }

    feats[0] = clamp_u16(pkt_rate * TX_SCALE[0]);
    feats[1] = clamp_u16(pkt_size * TX_SCALE[1]);
    feats[2] = clamp_u16(seq_gap  * TX_SCALE[2]);
    feats[3] = clamp_u16(iat_var  * TX_SCALE[3]);
}

int main(void)
{
    board_init();

    uint16_t seq = 0u;
    uint32_t prev_seq = 0u;
    uint32_t t_prev = board_millis();
    uint8_t  frame[AEGIS_FRAME_LEN];

    for (;;) {
        /* wait for the next sample tick (deterministic period) */
        while ((board_millis() - t_prev) < SAMPLE_PERIOD_MS) {
            /* idle / low-power wait on the real board */
        }
        uint32_t now = board_millis();
        uint32_t dt_ms = now - t_prev;
        t_prev = now;

        sensor_sample_t s;
        board_sample_sensors(&s);

        uint16_t feats[AEGIS_N_FEATURES];
        compute_features(&s, dt_ms, feats, prev_seq);
        prev_seq = s.last_seq;

        size_t n = aegis_build_frame(frame, seq, feats);
        board_uart_write(frame, n);    /* -> Raspberry Pi gateway */

        seq++;
    }
    /* not reached */
}
