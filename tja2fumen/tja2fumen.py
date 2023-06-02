import os, sys, struct, argparse, io

fumen2osu_version = "v1.4"

branchNames = ("normal", "advanced", "master")

def readFumen(inputFile, byteOrder=None, debug=False):
    if type(inputFile) is str:
        file = open(inputFile, "rb")
    else:
        file = inputFile
    size = os.fstat(file.fileno()).st_size

    noteTypes = {
        0x1: "Don", # ドン
        0x2: "Don", # ド
        0x3: "Don", # コ
        0x4: "Ka", # カッ
        0x5: "Ka", # カ
        0x6: "Drumroll",
        0x7: "DON",
        0x8: "KA",
        0x9: "DRUMROLL",
        0xa: "Balloon",
        0xb: "DON", # hands
        0xc: "Kusudama",
        0xd: "KA", # hands
        0x62: "Drumroll" # ?
    }
    song = {}

    def readStruct(format, seek=None):
        if seek:
            file.seek(seek)
        return struct.unpack(order + format, file.read(struct.calcsize(order + format)))

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
            measure["offset"] = prev["offset"] + measure["fumenOffset"] + 240000 / measure["bpm"] - prev["fumenOffset"] - 240000 / prev["bpm"]
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

def writeOsu(song, globalOffset=0, title=None, subtitle="", wave=None, selectedBranch=None, outputFile=None, inputFile=None):
    if not song or len(song) == 0:
        return False

    if inputFile:
        if type(inputFile) is str:
            filename = inputFile
        else:
            filename = inputFile.name
        filenameNoExt = os.path.splitext(filename)[0]
        title = title or filenameNoExt
        wave = wave or "SONG_{0}.wav".format(
            filenameNoExt.split("_")[0].upper()
        )
        outputFile = outputFile or "{0}.osu".format(filenameNoExt)
    else:
        title = title or "Song Title"
        wave = wave or "song.wav"

    if song["branches"] == True:
        if selectedBranch not in branchNames:
            selectedBranch = branchNames[-1]
            debugPrint("Warning: Using the {0} branch in a branched song.".format(selectedBranch))
    else:
        selectedBranch = branchNames[0]

    osu = []
    osu.append(b"""osu file format v14

[General]""")
    osu.append(b"AudioFilename: " + bytes(wave, "utf8"))
    osu.append(b"""AudioLeadIn: 0
PreviewTime: 0
CountDown: 0
SampleSet: Normal
StackLeniency: 0.7
Mode: 1
LetterboxInBreaks: 0
WidescreenStoryboard: 0

[Editor]
DistanceSpacing: 0.8
BeatDivisor: 4
GridSize: 4
TimelineZoom: 1

[Metadata]""")
    osu.append(b"Title:" + bytes(title, "utf8"))
    osu.append(b"TitleUnicode:" + bytes(title, "utf8"))
    osu.append(b"Artist:" + bytes(subtitle, "utf8"))
    osu.append(b"ArtistUnicode:" + bytes(subtitle, "utf8"))
    osu.append(b"""Creator:
Version:
Source:
Tags:

[Difficulty]
HPDrainRate:3
CircleSize:5
OverallDifficulty:3
ApproachRate:5
SliderMultiplier:1.4
SliderTickRate:4

[TimingPoints]""")
    globalOffset = globalOffset * 1000.0
    for i in range(song["length"]):
        prevMeasure = song[i - 1] if i != 0 else None
        prevBranch = prevMeasure[selectedBranch] if i != 0 else None
        measure = song[i]
        branch = measure[selectedBranch]
        if i == 0 or prevMeasure["bpm"] != measure["bpm"] or prevMeasure["gogo"] != measure["gogo"] or prevBranch["speed"] != branch["speed"]:
            offset = measure["offset"] - globalOffset
            gogo = 1 if measure["gogo"] else 0
            if i == 0 or prevMeasure["bpm"] != measure["bpm"]:
                msPerBeat = 1000 / measure["bpm"] * 60
                osu.append(bytes("{0},{1},4,1,0,100,1,{2}".format(
                    int(offset),
                    msPerBeat,
                    gogo
                ), "ascii"))
            if branch["speed"] != 1 or i != 0 and (prevBranch["speed"] != branch["speed"] or prevMeasure["bpm"] == measure["bpm"]):
                msPerBeat = -100 / branch["speed"]
                osu.append(bytes("{0},{1},4,1,0,100,1,{2}".format(
                    int(offset),
                    msPerBeat,
                    gogo
                ), "ascii"))
    osu.append(b"""

[HitObjects]""")
    osuSounds = {
        "Don": 0,
        "Ka": 8,
        "DON": 4,
        "KA": 12,
        "Drumroll": 0,
        "DRUMROLL": 4,
        "Balloon": 0,
        "Kusudama": 0
    }
    for i in range(song["length"]):
        measure = song[i]
        branch = song[i][selectedBranch]
        for j in range(branch["length"]):
            note = branch[j]
            noteType = note["type"]
            offset = measure["offset"] + note["pos"] - globalOffset
            if noteType == "Don" or noteType == "Ka" or noteType == "DON" or noteType == "KA":
                sound = osuSounds[noteType]
                osu.append(bytes("416,176,{0},1,{1},0:0:0:0:".format(
                    int(offset),
                    sound
                ), "ascii"))
            elif noteType == "Drumroll" or noteType == "DRUMROLL":
                sound = osuSounds[noteType]
                velocity = 1.4 * branch["speed"] * 100 / (1000 / measure["bpm"] * 60)
                pixelLength = note["duration"] * velocity
                osu.append(bytes("416,176,{0},2,{1},L|696:176,1,{2},0|0,0:0|0:0,0:0:0:0:".format(
                    int(offset),
                    sound,
                    int(pixelLength)
                ), "ascii"))
            elif noteType == "Balloon" or noteType == "Kusudama":
                sound = osuSounds[noteType]
                endTime = offset + note["duration"]
                osu.append(bytes("416,176,{0},12,0,{1},0:0:0:0:".format(
                    int(offset),
                    int(endTime)
                ), "ascii"))
    osu.append(b"")
    osuContents = b"\n".join(osu)

    if outputFile:
        if type(outputFile) is str:
            file = open(outputFile, "bw+")
        else:
            file = outputFile
        if type(outputFile) is io.TextIOWrapper:
            osuContents = osuContents.decode("utf-8")
        try:
            file.write(osuContents)
        except UnicodeEncodeError as e:
            print(e)
        file.close()
        return True
    else:
        return osuContents

def shortHex(number):
    return hex(number)[2:]

def getBool(number):
    return True if number == 0x1 else False if number == 0x0 else number

def nameValue(*lists):
    string = []
    for list in lists:
        for name in list:
            if name == "type":
                string.append(list[name])
            elif name != "length" and type(name) is not int:
                value = list[name]
                if type(value) == float and value % 1 == 0.0:
                    value = int(value)
                string.append("{0}: {1}".format(name, value))
    return ", ".join(string)

def debugPrint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

if __name__=="__main__":
    parser = argparse.ArgumentParser(
        description="fumen2osu {0}".format(fumen2osu_version)
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
        args = parser.parse_args()
        inputFile = getattr(args, "file_m.bin")
        song = readFumen(inputFile, args.order, args.debug)
        writeOsu(song, args.offset, args.title, args.subtitle, args.wave, args.branch, args.o, inputFile)
