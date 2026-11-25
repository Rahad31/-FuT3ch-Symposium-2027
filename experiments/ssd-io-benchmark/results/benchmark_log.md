# Benchmark Log

## Experiment 001 — Initial Sequential I/O Test

**Date:** 25 November 2026

**Platform:** TH Deggendorf HexHPC

**Compute Node:** ant20

**Storage:** SK hynix PC801 NVMe SSD

**Device:** `/dev/nvme0n1`

**Filesystem:** XFS (`/scratch`)

**Benchmark Tool:** fio 3.43-49-g6288

### 1. Objective

The objective of this experiment was to establish an initial performance baseline for the NVMe scratch storage available on the TH Deggendorf HexHPC cluster.

Sequential write and read performance were measured using Flexible I/O Tester (fio).

The experiment provides baseline measurements for future tests involving different block sizes, queue depths and I/O patterns.

### 2. Experimental Configuration

| Parameter | Value |
|---|---|
| Block size | 1 MiB |
| File size | 1 GiB |
| Runtime | 30 seconds |
| I/O engine | sync |
| Queue depth | 1 |
| Direct I/O | Enabled |
| Number of jobs | 1 |
| Time-based execution | Enabled |
| Group reporting | Enabled |
| Test directory | `$SCRATCH` |

### 3. Benchmark Execution

Both tests were executed on compute node `ant20` using the Slurm scratch directory.

**3.1 Sequential Write**

```bash
fio --name=ssd-sequential-write \
    --filename="$SCRATCH/fio-test.tmp" \
    --size=1G \
    --rw=write \
    --bs=1M \
    --ioengine=sync \
    --iodepth=1 \
    --direct=1 \
    --numjobs=1 \
    --runtime=30 \
    --time_based \
    --group_reporting
```

**3.2 Sequential Read**

```bash
fio --name=ssd-sequential-read \
    --filename="$SCRATCH/fio-test.tmp" \
    --size=1G \
    --rw=read \
    --bs=1M \
    --ioengine=sync \
    --iodepth=1 \
    --direct=1 \
    --numjobs=1 \
    --runtime=30 \
    --time_based \
    --group_reporting
```

The read test used the same temporary file created during the write test.

### 4. Benchmark Results

The following values were obtained from the actual fio execution output.

| Metric | Sequential Write | Sequential Read |
|---|---:|---:|
| Bandwidth | 4530 MiB/s | 5859 MiB/s |
| IOPS | 4530 | 5858 |
| Average latency | 220.45 µs | 170.54 µs |
| Runtime | 30.001 s | 30.001 s |
| Total I/O | 133 GiB | 172 GiB |
| Errors | 0 | 0 |

### 5. Additional fio Observations

**Sequential Write**

- Average completion latency (clat): 195.98 µs.
- Average total latency: 220.45 µs.
- Bandwidth standard deviation: 55.64 MiB/s.
- Device utilization reported by fio: 83.81%.

**Sequential Read**

- Average completion latency (clat): 170.53 µs.
- Average total latency: 170.54 µs.
- Bandwidth standard deviation: 38.33 MiB/s.
- Device utilization reported by fio: 90.50%.

### 6. Results Analysis

The sequential read test achieved higher bandwidth than the sequential write test.

- Read bandwidth: 5859 MiB/s.
- Write bandwidth: 4530 MiB/s.
- Read performance was approximately 29.3% higher than write performance.

The average read latency was also lower than the average write latency under this configuration.

Both tests completed with zero reported fio errors.

These measurements establish an initial performance baseline for subsequent SSD I/O experiments.

### 7. Execution Validation

Both fio commands completed their 30-second benchmark runs successfully.

The output reported `err=0` for both tests.

The Slurm job was subsequently cancelled because it reached its allocated time limit. This happened after both benchmark tests had completed and does not affect the recorded results.

### 8. Limitations

- Only one block size (1 MiB) was tested.
- Queue depth was fixed at 1.
- Only sequential read and write operations were evaluated.
- The synchronous I/O engine was used.
- Measurements characterize the tested scratch filesystem and its underlying storage environment, not necessarily the raw NVMe device in isolation.
- The results do not represent the maximum theoretical performance of the NVMe SSD.

### 9. Next Experiments

The next experiments will investigate:

1. The effect of different block sizes on sequential read and write bandwidth.
2. Random read and write performance.
3. The impact of different queue depths.
4. Performance differences between supported I/O engines.
5. Bandwidth, IOPS and latency under different configurations.

The results will be recorded separately to support comparison and analysis.

### 10. Conclusion

The initial sequential I/O benchmark was successfully completed on the TH Deggendorf HexHPC cluster using fio.

The tested scratch storage achieved 4530 MiB/s sequential write bandwidth and 5859 MiB/s sequential read bandwidth with a 1 MiB block size and queue depth of 1.

These measurements provide the first baseline for further investigation of SSD I/O performance under different workloads and configurations.