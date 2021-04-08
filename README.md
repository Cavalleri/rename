# Rename 1.0.0

Rename finds and deletes identical copies of a file and uses Exiftool to rename files in the given directory. Files are renamed to their date of creation or modification (whichever is older) following the YYYYMMDD HHMMSS ZZZZ format. If more than one file has the same creation or modification date, a positive integer is appended to its name.

## Usage

To use Rename, use the following command (assuming you have rename.py in the PATH variable):

``` bash
rename.py <path> # where <path> is the directory of the files to be renamed
```

## Requirements

You must have Exiftool installed.
