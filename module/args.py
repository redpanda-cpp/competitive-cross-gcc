import argparse
import os
import subprocess
from subprocess import PIPE

def get_gcc_triplet():
  result = subprocess.run(['gcc', '-dumpmachine'], stdout = PIPE, stderr = PIPE)
  if result.returncode != 0:
    return None
  return result.stdout.decode('utf-8').strip()

def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-b', '--branch',
    type = str,
    choices = [
      # C++17 era
      '15', '14', '13', '12', '11',
      # C++14 era
      '10', '9', '8', '7', '6',
      # C++98 era
      '5', '4.9', '4.8',
    ],
    required = True,
    help = 'GCC branch to build',
  )

  gcc_triplet = get_gcc_triplet()
  parser.add_argument(
    '--build',
    type = str,
    default = gcc_triplet,
    required = not bool(gcc_triplet),
    help = 'Build system triplet',
  )

  parser.add_argument(
    '-c', '--clean',
    action = 'store_true',
    help = 'Clean build directories',
  )
  parser.add_argument(
    '-j', '--jobs',
    type = int,
    default = os.cpu_count(),
  )
  parser.add_argument(
    '-nx', '--no-cross',
    action = 'store_true',
    help = 'Do not build cross toolchain',
  )
  parser.add_argument(
    '-nm', '--no-mingw',
    action = 'store_true',
    help = 'Do not build mingw toolchain',
  )
  parser.add_argument(
    '-v', '--verbose',
    action = 'count',
    default = 0,
    help = 'Increase verbosity (up to 2)',
  )

  result = parser.parse_args()
  return result
