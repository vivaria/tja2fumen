import os
import sys
import struct
import argparse

tja2fumen_version = "v0.1"

branchNames = ("normal", "advanced", "master")


def readFumen(fumenFile, byteOrder=None, debug=False):
    if type(fumenFile) is str:
        file = open(fumenFile, "rb")
    else:
        file = fumenFile
    size = os.fstat(file.fileno()).st_size

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
    song = {}

    def readStruct(fmt, seek=None):
        if seek:
            file.seek(seek)
        return struct.unpack(order + fmt, file.read(struct.calcsize(order + fmt)))

    if byteOrder:
        order = ">" if byteOrder == "big" else "<"
        totalMeasures = readStruct("I", 0x200)[0]
    else:
        order = ""
        measuresBig = readStruct(">I", 0x200)[0]
        measuresLittle = readStruct("<I", 0x200)[0]
        if measuresBig < measuresLittle:
            order = ">"
            totalMeasures = measuresBig
        else:
            order = "<"
            totalMeasures = measuresLittle

    hasBranches = getBool(readStruct("B", 0x1b0)[0])
    song["branches"] = hasBranches
    if debug:
        debugPrint("Total measures: {0}, {1} branches, {2}-endian".format(
            totalMeasures,
            "has" if hasBranches else "no",
            "Big" if order == ">" else "Little"
        ))

    file.seek(0x208)
    for measureNumber in range(totalMeasures):
        measure = {}
        # measureStruct: bpm 4, offset 4, gogo 1, hidden 1, dummy 2, branchInfo 4 * 6, dummy 4
        measureStruct = readStruct("ffBBHiiiiiii")
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

        for branchNumber in range(3):
            branch = {}
            # branchStruct: totalNotes 2, dummy 2, speed 4
            branchStruct = readStruct("HHf")
            totalNotes = branchStruct[0]
            branch["speed"] = branchStruct[2]

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

            for noteNumber in range(totalNotes):
                if debug:
                    fileOffset = file.tell()
                    debugPrint("Note #{0} at {1}-{2}".format(
                        noteNumber + 1,
                        shortHex(fileOffset),
                        shortHex(fileOffset + 0x17)
                    ), end="")

                note = {}
                # noteStruct: type 4, pos 4, item 4, dummy 4, init 2, diff 2, duration 4
                noteStruct = readStruct("ififHHf")
                noteType = noteStruct[0]

                if noteType not in noteTypes:
                    if debug:
                        debugPrint("")
                    debugPrint("Error: Unknown note type '{0}' at offset {1}".format(
                        shortHex(noteType).upper(),
                        hex(file.tell() - 0x18))
                    )
                    return False

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
                branch[noteNumber] = note

                if debug:
                    debugPrint(" ({0})".format(nameValue(note)))

                if noteType == 0x6 or noteType == 0x9 or noteType == 0x62:
                    # Drumrolls have 8 dummy bytes at the end
                    file.seek(0x8, os.SEEK_CUR)

            branch["length"] = totalNotes
            measure[branchNames[branchNumber]] = branch

        song[measureNumber] = measure
        if file.tell() >= size:
            break

    song["length"] = totalMeasures

    file.close()
    return song


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
