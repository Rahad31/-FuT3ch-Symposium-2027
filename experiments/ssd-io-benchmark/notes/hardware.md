# HexHPC Hardware Information

## Storage Device

- Cluster: TH Deggendorf HexHPC
- Compute node: ant20
- Device name: nvme0n1
- Model: PC801 NVMe SK hynix
- Reported capacity: 953.9 GB
- Storage type: NVMe SSD
- Filesystem: XFS
- Mount point: /scratch

## Software Environment

- Operating system: AlmaLinux 10.2
- Benchmark software: fio 3.43-49-g6288
- Scheduler: Slurm

## Initial Observations

The NVMe device was identified using `lsblk`.

The scratch filesystem was accessible from the allocated compute node.

Write access was verified using a temporary test file.
