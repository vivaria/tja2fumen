import os
import sys
import struct
import argparse

tja2fumen_version = "v0.1"

branchNames = ("normal", "advanced", "master")

noteTypes = {
    0x1: "Don",  # ドン
    0x2: "Don",  # ド
    0x3: "Don",  # コ
    0x4: "Ka",   # カッ
    0x5: "Ka",   # カ
    0x6: "Drumroll",
    0x7: "DON",
    0x8: "KA",
    0x9: "DRUMROLL",
    0xa: "Balloon",
    0xb: "DON",       # hands
    0xc: "Kusudama",
    0xd: "KA",        # hands
    0x62: "Drumroll"  # ?
}

# Fumen headers are made up of smaller substrings of bytes
b_x00 = b'\x00\x00\x00\x00\x00\x00'
b_431 = b'43\xc8Ag&\x96B"\xe2\xd8B'
b_432 = b'43\xc8Ag&\x96BD\x84\xb7B'
b_433 = b'43\xc8A"\xe2\xd8B\x00@\xfaB'
b_434 = b'43\xc8AD\x84\xb7B"\xe2\xd8B'
b_g1 = b'g&\x96B4\xa3\x89Cxw\x05A'
b_V1 = b'V\xd5&B\x00@\xfaB\x00@\xfaB'
b_V2 = b'V\xd5&B"\xe2\xd8B\x00@\xfaB'
b_V3 = b'V\xd5&B\x00@\xfaB\xf0\xce\rC'

simpleHeaders = [b * 36 for b in [b_431, b_V1, b_V2]]


def checkValidHeader(header):
    # These simple headers (substrings repeated 36 times) are used for many Gen2 systems (AC, Wii, etc.)
    if header in simpleHeaders:
        return True
    # Starting with Gen3, they began using unique headers for every song. (3DS and PSPDX are the big offenders.)
    #   They seem to be some random combination of b_x00 + one of the non-null byte substrings.
    #   To avoid enumerating every combination of 432 bytes, we do a lazy check instead.
    elif b_x00 in header and any(b in header for b in [b_431, b_432, b_433, b_434, b_V1, b_V2, b_V3]):
        return True
    # The PS4 song 'wii5op' is a special case: It throws in this odd b_g1 string in combo with other substrings.
    elif b_g1 in header and any(b in header for b in [b_431, b_V2]):
        return True
    # Otherwise, this is some unknown header we haven't seen before.
    # Typically, these will be tja2bin.exe converted files with a completely invalid header.
    else:
        return False


