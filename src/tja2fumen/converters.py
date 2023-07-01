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
    'fumenOffset': 0.0,
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
                           'subdivisions': len(measure['data']), 'pos_start': 0, 'pos_end': 0,
                           'branchStart': None, 'time_sig': [currentDividend, currentDivisor], 'data': []}
            for data in measure['combined']:
                # Handle note data
                if data['type'] == 'note':
                    measure_cur['data'].append(data)

                # Handle commands that can only be placed between measures (i.e. no mid-measure variations)
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
                                       'barline': currentBarline,
                                       'subdivisions': len(measure['data']), 'pos_start': data['pos'], 'pos_end': 0,
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
    # Parse TJA measures to create converted TJA -> Fumen file
    tjaConverted = {'measures': [deepcopy(default_measure) for _ in range(len(tja['branches']['normal']))]}
    for currentBranch, branch in tja['branches'].items():
        if not len(branch):
            continue
        total_notes = 0
        total_notes_branch = 0
        note_counter_branch = 0
        measureDurationPrev = 0
        currentDrumroll = None
        courseBalloons = tja['metadata']['balloon'].copy()
        for idx_m, measureTJA in enumerate(branch):
            measureFumen = tjaConverted['measures'][idx_m]

            # Check to see if the measure contains a branching condition
            if measureTJA['branchStart']:
                measureFumen['branchStart'] = measureTJA['branchStart']
            if measureFumen['branchStart']:
                if measureFumen['branchStart'][0] == 'p':
                    if currentBranch == 'normal':
                        idx_b1, idx_b2 = 0, 1
                    elif currentBranch == 'advanced':
                        idx_b1, idx_b2 = 2, 3
                    elif currentBranch == 'master':
                        idx_b1, idx_b2 = 4, 5
                    measureFumen['branchInfo'][idx_b1] = int(total_notes_branch * measureFumen['branchStart'][1] * 20)
                    measureFumen['branchInfo'][idx_b2] = int(total_notes_branch * measureFumen['branchStart'][2] * 20)
                elif measureTJA['branchStart'][0] == 'r':
                    pass
                total_notes_branch = 0
            total_notes_branch += note_counter_branch

            # Compute the duration of the measure
            measureSize = measureTJA['time_sig'][0] / measureTJA['time_sig'][1]
            measureLength = measureTJA['pos_end'] - measureTJA['pos_start']
            measureRatio = 1.0 if measureTJA['subdivisions'] == 0.0 else (measureLength / measureTJA['subdivisions'])
            # - measureDurationBase: The "base" measure duration, computed using a single BPM value.
            # - measureDuration: The actual measure duration, which may be adjusted if there is a mid-measure BPM change.
            measureDurationBase = measureDuration = (4 * 60_000 * measureSize * measureRatio / measureTJA['bpm'])
            # The following adjustment accounts for BPM changes. (!!! Discovered by tana :3 !!!)
            if idx_m != len(branch)-1:
                measureTJANext = branch[idx_m + 1]
                if measureTJA['bpm'] != measureTJANext['bpm']:
                    measureDuration -= (4 * 60_000 * ((1 / measureTJANext['bpm']) - (1 / measureTJA['bpm'])))

            # Compute the millisecond offset for each measure
            if idx_m == 0:
                pass  # NB: Pass for now, since we need the 2nd measure's duration to compute the 1st measure's offset
            else:
                # Compute the 1st measure's offset by subtracting the 2nd measure's duration from the tjaOffset
                if idx_m == 1:
                    tjaOffset = float(tja['metadata']['offset']) * 1000 * -1
                    tjaConverted['measures'][idx_m-1]['fumenOffset'] = tjaOffset - measureDurationPrev
                # Use the previous measure's offset plus the previous duration to compute the current measure's offset
                measureOffsetPrev = tjaConverted['measures'][idx_m-1]['fumenOffset']
                measureFumen['fumenOffset'] = measureOffsetPrev + measureDurationPrev
            measureDurationPrev = measureDuration

            # Best guess at what 'barline' status means for each measure:
            # - 'True' means the measure lands on a barline (i.e. most measures), and thus barline should be shown
            # - 'False' means that the measure doesn't land on a barline, and thus barline should be hidden.
            #   For example:
            #     1. Measures where #BARLINEOFF has been set
            #     2. Sub-measures that don't fall on the barline
            if measureTJA['barline'] is False or (measureRatio != 1.0 and measureTJA['pos_start'] != 0):
                measureFumen['barline'] = False

            # Create note dictionaries based on TJA measure data (containing 0's plus 1/2/3/4/etc. for notes)
            note_counter_branch = 0
            note_counter = 0
            for idx_d, data in enumerate(measureTJA['data']):
                if data['type'] == 'note':
                    # Note positions must be calculated using the base measure duration (that uses a single BPM value)
                    # (In other words, note positions do not take into account any mid-measure BPM change adjustments.)
                    note_pos = measureDurationBase * (data['pos'] - measureTJA['pos_start']) / measureLength
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
            measureFumen[currentBranch]['length'] = note_counter
            measureFumen[currentBranch]['speed'] = measureTJA['scroll']
            measureFumen['gogo'] = measureTJA['gogo']
            measureFumen['bpm'] = measureTJA['bpm']

            # If drumroll hasn't ended by the end of this measure, increase duration by measure timing
            if currentDrumroll:
                if currentDrumroll['duration'] == 0.0:
                    currentDrumroll['duration'] += (measureDurationBase - currentDrumroll['pos'])
                    currentDrumroll['multimeasure'] = True
                else:
                    currentDrumroll['duration'] += measureDurationBase

            total_notes += note_counter

    # Take a stock header metadata sample and add song-specific metadata
    headerMetadata = sampleHeaderMetadata.copy()
    headerMetadata[8] = DIFFICULTY_BYTES[tja['metadata']['course']][0]
    headerMetadata[9] = DIFFICULTY_BYTES[tja['metadata']['course']][1]
    headerMetadata[20], headerMetadata[21] = computeSoulGaugeBytes(
        n_notes=total_notes,
        difficulty=tja['metadata']['course'],
        stars=tja['metadata']['level']
    )
    tjaConverted['headerMetadata'] = b"".join(i.to_bytes(1, 'little') for i in headerMetadata)
    tjaConverted['headerPadding'] = simpleHeaders[0]  # Use a basic, known set of header bytes
    tjaConverted['order'] = '<'
    tjaConverted['unknownMetadata'] = 0
    tjaConverted['branches'] = all([len(b) for b in tja['branches'].values()])
    tjaConverted['scoreInit'] = tja['metadata']['scoreInit']
    tjaConverted['scoreDiff'] = tja['metadata']['scoreDiff']

    return tjaConverted
