import sys
import struct
import math

from constants import simpleHeaders, byte_strings


def checkValidHeader(header):
    # These simple headers (substrings repeated 36 times) are used for many Gen2 systems (AC, Wii, etc.)
    if header in simpleHeaders:
        return True
    # Starting with Gen3, they began using unique headers for every song. (3DS and PSPDX are the big offenders.)
    #   They seem to be some random combination of b_x00 + one of the non-null byte substrings.
    #   To avoid enumerating every combination of 432 bytes, we do a lazy check instead.
    elif (byte_strings['x00'] in header and
            any(b in header for b in [byte_strings[key] for key in ['431', '432', '433', '434', 'V1', 'V2', 'V3']])):
        return True
    # The PS4 song 'wii5op' is a special case: It throws in this odd 'g1' string in combo with other substrings.
    elif (byte_strings['g1'] in header and
            any(b in header for b in [byte_strings[key] for key in ['431', 'V2']])):
        return True
    # Otherwise, this is some unknown header we haven't seen before.
    # Typically, these will be tja2bin.exe converted files with a completely invalid header.
    else:
        return False


def validateHeaderMetadata(headerBytes):
    for idx, val in enumerate(headerBytes):
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
        # I'm going to ignore the unique bytes when it comes to converting TJA files to fumens.
        if idx in [0, 1, 2, 3]:
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

        # 3. TODO: Note count / drumroll count / note score / song length / etc.
        # Notes:
        # - For Oni songs, bytes (12, 16, 20) correlate with note count (bytes 13, 17 are always 0):
        #     * If we look at 10* Oni songs, we see the following 2 ends of the spectrum for bytes (12, 13, 16, 17, 20):
        #         - (9, 0, 4, 0, 238): Sotsu Omeshii Full (1487 notes)
        #         - (9, 0, 5, 0, 237): Shimedore 2000 (1414 notes)
        #                        Shimedore 2000+ (1414 notes)
        #                        Silent Jealousy (1408 notes)
        #                        The Future of the Taiko Drum (1400 notes)
        #                        Dairouketen Maou (1396 notes)
        #         - (10, 0, 5, 0, 235): Yugen no Ran (1262 notes)
        #         - [...]
        #         - (27, 0, 14, 0, 201): Pan vs. Gohan! Daikessen! [Normal Route] (480 notes)
        #         - (28, 0, 14, 0, 200): Anata to Tu-lat-tat-ta (468 notes)
        #         - (34, 0, 17, 0, 189): GeGeGe no Kitaro [6th Season] (390 notes)
        #     * Just to confirm, if we look at the top/bottom 9* songs, we see:
        #         - (8, 0, 4, 0, 240): Hypnosismic -Division Battle Anthem- (1608 notes)
        #         - (10, 0, 8, 0, 225): Rokuchounen to Ichiyo Monogatari (846 notes)
        #         - (48, 0, 24, 0, 160): Inscrutable Battle (274 notes)
        #     * So, to summarize, for Oni songs:
        #         - As the number of notes increases, bytes 12/16 decrease, and byte 20 increases
        #         - As the number of notes decreases, bytes 12/16 increase, and byte 20 decreases
        #
        # - However, the relationship doesn't hold when checking, for example, 1* Easy charts
        #     * Bytes 13 and 17, which were previously always 0, are now 0/1/2:
        #         - (249, 0, 187, 0, 132): Let's go! Smile Precure (67 notes)
        #         - (249, 1, 123, 1, 3): Anata to Tu-lat-tat-ta (33 notes)
        #         - (44, 2, 161, 1, 234): Do you want to build a Snowman? (30 notes)
        #         - (0, 1, 192, 0, 128): Odoru Ponpokorin (65 notes)
        #     * I'm having trouble making sense of the relationships between these bytes.
        elif idx in [12, 13]:
            pass
        elif idx in [16, 17]:
            pass
        elif idx == 20:
            pass

        # 6. <padding>
        # Notes:
        #   * For the vast majority (99%) of charts, bytes 21, 22, and 23 have the values (255, 255, 255)
        #   * For a very tiny minority of charts (~5), byte 21 will be 254 or 253 instead.
        # Given that most platforms use the values (255, 255, 255), and unique values are very platform-specific,
        # I'm going to ignore the unique bytes when it comes to converting TJA files to fumens.
        elif idx in [21, 22, 23]:
            assert val in [253, 254, 255], f"Expected 255 at position '{idx}', got '{val}' instead."

        # 7. <padding>
        # Notes:
        #   * For the vast majority (99%) of charts, bytes 21, 22, and 23 have the values (1, 1, 1)
        #   * For a small minority of charts (~100), one or both of bytes 30/34 will be 0 instead of 1
        # Given that most platforms use the values (1, 1, 1), and unique values are very platform-specific,
        # I'm going to ignore the unique bytes when it comes to converting TJA files to fumens.
        elif idx == 26:
            assert val == 1, f"Expected 1 at position '{idx}', got '{val}' instead."
        elif idx in [30, 34]:
            assert val in [1, 0], f"Expected 1/0 at position '{idx}', got '{val}' instead."

        # 8. Unknown
        # Notes:
        #   * For the vast majority (99%) of charts, bytes (28, 29) and (32, 33) have the values (0, 0)
        #   * But, for some games (Gen3Arcade, 3DS), unique values will be stored in these bytes.
        # Given that most platforms use the values (0, 0), and unique values are very platform-specific,
        # I'm going to ignore the unique bytes when it comes to converting TJA files to fumens.
        elif idx in [28, 29]:
            pass
        elif idx in [32, 33]:
            pass

        # 8. <padding>
        # Notes:
        #   * For the vast majority (99%) of charts, bytes (36, 40, 48) and (52, 56, 50) have the values (20, 10, 1)
        #   * For a small minority of charts (~45), these values can be 0,1,2 instead.
        # Given that most platforms use the values (20, 10, 1), and unique values are very platform-specific,
        # I'm going to ignore the unique bytes when it comes to converting TJA files to fumens.
        elif idx in [36, 52]:
            assert val in [20, 0, 1, 2], f"Expected 20 (or 0,1,2) at position '{idx}', got '{val}' instead."
        elif idx in [40, 56]:
            assert val in [10, 0, 1], f"Expected 10 (or 0,1) at position '{idx}', got '{val}' instead."
        elif idx in [48, 60]:
            # NB: See below for an explanation about '255' for byte 60
            assert val in [1, 0, 255], f"Expected 1 (or 0) at position '{idx}', got '{val}' instead."

        # 8. <padding>
        # Notes:
        #   * For the vast majority (99%) of charts, bytes (61, 62, 63) have the values (0, 0, 0)
        #   * However, for iOS and iOSU charts (144 total), bytes (60, 61, 62, 63) are (255, 255, 255, 255) instead.
        # Given that most platforms use the values (0, 0, 0), and unique values are very platform-specific,
        # I'm going to ignore the unique bytes when it comes to converting TJA files to fumens.
        elif idx in [61, 62, 63]:
            assert val in [0, 255], f"Expected 0/255 at position '{idx}', got '{val}' instead."

        # 9. <padding>
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
            assert val in [30, 0, 1], f"Expected 30/0 at position '{idx}', got '{val}' instead."
        elif idx == 72:
            assert val in [20, 0], f"Expected 20/0 at position '{idx}', got '{val}' instead."

        # 10. Difficulty (Gen2) and ???? (Gen3)
        # Notes:
        #   * In Gen2 charts (AC, Wii), these values would be one of 4 different byte combinations.
        #   * These values correspond to the difficulty of the song (no Uras in Gen2, hence 4 values):
        #      - [192, 42, 12]  (Easy)
        #      - [92, 205, 23]  (Normal)
        #      - [8, 206, 31]   (Hard)
        #      - [288, 193, 44] (Oni)
        #   * However, starting in Gen3 (AC, console), these bytes were given unique per-song, per-chart values.
        #      - In total, Gen3 contains 6449 unique combinations of bytes (with some minor overlaps between games).
        # For TJA conversion, I plan to just stick with the Gen2 scheme (and make up the missing value for Uras),
        # which would be much easier than trying to figure out the Gen3 scheme.
        elif idx in [76, 77, 78]:
            pass

        # 11. Empty bytes
        else:
            assert val == 0, f"Expected 0 at position '{idx}', got '{val}' instead."