def readFumen(fumenFile, byteOrder=None, debug=False):
    """
    Parse bytes of a fumen .bin file into nested measure, branch, and note dictionaries.

    For more information on any of the terms used in this function (e.g. scoreInit, scoreDiff),
    please refer to KatieFrog's excellent guide: https://gist.github.com/KatieFrogs/e000f406bbc70a12f3c34a07303eec8b
    """
    if type(fumenFile) is str:
        file = open(fumenFile, "rb")
    else:
        file = fumenFile
    size = os.fstat(file.fileno()).st_size

    # Check for valid fumen header (first 432 bytes) using valid byte substrings
    fumenHeader = file.read(432)
    if not checkValidHeader(fumenHeader):
        debugPrint(f"Invalid header!")

    # Determine:
    #   - The byte order (big or little endian)
    #   - The total number of measures from byte 0x200 (decimal 512)
    if byteOrder:
        order = ">" if byteOrder == "big" else "<"
        totalMeasures = readStruct(file, order, format_string="I", seek=0x200)[0]
    else:
        # Use the number of measures to determine the byte order
        measuresBig = readStruct(file, order="", format_string=">I", seek=0x200)[0]
        measuresLittle = readStruct(file, order="", format_string="<I", seek=0x200)[0]
        if measuresBig < measuresLittle:
            order = ">"
            totalMeasures = measuresBig
        else:
            order = "<"
            totalMeasures = measuresLittle

    # Initialize the dict that will contain the chart information
    song = {}
    song["length"] = totalMeasures

    # Determine whether the song has branches from byte 0x1b0 (decimal 432)
    hasBranches = getBool(readStruct(file, order, format_string="B", seek=0x1b0)[0])
    song["branches"] = hasBranches

    # Print general debug metadata about the song
    if debug:
        debugPrint("Total measures: {0}, {1} branches, {2}-endian".format(
            totalMeasures,
            "has" if hasBranches else "no",
            "Big" if order == ">" else "Little"
        ))

    # Start reading measure data from position 0x208 (decimal 520)
    file.seek(0x208)
    for measureNumber in range(totalMeasures):
        # Parse the measure data using the following `format_string`:
        #   "ffBBHiiiiiii" (12 format characters, 40 bytes per measure)
        #     - 'f': BPM              (represented by one float (4 bytes))
        #     - 'f': fumenOffset      (represented by one float (4 bytes))
        #     - 'B': gogo             (represented by one unsigned char (1 byte))
        #     - 'B': hidden           (represented by one unsigned char (1 byte))
        #     - 'H': <padding>        (represented by one unsigned short (2 bytes))
        #     - 'iiiiii': branchInfo  (represented by six integers (24 bytes))
        #     - 'i': <padding>        (represented by one integer (4 bytes)
        measureStruct = readStruct(file, order, format_string="ffBBHiiiiiii")

        # Create the measure dictionary using the newly-parsed measure data
        measure = {}
        measure["bpm"] = measureStruct[0]
        measure["fumenOffset"] = measureStruct[1]
        if measureNumber == 0:
            measure["offset"] = measure["fumenOffset"] + 240000 / measure["bpm"]
        else:
            prev = song[measureNumber - 1]
            measure["offset"] = ((prev["offset"] + measure["fumenOffset"] + 240000) /
                                 (measure["bpm"] - prev["fumenOffset"] - 240000 / prev["bpm"]))
        measure["gogo"] = getBool(measureStruct[2])
        measure["hidden"] = getBool(measureStruct[3])

        # Iterate through the three branch types
        for branchNumber in range(len(branchNames)):
            # Parse the measure data using the following `format_string`:
            #   "HHf" (3 format characters, 8 bytes per branch)
            #     - 'H': totalNotes (represented by one unsigned short (2 bytes))
            #     - 'H': <padding>  (represented by one unsigned short (2 bytes))
            #     - 'f': speed      (represented by one float (4 bytes)
            branchStruct = readStruct(file, order, format_string="HHf")

            # Create the branch dictionary using the newly-parsed branch data
            branch = {}
            totalNotes = branchStruct[0]
            branch["length"] = totalNotes
            branch["speed"] = branchStruct[2]

            # Print debug metadata about the branches
            if debug and (hasBranches or branchNumber == 0 or totalNotes != 0):
                branchName = " ({0})".format(
                    branchNames[branchNumber]
                ) if hasBranches or branchNumber != 0 else ""
                fileOffset = file.tell()
                debugPrint("")
                debugPrint("Measure #{0}{1} at {2}-{3} ({4})".format(
                    measureNumber + 1,
                    branchName,
                    shortHex(fileOffset - 0x8),
                    shortHex(fileOffset + 0x18 * totalNotes),
                    nameValue(measure, branch)
                ))
                debugPrint("Total notes: {0}".format(totalNotes))

            # Iterate through each note in the measure (per branch)
            for noteNumber in range(totalNotes):
                if debug:
                    fileOffset = file.tell()
                    debugPrint("Note #{0} at {1}-{2}".format(
                        noteNumber + 1,
                        shortHex(fileOffset),
                        shortHex(fileOffset + 0x17)
                    ), end="")

                # Parse the note data using the following `format_string`:
                #   "ififHHf" (7 format characters, 24 bytes per note cluster)
                #     - 'i': note type
                #     - 'f': note position
                #     - 'i': item
                #     - 'f': <padding>
                #     - 'H': scoreInit
                #     - 'H': scoreDiff
                #     - 'f': duration
                # NB: 'item' doesn't seem to be used at all in this function.
                noteStruct = readStruct(file, order, format_string="ififHHf")

                # Validate the note type
                noteType = noteStruct[0]
                if noteType not in noteTypes:
                    raise ValueError("Error: Unknown note type '{0}' at offset {1}".format(
                        shortHex(noteType).upper(),
                        hex(file.tell() - 0x18))
                    )

                # Create the note dictionary using the newly-parsed note data
                note = {}
                note["type"] = noteTypes[noteType]
                note["pos"] = noteStruct[1]
                if noteType == 0xa or noteType == 0xc:
                    # Balloon hits
                    note["hits"] = noteStruct[4]
                elif "scoreInit" not in song:
                    song["scoreInit"] = noteStruct[4]
                    song["scoreDiff"] = noteStruct[5] / 4.0
                if noteType == 0x6 or noteType == 0x9 or noteType == 0xa or noteType == 0xc:
                    # Drumroll and balloon duration in ms
                    note["duration"] = noteStruct[6]

                # Print debug information about the note
                if debug:
                    debugPrint(" ({0})".format(nameValue(note)))

                # Seek forward 8 bytes to account for padding bytes at the end of drumrolls
                if noteType == 0x6 or noteType == 0x9 or noteType == 0x62:
                    file.seek(0x8, os.SEEK_CUR)

                # Assign the note to the branch
                branch[noteNumber] = note

            # Assign the branch to the measure
            measure[branchNames[branchNumber]] = branch

        # Assign the measure to the song
        song[measureNumber] = measure
        if file.tell() >= size:
            break

    file.close()
    return song


