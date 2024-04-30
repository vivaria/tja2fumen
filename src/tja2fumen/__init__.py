"""
Entry points for tja2fumen.
"""

import argparse
import os
import shutil
import sys
from typing import Sequence, Tuple, List

from tja2fumen.parsers import parse_tja, parse_fumen
from tja2fumen.converters import convert_tja_to_fumen, fix_dk_note_types_course
from tja2fumen.writers import write_fumen
from tja2fumen.constants import COURSE_IDS
from tja2fumen.classes import TJACourse


def main(argv: Sequence[str] = ()) -> None:
    """
    Main entry point for tja2fumen's command line interface.
    """
    if not argv:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""
tja2fumen is a tool to

tja2fumen can be used in 3 ways:
- If a .tja file is provided, then three steps are performed:
    1. Parse TJA into multiple TJACourse objects. Then, for each course:
    2. Convert TJACourse objects into FumenCourse objects.
    3. Write each FumenCourse to its own .bin file.

- If a .bin file is provided, then the existing .bin is repaired:
    1. Update don/kat senote types to do-ko-don and ka-kat.
    2. Update timing windows to fix previous bug with Easy/Normal timing.

- If a folder is provided, then all .tja and .bin files will be recursively
processed according to the above logic. (Confirmation is required for safety.)
        """
    )
    parser.add_argument(
        "input",
        help="Path to a Taiko no Tatsujin chart file or folder.",
    )
    args = parser.parse_args(argv)
    path_input = getattr(args, "input")
    if os.path.isdir(path_input):
        print(f"Folder passed to tja2fumen. "
              f"Looking for files in {path_input}...\n")
        tja_files, bin_files = parse_files(path_input)
        print("\nThe following TJA files will be CONVERTED:")
        for tja_file in tja_files:
            print(f"  - {tja_file}")
        print("\nThe following BIN files will be REPAIRED:")
        for bin_file in bin_files:
            print(f"  - {bin_file}")
        choice = input("\nDo you wish to continue? [y/n]")
        if choice.lower() != "y":
            sys.exit("'y' not selected, exiting.")
        print()
        files = tja_files + bin_files

    elif os.path.isfile(path_input):
        files = [path_input]
    else:
        raise FileNotFoundError("No such file or directory: " + path_input)

    for file in files:
        process_file(file)


def parse_files(directory: str) -> Tuple[List[str], List[str]]:
    """Find all .tja or .bin files within a directory."""
    tja_files, bin_files = [], []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".tja"):
                tja_files.append(os.path.join(root, file))
            elif file.endswith(".bin"):
                if file.startswith("song_"):
                    print(f"Skipping '{file}' because it starts with 'song_' "
                          f"(probably an audio file, not a chart file).")
                    continue
                bin_files.append(os.path.join(root, file))
    return tja_files, bin_files


def process_file(fname: str) -> None:
    """Process a single file path (TJA or BIN)."""
    if fname.endswith(".bin"):
        print(f"Repairing {fname}")
        repair_bin(fname)
    elif fname.endswith(".tja"):
        print(f"Converting {fname}")
        # Parse lines in TJA file
        parsed_tja = parse_tja(fname)

        # Convert parsed TJA courses and write each course to `.bin` files
        base_name = os.path.splitext(fname)[0]
        for course_name, course in parsed_tja.courses.items():
            convert_and_write(course, course_name, base_name,
                              single_course=len(parsed_tja.courses) == 1)
    else:
        raise ValueError(f"Unrecognized file type: {fname} "
                         f"(expected .tja or .bin)")


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
    # fix timing windows
    for course, course_id in COURSE_IDS.items():
        if any(fname_bin.endswith(f"_{i}.bin")
               for i in [course_id, f"{course_id}_1", f"{course_id}_2"]):
            print(f"  - Setting {course} timing windows...")
            fumen_data.header.set_timing_windows(difficulty=course)
            break
    else:
        print(f"  - Can't infer difficulty {list(COURSE_IDS.values())} from "
              f"filename. Skipping timing window fix...")

    # fix don/ka types
    print("  - Fixing don/ka note types (do/ko/don, ka/kat)...")
    fix_dk_note_types_course(fumen_data)
    # write repaired fumen
    shutil.move(fname_bin, fname_bin+".bak")
    write_fumen(fname_bin, fumen_data)


# NB: This entry point is necessary for the Pyinstaller executable
if __name__ == "__main__":
    main()
