import argparse
import json
import logging
import shutil
import subprocess
from packaging.version import Version

from module.debug import shell_here
from module.path import ProjectPaths
from module.profile import BranchProfile
from module.util import cflags_A, cflags_B, configure, ensure, make_custom, make_default, make_destdir_install, make_install, make_install, temporary_symlink

def _binutils(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.binutils / 'build-ABB'
  ensure(build_dir)
  configure('binutils', build_dir, [
    '--prefix=',
    '--target=x86_64-w64-mingw32',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    # static build
    '--with-static-standard-libraries',
    # features
    '--disable-install-libbfd',
    '--disable-multilib',
    '--disable-nls',
    # libtool eats `-static`
    *cflags_A(ld_extra = ['--static']),
  ])
  make_default('binutils', build_dir, config.jobs)
  make_custom('binutils (install)', build_dir, [
    f'DESTDIR={paths.mingw_prefix}',
    # use native layout
    f'tooldir={paths.mingw_prefix}',
    'install',
  ], jobs = 1)

def _headers(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mingw / 'mingw-w64-headers' / 'build-ABB'
  ensure(build_dir)

  if ver.win32_winnt >= 0x0A00:
    crt = 'ucrt'
  else:
    crt = 'msvcrt'

  configure('mingw-w64-headers', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    f'--with-default-msvcrt={crt}',
    f'--with-default-win32-winnt=0x{ver.win32_winnt:04X}',
  ])
  make_default('headers', build_dir, config.jobs)
  make_destdir_install('headers', build_dir, paths.mingw_prefix)

def _crt(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mingw / 'mingw-w64-crt' / 'build-ABB'
  ensure(build_dir)

  if ver.win32_winnt >= 0x0A00:
    crt = 'ucrt'
  else:
    crt = 'msvcrt'

  configure('crt', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    f'--with-default-msvcrt={crt}',
    f'--with-default-win32-winnt=0x{ver.win32_winnt:04X}',
    '--enable-lib64',
    '--disable-lib32',
    *cflags_B(),
  ])
  make_default('crt', build_dir, config.jobs)
  make_destdir_install('crt', build_dir, paths.mingw_prefix)

def _winpthreads(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mingw / 'mingw-w64-libraries' / 'winpthreads' / 'build-ABB'
  ensure(build_dir)
  configure('winpthreads', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_B(),
  ])
  make_default('winpthreads', build_dir, config.jobs)
  make_destdir_install('winpthreads', build_dir, paths.mingw_prefix)

def _gcc(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gcc)
  build_dir = paths.gcc / 'build-ABB'
  ensure(build_dir)
  configure('gcc', build_dir, [
    '--prefix=',
    f'--libexecdir=/lib',
    '--with-gcc-major-version-only',
    '--target=x86_64-w64-mingw32',
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
    '--enable-threads=posix',
    # packages
    '--without-libcc1',
    # libtool eats `-static`
    *cflags_B(ld_extra = ['--static']),
    *cflags_B('_FOR_TARGET', ld_extra = ['--static']),
  ])
  if v.major >= 8:
    make_default('gcc', build_dir, config.jobs)
  else:
    with temporary_symlink(paths.mingw_prefix, '/mingw'):
      make_default('gcc', build_dir, config.jobs)
  make_destdir_install('gcc', build_dir, paths.mingw_prefix)

  # emulate linux experience: add `print.o` to `libstdc++.a`,
  # allowing `<print>` without `-lstdc++exp`
  if 14 <= v.major < 16:
    res = subprocess.run([
      'x86_64-w64-mingw32-ar', 'r',
      paths.mingw_prefix / 'lib' / 'libstdc++.a',
      build_dir / 'x86_64-w64-mingw32' / 'libstdc++-v3' / 'src' / 'c++23' / 'print.o',
    ])
    if res.returncode != 0:
      message = f'Build fail: libstdc++ ar returned {res.returncode}'
      logging.critical(message)
      raise Exception(message)

def _gdb(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gdb)
  v_gcc = Version(ver.gcc)
  build_dir = paths.gdb / 'build-ABB'
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
    '--target=x86_64-w64-mingw32',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    # features
    '--disable-tui',
    # packages
    f'--with-system-gdbinit=/share/gdb/gdbinit',
    *python_flags,
    *cflags_B(
      common_extra = ['-DPDC_WIDE'],
      c_extra = c_extra
    ),
  ])
  make_default('gdb', build_dir, config.jobs)
  make_destdir_install('gdb', build_dir, paths.mingw_prefix)

  if ver.python:
    shutil.copy(paths.x_prefix / 'x86_64-w64-mingw32' / 'lib' / 'python.zip', paths.mingw_prefix / 'lib' / 'python.zip')
    with open(paths.mingw_prefix / 'bin' / 'gdb._pth', 'w') as f:
      f.write('../lib/python.zip\n')
    with open(paths.mingw_prefix / 'share' / 'gdb' / 'gdbinit', 'w') as f:
      f.write('python\n')
      f.write('from libstdcxx.v6.printers import register_libstdcxx_printers\n')
      f.write('register_libstdcxx_printers(None)\n')
      f.write('end\n')

def _gmake(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.make)
  v_gcc = Version(ver.gcc)
  build_dir = paths.make / f'build-ABB'
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
  shutil.copy(build_dir / 'make.exe', paths.mingw_prefix / 'bin' / 'mingw32-make.exe')

def _licenses(ver: BranchProfile, paths: ProjectPaths):
  license_dir = paths.mingw_prefix / 'share' / 'licenses'
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

  ensure(license_dir / 'gmp')
  if Version(ver.gmp).major < 6:
    gmp_files = ['README', 'COPYING', 'COPYING.LIB']
  else:
    gmp_files = ['README', 'COPYINGv2', 'COPYINGv3', 'COPYING.LESSERv3']
  for file in gmp_files:
    shutil.copy(paths.gmp / file, license_dir / 'gmp' / file)

  ensure(license_dir / 'make')
  shutil.copy(paths.make / 'COPYING', license_dir / 'make' / 'COPYING')

  ensure(license_dir / 'mingw-w64')
  shutil.copy(paths.mingw / 'COPYING', license_dir / 'mingw-w64' / 'COPYING')

  ensure(license_dir / 'mingw-w64-libraries-winpthreads')
  shutil.copy(paths.mingw / 'mingw-w64-libraries' / 'winpthreads' / 'COPYING', license_dir / 'mingw-w64-libraries-winpthreads' / 'COPYING')

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

def build_ABB_toolchain(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _binutils(ver, paths, config)

  _headers(ver, paths, config)

  _crt(ver, paths, config)

  _winpthreads(ver, paths, config)

  _gcc(ver, paths, config)

  _gdb(ver, paths, config)

  _gmake(ver, paths, config)

  _licenses(ver, paths)
