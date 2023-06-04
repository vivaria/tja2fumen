# tja2fumen

`tja2fumen` is a tool for Taiko no Tatsujin games that allows you to convert TJA files (`.tja`) to fumen files (`.bin`).

This project attempts to replace/complement the existing closed-source [tja2bin.exe](https://github.com/Fluto/TakoTako/blob/c269bcab60530877a16c2a473c84796b94d0a5ce/README.md?plain=1#L181) converter packaged alongside TakoTako. 

## Goals

- Act as a drop-in replacement for `tja2bin.exe` in TakoTako.
- Fix https://github.com/Fluto/TakoTako/issues/16. (The original `tjabin.exe` doesn't properly handle `#BPMCHANGE` commands.)
- Provide open source code to act as a reference for parsing and writing both the TJA and Fumen file formats.
- Stick to the Python stdlib, i.e. no external dependencies if possible.

## Usage

### Option 1: Standalone Python installation

If you're familiar with Python, you can install `tja2fumen` by running:

```
pip install tja2fumen
```

Then, you can convert a TJA file by running:

```
tja2fumen file.tja
```

### Option 2: Using with TakoTako

> **Note**: Before adding `tja2fumen` to TakoTako, you may want to back up the original `tja2bin.exe` file, to make sure you can switch back to the old converter if necessary. The easiest way to do this is by renaming the existing file to `tja2bin.exe.bak`.

To use this converter with TakoTako, head to the [Releases](https://github.com/vivaria/tja2fumen/releases) page, and download the `tja2fumen.exe` file attached to the release. Then, rename `tja2fumen.exe` to `tja2bin.exe`, and place the file in the TakoTako plugin folder.

TakoTako's plugin folder is inside of the BepInEx folder, which will typically look something like:

```
C:\XboxGames\T Tablet\Content\BepInEx\plugins\com.fluto.takotako
```

## Attribution

- The fumen-parsing code in this project is based off of a modified copy of the [`readFumen()`](https://github.com/KatieFrogs/fumen-tools/blob/6ff3a2f7f53687f3dd49c5c57fcfc5ccbe3e5a10/fumen2osu/fumen2osu.py#L7-L152) function from the [`fumen2osu.py`](https://github.com/KatieFrogs/fumen-tools/blob/main/fumen2osu/fumen2osu.py) found in @KatieFrogs' [`fumen-tools`](https://github.com/KatieFrogs/fumen-tools) project.
- The TJA-parsing code in this project is a Python translation of the [`parseTJA.js`](https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js) file from @WHMHammer's [`tja-tools`](https://github.com/WHMHammer/tja-tools).

> **Note**: To be explicily clear, neither @KatieFrogs nor @WHMHammer have endorsed this project, are affiliated with this project, or have made any direct contributions to this project. I have just modified their existing work.
