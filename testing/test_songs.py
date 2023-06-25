import os
import shutil
import zipfile
import re

import pytest

from tja2fumen import main as convert
from tja2fumen.parsers import readFumen
from tja2fumen.constants import COURSE_IDS, NORMALIZE_COURSE


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
def test_converted_tja_vs_cached_fumen(id_song, tmp_path):
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
    _, _, paths_out = convert(argv=[path_tja_tmp])

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
        assert_song_property(co_song, ca_song, 'header', func=len)
        assert_song_property(co_song, ca_song, 'headerUnknown', func=len)
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

