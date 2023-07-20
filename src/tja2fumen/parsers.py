import os
import re
from copy import deepcopy

from tja2fumen.utils import read_struct, short_hex
from tja2fumen.constants import NORMALIZE_COURSE, TJA_NOTE_TYPES, BRANCH_NAMES, FUMEN_NOTE_TYPES
from tja2fumen.types import (TJASong, TJAMeasure, TJAData,
                             FumenCourse, FumenMeasure, FumenBranch, FumenNote, FumenHeader)

########################################################################################################################
# TJA-parsing functions ( Original source: https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js)
########################################################################################################################


def parse_tja(fname_tja):
    try:
        tja_text = open(fname_tja, "r", encoding="utf-8-sig").read()
    except UnicodeDecodeError:
        tja_text = open(fname_tja, "r", encoding="shift-jis").read()

    lines = [line for line in tja_text.splitlines() if line.strip() != '']
    parsed_tja = get_course_data(lines)
    for course in parsed_tja.courses.values():
        parse_course_measures(course)

    return parsed_tja


def get_course_data(lines):
    parsed_tja = None
    current_course = ''
    current_course_cached = ''
    song_bpm = 0
    song_offset = 0

    for line in lines:
        # Case 1: Header metadata
        match_header = re.match(r"^([A-Z]+):(.*)", line)
        if match_header:
            name_upper = match_header.group(1).upper()
            value = match_header.group(2).strip()

            # Global header fields
            if name_upper in ['BPM', 'OFFSET']:
                if name_upper == 'BPM':
                    song_bpm = value
                elif name_upper == 'OFFSET':
                    song_offset = value
                if song_bpm and song_offset:
                    parsed_tja = TJASong(song_bpm, song_offset)

            # Course-specific header fields
            elif name_upper == 'COURSE':
                current_course = NORMALIZE_COURSE[value]
                current_course_cached = current_course
                if current_course not in parsed_tja.courses.keys():
                    raise ValueError()
            elif name_upper == 'LEVEL':
                parsed_tja.courses[current_course].level = int(value) if value else 0
            # NB: If there are multiple SCOREINIT/SCOREDIFF values, use the last one (shinuti)
            elif name_upper == 'SCOREINIT':
                parsed_tja.courses[current_course].score_init = int(value.split(",")[-1]) if value else 0
            elif name_upper == 'SCOREDIFF':
                parsed_tja.courses[current_course].score_diff = int(value.split(",")[-1]) if value else 0
            elif name_upper == 'BALLOON':
                if value:
                    balloons = [int(v) for v in value.split(",") if v]
                    parsed_tja.courses[current_course].balloon = balloons
            elif name_upper == 'STYLE':
                # Reset the course name to remove "P1/P2" that may have been added by a previous STYLE:DOUBLE chart
                if value == 'Single':
                    current_course = current_course_cached
            else:
                pass  # Ignore other header fields such as 'TITLE', 'SUBTITLE', 'WAVE', etc.

        # Case 2: Commands and note data (to be further processed course-by-course later on)
        elif not re.match(r"//.*", line):  # Exclude comment-only lines ('//')
            match_command = re.match(r"^#([A-Z]+)(?:\s+(.+))?", line)
            match_notes = re.match(r"^(([0-9]|A|B|C|F|G)*,?).*$", line)
            if match_command:
                name_upper = match_command.group(1).upper()
                value = match_command.group(2).strip() if match_command.group(2) else ''
                # For STYLE:Double, #START P1/P2 indicates the start of a new chart
                # But, we want multiplayer charts to inherit the metadata from the course as a whole, so we deepcopy
                if name_upper == "START":
                    if value in ["P1", "P2"]:
                        current_course = current_course_cached + value
                        parsed_tja.courses[current_course] = deepcopy(parsed_tja.courses[current_course_cached])
                        parsed_tja.courses[current_course].data = list()  # Keep the metadata, but reset the note data
                        value = ''  # Once we've made the new course, we can reset this to a normal #START command
                    elif value:
                        raise ValueError(f"Invalid value '{value}' for #START command.")
            elif match_notes:
                name_upper = 'NOTES'
                value = match_notes.group(1)
            parsed_tja.courses[current_course].data.append(TJAData(name_upper, value))
            
    # If a course has no song data, then this is likely because the course has "STYLE: Double" but no "STYLE: Single".
    # To fix this, we copy over the P1 chart from "STYLE: Double" to fill the "STYLE: Single" role.
    for course_name, course in parsed_tja.courses.items():
        if not course.data:
            if course_name+"P1" in parsed_tja.courses.keys():
                parsed_tja.courses[course_name] = deepcopy(parsed_tja.courses[course_name+"P1"])

    # Remove any charts (e.g. P1/P2) not present in the TJA file
    for course_name in [k for k, v in parsed_tja.courses.items() if not v.data]:
        del parsed_tja.courses[course_name]

    return parsed_tja


