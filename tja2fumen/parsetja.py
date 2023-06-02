# Original source: https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js

import re

# Valid strings for headers and chart commands
HEADER_GLOBAL = ['TITLE', 'TITLEJA', 'SUBTITLE', 'SUBTITLEJA', 'BPM', 'WAVE', 'OFFSET', 'DEMOSTART', 'GENRE']
HEADER_COURSE = ['COURSE', 'LEVEL', 'BALLOON', 'SCOREINIT', 'SCOREDIFF', 'TTRO' 'WBEAT']
COMMAND = ['START', 'END', 'GOGOSTART', 'GOGOEND', 'BRANCHSTART', 'BRANCHEND', 'BARLINEON', 'BARLINEOFF', 'MEASURE',
           'BPMCHANGE', 'DELAY', 'SECTION', 'N', 'E', 'M', 'LEVELHOLD', 'SCROLL', 'BMSCROLL', 'HBSCROLL', 'TTBREAK']


def getCourse(tjaHeaders, lines):
    headers = {
        "course": 'Oni',
        "level": 0,
        "balloon": [],
        "scoreInit": 100,
        "scoreDiff": 100,
        "ttRowBeat": 16,
    }

    measures = []
    measureDividend = 4
    measureDivisor = 4
    measureProperties = {}
    measureData = ''
    measureEvents = []
    currentBranch = 'N'
    targetBranch = 'N'
    flagLevelhold = False

    # Process lines
    for line in lines:
        if line["type"] == 'header':
            if line["name"] == 'COURSE':
                headers['course'] = line['value']
                
            elif line["name"] == 'LEVEL':
                headers['level'] = int(line['value'])
                
            elif line["name"] == 'BALLOON':
                if line['value']:
                    balloons = [int(v) for v in line['value'].split(",")]
                else:
                    balloons = []
                headers['balloon'] = balloons
                
            elif line["name"] == 'SCOREINIT':
                headers['scoreInit'] = int(line['value'])
                
            elif line["name"] == 'SCOREDIFF':
                headers['scoreDiff'] = int(line['value'])
                
            elif line["name"] == 'TTROWBEAT':
                headers['ttRowBeat'] = int(line['value'])

        elif line["type"] == 'command':
            if line["name"] == 'BRANCHSTART':
                if flagLevelhold:
                    continue
                values = line['value'].split(',')
                if values[0] == 'r':
                    if len(values) >= 3: 
                        targetBranch = 'M'
                    elif len(values) == 2:
                        targetBranch = 'E'
                    else:
                        targetBranch = 'N'
                elif values[0] == 'p':
                    if len(values) >= 3 and float(values[2]) <= 100:
                        targetBranch = 'M'
                    elif len(values) >= 2 and float(values[1]) <= 100:
                        targetBranch = 'E'
                    else:
                        targetBranch = 'N'

            elif line["name"] == 'BRANCHEND':
                currentBranch = targetBranch

            elif line["name"] == 'N':
                currentBranch = 'N'

            elif line["name"] == 'E':
                currentBranch = 'E'

            elif line["name"] == 'M':
                currentBranch = 'M'

            elif line["name"] == 'START':
                currentBranch = 'N'
                targetBranch = 'N'
                flagLevelhold = False

            elif line["name"] == 'END':
                currentBranch = 'N'
                targetBranch = 'N'
                flagLevelhold = False

            else:
                if currentBranch != targetBranch:
                    continue
                    
                if line['name'] == 'MEASURE':
                    matchMeasure = re.match(r"(\d+)/(\d+)", line['value'])
                    if not matchMeasure:
                        continue
                    measureDividend = int(matchMeasure.group(1))
                    measureDivisor = int(matchMeasure.group(2))

                elif line['name'] == 'GOGOSTART':
                    measureEvents.append({
                        "name": 'gogoStart',
                        "position": len(measureData),
                    })

                elif line['name'] == 'GOGOEND':
                    measureEvents.append({
                        "name": 'gogoEnd',
                        "position": len(measureData),
                    })

                elif line['name'] == 'SCROLL':
                    measureEvents.append({
                        "name": 'scroll',
                        "position": len(measureData),
                        "value": float(line['value']),
                    })

                elif line['name'] == 'BPMCHANGE':
                    measureEvents.append({
                        "name": 'bpm',
                        "position": len(measureData),
                        "value": float(line['value']),
                    })

                elif line['name'] == 'TTBREAK':
                    measureProperties['ttBreak'] = True

                elif line['name'] == 'LEVELHOLD':
                    flagLevelhold = True

                else:
                    print(line['name'])  # Unknown: BARLINEOFF, BARLINEON

        elif line['type'] == 'data' and currentBranch is targetBranch:
            data = line['data']
            if data.endswith(','):
                measureData += data[0:-1]
                measure = {
                    "length": [measureDividend, measureDivisor],
                    "properties": measureProperties,
                    "data": measureData,
                    "events": measureEvents,
                }
                measures.append(measure)
                measureData = ''
                measureEvents = []
                measureProperties = {}
            else:
                measureData += data

    if len(measures):
        # Make first BPM event
        firstBPMEventFound = False
        # Search for BPM event in the first measure
        for i in range(len(measures[0]['events'])):
            evt = measures[0]['events'][i]
            if evt.name == 'bpm' and evt.position == 0:
                firstBPMEventFound = True
        if not firstBPMEventFound:
            # noinspection PyTypeChecker
            measures[0]['events'].insert(0, {
                "name": 'bpm',
                "position": 0,
                "value": tjaHeaders['bpm'],
            })

    # Helper values
    course = 0
    courseValue = headers['course'].lower()

    if courseValue in ['easy', '0']:
        course = 0
    elif courseValue in ['normal', '1']:
        course = 1
    elif courseValue in ['hard', '2']:
        course = 2
    elif courseValue in ['oni', '3']:
        course = 3
    elif courseValue in ['ura', 'edit', '4']:
        course = 4

    if measureData:
        measures.append({
            "length": [measureDividend, measureDivisor],
            "properties": measureProperties,
            "data": measureData,
            "events": measureEvents,
        })
    else:
        for event in measureEvents:
            event['position'] = len(measures[len(measures) - 1]['data'])
            # noinspection PyTypeChecker
            measures[len(measures) - 1]['events'].append(event)

    # Output
    print(measures[len(measures) - 1])
    return course, headers, measures


