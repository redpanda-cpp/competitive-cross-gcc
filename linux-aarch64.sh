#!/bin/bash

# usage:
#   podman run -it --rm -v $PWD:/mnt -w /mnt docker.io/amd64/ubuntu:24.04
#   ./support/dep.sh
#   ./linux-aarch64.sh

set -euxo pipefail

_build=x86_64-linux-gnu
_host=x86_64-w64-mingw32
_target=aarch64-linux-gnu
_x_prefix=$PWD/cross
_prefix=$PWD/gcc-linux-aarch64

function install_kernel_headers() {
  pushd build/linux-4.4.302
  (
    make headers_install \
      ARCH=arm64 \
      INSTALL_HDR_PATH=$_x_prefix/$_target
    make headers_install \
      ARCH=arm64 \
      INSTALL_HDR_PATH=$_prefix/$_target

    # remove hidden files `.install` and `..install.cmd`
    find $_prefix/$_target/include/linux -name '.*' -delete

    # netfilter has pairs of files that only differ in case
    rm -rf $_prefix/$_target/include/linux/netfilter*
  )
  popd
}

function build_part1_binutils() {
  pushd build/binutils-2.43.1
  (
    mkdir -p build-$_build-$_target && cd build-$_build-$_target
    ../configure \
      --prefix=$_x_prefix \
      --target=$_target \
      --host=$_build \
      --disable-multilib \
      --disable-nls \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build_part1_gcc_p1() {
  pushd build/gcc-14.2.0
  (
    mkdir -p build-$_build-$_target && cd build-$_build-$_target
    ../configure \
      --prefix=$_x_prefix \
      --target=$_target \
      --host=$_build \
      \
      --disable-shared \
      --enable-static \
      \
      --disable-bootstrap \
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
    make -j$(nproc) all-gcc
    make install-gcc
  )
  popd
}

function build_glibc_p1() {
  pushd build/glibc-2.40
  (
    mkdir -p build-$_target && cd build-$_target

    # static-only is not supported
    # here we build with dynamic library enabled ...
    ../configure \
      --prefix= \
      --host=$_target \
      \
      --enable-shared \
      --enable-static \
      --enable-static-nss \
      \
      --disable-build-nscd \
      --disable-fortify-source \
      --enable-kernel=4.4.0 \
      --disable-multi-arch \
      --disable-nscd \
      --disable-timezone-tools \
      \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make DESTDIR=$_x_prefix/$_target install-headers
    make DESTDIR=$_prefix/$_target install-headers
    touch $_x_prefix/$_target/include/gnu/stubs.h
  )
  popd
}

function build_part1_gcc_p2() {
  pushd build/gcc-14.2.0/build-$_build-$_target
  (
    make -j$(nproc) all-target-libgcc
    make install-target-libgcc
  )
  popd
}

function build_glibc_p2() {
  pushd build/glibc-2.40/build-$_target
  (
    make -j$(nproc)
    make DESTDIR=$_x_prefix/$_target install
    make DESTDIR=$_prefix/$_target install

    # ... and then remove the dynamic library (and other stuff)
    rm -rf $_prefix/$_target/lib/*.so*
    rm -rf $_prefix/$_target/{bin,etc,lib/audit,lib/gconv,libexec,sbin,share,var}

    # fix libm.a reference path
    sed -i 's|/lib/|./|g' \
      $_x_prefix/$_target/lib/lib{c.so,m.so,m.a} \
      $_prefix/$_target/lib/libm.a
  )
  popd
}

function build_part1_gcc_p3() {
  pushd build/gcc-14.2.0/build-$_build-$_target
  (
    make -j$(nproc)
    make install
  )
  popd
}

function build_part3_binutils() {
  pushd build/binutils-2.43.1
  {
    mkdir -p build-$_host-$_target && cd build-$_host-$_target
    ../configure \
      --prefix= \
      --target=$_target \
      --host=$_host \
      --disable-multilib \
      --disable-nls \
      --with-static-standard-libraries \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make DESTDIR=$_prefix tooldir=/ install
  }
  popd
}

function build_part3_gmp() {
  pushd build/gmp-6.3.0
  (
    mkdir -p build-$_host && cd build-$_host
    ../configure \
      --prefix=$_x_prefix/$_host \
      --host=$_host \
      --disable-assembly \
      --enable-static \
      --disable-shared \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build_part3_mpfr() {
  pushd build/mpfr-4.2.1
  (
    mkdir -p build-$_host && cd build-$_host
    ../configure \
      --prefix=$_x_prefix/$_host \
      --host=$_host \
      --with-gmp=$_x_prefix/$_host \
      --enable-static \
      --disable-shared \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build_part3_mpc() {
  pushd build/mpc-1.3.1
  (
    mkdir -p build-$_host && cd build-$_host
    ../configure \
      --prefix=$_x_prefix/$_host \
      --host=$_host \
      --with-gmp=$_x_prefix/$_host \
      --with-mpfr=$_x_prefix/$_host \
      --enable-static \
      --disable-shared \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s
    make -j$(nproc)
    make install
  )
  popd
}

function build_part3_gcc() {
  pushd build/gcc-14.2.0
  (
    mkdir -p build-$_host-$_target && cd build-$_host-$_target
    ../configure \
      --prefix= \
      --libexecdir=/lib \
      --with-gcc-major-version-only \
      --target=$_target \
      --host=$_host \
      \
      --disable-plugin \
      --disable-shared \
      --enable-static \
      --without-pic \
      \
      --disable-bootstrap \
      --disable-checking \
      --enable-languages=c,c++ \
      --disable-libgomp \
      --disable-libsanitizer \
      --enable-lto \
      --disable-multilib \
      --disable-nls \
      \
      --with-gmp=$_x_prefix/$_host \
      --without-libcc1 \
      --without-libiconv \
      --without-libintl \
      --with-mpc=$_x_prefix/$_host \
      --with-mpfr=$_x_prefix/$_host \
      \
      CFLAGS=-O2 CXXFLAGS=-O2 LDFLAGS=-s \
      CFLAGS_FOR_TARGET=-O2 CXXFLAGS_FOR_TARGET=-O2 LDFLAGS_FOR_TARGET=-s
    make -j$(nproc)
    make DESTDIR=$_prefix install
  )
  popd
}

function create_unprefixed_tool() {
  pushd $_prefix/bin
  (
    for f in $_target-*; do
      local unprefixed=${f#$_target-}
      if [[ ! -f $unprefixed ]]; then
        ln -s $f $unprefixed
      fi
    done
  )
  popd
}

function package() {
  7z a -t7z \
    -mf=BCJ2 -mx9 -ms=on -mqs -m0=LZMA:d=64m:fb273 \
    gcc-linux-aarch64.7z \
    gcc-linux-aarch64
}

./support/prepare_source.sh
install_kernel_headers
export PATH=$_x_prefix/bin:/opt/x-mingw64-ucrt-14/bin:$PATH

#################################
## PART I: cross toolchain     ##
##   host  : x86_64-linux-gnu  ##
##   target: aarch64-linux-gnu ##
#################################

build_part1_binutils
build_part1_gcc_p1
build_glibc_p1
build_part1_gcc_p2
build_glibc_p2
build_part1_gcc_p3

########################################
## PART II: cross toolchain           ##
##   host  : x86_64-linux (libc-free) ##
##   target: x86_64-w64-mingw32       ##
## Provided by mingw-lite.            ##
########################################

##################################
## PART III: cross toolchain    ##
##   host  : x86_64-w64-mingw32 ##
##   target: aarch64-linux-gnu  ##
##################################

build_part3_binutils
build_part3_gmp
build_part3_mpfr
build_part3_mpc
build_part3_gcc

################
## PRODUCTION ##
################

create_unprefixed_tool
package
