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
        branches, balloon_data = parse_tja_course_data(course.data)
        course.branches = branches
        course.balloon = fix_balloon_field(course.balloon, balloon_data)

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
    tja_metadata = {}
    for required_metadata in ["BPM", "OFFSET"]:
        for line in lines:
            if line.startswith(required_metadata):
                tja_metadata[required_metadata] = float(line.split(":")[1])
                break
        else:
            raise ValueError(f"TJA does not contain required "
                             f"'{required_metadata}' metadata.")
    parsed_tja = TJASong(
        bpm=tja_metadata['BPM'],
        offset=tja_metadata['OFFSET'],
        courses={course: TJACourse(bpm=tja_metadata['BPM'],
                                   offset=tja_metadata['OFFSET'],
                                   course=course)
                 for course in TJA_COURSE_NAMES}
    )

    current_course = ''
    current_course_basename = ''
    for line in lines:
        # Only metadata and #START commands are relevant for this function
        match_metadata = re.match(r"^([a-zA-Z0-9]+):(.*)", line)
        match_start = re.match(r"^#START(?:\s+(.+))?", line)

        # Case 1: Metadata lines
        if match_metadata:
            name_upper = match_metadata.group(1).upper()
            value = match_metadata.group(2).strip()

            # Course-specific metadata fields
            if name_upper == 'COURSE':
                value = value.lower().capitalize()  # coerce hard/HARD -> Hard
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


