import os
import shutil
import zipfile
import re
import glob

import pytest

from tja2fumen import main as convert
from tja2fumen.parsers import readFumen
from tja2fumen.constants import COURSE_IDS, NORMALIZE_COURSE, simpleHeaders, byte_strings


def normalize_type(note_type):
    return re.sub(r'[0-9]', '', note_type)


def assert_song_property(obj1, obj2, prop, measure=None, branch=None, note=None, func=None, abs=None):
    # NB: TJA parser/converter uses 0-based indexing, but TJA files use 1-based indexing.
    #     So, we increment 1 in the error message to more easily identify problematic lines in TJA files.
    msg_failure = f"'{prop}' mismatch"
    msg_failure += f": measure '{measure+1}'" if measure is not None else ""
    msg_failure += f", branch '{branch}'" if branch is not None else ""
    msg_failure += f", note '{note+1}'" if note is not None else ""
    if func:
        assert func(obj1[prop]) == func(obj2[prop]), msg_failure
    elif abs:
        assert obj1[prop] == pytest.approx(obj2[prop], abs=abs), msg_failure
    else:
        assert obj1[prop] == obj2[prop], msg_failure


@pytest.mark.parametrize('id_song', ['mikdp'])
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
        co_song = readFumen(path_out)
        ca_song = readFumen(os.path.join(path_bin, os.path.basename(path_out)))
        # 1. Check song headers
        checkValidHeader(co_song['headerPadding']+co_song['headerMetadata'], strict=True)
        checkValidHeader(ca_song['headerPadding']+ca_song['headerMetadata'])
        # 2. Check song metadata
        assert_song_property(co_song, ca_song, 'order')
        assert_song_property(co_song, ca_song, 'branches')
        assert_song_property(co_song, ca_song, 'scoreInit')
        assert_song_property(co_song, ca_song, 'scoreDiff')
        assert_song_property(co_song, ca_song, 'length')
        assert_song_property(co_song, ca_song, 'measures', func=len)
        # 3. Check measure data
        for i_measure, (co_measure, ca_measure) in enumerate(zip(co_song['measures'], ca_song['measures'])):
            # 3a. Check measure metadata
            assert_song_property(co_measure, ca_measure, 'bpm', i_measure, abs=0.01)
            assert_song_property(co_measure, ca_measure, 'fumenOffset', i_measure, abs=0.5)
            assert_song_property(co_measure, ca_measure, 'gogo', i_measure)
            assert_song_property(co_measure, ca_measure, 'barline', i_measure)
            # 3b. Check measure notes
            for i_branch in ['normal', 'advanced', 'master']:
                co_branch = co_measure[i_branch]
                ca_branch = ca_measure[i_branch]
                assert_song_property(co_branch, ca_branch, 'length', i_measure, i_branch)
                # NB: We check for branching before checking speed as fumens store speed changes even for empty branches
                if co_branch['length'] == 0:
                    continue
                assert_song_property(co_branch, ca_branch, 'speed', i_measure, i_branch)
                for i_note in range(co_branch['length']):
                    co_note = co_branch[i_note]
                    ca_note = ca_branch[i_note]
                    assert_song_property(co_note, ca_note, 'type', i_measure, i_branch, i_note, func=normalize_type)
                    assert_song_property(co_note, ca_note, 'pos', i_measure, i_branch, i_note, abs=0.1)
                    # NB: Drumroll duration doesn't always end exactly on a beat. So, use a larger tolerance.
                    assert_song_property(co_note, ca_note, 'duration', i_measure, i_branch, i_note, abs=10.0)
                    if ca_note['type'] not in ["Balloon", "Kusudama"]:
                        assert_song_property(co_note, ca_note, 'scoreInit', i_measure, i_branch, i_note)
                        assert_song_property(co_note, ca_note, 'scoreDiff', i_measure, i_branch, i_note)
                    # NB: 'item' still needs to be implemented: https://github.com/vivaria/tja2fumen/issues/17
                    # assert_song_property(co_note, ca_note, 'item', i_measure, i_branch, i_note)


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
        # 0. Unknown
        # Notes:
        #   * Breakdown of distribution of different byte combinations:
        #       - 5739/7482 charts: [0, 0, 0, 0]    (Most platforms)
        #       -  386/7482 charts: [0, 151, 68, 0]
        #       -  269/7482 charts: [0, 1, 57, 0]
        #       -   93/7482 charts: [1, 0, 0, 0]
        #       -   93/7482 charts: [0, 64, 153, 0]
        #       -   And more...
        #       -   After this, we see a long tail of hundreds of different unique byte combinations.
        #   * Games with the greatest number of unique byte combinations:
        #       - VitaMS: 258 unique byte combinations
        #       - iOSU: 164 unique byte combinations
        #       - Vita: 153 unique byte combinations
        # Given that most platforms use the values (0, 0, 0, 0), and unique values are very platform-specific,
        # I'm going to stick with (0, 0, 0, 0) bytes when it comes to converting TJA files to fumens.
        if idx in [0, 1, 2, 3]:
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

        # 3. Unknown (possibly related to n_notes)
        elif idx in [12, 13]:
            pass
        elif idx in [16, 17]:
            pass

        # 6. Soul gauge bytes
        # Notes:
        #   * These bytes determine how quickly the soul gauge should increase
        #   * The higher the number of notes, the higher these values will be (i.e. the slower the soul gauge will rise)
        #   * In practice, most of the time [21, 22, 23] will be 255.
        #   * So, this means that byte 20 largely determines the soul gauge increase.
        #   * The precise mapping between n_notes and byte values is complex, and depends on difficulty/stars.
        #      - See also: https://github.com/vivaria/tja2fumen/issues/14
        #   * Re: Byte 21, a very small number of songs (~10) have values 253 or 254 instead of 255.
        #      - This applies to Easy/Normal songs with VERY few notes (<30).
        #      - For these songs, byte 20 will drop BELOW 1 and wrap around back to <=255, decrementing byte 21 by one.
        #      - So, you can think of it like this:
        #         * b21==253: (0*255) + 1-255 = 1-225    (VERY rapid soul gauge increase)
        #         * b21==254: (1*255) + 1-255 = 256-510  (Rapid soul gauge increase)
        #         * b21==255: (2*255) + 1-255 = 511-765  (Moderate to slow soul gauge increase, i.e. most songs)
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

