FROM docker.io/amd64/alpine:3.20

RUN apk update && \
    apk add \
      # build tools
      autoconf automake bison build-base flex libtool rsync texinfo xmake \
      # general tools
      7zip ca-certificates curl file gawk libarchive-tools py3-packaging python3 zstd
