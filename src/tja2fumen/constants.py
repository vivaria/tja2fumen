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

FUMEN_NOTE_TYPES = {
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
FUMEN_TYPE_NOTES = {v: k for k, v in FUMEN_NOTE_TYPES.items()}

BRANCH_NAMES = ("normal", "advanced", "master")

TJA_COURSE_NAMES = []
for difficulty in ['Ura', 'Oni', 'Hard', 'Normal', 'Easy']:
    for player in ['', 'P1', 'P2']:
        TJA_COURSE_NAMES.append(difficulty+player)

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

COURSE_IDS = {
    'Easy': 'e',
    'Normal': 'n',
    'Hard': 'h',
    'Oni': 'm',
    'Ura': 'x',
    'Edit': 'x'
}
