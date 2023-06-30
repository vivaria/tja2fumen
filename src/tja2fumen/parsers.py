import os
import re

from tja2fumen.utils import readStruct, getBool, shortHex
from tja2fumen.constants import (
    # TJA constants
    HEADER_GLOBAL, HEADER_COURSE, BRANCH_COMMANDS, MEASURE_COMMANDS, COMMAND, NORMALIZE_COURSE, TJA_NOTE_TYPES,
    # Fumen constants
    branchNames, noteTypes
)


########################################################################################################################
# TJA-parsing functions ( Original source: https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js)
########################################################################################################################


def parseTJA(fnameTJA):
    try:
        tja = open(fnameTJA, "r", encoding="utf-8-sig")
    except UnicodeDecodeError:
        tja = open(fnameTJA, "r", encoding="shift-jis")

    # Split into lines
    lines = tja.read().splitlines()
    lines = [line for line in lines if line.strip()]  # Discard empty lines

    # Line by line
    headers = {}
    courses = {}
    currentCourse = ''
    for line in lines:
        # Regex matches for various line types
        match_comment = re.match(r"//.*", line)
        match_header = re.match(r"^([A-Z]+):(.*)", line)
        match_command = re.match(r"^#([A-Z]+)(?:\s+(.+))?", line)
        match_data = re.match(r"^(([0-9]|A|B|C|F|G)*,?).*$", line)

        if match_comment:
            continue
        elif match_header:
            nameUpper = match_header.group(1).upper()
            value = match_header.group(2)
            if nameUpper in HEADER_GLOBAL:
                headers[nameUpper.lower()] = value.strip()
            elif nameUpper in HEADER_COURSE:
                parsed = {"type": 'header', "scope": 'course', "name": nameUpper, "value": value.strip()}
                if parsed['name'] == 'COURSE':
                    currentCourse = NORMALIZE_COURSE[parsed['value']]
                    if currentCourse not in courses.keys():
                        courses[currentCourse] = []
                courses[currentCourse].append(parsed)
        elif match_command:
            nameUpper = match_command.group(1).upper()
            value = match_command.group(2) if match_command.group(2) else ''
            if nameUpper in COMMAND:
                parsed = {"type": 'command', "name": nameUpper, "value": value.strip()}
                courses[currentCourse].append(parsed)
        elif match_data:
            parsed = {"type": 'data', "data": match_data.group(1)}
            courses[currentCourse].append(parsed)

    # Convert parsed course lines into actual note data
    songs = {}
    for courseName, courseLines in courses.items():
        courseHeader, courseMeasures = getCourse(headers, courseLines)
        tja = applyFumenStructureToParsedTJA(headers, courseHeader, courseMeasures)
        tja['measures'] = preprocessTJAMeasures(tja)
        songs[courseName] = tja

    return songs


