import sys
import struct

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
