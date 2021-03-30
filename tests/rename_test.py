from rename import rename

import datetime
import os
import pathlib
import pytest
import pytz
import shutil


TESTS = pathlib.Path() / 'tests'
SAMPLES = TESTS / 'samples'


def clean_up():
    """Removes all JPG files in the tests directory."""

    for file_ in TESTS.iterdir():
        if file_.suffix == '.jpg':
            os.remove(file_)


def test_clean_up():
    """Tests if all JPG files have been removed from the tests directory."""

    for file_ in SAMPLES.iterdir():
        shutil.copy2(file_, TESTS)

    clean_up()

    files = [file_ for file_ in TESTS.iterdir() if file_.suffix == '.jpg']
    assert len(files) == 0


def test_find_duplicates_no_duplicate():
    """Tests if rename.find_duplicates finds duplicates when there is no
    duplicates."""

    for file_ in SAMPLES.iterdir():
        shutil.copy2(file_, TESTS)

    duplicates = rename.search_duplicates(TESTS)

    clean_up()

    assert len(duplicates) == 0


def test_find_duplicates_all_duplicates():
    """Tests if rename.find_duplicates can find duplicates when all the files
    have duplicates."""

    counter = 1
    for file_ in SAMPLES.iterdir():
        for __ in range(2):
            shutil.copy2(file_, TESTS / f'sample {counter}.jpg')
            counter += 1

    duplicates = rename.search_duplicates(TESTS)

    clean_up()

    assert len(duplicates) == len(list(SAMPLES.iterdir()))


def test_delete_duplicates_no_duplicate(capsys):
    rename.delete_duplicates([])
    captured = capsys.readouterr()

    assert captured.out == 'No duplicates files were found\n'


def test_delete_duplicates_input_no(capsys):
    """Tests if rename.delete_duplicates skips duplicates deletion when the
    user's input is no."""

    duplicates = []

    counter = 1
    for file_ in SAMPLES.iterdir():
        paths = []

        for __ in range(2):
            path = TESTS / f'sample {counter}.jpg'
            paths.append(path)
            shutil.copy2(file_, path)
            counter += 1

        duplicates.append(paths)

    # Mock built-in input function allowing stdout to be captured by capsys
    rename.input = lambda arg: 'n'

    rename.delete_duplicates(duplicates)
    captured = capsys.readouterr()

    clean_up()
    rename.input = input

    output = 'The following files are duplicated:\n'

    for duplicate in duplicates:
        output += str(duplicate[0]) + ' ' + str(duplicate[1]) + '\n'

    output += 'No duplicate file was deleted\n'

    assert captured.out == output


def test_delete_duplicates_input_yes(capsys):
    """Tests if rename.delete_duplicates correclty deletes the duplicates found
    and reports the amount of duplicates deleted."""

    duplicates = []

    counter = 1
    for file_ in SAMPLES.iterdir():
        paths = []

        for __ in range(2):
            path = TESTS / f'sample {counter}.jpg'
            paths.append(path)
            shutil.copy2(file_, path)
            counter += 1

        duplicates.append(paths)

    # Mock built-in input function allowing stdout to be captured by capsys
    rename.input = lambda arg: 'y'

    rename.delete_duplicates(duplicates)
    captured = capsys.readouterr()

    clean_up()
    rename.input = input

    output = 'The following files are duplicated:\n'

    for duplicate in duplicates:
        output += str(duplicate[0]) + ' ' + str(duplicate[1]) + '\n'

    output += f'{len(duplicates)} duplicate files deleted\n'

    assert captured.out == output


def test_create_date_with_exif():
    create_date = rename.get_create_date(SAMPLES / 'sample 1.jpg')
    assert create_date == datetime.datetime(2008, 5, 30, 15, 56, 1)


def test_create_date_without_exif():
    with pytest.raises(ValueError):
        rename.get_create_date(SAMPLES / 'sample 6.jpg')


def test_create_date_no_exiftool(capsys):
    """Ensures that the user will be notified if he does not has Exiftool
    installed."""

    # Mock subprocess.run to force raise FileNotFoundError
    def mock_run(*args, **kwargs):
        raise FileNotFoundError

    mocked_run = rename.subprocess.run
    rename.subprocess.run = mock_run

    with pytest.raises(FileNotFoundError):
        rename.get_create_date(SAMPLES / 'sample 2.jpg')

    captured = capsys.readouterr()

    rename.subprocess.run = mocked_run

    assert captured.out == ('Could not run Exiftool. Make sure you have '
                            'Exiftool installed\n' + '-' * 61 + '\n')


@pytest.fixture
def sample_1_create_date():
    """Localize the sample 1 create date based on the user's time zone."""

    # NOTE: I don't know why, but providing tz_info to datetime set the time
    # zone off by a few minutes
    tz_info = pytz.timezone('America/Sao_Paulo')
    date = datetime.datetime(2008, 5, 30, 15, 56, 1)
    date = tz_info.localize(date)
    date = date.astimezone(rename.LOCAL_TZ)

    return date.strftime('%Y%m%d %H%M%S %z')


def test_get_name(sample_1_create_date):
    """Tests if rename.test_get_name correctly gets the name of a sample that
    has EXIF information."""

    name = rename.get_name(SAMPLES / 'sample 1.jpg')
    assert name == sample_1_create_date


def test_get_target_no_counter(sample_1_create_date):
    """Tests if rename.get_target correctly builds the target path to rename
    the sample."""

    sample_1 = pathlib.Path(SAMPLES / 'sample 1.jpg')
    target = rename.get_target(sample_1)
    assert target == SAMPLES / (sample_1_create_date + '.jpg')


def test_get_target_with_counter(sample_1_create_date):
    """Tests if rename.get_target correctly builds the target path to rename
    the sample if counter is given."""

    sample_1 = pathlib.Path(SAMPLES / 'sample 1.jpg')
    target = rename.get_target(sample_1, 1)
    assert target == SAMPLES / (sample_1_create_date + ' 1.jpg')


def test_rename_1_sample(sample_1_create_date):
    """Tests if rename.rename_file correctly renames a single sample."""

    shutil.copy2(SAMPLES / 'sample 1.jpg', TESTS)
    rename.rename_file(TESTS / 'sample 1.jpg')
    samples = pathlib.Path(TESTS).glob('*.jpg')
    sample_1 = list(samples)[0]

    clean_up()

    assert sample_1.stem == sample_1_create_date


def test_rename_3_samples(sample_1_create_date):
    """Tests if rename.rename_file correctly renames samples that have the
    same create date."""

    for index in range(3):
        shutil.copy2(SAMPLES / 'sample 1.jpg', TESTS / f'sample {index}.jpg')

    for file_ in TESTS.iterdir():
        if file_.suffix == '.jpg':
            rename.rename_file(file_)

    samples = pathlib.Path(TESTS).glob('*.jpg')

    clean_up()

    for index, sample in enumerate(samples):
        assert sample.stem == f'{sample_1_create_date} {index + 1}'