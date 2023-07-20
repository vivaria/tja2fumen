import argparse
import os
import sys

from tja2fumen.parsers import parse_tja
from tja2fumen.writers import write_fumen
from tja2fumen.converters import convert_tja_to_fumen
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
    fname_tja = getattr(args, "file.tja")
    base_name = os.path.splitext(fname_tja)[0]

    # Parse lines in TJA file
    parsed_tja = parse_tja(fname_tja)

    # Convert parsed TJA courses to Fumen data, and write each course to `.bin` files
    for course in parsed_tja.courses.items():
        convert_and_write(course, base_name, single_course=(len(parsed_tja.courses) == 1))


def convert_and_write(parsed_course, base_name, single_course=False):
    course_name, tja_data = parsed_course
    fumen_data = convert_tja_to_fumen(tja_data)
    # Add course ID (e.g. '_x', '_x_1', '_x_2') to the output file's base name
    output_name = base_name
    if single_course:
        pass  # Replicate tja2bin.exe behavior by excluding course ID if there's only one course
    else:
        split_name = course_name.split("P")  # e.g. 'OniP2' -> ['Oni', '2'], 'Oni' -> ['Oni']
        output_name += f"_{COURSE_IDS[split_name[0]]}"
        if len(split_name) == 2:
            output_name += f"_{split_name[1]}"  # Add "_1" or "_2" if P1/P2 chart
    write_fumen(f"{output_name}.bin", fumen_data)


# NB: This entry point is necessary for the Pyinstaller executable
if __name__ == "__main__":
    main()
