from tja2fumen.constants import sampleHeaderMetadata, simpleHeaders


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


class FumenCourse:
    def __init__(self, measures=None, hasBranches=False, scoreInit=0, scoreDiff=0,
                 order='<',  headerPadding=None, headerMetadata=None, unknownMetadata=0):
        if isinstance(measures, int):
            self.measures = [FumenMeasure() for _ in range(measures)]
        else:
            self.measures = measures
        self.hasBranches = hasBranches
        self.scoreInit = scoreInit
        self.scoreDiff = scoreDiff
        self.order = order
        self.headerPadding = simpleHeaders.copy()[0] if headerPadding is None else headerPadding
        self.headerMetadata = sampleHeaderMetadata.copy() if headerMetadata is None else headerMetadata
        self.unknownMetadata = unknownMetadata

    def __repr__(self):
        return str(self.__dict__)


class FumenMeasure:
    def __init__(self, bpm=0.0, fumenOffsetStart=0.0, fumenOffsetEnd=0.0, duration=0.0,
                 gogo=False, barline=True, branchStart=None, branchInfo=None, padding1=0, padding2=0):
        self.bpm = bpm
        self.fumenOffsetStart = fumenOffsetStart
        self.fumenOffsetEnd = fumenOffsetEnd
        self.duration = duration
        self.gogo = gogo
        self.barline = barline
        self.branchStart = branchStart
        self.branchInfo = [-1, -1, -1, -1, -1, -1] if branchInfo is None else branchInfo
        self.branches = {'normal': FumenBranch(), 'advanced': FumenBranch(), 'master': FumenBranch()}
        self.padding1 = padding1
        self.padding2 = padding2

    def __repr__(self):
        return str(self.__dict__)


class FumenBranch:
    def __init__(self, length=0, speed=0.0, padding=0):
        self.length = length
        self.speed = speed
        self.padding = padding
        self.notes = []

    def __repr__(self):
        return str(self.__dict__)


class FumenNote:
    def __init__(self, note_type='', pos=0.0, scoreInit=0, scoreDiff=0, padding=0, item=0, duration=0.0,
                 multimeasure=False, hits=0, hitsPadding=0, drumrollBytes=b'\x00\x00\x00\x00\x00\x00\x00\x00'):
        self.note_type = note_type
        self.pos = pos
        self.scoreInit = scoreInit
        self.scoreDiff = scoreDiff
        self.padding = padding
        # TODO: Determine how to properly set the item byte (https://github.com/vivaria/tja2fumen/issues/17)
        self.item = item
        # These attributes are only used for drumrolls/balloons
        self.duration = duration
        self.multimeasure = multimeasure
        self.hits = hits
        self.hitsPadding = hitsPadding
        self.drumrollBytes = drumrollBytes

    def __repr__(self):
        return str(self.__dict__)
