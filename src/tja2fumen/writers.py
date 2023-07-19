from tja2fumen.utils import writeStruct
from tja2fumen.constants import branchNames, typeNotes


def writeFumen(path_out, song):
    with open(path_out, "wb") as file:
        file.write(song.header.raw_bytes)

        for measureNumber in range(len(song.measures)):
            measure = song.measures[measureNumber]
            measureStruct = [measure.bpm, measure.fumenOffsetStart, int(measure.gogo), int(measure.barline)]
            measureStruct.extend([measure.padding1] + measure.branchInfo + [measure.padding2])
            writeStruct(file, song.header.order, format_string="ffBBHiiiiiii", value_list=measureStruct)

            for branchNumber in range(len(branchNames)):
                branch = measure.branches[branchNames[branchNumber]]
                branchStruct = [branch.length, branch.padding, branch.speed]
                writeStruct(file, song.header.order, format_string="HHf", value_list=branchStruct)

                for noteNumber in range(branch.length):
                    note = branch.notes[noteNumber]
                    noteStruct = [typeNotes[note.type], note.pos, note.item, note.padding]
                    if note.hits:
                        noteStruct.extend([note.hits, note.hitsPadding, note.duration])
                    else:
                        noteStruct.extend([note.scoreInit, note.scoreDiff * 4, note.duration])
                    writeStruct(file, song.header.order, format_string="ififHHf", value_list=noteStruct)

                    if note.type.lower() == "drumroll":
                        file.write(note.drumrollBytes)
