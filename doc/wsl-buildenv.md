# Prepare WSL Build Environment

The build script requires root privileges, so AN EXCLUSIVE DISTRO is highly recommended.

## Install WSL

- WSL 1: check “Windows Subsystem for Linux” in “Turn Windows features on or off” dialog is sufficient.
- WSL 2: see [Microsoft Learn](https://learn.microsoft.com/en-us/windows/wsl/install).

## Create an Exclusive Distro

1. Download Alpine Linux 3.20 mini rootfs tarball from [Alpine Linux Repository](https://dl-cdn.alpinelinux.org/alpine/v3.20/releases/x86_64/).
2. Import it into WSL, for example:
   ```pwsh
   wsl --import competitive-cross-gcc-buildenv C:\wsl\competitive-cross-gcc-buildenv Downloads\alpine-minirootfs-3.20.5-x86_64.tar.gz
   ```
3. Restart Windows Terminal. “competitive-cross-gcc-buildenv” now appears in the dropdown list.

## Install Dependencies

1. Launch the exclusive distro (launch “Terminal”, select “competitive-cross-gcc-buildenv” from the dropdown list).
2. Install required packages:
   ```bash
   apk update
   apk add \
     autoconf automake bison build-base flex libtool rsync texinfo xmake \
     7zip ca-certificates curl file gawk libarchive-tools py3-packaging python3 zstd
   ```

## Clone the Repository

Cloning to Windows filesystem is recommended. For example with Windows Git Bash:
```bash
git clone https://github.com/redpanda-cpp/competitive-cross-gcc.git /d/competitive-cross-gcc --config=core.autocrlf=false
```

Auto-converting line endings must be disabled. To disable in an existing repo, run:
```bash
# save workspace
git add *
git stash

# do convertion
git config core.autocrlf false
git reset --hard

# restore workspace
git stash pop
```
