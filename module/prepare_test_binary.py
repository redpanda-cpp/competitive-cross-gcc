import argparse
import logging
import os
from packaging.version import Version
from pathlib import Path
from shutil import copyfile
import subprocess

from module.fetch import validate_and_download, check_and_extract
from module.path import ProjectPaths
from module.profile import BranchProfile

def _chimeara(ver: BranchProfile, paths: ProjectPaths):
  subprocess.check_call([
    'wineg++',
    '-std=c++17', '-O2', '-municode',
    paths.chimaera_src,
    '-o', paths.chimaera_exe,
  ])

def _gcc_linux(arch: str, ver: BranchProfile, paths: ProjectPaths):
  check_and_extract(paths.test_linux(arch), paths.linux_pkg(arch))
  (paths.test_linux(arch) / '.patched').touch()

def _gcc_mingw(ver: BranchProfile, paths: ProjectPaths):
  check_and_extract(paths.test_mingw, paths.mingw_pkg)
  (paths.test_mingw / '.patched').touch()

def _xmake(ver: BranchProfile, paths: ProjectPaths):
  url = f'https://github.com/xmake-io/xmake/releases/download/v{ver.xmake}/{paths.xmake_arx.name}'
  validate_and_download(paths.xmake_arx, url)
  check_and_extract(paths.xmake, paths.xmake_arx)
  paths.xmake_exe.chmod(0o755)
  (paths.xmake / '.patched').touch()

def prepare_test_binary(ver: BranchProfile, paths: ProjectPaths, config: argparse.Namespace):
  _chimeara(ver, paths)

  _gcc_linux('x86_64', ver, paths)

  _gcc_linux('aarch64', ver, paths)

  if not config.no_mingw:
    _gcc_mingw(ver, paths)

  _xmake(ver, paths)
