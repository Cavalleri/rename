from rename import rename

import datetime
import os
import pathlib
import pytest
import pytz
import shutil


TESTS = pathlib.Path() / 'tests'
SAMPLES = TESTS / 'samples'


def clean_up(target=TESTS):
    """Removes all .jpg file in the given target (default is TESTS)."""

    for file_ in target.iterdir():
        if file_.suffix == '.jpg':
            os.remove(file_)


def copy_samples(destination=TESTS):
    """Copy all the samples in SAMPLES to the given destination
    (default is TESTS)."""

    # It is not necesssary to check if file_ is a file because SAMPLES
    # must contain only files
    for file_ in SAMPLES.iterdir():
        shutil.copy2(file_, destination)


def copy_sample_n_times(times):
    """Copy SAMPLES/sample 1.jpg to TESTS n times. Returns a list of the
    target paths to facilitate testing."""

    targets = []

    for index in range(times):
        target = TESTS / f'sample {index + 1}.jpg'
        shutil.copy2(SAMPLES / 'sample 1.jpg', target)
        targets.append(target)

    return targets


@pytest.fixture
def samples_create_date():
    """Localize the sample create date based on the user's time zone."""

    tz_info = pytz.timezone('America/Sao_Paulo')
    create_dates = (
        (2008, 5, 30, 15, 56, 1),
        (2008, 5, 4, 16, 47, 24),
        (2004, 8, 27, 13, 52, 55),
        (2001, 2, 19, 6, 40, 5),
        (2006, 10, 22, 15, 44, 29)
    )

    dates = []
    for create_date in create_dates:
        # NOTE: Providing a tz_info to the datetime constructor set the time
        # zone off by a few minutes, but using tzlocal localize does not
        date = datetime.datetime(*create_date)
        date = tz_info.localize(date)
        date = date.astimezone(rename.LOCAL_TZ)
        dates.append(date.strftime('%Y%m%d %H%M%S %z'))

    return dates


def test_samples_create_date(samples_create_date):
    """Tests if the list of dates produced by samples_create_date fixture are
    correct."""

    if str(rename.LOCAL_TZ) != 'America/Sao_Paulo':
        pytest.skip('This test only works for the GMT-3 time zone.')

    expected = [
        '20080530 155601 -0300',
        '20080504 164724 -0300',
        '20040827 135255 -0300',
        '20010219 064005 -0300',
        '20061022 154429 -0300'
    ]

    assert expected == samples_create_date


def test_list_duplicates(capsys):
    """Tests if rename.list_duplicates outputs as expected."""

    samples = [rename.File(sample) for sample in SAMPLES.iterdir()]
    rename.list_duplicates(sorted(samples))

    captured = capsys.readouterr()

    expected = 'Found the following duplicate files:\n'
    for index in range(len(samples)):
        expected += f'tests/samples/sample {index + 1}.jpg\n'

    assert captured.out == expected


def test_list_duplicates_no_duplicates(capsys):
    """Tests if rename.list_duplicates outputs as expected when the duplicates
    list is empty."""

    rename.list_duplicates([])
    captured = capsys.readouterr()

    assert captured.out == 'No duplicate file was found\n'


def test_prompt_user(capsys):
    """Ensures rename.prompt_user outputs the correct message according to
    the user's response."""

    mocked_remove = rename.FileManager.remove_duplicates
    rename.FileManager.remove_duplicates = lambda *a, **kw: a

    mocked_delete = rename.FileManager.delete_duplicates
    rename.FileManager.delete_duplicates = lambda *a, **kw: a

    duplicates = list(range(10))
    file_manager = rename.FileManager(SAMPLES)

    # Test positive answer
    rename.input = lambda *a, **kw: 'y'
    rename.prompt_user(duplicates, file_manager)
    captured = capsys.readouterr()
    assert captured.out == '10 duplicate files deleted.\n'

    # Test negative answer
    rename.input = lambda *a, **kw: 'n'
    rename.prompt_user(duplicates, file_manager)
    captured = capsys.readouterr()
    assert captured.out == 'No duplicate file was removed.\n'

    rename.input = input
    rename.FileManager.remove_duplicates = mocked_remove
    rename.FileManager.delete_duplicates = mocked_delete


