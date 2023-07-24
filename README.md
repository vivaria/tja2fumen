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
</p>


----

## Usage

tja2fumen is included as part of several existing projects. So, you may be using tja2fumen already!

- **XB1/TDMX**: [TakoTako](https://github.com/fluto/takotako) converts both chart and audio files for XB1/TDMX.
- **Nijiro**: [TaikoSoundEditor](https://github.com/NotImplementedLife/TaikoSoundEditor) converts both chart and audio files for NIjiro.

You can also use tja2fumen directly on a `.tja` file by downloading `tja2fumen.exe` from the [Releases](https://github.com/vivaria/tja2fumen/releases) page and running `tja2fumen.exe file.tja` in a command prompt.

> **Note**: For older versions of TakoTako (3.2.0 and below), you can add tja2fumen by renaming `tja2fumen.exe` to `tja2bin.exe` and placing it inside TakoTako's plugin folder (`BepInEx/plugins/com.fluto.takotako/`).

## TJA Support

If there is an unsupported command or metadata field that you would like support for, please make a request by [opening a new issue](https://github.com/vivaria/tja2fumen/issues/new).

### Supported metadata

> **Legend**: `✅` = Fully supported, `⚪️` = Ignored, `⚠️` = Incorrect behavior, `❌` = Not supported

| Metadata                                                        | tja2fumen | tja2bin | Comments                                                                |
|-----------------------------------------------------------------|-----------|---------|-------------------------------------------------------------------------|
| `BPM:`, `OFFSET:`                                               | `✅`       | `✅`     |                                                                         |
| `TITLE:`, `SUBTITLE:`, `WAVE:`,<br>`DEMOSTART:`, etc.           | `⚪️`      | `⚪️`    | The only global metadata needed are `BPM:` and `OFFSET:`.               |
| `COURSE:`, `LEVEL:`, `BALLOON:`,<br> `SCOREINIT:`, `SCOREDIFF:` | `✅`       | `✅`     |                                                                         |
| `STYLE: Single`, `STYLE: Double`                                | `✅`       | `❌`     |                                                                         |
| `EXAM1:`, `GAUGEINCR:`, `TOTAL:`, etc.                          | `⚪️`      | `⚪️`    | Other simulator-specific metadata fields are not currently supported.   |

### Supported notes/commands

> **Legend**: `✅` = Fully supported, `⚪️` = Ignored, `⚠️` = Incorrect behavior, `❌` = Not supported

| Note/command                                    | tja2fumen | tja2bin | Comments                                                             |
|-------------------------------------------------|-----------|---------|----------------------------------------------------------------------|
| `0`, `1`, `2`, `3`, `4` `5`, `6`, `7`, `8`, `9` | `✅`       | `✅`     |                                                                      |
| `A`, `B`                                        | `✅`       | `❌`     |                                                                      | 
| `F`                                             | `❔`       | `❔`     | Hidden ADLIB note.                                                   |
| `9000,`<br>`9008,`                              | `⚪️`      | `❔`     | Double Kusudama note to reset accuracy.                              |
| `#START`, `#END`                                | `✅`       | `✅`     |                                                                      |
| `#START P1`, `START P2`                         | `✅`       | `❔`     |                                                                      |
| `#MEASURE`                                      | `✅`       | `✅`     |                                                                      |
| `#BPMCHANGE`                                    | `✅`       | `⚠️`    | See https://github.com/Fluto/TakoTako/issues/16                      |
| `#DELAY`                                        | `✅`       | `❌`     |                                                                      |
| `#SCROLL`                                       | `✅`       | `✅`     |                                                                      |
| `#GOGOSTART`, `#GOGOEND`                        | `✅`       | `✅`     |                                                                      |
| `#BARLINEOFF`, `#BARLINEON`                     | `✅`       | `✅`     |                                                                      |
| `#BRANCHSTART`                                  | `✅`       | `✅`     |                                                                      |
| `#SECTION`                                      | `✅`       | `✅`     |                                                                      |
| `#LEVELHOLD`                                    | `❔`       | `❔`     |                                                                      |
| `#N`, `#E`, `#M`                                | `✅`       | `✅`     |                                                                      |
| `#BRANCHEND`                                    | `✅`       | `✅`     |                                                                      |
| `#BMSCROLL`, `#LYRIC`,<br>`#DIRECTION`, etc.    | `⚪️`      | `❌`     | Other simulator-specific chart commands are not currently supported. |

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
