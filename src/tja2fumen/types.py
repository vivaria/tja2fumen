import csv
import os
import struct

from tja2fumen.constants import TJA_COURSE_NAMES


class TJASong:
    def __init__(self, BPM=None, offset=None):
        self.BPM = float(BPM)
        self.offset = float(offset)
        self.courses = {course: TJACourse(self.BPM, self.offset, course) for course in TJA_COURSE_NAMES}

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


class TJAMeasureProcessed:
    def __init__(self, bpm, scroll, gogo, barline, time_sig, subdivisions,
                 pos_start=0, pos_end=0, delay=0, branchStart=None, data=None):
        self.bpm = bpm
        self.scroll = scroll
        self.gogo = gogo
        self.barline = barline
        self.time_sig = time_sig
        self.subdivisions = subdivisions
        self.pos_start = pos_start
        self.pos_end = pos_end
        self.delay = delay
        self.branchStart = branchStart
        self.data = [] if data is None else data

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
    def __init__(self, measures=None, header=None, scoreInit=0, scoreDiff=0):
        if isinstance(measures, int):
            self.measures = [FumenMeasure() for _ in range(measures)]
        else:
            self.measures = [] if measures is None else measures
        self.header = FumenHeader() if header is None else header
        self.scoreInit = scoreInit
        self.scoreDiff = scoreDiff

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