def parseLine(line):
    # Regex matches for various line types
    match_comment = re.match(r"//.*", line)
    match_header = re.match(r"^([A-Z]+):(.+)", line)
    match_command = re.match(r"^#([A-Z]+)(?:\s+(.+))?", line)
    match_data = re.match(r"^(([0-9]|A|B|C|F|G)*,?)$", line)

    if match_comment:
        return {"type": 'comment', "value": line}

    elif match_header:
        nameUpper = match_header.group(1).upper()
        value = match_header.group(2)
        if nameUpper in HEADER_GLOBAL:
            return {"type": 'header', "scope": 'global', "name": nameUpper, "value": value.strip()}
        elif nameUpper in HEADER_COURSE:
            return {"type": 'header', "scope": 'course', "name": nameUpper, "value": value.strip()}

    elif match_command:
        nameUpper = match_command.group(1).upper()
        value = match_command.group(2) if match_command.group(2) else ''
        if nameUpper in COMMAND:
            return {"type": 'command', "name": nameUpper, "value": value.strip()}

    elif match_data:
        return {"type": 'data', "data": match_data.group(1)}

    return {"type": 'unknown', "value": line}


def parseTJA(tja):
    # Split into lines
    lines = tja.read().splitlines()
    lines = [line for line in lines if line]  # Discard empty lines

    # Line by line
    headers = {}
    courses = {}
    currentCourse = ''
    for line in lines:
        parsed = parseLine(line)
        # Case 1: Comments (ignore
        if parsed['type'] == 'comment':
            pass
        # Case 2: Global header metadata
        elif parsed['type'] == 'header' and parsed['scope'] == 'global':
            headers[parsed['name'].lower()] = parsed['value']
        # Case 3: Course data (metadata, commands, note data)
        else:
            # Check to see if we're starting a new course
            if parsed['type'] == 'header' and parsed['scope'] == 'course' and parsed['name'] == 'COURSE':
                currentCourse = parsed['value']
                if currentCourse not in courses.keys():
                    courses[currentCourse] = []
            # Append the line to the current course
            courses[currentCourse].append(parsed)

    # Convert parsed course lines into actual note data
    for courseName, courseLines in courses.items():
        courses[courseName] = getCourse(headers, courseLines)

    return headers, courses
