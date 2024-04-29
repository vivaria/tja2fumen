import os
import shutil
import zipfile
import re
import glob

import pytest

from conftest import convert
from tja2fumen.parsers import parse_fumen


@pytest.mark.parametrize('id_song', [
    pytest.param('butou5'),
    pytest.param('shoto9',
                 marks=pytest.mark.skip("TJA measures do not match fumen.")),
    pytest.param('genpe'),
    pytest.param('gimcho'),
    pytest.param('imcanz'),
    pytest.param('clsca'),
    pytest.param('linda'),
    pytest.param('senpac'),
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
    convert(path_test, path_tja_tmp, entry_point)

    # Fetch output fumen paths
    paths_out = glob.glob(os.path.join(path_temp, "*.bin"))
    assert paths_out, f"No bin files generated in {path_temp}"
    order = "xmhne"  # Ura Oni -> Oni -> Hard -> Normal -> Easy
    paths_out = sorted(paths_out, key=lambda s: [order.index(c) if c in order
                                                 else len(order) for c in s])

    # Extract cached fumen files to working directory
    path_binzip = os.path.join(path_test, "data", f"{id_song}.zip")
    path_bin = os.path.join(path_temp, "ca_bins")
    with zipfile.ZipFile(path_binzip, 'r') as zip_ref:
        zip_ref.extractall(path_bin)

    # Compare cached fumen with generated fumen
    for path_out in paths_out:
        # Difficulty introspection to help with debugging
        i_difficult_id = os.path.basename(path_out).split(".")[0].split("_")[1]
        # 0. Read fumen data (converted vs. cached)
        path_out_fumen = os.path.join(path_bin, os.path.basename(path_out))
        co_song = parse_fumen(path_out, exclude_empty_measures=True)
        ca_song = parse_fumen(path_out_fumen, exclude_empty_measures=True)
        # 1. Check song headers
        checkValidHeader(co_song.header)
        checkValidHeader(ca_song.header)
        for header_property in ['order',
                                'b432_b435_has_branches',
                                'b436_b439_hp_max',
                                'b440_b443_hp_clear',
                                'b444_b447_hp_gain_good',
                                'b448_b451_hp_gain_ok',
                                'b452_b455_hp_loss_bad',
                                'b456_b459_normal_normal_ratio',
                                'b460_b463_normal_professional_ratio',
                                'b464_b467_normal_master_ratio']:
            check(co_song.header, ca_song.header, header_property, abv=1)
        # NB: KAGEKIYO's branching condition is very unique (BIG only), which
        # cannot be expressed in a TJA file. So, we skip checking the
        # `branch_point` header values for KAGEKIYO.
        if id_song != 'genpe':
            for header_property in ['b000_b431_timing_windows',
                                    'b468_b471_branch_pts_good',
                                    'b472_b475_branch_pts_ok',
                                    'b476_b479_branch_pts_bad',
                                    'b480_b483_branch_pts_drumroll',
                                    'b484_b487_branch_pts_good_big',
                                    'b488_b491_branch_pts_ok_big',
                                    'b492_b495_branch_pts_drumroll_big',
                                    'b496_b499_branch_pts_balloon',
                                    'b500_b503_branch_pts_kusudama']:
                check(co_song.header, ca_song.header, header_property)
        # 2. Check song metadata
        check(co_song, ca_song, 'score_init')
        check(co_song, ca_song, 'score_diff')
        # 3. Check measure data
        for i_measure in range(max([len(co_song.measures),
                                    len(ca_song.measures)])):
            # NB: We could assert that len(measures) is the same for both
            # songs, then iterate through zipped measures. But, if there is a
            # mismatched number of measures, we want to know _where_ it
            # occurs. So, we let the comparison go on using the max length of
            # both songs until something else fails.
            co_measure = co_song.measures[i_measure]
            ca_measure = ca_song.measures[i_measure]
            # 3a. Check measure metadata
            check(co_measure, ca_measure, 'bpm', i_measure, abv=0.01)
            check(co_measure, ca_measure, 'offset_start', i_measure, abv=0.15)
            check(co_measure, ca_measure, 'gogo', i_measure)
            check(co_measure, ca_measure, 'barline', i_measure)

            # NB: KAGEKIYO's fumen has some strange details that can't be
            # replicated using the TJA charting format. So, for now, we use a
            # special case to skip checking:
            #     A) notes for certain measures and
            #     B) branchInfo
            if id_song == 'genpe':
                # A) The 2/4 measures in the Ura of KAGEKIYO's official Ura
                # fumen don't match the wikiwiki.jp/TJA charts. In the official
                # fumen, the note ms offsets of branches 5/12/17/etc. go _past_
                # the duration of the measure. This behavior is impossible to
                # represent using the TJA format, so we skip checking notes
                # for these measures, since the rest of the measures have
                # perfect note ms offsets anyway.
                if (i_difficult_id == "x" and
                        i_measure in [5, 6, 12, 13, 17, 18, 26, 27,
                                      46, 47, 51, 52, 56, 57]):
                    continue
                # B) The branching condition for KAGEKIYO is very strange
                # (accuracy for the 7 big notes in the song) So, we only test
                # the branchInfo bytes for non-KAGEKIYO songs:
            else:
                check(co_measure, ca_measure, 'branch_info', i_measure)

            # 3b. Check measure notes
            for i_branch in ['normal', 'professional', 'master']:
                co_branch = co_measure.branches[i_branch]
                ca_branch = ca_measure.branches[i_branch]
                # NB: We only check speed for non-empty branches, as fumens
                # store speed changes even for empty branches.
                if co_branch.length != 0:
                    check(co_branch, ca_branch, 'speed', i_measure, i_branch)
                # NB: We could assert that len(notes) is the same for both
                # songs, then iterate through zipped notes. But, if there is a
                # mismatched number of notes, we want to know _where_ it
                # occurs. So, we let the comparison go on using the max length
                # of both branches until something else fails.
                for i_note in range(max([co_branch.length, ca_branch.length])):
                    co_note = co_branch.notes[i_note]
                    ca_note = ca_branch.notes[i_note]
                    check(co_note, ca_note, 'note_type', i_measure,
                          i_branch, i_note, func=normalize_type)
                    check(co_note, ca_note, 'pos', i_measure,
                          i_branch, i_note, abv=0.1)
                    # NB: Drumroll duration doesn't always end exactly on a
                    # beat. Plus, TJA charters often eyeball drumrolls,
                    # leading them to be often off by a 1/4th/8th/16th/etc.
                    # These charting errors are fixable, but tedious to do
                    # when writing tests. So, I've added a try/except so that
                    # they can be checked locally with a breakpoint when
                    # adding new songs, but so that fixing every
                    # duration-related chart error isn't 100% mandatory.
                    try:
                        check(co_note, ca_note, 'duration', i_measure,
                              i_branch, i_note, abv=25.0)
                    except AssertionError:
                        pass
                    if ca_note.note_type not in ["Balloon", "Kusudama"]:
                        check(co_note, ca_note, 'score_init', i_measure,
                              i_branch, i_note)
                        check(co_note, ca_note, 'score_diff', i_measure,
                              i_branch, i_note)
                    # NB: 'item' still needs to be implemented:
                    # https://github.com/vivaria/tja2fumen/issues/17
                    # check(co_note, ca_note, 'item', i_measure,
                    #       i_branch, i_note)


def check(converted_obj, cached_obj, prop, measure=None,
          branch=None, note=None, func=None, abv=None):
    # NB: TJA parser/converter uses 0-based indexing, but TJA files use
    # 1-based indexing. So, we increment 1 in the error message to more easily
    # identify problematic lines in TJA files.
    msg_failure = f"'{prop}' mismatch"
    msg_failure += f": measure '{measure+1}'" if measure is not None else ""
    msg_failure += f", branch '{branch}'" if branch is not None else ""
    msg_failure += f", note '{note+1}'" if note is not None else ""
    converted_val = converted_obj.__getattribute__(prop)
    cached_val = cached_obj.__getattribute__(prop)
    if func:
        assert func(converted_val) == func(cached_val), msg_failure
    elif abv:
        assert converted_val == pytest.approx(cached_val, abs=abv), msg_failure
    else:
        assert converted_val == cached_val, msg_failure


def normalize_type(note_type):
    return re.sub(r'[0-9]', '', note_type)


def checkValidHeader(header):
    assert len(header.raw_bytes)                      == 520
    assert header.b432_b435_has_branches              in [0, 1]
    assert header.b436_b439_hp_max                    == 10000
    assert header.b440_b443_hp_clear                  in [6000, 7000, 8000]
    assert 10   <= header.b444_b447_hp_gain_good      <= 1020
    assert 5    <= header.b448_b451_hp_gain_ok        <= 1020
    assert -765 <= header.b452_b455_hp_loss_bad       <= -20
    assert header.b456_b459_normal_normal_ratio       <= 65536
    assert header.b460_b463_normal_professional_ratio <= 65536
    assert header.b464_b467_normal_master_ratio       <= 65536
    assert header.b468_b471_branch_pts_good           in [20, 0, 1, 2]
    assert header.b472_b475_branch_pts_ok             in [10, 0, 1]
    assert header.b476_b479_branch_pts_bad            == 0
    assert header.b480_b483_branch_pts_drumroll       in [1, 0]
    assert header.b484_b487_branch_pts_good_big       in [20, 0, 1, 2]
    assert header.b488_b491_branch_pts_ok_big         in [10, 0, 1]
    assert header.b492_b495_branch_pts_drumroll_big   in [1, 0]
    assert header.b496_b499_branch_pts_balloon        in [30, 0, 1]
    assert header.b500_b503_branch_pts_kusudama       in [30, 0]
