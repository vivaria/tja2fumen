# tja2fumen

This repo a new attempt to write a tja2fumen chart converter to replace/complement the existing [tja2bin.exe](https://github.com/Fluto/TakoTako/blob/c269bcab60530877a16c2a473c84796b94d0a5ce/README.md?plain=1#L181) converter. 

### Goals

- Fix desyncronization issues due to BPMCHANGE commands. (See: https://github.com/Fluto/TakoTako/issues/16)
- Provide open source code, as opposed to distributing only a closed-source binary.
- Provide a highly-documented reference for parsing both the TJA and Fumen file formats.
- Stick to "pure Python", i.e. no external dependencies if possible.
- Provide support for Windows/Linux/macOS via [`PyInstaller`](https://pyinstaller.org/en/stable/) or something similar.

### Usage

The converter is in a messy/experimental state, and is not yet fit for use due to lack of support for important TJA commands.

### Attribution

- The fumen-parsing code in this project is based off of a modified copy of the [`readFumen()`](https://github.com/KatieFrogs/fumen-tools/blob/6ff3a2f7f53687f3dd49c5c57fcfc5ccbe3e5a10/fumen2osu/fumen2osu.py#L7-L152) function from the [`fumen2osu.py`](https://github.com/KatieFrogs/fumen-tools/blob/main/fumen2osu/fumen2osu.py) found in @KatieFrogs' [`fumen-tools`](https://github.com/KatieFrogs/fumen-tools) project.
- The TJA-parsing code in this project is a Python translation of the [`parseTJA.js`](https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js) file from @WHMHammer's [`tja-tools`](https://github.com/WHMHammer/tja-tools).

> **Note**: To be explicily clear, neither @KatieFrogs nor @WHMHammer have endorsed this project, are affiliated with this project, or have made any direct contributions to this project. I have just modified their existing work.
