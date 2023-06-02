from parsers import readFumen, parseTJA
from writers import writeFumen
from converters import convertTJAToFumen
from utils import checkMismatchedBytes

tja2fumen_version = "v0.1"


if __name__ == "__main__":
    # arguments = parser.parse_args()
    arguments = {
        "input_fumen": "test-data/ia6cho_m.bin",  # NB: Contains only oni chart
        "input_tja": "test-data/Rokuchounen to Ichiya Monogatari.tja",  # NB: Contains 5 charts
    }
    # Parse fumen
    inputFile = open(arguments["input_fumen"], "rb")
    parsedSongFumen = readFumen(inputFile)

    # Steps to validate the `writeFumen` function to make sure it reproduces correct output
    validate = False
    if validate:
        outputName = inputFile.name.split('.')[0] + "_rebuilt.bin"
        outputFile = open(outputName, "wb")
        writeFumen(outputFile, parsedSongFumen)
        # Read output file back in to validate that the rewritten song is a perfect match
        print(False if checkMismatchedBytes(inputFile.name, outputFile.name) else True)

    # Parse tja
    inputFile = open(arguments["input_tja"], "r", encoding="utf-8-sig")
    parsedSongsTJA = parseTJA(inputFile)

    # Try converting the Oni TJA chart to match the Oni fumen
    convertedTJA = convertTJAToFumen(parsedSongFumen, parsedSongsTJA['Oni'])
    outputName = inputFile.name.split('.')[0] + ".bin"
    outputFile = open(outputName, "wb")
    writeFumen(outputFile, convertedTJA)
