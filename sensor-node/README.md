# AEGIS — Sensor Node (MSP432E401Y, C)

The front-line device. Samples its link counters, computes 4 traffic features,
and publishes them to the Pi gateway as an authenticated-ready binary frame
(length prefix, sequence number, CRC — see `../PROTOCOL.md`).

## Files

| File | Role | Builds on laptop? |
|------|------|-------------------|
| `aegis_frame.h/.c` | Portable frame builder + CRC-16/CCITT. No hardware deps. | yes |
| `host_test.c` | Laptop test harness: prints a frame's bytes as hex. | yes |
| `main.c` | Board firmware loop (sample → feature → frame → UART). | no (needs board HAL) |
| `board_hal.h` | Hardware-abstraction layer the real board implements. | — |

## Build & run the laptop test

> **Windows note:** compile from **PowerShell**, not git-bash. The bash sandbox
> mangles gcc's child processes (cc1/as/ld produce no output). PowerShell is clean.

```powershell
$env:Path = "C:\mingw64\bin;" + $env:Path
gcc -std=c11 -Wall -Wextra -O2 -o host_test.exe aegis_frame.c host_test.c
.\host_test.exe 7 1100 512 120 500
# -> AE 51 07 00 08 4C 04 00 02 78 00 F4 01 FD BE
```

The cross-language proof (`../integration_test.py`) compiles this and checks the
bytes match the Python gateway exactly.

## On the real board (tomorrow / later)

- Implement `board_hal.h` with TivaWare/MSP432 driverlib (UART + link counters).
- Build `main.c` + `aegis_frame.c` with `arm-none-eabi-gcc` or Code Composer Studio.
- Stretch: swap raw UART for lwIP + MQTT, and wrap frames with the on-chip
  AES/SHA engine for authenticated, encrypted telemetry + attestation.
