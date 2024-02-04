"""
Functions for converting TJA song data to Fumen song data.
"""

import re
from typing import List, Dict, Tuple, Union

from tja2fumen.classes import (TJACourse, TJAMeasure, TJAMeasureProcessed,
                               FumenCourse, FumenHeader, FumenMeasure,
                               FumenNote)
from tja2fumen.constants import BRANCH_NAMES


def process_commands(tja_branches: Dict[str, List[TJAMeasure]], bpm: float) \
                                -> Dict[str, List[TJAMeasureProcessed]]:
    """
    Process all commands in each measure.

    This function takes care of two main tasks:
        1. Keeping track of what the current values are for BPM, scroll,
           gogotime, barline, and time signature (i.e. #MEASURE).
        2. Detecting when a command is placed in the middle of a measure,
           and splitting that measure into sub-measures.

    ((Note: We split measures into sub-measures because official `.bin` files
      can only have 1 value for BPM/SCROLL/GOGO per measure. So, if a TJA
      measure has multiple BPMs/SCROLLs/GOGOs, it has to be split up.))

    After this function is finished, all the #COMMANDS will be gone, and each
    measure will have attributes (e.g. measure.bpm, measure.scroll) instead.
    """
    tja_branches_processed: Dict[str, List[TJAMeasureProcessed]] = {
        branch_name: [] for branch_name in tja_branches.keys()
    }
    for branch_name, branch_measures_tja in tja_branches.items():
        current_bpm = bpm
        current_scroll = 1.0
        current_gogo = False
        current_barline = True
        current_dividend = 4
        current_divisor = 4
        for measure_tja in branch_measures_tja:
            measure_tja_processed = TJAMeasureProcessed(
                bpm=current_bpm,
                scroll=current_scroll,
                gogo=current_gogo,
                barline=current_barline,
                time_sig=[current_dividend, current_divisor],
                subdivisions=len(measure_tja.notes),
            )
            for data in measure_tja.combined:
                # Handle note data
                if data.name == 'note':
                    measure_tja_processed.notes.append(data)

                # Handle commands that can only be placed between measures
                # (i.e. no mid-measure variations)
                elif data.name == 'delay':
                    measure_tja_processed.delay = float(data.value) * 1000
                elif data.name == 'branch_start':
                    branch_type, val1, val2 = data.value.split(',')
                    if branch_type == 'r':  # r = drumRoll
                        branch_cond = (float(val1), float(val2))
                    elif branch_type == 'p':  # p = Percentage
                        branch_cond = (float(val1)/100, float(val2)/100)
                    else:
                        raise ValueError(f"Invalid #BRANCHSTART type: "
                                         f"'{branch_type}'.")
                    measure_tja_processed.branch_type = branch_type
                    measure_tja_processed.branch_cond = branch_cond
                elif data.name == 'section':
                    measure_tja_processed.section = bool(data.value)
                elif data.name == 'levelhold':
                    measure_tja_processed.levelhold = True
                elif data.name == 'barline':
                    current_barline = bool(int(data.value))
                    measure_tja_processed.barline = current_barline
                elif data.name == 'measure':
                    match_measure = re.match(r"(\d+)/(\d+)", data.value)
                    if not match_measure:
                        continue
                    current_dividend = int(match_measure.group(1))
                    current_divisor = int(match_measure.group(2))
                    measure_tja_processed.time_sig = [current_dividend,
                                                      current_divisor]

                # Handle commands that can be placed in the middle of a
                # measure. (For fumen files, if there is a mid-measure change
                # to BPM/SCROLL/GOGO, then the measure will actually be split
                # into two small submeasures. So, we need to start a new
                # measure in those cases.)
                elif data.name in ['bpm', 'scroll', 'gogo']:
                    # Parse the values
                    new_val: Union[bool, float]
                    if data.name == 'bpm':
                        new_val = current_bpm = float(data.value)
                    elif data.name == 'scroll':
                        new_val = current_scroll = float(data.value)
                    elif data.name == 'gogo':
                        new_val = current_gogo = bool(int(data.value))
                    # Check for mid-measure commands
                    # - Case 1: Command happens at the start of a measure;
                    #           just change the value directly
                    if data.pos == 0:
                        setattr(measure_tja_processed, data.name,
                                new_val)  # noqa: new_val will always be set
                    # - Case 2: Command happens in the middle of a measure;
                    #           start a new sub-measure
                    else:
                        measure_tja_processed.pos_end = data.pos
                        tja_branches_processed[branch_name]\
                            .append(measure_tja_processed)
                        measure_tja_processed = TJAMeasureProcessed(
                            bpm=current_bpm,
                            scroll=current_scroll,
                            gogo=current_gogo,
                            barline=current_barline,
                            time_sig=[current_dividend, current_divisor],
                            subdivisions=len(measure_tja.notes),
                            pos_start=data.pos
                        )

                else:
                    print(f"Unexpected event type: {data.name}")

            measure_tja_processed.pos_end = len(measure_tja.notes)
            tja_branches_processed[branch_name].append(measure_tja_processed)

    has_branches = all(len(b) for b in tja_branches_processed.values())
    if has_branches:
        if len({len(b) for b in tja_branches_processed.values()}) != 1:
            raise ValueError(
                "Branches do not have the same number of measures. (This "
                "check was performed after splitting up the measures due "
                "to mid-measure commands. Please check any GOGO, BPMCHANGE, "
                "and SCROLL commands you have in your branches, and make sure"
                "that each branch has the same number of commands.)"
            )

    return tja_branches_processed


