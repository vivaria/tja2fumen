import argparse
import os
import sys

from tja2fumen.parsers import parseTJA
from tja2fumen.writers import writeFumen
from tja2fumen.converters import convertTJAToFumen
from tja2fumen.constants import COURSE_IDS


def main(argv):
    # Parse args
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
    outputFilenames = [baseName + f"_{COURSE_IDS[course]}.bin" if len(parsedSongsTJA) > 1
                       else baseName + ".bin"
                       for course in parsedSongsFumen.keys()]

    # Write fumen data to files
    for fumenData, outputName in zip(parsedSongsFumen.values(), outputFilenames):
        writeFumen(open(outputName, "wb"), fumenData)

    return parsedSongsTJA, parsedSongsFumen, outputFilenames


if __name__ == "__main__":
    main(argv=sys.argv[1:])
