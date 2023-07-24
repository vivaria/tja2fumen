import re

from tja2fumen.types import TJAMeasureProcessed, FumenCourse, FumenNote


def process_tja_commands(tja):
    """
    Merge TJA 'data' and 'event' fields into a single measure property, and
    split measures into sub-measures whenever a mid-measure BPM/SCROLL/GOGO
    change occurs.

    The TJA parser produces measure objects with two important properties:
      - 'data': Contains the note data (1: don, 2: ka, etc.) along with
                spacing (s)
      - 'events' Contains event commands such as MEASURE, BPMCHANGE,
                 GOGOTIME, etc.

    However, notes and events can be intertwined within a single measure. So,
    it's not possible to process them separately; they must be considered as
    single sequence.

    A particular danger is BPM changes. TJA allows multiple BPMs within a
    single measure, but the fumen format permits one BPM per measure. So, a
    TJA measure must be split up if it has multiple BPM changes within a
    measure.

    In the future, this logic should probably be moved into the TJA parser
    itself.
    """
    tja_branches_processed = {branch_name: []
                              for branch_name in tja.branches.keys()}
    for branch_name, branch_measures_tja in tja.branches.items():
        current_bpm = tja.BPM
        current_scroll = 1.0
        current_gogo = False
        current_barline = True
        current_dividend = 4
        current_divisor = 4
        for measure_tja in branch_measures_tja:
            # Split measure into submeasure
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
                    measure_tja_processed.data.append(data)

                # Handle commands that can only be placed between measures
                # (i.e. no mid-measure variations)
                elif data.name == 'delay':
                    measure_tja_processed.delay = data.value * 1000  # ms -> s
                elif data.name == 'branch_start':
                    measure_tja_processed.branch_start = data.value
                elif data.name == 'section':
                    measure_tja_processed.section = data.value
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
                # measure in those cases.
                elif data.name in ['bpm', 'scroll', 'gogo']:
                    # Parse the values
                    if data.name == 'bpm':
                        new_val = current_bpm = float(data.value)
                    elif data.name == 'scroll':
                        new_val = current_scroll = data.value
                    elif data.name == 'gogo':
                        new_val = current_gogo = bool(int(data.value))
                    # Check for mid-measure commands
                    # - Case 1: Command happens at the start of a measure;
                    #           just change the value directly
                    if data.pos == 0:
                        measure_tja_processed.__setattr__(data.name, new_val)
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
        if len(set([len(b) for b in tja.branches.values()])) != 1:
            raise ValueError(
                "Branches do not have the same number of measures. (This "
                "check was performed prior to splitting up the measures due "
                "to mid-measure commands. Please check the number of ',' you"
                "have in each branch.)"
            )
        if len(set([len(b) for b in tja_branches_processed.values()])) != 1:
            raise ValueError(
                "Branches do not have the same number of measures. (This "
                "check was performed after splitting up the measures due "
                "to mid-measure commands. Please check any GOGO, BPMCHANGE, "
                "and SCROLL commands you have in your branches, and make sure"
                "that each branch has the same number of commands.)"
            )

    return tja_branches_processed


