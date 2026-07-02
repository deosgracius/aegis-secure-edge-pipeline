/*
 * host_test.c -- runs on the laptop (gcc), NOT the board.
 *
 * Builds one AEGIS frame from command-line args and prints the raw bytes as
 * hex. The Python bridge then parses those exact bytes -- if they agree, the C
 * firmware and the Python gateway speak the same protocol byte-for-byte.
 *
 *   usage:  host_test <seq> <f0> <f1> <f2> <f3>   (features already tx-scaled)
 *   prints: 15 space-separated hex bytes, e.g. "AE 51 07 00 08 ..."
 *
 * build:  gcc -std=c11 -Wall -Wextra -o host_test aegis_frame.c host_test.c
 */
#include <stdio.h>
#include <stdlib.h>
#include "aegis_frame.h"

int main(int argc, char **argv)
{
    if (argc != 6) {
        fprintf(stderr, "usage: %s <seq> <f0> <f1> <f2> <f3>\n", argv[0]);
        return 2;
    }
    uint16_t seq = (uint16_t)strtoul(argv[1], NULL, 0);
    uint16_t feats[AEGIS_N_FEATURES];
    for (int i = 0; i < 4; ++i)
        feats[i] = (uint16_t)strtoul(argv[2 + i], NULL, 0);

    uint8_t buf[AEGIS_FRAME_LEN];
    size_t n = aegis_build_frame(buf, seq, feats);

    for (size_t i = 0; i < n; ++i)
        printf("%02X%s", buf[i], (i + 1 < n) ? " " : "\n");
    return 0;
}
