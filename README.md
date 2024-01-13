&nbsp;
<p align="center">
  <img
    width="400"
    src="https://user-images.githubusercontent.com/76574898/255353006-6c4504d0-c9a4-40d1-961f-db4cef7add0d.png"
    alt="tja2fumen – TJA chart converter"
  />
  <br>
  tja2fumen is a tool that allows you to convert TJA charts (<code>.tja</code>) to fumen charts (<code>.bin</code>).
</p>

<p align="center">
  <a href="https://github.com/vivaria/tja2fumen/actions/workflows/test_and_publish_release.yml?query=branch%3Amain"><img src="https://img.shields.io/github/actions/workflow/status/vivaria/tja2fumen/test_and_publish_release.yml?label=Tests" alt="Test status (main branch)"></a>
  <a href="https://github.com/vivaria/tja2fumen/releases/latest"><img src="https://img.shields.io/github/v/release/vivaria/tja2fumen" alt="GitHub release (with filter)"></a>
  <a href="https://github.com/vivaria/tja2fumen/blob/main/LICENSE.txt"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
  <a href="https://github.com/pylint-dev/pylint"><img src="https://img.shields.io/badge/Linting-pylint-black" alt="Linting pylint"></a>
  <a href="https://github.com/PyCQA/flake8"><img src="https://img.shields.io/badge/Linting-flake8-black" alt="Linting flake8"></a>
  <a href="https://github.com/python/mypy"><img src="https://img.shields.io/badge/Typing-mypy-black" alt="Linting mypy"></a>
</p>

<p align="center">


</p>



----

## Features

tja2fumen is designed to be an open source alternative to the closed source tja2bin tool that has been floating around various Discord servers. tja2fumen fixes several outstanding tja2bin issues, while providing an open source codebase to modify and learn from.

- Converts `.tja` chart files to official fumen `.bin` files.
- Decodes official fumen `.bin` files (to inspect metadata and note data).
- Uses strong development practices (thorough test suite with example charts, type checking)
- Provides an open source resource for the Taiko no Tatsujin fumen file format.

## Usage

> [!NOTE]  
> For older versions of TakoTako (3.2.0 and below), you can add tja2fumen by renaming `tja2fumen.exe` to `tja2bin.exe` and placing it inside TakoTako's plugin folder (`BepInEx/plugins/com.fluto.takotako/`).

tja2fumen is included as part of several existing projects. So, you may be using tja2fumen already!

