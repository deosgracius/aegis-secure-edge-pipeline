# AEGIS Telemetry Frame (v1)

The hand-rolled, length-prefixed, checksummed binary frame a sensor node sends to
the Pi gateway. Implemented identically in C (the MSP432 node) and Python (the Pi
bridge). Little-endian throughout.

```
 offset  size  field      meaning
 ------  ----  ---------  -------------------------------------------------
   0      1    MAGIC0     0xAE   } 2-byte sync word so the receiver can find
   1      1    MAGIC1     0x51   } the start of a frame in a byte stream
   2      2    seq        uint16 sequence number (wraps); detects loss/replay
   4      1    len        uint8  payload length in bytes (always 8 here)
   5      8    payload    4 x uint16: f0, f1, f2, f3  (tx-scaled features)
  13      2    crc16      uint16 CRC-16/CCITT-FALSE over bytes[2..12]
 ------  ----
  total = 15 bytes
```

- **CRC-16/CCITT-FALSE**: poly `0x1021`, init `0xFFFF`, no reflection, xorout `0x0000`.
  Computed over `seq + len + payload` (11 bytes), i.e. everything except the magic
  word and the CRC itself. The receiver recomputes and drops the frame on mismatch.

- **tx-scale**: features are sent as integers. Each feature `i` is transmitted as
  `round(value * TX_SCALE[i])`, clamped to a uint16. The Pi divides back out before
  quantizing for the FPGA.

  | feature | name      | TX_SCALE | why                                   |
  |---------|-----------|----------|---------------------------------------|
  | f0      | pkt_rate  | 1        | already a whole number (pps)          |
  | f1      | pkt_size  | 1        | already a whole number (bytes)        |
  | f2      | seq_gap   | 100      | small value, keep 2 decimals of detail|
  | f3      | iat_var   | 100      | small value, keep 2 decimals of detail|

## Data path

```
MSP432 node                Raspberry Pi gateway                 Basys 3 FPGA
-----------                --------------------                 ------------
read sensors                                                    
compute f0..f3 (float)                                          
tx-scale -> uint16                                              
build frame + CRC  ──UART──►  parse frame, check CRC            
                              recover floats (÷ TX_SCALE)       
                              quantize -> 16-bit  ──UART/SPI──►  scorer.v
                              receive verdict      ◄──────────  verdict + score (20 ns)
                              forward to control plane          
```

Today the FPGA step is emulated in software by `pi_bridge.py` using the *exact*
same model that becomes `scorer.v` (verified bit-exact), so the whole path runs on
a laptop with no hardware. Tomorrow the emulated step is swapped for the real UART
link to the board.
