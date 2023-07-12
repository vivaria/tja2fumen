from tja2fumen.utils import writeStruct, putBool
from tja2fumen.constants import branchNames, typeNotes


def writeFumen(path_out, song):
    # Fetch the byte order (little/big endian)
    order = song.order

    # Write the header
    file = open(path_out, "wb")
    file.write(song.headerPadding)   # Write header padding bytes
    file.write(song.headerMetadata)  # Write header metadata bytes

    # Preallocate space in the file
    len_metadata = 8
    len_measures = 0
    for measureNumber in range(len(song.measures)):
        len_measures += 40
        measure = song.measures[measureNumber]
        for branchNumber in range(len(branchNames)):
            len_measures += 8
            branch = measure.branches[branchNames[branchNumber]]
            for noteNumber in range(branch.length):
                len_measures += 24
                note = branch.notes[noteNumber]
                if note.type.lower() == "drumroll":
                    len_measures += 8
    file.write(b'\x00' * (len_metadata + len_measures))

    # Write metadata
    writeStruct(file, order, format_string="B", value_list=[putBool(song.hasBranches)], seek=0x1b0)
    writeStruct(file, order, format_string="I", value_list=[len(song.measures)], seek=0x200)
    writeStruct(file, order, format_string="I", value_list=[song.unknownMetadata], seek=0x204)

    # Write measure data
    file.seek(0x208)
    for measureNumber in range(len(song.measures)):
        measure = song.measures[measureNumber]
        measureStruct = [measure.bpm, measure.fumenOffsetStart, int(measure.gogo), int(measure.barline)]
        measureStruct.extend([measure.padding1] + measure.branchInfo + [measure.padding2])
        writeStruct(file, order, format_string="ffBBHiiiiiii", value_list=measureStruct)

        for branchNumber in range(len(branchNames)):
            branch = measure.branches[branchNames[branchNumber]]
            branchStruct = [branch.length, branch.padding, branch.speed]
            writeStruct(file, order, format_string="HHf", value_list=branchStruct)

            for noteNumber in range(branch.length):
                note = branch.notes[noteNumber]
                noteStruct = [typeNotes[note.type], note.pos, note.item, note.padding]
                # Balloon hits
                if note.hits:
                    noteStruct.extend([note.hits, note.hitsPadding])
                else:
                    noteStruct.extend([note.scoreInit, note.scoreDiff * 4])
                # Drumroll or balloon duration
                noteStruct.append(note.duration)
                writeStruct(file, order, format_string="ififHHf", value_list=noteStruct)
                if note.type.lower() == "drumroll":
                    file.write(note.drumrollBytes)
    file.close()