def convert_tja_to_fumen(tja: TJACourse) -> FumenCourse:
    """
    Convert TJA data to Fumen data by calculating Fumen-specific values.

    Fumen files (`.bin`) use a very strict file structure. Certain values are
    expected at very specific byte locations in the file, such as:
      - Header metadata (first 520 bytes). The header stores information such
        as branch points for each note type, soul gauge behavior, etc.
      - Note data (millisecond offset values, drumroll duration, etc.)
      - Branch condition info for each measure

    Since TJA files only contain notes and commands, we must compute all of
    these extra values ourselves. The values are then stored in new "Fumen"
    Python objects that mimic the structure of the fumen `.bin` files:

    FumenCourse
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

    ((Note: The fumen file structure is the opposite of the TJA file structure;
    branch data is stored within the measure object, rather than measure data
    being stored within the branch object.))
    """
    # Preprocess commands
    tja_branches_processed = process_commands(tja.branches, tja.bpm)

    # Pre-allocate the measures for the converted TJA
    n_measures = len(tja_branches_processed['normal'])
    fumen = FumenCourse(
        measures=[FumenMeasure() for _ in range(n_measures)],
        header=FumenHeader(),
        score_init=tja.score_init,
        score_diff=tja.score_diff,
    )

    # Set song metadata using information from the processed measures
    fumen.header.b512_b515_number_of_measures = n_measures
    fumen.header.b432_b435_has_branches = int(all(
        len(b) for b in tja_branches_processed.values()
    ))

    # Iterate through the different branches in the TJA
    total_notes = {'normal': 0, 'professional': 0, 'master': 0}
    for current_branch, branch_tja in tja_branches_processed.items():
        # Skip empty branches (e.g. 'professional', 'master')
        if not branch_tja:
            continue

        # Track properties that will change over the course of the song
        branch_points_total = 0
        branch_points_measure = 0
        current_drumroll = FumenNote()
        current_levelhold = False
        branch_types: List[str] = []
        branch_conditions: List[Tuple[float, float]] = []
        course_balloons = tja.balloon.copy()

        # Iterate over pairs of TJA and Fumen measures
        for idx_m, (measure_tja, measure_fumen) in \
                enumerate(zip(branch_tja, fumen.measures)):

            # Copy over basic measure properties from the TJA
            measure_fumen.branches[current_branch].speed = measure_tja.scroll
            measure_fumen.gogo = measure_tja.gogo
            measure_fumen.bpm = measure_tja.bpm

            # Compute the duration of the measure
            measure_length = measure_tja.pos_end - measure_tja.pos_start
            measure_fumen.set_duration(
                time_sig=measure_tja.time_sig,
                measure_length=measure_length,
                subdivisions=measure_tja.subdivisions
            )

            # Compute the millisecond offsets for the start/end of each measure
            if idx_m == 0:
                measure_fumen.set_first_ms_offsets(song_offset=tja.offset)
            else:
                measure_fumen.set_ms_offsets(
                    delay=measure_tja.delay,
                    prev_measure=fumen.measures[idx_m-1],
                )

            # Handle whether barline should be hidden:
            #     1. Measures where #BARLINEOFF has been set
            #     2. Sub-measures that don't fall on the barline
            barline_off = measure_tja.barline is False
            is_submeasure = (measure_length < measure_tja.subdivisions and
                             measure_tja.pos_start != 0)
            if barline_off or is_submeasure:
                measure_fumen.barline = False

            # Check to see if the measure contains a branching condition
            branch_type = measure_tja.branch_type
            branch_cond = measure_tja.branch_cond
            if branch_type and branch_cond:
                # Update the branch_info values for the measure
                measure_fumen.set_branch_info(
                    branch_type, branch_cond,
                    branch_points_total, current_branch,
                    has_levelhold=current_levelhold
                )
                # Reset the points to prepare for the next `#BRANCHSTART p`
                branch_points_total = 0
                # Reset the levelhold value (so that future branch_conditions
                # work normally)
                current_levelhold = False
                # Keep track of the branch conditions (to later determine how
                # to set the header bytes for branches)
                branch_types.append(branch_type)
                branch_conditions.append(branch_cond)

            # NB: We update the branch condition note counter *after*
            # we check the current measure's branch condition.
            # This is because the TJA spec says:
            #    "The requirement is calculated one measure before
            #     #BRANCHSTART, changing the branch visually when it
            #     is calculated and changing the notes after #BRANCHSTART."
            # So, by delaying the summation by one measure, we perform the
            # calculation with notes "one measure before".
            branch_points_total += branch_points_measure

            # LEVELHOLD essentially means "ignore the branch condition for
            # the next `#BRANCHSTART` command", so we check this value after
            # we've already processed the branch condition for this measure.
            if measure_tja.levelhold:
                current_levelhold = True

            # Create notes based on TJA measure data
            branch_points_measure = 0
            for note_tja in measure_tja.notes:
                # Compute the ms position of the note
                pos_ratio = ((note_tja.pos - measure_tja.pos_start) /
                             (measure_tja.pos_end - measure_tja.pos_start))
                note_pos = measure_fumen.duration * pos_ratio

                # Handle '8' notes (end of a drumroll/balloon)
                if note_tja.value == "EndDRB":
                    if not current_drumroll.note_type:
                        raise ValueError(
                            "'8' note encountered without matching "
                            "drumroll/balloon/kusudama note."
                        )
                    # If a drumroll spans a single measure, then add the
                    # difference between start/end position
                    if not current_drumroll.multimeasure:
                        current_drumroll.duration += (note_pos -
                                                      current_drumroll.pos)
                    # Otherwise, if a drumroll spans multiple measures,
                    # then we want to add the duration between the start
                    # of the measure and the drumroll's end position.
                    else:
                        current_drumroll.duration += (note_pos - 0.0)
                    current_drumroll.duration = float(int(
                        current_drumroll.duration
                    ))
                    current_drumroll = FumenNote()
                    continue

                # The TJA spec technically allows you to place
                # double-Kusudama notes. But this is unsupported in
                # fumens, so just skip the second Kusudama note.
                if note_tja.value == "Kusudama" and current_drumroll.note_type:
                    continue

                # Now that the edge cases have been taken care of ('continue'),
                # we can initialize a note and handle general note metadata.
                note = FumenNote()
                note.pos = note_pos
                note.note_type = note_tja.value
                note.score_init = tja.score_init
                note.score_diff = tja.score_diff

                # Handle drumroll-specific note metadata
                if note.note_type in ["Drumroll", "DRUMROLL"]:
                    current_drumroll = note
                elif note.note_type in ["Balloon", "Kusudama"]:
                    try:
                        note.hits = course_balloons.pop(0)
                    except IndexError as exc:
                        raise ValueError(f"Not enough values for 'BALLOON: "
                                         f"{course_balloons}'") from exc
                    current_drumroll = note

                # Track Don/Ka notes (to later compute header values)
                elif (note.note_type.lower().startswith('don')
                        or note.note_type.lower().startswith('ka')):
                    total_notes[current_branch] += 1

                # Track branch points (to later compute `#BRANCHSTART p` vals)
                if note.note_type in ['Don', 'Ka']:
                    pts_to_add = fumen.header.b468_b471_branch_pts_good
                elif note.note_type in ['DON', 'KA']:
                    pts_to_add = fumen.header.b484_b487_branch_pts_good_big
                elif note.note_type == 'Balloon':
                    pts_to_add = fumen.header.b496_b499_branch_pts_balloon
                elif note.note_type == 'Kusudama':
                    pts_to_add = fumen.header.b500_b503_branch_pts_kusudama
                else:
                    pts_to_add = 0  # Drumrolls not relevant for `p` conditions
                branch_points_measure += pts_to_add

                # Add the note to the branch for this measure
                measure_fumen.branches[current_branch].notes.append(note)
                measure_fumen.branches[current_branch].length += 1

            # If drumroll hasn't ended by this measure, increase duration
            if current_drumroll.note_type:
                # If drumroll spans multiple measures, add full duration
                if current_drumroll.multimeasure:
                    current_drumroll.duration += measure_fumen.duration
                # Otherwise, add the partial duration spanned by the drumroll
                else:
                    current_drumroll.multimeasure = True
                    current_drumroll.duration += (measure_fumen.duration -
                                                  current_drumroll.pos)

    # Compute the header bytes that dictate the soul gauge bar behavior
    fumen.header.set_hp_bytes(total_notes['normal'], tja.course, tja.level)

    # If song has only drumroll branching conditions (also allowing percentage
    # conditions that force a level up/level down), then set the header bytes
    # so that only drumrolls contribute to branching.
    drumroll_only = (
        branch_types           # noqa: branch_types will always be set
        and branch_conditions  # noqa: branch_conditions will always be set
        and all(
            (branch_type == 'r') or
            (branch_type == 'p' and cond[0] == 0.0 and cond[1] == 0.0) or
            (branch_type == 'p' and cond[0] > 1.00 and cond[1] > 1.00)
            for branch_type, cond in zip(branch_types, branch_conditions)
        )
    )
    if drumroll_only:
        fumen.header.b468_b471_branch_pts_good = 0
        fumen.header.b484_b487_branch_pts_good_big = 0
        fumen.header.b472_b475_branch_pts_ok = 0
        fumen.header.b488_b491_branch_pts_ok_big = 0
        fumen.header.b496_b499_branch_pts_balloon = 0
        fumen.header.b500_b503_branch_pts_kusudama = 0

    # Alternatively, if the song has only percentage-based conditions, then set
    # the header bytes so that only notes and balloons contribute to branching.
    percentage_only = (
        branch_types  # noqa: branch_types will always be set
        and all(
            (branch_type != 'r')
            for branch_type in branch_types
        )
    )
    if percentage_only:
        fumen.header.b480_b483_branch_pts_drumroll = 0
        fumen.header.b492_b495_branch_pts_drumroll_big = 0

    # Compute the ratio between normal and professional/master branches
    if total_notes['professional']:
        fumen.header.b460_b463_normal_professional_ratio = \
            int(65536 * (total_notes['normal'] / total_notes['professional']))
    if total_notes['master']:
        fumen.header.b464_b467_normal_master_ratio = \
            int(65536 * (total_notes['normal'] / total_notes['master']))

    return fumen


