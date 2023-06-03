import argparse

from tja2fumen.parsers import readFumen, parseTJA
from tja2fumen.writers import writeFumen
from tja2fumen.converters import convertTJAToFumen
from tja2fumen.utils import checkMismatchedBytes
from tja2fumen.constants import COURSE_IDS

tja2fumen_version = "v0.1"


def main(fnameFumen=None, fnameTJA=None, validate=False):
    if fnameFumen:
        # Parse fumen
        inputFile = open(fnameFumen, "rb")
        parsedSongFumen = readFumen(inputFile)

        # Steps to validate the `writeFumen` function to make sure it reproduces correct output
        if validate:
            outputName = inputFile.name.split('.')[0] + "_rebuilt.bin"
            outputFile = open(outputName, "wb")
            writeFumen(outputFile, parsedSongFumen)
            # Read output file back in to validate that the rewritten song is a perfect match
            print(False if checkMismatchedBytes(inputFile.name, outputFile.name) else True)
    else:
        parsedSongFumen = None

    convertedTJAs = {}
    if fnameTJA:
        # Parse tja
        try:
            inputFile = open(fnameTJA, "r", encoding="utf-8-sig")
            parsedSongsTJA = parseTJA(inputFile)
        except UnicodeDecodeError:
            inputFile = open(fnameTJA, "r", encoding="shift-jis")
            parsedSongsTJA = parseTJA(inputFile)

        for course, song in parsedSongsTJA.items():
            convertedTJA = convertTJAToFumen(parsedSongFumen, song)
            convertedTJAs[course] = convertedTJA

    return parsedSongFumen, convertedTJAs


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
        outputName = ".".join(fnameTJA.split('.')[0:-1]) + f"_{COURSE_IDS[course]}.bin"
        outputFile = open(outputName, "wb")
        writeFumen(outputFile, song)
