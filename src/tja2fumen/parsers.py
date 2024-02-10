"""
Functions for parsing TJA files (.tja) and Fumen files (.bin)
"""

import os
import re
import struct
import warnings
from copy import deepcopy
from typing import BinaryIO, Any, List, Dict, Tuple

from tja2fumen.classes import (TJASong, TJACourse, TJAMeasure, TJAData,
                               FumenCourse, FumenMeasure, FumenBranch,
                               FumenNote, FumenHeader)
from tja2fumen.constants import (NORMALIZE_COURSE, COURSE_NAMES, BRANCH_NAMES,
                                 TJA_COURSE_NAMES, TJA_NOTE_TYPES,
                                 FUMEN_NOTE_TYPES)

###############################################################################
#                          TJA-parsing functions                              #
###############################################################################


def parse_tja(fname_tja: str) -> TJASong:
    """Read in lines of a .tja file and load them into a TJASong object."""
    try:
        with open(fname_tja, "r", encoding="utf-8-sig") as tja_file:
            tja_text = tja_file.read()
    except UnicodeDecodeError:
        with open(fname_tja, "r", encoding="shift-jis") as tja_file:
            tja_text = tja_file.read()

    tja_lines = [line for line in tja_text.splitlines() if line.strip() != '']
    tja = split_tja_lines_into_courses(tja_lines)
    for course in tja.courses.values():
        course.branches = parse_tja_course_data(course.data)

    return tja


def split_tja_lines_into_courses(lines: List[str]) -> TJASong:
    """
    Parse TJA metadata in order to split TJA lines into separate courses.

    In TJA files, metadata lines are denoted by a colon (':'). These lines
    provide general info about the song (BPM, TITLE, OFFSET, etc.). They also
    define properties for each course in the song (difficulty, level, etc.).

    This function processes each line of metadata, and assigns the metadata
    to TJACourse objects (one for each course). To separate each course, this
    function uses the `COURSE:` metadata and any `#START P1/P2` commands,
    resulting in the following structure:

    TJASong
    ├─ TJACourse (e.g. Ura)
    │  ├─ Course metadata (level, balloons, scoreinit, scorediff, etc.)
    │  └─ Unparsed data (notes, commands)
    ├─ TJACourse (e.g. Ura-P1)
    ├─ TJACourse (e.g. Ura-P2)
    ├─ TJACourse (e.g. Oni)
    ├─ TJACourse (e.g. Hard)
    └─ ...

    The data for each TJACourse can then be parsed individually using the
    `parse_tja_course_data()` function.
    """
    # Strip leading/trailing whitespace and comments ('// Comment')
    lines = [line.split("//")[0].strip() for line in lines
             if line.split("//")[0].strip()]

    # Initialize song with BPM and OFFSET global metadata
    bpm = float([line.split(":")[1] for line in lines
                if line.startswith("BPM")][0])
    offset = float([line.split(":")[1] for line in lines
                   if line.startswith("OFFSET")][0])
    parsed_tja = TJASong(
        bpm=bpm,
        offset=offset,
        courses={course: TJACourse(bpm=bpm, offset=offset, course=course)
                 for course in TJA_COURSE_NAMES}
    )

    current_course = ''
    current_course_basename = ''
    for line in lines:
        # Only metadata and #START commands are relevant for this function
        match_metadata = re.match(r"^([A-Z0-9]+):(.*)", line)
        match_start = re.match(r"^#START(?:\s+(.+))?", line)

        # Case 1: Metadata lines
        if match_metadata:
            name_upper = match_metadata.group(1).upper()
            value = match_metadata.group(2).strip()

            # Course-specific metadata fields
            if name_upper == 'COURSE':
                if value not in NORMALIZE_COURSE:
                    raise ValueError(f"Invalid COURSE value: '{value}'")
                current_course = NORMALIZE_COURSE[value]
                current_course_basename = current_course
            elif name_upper == 'LEVEL':
                if not value.isdigit():
                    raise ValueError(f"Invalid LEVEL value: '{value}'")
                # restrict to 1 <= level <= 10
                parsed_level = min(max(int(value), 1), 10)
                parsed_tja.courses[current_course].level = parsed_level
            elif name_upper == 'SCOREINIT':
                parsed_tja.courses[current_course].score_init = \
                    int(value.split(",")[-1]) if value else 0
            elif name_upper == 'SCOREDIFF':
                parsed_tja.courses[current_course].score_diff = \
                    int(value.split(",")[-1]) if value else 0
            elif name_upper == 'BALLOON':
                if value:
                    balloons = [int(v) for v in value.split(",") if v]
                    parsed_tja.courses[current_course].balloon = balloons
            elif name_upper == 'STYLE':
                # Reset the course name to remove "P1/P2" that may have been
                # added by a previous STYLE:DOUBLE chart
                if value == 'Single':
                    current_course = current_course_basename
            else:
                pass  # Ignore 'TITLE', 'SUBTITLE', 'WAVE', etc.

        # Case 2: #START commands
        elif match_start:
            value = match_start.group(1) if match_start.group(1) else ''
            # For STYLE:Double, #START P1/P2 indicates the start of a new
            # chart. But, we want multiplayer charts to inherit the
            # metadata from the course as a whole, so we deepcopy the
            # existing course for that difficulty.
            if value in ["1P", "2P"]:
                value = value[1] + value[0]  # Fix user typo (e.g. 1P -> P1)
            if value in ["P1", "P2"]:
                current_course = current_course_basename + value
                parsed_tja.courses[current_course] = \
                    deepcopy(parsed_tja.courses[current_course_basename])
                parsed_tja.courses[current_course].data = []
            elif value:
                raise ValueError(f"Invalid value '{value}' for #START.")

            # Since P1/P2 has been handled, we can just use a normal '#START'
            parsed_tja.courses[current_course].data.append("#START")

        # Case 3: For other commands and data, simply copy as-is (parse later)
        else:
            if current_course:
                parsed_tja.courses[current_course].data.append(line)
            else:
                warnings.warn(f"Data encountered before first COURSE: "
                              f"'{line}' (Check for typos in TJA)")

    # If a .tja has "STYLE: Double" but no "STYLE: Single", then it will be
    # missing data for the "single player" chart. To fix this, we copy over
    # the P1 chart from "STYLE: Double" to fill the "STYLE: Single" role.
    for course_name in COURSE_NAMES:
        course_single_player = parsed_tja.courses[course_name]
        course_player_one = parsed_tja.courses[course_name+"P1"]
        if course_player_one.data and not course_single_player.data:
            parsed_tja.courses[course_name] = deepcopy(course_player_one)

    # Remove any charts (e.g. P1/P2) not present in the TJA file (empty data)
    for course_name in [k for k, v in parsed_tja.courses.items()
                        if not v.data]:
        del parsed_tja.courses[course_name]

    # Recreate dict with consistent insertion order
    parsed_tja.courses = {
        key: parsed_tja.courses[key] for key
        in sorted(parsed_tja.courses.keys())
    }

    return parsed_tja


