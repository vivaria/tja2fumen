import os
import shutil
import zipfile
import re
import glob

import pytest

from tja2fumen import main as convert
from tja2fumen.parsers import readFumen
from tja2fumen.constants import COURSE_IDS, NORMALIZE_COURSE, simpleHeaders, byte_strings


@pytest.mark.parametrize('id_song', [
    pytest.param('genpe'),
    pytest.param('gimcho'),
    pytest.param('imcanz'),
    pytest.param('clsca'),
    pytest.param('linda'),
    pytest.param('senpac'),
    pytest.param('butou5'),
    pytest.param('hol6po'),
    pytest.param('mikdp'),
    pytest.param('ia6cho'),
])
def test_converted_tja_vs_cached_fumen(id_song, tmp_path, entry_point):
    # Define the testing directory
    path_test = os.path.dirname(os.path.realpath(__file__))

    # Define the working directory
    path_temp = os.path.join(tmp_path, id_song)
    os.mkdir(path_temp)

    # Copy input TJA to working directory
    path_tja = os.path.join(path_test, "data", f"{id_song}.tja")
    path_tja_tmp = os.path.join(path_temp, f"{id_song}.tja")
    shutil.copy(path_tja, path_tja_tmp)

    # Convert TJA file to fumen files
    if entry_point == "python-api":
        convert(argv=[path_tja_tmp])
    elif entry_point == "python-cli":
        os.system(f"tja2fumen {path_tja_tmp}")
    elif entry_point == "exe":
        exe_path = glob.glob(os.path.join(os.path.split(path_test)[0], "dist", "*.exe"))[0]
        os.system(f"{exe_path} {path_tja_tmp}")

    # Fetch output fumen paths
    paths_out = glob.glob(os.path.join(path_temp, "*.bin"))
    assert paths_out, f"No bin files generated in {path_temp}"
    order = "xmhne"  # Ura Oni -> Oni -> Hard -> Normal -> Easy
    paths_out = sorted(paths_out, key=lambda s: [order.index(c) if c in order else len(order) for c in s])

    # Extract cached fumen files to working directory
    path_binzip = os.path.join(path_test, "data", f"{id_song}.zip")
    path_bin = os.path.join(path_temp, "ca_bins")
    with zipfile.ZipFile(path_binzip, 'r') as zip_ref:
        zip_ref.extractall(path_bin)

    # Compare cached fumen with generated fumen
    for path_out in paths_out:
        # Difficulty introspection to help with debugging
        i_difficult_id = os.path.basename(path_out).split(".")[0].split("_")[1]
        i_difficulty = NORMALIZE_COURSE[{v: k for k, v in COURSE_IDS.items()}[i_difficult_id]]  # noqa
        # 0. Read fumen data (converted vs. cached)
        co_song = readFumen(path_out, exclude_empty_measures=True)
        ca_song = readFumen(os.path.join(path_bin, os.path.basename(path_out)), exclude_empty_measures=True)
        # 1. Check song headers
        checkValidHeader(co_song.headerPadding+co_song.headerMetadata, strict=True)
        checkValidHeader(ca_song.headerPadding+ca_song.headerMetadata)
        # 2. Check song metadata
        assert_song_property(co_song, ca_song, 'order')
        assert_song_property(co_song, ca_song, 'hasBranches')
        assert_song_property(co_song, ca_song, 'scoreInit')
        assert_song_property(co_song, ca_song, 'scoreDiff')
        # 3. Check measure data
        for i_measure in range(max([len(co_song.measures), len(ca_song.measures)])):
            # NB: We could assert that len(measures) is the same for both songs, then iterate through zipped measures.
            # But, if there is a mismatched number of measures, we want to know _where_ it occurs. So, we let the
            # comparison go on using the max length of both songs until something else fails.
            co_measure = co_song.measures[i_measure]
            ca_measure = ca_song.measures[i_measure]
            # 3a. Check measure metadata
            assert_song_property(co_measure, ca_measure, 'bpm', i_measure, abs=0.01)
            assert_song_property(co_measure, ca_measure, 'fumenOffsetStart', i_measure, abs=0.15)
            assert_song_property(co_measure, ca_measure, 'gogo', i_measure)
            assert_song_property(co_measure, ca_measure, 'barline', i_measure)
            assert_song_property(co_measure, ca_measure, 'branchInfo', i_measure)
            # 3b. Check measure notes
            for i_branch in ['normal', 'advanced', 'master']:
                co_branch = co_measure.branches[i_branch]
                ca_branch = ca_measure.branches[i_branch]
                # NB: We check for branching before checking speed as fumens store speed changes even for empty branches
                if co_branch.length == 0:
                    continue
                assert_song_property(co_branch, ca_branch, 'speed', i_measure, i_branch)
                # NB: We could assert that len(notes) is the same for both songs, then iterate through zipped notes.
                # But, if there is a mismatched number of notes, we want to know _where_ it occurs. So, we let the
                # comparison go on using the max length of both branches until something else fails.
                for i_note in range(max([co_branch.length, ca_branch.length])):
                    co_note = co_branch.notes[i_note]
                    ca_note = ca_branch.notes[i_note]
                    assert_song_property(co_note, ca_note, 'note_type', i_measure, i_branch, i_note, func=normalize_type)
                    assert_song_property(co_note, ca_note, 'pos', i_measure, i_branch, i_note, abs=0.1)
                    # NB: Drumroll duration doesn't always end exactly on a beat. Plus, TJA charters often eyeball
                    #     drumrolls, leading them to be often off by a 1/4th/8th/16th/32th/etc. These charting errors
                    #     are fixable, but tedious to do when writing tests. So, I've added a try/except so that they
                    #     can be checked locally with a breakpoint when adding new songs, but so that fixing every
                    #     duration-related chart error isn't 100% mandatory.
                    try:
                        assert_song_property(co_note, ca_note, 'duration', i_measure, i_branch, i_note, abs=25.0)
                    except AssertionError:
                        pass
                    if ca_note.note_type not in ["Balloon", "Kusudama"]:
                        assert_song_property(co_note, ca_note, 'scoreInit', i_measure, i_branch, i_note)
                        assert_song_property(co_note, ca_note, 'scoreDiff', i_measure, i_branch, i_note)
                    # NB: 'item' still needs to be implemented: https://github.com/vivaria/tja2fumen/issues/17
                    # assert_song_property(co_note, ca_note, 'item', i_measure, i_branch, i_note)


