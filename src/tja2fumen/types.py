import csv
import os
import struct
from typing import Dict, List

from dataclasses import dataclass, field, fields

from tja2fumen.constants import BRANCH_NAMES


@dataclass
class ConvertTypesOnInit:
    """
    Add type conversion support to dataclasses.

    This mimics type validation from the Pydantic library, without incurring
    the performance slowdown that comes with using Pydantic's BaseModel class.

    (Pydantic's additional feature set is overkill for this project.)
    """
    def __post_init__(self):
        for f in fields(self):
            # Check if passed value matches expected type
            value = getattr(self, f.name)
            try:
                correct_type = isinstance(value, f.type)
            except TypeError:
                # Catch "TypeError: Subscripted generics cannot be used with
                #        class and instance checks"
                # This is thrown when the `typing` module's generic types
                # are used with subscripted types, e.g.: "List[int]"
                return

            # If the value is already the correct type, don't try to convert
            if correct_type:
                return
            # Otherwise, try coercing the value to the expected type
            else:
                try:
                    value = f.type(value)
                    setattr(self, f.name, value)
                except ValueError as exc:
                    raise ValueError(
                        f"Error setting {f.name}: Value '{repr(value)}' "
                        f"cannot be coerced to type '{f.type}'."
                    ) from exc


@dataclass
class TJAData(ConvertTypesOnInit):
    """Contains the information for a single note or single command."""
    name: str
    value: str
    # For TJA, 'pos' is stored as an integer rather than in milliseconds
    pos: int


@dataclass
class TJAMeasure(ConvertTypesOnInit):
    """Contains all the data in a single TJA measure (denoted by ',')."""
    notes: List[TJAData] = field(default_factory=list)
    events: List[TJAData] = field(default_factory=list)
    combined: List[TJAData] = field(default_factory=list)


@dataclass
class TJACourse(ConvertTypesOnInit):
    """Contains all the data in a single TJA `COURSE:` section."""
    BPM: float
    offset: float
    course: str
    level: int = 0
    balloon: list = field(default_factory=list)
    score_init: int = 0
    score_diff: int = 0
    data: list = field(default_factory=list)
    branches: Dict[str, List[TJAMeasure]] = field(
        default_factory=lambda: {k: [TJAMeasure()] for k in BRANCH_NAMES}
    )


@dataclass
class TJASong(ConvertTypesOnInit):
    """Contains all the data in a single TJA (`.tja`) chart file."""
    BPM: float
    offset: float
    courses: Dict[str, TJACourse]


@dataclass
class TJAMeasureProcessed(ConvertTypesOnInit):
    """
    Contains all the data in a single TJA measure (denoted by ','), but with
    all `#COMMAND` lines processed, and their values stored as attributes.

    ((Note: Because only one BPM/SCROLL/GOGO value can be stored per measure,
      any TJA measures with mid-measure commands must be split up. So, the
      number of `TJAMeasureProcessed` objects will often be greater than
      the number of `TJAMeasure` objects for a given song.))
    """
    bpm: float
    scroll: float
    gogo: bool
    barline: bool
    time_sig: List[int]
    subdivisions: int
    pos_start: int = 0
    pos_end: int = 0
    delay: float = 0.0
    section: bool = False
    levelhold: bool = False
    branch_start: List = field(default_factory=list)
    data: list = field(default_factory=list)


@dataclass
class FumenNote(ConvertTypesOnInit):
    """Contains all the byte values for a single Fumen note."""
    note_type: str = ''
    pos: float = 0.0
    score_init: int = 0
    score_diff: int = 0
    padding: int = 0
    item: int = 0
    duration: float = 0.0
    multimeasure: bool = False
    hits: int = 0
    hits_padding: int = 0
    drumroll_bytes: bytes = b'\x00\x00\x00\x00\x00\x00\x00\x00'


@dataclass
class FumenBranch(ConvertTypesOnInit):
    """Contains all the data in a single Fumen branch."""
    length: int = 0
    speed: float = 0.0
    padding: int = 0
    notes: list = field(default_factory=list)


