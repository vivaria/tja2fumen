import os
import re
from copy import deepcopy

from tja2fumen.utils import readStruct, shortHex
from tja2fumen.constants import NORMALIZE_COURSE, TJA_NOTE_TYPES, branchNames, noteTypes
from tja2fumen.types import (TJASong, TJAMeasure, TJAData,
                             FumenCourse, FumenMeasure, FumenBranch, FumenNote, FumenHeader)

########################################################################################################################
# TJA-parsing functions ( Original source: https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js)
########################################################################################################################


def parseTJA(fnameTJA):
    try:
        tja_text = open(fnameTJA, "r", encoding="utf-8-sig").read()
    except UnicodeDecodeError:
        tja_text = open(fnameTJA, "r", encoding="shift-jis").read()

    lines = [line for line in tja_text.splitlines() if line.strip() != '']
    parsedTJA = getCourseData(lines)
    for course in parsedTJA.courses.values():
        parseCourseMeasures(course)

    return parsedTJA


def getCourseData(lines):
    parsedTJA = None
    currentCourse = ''
    currentCourseCached = ''
    songBPM = 0
    songOffset = 0

    for line in lines:
        # Case 1: Header metadata
        match_header = re.match(r"^([A-Z]+):(.*)", line)
        if match_header:
            nameUpper = match_header.group(1).upper()
            value = match_header.group(2).strip()

            # Global header fields
            if nameUpper in ['BPM', 'OFFSET']:
                if nameUpper == 'BPM':
                    songBPM = value
                elif nameUpper == 'OFFSET':
                    songOffset = value
                if songBPM and songOffset:
                    parsedTJA = TJASong(songBPM, songOffset)

            # Course-specific header fields
            elif nameUpper == 'COURSE':
                currentCourse = NORMALIZE_COURSE[value]
                currentCourseCached = currentCourse
                if currentCourse not in parsedTJA.courses.keys():
                    raise ValueError()
            elif nameUpper == 'LEVEL':
                parsedTJA.courses[currentCourse].level = int(value) if value else 0
            # NB: If there are multiple SCOREINIT/SCOREDIFF values, use the last one (shinuti)
            elif nameUpper == 'SCOREINIT':
                parsedTJA.courses[currentCourse].scoreInit = int(value.split(",")[-1]) if value else 0
            elif nameUpper == 'SCOREDIFF':
                parsedTJA.courses[currentCourse].scoreDiff = int(value.split(",")[-1]) if value else 0
            elif nameUpper == 'BALLOON':
                if value:
                    balloons = [int(v) for v in value.split(",") if v]
                    parsedTJA.courses[currentCourse].balloon = balloons
            elif nameUpper == 'STYLE':
                # Reset the course name to remove "P1/P2" that may have been added by a previous STYLE:DOUBLE chart
                if value == 'Single':
                    currentCourse = currentCourseCached
            else:
                pass  # Ignore other header fields such as 'TITLE', 'SUBTITLE', 'WAVE', etc.

        # Case 2: Commands and note data (to be further processed course-by-course later on)
        elif not re.match(r"//.*", line):  # Exclude comment-only lines ('//')
            match_command = re.match(r"^#([A-Z]+)(?:\s+(.+))?", line)
            match_notes = re.match(r"^(([0-9]|A|B|C|F|G)*,?).*$", line)
            if match_command:
                nameUpper = match_command.group(1).upper()
                value = match_command.group(2).strip() if match_command.group(2) else ''
                # For STYLE:Double, #START P1/P2 indicates the start of a new chart
                # But, we want multiplayer charts to inherit the metadata from the course as a whole, so we deepcopy
                if nameUpper == "START":
                    if value in ["P1", "P2"]:
                        currentCourse = currentCourseCached + value
                        parsedTJA.courses[currentCourse] = deepcopy(parsedTJA.courses[currentCourseCached])
                        parsedTJA.courses[currentCourse].data = list()  # Keep the metadata, but reset the note data
                        value = ''  # Once we've made the new course, we can reset this to a normal #START command
                    elif value:
                        raise ValueError(f"Invalid value '{value}' for #START command.")
            elif match_notes:
                nameUpper = 'NOTES'
                value = match_notes.group(1)
            parsedTJA.courses[currentCourse].data.append(TJAData(nameUpper, value))
            
    # If a course has no song data, then this is likely because the course has "STYLE: Double" but no "STYLE: Single".
    # To fix this, we copy over the P1 chart from "STYLE: Double" to fill the "STYLE: Single" role.
    for courseName, course in parsedTJA.courses.items():
        if not course.data:
            if courseName+"P1" in parsedTJA.courses.keys():
                parsedTJA.courses[courseName] = deepcopy(parsedTJA.courses[courseName+"P1"])

    # Remove any charts (e.g. P1/P2) not present in the TJA file
    for course_name in [k for k, v in parsedTJA.courses.items() if not v.data]:
        del parsedTJA.courses[course_name]

    return parsedTJA


