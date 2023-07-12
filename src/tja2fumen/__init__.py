import argparse
import os
import sys

from tja2fumen.parsers import parseTJA
from tja2fumen.writers import writeFumen
from tja2fumen.converters import convertTJAToFumen
from tja2fumen.constants import COURSE_IDS


def main(argv=None):
    if not argv:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="tja2fumen"
    )
    parser.add_argument(
        "file.tja",
        help="Path to a Taiko no Tatsujin TJA file.",
    )
    args = parser.parse_args(argv)
    fnameTJA = getattr(args, "file.tja")
    baseName = os.path.splitext(fnameTJA)[0]

    # Parse lines in TJA file
    parsedTJA = parseTJA(fnameTJA)

    # Convert parsed TJA courses to Fumen data, and write each course to `.bin` files
    for course in parsedTJA.courses.items():
        convert_and_write(course, baseName, singleCourse=(len(parsedTJA.courses) == 1))


def convert_and_write(parsedCourse, baseName, singleCourse=False):
    courseName, tjaData = parsedCourse
    fumenData = convertTJAToFumen(tjaData)
    # Add course ID (e.g. '_x', '_x_1', '_x_2') to the output file's base name
    outputName = baseName
    if singleCourse:
        pass  # Replicate tja2bin.exe behavior by excluding course ID if there's only one course
    else:
        splitName = courseName.split("P")  # e.g. 'OniP2' -> ['Oni', '2'], 'Oni' -> ['Oni']
        outputName += f"_{COURSE_IDS[splitName[0]]}"
        if len(splitName) == 2:
            outputName += f"_{splitName[1]}"  # Add "_1" or "_2" if P1/P2 chart
    writeFumen(f"{outputName}.bin", fumenData)


# NB: This entry point is necessary for the Pyinstaller executable
if __name__ == "__main__":
    main()
