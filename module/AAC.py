import argparse
import glob
import os
import shutil
from packaging.version import Version

from module.debug import shell_here
from module.path import ProjectPaths
from module.profile import BranchProfile
from module.util import cflags_A, cflags_C, configure, ensure, fix_limits_h, make_custom, make_default, make_destdir_install, make_install

def _binutils(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.binutils / f'build-AAC-{arch}'
  ensure(build_dir)
  configure('binutils', build_dir, [
    f'--prefix=',
    f'--target={arch}-linux-gnu',
    f'--build={config.build}',
    # static build
    '--disable-plugins',
    '--disable-shared',
    '--enable-static',
    '--disable-werror',
    # features
    '--disable-gprofng',
    '--disable-install-libbfd',
    '--disable-multilib',
    '--disable-nls',
    # libtool eats `-static`
    *cflags_A(ld_extra = ['--static']),
  ])
  make_default('binutils', build_dir, config.jobs)
  make_destdir_install('binutils', build_dir, paths.x_prefix)

def _kernel_headers(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  KARCH_MAP = {
    'aarch64': 'arm64',
    'x86_64': 'x86',
  }
  make_custom('kernel headers', paths.kernel, [
    'headers_install',
    f'ARCH={KARCH_MAP[arch]}',
    f'INSTALL_HDR_PATH={paths.x_prefix}/{arch}-linux-gnu',
  ], config.jobs)

def _gcc(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gcc)
  build_dir = paths.gcc / f'build-AAC-{arch}'
  ensure(build_dir)

  libexec_target = paths.x_prefix / 'lib' / 'gcc' / f'{arch}-linux-gnu'

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
    f'--prefix={paths.x_prefix}',
    f'--libexecdir={paths.x_prefix}/lib',
    f'--target={arch}-linux-gnu',
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
    '--disable-libsanitizer',
    '--disable-lto',
    '--disable-multilib',
    '--disable-nls',
    # packages
    f'--with-glibc-version={ver.glibc}',
    f'--with-gmp={paths.x_dep}',
    '--without-libcc1',
    f'--with-mpc={paths.x_dep}'
    f'--with-mpfr={paths.x_dep}',
    *config_flags,
    # libtool eats `-static`
    *cflags_A(ld_extra = ['--static']),
    *cflags_C('_FOR_TARGET', ld_extra = ['--static']),
  ])

  make_custom('gcc (all-gcc)', build_dir, ['all-gcc'], config.jobs)
  make_custom('gcc (install-gcc)', build_dir, ['install-gcc'], jobs = 1)
  yield

  make_custom('gcc (all-target-libgcc)', build_dir, ['all-target-libgcc'], config.jobs)
  make_custom('gcc (install-target-libgcc)', build_dir, ['install-target-libgcc'], jobs = 1)
  yield

  make_default('gcc', build_dir, config.jobs)
  make_install('gcc', build_dir)
  fix_limits_h(limits_h, paths.gcc)
  yield

def _glibc(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.glibc)
  build_dir = paths.glibc / f'build-AAC-{arch}'
  ensure(build_dir)

  prefix = paths.x_prefix / f'{arch}-linux-gnu'
  destdir = paths.glibc / f'pkg-AAC-{arch}'

  config_flags = []

  # workaround libunwind detection
  # not sure fixed in 2.25 or 2.26
  if v < Version('2.26'):
    config_flags.append('libc_cv_forced_unwind=yes')

  configure('glibc', build_dir, [
    '--prefix=',
    f'--host={arch}-linux-gnu',
    f'--build={config.build}',
    # static-only is not supported
    # here we build with dynamic library enabled ...
    '--enable-shared',
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
    *config_flags,
    *cflags_C(ld_extra = ['-static']),
    # disable C++ to avoid -lgcc_s in test links-dso-program
    # which is not supported by static compiler
    'CXX=false',
  ])

  make_custom('glibc (install-headers)', build_dir, [f'DESTDIR={prefix}', 'install-headers'], jobs = 1)
  with open(prefix / 'include' / 'gnu' / 'stubs.h', 'w'):
    pass
  yield

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
  yield

def build_AAC_compiler(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _binutils(arch, ver, paths, config)

  _kernel_headers(arch, ver, paths, config)

  gcc = _gcc(arch, ver, paths, config)
  gcc.__next__()

  glibc = _glibc(arch, ver, paths, config)
  glibc.__next__()

  gcc.__next__()

  glibc.__next__()

  gcc.__next__()

def _gmp(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gmp)
  v_gcc = Version(ver.gcc)
  build_dir = paths.gmp / f'build-AAC-{arch}'
  ensure(build_dir)

  c_extra = []

  # GCC 15 defaults to C23, in which `foo()` means `foo(void)` instead of `foo(...)`.
  if v_gcc.major >= 15 and v < Version('6.4.0'):
    c_extra.append('-std=gnu11')

  configure('gmp', build_dir, [
    '--prefix=',
    f'--host={arch}-linux-gnu',
    f'--build={config.build}',
    '--disable-assembly',
    '--enable-static',
    '--disable-shared',
    *cflags_C(c_extra = c_extra),
  ])
  make_default('gmp', build_dir, config.jobs)
  make_destdir_install('gmp', build_dir, paths.x_prefix / f'{arch}-linux-gnu')

def _mpfr(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mpfr / f'build-AAC-{arch}'
  ensure(build_dir)
  configure('mpfr', build_dir, [
    '--prefix=',
    f'--host={arch}-linux-gnu',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_C(),
  ])
  make_default('mpfr', build_dir, config.jobs)
  make_destdir_install('mpfr', build_dir, paths.x_prefix / f'{arch}-linux-gnu')

  # remove absolute reference from libtool
  la_path = paths.x_prefix / f'{arch}-linux-gnu' / 'lib' / 'libmpfr.la'
  la_content = open(la_path, 'r').readlines()
  with open(la_path, 'w') as f:
    for line in la_content:
      if line.startswith('dependency_libs='):
        f.write("dependency_libs='-lgmp'\n")
      else:
        f.write(line)

def _mpc(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  build_dir = paths.mpc / f'build-AAC-{arch}'
  ensure(build_dir)
  configure('mpc', build_dir, [
    '--prefix=',
    f'--host={arch}-linux-gnu',
    f'--build={config.build}',
    '--enable-static',
    '--disable-shared',
    *cflags_C(),
  ])
  make_default('mpc', build_dir, config.jobs)
  make_destdir_install('mpc', build_dir, paths.x_prefix / f'{arch}-linux-gnu')

  # remove absolute reference from libtool
  la_path = paths.x_prefix / f'{arch}-linux-gnu' / 'lib' / 'libmpfr.la'
  la_content = open(la_path, 'r').readlines()
  with open(la_path, 'w') as f:
    for line in la_content:
      if line.startswith('dependency_libs='):
        f.write("dependency_libs='-lmpfr -lgmp -lm'\n")
      else:
        f.write(line)

def build_AAC_library(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _gmp(arch, ver, paths, config)

  _mpfr(arch, ver, paths, config)

  _mpc(arch, ver, paths, config)
