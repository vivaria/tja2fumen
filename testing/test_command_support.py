import os
import subprocess
from subprocess import CalledProcessError
import shutil
import glob
import traceback

import pytest

from tja2fumen import main as convert


@pytest.mark.parametrize('id_song,err_msg', [
    ['basic_song', None]
])
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
    tb = call_conversion_func(path_test, path_tja_tmp, err_msg, entry_point)
    if err_msg:
        assert err_msg in tb
    else:
        assert tb == ''


def call_conversion_func(path_test, path_tja_tmp, err_msg, entry_point):
    tb = ''

    if entry_point == "python-api":
        if not err_msg:
            convert(argv=[path_tja_tmp])
        else:
            with pytest.raises(ValueError) as e:
                convert(argv=[path_tja_tmp])
            tb = "".join(traceback.format_tb(e.tb))

    elif entry_point == "python-cli":
        if not err_msg:
            subprocess.check_output(f"tja2fumen {path_tja_tmp}", text=True,
                                    shell=True, stderr=subprocess.STDOUT)
        else:
            with pytest.raises(CalledProcessError) as e:
                subprocess.check_output(f"tja2fumen {path_tja_tmp}", text=True,
                                        shell=True, stderr=subprocess.STDOUT)
            tb = e.value.output

    elif entry_point == "exe":
        exe_glob = os.path.join(os.path.split(path_test)[0], "dist", "*.exe")
        exe = glob.glob(exe_glob)[0]
        if not err_msg:
            subprocess.check_output(f"{exe} {path_tja_tmp}", text=True,
                                    shell=True, stderr=subprocess.STDOUT)
        else:
            with pytest.raises(CalledProcessError) as e:
                subprocess.check_output(f"{exe} {path_tja_tmp}", text=True,
                                        shell=True, stderr=subprocess.STDOUT)
            tb = e.value.output

    return tb
