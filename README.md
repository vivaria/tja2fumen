&nbsp;
<p align="center">
  <img
    width="400"
    src="https://user-images.githubusercontent.com/76574898/255353006-6c4504d0-c9a4-40d1-961f-db4cef7add0d.png"
    alt="tja2fumen – TJA chart converter"
  />
</p>

<p align="center">
  <code>tja2fumen</code> is a tool for Taiko no Tatsujin that allows you to convert TJA charts (<code>.tja</code>) to fumen charts (<code>.bin</code>).
</p>

----

## Goals

- Provide open source code to act as a reference for parsing and writing both the TJA and Fumen file formats.
- Fix the existing issues with `tja2bin.exe`:
  - Desync due to `#BPMCHANGE` commands. (https://github.com/Fluto/TakoTako/issues/16)
  - Crashes due to `#SECTION`, `#NEXTSONG`, `#LYRIC`, etc. commands.

## Usage

tja2fumen is included as part of several existing projects. So, you may be using tja2fumen already!

- **XB1/TDMX**: [TakoTako](https://github.com/fluto/takotako) converts both chart and audio files for XB1/TDMX.
- **Nijiro**: [TaikoSoundEditor](https://github.com/NotImplementedLife/TaikoSoundEditor) converts both chart and audio files for NIjiro.

### → Adding `tja2fumen.exe` to older TakoTako versions (3.2.0 and below)

> **Note**: Before adding `tja2fumen` to TakoTako, you may want to back up the original `tja2bin.exe` file, to make sure you can switch back to the old converter if necessary. The easiest way to do this is by renaming the existing file to `tja2bin.exe.bak`.

To use this converter with TakoTako, head to the [Releases](https://github.com/vivaria/tja2fumen/releases) page and download the `tja2fumen.exe` file attached to the release. Then, rename `tja2fumen.exe` to `tja2bin.exe`, and place the file in the TakoTako plugin folder.

TakoTako's plugin folder is inside of the BepInEx folder, which will typically look something like:

```
C:\XboxGames\T Tablet\Content\BepInEx\plugins\com.fluto.takotako
```

### → Using `tja2fumen` directly

If you'd like to build a project on top of `tja2fumen`, you have several options:

#### 1. Using the executable file (`tja2fumen.exe`)

Head to the [Releases](https://github.com/vivaria/tja2fumen/releases) page, and download the `tja2fumen.exe` file attached to the release.

Then, you can convert a TJA file on the command line by running:

```
tja2fumen.exe file.tja
```

#### 2. Using the `tja2fumen` Python package

If you're familiar with Python, you can install `tja2fumen` by running:

```
pip install tja2fumen
```

Then, you can convert a TJA file on the command line by running:

```
tja2fumen file.tja
```

Or, you can import the `main` function in your Python code, and convert TJA files this way instead:

```python
from tja2fumen import main
main(argv=["file.tja"])
```

## Reporting bugs

If you've found a .TJA file that `tja2fumen` converts incorrectly, please [open a new issue](https://github.com/vivaria/tja2fumen/issues/new) on the tja2fumen repo. 

It is especially important that you attach the song files to the issue. You can do this by adding the song files to a `.zip` (Select files -> Right click -> "Send to" -> "Compressed (zipped) folder"), and then uploading the `.zip` to the issue. This greatly helps me to reproduce and fix any issues.

## Attribution

- The fumen-parsing code in this project is based off of a modified copy of the [`readFumen()`](https://github.com/KatieFrogs/fumen-tools/blob/6ff3a2f7f53687f3dd49c5c57fcfc5ccbe3e5a10/fumen2osu/fumen2osu.py#L7-L152) function from the [`fumen2osu.py`](https://github.com/KatieFrogs/fumen-tools/blob/main/fumen2osu/fumen2osu.py) found in @KatieFrogs' [`fumen-tools`](https://github.com/KatieFrogs/fumen-tools) project.
- The TJA-parsing code in this project is a Python translation of the [`parseTJA.js`](https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js) file from @WHMHammer's [`tja-tools`](https://github.com/WHMHammer/tja-tools).

> **Note**: To be explicily clear, neither @KatieFrogs nor @WHMHammer have endorsed this project, are affiliated with this project, or have made any direct contributions to this project. I have just modified their existing work.
