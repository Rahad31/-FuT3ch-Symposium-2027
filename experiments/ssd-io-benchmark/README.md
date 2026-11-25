# SSD I/O Benchmark

## Objective

Characterize the NVMe storage performance available on the TH Deggendorf HexHPC cluster using fio.

The benchmark investigates sequential and random read/write performance under different I/O configurations.

## Test Environment

- Cluster: TH Deggendorf HexHPC
- Compute node: ant20
- Storage device: SK hynix PC801 NVMe
- Device: `/dev/nvme0n1`
- Scratch filesystem: `/scratch`
- Benchmark tool: fio 3.43-49-g6288

## Initial Baseline Results

| Parameter | Sequential Write | Sequential Read |
|---|---:|---:|
| Block size | 1 MiB | 1 MiB |
| File size | 1 GiB | 1 GiB |
| I/O engine | sync | sync |
| Queue depth | 1 | 1 |
| Duration | 30 seconds | 30 seconds |
| Bandwidth | 4530 MiB/s | 5859 MiB/s |
| IOPS | 4530 | 5858 |
| Average latency | 220.45 µs | 170.54 µs |

## Next Experiments

1. Test different block sizes.
2. Measure random read/write performance.
3. Compare different queue depths.
4. Evaluate supported I/O engines.
5. Analyze bandwidth, IOPS and latency.

## Notes

These results represent the initial benchmark configuration, not the maximum theoretical performance of the NVMe device.

Further experiments will investigate the impact of block size, queue depth and I/O engine.
