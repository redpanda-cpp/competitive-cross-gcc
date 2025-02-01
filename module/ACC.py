import argparse
import os
import shutil
from packaging.version import Version

from module.debug import shell_here
from module.path import ProjectPaths
from module.profile import BranchProfile
from module.util import cflags_A, cflags_C, configure, ensure, make_custom, make_default, make_install

def _gdbserver(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  v = Version(ver.gdb)
  build_dir = paths.gdb / f'build-ACC-{arch}'
  ensure(build_dir)

  configure('gdbserver', build_dir, [
    '--prefix=',
    f'--target={arch}-linux-gnu',
    f'--host={arch}-linux-gnu',
    f'--build={config.build}',
    # static build
    '--disable-inprocess-agent',
    '--disable-shared',
    '--enable-static',
    # features
    '--disable-sim',
    '--disable-tui',
    '--disable-werror',
    # packages
    '--with-gdbserver',
    # libtool eats `-static`
    *cflags_C(ld_extra = ['--static']),
  ])

  if v.major >= 10:
    make_custom('gdbserver', build_dir, ['all-gdbserver'], config.jobs)
    make_custom('gdbserver (install)', build_dir, [f'DESTDIR={paths.linux_prefix(arch)}', 'install-gdbserver'], jobs = 1)
  else:
    make_custom('gdbserver', build_dir, ['all-gdb'], config.jobs)
    make_custom('gdbserver (install)', build_dir / 'gdb' / 'gdbserver', [f'DESTDIR={paths.linux_prefix(arch)}', 'install-only'], jobs = 1)

def build_ACC_gdbserver(arch: str, ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _gdbserver(arch, ver, paths, config)
