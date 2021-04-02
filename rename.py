#!/usr/bin/env python3

import pathlib
import subprocess
import sys


def print_message(message):
    print(message + '\n' + '-' * len(message))


if __name__ == '__main__':
    try:
        subprocess.run(['exiftool'], capture_output=True)
    except FileNotFoundError as error:
        message = 'Make sure you have Exiftool installed'
        print_message(message)
        raise error

    try:
        path = pathlib.Path(sys.argv[1])
    except IndexError as error:
        message = 'Usage: rename.py <path>'
        print_message(message)
        raise error

    if not path.exists():
        print_message('Make sure <path> is correct')
        raise FileNotFoundError(f'{path} does not exists')

    repository = pathlib.Path(__file__).parent.absolute()
    rename = repository / 'rename' / 'rename.py'
    python = repository / '.venv' / 'bin' / 'python'

    try:
        subprocess.run([python, rename, path], capture_output=True)
    except FileNotFoundError as error:
        message = ('Make sure you created the virtual environment in the '
                   'project folder')
        print_message(message)
        raise error