@dataclass
class FumenMeasure(ConvertTypesOnInit):
    """Contains all the data in a single Fumen measure."""
    bpm: float = 0.0
    offset_start: float = 0.0
    offset_end: float = 0.0
    duration: float = 0.0
    gogo: bool = False
    barline: bool = True
    branch_start: list = field(default_factory=list)
    branch_info: List[int] = field(default_factory=lambda: [-1] * 6)
    branches: Dict[str, FumenBranch] = field(
        default_factory=lambda: {b: FumenBranch() for b in BRANCH_NAMES}
    )
    padding1: int = 0
    padding2: int = 0

    def set_duration(self, time_sig, measure_length, subdivisions):
        """Compute the millisecond duration of the measure."""
        # First, we compute the duration for a full 4/4 measure.
        full_duration = (4 * 60_000 / self.bpm)
        # Next, we adjust this duration based on both:
        #   1. The *actual* measure size (e.g. #MEASURE 1/8, 5/4, etc.)
        #   2. Whether this is a "submeasure" (i.e. whether it contains
        #      mid-measure commands, which split up the measure)
        #      - If this is a submeasure, then `measure_length` will be
        #        less than the total number of subdivisions.
        #      - In other words, `measure_ratio` will be less than 1.0.
        measure_size = time_sig[0] / time_sig[1]
        measure_ratio = (
            1.0 if subdivisions == 0.0  # Avoid DivisionByZeroErrors
            else (measure_length / subdivisions)
        )
        self.duration = (full_duration * measure_size * measure_ratio)

    def set_ms_offsets(self, song_offset, delay, prev_measure, first_measure):
        """Compute the millisecond offsets for the start/end of the measure."""
        if first_measure:
            self.offset_start = (song_offset * -1000) - (4 * 60_000 / self.bpm)
        else:
            # First, start with the end timing of the previous measure
            self.offset_start = prev_measure.offset_end
            # Add any #DELAY commands
            self.offset_start += delay
            # Adjust the start timing to account for #BPMCHANGE commands
            # (!!! Discovered by tana :3 !!!)
            self.offset_start += (4 * 60_000 / prev_measure.bpm)
            self.offset_start -= (4 * 60_000 / self.bpm)

        # Compute the end offset by adding the duration to the start offset
        self.offset_end = self.offset_start + self.duration

    def set_branch_info(self, branch_condition, branch_points_total,
                        current_branch, first_branch_condition,
                        has_section, has_levelhold):
        """Compute the values that represent branching/diverge conditions."""
        # If levelhold is set, force the branch to stay the same,
        # regardless of the value of the current branch condition.
        if has_levelhold:
            if current_branch == 'normal':
                self.branch_info[0:2] = [999, 999]  # Forces fail/fail
            elif current_branch == 'professional':
                self.branch_info[2:4] = [0, 999]    # Forces pass/fail
            elif current_branch == 'master':
                self.branch_info[4:6] = [0, 0]      # Forces pass/pass

        # Handle branch conditions for percentage accuracy
        # There are three cases for interpreting #BRANCHSTART p:
        #    1. Percentage is between 0% and 100%
        #    2. Percentage is above 100% (guaranteed level down)
        #    3. Percentage is 0% (guaranteed level up)
        elif branch_condition[0] == 'p':
            vals = []
            for percent in branch_condition[1:]:
                if 0 < percent <= 1:
                    vals.append(int(branch_points_total * percent))
                elif percent > 1:
                    vals.append(999)
                else:
                    vals.append(0)
            if current_branch == 'normal':
                self.branch_info[0:2] = vals
            elif current_branch == 'professional':
                self.branch_info[2:4] = vals
            elif current_branch == 'master':
                self.branch_info[4:6] = vals

        # Handle branch conditions for drumroll accuracy
        # There are three cases for interpreting #BRANCHSTART r:
        #    1. It's the first branching condition.
        #    2. It's not the first branching condition, but it
        #       has a #SECTION command to reset the accuracy.
        #    3. It's not the first branching condition, and it
        #       doesn't have a #SECTION command.
        # TODO: Determine the behavior for these 3 conditions
        elif branch_condition[0] == 'r':
            if current_branch == 'normal':
                self.branch_info[0:2] = branch_condition[1:]
            elif current_branch == 'professional':
                self.branch_info[2:4] = branch_condition[1:]
            elif current_branch == 'master':
                self.branch_info[4:6] = branch_condition[1:]