def parse_tja_course_data(data: List[str]) -> Dict[str, List[TJAMeasure]]:
    """
    Parse course data (notes, commands) into a nested song structure.

    The goal of this function is to process measure separators (',') and
    branch commands ('#BRANCHSTART`, '#N`, '#E', '#M') to split the data
    into branches and measures, resulting in the following structure:

    TJACourse
    ├─ TJABranch ('normal')
    │  ├─ TJAMeasure
    │  │  ├─ TJAData (notes, commands)
    │  │  ├─ TJAData
    │  │  └─ ...
    │  ├─ TJAMeasure
    │  ├─ TJAMeasure
    │  └─ ...
    ├─ TJABranch ('professional')
    └─ TJABranch ('master')

    This provides a faithful, easy-to-inspect tree-style representation of the
    branches and measures within each course of the .tja file.
    """
    parsed_branches = {k: [TJAMeasure()] for k in BRANCH_NAMES}
    has_branches = bool([d for d in data if d.startswith('#BRANCH')])
    current_branch = 'all' if has_branches else 'normal'
    branch_condition = ''

    # Process course lines
    idx_m = 0
    idx_m_branchstart = 0
    for idx_l, line in enumerate(data):
        # 0. Check to see whether line is a command or note data
        command, name, value, note_data = '', '', '', ''
        match_command = re.match(r"^#([A-Z]+)(?:\s+(.+))?", line)
        if match_command:
            command = match_command.group(1)
            if match_command.group(2):
                value = match_command.group(2)
        else:
            note_data = line  # If not a command, then line must be note data

        # 1. Parse measure notes
        if note_data:
            # If measure has ended, then add notes to the current measure,
            # then start a new measure by incrementing idx_m
            if note_data.endswith(','):
                for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                    else [current_branch]):
                    parsed_branches[branch_name][idx_m].notes += note_data[:-1]
                    parsed_branches[branch_name].append(TJAMeasure())
                idx_m += 1
            # Otherwise, keep adding notes to the current measure ('idx_m')
            else:
                for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                    else [current_branch]):
                    parsed_branches[branch_name][idx_m].notes += note_data

        # 2. Parse measure commands that produce an "event"
        elif command in ['GOGOSTART', 'GOGOEND', 'BARLINEON', 'BARLINEOFF',
                         'DELAY', 'SCROLL', 'BPMCHANGE', 'MEASURE',
                         'LEVELHOLD', 'SECTION', 'BRANCHSTART']:
            # Get position of the event
            pos = 0
            for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                else [current_branch]):
                pos = len(parsed_branches[branch_name][idx_m].notes)

            # Parse event type
            if command == 'GOGOSTART':
                name, value = 'gogo', '1'
            elif command == 'GOGOEND':
                name, value = 'gogo', '0'
            elif command == 'BARLINEON':
                name, value = 'barline', '1'
            elif command == 'BARLINEOFF':
                name, value = 'barline', '0'
            elif command == 'DELAY':
                name = 'delay'
            elif command == 'SCROLL':
                name = 'scroll'
            elif command == 'BPMCHANGE':
                name = 'bpm'
            elif command == 'MEASURE':
                name = 'measure'
            elif command == 'LEVELHOLD':
                name = 'levelhold'
            elif command == 'SECTION':
                # If #SECTION occurs before a #BRANCHSTART, then ensure that
                # it's present on every branch. Otherwise, #SECTION will only
                # be present on the current branch, and so the `branch_info`
                # values won't be correctly set for the other two branches.
                if data[idx_l+1].startswith('#BRANCHSTART'):
                    name = 'section'
                    current_branch = 'all'
                # Otherwise, #SECTION exists in isolation. In this case, to
                # reset the accuracy, we just repeat the previous #BRANCHSTART.
                else:
                    name, value = 'branch_start', branch_condition
            elif command == 'BRANCHSTART':
                # Ensure that the #BRANCHSTART command is added to all branches
                current_branch = 'all'
                name = 'branch_start'
                branch_condition = value
                # Preserve the index of the BRANCHSTART command to re-use
                idx_m_branchstart = idx_m

            # Append event to the current measure's events
            for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                else [current_branch]):
                parsed_branches[branch_name][idx_m].events.append(
                    TJAData(name=name, value=value, pos=pos)
                )

        # 3. Parse commands that don't create an event
        #    (e.g. simply changing the current branch)
        else:
            if command in ('START', 'END'):
                current_branch = 'all' if has_branches else 'normal'
            elif command == 'N':
                current_branch = 'normal'
                idx_m = idx_m_branchstart
            elif command == 'E':
                current_branch = 'professional'
                idx_m = idx_m_branchstart
            elif command == 'M':
                current_branch = 'master'
                idx_m = idx_m_branchstart
            elif command == 'BRANCHEND':
                current_branch = 'all'

            else:
                warnings.warn(f"Ignoring unsupported command '{command}'")

    # Delete the last measure in the branch if no notes or events
    # were added to it (due to preallocating empty measures)
    for branch in parsed_branches.values():
        if not branch[-1].notes and not branch[-1].events:
            del branch[-1]

    # Merge measure data and measure events in chronological order
    for branch_name, branch in parsed_branches.items():
        for measure in branch:
            notes = [TJAData(name='note', value=TJA_NOTE_TYPES[note], pos=i)
                     for i, note in enumerate(measure.notes) if
                     TJA_NOTE_TYPES[note] != 'Blank']
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
        if len({len(b) for b in parsed_branches.values()}) != 1:
            raise ValueError(
                "Branches do not have the same number of measures. (This "
                "check was performed prior to splitting up the measures due "
                "to mid-measure commands. Please check the number of ',' you"
                "have in each branch.)"
            )

    return parsed_branches