def getCourse(tjaHeaders, lines):
    def parseHeaderMetadata(line):
        nonlocal headers
        if line["name"] == 'COURSE':
            headers['course'] = NORMALIZE_COURSE[line['value']]
        elif line["name"] == 'LEVEL':
            headers['level'] = int(line['value']) if line['value'] else 0
        elif line["name"] == 'SCOREINIT':
            headers['scoreInit'] = int(line['value']) if line['value'] else 0
        elif line["name"] == 'SCOREDIFF':
            headers['scoreDiff'] = int(line['value']) if line['value'] else 0
        elif line["name"] == 'BALLOON':
            if line['value']:
                balloons = [int(v) for v in line['value'].split(",") if v]
            else:
                balloons = []
            headers['balloon'] = balloons
        # STYLE is a P1/P2 command, which we don't support yet, so normally this would be a NotImplemetedError.
        # However, TakoTako outputs `STYLE:SINGLE` when converting Ura charts, so throwing an error here prevents
        # Ura charts from being converted. See: https://github.com/vivaria/tja2fumen/issues/15#issuecomment-1575341088
        elif line["name"] == 'STYLE':
            pass
        else:
            raise NotImplementedError

    def parseBranchCommands(line):
        nonlocal flagLevelhold, targetBranch, currentBranch
        if line["name"] == 'BRANCHSTART':
            if flagLevelhold:
                return
            values = line['value'].split(',')
            if values[0] == 'r':
                if len(values) >= 3:
                    targetBranch = 'M'
                elif len(values) == 2:
                    targetBranch = 'E'
                else:
                    targetBranch = 'N'
            elif values[0] == 'p':
                if len(values) >= 3 and float(values[2]) <= 100:
                    targetBranch = 'M'
                elif len(values) >= 2 and float(values[1]) <= 100:
                    targetBranch = 'E'
                else:
                    targetBranch = 'N'
        elif line["name"] == 'BRANCHEND':
            currentBranch = targetBranch
        elif line["name"] == 'N':
            currentBranch = 'N'
        elif line["name"] == 'E':
            currentBranch = 'E'
        elif line["name"] == 'M':
            currentBranch = 'M'
        elif line["name"] == 'START' or line['name'] == 'END':
            currentBranch = 'N'
            targetBranch = 'N'
            flagLevelhold = False
        elif line['name'] == 'SECTION':
            raise NotImplementedError
        else:
            raise NotImplementedError

    def parseMeasureCommands(line):
        nonlocal measureDivisor, measureDividend, measureEvents, flagLevelhold
        if line['name'] == 'MEASURE':
            matchMeasure = re.match(r"(\d+)/(\d+)", line['value'])
            if not matchMeasure:
                return
            measureDividend = int(matchMeasure.group(1))
            measureDivisor = int(matchMeasure.group(2))
        elif line['name'] == 'GOGOSTART':
            measureEvents.append({"name": 'gogo', "position": len(measureData), "value": '1'})
        elif line['name'] == 'GOGOEND':
            measureEvents.append({"name": 'gogo', "position": len(measureData), "value": '0'})
        elif line['name'] == 'BARLINEON':
            measureEvents.append({"name": 'barline', "position": len(measureData), "value": '1'})
        elif line['name'] == 'BARLINEOFF':
            measureEvents.append({"name": 'barline', "position": len(measureData), "value": '0'})
        elif line['name'] == 'SCROLL':
            measureEvents.append({"name": 'scroll', "position": len(measureData), "value": float(line['value'])})
        elif line['name'] == 'BPMCHANGE':
            measureEvents.append({"name": 'bpm', "position": len(measureData), "value": float(line['value'])})
        elif line['name'] == 'LEVELHOLD':
            flagLevelhold = True
        elif line['name'] == 'DELAY':
            raise NotImplementedError
        elif line['name'] == 'LYRIC':
            pass
        elif line['name'] == 'NEXTSONG':
            pass
        else:
            raise NotImplementedError

    def parseMeasureData(line):
        nonlocal measures, measureData, measureDividend, measureDivisor, measureEvents
        data = line['data']
        # If measure has ended, then append the measure and start anew
        if data.endswith(','):
            measureData += data[0:-1]
            measure = {
                "length": [measureDividend, measureDivisor],
                "data": measureData,
                "events": measureEvents,
            }
            measures.append(measure)
            measureData = ''
            measureEvents = []
        # Otherwise, keep tracking measureData
        else:
            measureData += data

    # Define state variables
    headers = {'balloon': []}  # Charters sometimes exclude `BALLOON` entirely if there are none
    measures = []
    measureDividend = 4
    measureDivisor = 4
    measureData = ''
    measureEvents = []
    currentBranch = 'N'
    targetBranch = 'N'
    flagLevelhold = False

    # Process course lines
    for line in lines:
        if line["type"] == 'header':
            parseHeaderMetadata(line)
        elif line["type"] == 'command' and line['name'] in BRANCH_COMMANDS:
            parseBranchCommands(line)
        elif line["type"] == 'command' and line['name'] in MEASURE_COMMANDS and currentBranch == targetBranch:
            parseMeasureCommands(line)
        elif line['type'] == 'data' and currentBranch == targetBranch:
            parseMeasureData(line)

    # Post-processing: Ensure the first measure has a BPM event
    if measures:
        firstBPMEventFound = False
        # Search for BPM event in the first measure
        for i in range(len(measures[0]['events'])):
            evt = measures[0]['events'][i]
            if evt['name'] == 'bpm' and evt['position'] == 0:
                firstBPMEventFound = True
        # If not present, insert a BPM event into the first measure using the global header metadata
        if not firstBPMEventFound:
            # noinspection PyTypeChecker
            measures[0]['events'].insert(0, {"name": 'bpm', "position": 0, "value": tjaHeaders['bpm']})

    # Post-processing: In case the file doesn't end on a "measure end" symbol (','), append whatever is left
    if measureData:
        measures.append({
            "length": [measureDividend, measureDivisor],
            "data": measureData,
            "events": measureEvents,
        })

    # Post-processing: Otherwise, if the file ends on a measure event (e.g. #GOGOEND), append any remaining events
    elif measureEvents:
        for event in measureEvents:
            event['position'] = len(measures[len(measures) - 1]['data'])
            # noinspection PyTypeChecker
            measures[len(measures) - 1]['events'].append(event)

    return headers, measures


