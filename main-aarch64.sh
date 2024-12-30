#!/bin/bash

# usage:
#   podman run -it --rm -v $PWD:/mnt -w /mnt docker.io/amd64/ubuntu:24.04
#   ./support/dep.sh
#   ./main-aarch64.sh

set -euxo pipefail

function prepare_source() {
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
  fi
  if [[ ! -d build/gmp-6.3.0 ]]; then
    if [[ ! -f assets/gmp-6.3.0.tar.zst ]]; then
      curl -L https://ftpmirror.gnu.org/gmp/gmp-6.3.0.tar.zst -o assets/gmp-6.3.0.tar.zst
    fi
    bsdtar -C build -xf assets/gmp-6.3.0.tar.zst --no-same-owner
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
}

function build__gnu_gnu_musl__binutils() {
  pushd build/binutils-2.43.1
  (
    mkdir -p build-gnu-musl-aarch64 && cd build-gnu-musl-aarch64
    ../configure \
      --prefix=/mnt/cross \
      --target=aarch64-linux-musl \
      --host=x86_64-linux-gnu \
      --disable-multilib \
      --disable-nls \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build__gnu_musl__musl() {
  # trick: use aarch64-gnu gcc to build musl
  pushd build/musl-1.2.5
  (
    mkdir -p build-aarch64 && cd build-aarch64
    ../configure \
      --prefix=/aarch64-linux-musl \
      --target=aarch64-linux-musl \
      --disable-shared \
      --enable-static \
      --disable-gcc-wrapper \
      CC=aarch64-linux-gnu-gcc \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make DESTDIR=/mnt/cross install
    make DESTDIR=/mnt/pkg-aarch64 install
  )
  popd
}

function build__gnu_gnu_musl__gcc() {
  pushd build/gcc-14.2.0
  (
    mkdir -p build-gnu-musl-aarch64 && cd build-gnu-musl-aarch64
    ../configure \
      --prefix=/mnt/cross \
      --target=aarch64-linux-musl \
      --host=x86_64-linux-gnu \
      \
      --disable-checking \
      --enable-languages=c,c++ \
      --disable-libgomp \
      --disable-libsanitizer \
      --disable-lto \
      --disable-multilib \
      --disable-nls \
      \
      --without-libcc1 \
      --without-libiconv \
      --without-libintl \
      \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s \
      CFLAGS_FOR_TARGET=-O2 CXXFLAGS_FOR_TARGET=-O2 LDFLAGS_FOR_TARGET=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build__gnu_mingw_musl__binutils() {
  pushd build/binutils-2.43.1
  {
    mkdir -p build-mingw-musl-aarch64 && cd build-mingw-musl-aarch64
    ../configure \
      --prefix=/ \
      --target=aarch64-linux-musl \
      --host=x86_64-w64-mingw32 \
      --disable-multilib \
      --disable-nls \
      --with-static-standard-libraries \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make DESTDIR=/mnt/pkg-aarch64 tooldir=/ install
  }
  popd
}

function build__gnu_mingw__gmp() {
  pushd build/gmp-6.3.0
  (
    mkdir -p build-x86_64 && cd build-x86_64
    ../configure \
      --prefix=/mnt/dep-x86_64 \
      --host=x86_64-w64-mingw32 \
      --disable-assembly \
      --enable-static \
      --disable-shared \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build__gnu_mingw__mpfr() {
  pushd build/mpfr-4.2.1
  (
    mkdir -p build-x86_64 && cd build-x86_64
    ../configure \
      --prefix=/mnt/dep-x86_64 \
      --host=x86_64-w64-mingw32 \
      --with-gmp=/mnt/dep-x86_64 \
      --enable-static \
      --disable-shared \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build__gnu_mingw__mpc() {
  pushd build/mpc-1.3.1
  (
    mkdir -p build-x86_64 && cd build-x86_64
    ../configure \
      --prefix=/mnt/dep-x86_64 \
      --host=x86_64-w64-mingw32 \
      --with-gmp=/mnt/dep-x86_64 \
      --with-mpfr=/mnt/dep-x86_64 \
      --enable-static \
      --disable-shared \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build__gnu_mingw_musl__gcc() {
  pushd build/gcc-14.2.0
  (
    mkdir -p build-mingw-musl-aarch64 && cd build-mingw-musl-aarch64
    ../configure \
      --prefix=/ \
      --libexecdir=//lib \
      --with-gcc-major-version-only \
      --target=aarch64-linux-musl \
      --host=x86_64-w64-mingw32 \
      \
      --disable-plugin \
      --disable-shared \
      --enable-static \
      --without-pic \
      \
      --disable-checking \
      --enable-languages=c,c++ \
      --disable-libgomp \
      --disable-libsanitizer \
      --enable-lto \
      --disable-multilib \
      --disable-nls \
      \
      --with-gmp=/mnt/dep-x86_64 \
      --without-libcc1 \
      --without-libiconv \
      --without-libintl \
      --with-mpc=/mnt/dep-x86_64 \
      --with-mpfr=/mnt/dep-x86_64 \
      \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s \
      CFLAGS_FOR_TARGET=-O2 CXXFLAGS_FOR_TARGET=-O2 LDFLAGS_FOR_TARGET=-s
    make -j$(nproc)
    make DESTDIR=/mnt/pkg-aarch64 install
  )
  popd
}

function create_unprefixed_tool() {
  pushd /mnt/pkg-aarch64/bin
  (
    for f in aarch64-linux-musl-*; do
      local unprefixed=${f#aarch64-linux-musl-}
      if [[ ! -f $unprefixed ]]; then
        ln -s $f $unprefixed
      fi
    done
  )
  popd
}

function package() {
  if [[ ! -h 'gcc-14 on x86_64-w64-mingw32 for aarch64-linux-musl' ]]; then
    ln -s pkg-aarch64 'gcc-14 on x86_64-w64-mingw32 for aarch64-linux-musl'
  fi
  7z a -t7z \
    -mf=BCJ2 -mx9 -ms=on -mqs -m0=LZMA:d=64m:fb273 \
    'gcc-14 on x86_64-w64-mingw32 for aarch64-linux-musl.7z' \
    'gcc-14 on x86_64-w64-mingw32 for aarch64-linux-musl'
}

prepare_source
export PATH=/mnt/cross/bin:/opt/x-mingw64-ucrt-14/bin:$PATH
build__gnu_gnu_musl__binutils
build__gnu_musl__musl
build__gnu_gnu_musl__gcc
# gnu-gnu-mingw toolchain provided by mingw-lite
build__gnu_mingw_musl__binutils
build__gnu_mingw__gmp
build__gnu_mingw__mpfr
build__gnu_mingw__mpc
build__gnu_mingw_musl__gcc
create_unprefixed_tool
package