@dataclass
class FumenHeader(ConvertTypesOnInit):
    """Contains all the byte values for a Fumen chart file's header."""
    order: str = "<"
    b000_b431_timing_windows: List[float] = field(default_factory=lambda:
                                                  [25.025, 75.075, 108.422]*36)
    b432_b435_has_branches:               int = 0
    b436_b439_hp_max:                     int = 10000
    b440_b443_hp_clear:                   int = 8000
    b444_b447_hp_gain_good:               int = 10
    b448_b451_hp_gain_ok:                 int = 5
    b452_b455_hp_loss_bad:                int = -20
    b456_b459_normal_normal_ratio:        int = 65536
    b460_b463_normal_professional_ratio:  int = 65536
    b464_b467_normal_master_ratio:        int = 65536
    b468_b471_branch_points_good:         int = 20
    b472_b475_branch_points_ok:           int = 10
    b476_b479_branch_points_bad:          int = 0
    b480_b483_branch_points_drumroll:     int = 1
    b484_b487_branch_points_good_big:     int = 20
    b488_b491_branch_points_ok_big:       int = 10
    b492_b495_branch_points_drumroll_big: int = 1
    b496_b499_branch_points_balloon:      int = 30
    b500_b503_branch_points_kusudama:     int = 30
    b504_b507_branch_points_unknown:      int = 20
    b508_b511_dummy_data:                 int = 12345678
    b512_b515_number_of_measures:         int = 0
    b516_b519_unknown_data:               int = 0

    def parse_header_values(self, raw_bytes):
        """Parse a raw string of 520 bytes to get the header values."""
        self.order = self._parse_order(raw_bytes)
        rb = raw_bytes  # We use a shortened form just for visual clarity:
        self.b000_b431_timing_windows           = self.up(rb, "f"*108, 0, 431)
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
        """Unpack a raw byte string according to specific types."""
        if s is not None and e is not None:
            raw_bytes = raw_bytes[s:e+1]
        vals = struct.unpack(self.order + type_string, raw_bytes)
        return vals[0] if len(vals) == 1 else vals

    def _parse_order(self, raw_bytes):
        """Parse the order of the song (little or big endian)."""
        self.order = ''
        # Bytes 512-515 are the number of measures. We check the values using
        # both little and big endian, then compare to see which is correct.
        if (self.up(raw_bytes, ">I", 512, 515) <
                self.up(raw_bytes, "<I", 512, 515)):
            return ">"
        else:
            return "<"

    def set_hp_bytes(self, n_notes, difficulty, stars):
        """Compute header bytes related to the soul gauge (HP) behavior."""
        # Note: Ura Oni is equivalent to Oni for soul gauge behavior
        difficulty = 'Oni' if difficulty in ['Ura', 'Edit'] else difficulty
        self._get_hp_from_LUTs(n_notes, difficulty, stars)
        self.b440_b443_hp_clear = {'Easy': 6000, 'Normal': 7000,
                                   'Hard': 7000, 'Oni': 8000}[difficulty]

    def _get_hp_from_LUTs(self, n_notes, difficulty, stars):
        """Fetch pre-computed soul gauge values from lookup tables (LUTs)."""
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
            for num, line in enumerate(csv.DictReader(fp)):
                if num+1 == n_notes:
                    self.b444_b447_hp_gain_good = int(line[f"good_{key}"])
                    self.b448_b451_hp_gain_ok = int(line[f"ok_{key}"])
                    self.b452_b455_hp_loss_bad = int(line[f"bad_{key}"])
                    break

    @property
    def raw_bytes(self):
        """Represent the header values as a string of raw bytes."""
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


@dataclass
class FumenCourse(ConvertTypesOnInit):
    """Contains all the data in a single Fumen (`.bin`) chart file."""
    header: FumenHeader
    measures: List[FumenMeasure] = field(default_factory=list)
    score_init: int = 0
    score_diff: int = 0
