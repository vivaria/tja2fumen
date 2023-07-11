# TJA parsing

courseNames = []
for difficulty in ['Ura', 'Oni', 'Hard', 'Normal', 'Easy']:
    for player in ['', 'P1', 'P2']:
        courseNames.append(difficulty+player)


class TJASong:
    def __init__(self, BPM=None, offset=None):
        self.BPM = float(BPM)
        self.offset = float(offset)
        self.courses = {course: TJACourse(self.BPM, self.offset, course) for course in courseNames}

    def __repr__(self):
        return f"{{'BPM': {self.BPM}, 'offset': {self.offset}, 'courses': {list(self.courses.keys())}}}"


class TJACourse:
    def __init__(self, BPM, offset, course, level=0, balloon=None, scoreInit=0, scoreDiff=0):
        self.level = level
        self.balloon = [] if balloon is None else balloon
        self.scoreInit = scoreInit
        self.scoreDiff = scoreDiff
        self.BPM = BPM
        self.offset = offset
        self.course = course
        self.data = []
        self.branches = {
            'normal': [TJAMeasure()],
            'advanced': [TJAMeasure()],
            'master': [TJAMeasure()]
        }

    def __repr__(self):
        return str(self.__dict__) if self.data else "{'data': []}"


class TJAMeasure:
    def __init__(self, notes=None, events=None):
        self.notes = [] if notes is None else notes
        self.events = [] if events is None else events
        self.combined = []

    def __repr__(self):
        return str(self.__dict__)


class TJAData:
    def __init__(self, name, value, pos=None):
        self.pos = pos
        self.name = name
        self.value = value

    def __repr__(self):
        return str(self.__dict__)
