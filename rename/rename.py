import dataclasses
import datetime
import os
import pathlib
import subprocess
import sys
import tzlocal


LOCAL_TZ = tzlocal.get_localzone()


class DuplicateNotRemovedError(Exception):
    """Exception raised when the user attempts to delete a duplicate file that
    was not removed from FileManager.files."""
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


@dataclasses.dataclass(order=True)
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
        """Gets the file oldest available date of creation or modification."""

        # Lists all dates related to the creation or modification of the file,
        # then sorts the list and localizes the oldest date
        args = ['exiftool', path, '-CreateDate', '-ModifyDate',
                '-FileModifyDate', '-s', '-s', '-s']
        process = subprocess.run(args, capture_output=True)
        output = process.stdout.decode('utf-8')

        dates = []
        for str_ in output.split('\n')[:-1]:
            # Slices off the time zone part
            if len(str_) > 19:
                str_ = str_[:-6]

            year = int(str_[:4])
            if year > datetime.MINYEAR and year < datetime.MAXYEAR:
                date = datetime.datetime.strptime(str_, '%Y:%m:%d %H:%M:%S')
                dates.append(date)

        stamp = path.stat().st_ctime
        date = datetime.datetime.fromtimestamp(stamp)
        dates.append(date)

        date = sorted(dates)[0]
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

    def rename(self):
        """Rename the File. Raises TargetNotResolvedError if the target was not
        resolved by the FileManager."""

        if not self.resolved:
            message = (f'Resolve {self.path} target before attempting to '
                       'rename it.')
            raise TargetNotResolvedError(message)

        self.path.rename(self.target)


@dataclasses.dataclass
class FileManager:
    """Manages File instances."""

    path: pathlib.Path
    files: list = dataclasses.field(init=False)
    depleted: bool = dataclasses.field(default=False, init=False)

    def __post_init__(self):
        files = FileManager.list_files(self.path)

        # Makes sure there are files to be renamed
        if len(files) == 0:
            message = f'No file was found in {self.path} to be renamed.'
            print(message + '\n' + '-' * len(message))
            raise NoFileToRenameError(f'{self.path} has no file to rename.')
        else:
            self.files = sorted(files)

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

        # Verifies if the name of the file is unique or if its the first of a
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
        NoFileToRenameError if the FileManager was depleted."""

        if self.depleted:
            message = ('FileManager is depleted. There is no file to be '
                       'renamed')
            raise NoFileToRenameError(message)

        for file_ in self.files:
            file_.rename()

        self.depleted = True


def list_duplicates(duplicates):
    """Prints a list of all duplicate files found."""

    if len(duplicates) == 0:
        print('No duplicate file was found')
    else:
        print('Found the following duplicate files:')

        for duplicate in duplicates:
            print(duplicate.path)


def prompt_user(duplicates, file_manager):
    """Ask the user if he wants to delete the duplicate files found. If the
    answer is positive, makes the FileManager instance delete the duplicate
    files."""

    if len(duplicates) != 0:
        answer = input('Delete duplicate files? (y/n) ')

        if answer in ['y', 'Y', 's', 'S']:
            file_manager.remove_duplicates(duplicates)
            file_manager.delete_duplicates(duplicates)

            print(f'{len(duplicates)} duplicate files deleted.')
        else:
            print('No duplicate file was removed.')


if __name__ == '__main__':
    path = pathlib.Path(sys.argv[1])
    file_manager = FileManager(path)

    duplicates = file_manager.find_duplicates()
    list_duplicates(duplicates)
    prompt_user(duplicates, file_manager)

    file_manager.resolve_targets()
    file_manager.rename_files()

    print(f'Renamed {len(file_manager.files)} files.')
