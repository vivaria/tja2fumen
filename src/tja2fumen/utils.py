import sys
import struct
import math


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