def parseCourseMeasures(course):
    # Check if the course has branches or not
    hasBranches = True if [l for l in course.data if l.name == 'BRANCHSTART'] else False
    currentBranch = 'all' if hasBranches else 'normal'
    branch_condition = None
    flagLevelhold = False

    # Process course lines
    idx_m = 0
    idx_m_branchstart = 0
    for idx_l, line in enumerate(course.data):
        # 1. Parse measure notes
        if line.name == 'NOTES':
            notes = line.value
            # If measure has ended, then add notes to the current measure, then start a new one by incrementing idx_m
            if notes.endswith(','):
                for branch in course.branches.keys() if currentBranch == 'all' else [currentBranch]:
                    course.branches[branch][idx_m].notes += notes[0:-1]
                    course.branches[branch].append(TJAMeasure())
                idx_m += 1
            # Otherwise, keep adding notes to the current measure ('idx_m')
            else:
                for branch in course.branches.keys() if currentBranch == 'all' else [currentBranch]:
                    course.branches[branch][idx_m].notes += notes

        # 2. Parse measure commands that produce an "event"
        elif line.name in ['GOGOSTART', 'GOGOEND', 'BARLINEON', 'BARLINEOFF', 'DELAY',
                           'SCROLL', 'BPMCHANGE', 'MEASURE', 'SECTION', 'BRANCHSTART']:
            # Get position of the event
            for branch in course.branches.keys() if currentBranch == 'all' else [currentBranch]:
                pos = len(course.branches[branch][idx_m].notes)

            # Parse event type
            if line.name == 'GOGOSTART':
                currentEvent = TJAData('gogo', '1', pos)
            elif line.name == 'GOGOEND':
                currentEvent = TJAData('gogo', '0', pos)
            elif line.name == 'BARLINEON':
                currentEvent = TJAData('barline', '1', pos)
            elif line.name == 'BARLINEOFF':
                currentEvent = TJAData('barline', '0', pos)
            elif line.name == 'DELAY':
                currentEvent = TJAData('delay', float(line.value), pos)
            elif line.name == 'SCROLL':
                currentEvent = TJAData('scroll', float(line.value), pos)
            elif line.name == 'BPMCHANGE':
                currentEvent = TJAData('bpm', float(line.value), pos)
            elif line.name == 'MEASURE':
                currentEvent = TJAData('measure', line.value, pos)
            elif line.name == 'SECTION':
                if branch_condition is None:
                    currentEvent = TJAData('section', 'not_available', pos)
                else:
                    currentEvent = TJAData('section', branch_condition, pos)
                # If the command immediately after #SECTION is #BRANCHSTART, then we need to make sure that #SECTION
                # is put on every branch. (We can't do this unconditionally because #SECTION commands can also exist
                # in isolation in the middle of separate branches.)
                if course.data[idx_l+1].name == 'BRANCHSTART':
                    currentBranch = 'all'
            elif line.name == 'BRANCHSTART':
                if flagLevelhold:
                    continue
                currentBranch = 'all'  # Ensure that the #BRANCHSTART command is present for all branches
                branch_condition = line.value.split(',')
                if branch_condition[0] == 'r':  # r = drumRoll
                    branch_condition[1] = int(branch_condition[1])  # # of drumrolls
                    branch_condition[2] = int(branch_condition[2])  # # of drumrolls
                elif branch_condition[0] == 'p':  # p = Percentage
                    branch_condition[1] = float(branch_condition[1]) / 100  # %
                    branch_condition[2] = float(branch_condition[2]) / 100  # %
                currentEvent = TJAData('branchStart', branch_condition, pos)
                idx_m_branchstart = idx_m  # Preserve the index of the BRANCHSTART command to re-use for each branch

            # Append event to the current measure's events
            for branch in course.branches.keys() if currentBranch == 'all' else [currentBranch]:
                course.branches[branch][idx_m].events.append(currentEvent)

        # 3. Parse commands that don't create an event (e.g. simply changing the current branch)
        else:
            if line.name == 'START' or line.name == 'END':
                currentBranch = 'all' if hasBranches else 'normal'
                flagLevelhold = False
            elif line.name == 'LEVELHOLD':
                flagLevelhold = True
            elif line.name == 'N':
                currentBranch = 'normal'
                idx_m = idx_m_branchstart
            elif line.name == 'E':
                currentBranch = 'advanced'
                idx_m = idx_m_branchstart
            elif line.name == 'M':
                currentBranch = 'master'
                idx_m = idx_m_branchstart
            elif line.name == 'BRANCHEND':
                currentBranch = 'all'

            else:
                print(f"Ignoring unsupported command '{line.name}'")

    # Delete the last measure in the branch if no notes or events were added to it (due to preallocating empty measures)
    for branch in course.branches.values():
        if not branch[-1].notes and not branch[-1].events:
            del branch[-1]

    # Merge measure data and measure events in chronological order
    for branchName, branch in course.branches.items():
        for measure in branch:
            notes = [TJAData('note', TJA_NOTE_TYPES[note], i)
                     for i, note in enumerate(measure.notes) if note != '0']
            events = measure.events
            while notes or events:
                if events and notes:
                    if notes[0].pos >= events[0].pos:
                        measure.combined.append(events.pop(0))
                    else:
                        measure.combined.append(notes.pop(0))
                elif events:
                    measure.combined.append(events.pop(0))
                elif notes:
                    measure.combined.append(notes.pop(0))

    # Ensure all branches have the same number of measures
    if hasBranches:
        branch_lens = [len(b) for b in course.branches.values()]
        if not branch_lens.count(branch_lens[0]) == len(branch_lens):
            raise ValueError("Branches do not have the same number of measures.")


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

    song = FumenCourse(
        header=FumenHeader(raw_bytes=file.read(520))
    )

    for measureNumber in range(song.header.b512_b515_number_of_measures):
        # Parse the measure data using the following `format_string`:
        #   "ffBBHiiiiiii" (12 format characters, 40 bytes per measure)
        #     - 'f': BPM              (represented by one float (4 bytes))
        #     - 'f': fumenOffset      (represented by one float (4 bytes))
        #     - 'B': gogo             (represented by one unsigned char (1 byte))
        #     - 'B': barline           (represented by one unsigned char (1 byte))
        #     - 'H': <padding>        (represented by one unsigned short (2 bytes))
        #     - 'iiiiii': branchInfo  (represented by six integers (24 bytes))
        #     - 'i': <padding>        (represented by one integer (4 bytes)
        measureStruct = readStruct(file, song.header.order, format_string="ffBBHiiiiiii")

        # Create the measure dictionary using the newly-parsed measure data
        measure = FumenMeasure(
            bpm=measureStruct[0],
            fumenOffsetStart=measureStruct[1],
            gogo=measureStruct[2],
            barline=measureStruct[3],
            padding1=measureStruct[4],
            branchInfo=list(measureStruct[5:11]),
            padding2=measureStruct[11]
        )

        # Iterate through the three branch types
        for branchName in branchNames:
            # Parse the measure data using the following `format_string`:
            #   "HHf" (3 format characters, 8 bytes per branch)
            #     - 'H': totalNotes (represented by one unsigned short (2 bytes))
            #     - 'H': <padding>  (represented by one unsigned short (2 bytes))
            #     - 'f': speed      (represented by one float (4 bytes)
            branchStruct = readStruct(file, song.header.order, format_string="HHf")

            # Create the branch dictionary using the newly-parsed branch data
            totalNotes = branchStruct[0]
            branch = FumenBranch(
                length=totalNotes,
                padding=branchStruct[1],
                speed=branchStruct[2],
            )

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
                noteStruct = readStruct(file, song.header.order, format_string="ififHHf")

                # Validate the note type
                noteType = noteStruct[0]
                if noteType not in noteTypes:
                    raise ValueError("Error: Unknown note type '{0}' at offset {1}".format(
                        shortHex(noteType).upper(),
                        hex(file.tell() - 0x18))
                    )

                # Create the note dictionary using the newly-parsed note data
                note = FumenNote(
                    note_type=noteTypes[noteType],
                    pos=noteStruct[1],
                    item=noteStruct[2],
                    padding=noteStruct[3],
                )

                if noteType == 0xa or noteType == 0xc:
                    # Balloon hits
                    note.hits = noteStruct[4]
                    note.hitsPadding = noteStruct[5]
                else:
                    song.scoreInit = note.scoreInit = noteStruct[4]
                    song.scoreDiff = note.scoreDiff = noteStruct[5] // 4

                # Drumroll/balloon duration
                note.duration = noteStruct[6]

                # Seek forward 8 bytes to account for padding bytes at the end of drumrolls
                if noteType == 0x6 or noteType == 0x9 or noteType == 0x62:
                    note.drumrollBytes = file.read(8)

                # Assign the note to the branch
                branch.notes.append(note)

            # Assign the branch to the measure
            measure.branches[branchName] = branch

        # Assign the measure to the song
        song.measures.append(measure)
        if file.tell() >= size:
            break

    file.close()

    # NB: Official fumens often include empty measures as a way of inserting barlines for visual effect.
    #     But, TJA authors tend not to add these empty measures, because even without them, the song plays correctly.
    #     So, in tests, if we want to only compare the timing of the non-empty measures between an official fumen and
    #     a converted non-official TJA, then it's useful to  exclude the empty measures.
    if exclude_empty_measures:
        song.measures = [m for m in song.measures
                         if m.branches['normal'].length or m.branches['advanced'].length or m.branches['master'].length]

    return song
