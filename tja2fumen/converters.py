from copy import deepcopy

from constants import TJA_NOTE_TYPES

# Filler metadata that the `writeFumen` function expects
default_note = {'type': '', 'pos': 0.0, 'item': 0, 'padding': 0.0,
                'scoreInit': 0, 'scoreDiff': 0, 'durationPadding': 0.0}
default_branch = {'length': 0, 'padding': 0, 'speed': 1.0}
default_measure = {
    'bpm': 0.0,
    'fumenOffset': 0.0,
    'gogo': False,
    'hidden': False,
    'padding1': 0,
    'branchInfo': [-1, -1, -1, -1, -1, -1],
    'padding2': 0,
    'normal': deepcopy(default_branch),
    'advanced': deepcopy(default_branch),
    'master': deepcopy(default_branch)
}


def convertTJAToFumen(fumen, tja):
    # Fumen offset for the first measure that has a barline
    fumenOffset1 = float(tja['metadata']['offset']) * -1000

    # Variables that will change over time due to events
    currentBPM = 0.0
    currentGogo = False
    currentHidden = False
    currentBranch = 'normal'  # TODO: Program in branch support

    # Parse TJA measures to create converted TJA -> Fumen file
    tjaConverted = {'measures': []}
    for i, measureTJA in enumerate(tja['measures']):
        measureFumenExample = fumen['measures'][i+9]
        measureFumen = deepcopy(default_measure)

        # TODO Event: GOGOTIME

        # TODO Event: HIDDEN

        # TODO Event: BARLINE

        # TODO Event: MEASURE

        # Event: BPMCHANGE
        # TODO: Handle TJA measure being broken up into multiple Fumen measures due to mid-measure BPM changes
        midMeasureBPM = [(0, currentBPM)]
        for event in measureTJA['events']:
            if event['name'] == 'bpm':
                currentBPM = float(event['value'])
                if event['position'] == 0:
                    midMeasureBPM[0] = (0, currentBPM,)
                else:
                    midMeasureBPM.append((event['position'], currentBPM))
        if len(midMeasureBPM) > 1:
            test = None
        measureFumen['bpm'] = currentBPM

        # TODO: `measureFumen['fumenOffset']
        #       Will need to account for BARLINEON and BARLINEOFF.
        #       Some examples that line up with actual fumen data:
        # fumenOffset0 = (fumenOffset1 - measureLength)
        # fumenOffset2 = (fumenOffset1 + measureLength)
        measureLength = 240_000 / currentBPM
        # measureFumen['fumenOffset'] = prev['fumenOffset'] + measureLength

        # Create note dictionaries based on TJA measure data (containing 0's plus 1/2/3/4/etc. for notes)
        note_counter = 0
        for i, note_value in enumerate(measureTJA['data']):
            if note_value != '0':
                note = deepcopy(default_note)
                note['pos'] = measureLength * (i / len(measureTJA['data']))
                note['type'] = TJA_NOTE_TYPES[note_value]  # TODO: Handle BALLOON/DRUMROLL
                note['scoreInit'] = tja['scoreInit']  # Probably not fully accurate
                note['scoreDiff'] = tja['scoreDiff']  # Probably not fully accurate
                measureFumen[currentBranch][note_counter] = note
                note_counter += 1
        measureFumen[currentBranch]['length'] = note_counter

        # Append the measure to the tja's list of measures
        tjaConverted['measures'].append(measureFumen)

    tjaConverted['headerUnknown'] = b'x\00' * 80
    tjaConverted['order'] = '<'
    tjaConverted['length'] = len(tjaConverted['measures'])
    tjaConverted['unknownMetadata'] = 0
    tjaConverted['branches'] = False

    return tjaConverted
