import argparse
import os

from tja2fumen.parsers import parseTJA
from tja2fumen.writers import writeFumen
from tja2fumen.converters import convertTJAToFumen
from tja2fumen.constants import COURSE_IDS

tja2fumen_version = "v0.1"


def main(fnameTJA):
    convertedTJAs = {}
    try:
        inputFile = open(fnameTJA, "r", encoding="utf-8-sig")
        parsedSongsTJA = parseTJA(inputFile)
    except UnicodeDecodeError:
        inputFile = open(fnameTJA, "r", encoding="shift-jis")
        parsedSongsTJA = parseTJA(inputFile)

    for course, song in parsedSongsTJA.items():
        convertedTJA = convertTJAToFumen(song)
        convertedTJAs[course] = convertedTJA

    return convertedTJAs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="tja2fumen"
    )
    parser.add_argument(
        "file.tja",
        help="Path to a Taiko no Tatsujin TJA file.",
    )
    args = parser.parse_args()
    fnameTJA = getattr(args, "file.tja")

    fumen, convertedTJAs = main(fnameTJA=fnameTJA)

    for course, song in convertedTJAs.items():
        outputName = os.path.splitext(fnameTJA)[0]
        if len(convertedTJAs) == 1:
            outputName += ".bin"
        else:
            outputName += f"_{COURSE_IDS[course]}.bin"
        outputFile = open(outputName, "wb")
        writeFumen(outputFile, song)