def parse_tja_course_data(data: List[str]) -> (Dict[str, List[TJAMeasure]],
                                               Dict[str, List[str]]):
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
    # keep track of balloons in order to fix the 'BALLOON' field value
    balloons = {k: [] for k in BRANCH_NAMES}

    # Process course lines
    idx_m = 0
    idx_m_branchstart = 0
    for idx_l, line in enumerate(data):
        # 0. Check to see whether line is a command or note data
        command, name, value, note_data = '', '', '', ''
        match_command = re.match(r"^#([a-zA-Z0-9]+)(?:\s+(.+))?", line)
        if match_command:
            command = match_command.group(1).upper()
            if match_command.group(2):
                value = match_command.group(2)
        else:
            note_data = line  # If not a command, then line must be note data

        # 1. Parse measure notes
        if note_data:
            notes_to_write = []
            # If measure has ended, then add notes to the current measure,
            # then start a new measure by incrementing idx_m
            if note_data.endswith(','):
                for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                    else [current_branch]):
                    check_branch_length(parsed_branches, branch_name,
                                        expected_len=idx_m+1)
                    notes_to_write = note_data[:-1]
                    parsed_branches[branch_name][idx_m].notes += notes_to_write
                    parsed_branches[branch_name].append(TJAMeasure())
                idx_m += 1
            # Otherwise, keep adding notes to the current measure ('idx_m')
            else:
                for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                    else [current_branch]):
                    notes_to_write = note_data
                    parsed_branches[branch_name][idx_m].notes += notes_to_write

            # Keep track of balloon notes that were added
            balloon_notes = [n for n in notes_to_write if n in ['7', '9']]
            # mark balloon notes as duplicates if necessary. this will be used
            # to fix the BALLOON: field to account for duplicated balloons.
            balloon_notes = (['DUPE'] * len(balloon_notes)
                             if current_branch == 'all' else balloon_notes)
            for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                else [current_branch]):
                balloons[branch_name].extend(balloon_notes)

        # 2. Parse measure commands that produce an "event"
        elif command in ['GOGOSTART', 'GOGOEND', 'BARLINEON', 'BARLINEOFF',
                         'DELAY', 'SCROLL', 'BPMCHANGE', 'MEASURE',
                         'LEVELHOLD', 'SECTION', 'BRANCHSTART']:
            # Get position of the event
            pos = 0
            for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                else [current_branch]):
                check_branch_length(parsed_branches, branch_name,
                                    expected_len=idx_m+1)
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
                elif not branch_condition:
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
                # If a branch was intentionally excluded by the charter,
                # make sure to copy measures from the longest branch.
                for branch_name in BRANCH_NAMES:
                    check_branch_length(parsed_branches, branch_name)
                # Preserve the index of the BRANCHSTART command to re-use
                idx_m_branchstart = idx_m

            # Append event to the current measure's events
            for branch_name in (BRANCH_NAMES if current_branch == 'all'
                                else [current_branch]):
                check_branch_length(parsed_branches, branch_name,
                                    expected_len=idx_m+1)
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
    deleted_branches = False
    for branch in parsed_branches.values():
        if not branch[-1].notes and not branch[-1].events:
            del branch[-1]
            deleted_branches = True
    if deleted_branches:
        idx_m -= 1

    # Equalize branch lengths to account for missing branches
    for branch_name, branch in parsed_branches.items():
        if branch:
            check_branch_length(parsed_branches, branch_name)

    # Merge measure data and measure events in chronological order
    for branch_name, branch in parsed_branches.items():
        for measure in branch:
            # warn the user if their measure have typos
            valid_notes = []
            for note in measure.notes:
                if note not in TJA_NOTE_TYPES:
                    warnings.warn(f"Ignoring invalid note '{note}' in measure "
                                  f"'{''.join(measure.notes)}' (check for "
                                  f"typos in TJA)")
                else:
                    valid_notes.append(note)
            notes = [TJAData(name='note', value=TJA_NOTE_TYPES[note], pos=i)
                     for i, note in enumerate(valid_notes) if
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
            # If `check_branch_length` works, this should never be reached
            raise ValueError(
                "Branches do not have the same number of measures. (This "
                "check was performed prior to splitting up the measures due "
                "to mid-measure commands. Please check the number of ',' you "
                "have in each branch.)"
            )

    return parsed_branches, balloons


def check_branch_length(parsed_branches: Dict[str, List[TJAMeasure]],
                        branch_name: str, expected_len: int = 0) -> None:
    """
    Ensure that a given branch ('branch_name') matches either an expected
    integer length, or the max length of all branches if length not given.

    Note: Modifies branch in-place.
    """
    branch_len = len(parsed_branches[branch_name])
    # If no length is provided, then we assume we're comparing branches,
    # then copying any missing measures from the largest branch.
    if expected_len == 0:
        max_branch_name = branch_name
        expected_len = branch_len
        for name, branch in parsed_branches.items():
            if len(branch) > expected_len:
                expected_len = len(branch)
                max_branch_name = name
        warning_msg = (f"To fix this, measures will be copied from the "
                       f"'{max_branch_name}' branch to equalize branch "
                       f"lengths.")
        for idx_m in range(branch_len, expected_len):
            parsed_branches[branch_name].append(
                parsed_branches[max_branch_name][idx_m]
            )
    # Otherwise, if length was provided, then simply pad with empty measures
    else:
        warning_msg = ("To fix this, empty measures will be added to "
                       "equalize branch lengths.")
        for idx_m in range(branch_len, expected_len):
            parsed_branches[branch_name].append(TJAMeasure())

    if branch_len < expected_len:
        warnings.warn(
            f"While parsing the TJA's branches, tja2fumen expected "
            f"{expected_len} measure(s) from the '{branch_name}' branch, but "
            f"it only had {branch_len} measure(s). {warning_msg} (Hint: Do "
            f"#N, #E, and #M all have the same number of measures?)"
        )


def fix_balloon_field(balloon_field: List[int],
                      balloon_data: Dict[str, List[str]]) -> List[int]:
    """
    Fix the 'BALLOON:' metadata field for certain branching songs.

    In Taiko, branching songs may have a different amount of balloons and/or
    different balloon values on their normal/professional/master branches.
    However, the TJA field "BALLOON:" is limited it how it can represent
    balloon hits; it uses a single comma-delimited list of integers. E.g.:

    BALLOON: 13,4,52,4,52,4,52

    It is unclear which of these values belong to which branches.

    This is especially unclear for songs that start out on the "normal" branch,
    or songs that have branching conditions that force a specific branch. These
    songs are often written as TJA with only a single branch written out, yet
    for official fumens, this branch information actually has to be present on
    *all three branches*. So, the 'BALLOON:' field will be missing values.

    In the example above, the "13" balloon actually occurs on the normal branch
    before the first branch condition. Meaning that the balloons are split up
    like this:

    BALLOON: (13,4,52)(4,52)(4,52)

    However, due to fumen requirements, we want the balloons to actually be
    like this:

    BALLOON: (13,4,52)(13,4,52)(13,4,52)

    So, the purpose of this function is to "fix" the balloon information so
    that it can be used for fumen conversion without error.

    NOTE: This fix probably only applies to a VERY small minority of songs.
          One example (shown above) is the Ura chart for Roppon no Bara to Sai
          no Uta. You can see in the wikiwiki that the opening 'Normal'
          section has a balloon note prior to the branch condition. We need
          to duplicate this value across all branches.
    """
    # Return early if course doesn't have branches
    if not all(balloon_data.values()):
        return balloon_field

    # Special case: Courses where the # of balloons is the same for all
    # branches, and the TJA author only listed 1 set of balloons.
    # Fix: Duplicate the balloons 3 times.
    if all(len(balloons) == len(balloon_field)
           for balloons in balloon_data.values()):
        return balloon_field * 3

    # Return early if there were no duplicated balloons in the course
    if not any('DUPE' in balloons for balloons in balloon_data.values()):
        return balloon_field

    # If balloons were duplicated, then we expect the BALLOON: field to have
    # fewer hits values than the number of balloons. If this *isn't* the case,
    # then perhaps the TJA author duplicated the balloon hits themselves, and
    # so we don't want to make any unnecessary edits. Thus, return early.
    # FIXME: This assumption fails for double-kusudama notes, where we may
    #        see a "fake" balloon, thus inflating the total number of balloons.
    #        But, this is such a rare case (double-kusudama + duplicated
    #        balloons + 'BALLOON:' field with implicitly duplicated hits) that
    #        I'm alright handling it incorrectly. If a user files a bug
    #        report, then I'll fix it then.
    total_num_balloons = sum(len(b) for b in balloon_data.values())
    if not (len(balloon_field) < total_num_balloons):
        return balloon_field

    # OK! So, by this point in the function, we're making these assumptions:
    #
    # 1. The TJA chart has branches.
    # 2. The TJA author wrote part of the song for only a single branch
    #    (e.g. the Normal branch, before the first branch condition), and thus
    #    we needed to duplicate some of the note data to create a valid fumen.
    # 3. The 'single branch' part of the TJA contained balloon/kusudama notes,
    #    and thus we needed to duplicate those notes.
    # 4. The TJA author wrote the 'BALLOON:' field such that there was only 1
    #    balloon value for the duplicated balloon note.
    #
    # The goal now is to identify which balloons were duplicated, and make sure
    # the "hits" value is present across all branches.
    duplicated_balloons = []
    balloon_field_fixed = []

    # Handle the normal branch first
    # If balloons are duplicated, then it's probably going to be from 'normal'
    # FIXME: If the balloons are duplicated from the master/professional branch
    #        (e.g. due to a forced branch change from a branch condition), then
    #        this logic will read the balloon values incorrectly.
    #        But, this is such a rare case that I'm alright handling it
    #        incorrectly. If a user files a bug report, then I'll fix it then.
    for balloon_note in balloon_data['normal']:
        balloon_hits = balloon_field.pop(0)
        if balloon_note == 'DUPE':
            duplicated_balloons.append(balloon_hits)
        balloon_field_fixed.append(balloon_hits)

    # Repeat any duplicated balloon notes for the professional/master branches
    for branch_name in ['professional', 'master']:
        dupes_to_copy = duplicated_balloons.copy()
        for balloon_note in balloon_data[branch_name]:
            if balloon_note == 'DUPE':
                balloon_field_fixed.append(dupes_to_copy.pop(0))
            else:
                balloon_field_fixed.append(balloon_field.pop(0))

    return balloon_field_fixed


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
