import os
import shutil

import pytest

from conftest import convert


@pytest.mark.parametrize('id_song,err_msg', [
    ['basic_song', None],
    ['basic_song_2P', None],
    ['unsupported', 'UserWarning'],
    ['notes_double_kusudama', None],
    ['notes_hands', None],
    ['notes_sim_only', None],
    ['notes_senotechange', None],
    ['missing_score', None],
    ['missing_balloon', "UserWarning"],
    ['missing_course', "Invalid COURSE value:"],
    ['missing_level', "Invalid LEVEL value:"]
])
@pytest.mark.skipif("CI" in os.environ, reason="Local-only")
def test_expected_errors(id_song, err_msg, tmp_path, entry_point):
    # Define the testing directory
    path_test = os.path.dirname(os.path.realpath(__file__))

    # Define the working directory
    path_temp = os.path.join(tmp_path, id_song)
    os.mkdir(path_temp)

    # Copy input TJA to working directory
    path_tja = os.path.join(path_test, "data", "dummy_tjas", f"{id_song}.tja")
    path_tja_tmp = os.path.join(path_temp, f"{id_song}.tja")
    shutil.copy(path_tja, path_tja_tmp)

    # Try to convert TJA file to fumen files, then check the error traceback
    if err_msg and 'Warning' in err_msg:
        with pytest.warns():
            convert(path_test, path_tja_tmp, entry_point)
    else:
        tb = convert(path_test, path_tja_tmp, entry_point, err_msg)
        if err_msg:
            assert err_msg in tb
        else:
            assert tb == ''