def fix_dk_note_types_course(fumen: FumenCourse) -> None:
    """
    Call `fix_dk_note_types` once per branch on a FumenCourse.
    """
    # try to determine the song's BPM from its measures
    measure_bpms = [m.bpm for m in fumen.measures]
    unique_bpms = set(measure_bpms)
    song_bpm = max(unique_bpms, key=measure_bpms.count)

    # collect the d/k notes for each branch, then fix their types
    for branch_name in BRANCH_NAMES:
        dk_notes = []
        for measure in fumen.measures:
            for note in measure.branches[branch_name].notes:
                if any(note.note_type.lower().startswith(t)
                       for t in ['don', 'ka']):
                    note.pos_abs = (measure.offset_start + note.pos +
                                    (4 * 60_000 / measure.bpm))
                    dk_notes.append(note)
        if dk_notes:
            fix_dk_note_types(dk_notes, song_bpm)


def fix_dk_note_types(dk_notes: List[FumenNote], song_bpm: float) -> None:
    """
    Cluster Don/Ka notes based on their relative positions, then replace
    Don/Ka notes with alternate versions (Don2, Don3, Ka2).

    NB: Modifies FumenNote objects in-place
    """
    # Sort the notes by their absolute positions to account for BPMCHANGE
    dk_notes = sorted(dk_notes, key=lambda note: note.pos_abs)

    # Get the differences between each note and the previous one
    for (note_1, note_2) in zip(dk_notes, dk_notes[1:]):
        note_1.diff = int(note_2.pos_abs - note_1.pos_abs)

    # Isolate the unique difference values and sort them
    diffs_unique = sorted(list({note.diff for note in dk_notes}))

    # Avoid clustering any whole notes, half notes, or quarter notes
    # i.e. only cluster 8th notes, 16th notes, etc.
    measure_duration = (4 * 60_000) / song_bpm
    quarter_note_duration = int(measure_duration / 4)
    diffs_under_quarter: List[int] = [diff for diff in diffs_unique
                                      if diff < quarter_note_duration]

    # Anything above an 8th note (12th, 16th, 24th, 36th, etc...) should be
    # clustered together as a single stream
    diffs_to_cluster: List[List[int]] = []
    diffs_under_8th: List[int] = []
    eighth_note_duration = int(measure_duration / 8)
    for diff in diffs_under_quarter:
        if diff < eighth_note_duration:
            diffs_under_8th.append(diff)
        else:
            diffs_to_cluster.append([diff])
    # Make sure to cluster the close-together notes first
    if diffs_under_8th:
        diffs_to_cluster.insert(0, diffs_under_8th)

    # Cluster the notes from the smallest difference to the largest
    semi_clustered: List[Union[FumenNote, List[FumenNote]]] = list(dk_notes)
    for diff_vals in diffs_to_cluster:
        semi_clustered = cluster_notes(semi_clustered, diff_vals)

    # Turn any remaining isolated notes into clusters (i.e. long diffs)
    clustered_notes = [cluster if isinstance(cluster, list) else [cluster]
                       for cluster in semi_clustered]

    # In each cluster, replace dons/kas with their alternate versions
    replace_alternate_don_kas(clustered_notes, eighth_note_duration)


