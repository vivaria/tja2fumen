import re

from tja2fumen.utils import computeSoulGaugeBytes
from tja2fumen.constants import DIFFICULTY_BYTES
from tja2fumen.types import TJAMeasureProcessed, FumenCourse, FumenNote


def processTJACommands(tja):
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
    tjaBranchesProcessed = {branchName: [] for branchName in tja.branches.keys()}
    for branchName, branchMeasuresTJA in tja.branches.items():
        currentBPM = tja.BPM
        currentScroll = 1.0
        currentGogo = False
        currentBarline = True
        currentDividend = 4
        currentDivisor = 4
        for measureTJA in branchMeasuresTJA:
            # Split measure into submeasure
            measureTJAProcessed = TJAMeasureProcessed(
                bpm=currentBPM,
                scroll=currentScroll, 
                gogo=currentGogo, 
                barline=currentBarline, 
                time_sig=[currentDividend, currentDivisor], 
                subdivisions=len(measureTJA.notes),
            )
            for data in measureTJA.combined:
                # Handle note data
                if data.name == 'note':
                    measureTJAProcessed.data.append(data)

                # Handle commands that can only be placed between measures (i.e. no mid-measure variations)
                elif data.name == 'delay':
                    measureTJAProcessed.delay = data.value * 1000  # ms -> s
                elif data.name == 'branchStart':
                    measureTJAProcessed.branchStart = data.value
                elif data.name == 'barline':
                    currentBarline = bool(int(data.value))
                    measureTJAProcessed.barline = currentBarline
                elif data.name == 'measure':
                    matchMeasure = re.match(r"(\d+)/(\d+)", data.value)
                    if not matchMeasure:
                        continue
                    currentDividend = int(matchMeasure.group(1))
                    currentDivisor = int(matchMeasure.group(2))
                    measureTJAProcessed.time_sig = [currentDividend, currentDivisor]

                # Handle commands that can be placed in the middle of a measure.
                #    NB: For fumen files, if there is a mid-measure change to BPM/SCROLL/GOGO, then the measure will
                #    actually be split into two small submeasures. So, we need to start a new measure in those cases.
                elif data.name in ['bpm', 'scroll', 'gogo']:
                    # Parse the values
                    if data.name == 'bpm':
                        new_val = currentBPM = float(data.value)
                    elif data.name == 'scroll':
                        new_val = currentScroll = data.value
                    elif data.name == 'gogo':
                        new_val = currentGogo = bool(int(data.value))
                    # Check for mid-measure commands
                    # - Case 1: Command happens at the start of a measure; just change the value directly
                    if data.pos == 0:
                        measureTJAProcessed.__setattr__(data.name, new_val)
                    # - Case 2: Command occurs mid-measure, so start a new sub-measure
                    else:
                        measureTJAProcessed.pos_end = data.pos
                        tjaBranchesProcessed[branchName].append(measureTJAProcessed)
                        measureTJAProcessed = TJAMeasureProcessed(
                            bpm=currentBPM,
                            scroll=currentScroll,
                            gogo=currentGogo,
                            barline=currentBarline,
                            time_sig=[currentDividend, currentDivisor],
                            subdivisions=len(measureTJA.notes),
                            pos_start=data.pos
                        )

                else:
                    print(f"Unexpected event type: {data.name}")

            measureTJAProcessed.pos_end = len(measureTJA.notes)
            tjaBranchesProcessed[branchName].append(measureTJAProcessed)

    hasBranches = all(len(b) for b in tjaBranchesProcessed.values())
    if hasBranches:
        branch_lens = [len(b) for b in tja.branches.values()]
        if not branch_lens.count(branch_lens[0]) == len(branch_lens):
            raise ValueError("Branches do not have the same number of measures.")
        else:
            branchCorrected_lens = [len(b) for b in tjaBranchesProcessed.values()]
            if not branchCorrected_lens.count(branchCorrected_lens[0]) == len(branchCorrected_lens):
                raise ValueError("Branches do not have matching GOGO/SCROLL/BPM commands.")

    return tjaBranchesProcessed


