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
    """Keeps track of the path, hash, date of creation and name of a file."""

    path: pathlib.Path
    hash_: int = dataclasses.field(init=False)
    date: datetime.datetime = dataclasses.field(init=False)
    target: pathlib.Path = dataclasses.field(init=False)
    index: int = 1
    resolved: bool = dataclasses.field(default=False, init=False)

    def __post_init__(self):
        self.hash_ = File.get_hash(self.path)
        self.date = File.get_date(self.path)
        self.target = self.get_target()

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

        return date

    def get_target(self, unique=False):
        """Makes the target path used to rename the file later. If unique is
        True, File.index will not be appended to the path stem."""

        date = self.date.strftime('%Y%m%d %H%M%S %z')

        if unique:
            name = f'{date}{self.path.suffix}'
        else:
            name = f'{date} {self.index}{self.path.suffix}'

        return self.path.parent / name

    def increment_target(self):
        """Increments File.index and remakes File.target."""

        self.index += 1
        self.target = self.get_target()


class DuplicateNotRemovedError(Exception):
    """Exception raised when the user attempts to delete a duplicate that was
    not removed from FileManager.files."""
    pass


class TargetNotResolvedError(Exception):
    """Exception raised when the user attempts to rename files before calling
    FileManager.resolve_targets."""
    pass


class NoFileToRenameError(Exception):
    """Exception raised when FileManager.files is empty because it was depleted
    by previously calling FileManager.rename_files or because the given
    directory has no files to rename."""
    pass


@dataclasses.dataclass
class FileManager:
    """Manages File instances."""

    path: pathlib.Path
    files: list = dataclasses.field(init=False)

    def __post_init__(self):
        files = FileManager.list_files(self.path)

        # Makes sure there are files to be renamed
        if len(files) == 0:
            message = f'{self.path} has no file to be rename.'
            raise NoFileToRenameError(message)
        else:
            self.files = files

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
        """Removes duplicate files from FileManager.files, preventing them
        to be renamed in the future."""

        for duplicate in duplicates:
            self.files.remove(duplicate)

    def delete_duplicates(self, duplicates):
        """Deletes duplicate files. Raise DuplicateNotRemovedError if the
        duplicate is an element of FileManager.files."""

        for duplicate in duplicates:
            if duplicate in self.files:
                message = (f'Remove {duplicate.path} from '
                           'FileManager.files with '
                           'FileManager.remove_duplicates before attempting '
                           'to deleting it.')
                raise DuplicateNotRemovedError(message)
            else:
                os.remove(duplicate.path)

    def resolve_targets(self):
        """Resolve targets collisions by incrementing indexes and finding
        unique names."""

        targets = []

        for file_ in self.files:
            while file_.target in targets:
                file_.increment_target()

            targets.append(file_.target)

        # Verify if the name of the file is unique or if its the first of a
        # sequence of incrementing names
        for file_ in self.files:
            if file_.index == 1:
                name = f'{file_.target.stem[:-1]}2{file_.target.suffix}'
                target = file_.target.parent / name

                if target not in targets:
                    file_.target = file_.get_target(unique=True)

            file_.resolved = True

    def rename_files(self):
        """Rename the files managed by this instance of FileManager. Raises
        NoFileToRenameError if FileManager.rename_files was called before and
        TargetNotResolvedError if FileManager.resolve_targets was not called
        yet."""

        if len(self.files) == 0:
            message = ('FileManager.files is empty. There is no file to '
                       'rename anymore')
            raise NoFileToRenameError(message)

        for file_ in self.files:
            if not file_.resolved:
                message = (f'Resolve {file_.path} target before attempting to '
                           'rename it.')
                raise TargetNotResolvedError(message)

            file_.path.rename(file_.target)

        self.files.clear()


if __name__ == '__main__':
    # TODO: Test if the path exists before instanciate FileManager
    path = pathlib.Path(sys.argv[1])
    file_manager = FileManager(path)
    duplicates = file_manager.find_duplicates()
    # TODO: Prompt the user to delete the duplicates found
    file_manager.remove_duplicates(duplicates)
    file_manager.delete_duplicates(duplicates)
    # TODO: Explore the possibility of inject exif info into files that does
    # not have it already
    file_manager.resolve_targets()
    file_manager.rename_files()
