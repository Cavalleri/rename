import datetime
import hashlib
import os
import pathlib
import subprocess
import sys
import tzlocal


LOCAL_TZ = tzlocal.get_localzone()


def digest(food):
    """Produces a SHA1 string for the given bytes."""

    sha1 = hashlib.sha1()
    sha1.update(food)
    return sha1.hexdigest()


def search_duplicates(path):
    """Compares SHA 1 hashes to find identical files. Returns a list of the
    original and duplicate files paths."""

    duplicates = []
    hashes = {}

    for file_ in path.iterdir():
        if file_.is_file():
            with file_.open(mode='rb') as food:
                hash_ = digest(food.read())

            if hash_ in hashes.keys():
                duplicates.append((file_, hashes[hash_]))
            else:
                hashes[hash_] = file_

    return duplicates


def delete_duplicates(duplicates):
    """Lists the duplicate files found and prompts the user to delete them. If
    the duplicate files are not deleted, they will be renamed."""

    if len(duplicates) == 0:
        print('No duplicates files were found')
    else:
        print('The following files are duplicated:')

        for duplicate in duplicates:
            print(*duplicate)

        if input('Delete duplicate files? (y/n) ') == 'y':
            for duplicate in duplicates:
                os.remove(duplicate[0])

            print(len(duplicates), 'duplicate files deleted')
        else:
            print('No duplicate file was deleted')


def get_create_date(file_):
    """Gets file create date if exif is present. If the file has no exif,
    datetime will raise ValueError. For this function to work the user must
    have exiftool installed, otherwise it will raise FileNotFoundError."""

    args = ['exiftool', file_, '-CreateDate', '-s', '-s', '-s']
    try:
        process = subprocess.run(args, capture_output=True)
    except FileNotFoundError as error:
        message = ('Could not run Exiftool. Make sure you have Exiftool '
                   'installed')
        print(message + '\n' + '-' * len(message))
        raise error

    create_date = process.stdout

    return datetime.datetime.strptime(create_date.decode('utf-8'),
                                      '%Y:%m:%d %H:%M:%S\n')


def get_modified_date(file_):
    """Gets the most recent metadata change on Unix or the time of creation
    on Windows."""

    modified_date = file_.stat().st_ctime
    return datetime.datetime.fromtimestamp(modified_date)


def get_name(file_):
    """Tries to get file's EXIF create date. If the file doesn't have EXIF,
    gets file's modified date. Returns the date and the local timezone offset
    as a string."""

    try:
        date = get_create_date(file_)
    except ValueError:
        date = get_modified_date(file_)

    date = LOCAL_TZ.localize(date)
    return date.strftime('%Y%m%d %H%M%S %z')


def get_target(file_, counter=None):
    """Builds the target path used to rename the file. Counter is a positive
    integer appended to the name when given."""

    name = get_name(file_)

    if counter is None:
        target = file_.parent / (name + file_.suffix)
    else:
        target = file_.parent / (name + f' {counter}' + file_.suffix)

    return target


def rename_file(file_):
    """Renames the file. If other file already has the same name, a positive
    integer will be appended to the end of the name."""

    counter = 1
    target = get_target(file_, counter)

    if target.stem == file_.stem:
        print("BUGUE BUGUE BUGUE BUGUE")

    while target.exists():
        counter += 1
        target = get_target(file_, counter)

    if counter == 1:
        target = get_target(file_)

        if target.exists():
            new_target = get_target(target, 1)
            # NOTE: The following is the buggy line. If the following renames
            # a file, the rename loop will fail to find the renamed file
            target.rename(new_target)
            target = get_target(file_, 2)

    file_.rename(target)


def main():
    try:
        path = pathlib.Path(sys.argv[1])
    except IndexError as error:
        message = 'Usage: rename.py <path>'
        print(message + '\n' + '-' * len(message))
        raise error

    duplicates = search_duplicates(path)
    delete_duplicates(duplicates)

    files = list(path.iterdir())
    for file_ in files:
        if file_.is_file():
            # BUG: When a file has the same name of another file, the other
            # will be renamed too, and, when the loop loops over the other, it
            # will no longer exists because it has been renamed.
            # Solution: remove renamed files from the files list. To acomplish
            # this, rename_files must return the other file renamed (I leaved a
            # note where the buggy code is) and them it must be removed from
            # the files list
            rename_file(file_)

    # NOTE: Instead of using the modified time, which will modify the file
    # metada, changing the modified time, try to inject the modified time as
    # EXIF created time, preventing future renames to push the name further
    # from the real create date
    print(len(files), 'files renamed.')


if __name__ == '__main__':
    pass