- **XB1/TDMX**: [TakoTako](https://github.com/fluto/takotako) converts both chart and audio files for XB1/TDMX.
- **Nijiro**: [TaikoSoundEditor](https://github.com/NotImplementedLife/TaikoSoundEditor) converts both chart and audio files for NIjiro.

You can also use tja2fumen directly on a `.tja` file by downloading `tja2fumen.exe` from the [Releases](https://github.com/vivaria/tja2fumen/releases) page and running `tja2fumen.exe file.tja` in a command prompt.

## TJA Support

If there is an unsupported feature that you would like support for, please make a request by [opening a new issue](https://github.com/vivaria/tja2fumen/issues/new).

### Supported file formats

> **Legend**: `✅` = Fully supported, `❌` = Not supported

|                     | tja 2 fumen | tja 2 bin | Comment  |
|---------------------|-------------|-----------|----------|
| UTF-8 (with BOM)    | `✅`         | `❌`       |          |
| UTF-8 (without BOM) | `✅️`        | `✅`       |          |
| Shift-JIS           | `✅`         | `✅`       |          |

### Supported metadata

> **Legend**: `✅` = Fully supported, `⚪️` = Ignored, `⚠️` = Incorrect behavior, `❌` = Not supported

|                                                                 | tja 2 fumen | tja 2 bin | Comment                                                                 |
|-----------------------------------------------------------------|-------------|-----------|-------------------------------------------------------------------------|
| `BPM:`, `OFFSET:`                                               | `✅`         | `✅`       |                                                                         |
| `TITLE:`, `SUBTITLE:`, `WAVE:`,<br>`DEMOSTART:`, etc.           | `⚪️`        | `⚪️`      | The only global metadata needed are `BPM:` and `OFFSET:`.               |
| `COURSE:`, `LEVEL:`, `BALLOON:`,<br> `SCOREINIT:`, `SCOREDIFF:` | `✅`         | `✅`       |                                                                         |
| `STYLE:` (`Single`, `Double`)                                   | `✅`         | `❌`       |                                                                         |
| `EXAM1:`, `GAUGEINCR:`, `TOTAL:`, etc.                          | `⚪️`        | `⚪️`      | Other simulator-specific metadata fields are currently ignored.         |

### Supported notes/commands

> **Legend**: `✅` = Fully supported, `⚪️` = Ignored, `⚠️` = Incorrect behavior, `❌` = Not supported

|                                              | tja 2 fumen | tja 2 bin | Comment                                                                                                       |
|----------------------------------------------|-------------|-----------|---------------------------------------------------------------------------------------------------------------|
| `0`, `1`, `2`, `3`, `4`                      | `✅`         | `✅`       |                                                                                                               |
| `5008,`, `6008,`, `7008,`                    | `✅`         | `✅`       |                                                                                                               |
| `9008,`                                      | `✅`         | `⚠️`      |                                                                                                               |
| `9000,`<br>`9008,`                           | `⚪️`        | `⚠️`      | Double Kusudama note treated as 1 drumroll by tja2fumen, but 2 overlapping drumrolls by tja2bin.              |
| `A`, `B`                                     | `✅`         | `❌`       | Multiplayer "hands" notes are valid in fumens, but unrecognized by tja2bin.                                   |
| `C`, `D`, `E`, `F`, `G`, `H`, `I`            | `⚠️`        | `❌`       | Replaced by normal notes/rolls in tja2fumen.                                                                  |
| `#START`, `#END`                             | `✅`         | `✅`       |                                                                                                               |
| `#START P1`, `#START P2`                     | `✅`         | `❌`       |                                                                                                               |
| `#BPMCHANGE`                                 | `✅`         | `⚠️`      | See [#16](https://github.com/Fluto/TakoTako/issues/16)                                                        |
| `#MEASURE`                                   | `✅`         | `✅`       |                                                                                                               |
| `#SCROLL`                                    | `✅`         | `✅`       |                                                                                                               |
| `#GOGOSTART`, `#GOGOEND`                     | `✅`         | `✅`       |                                                                                                               |
| `#BARLINEOFF`, `#BARLINEON`                  | `✅`         | `✅`       |                                                                                                               |
| `#DELAY`                                     | `✅`         | `❌`       | See [#27](https://github.com/Fluto/TakoTako/issues/27)                                                        |
| `#BRANCHSTART`, `#BRANCHEND`                 | `✅`         | `✅`       |                                                                                                               |
| `#N`, `#E`, `#M`                             | `✅`         | `✅`       |                                                                                                               |
| `#SECTION`                                   | `⚠️`        | `❌`       | See [#53](https://github.com/vivaria/tja2fumen/issues/53), [#27](https://github.com/Fluto/TakoTako/issues/27) |
| `#LEVELHOLD`                                 | `✅`         | `❌`       |                                                                                                               |
| `#BMSCROLL`, `#LYRIC`,<br>`#DIRECTION`, etc. | `⚪️`        | `❌`       | Other simulator-specific chart commands are currently ignored.                                                |

## Reporting bugs

If you've found a `.tja` file that tja2fumen converts incorrectly, please [open a new issue](https://github.com/vivaria/tja2fumen/issues/new) on the tja2fumen repo. 

It is especially important that you attach the song files to the issue. You can do this by adding the song files to a `.zip` (Select files -> Right click -> "Send to" -> "Compressed (zipped) folder"), and then uploading the `.zip` to the issue. This greatly helps me to reproduce and fix any issues.

You can also message me directly on Discord (`_vivaria`) if you don't have a GitHub account, and I will take care of making an issue for you. :)

## Building on top of tja2fumen

If you are a developer looking to add tja2fumen to your project, you have two options:

1. For non-Python projects, you can download `tja2fumen.exe` and call it via a system call.
2. For Python projects, you can install tja2fumen via `pip install tja2fumen`.

tja2fumen uses a very permissable license ([MIT License](https://choosealicense.com/licenses/mit/)). You are free to distribute and modify tja2fumen, but please include a copy of the MIT License alongside the `tja2fumen.exe` executable if you copy it into your project.

## Attribution

- The fumen-parsing code in this project is based off of a modified copy of the [`readFumen()`](https://github.com/KatieFrogs/fumen-tools/blob/6ff3a2f7f53687f3dd49c5c57fcfc5ccbe3e5a10/fumen2osu/fumen2osu.py#L7-L152) function from the [`fumen2osu.py`](https://github.com/KatieFrogs/fumen-tools/blob/main/fumen2osu/fumen2osu.py) found in @KatieFrogs' [`fumen-tools`](https://github.com/KatieFrogs/fumen-tools) project.
- The TJA-parsing code in this project is a Python translation of the [`parseTJA.js`](https://github.com/WHMHammer/tja-tools/blob/master/src/js/parseTJA.js) file from @WHMHammer's [`tja-tools`](https://github.com/WHMHammer/tja-tools).
- sakurada0291, DDDDDD, U-ros, and others in the Discord for helping to test tja2fumen. :)