def computeSoulGaugeByte(n_notes):
    # I don't think this is fully accurate. It doesn't work for non-Oni songs, and it's usually off by a bit.
    A = -85.548628
    B = 44.780199
    return round(A+B*math.log(n_notes))


def readStruct(file, order, format_string, seek=None):
    """
    Interpret bytes as packed binary data.

    Arguments:
        - file: The fumen's file object (presumably in 'rb' mode).
        - order: '<' or '>' (little or big endian).
        - format_string: String made up of format characters that describes the data layout.
                         Full list of available format characters:
                             (https://docs.python.org/3/library/struct.html#format-characters)
        - seek: The position of the read pointer to be used within the file.

    Return values:
        - interpreted_string: A string containing interpreted byte values,
                              based on the specified 'fmt' format characters.
    """
    if seek:
        file.seek(seek)
    expected_size = struct.calcsize(order + format_string)
    byte_string = file.read(expected_size)
    # One "official" fumen (AC11\deo\deo_n.bin) runs out of data early
    # This workaround fixes the issue by appending 0's to get the size to match
    if len(byte_string) != expected_size:
        byte_string += (b'\x00' * (expected_size - len(byte_string)))
    interpreted_string = struct.unpack(order + format_string, byte_string)
    return interpreted_string


def writeStruct(file, order, format_string, value_list, seek=None):
    if seek:
        file.seek(seek)
    packed_bytes = struct.pack(order + format_string, *value_list)
    file.write(packed_bytes)


def shortHex(number):
    return hex(number)[2:]


def getBool(number):
    return True if number == 0x1 else False if number == 0x0 else number


def putBool(boolean):
    return 0x1 if boolean is True else 0x0 if boolean is False else boolean


def nameValue(*lists):
    string = []
    for lst in lists:
        for name in lst:
            if name == "type":
                string.append(lst[name])
            elif name != "length" and type(name) is not int:
                value = lst[name]
                if type(value) == float and value % 1 == 0.0:
                    value = int(value)
                string.append("{0}: {1}".format(name, value))
    return ", ".join(string)


def debugPrint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def checkMismatchedBytes(file1, file2):
    with open(file1, 'rb') as file1, open(file2, 'rb') as file2:
        data1, data2 = file1.read(), file2.read()
    incorrect_bytes = {}
    # Ignore header (first 432 + 80 = 512 bytes)
    for i, (byte1, byte2) in enumerate(zip(data1[512:], data2[512:])):
        if byte1 == byte2:
            pass
        else:
            incorrect_bytes[hex(i+512)] = [byte1, byte2]
    return incorrect_bytes
