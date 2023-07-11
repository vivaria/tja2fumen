from copy import deepcopy
import re

from tja2fumen.utils import computeSoulGaugeBytes
from tja2fumen.constants import DIFFICULTY_BYTES, sampleHeaderMetadata, simpleHeaders

# Filler metadata that the `writeFumen` function expects
# TODO: Determine how to properly set the item byte (https://github.com/vivaria/tja2fumen/issues/17)
default_note = {'type': '', 'pos': 0.0, 'item': 0, 'padding': 0.0,
                'scoreInit': 0, 'scoreDiff': 0, 'duration': 0.0}
default_branch = {'length': 0, 'padding': 0, 'speed': 1.0}
default_measure = {
    'bpm': 0.0,
    'fumenOffsetStart': 0.0,
    'fumenOffsetEnd': 0.0,
    'duration': 0.0,
    'gogo': False,
    'barline': True,
    'padding1': 0,
    'branchStart': None,
    'branchInfo': [-1, -1, -1, -1, -1, -1],
    'padding2': 0,
    'normal': deepcopy(default_branch),
    'advanced': deepcopy(default_branch),
    'master': deepcopy(default_branch)
}


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
    branches = tja['branches']
    branchesCorrected = {branchName: [] for branchName in branches.keys()}
    for branchName, branch in branches.items():
        currentBPM = float(tja['metadata']['bpm'])
        currentScroll = 1.0
        currentGogo = False
        currentBarline = True
        currentDividend = 4
        currentDivisor = 4
        for measure in branch:
            # Split measure into submeasure
            measure_cur = {'bpm': currentBPM, 'scroll': currentScroll, 'gogo': currentGogo, 'barline': currentBarline,
                           'subdivisions': len(measure['data']), 'pos_start': 0, 'pos_end': 0, 'delay': 0,
                           'branchStart': None, 'time_sig': [currentDividend, currentDivisor], 'data': []}
            for data in measure['combined']:
                # Handle note data
                if data['type'] == 'note':
                    measure_cur['data'].append(data)

                # Handle commands that can only be placed between measures (i.e. no mid-measure variations)
                elif data['type'] == 'delay':
                    measure_cur['delay'] = data['value'] * 1000  # ms -> s
                elif data['type'] == 'branchStart':
                    measure_cur['branchStart'] = data['value']
                elif data['type'] == 'barline':
                    currentBarline = bool(int(data['value']))
                    measure_cur['barline'] = currentBarline
                elif data['type'] == 'measure':
                    matchMeasure = re.match(r"(\d+)/(\d+)", data['value'])
                    if not matchMeasure:
                        continue
                    currentDividend = int(matchMeasure.group(1))
                    currentDivisor = int(matchMeasure.group(2))
                    measure_cur['time_sig'] = [currentDividend, currentDivisor]

                # Handle commands that can be placed in the middle of a measure.
                #    NB: For fumen files, if there is a mid-measure change to BPM/SCROLL/GOGO, then the measure will
                #    actually be split into two small submeasures. So, we need to start a new measure in those cases.
                elif data['type'] in ['bpm', 'scroll', 'gogo']:
                    # Parse the values
                    if data['type'] == 'bpm':
                        new_val = currentBPM = float(data['value'])
                    elif data['type'] == 'scroll':
                        new_val = currentScroll = data['value']
                    elif data['type'] == 'gogo':
                        new_val = currentGogo = bool(int(data['value']))
                    # Check for mid-measure commands
                    # - Case 1: Command happens at the start of a measure; just change the value directly
                    if data['pos'] == 0:
                        measure_cur[data['type']] = new_val
                    # - Case 2: Command occurs mid-measure, so start a new sub-measure
                    else:
                        measure_cur['pos_end'] = data['pos']
                        branchesCorrected[branchName].append(measure_cur)
                        measure_cur = {'bpm': currentBPM, 'scroll': currentScroll, 'gogo': currentGogo,
                                       'barline': currentBarline, 'subdivisions': len(measure['data']),
                                       'pos_start': data['pos'], 'pos_end': 0, 'delay': 0,
                                       'branchStart': None, 'time_sig': [currentDividend, currentDivisor], 'data': []}

                else:
                    print(f"Unexpected event type: {data['type']}")

            measure_cur['pos_end'] = len(measure['data'])
            branchesCorrected[branchName].append(measure_cur)

    hasBranches = all(len(b) for b in branchesCorrected.values())
    if hasBranches:
        branch_lens = [len(b) for b in branches.values()]
        if not branch_lens.count(branch_lens[0]) == len(branch_lens):
            raise ValueError("Branches do not have the same number of measures.")
        else:
            branchCorrected_lens = [len(b) for b in branchesCorrected.values()]
            if not branchCorrected_lens.count(branchCorrected_lens[0]) == len(branchCorrected_lens):
                raise ValueError("Branches do not have matching GOGO/SCROLL/BPM commands.")

    return branchesCorrected


