/*
 * aegis_frame.c -- implementation of the AEGIS telemetry frame (portable C).
 * No hardware dependencies; identical bytes to the Python bridge.
 */
#include "aegis_frame.h"

uint16_t aegis_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; ++b) {
            if (crc & 0x8000u)
                crc = (uint16_t)((crc << 1) ^ 0x1021u);
            else
                crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

static void put_u16_le(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)(v & 0xFFu);
    p[1] = (uint8_t)((v >> 8) & 0xFFu);
}

size_t aegis_build_frame(uint8_t *buf, uint16_t seq,
                         const uint16_t feats[AEGIS_N_FEATURES])
{
    buf[0] = AEGIS_MAGIC0;
    buf[1] = AEGIS_MAGIC1;
    put_u16_le(&buf[2], seq);          /* sequence number          */
    buf[4] = AEGIS_PAYLOAD_LEN;        /* payload length           */
    for (unsigned i = 0; i < AEGIS_N_FEATURES; ++i)
        put_u16_le(&buf[5 + 2 * i], feats[i]);

    /* CRC covers seq + len + payload = bytes [2..12] = 11 bytes. */
    uint16_t crc = aegis_crc16(&buf[2], 1 + 2 + AEGIS_PAYLOAD_LEN);
    put_u16_le(&buf[13], crc);

    return AEGIS_FRAME_LEN;
}
