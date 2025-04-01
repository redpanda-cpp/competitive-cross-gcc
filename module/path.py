import argparse
from packaging.version import Version
from pathlib import Path
from typing import Callable

from module.profile import BranchProfile

class ProjectPaths:
  root: Path

  assets: Path
  dist: Path
  patch: Path

  linux_prefix: Callable[[str], Path]
  mingw_prefix: Path
  x_prefix: Path

  linux_pkg: Callable[[str], Path]
  mingw_pkg: Path
  x_pkg: Path

  # build phase

  build: Path
  x_dep: Path

  binutils: Path
  gcc: Path
  gdb: Path
  gettext: Path
  glibc: Path
  gmp: Path
  iconv: Path
  kernel: Path
  make: Path
  mingw: Path
  mpc: Path
  mpfr: Path
  python: Path
  python_z: Path

  binutils_arx: Path
  gcc_arx: Path
  gdb_arx: Path
  gettext_arx: Path
  glibc_arx: Path
  gmp_arx: Path
  iconv_arx: Path
  kernel_arx: Path
  make_arx: Path
  mingw_arx: Path
  mpc_arx: Path
  mpfr_arx: Path
  python_arx: Path
  python_z_arx: Path

  # test phase

  test: Path
  test_src: Path
  chimaera_src: Path
  chimaera_exe: Path

  test_linux: Callable[[str], Path]
  test_mingw: Path

  xmake: Path
  xmake_arx: Path
  xmake_exe: Path

  def __init__(
    self,
    config: argparse.Namespace,
    ver: BranchProfile,
  ):
    self.root = Path.cwd()

    self.assets = self.root / 'assets'
    self.dist = self.root / 'dist'
    self.patch = self.root / 'patch'

    GLIBC_LD_NAME_MAP = {
      'aarch64': 'linux-aarch64',
      'x86_64': 'linux-x86-64',
    }

    self.linux_prefix = lambda arch: Path(f'/opt/gcc-{GLIBC_LD_NAME_MAP[arch]}-{config.branch}')
    self.mingw_prefix = Path(f'/opt/gcc-mingw64-{config.branch}')
    self.x_prefix = Path(f'/opt/gcc-x-{config.branch}')

    self.linux_pkg = lambda arch: self.dist / f'gcc-{GLIBC_LD_NAME_MAP[arch]}-{ver.gcc}-r{ver.rev}.tar.zst'
    self.mingw_pkg = self.dist / f'gcc-mingw64-{ver.gcc}-r{ver.rev}.tar.zst'
    self.x_pkg = self.dist / f'gcc-x-{ver.gcc}-r{ver.rev}.tar.zst'

    # build phase

    self.build = Path(f'/tmp/build/gcc-{config.branch}')
    self.x_dep = self.build / 'dep'

    binutils = f'binutils-{ver.binutils}'
    self.binutils = self.build / binutils
    if Version(ver.binutils) >= Version('2.43'):
      self.binutils_arx = self.assets / f'{binutils}.tar.zst'
    elif Version(ver.binutils) >= Version('2.28.1'):
      self.binutils_arx = self.assets / f'{binutils}.tar.xz'
    else:
      self.binutils_arx = self.assets / f'{binutils}.tar.bz2'

    gcc = f'gcc-{ver.gcc}'
    self.gcc = self.build / gcc
    if Version(ver.gcc).major >= 5:
      self.gcc_arx = self.assets / f'{gcc}.tar.xz'
    else:
      self.gcc_arx = self.assets / f'{gcc}.tar.bz2'

    gdb = f'gdb-{ver.gdb}'
    self.gdb = self.build / gdb
    if Version(ver.gdb) >= Version('7.8'):
      self.gdb_arx = self.assets / f'{gdb}.tar.xz'
    else:
      self.gdb_arx = self.assets / f'{gdb}.tar.bz2'

    if ver.gettext:
      gettext = f'gettext-{ver.gettext}'
      self.gettext = self.build / gettext
      self.gettext_arx = self.assets / f'{gettext}.tar.xz'
    else:
      self.gettext = None
      self.gettext_arx = None

    glibc = f'glibc-{ver.glibc}'
    self.glibc = self.build / glibc
    self.glibc_arx = self.assets / f'{glibc}.tar.xz'

    gmp = f'gmp-{ver.gmp}'
    self.gmp = self.build / gmp
    if Version(ver.gmp) >= Version('6.2.0'):
      self.gmp_arx = self.assets / f'{gmp}.tar.zst'
    else:
      self.gmp_arx = self.assets / f'{gmp}.tar.xz'

    iconv = f'libiconv-{ver.iconv}'
    self.iconv = self.build / iconv
    self.iconv_arx = self.assets / f'{iconv}.tar.gz'

    kernel = f'linux-{ver.kernel}'
    self.kernel = self.build / kernel
    self.kernel_arx = self.assets / f'{kernel}.tar.xz'

    make = f'make-{ver.make}'
    self.make = self.build / make
    if Version(ver.make) >= Version('4.3'):
      self.make_arx = self.assets / f'{make}.tar.lz'
    else:
      self.make_arx = self.assets / f'{make}.tar.bz2'

    mingw = f'mingw-w64-v{ver.mingw}'
    self.mingw = self.build / mingw
    if Version(ver.mingw).major >= 3:
      self.mingw_arx = self.assets / f'{mingw}.tar.bz2'
    else:
      self.mingw_arx = self.assets / f'{mingw}.tar.gz'

    mpc = f'mpc-{ver.mpc}'
    self.mpc = self.build / mpc
    self.mpc_arx = self.assets / f'{mpc}.tar.gz'

    mpfr = f'mpfr-{ver.mpfr}'
    self.mpfr = self.build / mpfr
    self.mpfr_arx = self.assets / f'{mpfr}.tar.xz'

    if ver.python:
      python = f'Python-{ver.python}'
      python_z = f'zlib-{ver.python_z}'
      self.python = self.build / python
      self.python_arx = self.assets / f'{python}.tar.xz'
      self.python_z = self.build / python / python_z
      self.python_z_arx = self.assets / f'{python_z}.tar.gz'
    else:
      self.python = None
      self.python_arx = None
      self.python_z = None
      self.python_z_arx = None

    # test phase

    self.test = Path(f'/tmp/test/gcc-{config.branch}')
    self.test_src = self.root / 'support' / 'test'
    self.chimaera_src = self.root / 'support' / 'chimaera' / 'main.cc'
    self.chimaera_exe = self.test / 'chimaera.exe.so'

    self.test_linux = lambda arch: self.test / f'gcc-{GLIBC_LD_NAME_MAP[arch]}-{config.branch}'
    self.test_mingw = self.test / f'gcc-mingw64-{config.branch}'

    self.xmake = self.test / 'xmake'
    self.xmake_arx = self.assets / f'xmake-v{ver.xmake}.win64.zip'
    self.xmake_exe = self.xmake / 'xmake.exe'
