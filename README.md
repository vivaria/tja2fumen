# tja2fumen

This repo a new attempt to write a tja2fumen chart converter to replace/complement the existing [tja2bin.exe](https://github.com/Fluto/TakoTako/blob/c269bcab60530877a16c2a473c84796b94d0a5ce/README.md?plain=1#L181) converter. 

### Goals

- [X] Fix desyncronization issues due to BPMCHANGE commands. (See: https://github.com/Fluto/TakoTako/issues/16)
- [X] Provide open source code, as opposed to distributing only a closed-source binary.
- [ ] Provide a highly-documented reference for parsing both the TJA and Fumen file formats.
- [ ] Stick to "pure Python", i.e. no external dependencies if possible.
- [ ] Provide support for Windows/Linux/macOS via [`PyInstaller`](https://pyinstaller.org/en/stable/) or something similar.

### Usage

The converter is in a messy/experimental state, and is not yet fit for use due to lack of support for important TJA commands. 

### Future work

> **Note**: Simulator-specific commands (such as those used for Dan-i Dojo charts) are unlikely to be supported, due to the lack of support from official console releases.

* Bugfixes
  - [ ] Fix issue with BPMCHANGE + drumrolls. (Affected songs: Kokuryu, R.I.P. Hero, Challengers, etc.)
  - [ ] Properly handle the offset at the beginning of the song (Affected songs: SUPERNOVA, etc.)
  - [ ] Handle `areFilesGZipped=False` issue when combining charts with `TakoTako`/`tja2bin.exe` files (Affected songs: Aragami, MEGALOVANIA, exTora Trap!!).
* Missing command support
  - [ ] Support for branch commands (`#BRANCHSTART`, `#BRANCHEND`, `#N`, `#E`, `#M`, `#LEVELHOLD`, etc.)
  - [ ] Support for barline manipulation commands (`#BARLINEON`, `#BARLINEOFF`)
  - [ ] Support for delay commands (`#DELAY`)
  - [ ] Support for P1/P2 charts (`#STYLE: Single`, `#STYLE: Double`, `#START P1`, `START P2`)
* Project architecture
  - [ ] Refactoring into a more Pythonic style (variable names (`camelCase` -> `under_score`), object-oriented note/branch/measure representations, etc.)
  - [ ] Argument parsing + proper i/o handling
  - [ ] Packaging into an executable

Once these features are added, I will create an initial release. Until then, the source code in this repo is presented as-is.

### Attribution

- The fumen-parsing code in this project is based off of a modified copy of the [`readFumen()`](https://github.com/KatieFrogs/fumen-tools/blob/6ff3a2f7f53687f3dd49c5c57fcfc5ccbe3e5a10/fumen2osu/fumen2osu.py#L7-L152) function from the [`fumen2osu.py`](https://github.com/KatieFrogs/fumen-tools/blob/main/fumen2osu/fumen2osu.py) found in @KatieFrogs' [`fumen-tools`](https://github.com/KatieFrogs/fumen-tools) project.
- The TJA-parsing code in this project is a Python translation of the [`parseTJA.js`](https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js) file from @WHMHammer's [`tja-tools`](https://github.com/WHMHammer/tja-tools).

> **Note**: To be explicily clear, neither @KatieFrogs nor @WHMHammer have endorsed this project, are affiliated with this project, or have made any direct contributions to this project. I have just modified their existing work.