def applyFumenStructureToParsedTJA(globalHeader, courseHeader, measures):
    """Merge song metadata, course metadata, and course data into a single fumen-like object."""
    song = {'measures': [], 'metadata': {}}

    for k, v in globalHeader.items():
        song['metadata'][k] = v

    for k, v in courseHeader.items():
        if k in ['scoreInit', 'scoreDiff']:
            song[k] = v
        else:
            song['metadata'][k] = v

    for i, measure in enumerate(measures):
        song['measures'].append(measure)

    return song


def preprocessTJAMeasures(tja):
    """
    Merge TJA 'data' and 'event' fields into a single measure property, and split
    measures into sub-measures whenever a mid-measure BPM change occurs.

    The TJA parser produces measure objects with two important properties:
      - 'data': Contains the note data (1: don, 2: ka, etc.) along with spacing (s)
      - 'events' Contains event commands such as MEASURE, BPMCHANGE, GOGOTIME, etc.

    However, notes and events can be intertwined within a single measure. So, it's
    not possible to process them separately; they must be considered as single sequence.

    A particular danger is BPM changes. TJA allows multiple BPMs within a single measure,
    but the fumen format permits one BPM per measure. So, a TJA measure must be split up
    if it has multiple BPM changes within a measure.

    In the future, this logic should probably be moved into the TJA parser itself.
    """
    currentBPM = 0
    currentScroll = 1.0
    currentGogo = False
    currentBarline = True

    measuresCorrected = []
    for measure in tja['measures']:
        # Step 1: Combine notes and events
        notes = [{'pos': i, 'type': 'note', 'value': TJA_NOTE_TYPES[note]}
                 for i, note in enumerate(measure['data']) if note != '0']
        events = [{'pos': e['position'], 'type': e['name'], 'value': e['value']}
                  for e in measure['events']]
        combined = []
        while notes or events:
            if events and notes:
                if notes[0]['pos'] >= events[0]['pos']:
                    combined.append(events.pop(0))
                else:
                    combined.append(notes.pop(0))
            elif events:
                combined.append(events.pop(0))
            elif notes:
                combined.append(notes.pop(0))

        # Step 2: Split measure into submeasure
        measure_cur = {'bpm': currentBPM, 'scroll': currentScroll, 'gogo': currentGogo, 'barline': currentBarline,
                       'subdivisions': len(measure['data']), 'pos_start': 0, 'pos_end': 0,
                       'time_sig': measure['length'], 'data': []}
        for data in combined:
            if data['type'] == 'note':
                measure_cur['data'].append(data)
                # Update the current measure's SCROLL/GOGO/BARLINE status.
                measure_cur['scroll'] = currentScroll
                measure_cur['gogo'] = currentGogo
                measure_cur['barline'] = currentBarline
                # NB: The reason we update the measure's SCROLL/GOGO/BARLINE during the "note" event is because of
                # an ordering problem for mid-measure BPMCHANGEs. For example, imagine the following two TJA charts:
                #   33                     11021020
                #   #GOGOEND               #BPMCHANGE 178
                #   #BPMCHANGE 107         #SCROLL 1.04
                #   33,                    1102,
                # In both examples, BPMCHANGE + one other command happen mid-measure. But, the ordering differs.
                # This is relevant because in fumen files, "BPMCHANGE" signals the start of a new sub-measure.
                # Yet, in both cases, we want the 2nd command to apply to the notes _after_ the BPMCHANGE.
                # So, we make sure to only apply SCROLL/GOGO/BARLINE changes once we actually encounter new notes.
            elif data['type'] == 'bpm':
                currentBPM = float(data['value'])
                # Case 1: BPM change at the start of a measure; just change BPM
                if data['pos'] == 0:
                    measure_cur['bpm'] = currentBPM
                # Case 2: BPM change mid-measure, so start a new sub-measure
                else:
                    measure_cur['pos_end'] = data['pos']
                    measuresCorrected.append(measure_cur)
                    measure_cur = {'bpm': currentBPM, 'scroll': currentScroll, 'gogo': currentGogo, 'barline': currentBarline,
                                   'subdivisions': len(measure['data']), 'pos_start': data['pos'], 'pos_end': 0,
                                   'time_sig': measure['length'], 'data': []}
            elif data['type'] == 'scroll':
                currentScroll = data['value']
            elif data['type'] == 'gogo':
                currentGogo = bool(int(data['value']))
            elif data['type'] == 'barline':
                currentBarline = bool(int(data['value']))
            else:
                print(f"Unexpected event type: {data['type']}")
        measure_cur['pos_end'] = len(measure['data'])
        measuresCorrected.append(measure_cur)

    return measuresCorrected