def parse_course_measures(course):
    # Check if the course has branches or not
    has_branches = True if [l for l in course.data if l.name == 'BRANCHSTART'] else False
    current_branch = 'all' if has_branches else 'normal'
    branch_condition = None
    flag_levelhold = False

    # Process course lines
    idx_m = 0
    idx_m_branchstart = 0
    for idx_l, line in enumerate(course.data):
        # 1. Parse measure notes
        if line.name == 'NOTES':
            notes = line.value
            # If measure has ended, then add notes to the current measure, then start a new one by incrementing idx_m
            if notes.endswith(','):
                for branch in course.branches.keys() if current_branch == 'all' else [current_branch]:
                    course.branches[branch][idx_m].notes += notes[0:-1]
                    course.branches[branch].append(TJAMeasure())
                idx_m += 1
            # Otherwise, keep adding notes to the current measure ('idx_m')
            else:
                for branch in course.branches.keys() if current_branch == 'all' else [current_branch]:
                    course.branches[branch][idx_m].notes += notes

        # 2. Parse measure commands that produce an "event"
        elif line.name in ['GOGOSTART', 'GOGOEND', 'BARLINEON', 'BARLINEOFF', 'DELAY',
                           'SCROLL', 'BPMCHANGE', 'MEASURE', 'SECTION', 'BRANCHSTART']:
            # Get position of the event
            for branch in course.branches.keys() if current_branch == 'all' else [current_branch]:
                pos = len(course.branches[branch][idx_m].notes)

            # Parse event type
            if line.name == 'GOGOSTART':
                current_event = TJAData('gogo', '1', pos)
            elif line.name == 'GOGOEND':
                current_event = TJAData('gogo', '0', pos)
            elif line.name == 'BARLINEON':
                current_event = TJAData('barline', '1', pos)
            elif line.name == 'BARLINEOFF':
                current_event = TJAData('barline', '0', pos)
            elif line.name == 'DELAY':
                current_event = TJAData('delay', float(line.value), pos)
            elif line.name == 'SCROLL':
                current_event = TJAData('scroll', float(line.value), pos)
            elif line.name == 'BPMCHANGE':
                current_event = TJAData('bpm', float(line.value), pos)
            elif line.name == 'MEASURE':
                current_event = TJAData('measure', line.value, pos)
            elif line.name == 'SECTION':
                if branch_condition is None:
                    current_event = TJAData('section', 'not_available', pos)
                else:
                    current_event = TJAData('section', branch_condition, pos)
                # If the command immediately after #SECTION is #BRANCHSTART, then we need to make sure that #SECTION
                # is put on every branch. (We can't do this unconditionally because #SECTION commands can also exist
                # in isolation in the middle of separate branches.)
                if course.data[idx_l+1].name == 'BRANCHSTART':
                    current_branch = 'all'
            elif line.name == 'BRANCHSTART':
                if flag_levelhold:
                    continue
                current_branch = 'all'  # Ensure that the #BRANCHSTART command is present for all branches
                branch_condition = line.value.split(',')
                if branch_condition[0] == 'r':  # r = drumRoll
                    branch_condition[1] = int(branch_condition[1])  # # of drumrolls
                    branch_condition[2] = int(branch_condition[2])  # # of drumrolls
                elif branch_condition[0] == 'p':  # p = Percentage
                    branch_condition[1] = float(branch_condition[1]) / 100  # %
                    branch_condition[2] = float(branch_condition[2]) / 100  # %
                current_event = TJAData('branch_start', branch_condition, pos)
                idx_m_branchstart = idx_m  # Preserve the index of the BRANCHSTART command to re-use for each branch

            # Append event to the current measure's events
            for branch in course.branches.keys() if current_branch == 'all' else [current_branch]:
                course.branches[branch][idx_m].events.append(current_event)

        # 3. Parse commands that don't create an event (e.g. simply changing the current branch)
        else:
            if line.name == 'START' or line.name == 'END':
                current_branch = 'all' if has_branches else 'normal'
                flag_levelhold = False
            elif line.name == 'LEVELHOLD':
                flag_levelhold = True
            elif line.name == 'N':
                current_branch = 'normal'
                idx_m = idx_m_branchstart
            elif line.name == 'E':
                current_branch = 'advanced'
                idx_m = idx_m_branchstart
            elif line.name == 'M':
                current_branch = 'master'
                idx_m = idx_m_branchstart
            elif line.name == 'BRANCHEND':
                current_branch = 'all'

            else:
                print(f"Ignoring unsupported command '{line.name}'")

    # Delete the last measure in the branch if no notes or events were added to it (due to preallocating empty measures)
    for branch in course.branches.values():
        if not branch[-1].notes and not branch[-1].events:
            del branch[-1]

    # Merge measure data and measure events in chronological order
    for branch_name, branch in course.branches.items():
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
    if has_branches:
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


