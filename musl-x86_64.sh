#!/bin/bash

# usage:
#   podman run -it --rm -v $PWD:/mnt -w /mnt docker.io/amd64/ubuntu:24.04
#   ./support/dep.sh
#   ./musl-x86_64.sh

set -euxo pipefail

function build__gnu_gnu_musl__binutils() {
  pushd build/binutils-2.43.1
  (
    mkdir -p build-gnu-musl-x86_64 && cd build-gnu-musl-x86_64
    ../configure \
      --prefix=/mnt/cross \
      --target=x86_64-linux-musl \
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
  # trick: use host gcc to build musl
  pushd build/musl-1.2.5
  (
    mkdir -p build-x86_64 && cd build-x86_64
    ../configure \
      --prefix=/x86_64-linux-musl \
      --target=x86_64-linux-musl \
      --disable-shared \
      --enable-static \
      --disable-gcc-wrapper \
      CC=gcc \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make DESTDIR=/mnt/cross install
    make DESTDIR=/mnt/pkg-x86_64 install
  )
  popd
}

function build__gnu_gnu_musl__gcc() {
  pushd build/gcc-14.2.0
  (
    mkdir -p build-gnu-musl-x86_64 && cd build-gnu-musl-x86_64
    ../configure \
      --prefix=/mnt/cross \
      --target=x86_64-linux-musl \
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
    mkdir -p build-mingw-musl-x86_64 && cd build-mingw-musl-x86_64
    ../configure \
      --prefix=/ \
      --target=x86_64-linux-musl \
      --host=x86_64-w64-mingw32 \
      --disable-multilib \
      --disable-nls \
      --with-static-standard-libraries \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make DESTDIR=/mnt/pkg-x86_64 tooldir=/ install
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
    mkdir -p build-mingw-musl-x86_64 && cd build-mingw-musl-x86_64
    ../configure \
      --prefix=/ \
      --libexecdir=//lib \
      --with-gcc-major-version-only \
      --target=x86_64-linux-musl \
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
    make DESTDIR=/mnt/pkg-x86_64 install
  )
  popd
}

function create_unprefixed_tool() {
  pushd /mnt/pkg-x86_64/bin
  (
    for f in x86_64-linux-musl-*; do
      local unprefixed=${f#x86_64-linux-musl-}
      if [[ ! -f $unprefixed ]]; then
        ln -s $f $unprefixed
      fi
    done
  )
  popd
}

function package() {
  if [[ ! -h 'gcc-14 on x86_64-w64-mingw32 for x86_64-linux-musl' ]]; then
    ln -s pkg-x86_64 'gcc-14 on x86_64-w64-mingw32 for x86_64-linux-musl'
  fi
  7z a -t7z \
    -mf=BCJ2 -mx9 -ms=on -mqs -m0=LZMA:d=64m:fb273 \
    'gcc-14 on x86_64-w64-mingw32 for x86_64-linux-musl.7z' \
    'gcc-14 on x86_64-w64-mingw32 for x86_64-linux-musl'
}

./support/prepare_source.sh
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
