import logging
import os
from packaging.version import Version
from pathlib import Path
from shutil import copyfile
import subprocess

from module.fetch import validate_and_download, check_and_extract
from module.path import ProjectPaths
from module.profile import BranchProfile

def _patch(path: Path, patch: Path):
  res = subprocess.run([
    'patch',
    '-Np1',
    '-i', patch,
  ], cwd = path)
  if res.returncode != 0:
    message = 'Patch fail: applying %s to %s' % (patch.name, path.name)
    logging.critical(message)
    raise Exception(message)

def _autoreconf(path: Path):
  res = subprocess.run([
    'autoreconf',
    '-fi',
  ], cwd = path)
  if res.returncode != 0:
    message = 'Autoreconf fail: %s' % path.name
    logging.critical(message)
    raise Exception(message)

def _automake(path: Path):
  res = subprocess.run([
    'automake',
  ], cwd = path)
  if res.returncode != 0:
    message = 'Automake fail: %s' % path.name
    logging.critical(message)
    raise Exception(message)

def _patch_done(path: Path):
  mark = path / '.patched'
  mark.touch()

def _binutils(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://ftpmirror.gnu.org/gnu/binutils/{paths.binutils_arx.name}'
  validate_and_download(paths.binutils_arx, url)
  if check_and_extract(paths.binutils, paths.binutils_arx):
    v = Version(ver.binutils)

    # Backport
    if v == Version('2.37'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'backport_2.37.patch')
    elif v == Version('2.33.1'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'backport_2.33.1.patch')
    elif v == Version('2.27'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'backport_2.27.patch')

    # Fix path corruption
    if v >= Version('2.43'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'fix-path-corruption_2.43.patch')
    elif v >= Version('2.41'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'fix-path-corruption_2.41.patch')
    elif v >= Version('2.39'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'fix-path-corruption_2.39.patch')

    # Fix elf compress alignment
    if Version('2.26') <= v < Version('2.32'):
      if v >= Version('2.30'):
        _patch(paths.binutils, paths.patch / 'binutils' / 'fix-elf-compress-alignment_2.30.patch')
      elif v >= Version('2.29'):
        _patch(paths.binutils, paths.patch / 'binutils' / 'fix-elf-compress-alignment_2.29.patch')
      else:
        _patch(paths.binutils, paths.patch / 'binutils' / 'fix-elf-compress-alignment_2.26.patch')

    # Always enable sysroot
    if v < Version('2.26'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'always-enable-sysroot.patch')

    # Fix musl locale name
    if v < Version('2.29.1'):
      _patch(paths.binutils, paths.patch / 'binutils' / 'fix-musl-locale-name.patch')

    _patch_done(paths.binutils)

def _gcc(ver: BranchProfile, paths: ProjectPaths):
  v = Version(ver.gcc)
  if v.major >= 15:
    url = f'https://gcc.gnu.org/pub/gcc/snapshots/{ver.gcc}/{paths.gcc_arx.name}'
  else:
    url = f'https://ftpmirror.gnu.org/gnu/gcc/gcc-{ver.gcc}/{paths.gcc_arx.name}'
  validate_and_download(paths.gcc_arx, url)
  if check_and_extract(paths.gcc, paths.gcc_arx):
    # Backport
    if v.major == 11:
      # - poisoned calloc when building with musl
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport_11.patch')
    elif v.major == 10:
      # - mingw define standard PRI macros when building against musl
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport_10.patch')
    elif v.major == 9:
      # - mingw define standard PRI macros when building against musl
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport_9.patch')
    elif v.major == 8:
      # - gcc fails to find cc1plus if built against ucrt due to a behaviour of `_access`
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport_8.patch')
    elif v.major == 7:
      # - someone declared `bool error_p = NULL`, it works until musl 1.2 defines NULL to nullptr
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport_7.patch')
    elif v.major == 6:
      # - someone declared `bool error_p = NULL`, it works until musl 1.2 defines NULL to nullptr
      # - intl adds `-liconv` without proper libdir
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport_6.patch')
    elif v.major == 5:
      # - someone declared `bool error_p = NULL`, it works until musl 1.2 defines NULL to nullptr
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport_5.patch')

    # Fix std module preprocessor condition
    if v.major == 15:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-std-module-pp-cond.patch')

    # Fix failure due to language standard evolve
    if v.major >= 6:
      pass
    elif v >= Version('4.9'):
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-lang-std_4.9.patch')
    else:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-lang-std_4.8.patch')

    # Backport `--with-glibc-version``
    if v == Version('4.8.5'):
      _patch(paths.gcc, paths.patch / 'gcc' / 'backport-with-glibc-version_4.8.5.patch')

    # Fix libc -> libgcc -> libc dependency
    if v.major >= 9:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-libc-libgcc-libc-dep_9.patch')
    elif v.major >= 8:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-libc-libgcc-libc-dep_8.patch')
    else:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-libc-libgcc-libc-dep_4.8.patch')

    # Fix make variable
    # - gcc 12 use `override CFLAGS +=` to handle PGO build, which breaks workaround for ucrt `access`
    if v.major >= 14:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-make-variable_14.patch')
    elif v.major >= 12:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-make-variable_12.patch')

    # Fix libatomic build
    if v >= Version('4.8') and v.major < 10:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-libatomic-build.patch')

    # Fix sanitizer dependency of crypt
    if v.major == 13:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-sanitizer-dep.patch')

    # Fix VT sequence
    if v.major >= 12:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-vt-seq_12.patch')
    elif v.major >= 8:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-vt-seq_8.patch')

    # Fix console code page
    if v.major >= 13:
      _patch(paths.gcc, paths.patch / 'gcc' / 'fix-console-cp.patch')

    # x86_64 use `lib` instead of `lib64`
    filepath = paths.gcc / 'gcc' / 'config' / 'i386' / 't-linux64'
    content = open(filepath).readlines()
    with open(filepath, 'w') as f:
      for line in content:
        if 'm64=' in line:
          f.write(line.replace('lib64', 'lib'))
        else:
          f.write(line)

    # aarch64 use `lib` instead of `lib64`
    filepath = paths.gcc / 'gcc' / 'config' / 'aarch64' / 't-aarch64-linux'
    content = open(filepath).readlines()
    with open(filepath, 'w') as f:
      for line in content:
        if 'mabi.lp64=' in line:
          f.write(line.replace('lib64', 'lib'))
        else:
          f.write(line)

    _patch_done(paths.gcc)

def _gdb(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://ftpmirror.gnu.org/gnu/gdb/{paths.gdb_arx.name}'
  validate_and_download(paths.gdb_arx, url)
  if check_and_extract(paths.gdb, paths.gdb_arx):
    v = Version(ver.gdb)

    # Backport
    if v.major == 10:
      _patch(paths.gdb, paths.patch / 'gdb' / 'backport_10.patch')
    elif v == Version('8.3.1'):
      _patch(paths.gdb, paths.patch / 'gdb' / 'backport_8.3.1.patch')
    elif v == Version('7.8.2'):
      _patch(paths.gdb, paths.patch / 'gdb' / 'backport-stub-termcap_7.8.2.patch')
    elif v == Version('7.6.2'):
      _patch(paths.gdb, paths.patch / 'gdb' / 'backport-stub-termcap_7.6.2.patch')

    _patch_done(paths.gdb)

def _glibc(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://ftpmirror.gnu.org/gnu/glibc/{paths.glibc_arx.name}'
  validate_and_download(paths.glibc_arx, url)
  if check_and_extract(paths.glibc, paths.glibc_arx):
    v = Version(ver.glibc)

    # Fix make 4.x
    # glibc locks autoconf version, here we patch configure instead of autoreconf
    # we do not use make 3.x because it's not easy to build on modern systems
    if v == Version('2.18'):
      _patch(paths.glibc, paths.patch / 'glibc' / 'fix-make-4.x_2.18.patch')

    # Disable sunrpc
    # glibc wrongly implements host tool `rpcgen` as glibc-only
    # since they finally removed it, we disable it for old versions
    if v < Version('2.26'):
      _patch(paths.glibc, paths.patch / 'glibc' / 'disable-sunrpc.patch')

    _patch_done(paths.glibc)

def _gmp(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://ftpmirror.gnu.org/gnu/gmp/{paths.gmp_arx.name}'
  validate_and_download(paths.gmp_arx, url)
  check_and_extract(paths.gmp, paths.gmp_arx)
  _patch_done(paths.gmp)

def _kernel(ver: BranchProfile, paths: ProjectPaths):
  v = Version(ver.kernel)
  url = f'https://cdn.kernel.org/pub/linux/kernel/v{v.major}.x/{paths.kernel_arx.name}'
  validate_and_download(paths.kernel_arx, url)
  if check_and_extract(paths.kernel, paths.kernel_arx):
    # Fix x86 reloc redefinition
    if v < Version('3.18'):
      _patch(paths.kernel, paths.patch / 'linux' / 'fix-x86-reloc-redefinition.patch')

    _patch_done(paths.kernel)

def _make(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://ftpmirror.gnu.org/gnu/make/{paths.make_arx.name}'
  validate_and_download(paths.make_arx, url)
  if check_and_extract(paths.make, paths.make_arx):
    v = Version(ver.make)

    # Backport
    if v == Version('4.3'):
      _patch(paths.make, paths.patch / 'make' / 'backport_4.3.patch')

    # Fix fcntl declaration
    if v == Version('4.3'):
      _patch(paths.make, paths.patch / 'make' / 'fix-fcntl-decl.patch')

    _patch_done(paths.make)

def _mingw(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://downloads.sourceforge.net/project/mingw-w64/mingw-w64/mingw-w64-release/{paths.mingw_arx.name}'
  validate_and_download(paths.mingw_arx, url)
  check_and_extract(paths.mingw, paths.mingw_arx)
  _patch_done(paths.mingw)

def _mpc(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://ftpmirror.gnu.org/gnu/mpc/{paths.mpc_arx.name}'
  validate_and_download(paths.mpc_arx, url)
  check_and_extract(paths.mpc, paths.mpc_arx)
  _patch_done(paths.mpc)

def _mpfr(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://ftpmirror.gnu.org/gnu/mpfr/{paths.mpfr_arx.name}'
  validate_and_download(paths.mpfr_arx, url)
  check_and_extract(paths.mpfr, paths.mpfr_arx)
  _patch_done(paths.mpfr)

def prepare_source(ver: BranchProfile, paths: ProjectPaths):
  _binutils(ver, paths)
  _gcc(ver, paths)
  _gdb(ver, paths)
  _glibc(ver, paths)
  _gmp(ver, paths)
  _kernel(ver, paths)
  _make(ver, paths)
  _mingw(ver, paths)
  _mpc(ver, paths)
  _mpfr(ver, paths)
