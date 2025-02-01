from contextlib import contextmanager
import logging
import os
from pathlib import Path
import subprocess
from typing import List

def cflags_A(
  suffix: str = '',
  common_extra: List[str] = [],
  ld_extra: List[str] = [],
  c_extra: List[str] = [],
  cxx_extra: List[str] = [],
) -> List[str]:
  common = ['-Os']
  ld = ['-s']
  return [
    f'CFLAGS{suffix}=' + ' '.join(common + common_extra + c_extra),
    f'CXXFLAGS{suffix}=' + ' '.join(common + common_extra + cxx_extra),
    f'LDFLAGS{suffix}=' + ' '.join(ld + ld_extra),
  ]

def cflags_B(
  suffix: str = '',
  common_extra: List[str] = [],
  ld_extra: List[str] = [],
  c_extra: List[str] = [],
  cxx_extra: List[str] = [],
) -> List[str]:
  common = ['-Os']
  ld = ['-s']
  return [
    f'CFLAGS{suffix}=' + ' '.join(common + common_extra + c_extra),
    f'CXXFLAGS{suffix}=' + ' '.join(common + common_extra + cxx_extra),
    f'LDFLAGS{suffix}=' + ' '.join(ld + ld_extra),
  ]

def cflags_C(
  suffix: str = '',
  common_extra: List[str] = [],
  ld_extra: List[str] = [],
  c_extra: List[str] = [],
  cxx_extra: List[str] = [],
) -> List[str]:
  common = ['-Os']
  ld = ['-s']
  return [
    f'CFLAGS{suffix}=' + ' '.join(common + common_extra + c_extra),
    f'CXXFLAGS{suffix}=' + ' '.join(common + common_extra + cxx_extra),
    f'LDFLAGS{suffix}=' + ' '.join(ld + ld_extra),
  ]

def configure(component: str, cwd: Path, args: List[str]):
  res = subprocess.run(
    ['../configure', *args],
    cwd = cwd,
  )
  if res.returncode != 0:
    message = f'Build fail: {component} configure returned {res.returncode}'
    logging.critical(message)
    raise Exception(message)

def ensure(path: Path):
  path.mkdir(parents = True, exist_ok = True)

def fix_limits_h(limits_h: Path, gcc_src: Path):
  with open(limits_h, 'w') as f:
    f.writelines(open(gcc_src / 'gcc' / 'limitx.h', 'r').read())
    f.writelines(open(gcc_src / 'gcc' / 'glimits.h', 'r').read())
    f.writelines(open(gcc_src / 'gcc' / 'limity.h', 'r').read())

def make_custom(component: str, cwd: Path, extra_args: List[str], jobs: int):
  res = subprocess.run(
    ['make', *extra_args, f'-j{jobs}'],
    cwd = cwd,
  )
  if res.returncode != 0:
    message = f'Build fail: {component} make returned {res.returncode}'
    logging.critical(message)
    raise Exception(message)

def make_default(component: str, cwd: Path, jobs: int):
  make_custom(component + ' (default)', cwd, [], jobs)

def make_destdir_install(component: str, cwd: Path, destdir: Path):
  make_custom(component + ' (install)', cwd, [f'DESTDIR={destdir}', 'install'], jobs = 1)

def make_install(component: str, cwd: Path):
  make_custom(component + ' (install)', cwd, ['install'], jobs = 1)

@contextmanager
def temporary_symlink(target: Path | str, link_name: Path | str):
  os.symlink(target, link_name)
  try:
    yield
  finally:
    Path(link_name).unlink()