########################################################################################################################
# Fumen-parsing functions
########################################################################################################################

# Fumen format reverse engineering TODOs
# TODO: Figure out what drumroll bytes are (8 bytes after every drumroll)
#       NB: fumen2osu.py assumed these were padding bytes, but they're not!! They contain some sort of metadata.
# TODO: Figure out what the unknown Wii1, Wii4, and PS4 notes represent (just in case they're important somehow)


def readFumen(fumenFile, exclude_empty_measures=False):
    """
    Parse bytes of a fumen .bin file into nested measure, branch, and note dictionaries.

    For more information on any of the terms used in this function (e.g. scoreInit, scoreDiff),
    please refer to KatieFrog's excellent guide: https://gist.github.com/KatieFrogs/e000f406bbc70a12f3c34a07303eec8b
    """
    file = open(fumenFile, "rb")
    size = os.fstat(file.fileno()).st_size

    # Fetch the header bytes
    fumenHeader = file.read(512)

    # Determine:
    #   - The byte order (big or little endian)
    #   - The total number of measures from byte 0x200 (decimal 512)
    measuresBig = readStruct(file, order="", format_string=">I", seek=0x200)[0]
    measuresLittle = readStruct(file, order="", format_string="<I", seek=0x200)[0]
    if measuresBig < measuresLittle:
        order = ">"
        totalMeasures = measuresBig
    else:
        order = "<"
        totalMeasures = measuresLittle

    # Initialize the dict that will contain the chart information
    song = {'measures': []}
    song['headerPadding'] = fumenHeader[:432]
    song['headerMetadata'] = fumenHeader[-80:]
    song['order'] = order

    # I am unsure what byte this represents
    unknownMetadata = readStruct(file, order, format_string="I", seek=0x204)[0]
    song["unknownMetadata"] = unknownMetadata

    # Determine whether the song has branches from byte 0x1b0 (decimal 432)
    hasBranches = getBool(readStruct(file, order, format_string="B", seek=0x1b0)[0])
    song["branches"] = hasBranches

    # Start reading measure data from position 0x208 (decimal 520)
    file.seek(0x208)
    for measureNumber in range(totalMeasures):
        # Parse the measure data using the following `format_string`:
        #   "ffBBHiiiiiii" (12 format characters, 40 bytes per measure)
        #     - 'f': BPM              (represented by one float (4 bytes))
        #     - 'f': fumenOffset      (represented by one float (4 bytes))
        #     - 'B': gogo             (represented by one unsigned char (1 byte))
        #     - 'B': barline           (represented by one unsigned char (1 byte))
        #     - 'H': <padding>        (represented by one unsigned short (2 bytes))
        #     - 'iiiiii': branchInfo  (represented by six integers (24 bytes))
        #     - 'i': <padding>        (represented by one integer (4 bytes)
        measureStruct = readStruct(file, order, format_string="ffBBHiiiiiii")

        # Create the measure dictionary using the newly-parsed measure data
        measure = {}
        measure["bpm"] = measureStruct[0]
        measure["fumenOffset"] = measureStruct[1]
        # if measureNumber == 0:
        #     measure["offset"] = measure["fumenOffset"] + 240000 / measure["bpm"]
        # else:
        #     prev = song['measures'][measureNumber - 1]
        #     measure["offset"] = ((prev["offset"] + measure["fumenOffset"] + 240000) /
        #                          (measure["bpm"] - prev["fumenOffset"] - 240000 / prev["bpm"]))
        measure["gogo"] = getBool(measureStruct[2])
        measure["barline"] = getBool(measureStruct[3])
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

            # Iterate through each note in the measure (per branch)
            for noteNumber in range(totalNotes):
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
                    note['scoreDiff'] = noteStruct[5] // 4
                    if "scoreInit" not in song:
                        song["scoreInit"] = note['scoreInit']
                        song["scoreDiff"] = note['scoreDiff']
                if noteType == 0x6 or noteType == 0x9 or noteType == 0xa or noteType == 0xc:
                    # Drumroll and balloon duration in ms
                    note["duration"] = noteStruct[6]
                else:
                    note['duration'] = noteStruct[6]

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

    # NB: Official fumens often include empty measures as a way of inserting barlines for visual effect.
    #     But, TJA authors tend not to add these empty measures, because even without them, the song plays correctly.
    #     So, in tests, if we want to only compare the timing of the non-empty measures between an official fumen and
    #     a converted non-official TJA, then it's useful to  exclude the empty measures.
    if exclude_empty_measures:
        song['measures'] = [m for m in song['measures']
                            if m['normal']['length'] or m['advanced']['length'] or m['master']['length']]

    return song
