import re

from tja2fumen.types import TJAMeasureProcessed, FumenCourse, FumenNote


def process_tja_commands(tja):
    """
    Merge TJA 'data' and 'event' fields into a single measure property, and split
    measures into sub-measures whenever a mid-measure BPM/SCROLL/GOGO change occurs.

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
    tja_branches_processed = {branch_name: [] for branch_name in tja.branches.keys()}
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

                # Handle commands that can only be placed between measures (i.e. no mid-measure variations)
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
                    measure_tja_processed.time_sig = [current_dividend, current_divisor]

                # Handle commands that can be placed in the middle of a measure.
                #    NB: For fumen files, if there is a mid-measure change to BPM/SCROLL/GOGO, then the measure will
                #    actually be split into two small submeasures. So, we need to start a new measure in those cases.
                elif data.name in ['bpm', 'scroll', 'gogo']:
                    # Parse the values
                    if data.name == 'bpm':
                        new_val = current_bpm = float(data.value)
                    elif data.name == 'scroll':
                        new_val = current_scroll = data.value
                    elif data.name == 'gogo':
                        new_val = current_gogo = bool(int(data.value))
                    # Check for mid-measure commands
                    # - Case 1: Command happens at the start of a measure; just change the value directly
                    if data.pos == 0:
                        measure_tja_processed.__setattr__(data.name, new_val)
                    # - Case 2: Command occurs mid-measure, so start a new sub-measure
                    else:
                        measure_tja_processed.pos_end = data.pos
                        tja_branches_processed[branch_name].append(measure_tja_processed)
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
        branch_lens = [len(b) for b in tja.branches.values()]
        if not branch_lens.count(branch_lens[0]) == len(branch_lens):
            raise ValueError("Branches do not have the same number of measures.")
        else:
            branch_corrected_lens = [len(b) for b in tja_branches_processed.values()]
            if not branch_corrected_lens.count(branch_corrected_lens[0]) == len(branch_corrected_lens):
                raise ValueError("Branches do not have matching GOGO/SCROLL/BPM commands.")

    return tja_branches_processed


def convert_tja_to_fumen(tja):
    # Preprocess commands
    processed_tja_branches = process_tja_commands(tja)

    # Pre-allocate the measures for the converted TJA
    fumen = FumenCourse(
        measures=len(processed_tja_branches['normal']),
        score_init=tja.score_init,
        score_diff=tja.score_diff,
    )

    # Iterate through the different branches in the TJA
    total_notes = {'normal': 0, 'professional': 0, 'master': 0}
    for current_branch, branch_measures_tja_processed in processed_tja_branches.items():
        if not len(branch_measures_tja_processed):
            continue
        total_notes_branch = 0
        note_counter_branch = 0
        current_drumroll = None
        branch_conditions = []
        course_balloons = tja.balloon.copy()

        # Iterate through the measures within the branch
        for idx_m, measure_tja_processed in enumerate(branch_measures_tja_processed):
            # Fetch a pair of measures
            measure_fumen_prev = fumen.measures[idx_m-1] if idx_m != 0 else None
            measure_fumen = fumen.measures[idx_m]

            # Copy over basic measure properties from the TJA (that don't depend on notes or commands)
            measure_fumen.branches[current_branch].speed = measure_tja_processed.scroll
            measure_fumen.gogo = measure_tja_processed.gogo
            measure_fumen.bpm = measure_tja_processed.bpm

            # Compute the duration of the measure
            # First, we compute the duration for a full 4/4 measure
            measure_duration_full_measure = 4 * 60_000 / measure_tja_processed.bpm
            # Next, we adjust this duration based on both:
            #   1. The *actual* measure size (e.g. #MEASURE 1/8, #MEASURE 5/4, etc.)
            measure_size = measure_tja_processed.time_sig[0] / measure_tja_processed.time_sig[1]
            #   2. Whether this is a "submeasure" (i.e. it contains mid-measure commands, which split up the measure)
            #      - If this is a submeasure, then `measure_length` will be less than the total number of subdivisions.
            measure_length = measure_tja_processed.pos_end - measure_tja_processed.pos_start
            #      - In other words, `measure_ratio` will be less than 1.0:
            measure_ratio = (1.0 if measure_tja_processed.subdivisions == 0.0  # Avoid division by 0 for empty measures
                            else (measure_length / measure_tja_processed.subdivisions))
            # Apply the 2 adjustments to the measure duration
            measure_fumen.duration = measure_duration = measure_duration_full_measure * measure_size * measure_ratio

            # Compute the millisecond offsets for the start and end of each measure
            #  - Start: When the notes first appear on screen (to the right)
            #  - End:   When the notes arrive at the judgment line, and the note gets hit.
            if idx_m == 0:
                measure_fumen.fumen_offset_start = (tja.offset * 1000 * -1) - measure_duration_full_measure
            else:
                # First, start the measure using the end timing of the previous measure (plus any #DELAY commands)
                measure_fumen.fumen_offset_start = measure_fumen_prev.fumen_offset_end + measure_tja_processed.delay
                # Next, adjust the start timing to account for #BPMCHANGE commands (!!! Discovered by tana :3 !!!)
                # To understand what's going on here, imagine the following simple example:
                #   * You have a very slow-moving note (i.e. low BPM), like the big DON in Donkama 2000.
                #   * All the other notes move fast (i.e. high BPM), moving past the big slow note.
                #   * To get this overlapping to work, you need the big slow note to START EARLY, but also END LATE:
                #      - An early start means you need to subtract a LOT of time from the starting fumenOffset.
                #      - Thankfully, the low BPM of the slow note will create a HUGE `measure_offset_adjustment`,
                #        since we are dividing by the BPMs, and dividing by a small number will result in a big number.
                measure_offset_adjustment = (4 * 60_000 / measure_fumen.bpm) - (4 * 60_000 / measure_fumen_prev.bpm)
                #      - When we subtract this adjustment from the fumen_offset_start, we get the "START EARLY" part:
                measure_fumen.fumen_offset_start -= measure_offset_adjustment
                #      - The low BPM of the slow note will also create a HUGE measure duration.
                #      - When we add this long duration to the EARLY START, we end up with the "END LATE" part:
            measure_fumen.fumen_offset_end = measure_fumen.fumen_offset_start + measure_fumen.duration

            # Best guess at what 'barline' status means for each measure:
            # - 'True' means the measure lands on a barline (i.e. most measures), and thus barline should be shown
            # - 'False' means that the measure doesn't land on a barline, and thus barline should be hidden.
            #   For example:
            #     1. Measures where #BARLINEOFF has been set
            #     2. Sub-measures that don't fall on the barline
            if measure_tja_processed.barline is False or (measure_ratio != 1.0 and measure_tja_processed.pos_start != 0):
                measure_fumen.barline = False

            # If a #SECTION command occurs in isolation, and it has a valid condition, then treat it like a branch_start
            if (measure_tja_processed.section is not None and measure_tja_processed.section != 'not_available'
                    and not measure_tja_processed.branch_start):
                branch_condition = measure_tja_processed.section
            else:
                branch_condition = measure_tja_processed.branch_start

            # Check to see if the measure contains a branching condition
            if branch_condition:
                # Determine which values to assign based on the type of branching condition
                if branch_condition[0] == 'p':
                    vals = []
                    for percent in branch_condition[1:]:
                        # Ensure percentage is between 0% and 100%
                        if 0 <= percent <= 1:
                            val = total_notes_branch * percent * 20
                            # If the result is very close, then round to account for lack of precision in percentage
                            if abs(val - round(val)) < 0.1:
                                val = round(val)
                            vals.append(int(val))
                        # If it is above 100%, then it means a guaranteed "level down". Fumens use 999 for this.
                        elif percent > 1:
                            vals.append(999)
                        # If it is below 0%, it is a guaranteed "level up". Fumens use 0 for this.
                        else:
                            vals.append(0)
                    if current_branch == 'normal':
                        measure_fumen.branch_info[0:2] = vals
                    elif current_branch == 'professional':
                        measure_fumen.branch_info[2:4] = vals
                    elif current_branch == 'master':
                        measure_fumen.branch_info[4:6] = vals

                # If it's a drumroll, then the values to use depends on whether there is a #SECTION in the same measure
                #   - If there is a #SECTION, then accuracy is reset, so repeat the same condition for all 3 branches
                #   - If there isn't a #SECTION, but it's the first branch condition, repeat for all 3 branches as well
                #   - If there isn't a #SECTION, and there are previous branch conditions, the outcomes now matter:
                #        * If the player failed to go from Normal -> Advanced/Master, then they must stay in Normal,
                #          hence the 999 values (which force them to stay in Normal)
                #        * If the player made it to Advanced, then both condition values still apply (for either
                #          staying in Advanced or leveling up to Master)
                #        * If the player made it to Master, then only use the "master condition" value (2), otherwise
                #          they fall back to Normal.
                #   - The "no-#SECTION" behavior can be seen in songs like "Shoutoku Taiko no 「Hi Izuru Made Asuka」"
                elif branch_condition[0] == 'r':
                    if current_branch == 'normal':
                        measure_fumen.branch_info[0:2] = (branch_condition[1:] if measure_tja_processed.section or
                                                        not measure_tja_processed.section and not branch_conditions
                                                        else [999, 999])
                    elif current_branch == 'professional':
                        measure_fumen.branch_info[2:4] = branch_condition[1:]
                    elif current_branch == 'master':
                        measure_fumen.branch_info[4:6] = (branch_condition[1:] if measure_tja_processed.section or
                                                        not measure_tja_processed.section and not branch_conditions
                                                        else [branch_condition[2]] * 2)

                # Reset the note counter corresponding to this branch (i.e. reset the accuracy)
                total_notes_branch = 0
                # Keep track of branch conditions (to later determine how to set the header bytes for branches)
                branch_conditions.append(branch_condition)

            # NB: We update the branch condition note counter *after* we check the current measure's branch condition.
            # This is because the TJA spec says:
            #    "The requirement is calculated one measure before #BRANCHSTART, changing the branch visually when it
            #     is calculated and changing the notes after #BRANCHSTART."
            # So, by delaying the summation by one measure, we perform the calculation with notes "one measure before".
            total_notes_branch += note_counter_branch

            # Create notes based on TJA measure data
            note_counter_branch = 0
            note_counter = 0
            for idx_d, data in enumerate(measure_tja_processed.data):
                if data.name == 'note':
                    note = FumenNote()
                    # Note positions must be calculated using the base measure duration (that uses a single BPM value)
                    # (In other words, note positions do not take into account any mid-measure BPM change adjustments.)
                    note.pos = measure_duration * (data.pos - measure_tja_processed.pos_start) / measure_length
                    # Handle the note that represents the end of a drumroll/balloon
                    if data.value == "EndDRB":
                        # If a drumroll spans a single measure, then add the difference between start/end position
                        if not current_drumroll.multimeasure:
                            current_drumroll.duration += (note.pos - current_drumroll.pos)
                        # Otherwise, if a drumroll spans multiple measures, then we want to add the duration between
                        # the start of the measure (i.e. pos=0.0) and the drumroll's end position.
                        else:
                            current_drumroll.duration += (note.pos - 0.0)
                        # 1182, 1385, 1588, 2469, 1568, 752, 1568
                        current_drumroll.duration = float(int(current_drumroll.duration))
                        current_drumroll = None
                        continue
                    # The TJA spec technically allows you to place double-Kusudama notes:
                    #    "Use another 9 to specify when to lower the points for clearing."
                    # But this is unsupported in fumens, so just skip the second Kusudama note.
                    if data.value == "Kusudama" and current_drumroll:
                        continue
                    # Handle the remaining non-EndDRB, non-double Kusudama notes
                    note.type = data.value
                    note.score_init = tja.score_init
                    note.score_diff = tja.score_diff
                    # Handle drumroll/balloon-specific metadata
                    if note.type in ["Balloon", "Kusudama"]:
                        note.hits = course_balloons.pop(0)
                        current_drumroll = note
                        total_notes[current_branch] -= 1
                    if note.type in ["Drumroll", "DRUMROLL"]:
                        current_drumroll = note
                        total_notes[current_branch] -= 1
                    # Count dons, kas, and balloons for the purpose of tracking branching accuracy
                    if note.type.lower() in ['don', 'ka']:
                        note_counter_branch += 1
                    elif note.type.lower() in ['balloon', 'kusudama']:
                        note_counter_branch += 1.5
                    measure_fumen.branches[current_branch].notes.append(note)
                    note_counter += 1

            # If drumroll hasn't ended by the end of this measure, increase duration by measure timing
            if current_drumroll:
                if current_drumroll.duration == 0.0:
                    current_drumroll.duration += (measure_duration - current_drumroll.pos)
                    current_drumroll.multimeasure = True
                else:
                    current_drumroll.duration += measure_duration

            measure_fumen.branches[current_branch].length = note_counter
            total_notes[current_branch] += note_counter

    # Set song-specific metadata
    fumen.header.b512_b515_number_of_measures = len(fumen.measures)
    fumen.header.b432_b435_has_branches = int(all([len(b) for b in processed_tja_branches.values()]))
    fumen.header.set_hp_bytes(total_notes['normal'], tja.course, tja.level)

    # If song has only drumroll branching conditions (plus percentage conditions that force a level up/level down),
    # then set the header bytes so that only drumrolls contribute to branching.
    drumroll_only = branch_conditions != [] and all([
        (condition[0] == 'r') or
        (condition[0] == 'p' and condition[1] == 0.0 and condition[2] == 0.0) or
        (condition[0] == 'p' and condition[1] > 1.00 and condition[2] > 1.00)
        for condition in branch_conditions
    ])
    if drumroll_only:
        fumen.header.b468_b471_branch_points_good = 0
        fumen.header.b484_b487_branch_points_good_big = 0
        fumen.header.b472_b475_branch_points_ok = 0
        fumen.header.b488_b491_branch_points_ok_big = 0
        fumen.header.b496_b499_branch_points_balloon = 0
        fumen.header.b500_b503_branch_points_kusudama = 0

    # Compute the ratio between normal and professional/master branches (just in case the note counts differ)
    if total_notes['professional']:
        fumen.header.b460_b463_normal_professional_ratio = int(65536 * (total_notes['normal'] / total_notes['professional']))
    if total_notes['master']:
        fumen.header.b464_b467_normal_master_ratio = int(65536 * (total_notes['normal'] / total_notes['master']))

    return fumen