class FumenHeader:
    def __init__(self, raw_bytes=None):
        if raw_bytes is None:
            self.order = "<"
            self._assign_default_header_values()
        else:
            self.order = self._parse_order(raw_bytes)
            self._parse_header_values(raw_bytes)

    def _assign_default_header_values(self):
        self.b000_b431_timing_windows             = struct.unpack(self.order + ("fff" * 36),
                                                                  b'43\xc8Ag&\x96B"\xe2\xd8B' * 36)
        self.b432_b435_has_branches               = 0
        self.b436_b439_hp_max                     = 10000
        self.b440_b443_hp_clear                   = 8000
        self.b444_b447_hp_gain_good               = 10
        self.b448_b451_hp_gain_ok                 = 5
        self.b452_b455_hp_loss_bad                = -20
        self.b456_b459_normal_normal_ratio        = 65536
        self.b460_b463_normal_professional_ratio  = 65536
        self.b464_b467_normal_master_ratio        = 65536
        self.b468_b471_branch_points_good         = 20
        self.b472_b475_branch_points_ok           = 10
        self.b476_b479_branch_points_bad          = 0
        self.b480_b483_branch_points_drumroll     = 1
        self.b484_b487_branch_points_good_BIG     = 20
        self.b488_b491_branch_points_ok_BIG       = 10
        self.b492_b495_branch_points_drumroll_BIG = 1
        self.b496_b499_branch_points_balloon      = 30
        self.b500_b503_branch_points_kusudama     = 30
        self.b504_b507_branch_points_unknown      = 20
        self.b508_b511_dummy_data                 = 12345678
        self.b512_b515_number_of_measures         = 0
        self.b516_b519_unknown_data               = 0

    def _parse_header_values(self, raw_bytes):
        self.b000_b431_timing_windows             = struct.unpack(self.order + ("fff" * 36), raw_bytes[0:432])
        self.b432_b435_has_branches               = struct.unpack(self.order + "i", raw_bytes[432:436])[0]
        self.b436_b439_hp_max                     = struct.unpack(self.order + "i", raw_bytes[436:440])[0]
        self.b440_b443_hp_clear                   = struct.unpack(self.order + "i", raw_bytes[440:444])[0]
        self.b444_b447_hp_gain_good               = struct.unpack(self.order + "i", raw_bytes[444:448])[0]
        self.b448_b451_hp_gain_ok                 = struct.unpack(self.order + "i", raw_bytes[448:452])[0]
        self.b452_b455_hp_loss_bad                = struct.unpack(self.order + "i", raw_bytes[452:456])[0]
        self.b456_b459_normal_normal_ratio        = struct.unpack(self.order + "i", raw_bytes[456:460])[0]
        self.b460_b463_normal_professional_ratio  = struct.unpack(self.order + "i", raw_bytes[460:464])[0]
        self.b464_b467_normal_master_ratio        = struct.unpack(self.order + "i", raw_bytes[464:468])[0]
        self.b468_b471_branch_points_good         = struct.unpack(self.order + "i", raw_bytes[468:472])[0]
        self.b472_b475_branch_points_ok           = struct.unpack(self.order + "i", raw_bytes[472:476])[0]
        self.b476_b479_branch_points_bad          = struct.unpack(self.order + "i", raw_bytes[476:480])[0]
        self.b480_b483_branch_points_drumroll     = struct.unpack(self.order + "i", raw_bytes[480:484])[0]
        self.b484_b487_branch_points_good_BIG     = struct.unpack(self.order + "i", raw_bytes[484:488])[0]
        self.b488_b491_branch_points_ok_BIG       = struct.unpack(self.order + "i", raw_bytes[488:492])[0]
        self.b492_b495_branch_points_drumroll_BIG = struct.unpack(self.order + "i", raw_bytes[492:496])[0]
        self.b496_b499_branch_points_balloon      = struct.unpack(self.order + "i", raw_bytes[496:500])[0]
        self.b500_b503_branch_points_kusudama     = struct.unpack(self.order + "i", raw_bytes[500:504])[0]
        self.b504_b507_branch_points_unknown      = struct.unpack(self.order + "i", raw_bytes[504:508])[0]
        self.b508_b511_dummy_data                 = struct.unpack(self.order + "i", raw_bytes[508:512])[0]
        self.b512_b515_number_of_measures         = struct.unpack(self.order + "i", raw_bytes[512:516])[0]
        self.b516_b519_unknown_data               = struct.unpack(self.order + "i", raw_bytes[516:520])[0]

    @staticmethod
    def _parse_order(raw_bytes):
        if struct.unpack(">I", raw_bytes[512:516])[0] < struct.unpack("<I", raw_bytes[512:516])[0]:
            return ">"
        else:
            return "<"

    def set_hp_bytes(self, n_notes, difficulty, stars):
        self._get_hp_from_LUTs(n_notes, difficulty, stars)
        if difficulty == 'Easy':
            self.b440_b443_hp_clear = 6000
        elif difficulty in ['Normal', 'Hard']:
            self.b440_b443_hp_clear = 7000
        elif difficulty in ['Oni', 'Ura', 'Edit']:
            self.b440_b443_hp_clear = 8000

    def _get_hp_from_LUTs(self, n_notes, difficulty, stars):
        if difficulty in ['Oni', 'Ura']:
            if 9 <= stars:
                key = "Oni-9-10"
            elif stars == 8:
                key = "Oni-8"
            elif stars <= 7:
                key = "Oni-1-7"
        elif difficulty == 'Hard':
            if 5 <= stars:
                key = "Hard-5-8"
            elif stars == 4:
                key = "Hard-4"
            elif stars == 3:
                key = "Hard-3"
            elif stars <= 2:
                key = "Hard-1-2"
        elif difficulty == 'Normal':
            if 5 <= stars:
                key = "Normal-5-7"
            elif stars == 4:
                key = "Normal-4"
            elif stars == 3:
                key = "Normal-3"
            elif stars <= 2:
                key = "Normal-1-2"
        elif difficulty == 'Easy':
            if 4 <= stars:
                key = "Easy-4-5"
            elif 2 <= stars <= 3:
                key = "Easy-2-3"
            elif stars <= 1:
                key = "Easy-1"
        pkg_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(pkg_dir, "soulgauge_LUTs", f"byte1213_{key}.csv"), newline='') as csvfile:
            lut_reader = csv.reader(csvfile, delimiter=',')
            for row in lut_reader:
                if int(row[0]) == n_notes:
                    self.b444_b447_hp_gain_good = int(row[1])
                    break
        with open(os.path.join(pkg_dir, "soulgauge_LUTs", f"byte1617_{key}.csv"), newline='') as csvfile:
            lut_reader = csv.reader(csvfile, delimiter=',')
            for row in lut_reader:
                if int(row[0]) == n_notes:
                    self.b448_b451_hp_gain_ok = int(row[1])
                    break
        with open(os.path.join(pkg_dir, "soulgauge_LUTs", f"byte2021_{key}.csv"), newline='') as csvfile:
            lut_reader = csv.reader(csvfile, delimiter=',')
            for row in lut_reader:
                if int(row[0]) == n_notes:
                    self.b452_b455_hp_loss_bad = int(row[1]) - 765
                    break

    @property
    def raw_bytes(self):
        value_list = []
        format_string = self.order
        for key, val in self.__dict__.items():
            if key == "order":
                pass
            elif key == "b000_b431_timing_windows":
                value_list.extend(list(val))
                format_string += "f" * len(val)
            else:
                value_list.append(val)
                format_string += "i"
        raw_bytes = struct.pack(format_string, *value_list)
        assert len(raw_bytes) == 520
        return raw_bytes

    def __repr__(self):
        return str([v if not isinstance(v, tuple)
                    else [round(timing, 2) for timing in v[:3]]  # Display truncated version of timing windows
                    for v in self.__dict__.values()])
