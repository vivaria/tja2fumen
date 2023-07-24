import csv
import os
import struct

from tja2fumen.constants import TJA_COURSE_NAMES, BRANCH_NAMES


class TJASong:
    def __init__(self, BPM=None, offset=None):
        self.BPM = float(BPM)
        self.offset = float(offset)
        self.courses = {course: TJACourse(self.BPM, self.offset, course)
                        for course in TJA_COURSE_NAMES}

    def __repr__(self):
        return (f"{{'BPM': {self.BPM}, 'offset': {self.offset}, "
                f"'courses': {list(self.courses.keys())}}}")


class TJACourse:
    def __init__(self, BPM, offset, course, level=0, balloon=None,
                 score_init=0, score_diff=0):
        self.level = level
        self.balloon = [] if balloon is None else balloon
        self.score_init = score_init
        self.score_diff = score_diff
        self.BPM = BPM
        self.offset = offset
        self.course = course
        self.data = []
        self.branches = {
            'normal': [TJAMeasure()],
            'professional': [TJAMeasure()],
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
                 pos_start=0, pos_end=0, delay=0, section=None,
                 branch_start=None, data=None):
        self.bpm = bpm
        self.scroll = scroll
        self.gogo = gogo
        self.barline = barline
        self.time_sig = time_sig
        self.subdivisions = subdivisions
        self.pos_start = pos_start
        self.pos_end = pos_end
        self.delay = delay
        self.section = section
        self.branch_start = branch_start
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
    def __init__(self, measures=None, header=None, score_init=0, score_diff=0):
        if isinstance(measures, int):
            self.measures = [FumenMeasure() for _ in range(measures)]
        else:
            self.measures = [] if measures is None else measures
        self.header = FumenHeader() if header is None else header
        self.score_init = score_init
        self.score_diff = score_diff

    def __repr__(self):
        return str(self.__dict__)


