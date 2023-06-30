# Various commands and header fields for TJA files
HEADER_GLOBAL = ['TITLE', 'TITLEJA', 'SUBTITLE', 'SUBTITLEJA', 'BPM', 'WAVE', 'OFFSET', 'DEMOSTART', 'GENRE',
                 'SCOREMODE', 'BGMOVIE', 'SONGVOL', 'SEVOL']
HEADER_COURSE = ['COURSE', 'LEVEL', 'BALLOON', 'SCOREINIT', 'SCOREDIFF', 'STYLE']
BRANCH_COMMANDS = ['START', 'END', 'BRANCHSTART', 'BRANCHEND', 'N', 'E', 'M', 'SECTION']
MEASURE_COMMANDS = ['MEASURE', 'GOGOSTART', 'GOGOEND', 'BARLINEON', 'BARLINEOFF', 'SCROLL', 'BPMCHANGE', 'DELAY', 'LEVELHOLD']

# Note types for TJA files
TJA_NOTE_TYPES = {
    '1': 'Don',
    '2': 'Ka',
    '3': 'DON',
    '4': 'KA',
    '5': 'Drumroll',
    '6': 'DRUMROLL',
    '7': 'Balloon',
    '8': 'EndDRB',
    '9': 'Kusudama',
    'A': 'DON',  # hands
    'B': 'KA',   # hands
}

# Note types for fumen files
noteTypes = {
    0x1: "Don",   # ドン
    0x2: "Don2",  # ド
    0x3: "Don3",  # コ
    0x4: "Ka",    # カッ
    0x5: "Ka2",   # カ
    0x6: "Drumroll",
    0x7: "DON",
    0x8: "KA",
    0x9: "DRUMROLL",
    0xa: "Balloon",
    0xb: "DON2",        # hands
    0xc: "Kusudama",
    0xd: "KA2",         # hands
    0xe: "Unknown1",    # ? (Present in some Wii1 songs)
    0xf: "Unknown2",    # ? (Present in some PS4 songs)
    0x10: "Unknown3",   # ? (Present in some Wii1 songs)
    0x11: "Unknown4",   # ? (Present in some Wii1 songs)
    0x12: "Unknown5",   # ? (Present in some Wii4 songs)
    0x13: "Unknown6",   # ? (Present in some Wii1 songs)
    0x14: "Unknown7",   # ? (Present in some PS4 songs)
    0x15: "Unknown8",   # ? (Present in some Wii1 songs)
    0x16: "Unknown9",   # ? (Present in some Wii1 songs)
    0x17: "Unknown10",  # ? (Present in some Wii4 songs)
    0x18: "Unknown11",  # ? (Present in some PS4 songs)
    0x19: "Unknown12",  # ? (Present in some PS4 songs)
    0x22: "Unknown13",  # ? (Present in some Wii1 songs)
    0x62: "Drumroll2"   # ?
}
typeNotes = {v: k for k, v in noteTypes.items()}

branchNames = ("normal", "advanced", "master")

# The first 432 bytes of fumen headers are made up of combinations of byte substrings
# Commonly repeated byte substrings are listed below:
byte_strings = {
    # 6-byte substring
    'x00': b'\x00\x00\x00\x00\x00\x00',
    # 12-byte substrings
    '431': b'43\xc8Ag&\x96B"\xe2\xd8B',
    '432': b'43\xc8Ag&\x96BD\x84\xb7B',
    '433': b'43\xc8A"\xe2\xd8B\x00@\xfaB',
    '434': b'43\xc8AD\x84\xb7B"\xe2\xd8B',
    'g1': b'g&\x96B4\xa3\x89Cxw\x05A',
    'V1': b'V\xd5&B\x00@\xfaB\x00@\xfaB',
    'V2': b'V\xd5&B"\xe2\xd8B\x00@\xfaB',
    'V3': b'V\xd5&B\x00@\xfaB\xf0\xce\rC',
}
# The simplest 432-byte headers are just 36 repeated copies of the specific 12-byte substrings below
simpleHeaders = [b * 36 for b in [byte_strings['431'], byte_strings['V1'], byte_strings['V2']]]

# The next 80 bytes of fumen headers contain mostly 0s, with a few non-zero bytes thrown in
sampleHeaderMetadata = [0] * 80
# The following bytes are hardcoded by tja2bin.exe (implying they have little/no effect on how the song is parsed)
sampleHeaderMetadata[4] = 16
sampleHeaderMetadata[5] = 39
sampleHeaderMetadata[12] = 10
sampleHeaderMetadata[16] = 8
sampleHeaderMetadata[21] = 255
sampleHeaderMetadata[22] = 255
sampleHeaderMetadata[23] = 255
sampleHeaderMetadata[26] = 1
sampleHeaderMetadata[30] = 1
sampleHeaderMetadata[34] = 1
sampleHeaderMetadata[36] = 20
sampleHeaderMetadata[40] = 10
sampleHeaderMetadata[48] = 1
sampleHeaderMetadata[52] = 20
sampleHeaderMetadata[56] = 10
sampleHeaderMetadata[60] = 1
sampleHeaderMetadata[64] = 30
sampleHeaderMetadata[68] = 30
sampleHeaderMetadata[72] = 20
sampleHeaderMetadata[76] = 78
sampleHeaderMetadata[77] = 97
sampleHeaderMetadata[78] = 188
# Certain other bytes (8+9, 20) will need to be filled in on a song-by-song basis

NORMALIZE_COURSE = {
    '0': 'Easy',
    'Easy': 'Easy',
    '1': 'Normal',
    'Normal': 'Normal',
    '2': 'Hard',
    'Hard': 'Hard',
    '3': 'Oni',
    'Oni': 'Oni',
    '4': 'Ura',
    'Ura': 'Ura',
    'Edit': 'Ura'
}

DIFFICULTY_BYTES = {
    'Easy': [112, 23],
    'Normal': [88, 27],
    'Hard': [88, 27],
    'Oni': [64, 31],
    'Ura': [64, 31],
    'Edit': [64, 31]
}

COURSE_IDS = {
    'Easy': 'e',
    'Normal': 'n',
    'Hard': 'h',
    'Oni': 'm',
    'Ura': 'x',
    'Edit': 'x'
}
