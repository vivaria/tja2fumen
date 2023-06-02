import os
import sys
import struct
import argparse
from copy import deepcopy
from parsetja import parseTJA

tja2fumen_version = "v0.1"

# Fumen format reverse engineering TODOs
# TODO: Figure out the remaining header bytes represent (0x1b0 to 0x207)
# TODO: Figure out what drumroll bytes are (8 bytes after every drumroll)
#       NB: fumen2osu.py assumed these were padding bytes, but they're not!! They contain some sort of metadata.
# TODO: Figure out what the unknown Wii1, Wii4, and PS4 notes represent (just in case they're important somehow)

branchNames = ("normal", "advanced", "master")

noteTypes = {
    0x1: "Don",   # ドン
    0x2: "Don2",  # ド
    0x3: "Don3",  # コ
    0x4: "Ka",    # カッ
    0x5: "Ka2",   # カ
    0x6: "Drumroll",
    0x7: "DON",
    0x8: "KA",
    0x9: "DRUMROLL",
    0xa: "Balloon",
    0xb: "DON2",        # hands
    0xc: "Kusudama",
    0xd: "KA2",         # hands
    0xe: "Unknown1",    # ? (Present in some Wii1 songs)
    0xf: "Unknown2",    # ? (Present in some PS4 songs)
    0x10: "Unknown3",   # ? (Present in some Wii1 songs)
    0x11: "Unknown4",   # ? (Present in some Wii1 songs)
    0x12: "Unknown5",   # ? (Present in some Wii4 songs)
    0x13: "Unknown6",   # ? (Present in some Wii1 songs)
    0x14: "Unknown7",   # ? (Present in some PS4 songs)
    0x15: "Unknown8",   # ? (Present in some Wii1 songs)
    0x16: "Unknown9",   # ? (Present in some Wii1 songs)
    0x17: "Unknown10",  # ? (Present in some Wii4 songs)
    0x18: "Unknown11",  # ? (Present in some PS4 songs)
    0x19: "Unknown12",  # ? (Present in some PS4 songs)
    0x22: "Unknown13",  # ? (Present in some Wii1 songs)
    0x62: "Drumroll2"   # ?
}
typeNotes = {v: k for k, v in noteTypes.items()}

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
    # Read the next 80 bytes, which contains unknown information
    fumenHeaderUnknown = file.read(80)

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
    unknownMetadata = readStruct(file, order, format_string="I", seek=0x204)[0]

    # Initialize the dict that will contain the chart information
    song = { 'measures': [] }
    song['header'] = fumenHeader
    song['headerUnknown'] = fumenHeaderUnknown
    song['order'] = order
    song["length"] = totalMeasures
    song["unknownMetadata"] = unknownMetadata

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
            prev = song['measures'][measureNumber - 1]
            measure["offset"] = ((prev["offset"] + measure["fumenOffset"] + 240000) /
                                 (measure["bpm"] - prev["fumenOffset"] - 240000 / prev["bpm"]))
        measure["gogo"] = getBool(measureStruct[2])
        measure["hidden"] = getBool(measureStruct[3])
        measure["padding1"] = measureStruct[4]
        measure["branchInfo"] = list(measureStruct[5:11])
        measure["padding2"] = measureStruct[11]

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
            branch["padding"] = branchStruct[1]
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
                note["item"] = noteStruct[2]
                note["padding"] = noteStruct[3]
                if noteType == 0xa or noteType == 0xc:
                    # Balloon hits
                    note["hits"] = noteStruct[4]
                    note["hitsPadding"] = noteStruct[5]
                else:
                    note['scoreInit'] = noteStruct[4]
                    note['scoreDiff'] = noteStruct[5] / 4.0
                    if "scoreInit" not in song:
                        song["scoreInit"] = note['scoreInit']
                        song["scoreDiff"] = note['scoreDiff']
                if noteType == 0x6 or noteType == 0x9 or noteType == 0xa or noteType == 0xc:
                    # Drumroll and balloon duration in ms
                    note["duration"] = noteStruct[6]
                else:
                    note['durationPadding'] = noteStruct[6]

                # Print debug information about the note
                if debug:
                    debugPrint(" ({0})".format(nameValue(note)))

                # Seek forward 8 bytes to account for padding bytes at the end of drumrolls
                if noteType == 0x6 or noteType == 0x9 or noteType == 0x62:
                    note["drumrollBytes"] = file.read(8)

                # Assign the note to the branch
                branch[noteNumber] = note

            # Assign the branch to the measure
            measure[branchNames[branchNumber]] = branch

        # Assign the measure to the song
        song['measures'].append(measure)
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
    expected_size = struct.calcsize(order + format_string)
    byte_string = file.read(expected_size)
    # One "official" fumen (AC11\deo\deo_n.bin) runs out of data early
    # This workaround fixes the issue by appending 0's to get the size to match
    if len(byte_string) != expected_size:
        byte_string += (b'\x00' * (expected_size - len(byte_string)))
    interpreted_string = struct.unpack(order + format_string, byte_string)
    return interpreted_string