def convert_tja_to_fumen(tja):
    # Preprocess commands
    tja_branches_processed = process_tja_commands(tja)

    # Pre-allocate the measures for the converted TJA
    n_measures = len(tja_branches_processed['normal'])
    fumen = FumenCourse(
        measures=n_measures,
        score_init=tja.score_init,
        score_diff=tja.score_diff,
    )

    # Set song metadata using information from the processed measures
    fumen.header.b512_b515_number_of_measures = n_measures
    fumen.header.b432_b435_has_branches = int(all(
        [len(b) for b in tja_branches_processed.values()]
    ))

    # Iterate through the different branches in the TJA
    total_notes = {'normal': 0, 'professional': 0, 'master': 0}
    for current_branch, branch_tja in tja_branches_processed.items():
        if not len(branch_tja):
            continue
        branch_points_total = 0
        branch_points_measure = 0
        current_drumroll = None
        branch_conditions = []
        course_balloons = tja.balloon.copy()

        # Iterate through the measures within the branch
        for idx_m, measure_tja in enumerate(branch_tja):
            # Fetch a pair of measures
            measure_fumen_prev = fumen.measures[idx_m-1] if idx_m else None
            measure_fumen = fumen.measures[idx_m]

            # Copy over basic measure properties from the TJA
            measure_fumen.branches[current_branch].speed = measure_tja.scroll
            measure_fumen.gogo = measure_tja.gogo
            measure_fumen.bpm = measure_tja.bpm

            # Compute the duration of the measure
            # First, we compute the duration for a full 4/4 measure
            # Next, we adjust this duration based on both:
            #   1. The *actual* measure size (e.g. #MEASURE 1/8, 5/4, etc.)
            #   2. Whether this is a "submeasure" (i.e. whether it contains
            #      mid-measure commands, which split up the measure)
            #      - If this is a submeasure, then `measure_length` will be
            #        less than the total number of subdivisions.
            #      - In other words, `measure_ratio` will be less than 1.0.
            measure_duration_full_measure = (240000 / measure_fumen.bpm)
            measure_size = (measure_tja.time_sig[0] / measure_tja.time_sig[1])
            measure_length = (measure_tja.pos_end - measure_tja.pos_start)
            measure_ratio = (
                1.0 if measure_tja.subdivisions == 0.0  # Avoid "/0"
                else (measure_length / measure_tja.subdivisions)
            )
            measure_fumen.duration = (measure_duration_full_measure
                                      * measure_size * measure_ratio)

            # Compute the millisecond offsets for the start of each measure
            # First, start the measure using the end timing of the
            # previous measure (plus any #DELAY commands)
            # Next, adjust the start timing to account for #BPMCHANGE
            # commands (!!! Discovered by tana :3 !!!)
            if idx_m == 0:
                measure_fumen.offset_start = (
                    (tja.offset * 1000 * -1) - measure_duration_full_measure
                )
            else:
                measure_fumen.offset_start = measure_fumen_prev.offset_end
                measure_fumen.offset_start += measure_tja.delay
                measure_fumen.offset_start += (240000 / measure_fumen_prev.bpm)
                measure_fumen.offset_start -= (240000 / measure_fumen.bpm)

            # Compute the millisecond offset for the end of each measure
            measure_fumen.offset_end = (measure_fumen.offset_start +
                                        measure_fumen.duration)

            # Handle whether barline should be hidden:
            #     1. Measures where #BARLINEOFF has been set
            #     2. Sub-measures that don't fall on the barline
            barline_off = measure_tja.barline is False
            is_submeasure = (measure_ratio != 1.0 and
                             measure_tja.pos_start != 0)
            if barline_off or is_submeasure:
                measure_fumen.barline = False

            # If a #SECTION command occurs in isolation, and it has a valid
            # condition, then treat it like a branch_start
            if (measure_tja.section is not None
                    and measure_tja.section != 'not_available'
                    and not measure_tja.branch_start):
                branch_condition = measure_tja.section
            else:
                branch_condition = measure_tja.branch_start

            # Check to see if the measure contains a branching condition
            if branch_condition:
                # Handle branch conditions for percentage accuracy
                # There are three cases for interpreting #BRANCHSTART p:
                #    1. Percentage is between 0% and 100%
                #    2. Percentage is above 100% (guaranteed level down)
                #    3. Percentage is 0% (guaranteed level up)
                if branch_condition[0] == 'p':
                    vals = []
                    for percent in branch_condition[1:]:
                        if 0 < percent <= 1:
                            vals.append(int(branch_points_total * percent))
                        elif percent > 1:
                            vals.append(999)
                        else:
                            vals.append(0)
                    if current_branch == 'normal':
                        measure_fumen.branch_info[0:2] = vals
                    elif current_branch == 'professional':
                        measure_fumen.branch_info[2:4] = vals
                    elif current_branch == 'master':
                        measure_fumen.branch_info[4:6] = vals

                # Handle branch conditions for drumroll accuracy
                # There are three cases for interpreting #BRANCHSTART r:
                #    1. It's the first branching condition.
                #    2. It's not the first branching condition, but it
                #       has a #SECTION command to reset the accuracy.
                #    3. It's not the first branching condition, and it
                #       doesn't have a #SECTION command.
                # For the first two cases, the branching conditions are the
                # same no matter what branch you're currently on, so we just
                # use the values as-is: [c1, c2, c1, c2, c1, c2]
                # But, for the third case, since there is no #SECTION, the
                # accuracy is not reset. This results in the following
                # condition: [999, 999, c1, c2, c2, c2]
                #    - Normal can't advance to professional/master
                #    - Professional can stay, or advance to master.
                #    - Master can only stay in master.
                elif branch_condition[0] == 'r':
                    is_first_branch_condition = not branch_conditions
                    has_section = bool(measure_tja.section)
                    if is_first_branch_condition or has_section:
                        measure_fumen.branch_info = branch_condition[1:] * 3
                    else:
                        measure_fumen.branch_info = (
                            [999, 999] +
                            [branch_condition[1]] +
                            [branch_condition[2]] * 3
                        )

                # Reset the points to prepare for the next #BRANCHSTART p
                branch_points_total = 0
                # Keep track of the branch conditions (to later determine how
                # to set the header bytes for branches)
                branch_conditions.append(branch_condition)

            # NB: We update the branch condition note counter *after*
            # we check the current measure's branch condition.
            # This is because the TJA spec says:
            #    "The requirement is calculated one measure before
            #     #BRANCHSTART, changing the branch visually when it
            #     is calculated and changing the notes after #BRANCHSTART."
            # So, by delaying the summation by one measure, we perform the
            # calculation with notes "one measure before".
            branch_points_total += branch_points_measure

            # Create notes based on TJA measure data
            branch_points_measure = 0
            for data in measure_tja.data:
                # Compute the ms position of the note
                pos_ratio = ((data.pos - measure_tja.pos_start)
                             / measure_length)
                note_pos = (measure_fumen.duration * pos_ratio)

                # Handle '8' notes (end of a drumroll/balloon)
                if data.value == "EndDRB":
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
                    current_drumroll = None
                    continue

                # The TJA spec technically allows you to place
                # double-Kusudama notes. But this is unsupported in
                # fumens, so just skip the second Kusudama note.
                if data.value == "Kusudama" and current_drumroll:
                    continue

                # Handle note metadata
                note = FumenNote()
                note.pos = note_pos
                note.type = data.value
                note.score_init = tja.score_init
                note.score_diff = tja.score_diff

                # Handle drumroll notes
                if note.type in ["Balloon", "Kusudama"]:
                    try:
                        note.hits = course_balloons.pop(0)
                    except IndexError as e:
                        raise ValueError(f"Not enough values for 'BALLOON: "
                                         f"{','.join(course_balloons)}'") from e
                    current_drumroll = note
                elif note.type in ["Drumroll", "DRUMROLL"]:
                    current_drumroll = note

                # Track Don/Ka notes (to later compute header values)
                elif note.type.lower() in ['don', 'ka']:
                    total_notes[current_branch] += 1

                # Track branch points (to later compute `#BRANCHSTART p` vals)
                if note.type in ['Don', 'Ka']:
                    pts_to_add = fumen.header.b468_b471_branch_points_good
                elif note.type in ['DON', 'KA']:
                    pts_to_add = fumen.header.b484_b487_branch_points_good_big
                elif note.type == 'Balloon':
                    pts_to_add = fumen.header.b496_b499_branch_points_balloon
                elif note.type == 'Kusudama':
                    pts_to_add = fumen.header.b500_b503_branch_points_kusudama
                else:
                    pts_to_add = 0  # Drumrolls not relevant for `p` conditions
                branch_points_measure += pts_to_add

                # Add the note to the branch for this measure
                measure_fumen.branches[current_branch].notes.append(note)
                measure_fumen.branches[current_branch].length += 1

            # If drumroll hasn't ended by this measure, increase duration
            if current_drumroll:
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
    drumroll_only = branch_conditions != [] and all([
        (cond[0] == 'r') or
        (cond[0] == 'p' and cond[1] == 0.0 and cond[2] == 0.0) or
        (cond[0] == 'p' and cond[1] > 1.00 and cond[2] > 1.00)
        for cond in branch_conditions
    ])
    if drumroll_only:
        fumen.header.b468_b471_branch_points_good = 0
        fumen.header.b484_b487_branch_points_good_big = 0
        fumen.header.b472_b475_branch_points_ok = 0
        fumen.header.b488_b491_branch_points_ok_big = 0
        fumen.header.b496_b499_branch_points_balloon = 0
        fumen.header.b500_b503_branch_points_kusudama = 0

    # Alternatively, if the song has only percentage-based conditions, then set
    # the header bytes so that only notes and balloons contribute to branching.
    percentage_only = branch_conditions != [] and all([
        (condition[0] != 'r')
        for condition in branch_conditions
    ])
    if percentage_only:
        fumen.header.b480_b483_branch_points_drumroll = 0
        fumen.header.b492_b495_branch_points_drumroll_big = 0

    # Compute the ratio between normal and professional/master branches
    if total_notes['professional']:
        fumen.header.b460_b463_normal_professional_ratio = \
            int(65536 * (total_notes['normal'] / total_notes['professional']))
    if total_notes['master']:
        fumen.header.b464_b467_normal_master_ratio = \
            int(65536 * (total_notes['normal'] / total_notes['master']))

    return fumen