###############################################################################
#                          Fumen-parsing functions                            #
###############################################################################

def parse_fumen(fumen_file: str,
                exclude_empty_measures: bool = False) -> FumenCourse:
    """
    Parse bytes of a fumen .bin file into nested measures, branches, and notes.

    Fumen files use a very strict file structure. Certain values are expected
    at very specific byte locations in the file. Here, we parse these specific
    byte locations into the following structure:

    FumenCourse
    ├─ FumenHeader
    │  ├─ Timing windows
    │  ├─ Branch points
    │  ├─ Soul gauge bytes
    │  └─ ...
    ├─ FumenMeasure
    │  ├─ FumenBranch ('normal')
    │  │  ├─ FumenNote
    │  │  ├─ FumenNote
    │  │  └─ ...
    │  ├─ FumenBranch ('professional')
    │  └─ FumenBranch ('master')
    ├─ FumenMeasure
    ├─ FumenMeasure
    └─ ...
    """
    with open(fumen_file, "rb") as file:
        size = os.fstat(file.fileno()).st_size

        header = FumenHeader()
        header.parse_header_values(file.read(520))
        song = FumenCourse(header=header)

        for _ in range(song.header.b512_b515_number_of_measures):
            # Parse the measure data using the following `format_string`:
            #   "ffBBHiiiiiii" (12 format characters, 40 bytes per measure)
            #     - 'f': BPM               (one float (4 bytes))
            #     - 'f': fumenOffset       (one float (4 bytes))
            #     - 'B': gogo              (one unsigned char (1 byte))
            #     - 'B': barline           (one unsigned char (1 byte))
            #     - 'H': <padding>         (one unsigned short (2 bytes))
            #     - 'iiiiii': branch_info  (six integers (24 bytes))
            #     - 'i': <padding>         (one integer (4 bytes)
            measure_struct = read_struct(file, song.header.order,
                                         format_string="ffBBHiiiiiii")

            # Create the measure dictionary using the newly-parsed measure data
            measure = FumenMeasure(
                bpm=measure_struct[0],
                offset_start=measure_struct[1],
                gogo=bool(measure_struct[2]),
                barline=bool(measure_struct[3]),
                padding1=measure_struct[4],
                branch_info=list(measure_struct[5:11]),
                padding2=measure_struct[11]
            )

            # Iterate through the three branch types
            for branch_name in BRANCH_NAMES:
                # Parse the measure data using the following `format_string`:
                #   "HHf" (3 format characters, 8 bytes per branch)
                #     - 'H': total_notes ( one unsigned short (2 bytes))
                #     - 'H': <padding>  ( one unsigned short (2 bytes))
                #     - 'f': speed      ( one float (4 bytes)
                branch_struct = read_struct(file, song.header.order,
                                            format_string="HHf")

                # Create the branch dictionary using newly-parsed branch data
                total_notes = branch_struct[0]
                branch = FumenBranch(
                    length=total_notes,
                    padding=branch_struct[1],
                    speed=branch_struct[2],
                )

                # Iterate through each note in the measure (per branch)
                for _ in range(total_notes):
                    # Parse the note data using the following `format_string`:
                    #   "ififHHf" (7 format characters, 24b per note cluster)
                    #     - 'i': note type
                    #     - 'f': note position
                    #     - 'i': item
                    #     - 'f': <padding>
                    #     - 'H': score_init
                    #     - 'H': score_diff
                    #     - 'f': duration
                    note_struct = read_struct(file, song.header.order,
                                              format_string="ififHHf")

                    # Create the note dictionary using newly-parsed note data
                    note_type = note_struct[0]
                    note = FumenNote(
                        note_type=FUMEN_NOTE_TYPES[note_type],
                        pos=note_struct[1],
                        item=note_struct[2],
                        padding=note_struct[3],
                    )

                    if note_type in (0xa, 0xc):
                        # Balloon hits
                        note.hits = note_struct[4]
                        note.hits_padding = note_struct[5]
                    else:
                        song.score_init = note.score_init = note_struct[4]
                        song.score_diff = note.score_diff = note_struct[5] // 4

                    # Drumroll/balloon duration
                    note.duration = note_struct[6]

                    # Account for padding at the end of drumrolls
                    if note_type in (0x6, 0x9, 0x62):
                        note.drumroll_bytes = file.read(8)

                    # Assign the note to the branch
                    branch.notes.append(note)

                # Assign the branch to the measure
                measure.branches[branch_name] = branch

            # Assign the measure to the song
            song.measures.append(measure)
            if file.tell() >= size:
                break

    # NB: Official fumens often include empty measures as a way of inserting
    # barlines for visual effect. But, TJA authors tend not to add these empty
    # measures, because even without them, the song plays correctly. So, in
    # tests, if we want to only compare the timing of the non-empty measures
    # between an official fumen and a converted non-official TJA, then it's
    # useful to exclude the empty measures.
    if exclude_empty_measures:
        song.measures = [m for m in song.measures
                         if m.branches['normal'].length
                         or m.branches['professional'].length
                         or m.branches['master'].length]

    return song


def read_struct(file: BinaryIO,
                order: str,
                format_string: str) -> Tuple[Any, ...]:
    """
    Interpret bytes as packed binary data.

    Arguments:
        - file: The fumen's file object (presumably in 'rb' mode).
        - order: '<' or '>' (little or big endian).
        - format_string: String made up of format characters that describes
                         the data layout. Full list of available characters:
          (https://docs.python.org/3/library/struct.html#format-characters)
        - seek: The position of the read pointer to be used within the file.

    Return values:
        - interpreted_string: A string containing interpreted byte values,
                              based on the specified 'fmt' format characters.
    """
    expected_size = struct.calcsize(order + format_string)
    byte_string = file.read(expected_size)
    # One "official" fumen (AC11\deo\deo_n.bin) runs out of data early
    # This workaround fixes the issue by appending 0's to get the size to match
    if len(byte_string) != expected_size:
        byte_string += (b'\x00' * (expected_size - len(byte_string)))
    interpreted_string = struct.unpack(order + format_string, byte_string)
    return interpreted_string
