import dataclasses
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


@dataclasses.dataclass
class File:
    """Keeps track of the path, hash and date of creation of a file."""

    path: pathlib.Path
    hash_: int = dataclasses.field(init=False)
    date: datetime.datetime = dataclasses.field(init=False)

    def __post_init__(self):
        self.hash_ = File.get_hash(self.path)
        self.date = File.get_date(self.path)

    @staticmethod
    def get_hash(path):
        """Hashes the file using the built-in hash function."""

        with path.open(mode='rb') as file_:
            bytes_ = file_.read()

        return hash(bytes_)

    @staticmethod
    def get_date(path):
        """Uses Exiftool to extract the file's create date or, if the file does
        not have exif info, gets the last time its metadata was modified."""

        # TODO: check if the user has exiftool installed before starting to do
        # all the work. Delete this comment after implementing the checking
        # function
        args = ['exiftool', path, '-CreateDate', '-s', '-s', '-s']
        process = subprocess.run(args, capture_output=True)
        date_str = process.stdout.decode('utf-8')

        stamp = path.stat().st_ctime

        try:
            date = datetime.datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S\n')
        except ValueError:
            date = datetime.datetime.fromtimestamp(stamp)

        date = LOCAL_TZ.localize(date)

        return date.strftime('%Y%m%d %H%M%S %z')


@dataclasses.dataclass
class FileManager:
    """Manages File instances."""

    path: pathlib.Path
    files: list = dataclasses.field(init=False)

    def __post_init__(self):
        self.files = FileManager.list_files(self.path)

    @staticmethod
    def list_files(path):
        """Lists all files in the given directory as File instances."""

        return [File(file_) for file_ in path.iterdir() if file_.is_file()]

    def find_duplicates(self):
        """Compares the hash of File instances to find identical copies."""

        hashes = []
        duplicates = []

        for file_ in self.files:
            if file_.hash_ in hashes:
                duplicates.append(file_)
            else:
                hashes.append(file_.hash_)

        return duplicates

    def remove_duplicates(self, duplicates):
        """Removes duplicate files from FileManager.files member, preventing
        them to be renamed in the future."""

        for duplicate in duplicates:
            self.files.remove(duplicate)


if __name__ == '__main__':
    # TODO: Test if the path exists before instanciate FileManager
    file_manager = FileManager(sys.argv[1])
    duplicates = file_manager.find_duplicates()
    # TODO: Prompt the user to delete the duplicates found
    file_manager.remove_duplicates(duplicates)