def convertTJAToFumen(tja):
    # Preprocess commands
    processedTJABranches = processTJACommands(tja)

    # Pre-allocate the measures for the converted TJA
    fumen = FumenCourse(
        measures=len(processedTJABranches['normal']),
        hasBranches=all([len(b) for b in processedTJABranches.values()]),
        scoreInit=tja.scoreInit,
        scoreDiff=tja.scoreDiff,
    )

    # Iterate through the different branches in the TJA
    for currentBranch, branchMeasuresTJAProcessed in processedTJABranches.items():
        if not len(branchMeasuresTJAProcessed):
            continue
        total_notes = 0
        total_notes_branch = 0
        note_counter_branch = 0
        currentDrumroll = None
        courseBalloons = tja.balloon.copy()

        # Iterate through the measures within the branch
        for idx_m, measureTJAProcessed in enumerate(branchMeasuresTJAProcessed):
            # Fetch a pair of measures
            measureFumenPrev = fumen.measures[idx_m-1] if idx_m != 0 else None
            measureFumen = fumen.measures[idx_m]

            # Copy over basic measure properties from the TJA (that don't depend on notes or commands)
            measureFumen.branches[currentBranch].speed = measureTJAProcessed.scroll
            measureFumen.gogo = measureTJAProcessed.gogo
            measureFumen.bpm = measureTJAProcessed.bpm

            # Compute the duration of the measure
            # First, we compute the duration for a full 4/4 measure
            measureDurationFullMeasure = 4 * 60_000 / measureTJAProcessed.bpm
            # Next, we adjust this duration based on both:
            #   1. The *actual* measure size (e.g. #MEASURE 1/8, #MEASURE 5/4, etc.)
            measureSize = measureTJAProcessed.time_sig[0] / measureTJAProcessed.time_sig[1]
            #   2. Whether this is a "submeasure" (i.e. it contains mid-measure commands, which split up the measure)
            #      - If this is a submeasure, then `measureLength` will be less than the total number of subdivisions.
            measureLength = measureTJAProcessed.pos_end - measureTJAProcessed.pos_start
            #      - In other words, `measureRatio` will be less than 1.0:
            measureRatio = (1.0 if measureTJAProcessed.subdivisions == 0.0  # Avoid division by 0 for empty measures
                            else (measureLength / measureTJAProcessed.subdivisions))
            # Apply the 2 adjustments to the measure duration
            measureFumen.duration = measureDuration = measureDurationFullMeasure * measureSize * measureRatio

            # Compute the millisecond offsets for the start and end of each measure
            #  - Start: When the notes first appear on screen (to the right)
            #  - End:   When the notes arrive at the judgment line, and the note gets hit.
            if idx_m == 0:
                measureFumen.fumenOffsetStart = (tja.offset * 1000 * -1) - measureDurationFullMeasure
            else:
                # First, start the measure using the end timing of the previous measure (plus any #DELAY commands)
                measureFumen.fumenOffsetStart = measureFumenPrev.fumenOffsetEnd + measureTJAProcessed.delay
                # Next, adjust the start timing to account for #BPMCHANGE commands (!!! Discovered by tana :3 !!!)
                # To understand what's going on here, imagine the following simple example:
                #   * You have a very slow-moving note (i.e. low BPM), like the big DON in Donkama 2000.
                #   * All the other notes move fast (i.e. high BPM), moving past the big slow note.
                #   * To get this overlapping to work, you need the big slow note to START EARLY, but also END LATE:
                #      - An early start means you need to subtract a LOT of time from the starting fumenOffset.
                #      - Thankfully, the low BPM of the slow note will create a HUGE `measureOffsetAdjustment`,
                #        since we are dividing by the BPMs, and dividing by a small number will result in a big number.
                measureOffsetAdjustment = (4 * 60_000 / measureFumen.bpm) - (4 * 60_000 / measureFumenPrev.bpm)
                #      - When we subtract this adjustment from the fumenOffsetStart, we get the "START EARLY" part:
                measureFumen.fumenOffsetStart -= measureOffsetAdjustment
                #      - The low BPM of the slow note will also create a HUGE measure duration.
                #      - When we add this long duration to the EARLY START, we end up with the "END LATE" part:
            measureFumen.fumenOffsetEnd = measureFumen.fumenOffsetStart + measureFumen.duration

            # Best guess at what 'barline' status means for each measure:
            # - 'True' means the measure lands on a barline (i.e. most measures), and thus barline should be shown
            # - 'False' means that the measure doesn't land on a barline, and thus barline should be hidden.
            #   For example:
            #     1. Measures where #BARLINEOFF has been set
            #     2. Sub-measures that don't fall on the barline
            if measureTJAProcessed.barline is False or (measureRatio != 1.0 and measureTJAProcessed.pos_start != 0):
                measureFumen.barline = False

            # Check to see if the measure contains a branching condition
            if measureTJAProcessed.branchStart:
                # Determine which values to assign based on the type of branching condition
                if measureTJAProcessed.branchStart[0] == 'p':
                    vals = [int(total_notes_branch * v * 20) if 0 <= v <= 1  # Ensure value is actually a percentage
                            else int(v * 100)                                # If it's not, pass the value as-is
                            for v in measureTJAProcessed.branchStart[1:]]
                elif measureTJAProcessed.branchStart[0] == 'r':
                    vals = measureTJAProcessed.branchStart[1:]
                # Determine which bytes to assign the values to
                if currentBranch == 'normal':
                    idx_b1, idx_b2 = 0, 1
                elif currentBranch == 'advanced':
                    idx_b1, idx_b2 = 2, 3
                elif currentBranch == 'master':
                    idx_b1, idx_b2 = 4, 5
                # Assign the values to their intended bytes
                measureFumen.branchInfo[idx_b1] = vals[0]
                measureFumen.branchInfo[idx_b2] = vals[1]
                # Reset the note counter corresponding to this branch
                total_notes_branch = 0
            total_notes_branch += note_counter_branch

            # Create notes based on TJA measure data
            note_counter_branch = 0
            note_counter = 0
            for idx_d, data in enumerate(measureTJAProcessed.data):
                if data.name == 'note':
                    note = FumenNote()
                    # Note positions must be calculated using the base measure duration (that uses a single BPM value)
                    # (In other words, note positions do not take into account any mid-measure BPM change adjustments.)
                    note.pos = measureDuration * (data.pos - measureTJAProcessed.pos_start) / measureLength
                    # Handle the note that represents the end of a drumroll/balloon
                    if data.value == "EndDRB":
                        # If a drumroll spans a single measure, then add the difference between start/end position
                        if not currentDrumroll.multimeasure:
                            currentDrumroll.duration += (note.pos - currentDrumroll.pos)
                        # Otherwise, if a drumroll spans multiple measures, then we want to add the duration between
                        # the start of the measure (i.e. pos=0.0) and the drumroll's end position.
                        else:
                            currentDrumroll.duration += (note.pos - 0.0)
                        # 1182, 1385, 1588, 2469, 1568, 752, 1568
                        currentDrumroll.duration = float(int(currentDrumroll.duration))
                        currentDrumroll = None
                        continue
                    # The TJA spec technically allows you to place double-Kusudama notes:
                    #    "Use another 9 to specify when to lower the points for clearing."
                    # But this is unsupported in fumens, so just skip the second Kusudama note.
                    if data.value == "Kusudama" and currentDrumroll:
                        continue
                    # Handle the remaining non-EndDRB, non-double Kusudama notes
                    note.type = data.value
                    note.scoreInit = tja.scoreInit
                    note.scoreDiff = tja.scoreDiff
                    # Handle drumroll/balloon-specific metadata
                    if note.type in ["Balloon", "Kusudama"]:
                        note.hits = courseBalloons.pop(0)
                        currentDrumroll = note
                        total_notes -= 1
                    if note.type in ["Drumroll", "DRUMROLL"]:
                        currentDrumroll = note
                        total_notes -= 1
                    # Count dons, kas, and balloons for the purpose of tracking branching accuracy
                    if note.type.lower() in ['don', 'ka']:
                        note_counter_branch += 1
                    elif note.type.lower() in ['balloon', 'kusudama']:
                        note_counter_branch += 1.5
                    measureFumen.branches[currentBranch].notes.append(note)
                    note_counter += 1

            # If drumroll hasn't ended by the end of this measure, increase duration by measure timing
            if currentDrumroll:
                if currentDrumroll.duration == 0.0:
                    currentDrumroll.duration += (measureDuration - currentDrumroll.pos)
                    currentDrumroll.multimeasure = True
                else:
                    currentDrumroll.duration += measureDuration

            measureFumen.branches[currentBranch].length = note_counter
            total_notes += note_counter

    # Take a stock header metadata sample and add song-specific metadata
    fumen.headerMetadata[8] = DIFFICULTY_BYTES[tja.course][0]
    fumen.headerMetadata[9] = DIFFICULTY_BYTES[tja.course][1]
    soulGaugeBytes = computeSoulGaugeBytes(
        n_notes=total_notes,
        difficulty=tja.course,
        stars=tja.level
    )
    fumen.headerMetadata[12] = soulGaugeBytes[0]
    fumen.headerMetadata[13] = soulGaugeBytes[1]
    fumen.headerMetadata[16] = soulGaugeBytes[2]
    fumen.headerMetadata[17] = soulGaugeBytes[3]
    fumen.headerMetadata[20] = soulGaugeBytes[4]
    fumen.headerMetadata[21] = soulGaugeBytes[5]
    fumen.headerMetadata = b"".join(i.to_bytes(1, 'little') for i in fumen.headerMetadata)

    return fumen
