#!/bin/bash

set -euxo pipefail

mkdir -p assets build

if [[ ! -d build/binutils-2.43.1 ]]; then
  if [[ ! -f assets/binutils-2.43.1.tar.zst ]]; then
    curl -L https://ftpmirror.gnu.org/binutils/binutils-2.43.1.tar.zst -o assets/binutils-2.43.1.tar.zst
  fi
  bsdtar -C build -xf assets/binutils-2.43.1.tar.zst --no-same-owner
fi

if [[ ! -d build/gcc-14.2.0 ]]; then
  if [[ ! -f assets/gcc-14.2.0.tar.xz ]]; then
    curl -L https://ftpmirror.gnu.org/gcc/gcc-14.2.0/gcc-14.2.0.tar.xz -o assets/gcc-14.2.0.tar.xz
  fi
  bsdtar -C build -xf assets/gcc-14.2.0.tar.xz --no-same-owner
  sed -i '/m64=/s/lib64/lib/' build/gcc-14.2.0/gcc/config/i386/t-linux64
  sed -i '/mabi.lp64=/s/lib64/lib/' build/gcc-14.2.0/gcc/config/aarch64/t-aarch64-linux
fi

if [[ ! -d build/glibc-2.40 ]]; then
  if [[ ! -f assets/glibc-2.40.tar.xz ]]; then
    curl -L https://ftpmirror.gnu.org/glibc/glibc-2.40.tar.xz -o assets/glibc-2.40.tar.xz
  fi
  bsdtar -C build -xf assets/glibc-2.40.tar.xz --no-same-owner
fi

if [[ ! -d build/gmp-6.3.0 ]]; then
  if [[ ! -f assets/gmp-6.3.0.tar.zst ]]; then
    curl -L https://ftpmirror.gnu.org/gmp/gmp-6.3.0.tar.zst -o assets/gmp-6.3.0.tar.zst
  fi
  bsdtar -C build -xf assets/gmp-6.3.0.tar.zst --no-same-owner
fi

if [[ ! -d build/linux-4.4.302 ]]; then
  if [[ ! -f assets/linux-4.4.302.tar.xz ]]; then
    curl -L https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-4.4.302.tar.xz -o assets/linux-4.4.302.tar.xz
  fi
  bsdtar -C build -xf assets/linux-4.4.302.tar.xz --no-same-owner
fi

if [[ ! -d build/mpc-1.3.1 ]]; then
  if [[ ! -f assets/mpc-1.3.1.tar.gz ]]; then
    curl -L https://ftpmirror.gnu.org/mpc/mpc-1.3.1.tar.gz -o assets/mpc-1.3.1.tar.gz
  fi
  bsdtar -C build -xf assets/mpc-1.3.1.tar.gz --no-same-owner
fi

if [[ ! -d build/mpfr-4.2.1 ]]; then
  if [[ ! -f assets/mpfr-4.2.1.tar.xz ]]; then
    curl -L https://ftpmirror.gnu.org/mpfr/mpfr-4.2.1.tar.xz -o assets/mpfr-4.2.1.tar.xz
  fi
  bsdtar -C build -xf assets/mpfr-4.2.1.tar.xz --no-same-owner
fi

if [[ ! -d build/musl-1.2.5 ]]; then
  if [[ ! -f assets/musl-1.2.5.tar.gz ]]; then
    curl -L https://www.musl-libc.org/releases/musl-1.2.5.tar.gz -o assets/musl-1.2.5.tar.gz
  fi
  bsdtar -C build -xf assets/musl-1.2.5.tar.gz --no-same-owner
fi

if [[ ! -d /opt/x-mingw64-ucrt-14 ]]; then
  if [[ ! -f assets/x-mingw64-ucrt-14.2.0-r4.tar.zst ]]; then
    curl -L https://github.com/redpanda-cpp/mingw-lite/releases/download/14.2.0-r4/x-mingw64-ucrt-14.2.0-r4.tar.zst -o assets/x-mingw64-ucrt-14.2.0-r4.tar.zst
  fi
  bsdtar -C / -xf assets/x-mingw64-ucrt-14.2.0-r4.tar.zst --no-same-owner
fi
