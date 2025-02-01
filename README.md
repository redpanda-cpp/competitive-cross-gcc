# Competitive Cross GCC

Cross GCC on Windows for Linux.

## Build

1. Prepare build environment. Linux:
   ```bash
   podman build -t competitive-cross-gcc/buildenv support/buildenv
   ```
   For Windows host, [create an exclusive WSL distro for competitive-cross-gcc](doc/wsl-buildenv.md).
2. Launch build environment. Linux:
   ```bash
   podman run -it --rm -v $PWD:/mnt -w /mnt competitive-cross-gcc/buildenv
   ```
   To expose build directories for debugging:
   ```bash
   podman run -it --rm \
     -v $PWD:/mnt -w /mnt \
     -v $PWD/build:/tmp/build \
     -v $PWD/pkg:/opt \
     competitive-cross-gcc/buildenv
   ```
   Windows: in “Terminal”, select “competitive-cross-gcc-buildenv” from the dropdown list.
3. In the build environment, run:
   ```bash
   ./main.py -b <branch>
   ```

Available branches:

| Branch | GCC | Binutils | Glibc \[OS (x86, arm)] | MinGW (OS) |
| ------ | --- | -------- | ---------------------- | ---------- |
| 15 | 15-20250209 | 2.44 | 2.41 (4.4) | 12.0.0 (10.0) |
| 14 | 14.2.0 | 2.43.1 | 2.40 (4.4) | 12.0.0 (10.0) |
| 13 | 13.3.0 | 2.41 | 2.38 (4.4) | 11.0.1 (10.0) |
| 12 | 12.4.0 | 2.39 | 2.36 (4.4) | 10.0.0 (6.3) |
| 11 | 11.5.0 | 2.37 | 2.34 (4.4) | 9.0.0 (6.3) |
| 10 | 10.5.0 | 2.35.2 | 2.32 (4.4) | 8.0.3 (6.3) |
| 9 | 9.5.0 | 2.33.1 | 2.30 (3.16) | 7.0.0 (6.1) |
| 8 | 8.5.0 | 2.31.1 | 2.28 (3.16) | 6.0.1 (6.1) |
| 7 | 7.5.0 | 2.29.1 | 2.26 (3.2, 3.16) | 5.0.5 (6.1) |
| 6 | 6.5.0 | 2.27 | 2.24 (3.2, 3.10) | 5.0.5 (6.0) |
| 5 | 5.5.0 | 2.25.1 | 2.22 (2.6.32, 3.10) | 4.0.6 (6.0) |
| 4.9 | 4.9.4 | 2.25.1 | 2.20 (2.6.32, 3.10) | 3.3.0 (6.0) |
| 4.8 | 4.8.5 | 2.24 | 2.18 (2.6.32, 3.10) | 3.3.0 (5.2) |
