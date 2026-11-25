# Benchmark Log

## Experiment 001 — Initial Sequential I/O Test

**Date:** 25 November 2026

**Platform:** TH Deggendorf HexHPC

**Compute node:** ant20

**Tool:** fio 3.43-49-g6288

### Configuration

- Block size: 1 MiB
- File size: 1 GiB
- Runtime: 30 seconds
- I/O engine: sync
- Queue depth: 1
- Direct I/O: Enabled

### Results

**Sequential Write**
- Bandwidth: 4530 MiB/s
- IOPS: 4530
- Average latency: 220.45 µs
- Total I/O: 133 GiB

**Sequential Read**
- Bandwidth: 5859 MiB/s
- IOPS: 5858
- Average latency: 170.54 µs
- Total I/O: 172 GiB

### Observation

The initial benchmark completed successfully without I/O errors.

Sequential read bandwidth was higher than sequential write bandwidth under this configuration.

These measurements establish an initial performance baseline for subsequent experiments.

### Next Step

Investigate the effect of different block sizes and queue depths on NVMe performance.
