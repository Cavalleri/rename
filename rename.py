#!/usr/bin/env python3

import pathlib
import subprocess
import sys


if __name__ == '__main__':
    try:
        path = sys.argv[1]
    except IndexError as error:
        message = 'Usage: rename.py <path>'
        print(message + '\n' + '-' * len(message))
        raise error

    repository = pathlib.Path(__file__).parent.absolute()
    rename = repository / 'rename' / 'rename.py'
    python = repository / '.venv' / 'bin' / 'python'

    subprocess.run([python, rename, path])
