"""
Dataclasses used to represent song courses, branches, measures, and notes.
"""

import csv
import os
import struct
from typing import Any, Optional

from dataclasses import dataclass, field, fields

from tja2fumen.constants import BRANCH_NAMES


@dataclass(slots=True)
class TJAData:
    """Contains the information for a single note or single command."""
    name: str
    value: str
    # For TJA, 'pos' is stored as an integer rather than in milliseconds
    pos: int


@dataclass(slots=True)
class TJAMeasure:
    """Contains all the data in a single TJA measure (denoted by ',')."""
    notes: list[str] = field(default_factory=list)
    events: list[TJAData] = field(default_factory=list)
    combined: list[TJAData] = field(default_factory=list)


@dataclass(slots=True)
class TJACourse:
    """Contains all the data in a single TJA `COURSE:` section."""
    bpm: float
    offset: float
    course: str
    level: int = 0
    balloon: list[int] = field(default_factory=list)
    score_init: int = 0
    score_diff: int = 0
    data: list[str] = field(default_factory=list)
    branches: dict[str, list[TJAMeasure]] = field(
        default_factory=lambda: {k: [TJAMeasure()] for k in BRANCH_NAMES}
    )


@dataclass(slots=True)
class TJASong:
    """Contains all the data in a single TJA (`.tja`) chart file."""
    bpm: float
    offset: float
    courses: dict[str, TJACourse]


@dataclass(slots=True)
class TJAMeasureProcessed:
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
    time_sig: list[int]
    subdivisions: int
    pos_start: int = 0
    pos_end: int = 0
    delay: float = 0.0
    section: bool = False
    levelhold: bool = False
    branch_type: str = ''
    branch_cond: tuple[float, float] = (0.0, 0.0)
    data: list[TJAData] = field(default_factory=list)


@dataclass(slots=True)
class FumenNote:
    """Contains all the byte values for a single Fumen note."""
    note_type: str = ''
    pos: float = 0.0
    score_init: int = 0
    score_diff: int = 0
    padding: float = 0.0
    item: int = 0
    duration: float = 0.0
    multimeasure: bool = False
    hits: int = 0
    hits_padding: int = 0
    drumroll_bytes: bytes = b'\x00\x00\x00\x00\x00\x00\x00\x00'


@dataclass(slots=True)
class FumenBranch:
    """Contains all the data in a single Fumen branch."""
    length: int = 0
    speed: float = 0.0
    padding: int = 0
    notes: list[FumenNote] = field(default_factory=list)


@dataclass(slots=True)
class FumenMeasure:
    """Contains all the data in a single Fumen measure."""
    bpm: float = 0.0
    offset_start: float = 0.0
    offset_end: float = 0.0
    duration: float = 0.0
    gogo: bool = False
    barline: bool = True
    branch_info: list[int] = field(default_factory=lambda: [-1] * 6)
    branches: dict[str, FumenBranch] = field(
        default_factory=lambda: {b: FumenBranch() for b in BRANCH_NAMES}
    )
    padding1: int = 0
    padding2: int = 0

    def set_duration(self,
                     time_sig: list[int],
                     measure_length: int,
                     subdivisions: int) -> None:
        """Compute the millisecond duration of the measure."""
        # First, we compute the duration for a full 4/4 measure.
        full_duration = 4 * 60_000 / self.bpm
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
        self.duration = full_duration * measure_size * measure_ratio

    def set_first_ms_offsets(self, song_offset: float) -> None:
        """Compute the ms offsets for the start/end of the first measure."""
        # First, start with song's OFFSET: metadata
        self.offset_start = song_offset * -1 * 1000  # s -> ms
        # Then, subtract a full 4/4 measure for the current BPM
        self.offset_start -= (4 * 60_000 / self.bpm)
        # Compute the end offset by adding the duration to the start offset
        self.offset_end = self.offset_start + self.duration

    def set_ms_offsets(self,
                       delay: float,
                       prev_measure: 'FumenMeasure') -> None:
        """Compute the ms offsets for the start/end of a given measure."""
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

    def set_branch_info(self,
                        branch_type: str,
                        branch_cond: tuple[float, float],
                        branch_points_total: int,
                        current_branch: str,
                        has_levelhold: bool) -> None:
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
        elif branch_type == 'p':
            vals = []
            for percent in branch_cond:
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
        elif branch_type == 'r':
            vals = [int(v) for v in branch_cond]
            if current_branch == 'normal':
                self.branch_info[0:2] = vals
            elif current_branch == 'professional':
                self.branch_info[2:4] = vals
            elif current_branch == 'master':
                self.branch_info[4:6] = vals


