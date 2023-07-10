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

    # Convert TJA data to fumen data
    parsedSongsTJA = parseTJA(fnameTJA)
    parsedSongsFumen = {course: convertTJAToFumen(tjaData)
                        for course, tjaData in parsedSongsTJA.items()}

    # Generate output filenames
    baseName = os.path.splitext(fnameTJA)[0]
    outputFilenames = []
    for courseName, fumenData in parsedSongsFumen.items():
        if len(parsedSongsTJA) == 1:
            outputName = f"{baseName}.bin"
        else:
            splitName = courseName.split("P")  # e.g. 'OniP2' -> ['Oni', '2'], 'Oni' -> ['Oni']
            outputName = f"{baseName}_{COURSE_IDS[splitName[0]]}"
            if len(splitName) == 2:
                outputName += f"_{splitName[1]}"  # Add "_1" or "_2" if P1/P2 chart
            outputName += ".bin"
        outputFilenames.append(outputName)
        writeFumen(outputName, fumenData)


# NB: This entry point is necessary for the Pyinstaller executable
if __name__ == "__main__":
    main()