class TestFile:
    """Contains rename.File tests."""

    @staticmethod
    def test_get_date(samples_create_date):
        """Verifies if rename.File.get_date correctly extracts sample's create
        date using Exiftool."""

        date = rename.File.get_date(SAMPLES / 'sample 1.jpg')
        date = date.strftime('%Y%m%d %H%M%S %z')

        assert date == samples_create_date[0]

    @staticmethod
    def test_get_target(samples_create_date):
        """Ensures File.get_target correctly makes File.target."""

        file_ = rename.File(SAMPLES / 'sample 1.jpg')
        target = SAMPLES / f'{samples_create_date[0]} 1.jpg'

        assert file_.target == target

    @staticmethod
    def test_increment_target(samples_create_date):
        """Tests if File.increment_target correctly increments File.index and
        remakes File.target."""

        file_ = rename.File(SAMPLES / 'sample 1.jpg')
        file_.increment_target()
        target = SAMPLES / f'{samples_create_date[0]} 2.jpg'

        assert file_.target == target

    @staticmethod
    def test_rename(samples_create_date):
        """Tests if File.rename correctly renames the file."""

        copy_samples()
        files = [rename.File(file_) for file_ in TESTS.iterdir()
                 if file_.suffix == '.jpg']

        for file_ in files:
            file_.resolved = True
            file_.rename()

        expected = [pathlib.Path(TESTS) / f'{date} 1.jpg' for date
                    in samples_create_date]

        result = [sample for sample in TESTS.iterdir()
                  if sample.suffix == '.jpg']

        assert sorted(result) == sorted(expected)

        clean_up()

    @staticmethod
    def test_rename_raises_exception():
        """Ensures rename.File.rename raises rename.TargetNotResolvedError
        if the targets have not been resolved yet."""

        path, *__ = copy_sample_n_times(1)
        file_ = rename.File(path)

        with pytest.raises(rename.TargetNotResolvedError) as error:
            file_.rename()

        assert error.value.args[0] == (f'Resolve {path} target before '
                                       'attempting to rename it.')

        clean_up()


class TestFileManager:
    """Contains rename.FileManager tests."""

    @staticmethod
    def test_constructor_raises_exception():
        """Ensures rename.FileManger will raise rename.NotFileToRenameError,
        with the correct message, if the given directory is empty."""

        temp = TESTS / 'temp'
        temp.mkdir()

        with pytest.raises(rename.NoFileToRenameError) as error:
            rename.FileManager(temp)

        message = f'{temp} has no file to rename.'

        assert error.value.args[0] == message

        temp.rmdir()

    @staticmethod
    def test_find_duplicates_all_duplicates():
        """Asserts if rename.FileManager.find_duplicates correctly indentifies
        all the copies of the same file as duplicate."""

        copies = 5
        copy_sample_n_times(copies)

        file_manager = rename.FileManager(TESTS)
        duplicates = file_manager.find_duplicates()

        # One copy will be considered as the original
        assert len(duplicates) == copies - 1

        clean_up()

    @staticmethod
    def test_find_duplicates_no_duplicate():
        """Asserts if rename.FileManager.find_duplicates correctly indentifies
        all the copies of the same file as duplicate."""

        copy_samples()

        file_manager = rename.FileManager(TESTS)
        duplicates = file_manager.find_duplicates()

        assert len(duplicates) == 0

        clean_up()

    @staticmethod
    def test_delete_duplicate_before_remove():
        """Ensures that FileManager.delete_duplicate will raise
        rename.DuplicateNotRemovedError with the correct message if the user
        attempts to delete a duplicate file that was not first removed from
        FileManager.files"""

        copy_sample_n_times(2)
        file_manager = rename.FileManager(TESTS)
        duplicates = file_manager.find_duplicates()

        with pytest.raises(rename.DuplicateNotRemovedError) as error:
            file_manager.delete_duplicates(duplicates)

        message = (f'Remove {duplicates[0].path} from FileManager.files with '
                   'FileManager.remove_duplicates before attempting to '
                   'deleting it.')

        assert error.value.args[0] == message

        clean_up()

    @staticmethod
    def test_resolve_targets_all_duplicates(samples_create_date):
        """Tests if FileManager.resolve_targets correctly increments the
        targets when all samples are duplicates."""

        copies = 5
        copy_sample_n_times(copies)

        file_manager = rename.FileManager(TESTS)
        file_manager.resolve_targets()

        result = [file_.target for file_ in file_manager.files
                  if file_.path.suffix == '.jpg']

        expected = []
        for index in range(copies):
            path = TESTS / f'{samples_create_date[0]} {index + 1}.jpg'
            expected.append(path)

        assert sorted(result) == sorted(expected)

        clean_up()

    @staticmethod
    def test_resolve_targets_all_uniques(samples_create_date):
        """Tests if FileManager.resolve_targets correctly classifies all
        samples target as unique."""

        copy_samples()

        file_manager = rename.FileManager(TESTS)
        file_manager.resolve_targets()

        result = [file_.target for file_ in file_manager.files
                  if file_.path.suffix == '.jpg']

        expected = []
        for create_date in samples_create_date:
            path = TESTS / f'{create_date}.jpg'
            expected.append(path)

        assert sorted(result) == sorted(expected)

        clean_up()

    @staticmethod
    def test_rename_files_subsequent_call():
        """Tests if FileManager.rename_files raises rename.NoFileToRenameError,
        with the correct message, when the file manager has been depleted."""

        temp = TESTS / 'temp'
        temp.mkdir()
        copy_samples(temp)

        file_manager = rename.FileManager(temp)
        file_manager.resolve_targets()
        file_manager.rename_files()

        assert file_manager.depleted is True

        with pytest.raises(rename.NoFileToRenameError) as error:
            file_manager.rename_files()

        assert error.value.args[0] == ('FileManager is depleted. There is no '
                                       'file to be renamed')

        clean_up(temp)
        temp.rmdir()