def assert_song_property(converted_obj, cached_obj, prop, measure=None, branch=None, note=None, func=None, abs=None):
    # NB: TJA parser/converter uses 0-based indexing, but TJA files use 1-based indexing.
    #     So, we increment 1 in the error message to more easily identify problematic lines in TJA files.
    msg_failure = f"'{prop}' mismatch"
    msg_failure += f": measure '{measure+1}'" if measure is not None else ""
    msg_failure += f", branch '{branch}'" if branch is not None else ""
    msg_failure += f", note '{note+1}'" if note is not None else ""
    converted_val = converted_obj.__getattribute__(prop)
    cached_val = cached_obj.__getattribute__(prop)
    if func:
        assert func(converted_val) == func(cached_val), msg_failure
    elif abs:
        assert converted_val == pytest.approx(cached_val, abs=abs), msg_failure
    else:
        assert converted_val == cached_val, msg_failure


def normalize_type(note_type):
    return re.sub(r'[0-9]', '', note_type)


def checkValidHeader(headerBytes, strict=False):
    # Fumen headers should contain 512 bytes.
    assert len(headerBytes) == 512
    # The header for fumens can be split into 2 groups: The first 432 bytes (padding), and the last 80 bytes (metadata).
    headerPadding = headerBytes[:432]
    headerMetadata = headerBytes[-80:]

    # 1. Check the header's padding bytes for several possible combinations
    # 1a. These simple headers (12-byte substrings repeated 36 times) are used for many Gen2 systems (AC, Wii, etc.)
    cond1 = headerPadding in simpleHeaders
    # 1b. Starting with Gen3, they began using unique headers for every song. (3DS and PSPDX are the big offenders.)
    #   - They seem to be some random combination of b_x00 + one of the non-null byte substrings.
    #   - To avoid enumerating every combination of 432 bytes, we do a lazy check instead.
    cond2 = (byte_strings['x00'] in headerPadding and
             any(b in headerPadding for b in
                 [byte_strings[key] for key in ['431', '432', '433', '434', 'V1', 'V2', 'V3']]))
    # 1c. The PS4 song 'wii5op' is a special case: It throws in this odd 'g1' string in combo with 2 other substrings.
    cond3 = (byte_strings['g1'] in headerPadding and
             any(b in headerPadding for b in [byte_strings[key] for key in ['431', 'V2']]))
    # Otherwise, this is some unknown header we haven't seen before.
    assert cond1 or cond2 or cond3, "Header padding bytes do not match expected fumen byte substrings."

    # 2. Check the header's metadata bytes
    for idx, val in enumerate(headerMetadata):
        # Whether the song has branches
        if idx == 0:
            assert val in [0, 1], f"Expected 0/1 at position '{idx}', got '{val}' instead."

        # 0. Unknown
        # Notes:
        #   * Breakdown of distribution of different byte combinations:
        #       - 5832/7482 charts: [0, 0, 0]    (Most platforms)
        #       -  386/7482 charts: [151, 68, 0]
        #       -  269/7482 charts: [1, 57, 0]
        #       -   93/7482 charts: [64, 153, 0]
        #       -   And more...
        #       -   After this, we see a long tail of hundreds of different unique byte combinations.
        #   * Games with the greatest number of unique byte combinations:
        #       - VitaMS: 258 unique byte combinations
        #       - iOSU: 164 unique byte combinations
        #       - Vita: 153 unique byte combinations
        # Given that most platforms use the values (0, 0, 0), and unique values are very platform-specific,
        # I'm going to stick with (0, 0, 0) bytes when it comes to converting TJA files to fumens.
        elif idx in [1, 2, 3]:
            if strict:
                assert val == 0, f"Expected 0 at position '{idx}', got '{val}' instead."
            else:
                pass

        # 1. <padding>
        # Notes: These values are ALWAYS (16, 39), for every valid fumen.
        elif idx == 4:
            assert val == 16, f"Expected 16 at position '{idx}', got '{val}' instead."
        elif idx == 5:
            assert val == 39, f"Expected 39 at position '{idx}', got '{val}' instead."

        # 2. Difficulty
        # Notes:
        #   * Breakdown of distribution of different byte combinations:
        #       - 1805/7482 charts: [112, 23] (Easy)
        #       - 3611/7482 charts: [88, 27]  (Normal, Hard)
        #       - 2016/7482 charts: [64, 31]  (Oni, Ura)
        #   * In other words, all 5 difficulties map to only three different byte-pairs across all valid fumens.
        elif idx == 8:
            assert val in [88, 64, 112], f"Expected 88/64/112 at position '{idx}', got '{val}' instead."
        elif idx == 9:
            assert val in [27, 31, 23], f"Expected 27/31/23 at position '{idx}', got '{val}' instead."

        # 6. Soul gauge bytes
        # Notes:
        #   * These bytes determine how quickly the soul gauge should increase
        #   * The precise mapping between n_notes and byte values is complex, and depends on difficulty/stars.
        #      - See also: https://github.com/vivaria/tja2fumen/issues/14
        #   * Generally speaking, though, the higher the number of notes, then:
        #      - The lower that bytes 12/16 will go.
        #      - The higher that byte 21 will go.
        #   * Also, most of the time [13, 17] will be 0 and [21, 22, 23] will be 255.
        #   * However, a very small number of songs (~30) have values different from 0/255.
        #      - This applies to Easy/Normal songs with VERY few notes (<30).
        #         * Bytes 12/16 will go above 255 and wrap around back to >=0, incrementing bytes 13/17 by one.
        #         * Byte 20 will go below and wrap around back to <=255, decrementing byte 21 by one.
        elif idx == 12:
            assert 1 <= val <= 255
        elif idx == 13:
            assert val in [0, 1, 2, 3]
        elif idx == 16:
            assert 1 <= val <= 255
        elif idx == 17:
            assert val in [0, 1, 2, 3]
        elif idx == 20:
            assert 1 <= val <= 255
        elif idx == 21:
            assert val in [253, 254, 255]
        elif idx in [22, 23]:
            assert val == 255

        # 7. <padding>
        # Notes:
        #   * For the vast majority (99%) of charts, bytes 21, 22, and 23 have the values (1, 1, 1)
        #   * For a small minority of charts (~100), one or both of bytes 30/34 will be 0 instead of 1
        # Given that most platforms use the values (1, 1, 1), and unique values are very platform-specific,
        # I'm going to stick with (1, 1, 1) when it comes to converting TJA files to fumens.
        elif idx == 26:
            assert val == 1, f"Expected 1 at position '{idx}', got '{val}' instead."
        elif idx in [30, 34]:
            if strict:
                assert val == 1, f"Expected 1 at position '{idx}', got '{val}' instead."
            else:
                assert val in [1, 0], f"Expected 1/0 at position '{idx}', got '{val}' instead."

        # 8. Unknown
        # Notes:
        #   * For the vast majority (99%) of charts, bytes (28, 29) and (32, 33) have the values (0, 0)
        #   * But, for some games (Gen3Arcade, 3DS), unique values will be stored in these bytes.
        # Given that most platforms use the values (0, 0), and unique values are very platform-specific,
        # I'm going to stick with (0, 0) when it comes to converting TJA files to fumens.
        elif idx in [28, 29]:
            if strict:
                assert val == 0, f"Expected 0 at position '{idx}', got '{val}' instead."
            else:
                pass
        elif idx in [32, 33]:
            if strict:
                assert val == 0, f"Expected 0 at position '{idx}', got '{val}' instead."
            else:
                pass

        # 9. <padding>
        # Notes:
        #   * For the vast majority (99%) of charts, bytes (36, 40, 48) and (52, 56, 50) have the values (20, 10, 1)
        #   * For a small minority of charts (~45), these values can be 0,1,2 instead.
        # Given that most platforms use the values (20, 10, 1), and unique values are very platform-specific,
        # I'm going to stick with (20, 10, 0) when it comes to converting TJA files to fumens.
        elif idx in [36, 52]:
            if strict:
                assert val == 20, f"Expected 20 at position '{idx}', got '{val}' instead."
            else:
                assert val in [20, 0, 1, 2], f"Expected 20 (or 0,1,2) at position '{idx}', got '{val}' instead."
        elif idx in [40, 56]:
            if strict:
                assert val == 10, f"Expected 10 at position '{idx}', got '{val}' instead."
            else:
                assert val in [10, 0, 1], f"Expected 10 (or 0,1) at position '{idx}', got '{val}' instead."
        elif idx in [48, 60]:
            if strict:
                assert val == 1, f"Expected 1 at position '{idx}', got '{val}' instead."
            else:
                # NB: See below for an explanation for why '255' is included for byte 60
                assert val in [1, 0, 255], f"Expected 1 (or 0) at position '{idx}', got '{val}' instead."

        # 10. <padding>
        # Notes:
        #   * For the vast majority (99%) of charts, bytes (61, 62, 63) have the values (0, 0, 0)
        #   * However, for iOS and iOSU charts (144 total), bytes (60, 61, 62, 63) are (255, 255, 255, 255) instead.
        # Given that most platforms use the values (0, 0, 0), and unique values are very platform-specific,
        # I'm going to stick with (0, 0, 0) when it comes to converting TJA files to fumens.
        elif idx in [61, 62, 63]:
            if strict:
                assert val == 0, f"Expected 0/255 at position '{idx}', got '{val}' instead."
            else:
                assert val in [0, 255], f"Expected 0/255 at position '{idx}', got '{val}' instead."

        # 11. <padding>
        # Notes:
        #   * Breakdown of distribution of different byte combinations:
        #       - 5809/7482 charts: (30, 30, 20)
        #       - 1577/7482 charts: (30, 30, 0)
        #       -   41/7482 charts: (0, 0, 0)
        #       -    3/7482 charts: (1, 0, 0)
        #       -    2/7482 charts: (0, 0, 20)
        # Given that most platforms use the values (30, 30, 20), and unique values are very platform-specific,
        # I'm going to ignore the unique bytes when it comes to converting TJA files to fumens.
        elif idx in [64, 68]:
            if strict:
                assert val == 30, f"Expected 30 at position '{idx}', got '{val}' instead."
            else:
                assert val in [30, 0, 1], f"Expected 30 (or 0,1) at position '{idx}', got '{val}' instead."
        elif idx == 72:
            if strict:
                assert val == 20, f"Expected 20 at position '{idx}', got '{val}' instead."
            else:
                assert val in [20, 0], f"Expected 20 (or 0) at position '{idx}', got '{val}' instead."

        # 12. Difficulty (Gen2) and ???? (Gen3)
        # Notes:
        #   * In Gen2 charts (AC, Wii), these values would be one of 4 different byte combinations.
        #   * These values correspond to the difficulty of the song (no Uras in Gen2, hence 4 values):
        #      - [192, 42, 12]  (Easy)
        #      - [92, 205, 23]  (Normal)
        #      - [8, 206, 31]   (Hard)
        #      - [288, 193, 44] (Oni)
        #   * However, starting in Gen3 (AC, console), these bytes were given unique per-song, per-chart values.
        #      - In total, Gen3 contains 6449 unique combinations of bytes (with some minor overlaps between games).
        # For TJA conversion, I plan to just stick with one set of values (78, 97, 188) -- also used by tja2bin.exe.
        elif idx == 76:
            if strict:
                assert val == 78, f"Expected 78 at position '{idx}', got '{val}' instead."
            else:
                pass
        elif idx == 77:
            if strict:
                assert val == 97, f"Expected 20 at position '{idx}', got '{val}' instead."
            else:
                pass
        elif idx == 78:
            if strict:
                assert val == 188, f"Expected 20 at position '{idx}', got '{val}' instead."
            else:
                pass

        # 13. Empty bytes
        else:
            assert val == 0, f"Expected 0 at position '{idx}', got '{val}' instead."

