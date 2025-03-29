import argparse
import glob
import os
from packaging.version import Version
import shutil
import subprocess

from module.debug import shell_here
from module.path import ProjectPaths
from module.profile import BranchProfile
from module.util import cflags_B, cflags_C, configure, ensure, fix_limits_h, make_custom, make_default, make_destdir_install

def _binutils(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.binutils / f'build-ABC-{arch}'
  ensure(build_dir)
  configure('binutils', build_dir, [
    '--prefix=',
    f'--target={arch}-linux-gnu',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    # static build
    '--disable-shared',
    '--enable-static',
    '--disable-werror',
    # features
    '--disable-install-libbfd',
    '--disable-multilib',
    '--disable-nls',
    # libtool eats `-static`
    *cflags_B(ld_extra = ['--static']),
  ])
  make_default('binutils', build_dir, config.jobs)
  make_custom('binutils', build_dir, [f'DESTDIR={paths.linux_prefix(arch)}', 'tooldir=/', 'install'], jobs = 1)

def _kernel_headers(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  KARCH_MAP = {
    'aarch64': 'arm64',
    'x86_64': 'x86',
  }

  prefix = paths.linux_prefix(arch) / f'{arch}-linux-gnu'

  make_custom('kernel headers', paths.kernel, [
    'headers_install',
    f'ARCH={KARCH_MAP[arch]}',
    f'INSTALL_HDR_PATH={prefix}',
  ], config.jobs)

  # remove hidden files `.install` and `..install.cmd`
  for file in prefix.glob('**/.install'):
    file.unlink()
  for file in prefix.glob('**/..install.cmd'):
    file.unlink()

  # netfilter has pairs of files that only differ in case
  # here we simply remove related headers
  for file in prefix.glob('include/linux/netfilter*'):
    if file.is_dir():
      shutil.rmtree(file)
    else:
      file.unlink()

def _glibc(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.glibc)
  build_dir = paths.glibc / f'build-ABC-{arch}'
  ensure(build_dir)

  prefix = paths.linux_prefix(arch) / f'{arch}-linux-gnu'
  destdir = paths.glibc / f'pkg-ABC-{arch}'

  configure('glibc', build_dir, [
    '--prefix=',
    f'--host={arch}-linux-gnu',
    f'--build={config.build}',
    # static-only is not supported
    # here we build with dynamic library enabled ...
    '--enable-share',
    '--enable-static',
    '--enable-static-nss',
    # features
    '--disable-build-nscd',
    '--disable-fortify-source',
    f'--enable-kernel={ver.enable_kernel(arch)}',
    '--disable-multi-arch',
    '--disable-nscd',
    '--disable-timezone-tools',
    '--disable-werror',
    *cflags_C(ld_extra = ['-static']),
    # disable C++ to avoid -lgcc_s in test links-dso-program
    # which is not supported by static compiler
    'CXX=false',
  ])
  make_default('glibc', build_dir, config.jobs)
  make_destdir_install('glibc', build_dir, destdir)

  # ... and then remove the dynamic library (and other stuff)
  for file in destdir.glob('lib/*.so*'):
    file.unlink()
  remove_dirs = ['bin', 'etc', 'lib/gconv', 'libexec', 'sbin', 'share', 'var']
  # not sure since 2.19 or 2.20
  if v >= Version('2.20'):
    remove_dirs.append('lib/audit')
  for dir in remove_dirs:
    shutil.rmtree(f'{destdir}/{dir}')

  # fix libm.a reference path
  if (arch == 'x86_64' and v >= Version('2.25')) or (arch == 'aarch64' and v >= Version('2.38')):
    libm_content = open(f'{destdir}/lib/libm.a', 'r').read()
    with open(f'{destdir}/lib/libm.a', 'w') as f:
      f.write(libm_content.replace('/lib/', './'))

  # really install
  shutil.copytree(destdir, prefix, dirs_exist_ok = True)

def _gcc(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gcc)
  build_dir = paths.gcc / f'build-ABC-{arch}'
  ensure(build_dir)

  prefix = paths.linux_prefix(arch)
  libexec_target = prefix / 'lib' / 'gcc' / f'{arch}-linux-gnu'

  config_flags = []

  if v.major >= 13:
    config_flags.append('--with-gcc-major-version-only')
    limits_h = libexec_target / str(v.major) / 'include' / 'limits.h'
  elif v.major >= 7:
    config_flags.append('--with-gcc-major-version-only')
    limits_h = libexec_target / str(v.major) / 'include-fixed' / 'limits.h'
  else:
    limits_h = libexec_target / ver.gcc / 'include-fixed' / 'limits.h'

  configure('gcc', build_dir, [
    '--prefix=',
    f'--libexecdir=/lib',
    f'--target={arch}-linux-gnu',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    # static build
    '--disable-plugin',
    '--disable-shared',
    '--enable-static',
    '--without-pic',
    # features
    '--disable-bootstrap',
    '--enable-checking=release',
    '--enable-languages=c,c++',
    '--disable-libmpx',
    '--disable-multilib',
    '--enable-nls',
    # packages
    '--without-libcc1',
    *config_flags,
    # libtool eats `-static`
    *cflags_B(ld_extra = ['--static']),
    *cflags_C('_FOR_TARGET', ld_extra = ['--static']),
  ])
  make_default('gcc', build_dir, config.jobs)
  make_destdir_install('gcc', build_dir, prefix)
  fix_limits_h(limits_h, paths.gcc)

def _gdb(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gdb)
  v_gcc = Version(ver.gcc)
  build_dir = paths.gdb / f'build-ABC-{arch}'
  ensure(build_dir)

  python_flags = []
  c_extra = []

  if ver.python:
    python_flags.append(f'--with-python={paths.x_prefix}/x86_64-w64-mingw32/python-config.sh')

  # GCC 15 defaults to C23, in which `foo()` means `foo(void)` instead of `foo(...)`.
  if v_gcc.major >= 15 and v < Version('16.3'):
    c_extra.append('-std=gnu11')

  configure('gdb', build_dir, [
    '--prefix=',
    f'--target={arch}-linux-gnu',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    # static build
    '--disable-inprocess-agent',
    '--disable-shared',
    '--enable-static',
    # features
    '--disable-sim',
    '--disable-tui',
    # packages
    '--without-gdbserver',
    '--with-system-gdbinit=/share/gdb/gdbinit',
    *python_flags,
    # libtool eats `-static`
    *cflags_B(
      c_extra = c_extra,
      ld_extra = ['--static']
    ),
  ])
  make_default('gdb', build_dir, config.jobs)
  make_destdir_install('gdb', build_dir, paths.linux_prefix(arch))

  if ver.python:
    shutil.copy(paths.x_prefix / 'x86_64-w64-mingw32' / 'lib' / 'python.zip', paths.linux_prefix(arch) / 'lib' / 'python.zip')
    with open(paths.linux_prefix(arch) / 'bin' / 'gdb._pth', 'w') as f:
      f.write('../lib/python.zip\n')
    with open(paths.linux_prefix(arch) / 'share' / 'gdb' / 'gdbinit', 'w') as f:
      f.write('python\n')
      f.write('from libstdcxx.v6.printers import register_libstdcxx_printers\n')
      f.write('register_libstdcxx_printers(None)\n')
      f.write('end\n')

def _gmake(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.make)
  v_gcc = Version(ver.gcc)
  build_dir = paths.make / f'build-ABC-{arch}'
  ensure(build_dir)

  c_extra = []

  # GCC 15 defaults to C23, in which `foo()` means `foo(void)` instead of `foo(...)`.
  if v_gcc.major >= 15 and v < Version('4.5'):
    c_extra.append('-std=gnu11')

  configure('make', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    '--disable-nls',
    *cflags_B(c_extra = c_extra),
  ])
  make_default('make', build_dir, config.jobs)
  shutil.copy(build_dir / 'make.exe', paths.linux_prefix(arch) / 'bin' / 'mingw32-make.exe')

def _licenses(arch: str, ver: BranchProfile, paths: ProjectPaths):
  license_dir = paths.linux_prefix(arch) / 'share' / 'licenses'
  ensure(license_dir)

  ensure(license_dir / 'binutils')
  for file in ['README', 'COPYING', 'COPYING3', 'COPYING.LIB', 'COPYING3.LIB']:
    shutil.copy(paths.binutils / 'COPYING3', license_dir / 'binutils' / 'COPYING3')

  ensure(license_dir / 'gcc')
  for file in ['README', 'COPYING', 'COPYING3', 'COPYING.RUNTIME', 'COPYING.LIB', 'COPYING3.LIB']:
    shutil.copy(paths.gcc / file, license_dir / 'gcc' / file)

  ensure(license_dir / 'gdb')
  for file in ['README', 'COPYING', 'COPYING3', 'COPYING.LIB', 'COPYING3.LIB']:
    shutil.copy(paths.gdb / file, license_dir / 'gdb' / file)

  if ver.gettext:
    ensure(license_dir / 'gettext-runtime-intl')
    shutil.copy(paths.gettext / 'gettext-runtime' / 'intl' / 'COPYING.LIB', license_dir / 'gettext-runtime-intl' / 'COPYING.LIB')

  ensure(license_dir / 'glibc')
  for file in ['COPYING', 'COPYING.LIB', 'LICENSES']:
    shutil.copy(paths.glibc / file, license_dir / 'glibc' / file)

  ensure(license_dir / 'gmp')
  if Version(ver.gmp).major < 6:
    gmp_files = ['README', 'COPYING', 'COPYING.LIB']
  else:
    gmp_files = ['README', 'COPYINGv2', 'COPYINGv3', 'COPYING.LESSERv3']
  for file in gmp_files:
    shutil.copy(paths.gmp / file, license_dir / 'gmp' / file)

  ensure(license_dir / 'linux')
  shutil.copy(paths.kernel / 'COPYING', license_dir / 'linux' / 'COPYING')
  if Version(ver.kernel) >= Version('4.19'):
    shutil.copy(paths.kernel / 'LICENSES' / 'preferred' / 'GPL-2.0', license_dir / 'linux' / 'GPL-2.0')
    shutil.copy(paths.kernel / 'LICENSES' / 'exceptions' / 'Linux-syscall-note', license_dir / 'linux' / 'Linux-syscall-note')

  ensure(license_dir / 'make')
  shutil.copy(paths.make / 'COPYING', license_dir / 'make' / 'COPYING')

  ensure(license_dir / 'mpc')
  shutil.copy(paths.mpc / 'COPYING.LESSER', license_dir / 'mpc' / 'COPYING.LESSER')

  ensure(license_dir / 'mpfr')
  shutil.copy(paths.mpfr / 'COPYING.LESSER', license_dir / 'mpfr' / 'COPYING.LESSER')

  if ver.python:
    ensure(license_dir / 'python')
    shutil.copy(paths.python / 'LICENSE', license_dir / 'python' / 'LICENSE')

  if ver.python_z:
    ensure(license_dir / 'zlib')
    shutil.copy(paths.python_z / 'LICENSE', license_dir / 'zlib' / 'LICENSE')

def build_ABC_toolchain(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _binutils(arch, ver, paths, config)

  _kernel_headers(arch, ver, paths, config)

  _glibc(arch, ver, paths, config)

  _gcc(arch, ver, paths, config)

  _gdb(arch, ver, paths, config)

  _gmake(arch, ver, paths, config)

  _licenses(arch, ver, paths)

def create_ABC_alias(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  bindir = paths.linux_prefix(arch) / 'bin'
  target_prefix = f'{arch}-linux-gnu-'
  for file in bindir.glob(f'{target_prefix}*'):
    unprefixed = bindir / file.name[len(target_prefix):]
    if unprefixed.exists():
      if file.samefile(unprefixed):
        continue
      else:
        unprefixed.unlink()
    os.link(file, unprefixed)