def replace_alternate_don_kas(note_clusters: List[List[FumenNote]],
                              eighth_note_duration: int) -> None:
    """
    Replace Don/Ka notes with alternate versions (Don2, Don3, Ka2) based on
    positions within a cluster of notes.

    NB: Modifies FumenNote objects in-place
    """
    big_notes = ['DON', 'DON2', 'KA', 'KA2']
    for cluster in note_clusters:
        # Replace all small notes with the basic do/ka notes ("Don2", "Ka2")
        for note in cluster:
            if note.note_type not in big_notes:
                if note.note_type[-1].isdigit():
                    note.note_type = note.note_type[:-1] + "2"
                else:
                    note.note_type += "2"

        # The "ko" type of Don note only occurs every other note, and only
        # in odd-length all-don runs (DDD: Do-ko-don, DDDDD: Do-ko-do-ko-don)
        all_dons = all(note.note_type.startswith("Don") for note in cluster)
        for i, note in enumerate(cluster):
            if (all_dons and (len(cluster) % 2 == 1) and (i % 2 == 1)
                    and note.note_type not in big_notes):
                note.note_type = "Don3"

        # Replace the last note in a cluster with the ending Don/Kat
        # In other words, remove the '2' from the last note.
        # However, there's one exception: Groups of 4 notes, faster than 8th
        is_fast_cluster_of_4 = (len(cluster) == 4 and
                                all(note.diff < eighth_note_duration
                                    for note in cluster[:-1]))
        if is_fast_cluster_of_4:
            # Leave last note as Don2/Ka2
            pass
        else:
            # Replace last Don2/Ka2 with Don/Ka
            if cluster[-1].note_type not in big_notes:
                cluster[-1].note_type = cluster[-1].note_type[:-1]


def cluster_notes(item_list: List[Union[FumenNote, List[FumenNote]]],
                  cluster_diffs: List[int]) \
        -> List[Union[FumenNote, List[FumenNote]]]:
    """Group notes based on the differences between them."""
    clustered_notes: List[Union[FumenNote, List[FumenNote]]] = []
    current_cluster: List[FumenNote] = []
    for item in item_list:
        # If we encounter an already-clustered group of items, the current
        # cluster should end
        if isinstance(item, list):
            if current_cluster:
                clustered_notes.append(current_cluster)
                current_cluster = []
            clustered_notes.append(item)
        # Handle values that haven't been clustered yet
        else:
            assert isinstance(item, FumenNote)
            # Start and/or continue the current cluster
            if any(item.diff == diff for diff in cluster_diffs):
                current_cluster.append(item)
            else:
                # Finish the existing cluster
                if current_cluster:
                    current_cluster.append(item)
                    clustered_notes.append(current_cluster)
                    current_cluster = []
                # Or, if there is no cluster, append the item
                else:
                    clustered_notes.append(item)
    if current_cluster:
        clustered_notes.append(current_cluster)
    return clustered_notes