def writeFumen(file, song):
    # Fetch the byte order (little/big endian)
    order = song['order']

    # Write the header
    file.write(simpleHeaders[0])       # Write known, valid header
    file.write(song['headerUnknown'])  # Write unknown header

    # Preallocate space in the file
    len_metadata = 8
    len_measures = 0
    for measureNumber in range(song['length']):
        len_measures += 40
        measure = song['measures'][measureNumber]
        for branchNumber in range(len(branchNames)):
            len_measures += 8
            branch = measure[branchNames[branchNumber]]
            for noteNumber in range(branch['length']):
                len_measures += 24
                note = branch[noteNumber]
                if note['type'].lower() == "drumroll":
                    len_measures += 8
    file.write(b'\x00' * (len_metadata + len_measures))

    # Write metadata
    writeStruct(file, order, format_string="B", value_list=[putBool(song['branches'])], seek=0x1b0)
    writeStruct(file, order, format_string="I", value_list=[song['length']], seek=0x200)
    writeStruct(file, order, format_string="I", value_list=[song['unknownMetadata']], seek=0x204)

    # Write measure data
    file.seek(0x208)
    for measureNumber in range(song['length']):
        measure = song['measures'][measureNumber]
        measureStruct = [measure['bpm'], measure['fumenOffset'], int(measure['gogo']), int(measure['hidden'])]
        measureStruct.extend([measure['padding1']] + measure['branchInfo'] + [measure['padding2']])
        writeStruct(file, order, format_string="ffBBHiiiiiii", value_list=measureStruct)

        for branchNumber in range(len(branchNames)):
            branch = measure[branchNames[branchNumber]]
            branchStruct = [branch['length'], branch['padding'], branch['speed']]
            writeStruct(file, order, format_string="HHf", value_list=branchStruct)

            for noteNumber in range(branch['length']):
                note = branch[noteNumber]
                noteStruct = [typeNotes[note['type']], note['pos'], note['item'], note['padding']]
                # Balloon hits
                if 'hits' in note.keys():
                    noteStruct.extend([note["hits"], note['hitsPadding']])
                else:
                    noteStruct.extend([note['scoreInit'], int(note['scoreDiff'] * 4)])
                # Drumroll or balloon duration
                if 'duration' in note.keys():
                    noteStruct.append(note['duration'])
                else:
                    noteStruct.append(note['durationPadding'])
                writeStruct(file, order, format_string="ififHHf", value_list=noteStruct)
                if note['type'].lower() == "drumroll":
                    file.write(note['drumrollBytes'])
    file.close()


def writeStruct(file, order, format_string, value_list, seek=None):
    if seek:
        file.seek(seek)
    packed_bytes = struct.pack(order + format_string, *value_list)
    file.write(packed_bytes)


def shortHex(number):
    return hex(number)[2:]


def getBool(number):
    return True if number == 0x1 else False if number == 0x0 else number


def putBool(boolean):
    return 0x1 if boolean is True else 0x0 if boolean is False else boolean


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


def checkMismatchedBytes(file1, file2):
    with open(file1, 'rb') as file1, open(file2, 'rb') as file2:
        data1, data2 = file1.read(), file2.read()
    incorrect_bytes = {}
    # Ignore header (first 432 + 80 = 512 bytes)
    for i, (byte1, byte2) in enumerate(zip(data1[512:], data2[512:])):
        if byte1 == byte2:
            pass
        else:
            incorrect_bytes[hex(i+512)] = [byte1, byte2]
    return incorrect_bytes


