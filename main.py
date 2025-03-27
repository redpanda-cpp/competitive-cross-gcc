#!/usr/bin/python3

import argparse
import logging
import os
from packaging.version import Version
from pathlib import Path
import shutil
import subprocess
from subprocess import PIPE, Popen

from module.args import parse_args
from module.path import ProjectPaths
from module.prepare_source import prepare_source
from module.profile import BRANCHES

# A = x86_64-linux-musl
# B = x86_64-w64-mingw32
# C = {aarch64,x86_64}-linux-gnu
# XYZ: build = X, host = Y, target = Z
from module.AAA import build_AAA_make, build_AAA_library, build_AAA_python
from module.AAB import build_AAB_compiler, build_AAB_library
from module.AAC import build_AAC_compiler, build_AAC_library
from module.ABB import build_ABB_toolchain
from module.ABC import build_ABC_toolchain, create_ABC_alias
from module.ACC import build_ACC_gdbserver

def clean(config: argparse.Namespace, paths: ProjectPaths):
  if paths.build.exists():
    shutil.rmtree(paths.build)
  if not config.no_cross and paths.x_prefix.exists():
    shutil.rmtree(paths.x_prefix)
  if paths.linux_prefix('x86_64').exists():
    shutil.rmtree(paths.linux_prefix('x86_64'))
  if paths.linux_prefix('aarch64').exists():
    shutil.rmtree(paths.linux_prefix('aarch64'))
  if not config.no_mingw and paths.mingw_prefix.exists():
    shutil.rmtree(paths.mingw_prefix)

def prepare_dirs(paths: ProjectPaths):
  paths.assets.mkdir(parents = True, exist_ok = True)
  paths.build.mkdir(parents = True, exist_ok = True)
  paths.dist.mkdir(parents = True, exist_ok = True)

def _package(root: Path | str, src: Path | str, dst: Path):
  tar = Popen(['bsdtar', '-C', root, '-c', src], stdout = PIPE)
  zstd = Popen([
    'zstd', '-f',
    '--zstd=strat=5,wlog=27,hlog=25,slog=6',
    '-o', dst,
  ], stdin = tar.stdout)
  tar.stdout.close()
  zstd.communicate()
  tar.wait()
  if tar.returncode != 0 or zstd.returncode != 0:
    raise Exception('bsdtar | zstd failed')

def package_cross(paths: ProjectPaths):
  _package(paths.x_prefix.parent, paths.x_prefix.name, paths.x_pkg)

def package_linux(paths: ProjectPaths):
  _package(paths.linux_prefix('x86_64').parent, paths.linux_prefix('x86_64').name, paths.linux_pkg('x86_64'))
  _package(paths.linux_prefix('aarch64').parent, paths.linux_prefix('aarch64').name, paths.linux_pkg('aarch64'))

def package_mingw(paths: ProjectPaths):
  _package(paths.mingw_prefix.parent, paths.mingw_prefix.name, paths.mingw_pkg)

def main():
  config = parse_args()

  if config.verbose >= 2:
    logging.basicConfig(level = logging.DEBUG)
  elif config.verbose >= 1:
    logging.basicConfig(level = logging.INFO)
  else:
    logging.basicConfig(level = logging.ERROR)

  logging.info("building GCC %s", config.branch)

  ver = BRANCHES[config.branch]
  paths = ProjectPaths(config, ver)

  if config.clean:
    clean(config, paths)

  prepare_dirs(paths)

  prepare_source(ver, paths)

  # glibc prior to 2.31 can not be built with make 4.4 (infinite recursion)
  # upstream accidentally fixed it, cherry-pick seems very hard
  # the workaround is to build everything with make at that time
  # ref. https://github.com/crosstool-ng/crosstool-ng/issues/1932#issuecomment-1528139734
  if not config.no_cross:
    build_AAA_make(ver, paths, config)

  os.environ['PATH'] = f'{paths.x_prefix}/bin:{os.environ["PATH"]}'
  if not config.no_cross:
    build_AAA_library(ver, paths, config)
    build_AAA_python(ver, paths, config)
    build_AAC_compiler('x86_64', ver, paths, config)
    build_AAC_library('x86_64', ver, paths, config)
    build_AAC_compiler('aarch64', ver, paths, config)
    build_AAC_library('aarch64', ver, paths, config)
    build_AAB_compiler(ver, paths, config)
    build_AAB_library(ver, paths, config)
    package_cross(paths)

  build_ABC_toolchain('x86_64', ver, paths, config)
  create_ABC_alias('x86_64', ver, paths, config)
  build_ACC_gdbserver('x86_64', ver, paths, config)
  build_ABC_toolchain('aarch64', ver, paths, config)
  create_ABC_alias('aarch64', ver, paths, config)
  build_ACC_gdbserver('aarch64', ver, paths, config)
  package_linux(paths)

  if not config.no_mingw:
    build_ABB_toolchain(ver, paths, config)
    package_mingw(paths)

if __name__ == '__main__':
  main()