def convertTJAToFumen(tja):
    # Preprocess commands
    tja['branches'] = processTJACommands(tja)

    # Pre-allocate the measures for the converted TJA
    tjaConverted = {'measures': [deepcopy(default_measure) for _ in range(len(tja['branches']['normal']))]}

    # Iterate through the different branches in the TJA
    for currentBranch, branch in tja['branches'].items():
        if not len(branch):
            continue
        total_notes = 0
        total_notes_branch = 0
        note_counter_branch = 0
        currentDrumroll = None
        courseBalloons = tja['metadata']['balloon'].copy()

        # Iterate through the measures within the branch
        for idx_m, measureTJA in enumerate(branch):
            # Fetch a pair of measures
            measureFumenPrev = tjaConverted['measures'][idx_m-1] if idx_m != 0 else None
            measureFumen = tjaConverted['measures'][idx_m]

            # Copy over basic measure properties from the TJA (that don't depend on notes or commands)
            measureFumen[currentBranch]['speed'] = measureTJA['scroll']
            measureFumen['gogo'] = measureTJA['gogo']
            measureFumen['bpm'] = measureTJA['bpm']

            # Compute the duration of the measure
            # First, we compute the duration for a full 4/4 measure
            measureDurationFullMeasure = 4 * 60_000 / measureTJA['bpm']
            # Next, we adjust this duration based on both:
            #   1. The *actual* measure size (e.g. #MEASURE 1/8, #MEASURE 5/4, etc.)
            measureSize = measureTJA['time_sig'][0] / measureTJA['time_sig'][1]
            #   2. Whether this is a "submeasure" (i.e. it contains mid-measure commands, which split up the measure)
            #      - If this is a submeasure, then `measureLength` will be less than the total number of subdivisions.
            measureLength = measureTJA['pos_end'] - measureTJA['pos_start']
            #      - In other words, `measureRatio` will be less than 1.0:
            measureRatio = (1.0 if measureTJA['subdivisions'] == 0.0  # Avoid division by 0 for empty measures
                            else (measureLength / measureTJA['subdivisions']))
            # Apply the 2 adjustments to the measure duration
            measureFumen['duration'] = measureDuration = measureDurationFullMeasure * measureSize * measureRatio

            # Compute the millisecond offsets for the start and end of each measure
            #  - Start: When the notes first appear on screen (to the right)
            #  - End:   When the notes arrive at the judgment line, and the note gets hit.
            if idx_m == 0:
                tjaOffset = float(tja['metadata']['offset']) * 1000 * -1
                measureFumen['fumenOffsetStart'] = tjaOffset - measureDurationFullMeasure
            else:
                # First, start the measure using the end timing of the previous measure (plus any #DELAY commands)
                measureFumen['fumenOffsetStart'] = measureFumenPrev['fumenOffsetEnd'] + measureTJA['delay']
                # Next, adjust the start timing to account for #BPMCHANGE commands (!!! Discovered by tana :3 !!!)
                # To understand what's going on here, imagine the following simple example:
                #   * You have a very slow-moving note (i.e. low BPM), like the big DON in Donkama 2000.
                #   * All the other notes move fast (i.e. high BPM), moving past the big slow note.
                #   * To get this overlapping to work, you need the big slow note to START EARLY, but also END LATE:
                #      - An early start means you need to subtract a LOT of time from the starting fumenOffset.
                #      - Thankfully, the low BPM of the slow note will create a HUGE `measureOffsetAdjustment`,
                #        since we are dividing by the BPMs, and dividing by a small number will result in a big number.
                measureOffsetAdjustment = (4 * 60_000 / measureTJA['bpm']) - (4 * 60_000 / measureFumenPrev['bpm'])
                #      - When we subtract this adjustment from the fumenOffsetStart, we get the "START EARLY" part:
                measureFumen['fumenOffsetStart'] -= measureOffsetAdjustment
                #      - The low BPM of the slow note will also create a HUGE measure duration.
                #      - When we add this long duration to the EARLY START, we end up with the "END LATE" part:
            measureFumen['fumenOffsetEnd'] = measureFumen['fumenOffsetStart'] + measureFumen['duration']

            # Best guess at what 'barline' status means for each measure:
            # - 'True' means the measure lands on a barline (i.e. most measures), and thus barline should be shown
            # - 'False' means that the measure doesn't land on a barline, and thus barline should be hidden.
            #   For example:
            #     1. Measures where #BARLINEOFF has been set
            #     2. Sub-measures that don't fall on the barline
            if measureTJA['barline'] is False or (measureRatio != 1.0 and measureTJA['pos_start'] != 0):
                measureFumen['barline'] = False

            # Check to see if the measure contains a branching condition
            if measureTJA['branchStart']:
                # Determine which values to assign based on the type of branching condition
                if measureTJA['branchStart'][0] == 'p':
                    vals = [int(total_notes_branch * v * 20) if 0 <= v <= 1  # Ensure value is actually a percentage
                            else int(v * 100)                                # If it's not, pass the value as-is
                            for v in measureTJA['branchStart'][1:]]
                elif measureTJA['branchStart'][0] == 'r':
                    vals = measureTJA['branchStart'][1:]
                # Determine which bytes to assign the values to
                if currentBranch == 'normal':
                    idx_b1, idx_b2 = 0, 1
                elif currentBranch == 'advanced':
                    idx_b1, idx_b2 = 2, 3
                elif currentBranch == 'master':
                    idx_b1, idx_b2 = 4, 5
                # Assign the values to their intended bytes
                measureFumen['branchInfo'][idx_b1] = vals[0]
                measureFumen['branchInfo'][idx_b2] = vals[1]
                # Reset the note counter corresponding to this branch
                total_notes_branch = 0
            total_notes_branch += note_counter_branch

            # Create note dictionaries based on TJA measure data (containing 0's plus 1/2/3/4/etc. for notes)
            note_counter_branch = 0
            note_counter = 0
            for idx_d, data in enumerate(measureTJA['data']):
                if data['type'] == 'note':
                    # Note positions must be calculated using the base measure duration (that uses a single BPM value)
                    # (In other words, note positions do not take into account any mid-measure BPM change adjustments.)
                    note_pos = measureDuration * (data['pos'] - measureTJA['pos_start']) / measureLength
                    # Handle the note that represents the end of a drumroll/balloon
                    if data['value'] == "EndDRB":
                        # If a drumroll spans a single measure, then add the difference between start/end position
                        if 'multimeasure' not in currentDrumroll.keys():
                            currentDrumroll['duration'] += (note_pos - currentDrumroll['pos'])
                        # Otherwise, if a drumroll spans multiple measures, then we want to add the duration between
                        # the start of the measure (i.e. pos=0.0) and the drumroll's end position.
                        else:
                            currentDrumroll['duration'] += (note_pos - 0.0)
                        # 1182, 1385, 1588, 2469, 1568, 752, 1568
                        currentDrumroll['duration'] = float(int(currentDrumroll['duration']))
                        currentDrumroll = None
                        continue
                    # The TJA spec technically allows you to place double-Kusudama notes:
                    #    "Use another 9 to specify when to lower the points for clearing."
                    # But this is unsupported in fumens, so just skip the second Kusudama note.
                    if data['value'] == "Kusudama" and currentDrumroll:
                        continue
                    # Handle the remaining non-EndDRB, non-double Kusudama notes
                    note = deepcopy(default_note)
                    note['pos'] = note_pos
                    note['type'] = data['value']
                    note['scoreInit'] = tja['metadata']['scoreInit']  # Probably not fully accurate
                    note['scoreDiff'] = tja['metadata']['scoreDiff']  # Probably not fully accurate
                    # Handle drumroll/balloon-specific metadata
                    if note['type'] in ["Balloon", "Kusudama"]:
                        note['hits'] = courseBalloons.pop(0)
                        note['hitsPadding'] = 0
                        currentDrumroll = note
                        total_notes -= 1
                    if note['type'] in ["Drumroll", "DRUMROLL"]:
                        note['drumrollBytes'] = b'\x00\x00\x00\x00\x00\x00\x00\x00'
                        currentDrumroll = note
                        total_notes -= 1
                    # Count dons, kas, and balloons for the purpose of tracking branching accuracy
                    if note['type'].lower() in ['don', 'ka']:
                        note_counter_branch += 1
                    elif note['type'].lower() in ['balloon', 'kusudama']:
                        note_counter_branch += 1.5
                    measureFumen[currentBranch][note_counter] = note
                    note_counter += 1

            # If drumroll hasn't ended by the end of this measure, increase duration by measure timing
            if currentDrumroll:
                if currentDrumroll['duration'] == 0.0:
                    currentDrumroll['duration'] += (measureDuration - currentDrumroll['pos'])
                    currentDrumroll['multimeasure'] = True
                else:
                    currentDrumroll['duration'] += measureDuration

            measureFumen[currentBranch]['length'] = note_counter
            total_notes += note_counter

    # Take a stock header metadata sample and add song-specific metadata
    headerMetadata = sampleHeaderMetadata.copy()
    headerMetadata[8] = DIFFICULTY_BYTES[tja['metadata']['course']][0]
    headerMetadata[9] = DIFFICULTY_BYTES[tja['metadata']['course']][1]
    soulGaugeBytes = computeSoulGaugeBytes(
        n_notes=total_notes,
        difficulty=tja['metadata']['course'],
        stars=tja['metadata']['level']
    )
    headerMetadata[12] = soulGaugeBytes[0]
    headerMetadata[13] = soulGaugeBytes[1]
    headerMetadata[16] = soulGaugeBytes[2]
    headerMetadata[17] = soulGaugeBytes[3]
    headerMetadata[20] = soulGaugeBytes[4]
    headerMetadata[21] = soulGaugeBytes[5]
    tjaConverted['headerMetadata'] = b"".join(i.to_bytes(1, 'little') for i in headerMetadata)
    tjaConverted['headerPadding'] = simpleHeaders[0]  # Use a basic, known set of header bytes
    tjaConverted['order'] = '<'
    tjaConverted['unknownMetadata'] = 0
    tjaConverted['branches'] = all([len(b) for b in tja['branches'].values()])
    tjaConverted['scoreInit'] = tja['metadata']['scoreInit']
    tjaConverted['scoreDiff'] = tja['metadata']['scoreDiff']

    return tjaConverted
