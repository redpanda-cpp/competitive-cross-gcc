#!/usr/bin/python3

import argparse
import logging
import os
from pathlib import Path
from pprint import pprint
import resource
import shutil
import socket
import subprocess
from subprocess import PIPE
import sys

from module.args import parse_args
from module.path import ProjectPaths
from module.prepare_test_binary import prepare_test_binary
from module.profile import BRANCHES
from module.util import ensure

def clean(config: argparse.Namespace, paths: ProjectPaths):
  if paths.test.exists():
    shutil.rmtree(paths.test)

def prepare_dirs(paths: ProjectPaths):
  shutil.copytree(paths.test_src, paths.test)

def winepath(path: Path):
  return subprocess.check_output(['winepath', '-w', path]).decode().strip()

def available_port():
  with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(('localhost', 0))
    return s.getsockname()[1]

def test_linux_compiler(arch: str, paths: ProjectPaths, verbose: list[str]):
  subprocess.check_call([
    paths.xmake_exe, 'f', *verbose,
    '-p', 'linux', '-a', arch,
    f'--sdk={winepath(paths.test_linux(arch))}',
  ], cwd = paths.test)
  subprocess.check_call([paths.xmake_exe, 'b', *verbose], cwd = paths.test)

  # make Linux binaries executable
  build_dir = paths.test / 'build' / 'linux' / arch
  for file in build_dir.glob('**/*'):
    if file.is_file():
      file.chmod(0o755)

  # set unlimited stack to disable wine-staging seccomp, which hooks syscalls from low address space, where statically linked binaries are loaded
  resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
  subprocess.check_call([paths.xmake_exe, 'test', *verbose], cwd = paths.test)
  resource.setrlimit(resource.RLIMIT_STACK, (8192 * 1024, resource.RLIM_INFINITY))

def test_linux_make_gdb(arch: str, paths: ProjectPaths):
  bin_dir = paths.test_linux(arch) / 'bin'
  make_exe = bin_dir / 'mingw32-make.exe'
  gdb_exe = bin_dir / 'gdb.exe'
  gdbserver_exe = bin_dir / 'gdbserver'

  build_dir = paths.test / 'build' / 'linux' / arch / 'debug'
  inferior = build_dir / 'breakpoint'
  in_gdb_inferior = winepath(inferior).replace('\\', '/')
  ensure(build_dir)

  # make
  os.environ['WINEPATH'] = winepath(bin_dir)
  subprocess.check_call([make_exe, f'DIR={build_dir}'], cwd = paths.test)
  inferior.chmod(0o755)
  del os.environ['WINEPATH']

  # gdb
  port = available_port()
  comm = f'localhost:{port}'

  gdb_command = (
    f'file {in_gdb_inferior}\n'  # old releases disconnect when retriving symbol from gdbserver
    f'target remote {comm}\n'
    'b 12\n'
    'c\n'
    'p fib[i]\n'  # i = 2, fib[i] = 1
    'c\n'
    'p fib[i]\n'  # i = 3, fib[i] = 2
    'c\n'
    'p fib[i]\n'  # i = 4, fib[i] = 3
    'c\n'
    'p fib[i]\n'  # i = 5, fib[i] = 5
    'c\n'
  ).encode()

  expected_output = [
    '$1 = 1',
    '$2 = 2',
    '$3 = 3',
    '$4 = 5',
  ]

  if arch == 'x86_64':
    gdbserver = subprocess.Popen([gdbserver_exe, '--once', comm, inferior], cwd = paths.test)
  else:
    # gdbserver not work under qemu user mode emulation
    # here we check whether gdbserver can be started
    subprocess.check_call([gdbserver_exe, '--version'], cwd = paths.test)
    # and use qemu as debug server
    gdbserver = subprocess.Popen([f'qemu-{arch}', '-g', str(port), inferior], cwd = paths.test)
  gdb = subprocess.Popen([gdb_exe], cwd = paths.test, stdin = PIPE, stdout = PIPE)
  gdb.stdin.write(gdb_command)
  gdb.stdin.close()
  gdb.wait(timeout = 10.0)
  if gdb.returncode != 0:
    raise Exception(f"gdb exited with code {gdb.returncode}")
  gdbserver.wait(timeout = 1.0)
  if gdbserver.returncode != 0:
    raise Exception(f"gdbserver exited with code {gdbserver.returncode}")

  gdb_output = gdb.stdout.read().decode()
  for line in expected_output:
    if line not in gdb_output:
      raise Exception(f"expected output line '{line}' not found in gdb output:\n{gdb_output}")

def test_mingw_compiler(paths: ProjectPaths, verbose: list[str]):
  subprocess.check_call([
    paths.xmake_exe, 'f', *verbose,
    '-p', 'mingw', '-a', 'x86_64',
    f'--mingw={winepath(paths.test_mingw)}',
  ], cwd = paths.test)
  subprocess.check_call([paths.xmake_exe, 'b', *verbose], cwd = paths.test)
  subprocess.check_call([paths.xmake_exe, 'test', *verbose], cwd = paths.test)