@dataclass(slots=True)
class FumenHeader:
    """Contains all the byte values for a Fumen chart file's header."""
    order: str = "<"
    b000_b431_timing_windows: tuple[float, ...] = field(
        default_factory=lambda: tuple([25.025, 75.075, 108.422]*36)
    )
    b432_b435_has_branches:               int = 0
    b436_b439_hp_max:                     int = 10000
    b440_b443_hp_clear:                   int = 8000
    b444_b447_hp_gain_good:               int = 10
    b448_b451_hp_gain_ok:                 int = 5
    b452_b455_hp_loss_bad:                int = -20
    b456_b459_normal_normal_ratio:        int = 65536
    b460_b463_normal_professional_ratio:  int = 65536
    b464_b467_normal_master_ratio:        int = 65536
    b468_b471_branch_pts_good:         int = 20
    b472_b475_branch_pts_ok:           int = 10
    b476_b479_branch_pts_bad:          int = 0
    b480_b483_branch_pts_drumroll:     int = 1
    b484_b487_branch_pts_good_big:     int = 20
    b488_b491_branch_pts_ok_big:       int = 10
    b492_b495_branch_pts_drumroll_big: int = 1
    b496_b499_branch_pts_balloon:      int = 30
    b500_b503_branch_pts_kusudama:     int = 30
    b504_b507_branch_pts_unknown:      int = 20
    b508_b511_dummy_data:                 int = 12345678
    b512_b515_number_of_measures:         int = 0
    b516_b519_unknown_data:               int = 0

    def parse_header_values(self, raw_bytes: bytes) -> None:
        """Parse a raw string of 520 bytes to get the header values."""
        self._parse_order(raw_bytes)
        raw = raw_bytes  # We use a shortened form just for visual clarity:
        self.b000_b431_timing_windows          = self.unp(raw, "f"*108, 0, 431)
        self.b432_b435_has_branches              = self.unp(raw, "i", 432, 435)
        self.b436_b439_hp_max                    = self.unp(raw, "i", 436, 439)
        self.b440_b443_hp_clear                  = self.unp(raw, "i", 440, 443)
        self.b444_b447_hp_gain_good              = self.unp(raw, "i", 444, 447)
        self.b448_b451_hp_gain_ok                = self.unp(raw, "i", 448, 451)
        self.b452_b455_hp_loss_bad               = self.unp(raw, "i", 452, 455)
        self.b456_b459_normal_normal_ratio       = self.unp(raw, "i", 456, 459)
        self.b460_b463_normal_professional_ratio = self.unp(raw, "i", 460, 463)
        self.b464_b467_normal_master_ratio       = self.unp(raw, "i", 464, 467)
        self.b468_b471_branch_pts_good           = self.unp(raw, "i", 468, 471)
        self.b472_b475_branch_pts_ok             = self.unp(raw, "i", 472, 475)
        self.b476_b479_branch_pts_bad            = self.unp(raw, "i", 476, 479)
        self.b480_b483_branch_pts_drumroll       = self.unp(raw, "i", 480, 483)
        self.b484_b487_branch_pts_good_big       = self.unp(raw, "i", 484, 487)
        self.b488_b491_branch_pts_ok_big         = self.unp(raw, "i", 488, 491)
        self.b492_b495_branch_pts_drumroll_big   = self.unp(raw, "i", 492, 495)
        self.b496_b499_branch_pts_balloon        = self.unp(raw, "i", 496, 499)
        self.b500_b503_branch_pts_kusudama       = self.unp(raw, "i", 500, 503)
        self.b504_b507_branch_pts_unknown        = self.unp(raw, "i", 504, 507)
        self.b508_b511_dummy_data                = self.unp(raw, "i", 508, 511)
        self.b512_b515_number_of_measures        = self.unp(raw, "i", 512, 515)
        self.b516_b519_unknown_data              = self.unp(raw, "i", 516, 519)

    def unp(self, raw_bytes: bytes, type_string: str,
            start: Optional[int] = None, end: Optional[int] = None) -> Any:
        """Unpack a raw byte string according to specific types."""
        if start is not None and end is not None:
            raw_bytes = raw_bytes[start:end+1]
        vals = struct.unpack(self.order + type_string, raw_bytes)
        return vals[0] if len(vals) == 1 else vals

    def _parse_order(self, raw_bytes: bytes) -> None:
        """Parse the order of the song (little or big endian)."""
        self.order = ''
        # Bytes 512-515 are the number of measures. We check the values using
        # both little and big endian, then compare to see which is correct.
        if (self.unp(raw_bytes, ">I", 512, 515) <
                self.unp(raw_bytes, "<I", 512, 515)):
            self.order = ">"
        else:
            self.order = "<"

    def set_hp_bytes(self, n_notes: int, difficulty: str,
                     stars: int) -> None:
        """Compute header bytes related to the soul gauge (HP) behavior."""
        # Note: Ura Oni is equivalent to Oni for soul gauge behavior
        difficulty = 'Oni' if difficulty in ['Ura', 'Edit'] else difficulty
        self._get_hp_from_lookup_tables(n_notes, difficulty, stars)
        self.b440_b443_hp_clear = {'Easy': 6000, 'Normal': 7000,
                                   'Hard': 7000, 'Oni': 8000}[difficulty]

    def _get_hp_from_lookup_tables(self, n_notes: int, difficulty: str,
                                   stars: int) -> None:
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
        with open(os.path.join(pkg_dir, "hp_values.csv"),
                  newline='', encoding="utf-8") as csv_file:
            for num, line in enumerate(csv.DictReader(csv_file)):
                if num+1 == n_notes:
                    self.b444_b447_hp_gain_good = int(line[f"good_{key}"])
                    self.b448_b451_hp_gain_ok = int(line[f"ok_{key}"])
                    self.b452_b455_hp_loss_bad = int(line[f"bad_{key}"])
                    break

    @property
    def raw_bytes(self) -> bytes:
        """Represent the header values as a string of raw bytes."""
        format_string, value_list = '', []
        for byte_field in fields(self):
            value = getattr(self, byte_field.name)
            if byte_field.name == "order":
                format_string = value + format_string
            elif byte_field.name == "b000_b431_timing_windows":
                format_string += "f" * len(value)
                value_list.extend(list(value))
            else:
                format_string += "i"
                value_list.append(value)
        raw_bytes = struct.pack(format_string, *value_list)
        assert len(raw_bytes) == 520
        return raw_bytes


@dataclass(slots=True)
class FumenCourse:
    """Contains all the data in a single Fumen (`.bin`) chart file."""
    header: FumenHeader
    measures: list[FumenMeasure] = field(default_factory=list)
    score_init: int = 0
    score_diff: int = 0