TJA_NOTE_TYPES = {
    '1': 'Don',
    '2': 'Ka',
    '3': 'DON',
    '4': 'KA',
    '5': 'Drumroll',
    '6': 'DRUMROLL',
    '7': 'Balloon',
    '8': 'EndDRB',
    '9': 'Kusudama',
    'A': 'DON',  # hands
    'B': 'KA',   # hands
}

# Filler metadata that the `writeFumen` function expects
default_note = {'type': '', 'pos': 0.0, 'item': 0, 'padding': 0.0,
                'scoreInit': 0, 'scoreDiff': 0, 'durationPadding': 0.0}
default_branch = {'length': 0, 'padding': 0, 'speed': 1.0}
default_measure = {
    'bpm': 0.0,
    'fumenOffset': 0.0,
    'gogo': False,
    'hidden': False,
    'padding1': 0,
    'branchInfo': [-1, -1, -1, -1, -1, -1],
    'padding2': 0,
    'normal': deepcopy(default_branch),
    'advanced': deepcopy(default_branch),
    'master': deepcopy(default_branch)
}


def convertTJAToFumen(fumen, tja):
    # Fumen offset for the first measure that has a barline
    fumenOffset1 = float(tja['metadata']['offset']) * -1000

    # Variables that will change over time due to events
    currentBPM = 0.0
    currentGogo = False
    currentHidden = False
    currentBranch = 'normal'  # TODO: Program in branch support

    # Parse TJA measures to create converted TJA -> Fumen file
    tjaConverted = { 'measures': [] }
    for i, measureTJA in enumerate(tja['measures']):
        measureFumenExample = fumen['measures'][i+9]
        measureFumen = deepcopy(default_measure)

        # TODO Event: GOGOTIME

        # TODO Event: HIDDEN

        # TODO Event: BARLINE

        # TODO Event: MEASURE

        # Event: BPMCHANGE
        # TODO: Handle TJA measure being broken up into multiple Fumen measures due to mid-measure BPM changes
        midMeasureBPM = [(0, currentBPM)]
        for event in measureTJA['events']:
            if event['name'] == 'bpm':
                currentBPM = float(event['value'])
                if event['position'] == 0:
                    midMeasureBPM[0] = (0, currentBPM,)
                else:
                    midMeasureBPM.append((event['position'], currentBPM))
        if len(midMeasureBPM) > 1:
            test = None
        measureFumen['bpm'] = currentBPM

        # TODO: `measureFumen['fumenOffset']
        #       Will need to account for BARLINEON and BARLINEOFF.
        #       Some examples that line up with actual fumen data:
        # fumenOffset0 = (fumenOffset1 - measureLength)
        # fumenOffset2 = (fumenOffset1 + measureLength)
        measureLength = 240_000 / currentBPM
        # measureFumen['fumenOffset'] = prev['fumenOffset'] + measureLength

        # Create note dictionaries based on TJA measure data (containing 0's plus 1/2/3/4/etc. for notes)
        note_counter = 0
        for i, note_value in enumerate(measureTJA['data']):
            if note_value != '0':
                note = deepcopy(default_note)
                note['pos'] = measureLength * (i / len(measureTJA['data']))
                note['type'] = TJA_NOTE_TYPES[note_value]  # TODO: Handle BALLOON/DRUMROLL
                note['scoreInit'] = tja['scoreInit']  # Probably not fully accurate
                note['scoreDiff'] = tja['scoreDiff']  # Probably not fully accurate
                measureFumen[currentBranch][note_counter] = note
                note_counter += 1
        measureFumen[currentBranch]['length'] = note_counter

        # Append the measure to the tja's list of measures
        tjaConverted['measures'].append(measureFumen)

    tjaConverted['headerUnknown'] = b'x\00' * 80
    tjaConverted['order'] = '<'
    tjaConverted['length'] = len(tjaConverted['measures'])
    tjaConverted['unknownMetadata'] = 0
    tjaConverted['branches'] = False

    return tjaConverted


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
        # arguments = parser.parse_args()
        arguments = {
            "input_fumen": "./roku/ia6cho_m.bin",                        # NB: Contains only oni chart
            "input_tja": "./roku/Rokuchounen to Ichiya Monogatari.tja",  # NB: Contains 5 charts
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
        # writeFumen(outputFile, convertedTJA)
