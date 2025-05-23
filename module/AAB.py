import argparse
from packaging.version import Version
import shutil
import subprocess

from module.debug import shell_here
from module.path import ProjectPaths
from module.profile import BranchProfile
from module.util import cflags_A, cflags_B, configure, ensure, fix_libtool_absolute_reference, make_custom, make_default, make_destdir_install, make_install

def _binutils(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.binutils / 'build-AAB'
  ensure(build_dir)
  configure('binutils', build_dir, [
    '--prefix=',
    '--target=x86_64-w64-mingw32',
    f'--build={config.build}',
    # static build
    '--disable-plugins',
    '--disable-shared',
    '--enable-static',
    '--disable-werror',
    # features
    '--disable-install-libbfd',
    '--disable-multilib',
    '--disable-nls',
    # libtool eats `-static`
    *cflags_A(ld_extra = ['--static']),
  ])
  make_default('binutils', build_dir, config.jobs)
  make_destdir_install('binutils', build_dir, paths.x_prefix)

def _headers(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mingw / 'mingw-w64-headers' / 'build-AAB'
  ensure(build_dir)

  if ver.win32_winnt >= 0x0A00:
    crt = 'ucrt'
  else:
    crt = 'msvcrt'

  configure('headers', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    f'--with-default-msvcrt={crt}',
    f'--with-default-win32-winnt=0x{ver.win32_winnt:04X}',
  ])
  make_default('headers', build_dir, config.jobs)
  make_destdir_install('headers', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

def _gcc(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gcc)
  build_dir = paths.gcc / 'build-AAB'
  ensure(build_dir)

  config_flags = []
  c_extra = []
  cxx_extra = []

  if v.major >= 7:
    config_flags.append('--with-gcc-major-version-only')
  else:
    c_extra.append('-std=gnu89')
    cxx_extra.append('-std=gnu++98')

  configure('gcc', build_dir, [
    f'--prefix={paths.x_prefix}',
    f'--libexecdir={paths.x_prefix}/lib',
    '--target=x86_64-w64-mingw32',
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
    '--disable-libgomp',
    '--disable-libmpx',
    '--disable-lto',
    '--disable-multilib',
    '--disable-nls',
    '--enable-threads=posix',
    # packages
    f'--with-gmp={paths.x_dep}',
    '--without-libcc1',
    f'--with-mpc={paths.x_dep}'
    f'--with-mpfr={paths.x_dep}',
    *config_flags,
    *cflags_A(
      c_extra = c_extra,
      cxx_extra = cxx_extra,
      # libtool eats `-static`
      ld_extra = ['--static'],
    ),
    *cflags_B('_FOR_TARGET', ld_extra = ['--static']),
  ])

  make_custom('gcc (all-gcc)', build_dir, ['all-gcc'], config.jobs)
  make_custom('gcc (install-gcc)', build_dir, ['install-gcc'], jobs = 1)
  yield

  make_default('gcc', build_dir, config.jobs)
  make_install('gcc', build_dir)
  yield

def _crt(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mingw / 'mingw-w64-crt' / 'build-AAB'
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
  make_destdir_install('crt', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

def _winpthreads(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mingw / 'mingw-w64-libraries' / 'winpthreads' / 'build-AAB'
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
  make_destdir_install('winpthreads', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

def build_AAB_compiler(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _binutils(ver, paths, config)

  _headers(ver, paths, config)

  gcc = _gcc(ver, paths, config)
  gcc.__next__()

  _crt(ver, paths, config)

  _winpthreads(ver, paths, config)

  gcc.__next__()

def _gmp(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gmp)
  v_gcc = Version(ver.gcc)
  build_dir = paths.gmp / 'build-AAB'
  ensure(build_dir)

  c_extra = []

  # GCC 15 defaults to C23, in which `foo()` means `foo(void)` instead of `foo(...)`.
  if v_gcc.major >= 15 and v < Version('6.4.0'):
    c_extra.append('-std=gnu11')

  configure('gmp', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    '--disable-assembly',
    '--enable-static',
    '--disable-shared',
    *cflags_B(c_extra = c_extra),
    # To determine build system compiler, the configure script will firstly try host
    # compiler (i.e. *-w64-mingw32-gcc) and check whether the output is executable
    # (and fallback to cc otherwise). However, in WSL or Linux with Wine configured,
    # the check passes and thus *-w64-mingw32-gcc is detected as build system compiler.
    # Here we force the build system compiler to be gcc.
    'CC_FOR_BUILD=gcc',
  ])
  make_default('gmp', build_dir, config.jobs)
  make_destdir_install('gmp', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

def _mpfr(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mpfr / 'build-AAB'
  ensure(build_dir)
  configure('mpfr', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_B(),
  ])
  make_default('mpfr', build_dir, config.jobs)
  make_destdir_install('mpfr', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

  fix_libtool_absolute_reference(paths.x_prefix / 'x86_64-w64-mingw32' / 'lib' / 'libmpfr.la')

def _mpc(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mpc / 'build-AAB'
  ensure(build_dir)
  configure('mpc', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_B(),
  ])
  make_default('mpc', build_dir, config.jobs)
  make_destdir_install('mpc', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

  fix_libtool_absolute_reference(paths.x_prefix / 'x86_64-w64-mingw32' / 'lib' / 'libmpc.la')

def _iconv(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.iconv)
  v_gcc = Version(ver.gcc)
  build_dir = paths.iconv / 'build-AAB'
  ensure(build_dir)

  triplet_args = ['--host=x86_64-w64-mingw32']
  c_extra = []

  # libiconv 1.14 does not recognize 'x86_64-alpine-linux-musl'
  if v >= Version('1.15'):
    triplet_args.append(f'--build={config.build}')

  # GCC 15 defaults to C23
  if v_gcc.major >= 15 and v < Version('1.18'):
    c_extra.append('-std=gnu11')

  configure('iconv', build_dir, [
    '--prefix=',
    *triplet_args,
    '--disable-nls',
    '--enable-static',
    '--disable-shared',
    *cflags_B(c_extra = c_extra),
  ])
  make_default('iconv', build_dir, config.jobs)
  make_destdir_install('iconv', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

def _gettext(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.gettext / 'gettext-runtime' / 'build-AAB'
  ensure(build_dir)
  configure('gettext', build_dir, [
    '--prefix=',
    '--host=x86_64-w64-mingw32',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_B(),
  ])
  make_default('gettext', build_dir, config.jobs)
  make_destdir_install('gettext', build_dir, paths.x_prefix / 'x86_64-w64-mingw32')

  fix_libtool_absolute_reference(paths.x_prefix / 'x86_64-w64-mingw32' / 'lib' / 'libintl.la')

def _python(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  res = subprocess.run([
    'xmake', 'config', '--root',
    '-p', 'mingw',
    '-a', 'x86_64',
    f'--mingw={paths.x_prefix}',
    f'--cross=x86_64-w64-mingw32-',
  ], cwd = paths.python)
  if res.returncode != 0:
    raise Exception('xmake config failed')
  res = subprocess.run([
    'xmake', 'build', '--root',
    '-j', str(config.jobs),
  ], cwd = paths.python)
  if res.returncode != 0:
    raise Exception('xmake build failed')
  res = subprocess.run([
    'xmake', 'install', '--root',
    '-o', paths.x_prefix / 'x86_64-w64-mingw32',
  ], cwd = paths.python)
  if res.returncode != 0:
    raise Exception('xmake install failed')

def _python_packages(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  x_prefix_mingw = paths.x_prefix / 'x86_64-w64-mingw32'
  python_lib = x_prefix_mingw / 'Lib'
  python_lib_zip = x_prefix_mingw / 'lib' / 'python.zip'
  shutil.copytree(paths.x_prefix / 'share' / f'gcc-{config.branch}' / 'python', python_lib, dirs_exist_ok = True)
  subprocess.run([
    'python3', '-m', 'compileall',
    '-b',
    '-o', '2',
    '.',
  ], check = True, cwd = python_lib)
  if python_lib_zip.exists():
    python_lib_zip.unlink()
  subprocess.run([
    '7z', 'a', '-tzip',
    '-mx0',  # no compression, reduce final size
    python_lib_zip,
    '*', '-xr!__pycache__', '-xr!*.py',
  ], check = True, cwd = python_lib)

def build_AAB_library(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _gmp(ver, paths, config)

  _mpfr(ver, paths, config)

  _mpc(ver, paths, config)

  _iconv(ver, paths, config)

  if ver.gettext:
    _gettext(ver, paths, config)

  if ver.python:
    _python(ver, paths, config)
    _python_packages(ver, paths, config)
