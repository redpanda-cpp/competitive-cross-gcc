#!/bin/bash

set -euxo pipefail

apt update
apt install --no-install-recommends -y \
  autoconf automake bison build-essential crossbuild-essential-arm64 gawk texinfo \
  libgmp-dev libmpc-dev libmpfr-dev \
  ca-certificates curl 7zip libarchive-tools