def read_fumen(fumen_file, exclude_empty_measures=False):
    """
    Parse bytes of a fumen .bin file into nested measure, branch, and note dictionaries.

    For more information on any of the terms used in this function (e.g. score_init, score_diff),
    please refer to KatieFrog's excellent guide: https://gist.github.com/KatieFrogs/e000f406bbc70a12f3c34a07303eec8b
    """
    file = open(fumen_file, "rb")
    size = os.fstat(file.fileno()).st_size

    song = FumenCourse(
        header=FumenHeader(raw_bytes=file.read(520))
    )

    for measure_number in range(song.header.b512_b515_number_of_measures):
        # Parse the measure data using the following `format_string`:
        #   "ffBBHiiiiiii" (12 format characters, 40 bytes per measure)
        #     - 'f': BPM              (represented by one float (4 bytes))
        #     - 'f': fumenOffset      (represented by one float (4 bytes))
        #     - 'B': gogo             (represented by one unsigned char (1 byte))
        #     - 'B': barline           (represented by one unsigned char (1 byte))
        #     - 'H': <padding>        (represented by one unsigned short (2 bytes))
        #     - 'iiiiii': branch_info  (represented by six integers (24 bytes))
        #     - 'i': <padding>        (represented by one integer (4 bytes)
        measure_struct = read_struct(file, song.header.order, format_string="ffBBHiiiiiii")

        # Create the measure dictionary using the newly-parsed measure data
        measure = FumenMeasure(
            bpm=measure_struct[0],
            fumen_offset_start=measure_struct[1],
            gogo=measure_struct[2],
            barline=measure_struct[3],
            padding1=measure_struct[4],
            branch_info=list(measure_struct[5:11]),
            padding2=measure_struct[11]
        )

        # Iterate through the three branch types
        for branch_name in BRANCH_NAMES:
            # Parse the measure data using the following `format_string`:
            #   "HHf" (3 format characters, 8 bytes per branch)
            #     - 'H': total_notes (represented by one unsigned short (2 bytes))
            #     - 'H': <padding>  (represented by one unsigned short (2 bytes))
            #     - 'f': speed      (represented by one float (4 bytes)
            branch_struct = read_struct(file, song.header.order, format_string="HHf")

            # Create the branch dictionary using the newly-parsed branch data
            total_notes = branch_struct[0]
            branch = FumenBranch(
                length=total_notes,
                padding=branch_struct[1],
                speed=branch_struct[2],
            )

            # Iterate through each note in the measure (per branch)
            for note_number in range(total_notes):
                # Parse the note data using the following `format_string`:
                #   "ififHHf" (7 format characters, 24 bytes per note cluster)
                #     - 'i': note type
                #     - 'f': note position
                #     - 'i': item
                #     - 'f': <padding>
                #     - 'H': score_init
                #     - 'H': score_diff
                #     - 'f': duration
                # NB: 'item' doesn't seem to be used at all in this function.
                note_struct = read_struct(file, song.header.order, format_string="ififHHf")

                # Validate the note type
                note_type = note_struct[0]
                if note_type not in FUMEN_NOTE_TYPES:
                    raise ValueError("Error: Unknown note type '{0}' at offset {1}".format(
                        short_hex(note_type).upper(),
                        hex(file.tell() - 0x18))
                    )

                # Create the note dictionary using the newly-parsed note data
                note = FumenNote(
                    note_type=FUMEN_NOTE_TYPES[note_type],
                    pos=note_struct[1],
                    item=note_struct[2],
                    padding=note_struct[3],
                )

                if note_type == 0xa or note_type == 0xc:
                    # Balloon hits
                    note.hits = note_struct[4]
                    note.hits_padding = note_struct[5]
                else:
                    song.score_init = note.score_init = note_struct[4]
                    song.score_diff = note.score_diff = note_struct[5] // 4

                # Drumroll/balloon duration
                note.duration = note_struct[6]

                # Seek forward 8 bytes to account for padding bytes at the end of drumrolls
                if note_type == 0x6 or note_type == 0x9 or note_type == 0x62:
                    note.drumroll_bytes = file.read(8)

                # Assign the note to the branch
                branch.notes.append(note)

            # Assign the branch to the measure
            measure.branches[branch_name] = branch

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