class FumenMeasure:
    def __init__(self, bpm=0.0, offset_start=0.0, offset_end=0.0,
                 duration=0.0, gogo=False, barline=True, branch_start=None,
                 branch_info=None, padding1=0, padding2=0):
        self.bpm = bpm
        self.offset_start = offset_start
        self.offset_end = offset_end
        self.duration = duration
        self.gogo = gogo
        self.barline = barline
        self.branch_start = branch_start
        self.branch_info = [-1] * 6 if branch_info is None else branch_info
        self.branches = {b: FumenBranch() for b in BRANCH_NAMES}
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
    def __init__(self, note_type='', pos=0.0, score_init=0, score_diff=0,
                 padding=0, item=0, duration=0.0, multimeasure=False,
                 hits=0, hits_padding=0,
                 drumroll_bytes=b'\x00\x00\x00\x00\x00\x00\x00\x00'):
        self.note_type = note_type
        self.pos = pos
        self.score_init = score_init
        self.score_diff = score_diff
        self.padding = padding
        # TODO: Determine how to properly set the item byte
        #       (https://github.com/vivaria/tja2fumen/issues/17)
        self.item = item
        # These attributes are only used for drumrolls/balloons
        self.duration = duration
        self.multimeasure = multimeasure
        self.hits = hits
        self.hits_padding = hits_padding
        self.drumroll_bytes = drumroll_bytes

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
        # This byte string corresponds to
        timing_windows = self.up(b'43\xc8Ag&\x96B"\xe2\xd8B' * 36, "fff" * 36)
        self.b000_b431_timing_windows             = timing_windows
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
        self.b484_b487_branch_points_good_big     = 20
        self.b488_b491_branch_points_ok_big       = 10
        self.b492_b495_branch_points_drumroll_big = 1
        self.b496_b499_branch_points_balloon      = 30
        self.b500_b503_branch_points_kusudama     = 30
        self.b504_b507_branch_points_unknown      = 20
        self.b508_b511_dummy_data                 = 12345678
        self.b512_b515_number_of_measures         = 0
        self.b516_b519_unknown_data               = 0

    def _parse_header_values(self, raw_bytes):
        rb = raw_bytes
        self.b000_b431_timing_windows             = self.up(rb, "f" * 108,
                                                            0, 431)
        self.b432_b435_has_branches               = self.up(rb, "i", 432, 435)
        self.b436_b439_hp_max                     = self.up(rb, "i", 436, 439)
        self.b440_b443_hp_clear                   = self.up(rb, "i", 440, 443)
        self.b444_b447_hp_gain_good               = self.up(rb, "i", 444, 447)
        self.b448_b451_hp_gain_ok                 = self.up(rb, "i", 448, 451)
        self.b452_b455_hp_loss_bad                = self.up(rb, "i", 452, 455)
        self.b456_b459_normal_normal_ratio        = self.up(rb, "i", 456, 459)
        self.b460_b463_normal_professional_ratio  = self.up(rb, "i", 460, 463)
        self.b464_b467_normal_master_ratio        = self.up(rb, "i", 464, 467)
        self.b468_b471_branch_points_good         = self.up(rb, "i", 468, 471)
        self.b472_b475_branch_points_ok           = self.up(rb, "i", 472, 475)
        self.b476_b479_branch_points_bad          = self.up(rb, "i", 476, 479)
        self.b480_b483_branch_points_drumroll     = self.up(rb, "i", 480, 483)
        self.b484_b487_branch_points_good_big     = self.up(rb, "i", 484, 487)
        self.b488_b491_branch_points_ok_big       = self.up(rb, "i", 488, 491)
        self.b492_b495_branch_points_drumroll_big = self.up(rb, "i", 492, 495)
        self.b496_b499_branch_points_balloon      = self.up(rb, "i", 496, 499)
        self.b500_b503_branch_points_kusudama     = self.up(rb, "i", 500, 503)
        self.b504_b507_branch_points_unknown      = self.up(rb, "i", 504, 507)
        self.b508_b511_dummy_data                 = self.up(rb, "i", 508, 511)
        self.b512_b515_number_of_measures         = self.up(rb, "i", 512, 515)
        self.b516_b519_unknown_data               = self.up(rb, "i", 516, 519)

    def up(self, raw_bytes, type_string, s=None, e=None):
        if s is not None and e is not None:
            raw_bytes = raw_bytes[s:e+1]
        vals = struct.unpack(self.order + type_string, raw_bytes)
        return vals[0] if len(vals) == 1 else vals

    def _parse_order(self, raw_bytes):
        self.order = ''
        if (self.up(raw_bytes, ">I", 512, 515) <
                self.up(raw_bytes, "<I", 512, 515)):
            return ">"
        else:
            return "<"

    def set_hp_bytes(self, n_notes, difficulty, stars):
        difficulty = 'Oni' if difficulty in ['Ura', 'Edit'] else difficulty
        self._get_hp_from_LUTs(n_notes, difficulty, stars)
        self.b440_b443_hp_clear = {'Easy': 6000, 'Normal': 7000,
                                   'Hard': 7000, 'Oni': 8000}[difficulty]

    def _get_hp_from_LUTs(self, n_notes, difficulty, stars):
        if not 0 < n_notes <= 2500:
            return
        star_to_key = {
            'Oni':    {1: '17', 2: '17', 3: '17', 4: '17', 5: '17',
                       6: '17', 7: '17', 8: '8', 9: '910', 10: '910'},
            'Hard':   {1: '12', 2: '12', 3: '3',  4: '4',  5: '58',
                       6: '58', 7: '58', 8: '58', 9: '58', 10: '58'},
            'Normal': {1: '12', 2: '12', 3: '3',  4: '4',  5: '57',
                       6: '57', 7: '57', 8: '57', 9: '57', 10: '57'},
            'Easy':   {1: '1',  2: '23', 3: '23', 4: '45', 5: '45',
                       6: '45', 7: '45', 8: '45', 9: '45', 10: '45'},
        }
        key = f"{difficulty}-{star_to_key[difficulty][stars]}"
        pkg_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(pkg_dir, "hp_values.csv"), newline='') as fp:
            # Parse row data
            rows = [row for row in csv.reader(fp, delimiter=',')]
            # Get column numbers by indexing header row
            column_good = rows[0].index(f"good_{key}")
            column_ok = rows[0].index(f"ok_{key}")
            column_bad = rows[0].index(f"bad_{key}")
            # Fetch values from the row corresponding to the number of notes
            self.b444_b447_hp_gain_good = int(rows[n_notes][column_good])
            self.b448_b451_hp_gain_ok = int(rows[n_notes][column_ok])
            self.b452_b455_hp_loss_bad = int(rows[n_notes][column_bad])

    @property
    def raw_bytes(self):
        value_list = []
        format_string = self.order
        for key, val in self.__dict__.items():
            if key in ["order", "_raw_bytes"]:
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
        # Display truncated version of timing windows
        return str([v if not isinstance(v, tuple)
                    else [round(timing, 2) for timing in v[:3]]
                    for v in self.__dict__.values()])
