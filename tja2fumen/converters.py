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
    'hidden': True,
    'padding1': 0,
    'branchInfo': [-1, -1, -1, -1, -1, -1],
    'padding2': 0,
    'normal': deepcopy(default_branch),
    'advanced': deepcopy(default_branch),
    'master': deepcopy(default_branch)
}


def preprocessTJAMeasures(tja):
    """
    Merge TJA 'data' and 'event' fields into a single measure property, and split
    measures into sub-measures whenever a mid-measure BPM change occurs.

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
    currentBPM = 0
    currentScroll = 1.0
    currentGogo = False

    measuresCorrected = []
    for measure in tja['measures']:
        # Step 1: Combine notes and events
        notes = [{'pos': i, 'type': 'note', 'value': TJA_NOTE_TYPES[note]}
                 for i, note in enumerate(measure['data']) if note != '0']
        events = [{'pos': e['position'], 'type': e['name'], 'value': e['value']}
                  for e in measure['events']]
        combined = []
        while notes or events:
            if events and notes:
                if notes[0]['pos'] >= events[0]['pos']:
                    combined.append(events.pop(0))
                else:
                    combined.append(notes.pop(0))
            elif events:
                combined.append(events.pop(0))
            elif notes:
                combined.append(notes.pop(0))

        # Step 2: Split measure into submeasure
        measure_cur = {'bpm': currentBPM, 'scroll': currentScroll, 'gogo': currentGogo,
                       'subdivisions': len(measure['data']), 'pos_start': 0, 'pos_end': 0,
                       'time_sig': measure['length'], 'data': [], 'properties': measure['properties']}
        for data in combined:
            if data['type'] == 'note':
                measure_cur['data'].append(data)
            elif data['type'] == 'bpm':
                currentBPM = float(data['value'])
                # Case 1: BPM change at the start of a measure; just change BPM
                if data['pos'] == 0:
                    measure_cur['bpm'] = currentBPM
                # Case 2: BPM change mid-measure, so start a new sub-measure
                else:
                    measure_cur['pos_end'] = data['pos']
                    measuresCorrected.append(measure_cur)
                    measure_cur = {'bpm': currentBPM, 'scroll': currentScroll, 'gogo': currentGogo,
                                   'subdivisions': len(measure['data']), 'pos_start': data['pos'], 'pos_end': 0,
                                   'time_sig': measure['length'], 'data': [], 'properties': measure['properties']}
            elif data['type'] == 'scroll':
                currentScroll = data['value']
                measure_cur['scroll'] = currentScroll
            elif data['type'] == 'gogo':
                currentGogo = bool(data['value'])
                measure_cur['gogo'] = currentGogo
            elif data['type'] == 'barline':
                pass
            else:
                print(f"Unexpected event type: {data['type']}")
        measure_cur['pos_end'] = len(measure['data'])
        measuresCorrected.append(measure_cur)

    return measuresCorrected


def convertTJAToFumen(fumen, tja):
    # Hardcode currentBranch due to current lack of support for branching songs
    currentBranch = 'normal'  # TODO: Program in branch support
    fumen['measures'] = fumen['measures'][9:]
    tja['measures'] = preprocessTJAMeasures(tja)

    # Parse TJA measures to create converted TJA -> Fumen file
    tjaConverted = {'measures': []}
    for idx_m, measureTJA in enumerate(tja['measures']):
        measureFumen = deepcopy(default_measure)

        # Compute the fumenOffset change (i.e. the duration of the measure).
        measureSize = measureTJA['time_sig'][0] / measureTJA['time_sig'][1]
        measureLength = measureTJA['pos_end'] - measureTJA['pos_start']
        measureRatio = 1.0 if measureTJA['subdivisions'] == 0.0 else (measureLength / measureTJA['subdivisions'])
        # - measureDurationBase: The "base" measure duration, computed using a single BPM value.
        # - measureDuration: The actual measure duration, which may be adjusted if there is a mid-measure BPM change.
        measureDurationBase = measureDuration = (4 * 60_000 * measureSize * measureRatio / measureTJA['bpm'])
        # The following adjustment accounts for mid-measure BPM changes. (!!! Discovered by tana :3 !!!)
        if measureRatio != 1.0:
            measureTJANext = tja['measures'][idx_m+1]
            measureDuration -= (4 * 60_000 * ((1 / measureTJANext['bpm']) - (1 / measureTJA['bpm'])))

        # Apply the change in offset to the overall offset to get the measure offset
        # This is a bodge I'm using just for Rokuchounen to Ichiya Monogatari
        # Its first measure happens _before_ the first barline
        # So, we actually need to shift the offsets by 1 to get everything to line up
        if idx_m == 0:
            # Compute fumen offset for the first measure that has a barline
            fumenOffset = float(tja['metadata']['offset']) * -1000
            measureFumen['fumenOffset'] = fumenOffset - measureDuration
        else:
            # Just refer back to the previous offset
            measureOffsetPrev = tjaConverted['measures'][-1]['fumenOffset']
            measureFumen['fumenOffset'] = measureOffsetPrev + measureDurationNext
        measureDurationNext = measureDuration

        # Best guess at what 'hidden' status means for each measure:
        # - 'True' means the measure lands on a barline (i.e. most measures)
        # - 'False' means that the measure is between barlines. For example:
        #     1. Measures before the first barline
        #     2. Sub-measures that don't fall on the barline
        if idx_m == 0 or (measureRatio != 1.0 and measureTJA['pos_start'] != 0):
            measureFumen['hidden'] = False

        # Create note dictionaries based on TJA measure data (containing 0's plus 1/2/3/4/etc. for notes)
        note_counter = 0
        for idx_d, data in enumerate(measureTJA['data']):
            if data['type'] == 'note':
                note = deepcopy(default_note)
                # Note positions must be calculated using the base measure duration (that uses a single BPM value)
                # (In other words, note positions do not take into account any mid-measure BPM change adjustments.)
                note['pos'] = measureDurationBase * (data['pos'] - measureTJA['pos_start']) / measureLength
                note['type'] = data['value']  # TODO: Handle BALLOON/DRUMROLL
                note['scoreInit'] = tja['scoreInit']  # Probably not fully accurate
                note['scoreDiff'] = tja['scoreDiff']  # Probably not fully accurate
                measureFumen[currentBranch][note_counter] = note
                note_counter += 1
        measureFumen[currentBranch]['length'] = note_counter
        measureFumen[currentBranch]['speed'] = measureTJA['scroll']
        measureFumen['gogo'] = measureTJA['gogo']
        measureFumen['bpm'] = measureTJA['bpm']

        # Append the measure to the tja's list of measures
        tjaConverted['measures'].append(measureFumen)

    tjaConverted['headerUnknown'] = b'x\00' * 80
    tjaConverted['order'] = '<'
    tjaConverted['length'] = len(tjaConverted['measures'])
    tjaConverted['unknownMetadata'] = 0
    tjaConverted['branches'] = False

    return tjaConverted