def readStruct(file, order, format_string, seek=None):
    """
    Interpret bytes as packed binary data.

    Arguments:
        - file: The fumen's file object (presumably in 'rb' mode).
        - order: '<' or '>' (little or big endian).
        - format_string: String made up of format characters that describes the data layout.
                         Full list of available format characters:
                             (https://docs.python.org/3/library/struct.html#format-characters)
                         However, this script uses only the following format characters:
                           - B: unsigned char  (1 byte)
                           - H: unsigned short (2 bytes)
                           - I: unsigned int   (4 bytes)
                           - i: int            (4 bytes)
                           - f: float          (4 bytes)
        - seek: The position of the read pointer to be used within the file.

    Return values:
        - interpreted_string: A string containing interpreted byte values,
                              based on the specified 'fmt' format characters.
    """
    if seek:
        file.seek(seek)
    byte_string = file.read(struct.calcsize(order + format_string))
    interpreted_string = struct.unpack(order + format_string, byte_string)
    return interpreted_string


def shortHex(number):
    return hex(number)[2:]


def getBool(number):
    return True if number == 0x1 else False if number == 0x0 else number


def nameValue(*lists):
    string = []
    for lst in lists:
        for name in lst:
            if name == "type":
                string.append(lst[name])
            elif name != "length" and type(name) is not int:
                value = lst[name]
                if type(value) == float and value % 1 == 0.0:
                    value = int(value)
                string.append("{0}: {1}".format(name, value))
    return ", ".join(string)


def debugPrint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="tja2fumen {0}".format(tja2fumen_version)
    )
    parser.add_argument(
        "file_m.bin",
        help="Path to a Taiko no Tatsujin fumen file.",
        type=argparse.FileType("rb")
    )
    parser.add_argument(
        "offset",
        help="Note offset in seconds, negative values will make the notes appear later. Example: -1.9",
        nargs="?",
        type=float,
        default=0
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--big",
        help="Force big endian byte order for parsing.",
        action="store_const",
        dest="order",
        const="big"
    )
    group.add_argument(
        "--little",
        help="Force little endian byte order for parsing.",
        action="store_const",
        dest="order",
        const="little"
    )
    parser.add_argument(
        "-o",
        metavar="file.osu",
        help="Set the filename of the output file.",
        type=argparse.FileType("bw+")
    )
    parser.add_argument(
        "--title",
        metavar="\"Title\"",
        help="Set the title in the output file."
    )
    parser.add_argument(
        "--subtitle",
        metavar="\"Subtitle\"",
        help="Set the subtitle (artist field) in the output file.",
        default=""
    )
    parser.add_argument(
        "--wave",
        metavar="file.wav",
        help="Set the audio filename in the output file."
    )
    parser.add_argument(
        "--branch",
        metavar="master",
        help="Select a branch from a branched song ({0}).".format(", ".join(branchNames)),
        choices=branchNames
    )
    parser.add_argument(
        "-v", "--debug",
        help="Print verbose debug information.",
        action="store_true"
    )
    if len(sys.argv) == 1:
        parser.print_help()
    else:
        arguments = parser.parse_args()
        inputFile = getattr(arguments, "file_m.bin")
        parsedSong = readFumen(inputFile, arguments.order, arguments.debug)
        breakpoint()
