"""
Functions for writing song data to fumen files (.bin)
"""

import struct
from typing import BinaryIO, Any, List

from tja2fumen.classes import FumenCourse
from tja2fumen.constants import BRANCH_NAMES, FUMEN_TYPE_NOTES


def write_fumen(path_out: str, song: FumenCourse) -> None:
    """
    Write the values in a FumenCourse object to a `.bin` file.

    This operation is the reverse of the `parse_fumen` function. Please refer
    to that function for more details about the fumen file structure.
    """
    with open(path_out, "wb") as file:
        file.write(song.header.raw_bytes)

        for measure in song.measures:
            measure_struct = ([measure.bpm, measure.offset_start,
                               int(measure.gogo), int(measure.barline),
                               measure.padding1] + measure.branch_info +
                              [measure.padding2])
            write_struct(file, song.header.order,
                         format_string="ffBBHiiiiiii",
                         value_list=measure_struct)

            for branch_name in BRANCH_NAMES:
                branch = measure.branches[branch_name]
                branch_struct = [branch.length, branch.padding, branch.speed]
                write_struct(file, song.header.order,
                             format_string="HHf",
                             value_list=branch_struct)

                for note in branch.notes:
                    note_struct = [FUMEN_TYPE_NOTES[note.note_type], note.pos,
                                   note.item, note.padding]
                    if note.hits:
                        extra_vals = [note.hits, note.hits_padding]
                    else:
                        # Max value for H -> 0xffff -> 65535
                        extra_vals = [min(65535, note.score_init),
                                      min(65535, note.score_diff * 4)]
                    note_struct.extend(extra_vals)
                    note_struct.append(note.duration)
                    write_struct(file, song.header.order,
                                 format_string="ififHHf",
                                 value_list=note_struct)

                    if note.note_type.lower() == "drumroll":
                        file.write(note.drumroll_bytes)


def write_struct(file: BinaryIO,
                 order: str,
                 format_string: str,
                 value_list: List[Any]) -> None:
    """Pack (int, float, etc.) values into a string of bytes, then write."""
    try:
        packed_bytes = struct.pack(order + format_string, *value_list)
    except struct.error as err:
        raise ValueError(f"Can't fmt {value_list} as {format_string}") from err
    file.write(packed_bytes)