def test_mingw_make_gdb(paths: ProjectPaths):
  bin_dir = paths.test_mingw / 'bin'
  make_exe = bin_dir / 'mingw32-make.exe'
  gdb_exe = bin_dir / 'gdb.exe'
  gdbserver_exe = bin_dir / 'gdbserver.exe'

  build_dir = paths.test / 'build' / 'mingw' / 'x86_64' / 'debug'
  inferior = build_dir / 'breakpoint.exe'
  in_gdb_inferior = winepath(inferior).replace('\\', '/')
  ensure(build_dir)

  # make
  os.environ['WINEPATH'] = winepath(bin_dir)
  subprocess.check_call([make_exe, f'DIR={build_dir}', 'SUFFIX=.exe'], cwd = paths.test)
  del os.environ['WINEPATH']

  # gdb
  port = available_port()
  comm = f'localhost:{port}'

  gdb_command = (
    f'file {in_gdb_inferior}\n'  # old releases disconnect when retriving symbol from gdbserver
    f'target remote {comm}\n'
    'b 12\n'
    'c\n'
    'p fib[i]\n'  # i = 2, fib[i] = 1
    'c\n'
    'p fib[i]\n'  # i = 3, fib[i] = 2
    'c\n'
    'p fib[i]\n'  # i = 4, fib[i] = 3
    'c\n'
    'p fib[i]\n'  # i = 5, fib[i] = 5
    'c\n'
  ).encode()

  expected_output = [
    '$1 = 1',
    '$2 = 2',
    '$3 = 3',
    '$4 = 5',
  ]

  gdbserver = subprocess.Popen([gdbserver_exe, comm, winepath(inferior)], cwd = paths.test)
  gdb = subprocess.Popen([gdb_exe], cwd = paths.test, stdin = PIPE, stdout = PIPE)
  gdb.stdin.write(gdb_command)
  gdb.stdin.close()
  gdb.wait(timeout = 10.0)
  if gdb.returncode != 0:
    raise Exception(f"gdb exited with code {gdb.returncode}")
  gdbserver.wait(timeout = 1.0)
  if gdbserver.returncode != 0:
    raise Exception(f"gdbserver exited with code {gdbserver.returncode}")

  gdb_output = gdb.stdout.read().decode()
  for line in expected_output:
    if line not in gdb_output:
      raise Exception(f"expected output line '{line}' not found in gdb output:\n{gdb_output}")

def main():
  config = parse_args()

  if config.verbose >= 2:
    logging.basicConfig(level = logging.DEBUG)
    os.environ['WINEDEBUG'] = ''
    xmake_verbose = ['-vD']
  elif config.verbose >= 1:
    logging.basicConfig(level = logging.INFO)
    os.environ['WINEDEBUG'] = 'fixme-all'
    xmake_verbose = ['-v']
  else:
    logging.basicConfig(level = logging.ERROR)
    os.environ['WINEDEBUG'] = '-all'
    xmake_verbose = []

  logging.info("testing GCC %s", config.branch)

  ver = BRANCHES[config.branch]
  paths = ProjectPaths(config, ver)

  clean(config, paths)

  prepare_dirs(paths)

  prepare_test_binary(ver, paths, config)

  test_report = {
    'fail': False,
  }

  try:
    test_linux_compiler('x86_64', paths, xmake_verbose)
    test_report['linux-x86-64-compiler'] = "okay"
  except Exception as e:
    test_report['fail'] = True
    test_report['linux-x86-64-compiler'] = repr(e)
  try:
    test_linux_make_gdb('x86_64', paths)
    test_report['linux-x86-64-make-gdb'] = "okay"
  except Exception as e:
    test_report['fail'] = True
    test_report['linux-x86-64-make-gdb'] = repr(e)
  try:
    test_linux_compiler('aarch64', paths, xmake_verbose)
    test_report['linux-aarch64-compiler'] = "okay"
  except Exception as e:
    test_report['fail'] = True
    test_report['linux-aarch64-compiler'] = repr(e)
  try:
    test_linux_make_gdb('aarch64', paths)
    test_report['linux-aarch64-make-gdb'] = "okay"
  except Exception as e:
    test_report['fail'] = True
    test_report['linux-aarch64-make-gdb'] = repr(e)

  if not config.no_mingw:
    try:
      test_mingw_compiler(paths, xmake_verbose)
      test_report['mingw64-compiler'] = "okay"
    except Exception as e:
      test_report['fail'] = True
      test_report['mingw64-compiler'] = repr(e)
    try:
      test_mingw_make_gdb(paths)
      test_report['mingw64-make-gdb'] = "okay"
    except Exception as e:
      test_report['fail'] = True
      test_report['mingw64-make-gdb'] = repr(e)

  print("============================== TEST REPORT ==============================")
  pprint(test_report)

  if test_report['fail']:
    sys.exit(1)

if __name__ == '__main__':
  main()
