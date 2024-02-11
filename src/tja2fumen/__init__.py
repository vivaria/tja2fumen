"""
Entry points for tja2fumen.
"""

import argparse
import os
import shutil
import sys
from typing import Sequence

from tja2fumen.parsers import parse_tja, parse_fumen
from tja2fumen.converters import convert_tja_to_fumen, fix_dk_note_types_course
from tja2fumen.writers import write_fumen
from tja2fumen.constants import COURSE_IDS
from tja2fumen.classes import TJACourse


def main(argv: Sequence[str] = ()) -> None:
    """
    Main entry point for tja2fumen's command line interface.

    tja2fumen can be used in 2 ways:

    - If a .tja file is provided, then three steps are performed:
          1. Parse TJA into multiple TJACourse objects. Then, for each course:
          2. Convert TJACourse objects into FumenCourse objects.
          3. Write each FumenCourse to its own .bin file.
    - If a .bin file is provided, then the existing .bin is repaired:
          1. Update don/kat senote types to do-ko-don and ka-kat.
    """
    if not argv:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="tja2fumen"
    )
    parser.add_argument(
        "file",
        help="Path to a Taiko no Tatsujin chart file.",
    )
    args = parser.parse_args(argv)
    fname = getattr(args, "file")
    base_name = os.path.splitext(fname)[0]

    if fname.endswith(".bin"):
        repair_bin(fname)
    else:
        # Parse lines in TJA file
        parsed_tja = parse_tja(fname)

        # Convert parsed TJA courses and write each course to `.bin` files
        for course_name, course in parsed_tja.courses.items():
            convert_and_write(course, course_name, base_name,
                              single_course=len(parsed_tja.courses) == 1)


def convert_and_write(tja_data: TJACourse,
                      course_name: str,
                      base_name: str,
                      single_course: bool = False) -> None:
    """Process the parsed data for a single TJA course."""
    fumen_data = convert_tja_to_fumen(tja_data)
    # fix don/ka types
    fix_dk_note_types_course(fumen_data)
    # Add course ID (e.g. '_x', '_x_1', '_x_2') to the output file's base name
    output_name = base_name
    if single_course:
        pass  # Replicate tja2bin.exe behavior by excluding course ID
    else:
        split_name = course_name.split("P")  # e.g. 'OniP2' -> ['Oni', '2']
        output_name += f"_{COURSE_IDS[split_name[0]]}"
        if len(split_name) == 2:
            output_name += f"_{split_name[1]}"  # Add "_1"/"_2" if P1/P2 chart
    write_fumen(f"{output_name}.bin", fumen_data)


def repair_bin(fname_bin: str) -> None:
    """Repair the don/ka types of an existing .bin file."""
    fumen_data = parse_fumen(fname_bin)
    # fix don/ka types
    fix_dk_note_types_course(fumen_data)
    # write repaired fumen
    shutil.move(fname_bin, fname_bin+".bak")
    write_fumen(fname_bin, fumen_data)


# NB: This entry point is necessary for the Pyinstaller executable
if __name__ == "__main__":
    main()
