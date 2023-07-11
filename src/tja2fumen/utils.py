import os
import struct
import csv


def computeSoulGaugeBytes(n_notes, difficulty, stars):
    if difficulty in ['Oni', 'Ura']:
        if 9 <= stars:
            key = "Oni-9-10"
        elif stars == 8:
            key = "Oni-8"
        elif stars <= 7:
            key = "Oni-1-7"
    elif difficulty == 'Hard':
        if 5 <= stars:
            key = "Hard-5-8"
        elif stars == 4:
            key = "Hard-4"
        elif stars == 3:
            key = "Hard-3"
        elif stars <= 2:
            key = "Hard-1-2"
    elif difficulty == 'Normal':
        if 5 <= stars:
            key = "Normal-5-7"
        elif stars == 4:
            key = "Normal-4"
        elif stars == 3:
            key = "Normal-3"
        elif stars <= 2:
            key = "Normal-1-2"
    elif difficulty == 'Easy':
        if 4 <= stars:
            key = "Easy-4-5"
        elif 2 <= stars <= 3:
            key = "Easy-2-3"
        elif stars <= 1:
            key = "Easy-1"
    # Set default values for soul gauge bytes.
    # NB: These will only be used if n_notes > 2500 (i.e. the most extreme, impossible case, beyond all official charts)
    soulGaugeByte12 = 255
    soulGaugeByte13 = 3
    soulGaugeByte16 = 255
    soulGaugeByte17 = 2
    soulGaugeByte20 = 255
    soulGaugeByte21 = 253
    pkg_dir = os.path.dirname(os.path.realpath(__file__))
    with open(os.path.join(pkg_dir, "soulgauge_LUTs", f"byte1213_{key}.csv"), newline='') as csvfile:
        lut_reader = csv.reader(csvfile, delimiter=',')
        for row in lut_reader:
            if int(row[0]) == n_notes:
                soulGaugeByte12 = int(row[1]) % 255
                soulGaugeByte13 = int(row[1]) // 255
                break
    with open(os.path.join(pkg_dir, "soulgauge_LUTs", f"byte1617_{key}.csv"), newline='') as csvfile:
        lut_reader = csv.reader(csvfile, delimiter=',')
        for row in lut_reader:
            if int(row[0]) == n_notes:
                soulGaugeByte16 = int(row[1]) % 255
                soulGaugeByte17 = int(row[1]) // 255
                break
    with open(os.path.join(pkg_dir, "soulgauge_LUTs", f"byte2021_{key}.csv"), newline='') as csvfile:
        lut_reader = csv.reader(csvfile, delimiter=',')
        for row in lut_reader:
            if int(row[0]) == n_notes:
                soulGaugeByte20 = int(row[1]) % 255
                soulGaugeByte21 = 253 + (int(row[1]) // 255)
                break
    return soulGaugeByte12, soulGaugeByte13, soulGaugeByte16, soulGaugeByte17, soulGaugeByte20, soulGaugeByte21


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
