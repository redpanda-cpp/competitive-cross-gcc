import argparse
import os
import shutil
from packaging.version import Version

from module.debug import shell_here
from module.path import ProjectPaths
from module.profile import BranchProfile
from module.util import cflags_A, cflags_C, configure, ensure, make_custom, make_default, make_destdir_install, make_install

def _gmake(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.make)
  v_gcc = Version(ver.gcc)
  build_dir = paths.make / 'build-AAA'
  ensure(build_dir)

  c_extra = []

  # GCC 15 defaults to C23, in which `foo()` means `foo(void)` instead of `foo(...)`.
  if v_gcc.major >= 15 and v < Version('4.5'):
    c_extra.append('-std=gnu11')

  configure('make', build_dir, [
    '--prefix=',
    f'--build={config.build}',
    '--disable-nls',
    *cflags_A(c_extra = c_extra, ld_extra = ['-static']),
  ])
  make_default('make', build_dir, config.jobs)
  make_destdir_install('make', build_dir, paths.x_prefix)

def build_AAA_make(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _gmake(ver, paths, config)

def _gmp(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.gmp / 'build-AAA'
  ensure(build_dir)
  configure('gmp', build_dir, [
    f'--prefix={paths.x_dep}',
    f'--host={config.build}',
    f'--build={config.build}',
    '--disable-assembly',
    '--enable-static',
    '--disable-shared',
    *cflags_A(),
  ])
  make_default('gmp', build_dir, config.jobs)
  make_install('gmp', build_dir)

def _mpfr(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mpfr / 'build-AAA'
  ensure(build_dir)
  configure('mpfr', build_dir, [
    f'--prefix={paths.x_dep}',
    f'--host={config.build}',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_A(
      common_extra = [f'-I{paths.x_dep}/include'],
      ld_extra = [f'-L{paths.x_dep}/lib'],
    ),
  ])
  make_default('mpfr', build_dir, config.jobs)
  make_install('mpfr', build_dir)

def _mpc(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mpc / 'build-AAA'
  ensure(build_dir)
  configure('mpc', build_dir, [
    f'--prefix={paths.x_dep}',
    f'--host={config.build}',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_A(
      common_extra = [f'-I{paths.x_dep}/include'],
      ld_extra = [f'-L{paths.x_dep}/lib'],
    ),
  ])
  make_default('mpc', build_dir, config.jobs)
  make_install('mpc', build_dir)

def _python_z(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.python_z / 'build-AAA'
  ensure(build_dir)
  configure('zlib for python', build_dir, [
    '--prefix=',
    '--static',
  ])
  make_default('zlib for python', build_dir, config.jobs)
  make_destdir_install('zlib for python', build_dir, paths.x_dep)

def build_AAA_library(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _gmp(ver.gmp, paths, config)

  _mpfr(ver.mpfr, paths, config)

  _mpc(ver.mpc, paths, config)

  if ver.python:
    _python_z(ver, paths, config)

def _python(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.python / 'build-AAA'
  ensure(build_dir)
  configure('python', build_dir, [
    f'--prefix={paths.x_prefix}',
    # static
    '--disable-shared',
    'MODULE_BUILDTYPE=static',
    # features
    '--disable-test-modules',
    # packages
    '--without-static-libpython',
    f'ZLIB_CFLAGS=-I{paths.x_dep}/include',
    f'ZLIB_LIBS=-L{paths.x_dep}/lib -lz',
    *cflags_A(ld_extra = ['-static']),
  ])
  make_custom('python', build_dir, ['LDFLAGS=-static', 'LINKFORSHARED= '], config.jobs)
  make_install('python', build_dir)

def build_AAA_python(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  if ver.python:
    _python(ver, paths, config)
