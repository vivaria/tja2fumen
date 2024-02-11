import glob
import os
import subprocess
from subprocess import CalledProcessError

import pytest

from tja2fumen import main as api_convert


def pytest_addoption(parser):
    parser.addoption("--entry-point", action="store", default="python-api")


@pytest.fixture
def entry_point(request):
    return request.config.getoption("--entry-point")


def convert(path_test, path_tja_tmp, entry_point, err_msg=None):
    tb = ''

    if entry_point == "python-api":
        if not err_msg:
            api_convert(argv=[path_tja_tmp])
        else:
            try:
                api_convert(argv=[path_tja_tmp])
            except Exception as e:
                tb = str(e)

    elif entry_point == "python-cli":
        if not err_msg:
            subprocess.check_output(f"tja2fumen {path_tja_tmp}", text=True,
                                    shell=True, stderr=subprocess.STDOUT)
        else:
            try:
                subprocess.check_output(f"tja2fumen {path_tja_tmp}", text=True,
                                        shell=True, stderr=subprocess.STDOUT)
            except CalledProcessError as e:
                tb = str(e)

    elif entry_point == "exe":
        exe_glob = os.path.join(os.path.split(path_test)[0], "dist", "*.exe")
        exe = glob.glob(exe_glob)[0]
        if not err_msg:
            subprocess.check_output(f"{exe} {path_tja_tmp}", text=True,
                                    shell=True, stderr=subprocess.STDOUT)
        else:
            try:
                subprocess.check_output(f"{exe} {path_tja_tmp}", text=True,
                                        shell=True, stderr=subprocess.STDOUT)
            except CalledProcessError as e:
                tb = str(e)

    return tb
