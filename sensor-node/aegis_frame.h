/*
 * aegis_frame.h -- AEGIS telemetry frame builder (portable C).
 *
 * The byte-for-byte same frame format as ../PROTOCOL.md and the Python Pi
 * bridge. This file has NO hardware dependencies, so it compiles and runs on a
 * laptop (for tests) and on the MSP432 (in the real firmware) unchanged.
 */
#ifndef AEGIS_FRAME_H
#define AEGIS_FRAME_H

#include <stdint.h>
#include <stddef.h>

#define AEGIS_MAGIC0      0xAEu
#define AEGIS_MAGIC1      0x51u
#define AEGIS_PAYLOAD_LEN 8u          /* 4 x uint16 features            */
#define AEGIS_FRAME_LEN   15u         /* 2 magic +2 seq +1 len +8 +2 crc */
#define AEGIS_N_FEATURES  4u

/* CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, xorout 0. */
uint16_t aegis_crc16(const uint8_t *data, size_t len);

/*
 * Build one telemetry frame.
 *   buf   : output buffer, must hold at least AEGIS_FRAME_LEN bytes.
 *   seq   : sequence number (wraps).
 *   feats : 4 already-tx-scaled feature values (uint16, little-endian on wire).
 * Returns the number of bytes written (AEGIS_FRAME_LEN).
 */
size_t aegis_build_frame(uint8_t *buf, uint16_t seq,
                         const uint16_t feats[AEGIS_N_FEATURES]);

#endif /* AEGIS_FRAME_H */
