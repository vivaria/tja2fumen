import os
import shutil
import glob

import pytest

from conftest import convert
from tja2fumen.parsers import parse_fumen

CUSTOM_TJA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                              "data", "custom_tjas")
# CUSTOM_TJA_DIR = os.path.join("D:\\", "games", "TaikoTDM",
#                               "CustomSongSources", "ESE")
CUSTOM_TJAS = sum([
    # For each file in the subfolder, keep only if it ends in `.tja`
    [(root, f) for f in files if f.endswith(".tja")]
    # Iterate through all subfolders in the "unpaired_tjas" folder
    for root, _, files in os.walk(CUSTOM_TJA_DIR)
], [])  # sum([list of lists], []) -> https://stackoverflow.com/a/716489
CUSTOM_TJA_PATHS = [os.path.join(root, f) for (root, f) in CUSTOM_TJAS]
CUSTOM_TJA_IDS = [f for (root, f) in CUSTOM_TJAS]


@pytest.mark.parametrize('path_tja', CUSTOM_TJA_PATHS, ids=CUSTOM_TJA_IDS)
@pytest.mark.skipif("CI" in os.environ,
                    reason="Test is only for local debugging")
def test_converted_custom_tjas(path_tja, tmp_path, entry_point):
    """
    A test purely to aid with debugging. It lets me drop a .tja into a
    pre-determined folder and run the conversion, allowing me to set
    breakpoints and debug internal state without any tedious setup.
    """
    # Define the testing directory
    path_test = os.path.dirname(os.path.realpath(__file__))

    # Copy input TJA to working directory
    path_tja_tmp = str(tmp_path / "test.tja")
    shutil.copy(path_tja, path_tja_tmp)

    # Convert TJA file to fumen files
    convert(path_test, path_tja_tmp, entry_point)

    # Fetch output fumen paths
    paths_out = glob.glob(os.path.join(tmp_path, "*.bin"))
    assert paths_out, f"No bin files generated in {tmp_path}"
    order = "xmhne"  # Ura Oni -> Oni -> Hard -> Normal -> Easy
    paths_out = sorted(paths_out,
                       key=lambda s: [order.index(c) if c in order
                                      else len(order) for c in s])
    for path_out in paths_out:
        parse_fumen(path_out, exclude_empty_measures=False)
