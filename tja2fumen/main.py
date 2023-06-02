from tja2fumen.parsers import readFumen, parseTJA
from tja2fumen.writers import writeFumen
from tja2fumen.converters import convertTJAToFumen
from tja2fumen.utils import checkMismatchedBytes

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
    fnameFumen = "test-data/12373714_m.bin"
    fnameTJA = "test-data/Unlimited Games.tja"  # NB: Contains 5 charts
    fumen, convertedTJAs = main(fnameFumen=fnameFumen, fnameTJA=fnameTJA)

    for course, song in convertedTJAs.items():
        outputName = ".".join(fnameTJA.split('.')[0:-1]) + f"_{course}.bin"
        outputFile = open(outputName, "wb")
        writeFumen(outputFile, song)
