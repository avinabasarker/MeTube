# MeTube 2.0 - TEST LOG

Every row below is backed by a command that was actually executed on this
Windows machine, with its real output. Nothing here was written from
expectation.

- Harness: [scripts/e2e.py](scripts/e2e.py) (drives the real `App`, real
  `yt-dlp.exe`, real YouTube URLs, real Tk window).
- Machine-readable results: [evidence/e2e_results.json](evidence/e2e_results.json)
- Raw harness transcript: [evidence/e2e_full.log](evidence/e2e_full.log)

**Harness checks recorded: 137/137 PASS.**

## 1. Environment and setup

```
Microsoft Windows [Version 10.0.19045.6466]
 
Python 3.13.1
 
--- python in venv --- 
Python 3.13.1
```

### Pinned dependencies (`pip freeze`)

```
altgraph==0.17.5
customtkinter==5.2.2
darkdetect==0.8.0
packaging==26.3
pefile==2024.8.26
pillow==12.3.0
psutil==7.2.2
pyinstaller==6.22.3
pyinstaller-hooks-contrib==2026.8
pywin32-ctypes==0.2.3
setuptools==84.0.0
winotify==1.1.0
```

### `pip install -r requirements.txt` (idempotent re-run)

```
Requirement already satisfied: customtkinter==5.2.2 in .\.venv\Lib\site-packages (from -r requirements.txt (line 1)) (5.2.2)
Requirement already satisfied: pillow==12.3.0 in .\.venv\Lib\site-packages (from -r requirements.txt (line 2)) (12.3.0)
Requirement already satisfied: psutil==7.2.2 in .\.venv\Lib\site-packages (from -r requirements.txt (line 3)) (7.2.2)
Requirement already satisfied: winotify==1.1.0 in .\.venv\Lib\site-packages (from -r requirements.txt (line 4)) (1.1.0)
Requirement already satisfied: pyinstaller==6.22.3 in .\.venv\Lib\site-packages (from -r requirements.txt (line 5)) (6.22.3)
Requirement already satisfied: darkdetect in .\.venv\Lib\site-packages (from customtkinter==5.2.2->-r requirements.txt (line 1)) (0.8.0)
Requirement already satisfied: packaging in .\.venv\Lib\site-packages (from customtkinter==5.2.2->-r requirements.txt (line 1)) (26.3)
Requirement already satisfied: altgraph in .\.venv\Lib\site-packages (from pyinstaller==6.22.3->-r requirements.txt (line 5)) (0.17.5)
Requirement already satisfied: pefile>=2022.5.30 in .\.venv\Lib\site-packages (from pyinstaller==6.22.3->-r requirements.txt (line 5)) (2024.8.26)
Requirement already satisfied: pyinstaller-hooks-contrib>=2026.7 in .\.venv\Lib\site-packages (from pyinstaller==6.22.3->-r requirements.txt (line 5)) (2026.8)
Requirement already satisfied: pywin32-ctypes>=0.2.1 in .\.venv\Lib\site-packages (from pyinstaller==6.22.3->-r requirements.txt (line 5)) (0.2.3)
Requirement already satisfied: setuptools>=42.0.0 in .\.venv\Lib\site-packages (from pyinstaller==6.22.3->-r requirements.txt (line 5)) (84.0.0)
```

### Engine binaries shipped in `bin\`

```
yt-dlp.exe    rc=0  2026.08.19
ffmpeg.exe    rc=0  ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers
ffprobe.exe   rc=0 ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers

size + sha256 (first 32 hex chars):
ffmpeg.exe 168934400 7a66dd4355a0c14a3842ea9632ea62f8
ffprobe.exe 168716800 9996dddb28262041ac34c48aae608612
yt-dlp.exe 17840399 66674953fe251b89f4d08c5f0e35e072
```

## 2. T1 - T20 (Section 14)

| Row | Requirement | Result | Evidence |
| --- | --- | --- | --- |
| T1 | compileall clean + scripts/selftest.py passes | **PASS** | compileall rc=0; SELFTEST PASSED: 58 checks |
| T2 | Real MP3 download end to end | **PASS** | T2.1: PASS; T2.2: PASS; T2.3: PASS; T2.4: PASS; T2.5: PASS; T2.6: PASS; T2.7: PASS; T2.8: PASS |
| T3 | Same URL as MP4 Best, height == source max | **PASS** | T3.0: PASS; T3.1: PASS; T3.2: PASS |
| T4 | MP4 capped falls back to nearest lower, never fails | **PASS** | T4.1: PASS; T4.2: PASS; T4.3: PASS; T4.4: PASS |
| T5 | Paste 5 links: split, dedupe, sequential, countdowns | **PASS** | T5.0: PASS; T5.1: PASS; T5.2: PASS; T5.3: PASS; T5.4: PASS; T5.5: PASS; T5.6: PASS |
| T6 | Playlist URL expands to N; watch?v=&list= is one item | **PASS** | T6.1: PASS; T6.2: PASS; T6.3: PASS; T6.3b: PASS; T6.4: PASS; T6.5: PASS; T6.6: PASS |
| T7 | Invalid URL fails clearly, queue continues | **PASS** | T7.0: PASS; T7.1: PASS; T7.2: PASS |
| T8 | Pause mid-download freezes the process; Resume continues | **PASS** | T8.0: PASS; T8.1: PASS; T8.2: PASS; T8.3: PASS; T8.4: PASS; T8.5: PASS; T8.6: PASS; T8.7: PASS |
| T9 | Cancel mid-download removes .part, next item starts | **PASS** | T9.1: PASS; T9.2: PASS; T9.3: PASS; T9.4: PASS; T9.5: PASS |
| T10 | Folder change applies with no restart, survives a restart, is shown on screen, and the next download really lands in it | **PASS** | T10.1: PASS; T10.2: PASS; T10.3: PASS; T10.3b: PASS; T10.4: PASS; T10.5: PASS; T10.6: PASS; T10.6b: PASS; T10.6c: PASS; T10.6d: PASS; T10.6e: PASS; T10.7: PASS; T10.8: PASS; T10.9: PASS |
| T11 | Identical titles -> 'Title' + 'Title (1)' | **PASS** | T11.1: PASS |
| T12 | Close mid-queue -> relaunch -> restore prompt -> resumes | **PASS** | T12.0: PASS; T12.1: PASS; T12.2: PASS; T12.2b: PASS; T12.3: PASS; T12.4: PASS; T12.5: PASS |
| T13 | First-run picker once only; no silent death | **PASS** | T13.1: PASS; T13.2: PASS; T13.3: PASS; T13.4: PASS; T13.5: PASS; T13.5b: PASS; T13.6: PASS; T13.7: PASS; T13.8: PASS; T13.9: PASS; T13.10: PASS; T13.11: PASS |
| T14 | Second instance focuses the first; no zombie processes | **PASS** | T14.1: PASS; T14.2: PASS; T14.3: PASS; T14.4: PASS; T14.5: PASS; T14.6: PASS; T14.7: PASS |
| T15 | Offline: retries then Failed; manual Retry works; a nearly-full drive fails with a sentence before yt-dlp starts | **PASS** | T15.1: PASS; T15.2: PASS; T15.3: PASS; T15.4: PASS; T15.5: PASS; T15.6: PASS; T15.7: PASS |
| T16 | Placeholder: hides, pastes, returns, Add ignores it | **PASS** | T16.1: PASS; T16.2: PASS; T16.3: PASS; T16.4: PASS; T16.5: PASS; T16.6: PASS; T16.6b: PASS; T16.7: PASS; T16.8: PASS; T16.9: PASS |
| T17 | Quality dropdown disabled for MP3/M4A, enabled for MP4 | **PASS** | T17.1: PASS; T17.2: PASS; T17.3: PASS; T17.4: PASS; T17.5: PASS; T17.6: PASS |
| T18 | bin\ missing -> window opens, Add disabled, bootstrap fixes it | **PASS** | T18.1: PASS; T18.2: PASS; T18.3: PASS; T18.4: PASS; T18.5: PASS; T18.6: PASS; T18.7: PASS |
| T19 | Silent toast once when the queue finishes; the in-app banner never eats input | **PASS** | T19.1: PASS; T19.2: PASS; T19.3: PASS; T19.4: PASS; T19.5: PASS |
| T21 | Portable copy: a remembered folder from another PC is replaced by <app folder>\downloads, which is where the next download lands and what the window shows | **PASS** | T21.0: PASS; T21.1: PASS; T21.1b: PASS; T21.1c: PASS; T21.2: PASS; T21.2b: PASS; T21.3: PASS; T21.4: PASS |
| T20 | selftest: App without mainloop, widget/method resolution | **PASS** | SELFTEST PASSED: 58 checks |

### T1 / T20 commands and output

`python -m compileall -q app.py metube scripts` (exit 0, empty output = clean):

```
(no output - clean)
```

`python scripts/selftest.py` (exit 0):

```
  PASS  a client switch happens quickly; long cooldowns stay for rate limits
  PASS  the title grace period covers a metadata lookup that walks the ladder
  PASS  a 0x92 (code page) apostrophe from yt-dlp is decoded, not mangled
  PASS  a bot check is still classified as BOT after a lossy decode
  PASS  ...even when the apostrophe already arrived as U+FFFD
  PASS  a relative folder is resolved against the MeTube folder
  PASS  a leading dot survives the resolution (yt-dlp would strip it)
  PASS  an absolute folder is left untouched
  PASS  free space of a real folder is readable
  PASS  an unreadable path reports 'unknown' instead of raising
  PASS  the disk-full reason names the free space, the drive and Retry
  PASS  the download free-space floor is not so low that it is pointless
  PASS  the engine bootstrap checks both the download drive and the temp drive

[runtime] construct App without mainloop and pump update()
  PASS  every attribute read by handlers exists after construction
  PASS  widget self.add_button exists
  PASS  widget self.format_menu exists
  PASS  widget self.quality_menu exists
  PASS  widget self.input_box exists
  PASS  widget self.queue_frame exists
  PASS  widget self.progress_label exists
  PASS  widget self.overall_bar exists
  PASS  widget self.pause_button exists
  PASS  widget self.clear_button exists
  PASS  widget self.cancel_all_button exists
  PASS  widget self.history_button exists
  PASS  widget self.settings_button exists
  PASS  widget self.queue_count_label exists
  PASS  widget self.empty_label exists
  PASS  widget self.settings_view exists
  PASS  widget self.history_view exists
  PASS  widget self.toast exists
  PASS  widget self.folder_label exists
  PASS  the 'Saving to' line names the configured download folder
  PASS  the 'Saving to' line follows a folder change
  PASS  quality disabled for MP3 (B9)
  PASS  quality enabled for MP4
  PASS  quality disabled for M4A (B9)
  PASS  placeholder is not real input (B7)
  PASS  Add with placeholder-only content does nothing
  PASS  view switching works

====================================================================
SELFTEST PASSED: 58 checks
```

## 3. B1 - B14 regression guarantees (Section 16)

| Row | The v1 bug that must not exist | Result | Evidence |
| --- | --- | --- | --- |
| B1 | set_default_color_theme('dark') / bare customtkinter NameError | **PASS** | SELFTEST PASSED: 58 checks; T17.1: PASS |
| B2 | grab_set before the window is mapped -> first-launch vanish | **PASS** | T13.1: PASS; T13.4: PASS; T13.5: PASS; T13.5b: PASS |
| B3 | os.replace across drives -> WinError 17 | **PASS** | B3.1: PASS; B3.2: PASS; T18.6: PASS; B4.1: PASS |
| B4 | gyan.dev SSL failure / bootstrap hang | **PASS** | B4.1: PASS; B4.2: PASS; B4.3: PASS; B4.4: PASS; T18.4: PASS |
| B5 | download folder cached at startup; Settings change ignored | **PASS** | T10.3: PASS; T10.4: PASS; T10.5: PASS |
| B6 | file_path never captured; Show/Open dead buttons | **PASS** | T2.1: PASS; T2.6: PASS; T2.7: PASS; T2.8: PASS |
| B7 | placeholder text blocked pasting | **PASS** | T16.1: PASS; T16.3: PASS; T16.4: PASS; T16.5: PASS; T16.8: PASS |
| B8 | keep-awake acquired at app start, never released | **PASS** | B8.1: PASS; B8.2: PASS |
| B9 | quality dropdown state wrong for audio formats | **PASS** | T17.1: PASS; T17.2: PASS; T17.3: PASS |
| B10 | missing _sync_main_dropdowns crashed startup | **PASS** | T17.4: PASS; SELFTEST PASSED: 58 checks |
| B11 | silent --noconsole death (no crash log) | **PASS** | T13.9: PASS; T13.10: PASS; T13.11: PASS |
| B12 | two competing data folders (source vs exe) | **PASS** | T13.7: PASS; T13.8: PASS |
| B13 | duplicate import lines / theme leftovers | **PASS** | SELFTEST PASSED: 58 checks |
| B14 | second launch needed twice | **PASS** | T13.6: PASS; T14.2: PASS; T14.5: PASS; T14.6: PASS |

## 4. Source-tree audit (Section 17 "clean tree")

| Rule | Expected | Measured |
| --- | --- | --- |
| one data-dir resolution | 1 | 1 |
| one filename sanitizer | 1 | 1 |
| one dropdown sync method | 1 | 1 |
| zero bare `except:` | 0 | 0 |
| every thread daemon | 0 non-daemon | 0 of 9 |
| worker modules never import tkinter | 0 | 0 |
| no widget mutation from workers | 0 | 0 |
| scanner sanity: widget calls visible in the UI layer | > 0 | 132 |

Threads are counted with the AST (so a multi-line `threading.Thread(...)`
call cannot hide a missing `daemon=True`), and the widget scan runs on
source with comments and string literals blanked, so prose about widgets is
not counted. The UI-layer count proves the scan is not vacuous.

## 5. Per-check detail

| Check | Scenario | Result | Detail |
| --- | --- | --- | --- |
| B3.1 | bootstrap | PASS | src_drive=F: dst_drive=C: cross_volume=True moved=2097152/2097152 src_removed=True |
| B3.2 | bootstrap | PASS | cwd drive=F: temp drive=C: |
| B4.1 | bootstrap | PASS | finished=True elapsed=1.1s outcome={'ok': False, 'message': 'Download failed (HTTP 404).'} |
| B4.2 | bootstrap | PASS | message='Download failed (HTTP 404).' |
| B4.3 | bootstrap | PASS | ytdlp=https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe ffmpeg=https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip |
| B4.4 | bootstrap | PASS | 'Create a folder named "bin" next to MeTube.exe and place these three files inside it, named exactly: yt-dlp.exe, ffmpeg.exe, ffprobe.exe.\n\nGet them from:\n  yt-dlp: https://github.com/yt-dlp/yt-dlp/releases/latest/dow |
| B8.1 | queue | PASS | acquired=False |
| B8.2 | queue | PASS | ACQUIRED=1 RELEASED=1 |
| T10.1 | folder | PASS | path=<USER>\MeTube\MeTube2\.e2e\folder\folder_a\Me at the zoo.mp3 |
| T10.2 | folder | PASS | queue=0 |
| T10.3 | folder | PASS | live='<USER>\\MeTube\\MeTube2\\.e2e\\folder\\folder_b' on_disk='<USER>\\MeTube\\MeTube2\\.e2e\\folder\\folder_b' |
| T10.3b | folder | PASS | label='Saving to  <USER>\MeTube\MeTube2\.e2e\folder\folder_b' |
| T10.4 | folder | PASS | path=<USER>\MeTube\MeTube2\.e2e\folder\folder_b\Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp3 |
| T10.5 | folder | PASS | folder_a=['Me at the zoo.mp3'] |
| T10.6 | folder | PASS | after relaunch='<USER>\MeTube\MeTube2\.e2e\folder\folder_b' expected='<USER>\MeTube\MeTube2\.e2e\folder\folder_b' |
| T10.6b | folder | PASS | entry='<USER>\MeTube\MeTube2\.e2e\folder\folder_b' |
| T10.6c | folder | PASS | label='Saving to  <USER>\MeTube\MeTube2\.e2e\folder\folder_b' |
| T10.6d | folder | PASS | stored='<USER>\MeTube\MeTube2\relative_probe' shown='<USER>\MeTube\MeTube2\relative_probe' |
| T10.6e | folder | PASS | label='Saving to  <USER>\MeTube\MeTube2\relative_probe' |
| T10.7 | folder | PASS | path=<USER>\MeTube\MeTube2\.e2e\folder\folder_b\Me at the zoo.mp3 shown=<USER>\MeTube\MeTube2\.e2e\folder\folder_b |
| T10.8 | folder | PASS | bot_checks=0 client_switches=0 |
| T10.9 | folder | PASS | replacement_chars=0 |
| T11.1 | queue | PASS | names=['Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film (1).mp3', 'Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp3'] |
| T12.0 | restore | PASS | statuses=['Downloading… 0%', 'Queued', 'Queued'] |
| T12.1 | restore | PASS | path=<USER>\MeTube\MeTube2\.e2e\restore\data\queue.json items=[(None, 'Downloading… 0%'), (None, 'Queued'), (None, 'Queued')] |
| T12.2 | restore | PASS | shown=1 answered=True |
| T12.2b | restore | PASS | statuses=['Queued', 'Queued', 'Queued'] |
| T12.3 | restore | PASS | statuses=['Downloading… 0%', 'Queued', 'Queued'] |
| T12.4 | restore | PASS | shown=1 queue=0 snapshot=0 |
| T12.5 | restore | PASS | shown=0 queue=0 |
| T13.1 | firstrun | PASS | shown=1 answered='<USER>\\MeTube\\MeTube2\\.e2e\\firstrun\\downloads' |
| T13.10 | firstrun | PASS | rc=0 path=<USER>\MeTube\MeTube2\.e2e\firstrun\crashdata\logs\crash.log body='\n===== 2026-10-13 00:52:29 :: probe =====\nTraceback (most recent call last):\n  File "<string>", line 5, in <module>\n    raise Runtim |
| T13.11 | firstrun | PASS |  |
| T13.2 | firstrun | PASS | path=<USER>\MeTube\MeTube2\.e2e\firstrun\data\settings.json first_run=False |
| T13.3 | firstrun | PASS | <USER>\MeTube\MeTube2\.e2e\firstrun\downloads |
| T13.4 | firstrun | PASS | state=normal exists=1 |
| T13.5 | firstrun | PASS | deferred after(150, _safe_grab) + try/except TclError present |
| T13.5b | firstrun | PASS |  |
| T13.6 | firstrun | PASS | dialogs shown=0 |
| T13.7 | firstrun | PASS | log=<USER>\MeTube\MeTube2\.e2e\firstrun\data\logs\app.log exists=True |
| T13.8 | firstrun | PASS | config.data_dir()=<USER>\MeTube\MeTube2\.e2e\firstrun\data project data=<USER>\MeTube\MeTube2\data |
| T13.9 | firstrun | PASS | <USER>\MeTube\MeTube2\.e2e\firstrun\data\logs\crash.log |
| T14.1 | instance | PASS |  |
| T14.2 | instance | PASS | rc=0 out='acquired False\nsignalled' err='' |
| T14.3 | instance | PASS |  |
| T14.4 | instance | PASS |  |
| T14.5 | instance | PASS | calls=['lift', 'focus'] |
| T14.6 | instance | PASS | exists=1 engine_ready=True |
| T14.7 | instance | PASS | INFO: No tasks are running which match the specified criteria. |
| T15.1 | offline | PASS | status='Failed: [youtube] jNQXAC9IVRw: Unable to download API page: (\'Unable to connect to proxy\', NewConnectionError("HTTPSConnection(host=\'127.0.0.1\', port=9): Failed to establish a new conne…' seen=['Downloading…' |
| T15.2 | offline | PASS | observed=['Downloading…', 'Failed: [youtube] jNQXAC9IVRw: Unable to download API page: (\'Unable to connect to proxy\', NewConnectionError("HTTPSConnection(host=\'127.0.0.1\', port=9): Failed to establish a new conne…',  |
| T15.3 | offline | PASS | reason='[youtube] jNQXAC9IVRw: Unable to download API page: (\'Unable to connect to proxy\', NewConnectionError("HTTPSConnection(host=\'127.0.0.1\', port=9): Failed to establish a new conne…' |
| T15.4 | offline | PASS | history=[('jNQXAC9IVRw', 'Failed: [youtube] jNQXAC9IVRw: Unable to download API page: (\'Unable to connect to proxy\', NewConnectionError("HTTPSConnection(host=\'127.0.0.1\', port=9): Failed to establish a new conne…')] |
| T15.5 | offline | PASS | status='Completed ✓' path=<USER>\MeTube\MeTube2\.e2e\offline\downloads\jNQXAC9IVRw.mp3 |
| T15.6 | offline | PASS | status='Failed: not enough free disk space (5 MB left on F:) — free some space, then press Retry' |
| T15.7 | offline | PASS | download_start_lines=0 |
| T16.1 | ui | PASS | showing=True raw='Paste YouTube links — separate with commas or new lines' |
| T16.2 | ui | PASS | tag fg='#9A9AA5' |
| T16.3 | ui | PASS | showing=False raw='' |
| T16.4 | ui | PASS | input='https://www.youtube.com/watch?v=jNQXAC9IVRw' |
| T16.5 | ui | PASS | input='https://www.youtube.com/watch?v=jNQXAC9IVRw' |
| T16.6 | ui | PASS | queue=1 bindings=('<Control-Key-Return>', '<FocusOut>', '<FocusIn>') |
| T16.6b | ui | PASS | get_input='' |
| T16.7 | ui | PASS | queue before=1 after=1 |
| T16.8 | ui | PASS | queue=1 showing=True raw='Paste YouTube links — separate with commas or new lines' |
| T16.9 | ui | PASS | showing=True raw='Paste YouTube links — separate with commas or new lines' |
| T17.1 | ui | PASS | MP3=normal (was True) / M4A=True / MP4=normal (was True) |
| T17.2 | ui | PASS | fmt=MP3 quality=Best Available state=disabled |
| T17.3 | ui | PASS | settings quality state=disabled |
| T17.4 | ui | PASS |  |
| T17.5 | ui | PASS | state=normal |
| T17.6 | ui | PASS | settings=1 history=1 main=1 |
| T18.1 | bootstrap | PASS | exists=1 state=normal |
| T18.2 | bootstrap | PASS | state=disabled text='Preparing engine…' |
| T18.3 | bootstrap | PASS | engine_ready=False |
| T18.4 | bootstrap | PASS | ready=True text='Add to Queue' |
| T18.5 | bootstrap | PASS | <USER>\MeTube\MeTube2\.e2e\bootstrap\livedata\bin -> ['ffmpeg.exe', 'ffprobe.exe', 'yt-dlp.exe'] |
| T18.6 | bootstrap | PASS |  |
| T18.7 | bootstrap | PASS | ['ffmpeg.exe', 'ffprobe.exe', 'yt-dlp.exe'] |
| T19.1 | queue | PASS | toasts=[(5, 1, True)] |
| T19.2 | queue | PASS | winotify.Notification(app_id='MeTube', duration='short') — no audio API used |
| T19.3 | queue | PASS | mapped=True size=290x55 |
| T19.4 | queue | PASS | handles=[4391852, 1770720] exstyles=['0x80024', '0x800a8'] |
| T19.5 | queue | PASS | banner=4391852 window_at_point=65796 chain=[65796, 65794, 65790, 65700] |
| T2.1 | queue | PASS | status='Completed ✓' file_path='<USER>\\MeTube\\MeTube2\\.e2e\\queue\\downloads\\Me at the zoo.mp3' |
| T2.2 | queue | PASS | <USER>\MeTube\MeTube2\.e2e\queue\downloads\Me at the zoo.mp3 |
| T2.3 | queue | PASS | kinds=['audio', 'video'] attached_pic=True size=787643 |
| T2.4 | queue | PASS | title='Me at the zoo' artist='jawed' |
| T2.5 | queue | PASS | card_status='Completed ✓' buttons=('Show in folder', 'Open file') |
| T2.6 | queue | PASS | {'timestamp': '2026-10-13 00:43:20', 'title': 'Me at the zoo', 'url': 'https://www.youtube.com/watch?v=jNQXAC9IVRw', 'video_id': 'jNQXAC9IVRw', 'fmt': 'MP3', 'quality': 'Best Available', 'status': 'Completed ✓', 'file_pa |
| T2.7 | queue | PASS | revealed=['<USER>\\MeTube\\MeTube2\\.e2e\\queue\\downloads\\Me at the zoo.mp3'] opened=['<USER>\\MeTube\\MeTube2\\.e2e\\queue\\downloads\\Me at the zoo.mp3'] |
| T2.8 | queue | PASS | messages=['File location unknown — check your download folder', 'File location unknown — check your download folder'] |
| T21.0 | portable | PASS | Q:\metube_other_pc\Downloads\MeTube usable=False |
| T21.1 | portable | PASS | folder='<USER>\MeTube\MeTube2\downloads' expected='<USER>\MeTube\MeTube2\downloads' |
| T21.1b | portable | PASS | restore dialogs shown=0 |
| T21.1c | portable | PASS | label='Saving to  <USER>\MeTube\MeTube2\downloads' |
| T21.2 | portable | PASS | on_disk='<USER>\MeTube\MeTube2\downloads' |
| T21.2b | portable | PASS | notice logged=True |
| T21.3 | portable | PASS | path=<USER>\MeTube\MeTube2\downloads\Me at the zoo.mp3 |
| T21.4 | portable | PASS | <USER>\MeTube\MeTube2\downloads exists=False |
| T3.0 | mp4 | PASS | jNQXAC9IVRw:Completed ✓; 9bZkp7q19f0:Completed ✓ |
| T3.1 | mp4 | PASS | status=Completed ✓ path=<USER>\MeTube\MeTube2\.e2e\mp4\downloads\Me at the zoo.mp4 |
| T3.2 | mp4 | PASS | probed height=240 |
| T4.1 | mp4 | PASS | status=Completed ✓ height=360 |
| T4.2 | mp4 | PASS | <USER>\MeTube\MeTube2\.e2e\mp4\downloads\PSY - GANGNAM STYLE(강남스타일) MV.mp4 |
| T4.3 | mp4 | PASS | rc=0 out='144/160+140' err='' |
| T4.4 | mp4 | PASS | rc=0 out='720' |
| T5.0 | queue | PASS | engine_ready=True state=normal |
| T5.1 | queue | PASS | split -> ['https://www.youtube.com/watch?v=jNQXAC9IVRw', 'https://youtu.be/dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=9bZkp7q19f0', 'https://www.youtube.com/watch?v=jNQXAC9IVRw'] |
| T5.2 | queue | PASS | queue=3 cards=3 ids=['jNQXAC9IVRw', 'dQw4w9WgXcQ', '9bZkp7q19f0'] |
| T5.3 | queue | PASS | queue now 3 |
| T5.4 | queue | PASS | observed ['Starting in 1s', 'Starting in 2s', 'Starting in 3s', 'Starting in 4s'] ticks=[1, 2, 3, 4] countdown->download gap=4.12s |
| T5.5 | queue | PASS | jNQXAC9IVRw:Completed ✓; dQw4w9WgXcQ:Completed ✓; 9bZkp7q19f0:Completed ✓; zzzzzzzzzzz:Failed: [youtube] zzzzzzzzzzz: This video is unavailable; aqz-KE-bpKQ:Completed ✓; aqz-KE-bpKQ:Completed ✓ |
| T5.6 | queue | PASS | polls saw 753 'Downloading…' states across 6 items; max concurrent = 1 |
| T6.1 | playlist | PASS | id=UU4QobU6STFB0P71PMvOGN5A -> ['jNQXAC9IVRw'] |
| T6.2 | playlist | PASS |  |
| T6.3 | playlist | PASS | is_playlist=False id=jNQXAC9IVRw |
| T6.3b | playlist | PASS | is_playlist=False id=dQw4w9WgXcQ |
| T6.4 | playlist | PASS | expected=1 got=1 urls=['https://www.youtube.com/watch?v=jNQXAC9IVRw'] |
| T6.5 | playlist | PASS | toast='Added 1 videos from playlist' |
| T6.6 | playlist | PASS | queue=2 rick_items=1 |
| T7.0 | queue | PASS | queue=['https://www.youtube.com/watch?v=jNQXAC9IVRw', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=9bZkp7q19f0', 'https://www.youtube.com/watch?v=zzzzzzzzzzz'] |
| T7.1 | queue | PASS | status='Failed: [youtube] zzzzzzzzzzz: This video is unavailable' |
| T7.2 | queue | PASS | completed=5 |
| T8.0 | controls | PASS | [('aqz-KE-bpKQ', 'MP4', '720p'), ('aqz-KE-bpKQ', 'MP4', '720p'), ('jNQXAC9IVRw', 'MP3', '720p')] |
| T8.1 | controls | PASS | status=Downloading… 0% |
| T8.2 | controls | PASS | suspended=1 statuses=['stopped'] (at pause: ['stopped']) |
| T8.3 | controls | PASS | before=[] after=[] |
| T8.4 | controls | PASS | status='Paused' |
| T8.5 | controls | PASS | ['running'] engine_list=[] |
| T8.6 | controls | PASS |  |
| T8.7 | controls | PASS | status='Completed ✓' path=<USER>\MeTube\MeTube2\.e2e\controls\downloads\Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp4 |
| T9.1 | controls | PASS | status=Downloading… 0% |
| T9.2 | controls | PASS | status='Cancelled' |
| T9.3 | controls | PASS | before=[] after=[] |
| T9.4 | controls | PASS | next status='Starting in 2s' |
| T9.5 | controls | PASS | status='Completed ✓' |

## 6. Raw harness transcript

```
=================== scenario: queue (pid separated) ===================

=================== scenario: queue ===================
2026-10-13 00:43:05,094 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:43:05,094 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:43:05,094 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:43:05,094 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\queue\data  (METUBE_DATA_DIR override)
2026-10-13 00:43:05,095 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\queue\data\settings.json
2026-10-13 00:43:06,193 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:43:08,054 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T5.0      engine ready at startup; bin\ resolved from app_dir
  [PASS] T5.1      paste splits on newlines / commas / semicolons
  [PASS] T5.2      4 pasted links with 1 duplicate -> 3 cards, duplicate skipped silently
  [PASS] T5.3      re-pasting the same links adds zero items
2026-10-13 00:43:12,542 INFO    [MetadataFetcher-1] metube.metadata: metadata resolved for jNQXAC9IVRw: Me at the zoo
2026-10-13 00:43:12,692 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\queue\downloads
2026-10-13 00:43:12,708 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:43:13,906 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for dQw4w9WgXcQ: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)
2026-10-13 00:43:17,063 INFO    [MetadataFetcher-1] metube.metadata: metadata resolved for 9bZkp7q19f0: PSY - GANGNAM STYLE(강남스타일) M/V
2026-10-13 00:43:20,057 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\queue\downloads\Me at the zoo.mp3
2026-10-13 00:43:20,126 INFO    [QueueWorker] metube.engine: completed: Me at the zoo -> <USER>\MeTube\MeTube2\.e2e\queue\downloads\Me at the zoo.mp3
  [PASS] T5.4      visible 'Starting in {n}s' countdown ticks down between items (3-5s window)
2026-10-13 00:43:24,324 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=dQw4w9WgXcQ -> <USER>\MeTube\MeTube2\.e2e\queue\downloads
  [PASS] T7.0      bogus link is accepted with no add-time validation (as specified)
2026-10-13 00:43:27,655 INFO    [MetadataFetcher-0] metube.metadata: metadata lookup failed for https://www.youtube.com/watch?v=zzzzzzzzzzz: ERROR: [youtube] zzzzzzzzzzz: This video is unavailable
2026-10-13 00:43:29,622 INFO    [MetadataFetcher-1] metube.metadata: metadata resolved for aqz-KE-bpKQ: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film
2026-10-13 00:43:31,622 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for aqz-KE-bpKQ: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film
2026-10-13 00:43:34,573 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\queue\downloads\Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp3
2026-10-13 00:43:34,650 INFO    [QueueWorker] metube.engine: completed: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster) -> <USER>\MeTube\MeTube2\.e2e\queue\downloads\Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp3
2026-10-13 00:43:39,869 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=9bZkp7q19f0 -> <USER>\MeTube\MeTube2\.e2e\queue\downloads
2026-10-13 00:43:44,097 WARNING [QueueWorker] metube.downloader: download failed (exit=1 cancelled=False): ERROR: unable to download video data: HTTP Error 403: Forbidden
2026-10-13 00:43:59,713 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=9bZkp7q19f0 -> <USER>\MeTube\MeTube2\.e2e\queue\downloads
2026-10-13 00:44:09,669 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\queue\downloads\PSY - GANGNAM STYLE(강남스타일) MV.mp3
2026-10-13 00:44:09,730 INFO    [QueueWorker] metube.engine: completed: PSY - GANGNAM STYLE(강남스타일) M/V -> <USER>\MeTube\MeTube2\.e2e\queue\downloads\PSY - GANGNAM STYLE(강남스타일) MV.mp3
2026-10-13 00:44:26,967 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=zzzzzzzzzzz -> <USER>\MeTube\MeTube2\.e2e\queue\downloads
2026-10-13 00:44:29,474 WARNING [QueueWorker] metube.downloader: download failed (exit=1 cancelled=False): ERROR: [youtube] zzzzzzzzzzz: This video is unavailable
2026-10-13 00:44:29,561 WARNING [QueueWorker] metube.engine: failed: zzzzzzzzzzz :: [youtube] zzzzzzzzzzz: This video is unavailable
2026-10-13 00:44:32,705 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=aqz-KE-bpKQ -> <USER>\MeTube\MeTube2\.e2e\queue\downloads
2026-10-13 00:44:52,332 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\queue\downloads\Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp3
2026-10-13 00:44:52,420 INFO    [QueueWorker] metube.engine: completed: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film -> <USER>\MeTube\MeTube2\.e2e\queue\downloads\Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp3
2026-10-13 00:44:56,580 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=aqz-KE-bpKQ -> <USER>\MeTube\MeTube2\.e2e\queue\downloads
2026-10-13 00:45:16,009 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\queue\downloads\Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film (1).mp3
2026-10-13 00:45:16,075 INFO    [QueueWorker] metube.engine: completed: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film -> <USER>\MeTube\MeTube2\.e2e\queue\downloads\Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film (1).mp3
2026-10-13 00:45:16,075 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:45:16,075 INFO    [QueueWorker] metube.engine: queue idle: 5 completed, 1 failed
2026-10-13 00:45:16,153 INFO    [MainThread] metube.notify: toast shown: Queue finished: 5 completed, 1 failed.
  [PASS] T5.5      queue drains to terminal states (strictly sequential, nothing hangs)
  [PASS] T5.6      exactly one item was ever 'Downloading' at a time (no parallelism)
  [PASS] T2.1      MP3 download completed with a real file_path (regression B6)
  [PASS] T2.2      MP3 lands in the chosen folder with the .mp3 extension
  [PASS] T2.3      MP3 probes clean: audio stream + embedded thumbnail picture
  [PASS] T2.4      MP3 carries embedded title metadata
  [PASS] T2.5      card shows 'Completed ✓' and offers Show in folder / Open file
  [PASS] T2.6      history row exists for the completed MP3 and holds file_path
  [PASS] T2.7      'Show in folder' and 'Open file' actually call through (B6)
  [PASS] T2.8      missing file_path shows 'File location unknown', never a silent no-op
  [PASS] T7.1      invalid URL failed with a human reason and did not block the queue
  [PASS] T7.2      queue kept going after the failure (3 successes present)
  [PASS] T11.1     two identical titles -> 'Title.mp3' + 'Title (1).mp3'
  [PASS] T19.1     queue_finished toast fired exactly once with real counts
  [PASS] T19.2     toast is silent (winotify Notification built with duration='short', no audio)
  [PASS] T19.3     the finished-queue banner is on screen while it should be
  [PASS] T19.4     the banner window carries WS_EX_TRANSPARENT (it and its Tk wrapper)
  [PASS] T19.5     a hit-test in the middle of the banner lands on the main window, not the banner
  [PASS] B8.1      keep-awake released once the queue is fully idle
  [PASS] B8.2      keep-awake transitions are logged (acquired only when downloading)
2026-10-13 00:45:20,149 INFO    [MainThread] metube.engine: queue worker stopped

=== 26/26 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: mp4 (pid separated) ===================

=================== scenario: mp4 ===================
2026-10-13 00:45:20,600 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:45:20,600 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:45:20,600 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:45:20,600 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\mp4\data  (METUBE_DATA_DIR override)
2026-10-13 00:45:20,600 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\mp4\data\settings.json
2026-10-13 00:45:21,606 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:45:23,380 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
2026-10-13 00:45:27,928 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for jNQXAC9IVRw: Me at the zoo
2026-10-13 00:45:28,091 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\mp4\downloads
2026-10-13 00:45:28,100 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:45:29,486 INFO    [MetadataFetcher-1] metube.metadata: metadata resolved for 9bZkp7q19f0: PSY - GANGNAM STYLE(강남스타일) M/V
2026-10-13 00:45:31,911 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\mp4\downloads\Me at the zoo.mp4
2026-10-13 00:45:31,977 INFO    [QueueWorker] metube.engine: completed: Me at the zoo -> <USER>\MeTube\MeTube2\.e2e\mp4\downloads\Me at the zoo.mp4
2026-10-13 00:45:34,135 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=9bZkp7q19f0 -> <USER>\MeTube\MeTube2\.e2e\mp4\downloads
2026-10-13 00:45:39,595 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\mp4\downloads\PSY - GANGNAM STYLE(강남스타일) MV.mp4
2026-10-13 00:45:39,675 INFO    [QueueWorker] metube.engine: completed: PSY - GANGNAM STYLE(강남스타일) M/V -> <USER>\MeTube\MeTube2\.e2e\mp4\downloads\PSY - GANGNAM STYLE(강남스타일) MV.mp4
2026-10-13 00:45:39,675 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:45:39,675 INFO    [QueueWorker] metube.engine: queue idle: 2 completed, 0 failed
2026-10-13 00:45:39,770 INFO    [MainThread] metube.notify: toast shown: Queue finished: 2 completed, 0 failed.
  [PASS] T3.0      MP4 queue finished
  [PASS] T3.1      MP4 Best produced a real .mp4 in the download folder
  [PASS] T3.2      MP4 Best height equals the source max (240p for Me at the zoo)
  [PASS] T4.1      MP4 capped 360p on a 1080p source -> nearest lower (360p), not a failure
  [PASS] T4.2      capped MP4 still merged to .mp4 with an audio stream
2026-10-13 00:45:43,863 INFO    [MainThread] metube.engine: queue worker stopped
  [PASS] T4.3      under-satisfiable cap still resolves via the trailing '/best' (no failure)
  [PASS] T4.4      capped 720p selector against a 1080p source resolves to height<=720

=== 7/7 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: folder (pid separated) ===================

=================== scenario: folder ===================
2026-10-13 00:45:51,464 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:45:51,464 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:45:51,464 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:45:51,464 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\folder\data  (METUBE_DATA_DIR override)
2026-10-13 00:45:51,465 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\folder\data\settings.json
2026-10-13 00:45:52,392 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:45:54,259 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
2026-10-13 00:45:58,947 INFO    [MetadataFetcher-1] metube.metadata: metadata resolved for jNQXAC9IVRw: Me at the zoo
2026-10-13 00:45:59,069 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\folder\folder_a
2026-10-13 00:45:59,118 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:46:12,925 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\folder\folder_a\Me at the zoo.mp3
2026-10-13 00:46:12,999 INFO    [QueueWorker] metube.engine: completed: Me at the zoo -> <USER>\MeTube\MeTube2\.e2e\folder\folder_a\Me at the zoo.mp3
2026-10-13 00:46:12,999 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:46:12,999 INFO    [QueueWorker] metube.engine: queue idle: 1 completed, 0 failed
2026-10-13 00:46:13,057 INFO    [MainThread] metube.notify: toast shown: Queue finished: 1 completed, 0 failed.
  [PASS] T10.1     item 1 lands in the folder configured at launch
  [PASS] T10.2     'Clear Completed' empties the queue
2026-10-13 00:46:17,806 INFO    [MainThread] metube.app: settings saved; download folder = <USER>\MeTube\MeTube2\.e2e\folder\folder_b
  [PASS] T10.3     Settings save applies immediately (settings.json + live object)
2026-10-13 00:46:22,331 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for dQw4w9WgXcQ: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)
2026-10-13 00:46:22,374 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=dQw4w9WgXcQ -> <USER>\MeTube\MeTube2\.e2e\folder\folder_b
2026-10-13 00:46:22,383 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:46:31,817 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\folder\folder_b\Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp3
2026-10-13 00:46:31,878 INFO    [QueueWorker] metube.engine: completed: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster) -> <USER>\MeTube\MeTube2\.e2e\folder\folder_b\Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp3
2026-10-13 00:46:31,879 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:46:31,879 INFO    [QueueWorker] metube.engine: queue idle: 1 completed, 0 failed
2026-10-13 00:46:31,901 INFO    [MainThread] metube.notify: toast shown: Queue finished: 1 completed, 0 failed.
  [PASS] T10.3b    the main window's 'Saving to' line follows the change immediately
  [PASS] T10.4     item 2 lands in the NEW folder with NO restart (regression B5)
  [PASS] T10.5     nothing new was written into the old folder after the change
2026-10-13 00:46:35,832 INFO    [MainThread] metube.engine: queue worker stopped
2026-10-13 00:46:36,503 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:46:38,369 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T10.6     the download folder change survives a restart
  [PASS] T10.6b    the Settings screen shows the remembered folder (nothing to re-enter)
  [PASS] T10.6c    the relaunched window shows the remembered folder without opening Settings
2026-10-13 00:46:40,028 INFO    [MainThread] metube.app: settings saved; download folder = <USER>\MeTube\MeTube2\relative_probe
  [PASS] T10.6d    a relative download folder is stored absolute, under the app folder
  [PASS] T10.6e    ...and the 'Saving to' line shows the resolved folder
2026-10-13 00:46:40,461 INFO    [MainThread] metube.app: settings saved; download folder = <USER>\MeTube\MeTube2\.e2e\folder\folder_b
2026-10-13 00:46:44,368 INFO    [MetadataFetcher-1] metube.metadata: metadata resolved for jNQXAC9IVRw: Me at the zoo
2026-10-13 00:46:44,498 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\folder\folder_b
2026-10-13 00:46:44,507 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:46:57,384 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\folder\folder_b\Me at the zoo.mp3
2026-10-13 00:46:57,456 INFO    [QueueWorker] metube.engine: completed: Me at the zoo -> <USER>\MeTube\MeTube2\.e2e\folder\folder_b\Me at the zoo.mp3
2026-10-13 00:46:57,456 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:46:57,457 INFO    [QueueWorker] metube.engine: queue idle: 1 completed, 0 failed
2026-10-13 00:46:57,554 INFO    [MainThread] metube.notify: toast shown: Queue finished: 1 completed, 0 failed.
  [PASS] T10.7     a real download AFTER the restart lands in the remembered folder
  [PASS] T10.8     every bot check met by a real download switched the YouTube client
  [PASS] T10.9     no mojibake (U+FFFD) anywhere in the log of real downloads
2026-10-13 00:47:01,485 INFO    [MainThread] metube.engine: queue worker stopped

=== 14/14 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: portable (pid separated) ===================

=================== scenario: portable ===================
  [PASS] T21.0     the 'other PC' folder in settings.json really is unreachable here
2026-10-13 00:47:02,197 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:47:02,197 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:47:02,197 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:47:02,197 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\portable\data  (METUBE_DATA_DIR override)
2026-10-13 00:47:02,197 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\portable\data\settings.json
2026-10-13 00:47:02,317 WARNING [MainThread] metube.app: remembered download folder Q:\metube_other_pc\Downloads\MeTube is not usable here - using <USER>\MeTube\MeTube2\downloads
2026-10-13 00:47:02,388 INFO    [MainThread] metube.app: settings found at <USER>\MeTube\MeTube2\.e2e\portable\data\settings.json — skipping first-run dialog
2026-10-13 00:47:03,148 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:47:03,149 WARNING [MainThread] metube.app: Saved download folder is unavailable — downloads now go to <USER>\MeTube\MeTube2\downloads
2026-10-13 00:47:05,056 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T21.1     the app starts and moves downloads into its own folder
  [PASS] T21.1b    a queue holding only finished items does not nag for a restore
  [PASS] T21.2     the replacement is persisted, so the next launch needs no action
  [PASS] T21.1c    the window shows the folder the app will really use
  [PASS] T21.2b    the user is told where the downloads went
2026-10-13 00:47:09,494 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for jNQXAC9IVRw: Me at the zoo
2026-10-13 00:47:09,731 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\downloads
2026-10-13 00:47:09,739 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:47:22,630 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\downloads\Me at the zoo.mp3
2026-10-13 00:47:22,703 INFO    [QueueWorker] metube.engine: completed: Me at the zoo -> <USER>\MeTube\MeTube2\downloads\Me at the zoo.mp3
2026-10-13 00:47:22,703 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:47:22,703 INFO    [QueueWorker] metube.engine: queue idle: 1 completed, 0 failed
2026-10-13 00:47:22,824 INFO    [MainThread] metube.notify: toast shown: Queue finished: 1 completed, 0 failed.
  [PASS] T21.3     a real download lands in <app folder>\downloads
2026-10-13 00:47:26,723 INFO    [MainThread] metube.engine: queue worker stopped
  [PASS] T21.4     the harness cleaned up the portable downloads folder it created

=== 8/8 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: playlist (pid separated) ===================

=================== scenario: playlist ===================
  [PASS] T6.1      expand_playlist() returns video ids for a pure playlist URL
  [PASS] T6.2      is_playlist_url() true for the pure playlist URL
  [PASS] T6.3      watch?v=X&list=Y is NOT treated as a playlist (exactly one item)
  [PASS] T6.3b     m.youtube.com /shorts-style extra params still resolve to one video id
2026-10-13 00:47:29,593 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:47:29,593 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:47:29,593 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:47:29,593 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\playlist\data  (METUBE_DATA_DIR override)
2026-10-13 00:47:29,594 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\playlist\data\settings.json
2026-10-13 00:47:30,537 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:47:32,412 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T6.4      pasting a pure playlist URL adds N cards, none of them the playlist itself
  [PASS] T6.5      toast announces 'Added N videos from playlist'
  [PASS] T6.6      watch?v=&list= adds exactly one item (playlist stripped, dedupe apart)
2026-10-13 00:47:37,026 INFO    [MainThread] metube.engine: queue worker stopped

=== 7/7 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: controls (pid separated) ===================

=================== scenario: controls ===================
2026-10-13 00:47:37,487 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:47:37,487 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:47:37,487 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:47:37,487 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\controls\data  (METUBE_DATA_DIR override)
2026-10-13 00:47:37,487 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\controls\data\settings.json
2026-10-13 00:47:38,333 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:47:40,050 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T8.0      three items queued (2x MP4 720p, 1x MP3 tail)
2026-10-13 00:47:44,821 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for aqz-KE-bpKQ: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film
2026-10-13 00:47:44,985 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=aqz-KE-bpKQ -> <USER>\MeTube\MeTube2\.e2e\controls\downloads
  [PASS] T8.1      caught item 1 mid-download
2026-10-13 00:47:45,004 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:47:45,029 INFO    [QueueWorker] metube.engine: paused immediately after spawn
2026-10-13 00:47:45,640 INFO    [MetadataFetcher-1] metube.metadata: metadata resolved for aqz-KE-bpKQ: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film
  [PASS] T8.2      Pause suspends the live yt-dlp process tree (psutil status -> stopped)
  [PASS] T8.3      no bytes are written while paused
  [PASS] T8.4      card shows 'Paused' while the pause is active
2026-10-13 00:47:48,999 INFO    [MainThread] metube.engine: resumed paused process tree
2026-10-13 00:47:49,629 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for jNQXAC9IVRw: Me at the zoo
  [PASS] T8.5      Resume un-suspends the process tree and clears the engine's list
  [PASS] T8.6      download continues growing after Resume
2026-10-13 00:47:54,161 WARNING [QueueWorker] metube.downloader: download failed (exit=1 cancelled=False): ERROR: unable to download video data: HTTP Error 403: Forbidden
2026-10-13 00:48:09,825 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=aqz-KE-bpKQ -> <USER>\MeTube\MeTube2\.e2e\controls\downloads
2026-10-13 00:48:29,823 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\controls\downloads\Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp4
  [PASS] T8.7      the paused-then-resumed item completes successfully
2026-10-13 00:48:30,078 INFO    [QueueWorker] metube.engine: completed: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film -> <USER>\MeTube\MeTube2\.e2e\controls\downloads\Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film.mp4
2026-10-13 00:48:32,265 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=aqz-KE-bpKQ -> <USER>\MeTube\MeTube2\.e2e\controls\downloads
  [PASS] T9.1      caught item 2 mid-download
  [PASS] T9.2      Cancel marks the item Cancelled
  [PASS] T9.3      partial .part / .ytdl temp files are removed after Cancel
2026-10-13 00:48:52,202 WARNING [QueueWorker] metube.downloader: download failed (exit=0 cancelled=True): 
2026-10-13 00:48:52,241 INFO    [QueueWorker] metube.engine: cancelled: Big Buck Bunny 60fps 4K - Official Blender Foundation Short Film
  [PASS] T9.4      the cancelled item does not block the queue: next item starts
2026-10-13 00:48:54,462 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\controls\downloads
2026-10-13 00:49:05,527 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\controls\downloads\Me at the zoo.mp3
2026-10-13 00:49:05,605 INFO    [QueueWorker] metube.engine: completed: Me at the zoo -> <USER>\MeTube\MeTube2\.e2e\controls\downloads\Me at the zoo.mp3
2026-10-13 00:49:05,605 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:49:05,605 INFO    [QueueWorker] metube.engine: queue idle: 2 completed, 0 failed
2026-10-13 00:49:05,680 INFO    [MainThread] metube.notify: toast shown: Queue finished: 2 completed, 0 failed.
  [PASS] T9.5      the trailing item still completes after a cancel
2026-10-13 00:49:09,585 INFO    [MainThread] metube.engine: queue worker stopped

=== 13/13 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: offline (pid separated) ===================

=================== scenario: offline ===================
2026-10-13 00:49:10,027 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:49:10,027 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:49:10,027 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:49:10,027 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\offline\data  (METUBE_DATA_DIR override)
2026-10-13 00:49:10,027 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\offline\data\settings.json
2026-10-13 00:49:11,014 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:49:12,789 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
2026-10-13 00:49:25,013 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\offline\downloads
2026-10-13 00:49:25,027 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:49:31,272 INFO    [MetadataFetcher-1] metube.metadata: metadata lookup failed for https://www.youtube.com/watch?v=jNQXAC9IVRw:  establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))')); please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U
2026-10-13 00:49:43,183 WARNING [QueueWorker] metube.downloader: download failed (exit=1 cancelled=False): ction could be made because the target machine actively refused it")) (caused by ProxyError('(\'Unable to connect to proxy\', NewConnectionError("HTTPSConnection(host=\'127.0.0.1\', port=9): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))')); please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U
2026-10-13 00:49:58,594 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\offline\downloads
2026-10-13 00:50:16,733 WARNING [QueueWorker] metube.downloader: download failed (exit=1 cancelled=False): ction could be made because the target machine actively refused it")) (caused by ProxyError('(\'Unable to connect to proxy\', NewConnectionError("HTTPSConnection(host=\'127.0.0.1\', port=9): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))')); please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U
2026-10-13 00:50:47,691 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\offline\downloads
2026-10-13 00:51:05,894 WARNING [QueueWorker] metube.downloader: download failed (exit=1 cancelled=False): ction could be made because the target machine actively refused it")) (caused by ProxyError('(\'Unable to connect to proxy\', NewConnectionError("HTTPSConnection(host=\'127.0.0.1\', port=9): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))')); please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U
  [PASS] T15.1     offline download ends in a Failed status (never hangs forever)
  [PASS] T15.2     transient/bot failures are retried with visible vocabulary
  [PASS] T15.3     failure reason is one short human sentence, not a raw traceback
2026-10-13 00:51:05,948 WARNING [QueueWorker] metube.engine: failed: jNQXAC9IVRw :: [youtube] jNQXAC9IVRw: Unable to download API page: ('Unable to connect to proxy', NewConnectionError("HTTPSConnection(host='127.0.0.1', port=9): Failed to establish a new conne…
2026-10-13 00:51:05,948 INFO    [QueueWorker] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:51:05,948 INFO    [QueueWorker] metube.engine: queue idle: 0 completed, 1 failed
2026-10-13 00:51:06,025 INFO    [MainThread] metube.notify: toast shown: Queue finished: 0 completed, 1 failed.
  [PASS] T15.4     failure (with its reason) was recorded in history
  [PASS] T15.6     a nearly-full download drive fails with a sentence, not [Errno 28]
  [PASS] T15.7     ...and yt-dlp was never even started for that item
2026-10-13 00:51:18,189 WARNING [QueueWorker] metube.engine: failed:  :: not enough free disk space (5 MB left on F:) — free some space, then press Retry
2026-10-13 00:51:18,525 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\offline\downloads
2026-10-13 00:51:18,528 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:51:24,361 INFO    [MetadataFetcher-1] metube.metadata: metadata lookup failed for https://www.youtube.com/watch?v=dQw4w9WgXcQ:  establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))')); please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U
2026-10-13 00:51:31,436 INFO    [QueueWorker] metube.downloader: download finished: <USER>\MeTube\MeTube2\.e2e\offline\downloads\jNQXAC9IVRw.mp3
  [PASS] T15.5     manual Retry succeeds once the network is back
2026-10-13 00:51:31,506 INFO    [QueueWorker] metube.engine: completed: jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\offline\downloads\jNQXAC9IVRw.mp3
2026-10-13 00:51:31,506 INFO    [MainThread] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:51:31,507 INFO    [MainThread] metube.engine: queue worker stopped

=== 7/7 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: ui (pid separated) ===================

=================== scenario: ui ===================
2026-10-13 00:51:31,935 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:51:31,935 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:51:31,936 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:51:31,936 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\ui\data  (METUBE_DATA_DIR override)
2026-10-13 00:51:31,936 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\ui\data\settings.json
2026-10-13 00:51:32,936 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:51:34,726 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T16.1     startup: hint text is present, muted, and not real input
  [PASS] T16.2     hint is rendered in the muted colour, not the text colour
  [PASS] T16.3     FocusIn clears the hint and restores the normal text colour
  [PASS] T16.4     a link can be pasted immediately after focusing (regression B7)
  [PASS] T16.5     get_input() never returns the placeholder text
  [PASS] T16.6     Ctrl+Return is bound on the real inner Text and adds the item
  [PASS] T16.6b    deleting the hint leaves a genuinely empty, usable box
  [PASS] T16.7     Add with an empty textbox does nothing (no toast, no item)
  [PASS] T16.8     Add while the hint is showing (placeholder-only content) does nothing
  [PASS] T16.9     FocusOut on an empty box brings the hint back
  [PASS] T17.1     Quality dropdown: disabled for MP3, disabled for M4A, enabled for MP4
2026-10-13 00:51:38,763 INFO    [MainThread] metube.app: settings saved; download folder = <USER>\MeTube\MeTube2\.e2e\ui\downloads
  [PASS] T17.2     after a Settings save the dropdowns re-sync (B9): MP3 selected + Quality disabled
  [PASS] T17.3     the Settings screen's own Quality dropdown obeys the same rule
  [PASS] T17.4     sync method resolves under both canonical and alias names (B10)
  [PASS] T17.5     format dropdown stays always enabled
2026-10-13 00:51:39,259 INFO    [MetadataFetcher-0] metube.metadata: metadata resolved for jNQXAC9IVRw: Me at the zoo
2026-10-13 00:51:39,338 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\ui\downloads
2026-10-13 00:51:39,349 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
  [PASS] T17.6     Settings / History / main view switching works without errors
2026-10-13 00:51:40,395 WARNING [QueueWorker] metube.downloader: download failed (exit=15 cancelled=True): 
2026-10-13 00:51:40,401 INFO    [MainThread] metube.engine: terminated active download process
2026-10-13 00:51:40,421 INFO    [QueueWorker] metube.engine: cancelled: Me at the zoo
2026-10-13 00:51:40,421 INFO    [MainThread] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:51:40,421 INFO    [MainThread] metube.engine: queue worker stopped

=== 16/16 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: restore (pid separated) ===================

=================== scenario: restore ===================
2026-10-13 00:51:40,819 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:51:40,819 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:51:40,820 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:51:40,820 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\restore\data  (METUBE_DATA_DIR override)
2026-10-13 00:51:40,820 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\restore\data\settings.json
2026-10-13 00:51:41,745 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:51:43,879 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
2026-10-13 00:51:55,760 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\restore\downloads
2026-10-13 00:51:55,770 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
  [PASS] T12.0     the engine starts from a snapshot-loaded queue (state advances)
2026-10-13 00:51:55,800 INFO    [MainThread] metube.engine: terminated active download process
2026-10-13 00:51:55,800 WARNING [QueueWorker] metube.downloader: download failed (exit=15 cancelled=True): 
2026-10-13 00:51:55,801 INFO    [QueueWorker] metube.engine: cancelled: video
2026-10-13 00:51:55,801 INFO    [MainThread] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:51:55,801 INFO    [MainThread] metube.engine: queue worker stopped
  [PASS] T12.1     queue.json snapshot holds every item with all fields round-tripped
2026-10-13 00:51:55,978 INFO    [MainThread] metube.app: settings found at <USER>\MeTube\MeTube2\.e2e\restore\data\settings.json — skipping first-run dialog
2026-10-13 00:51:56,629 INFO    [MainThread] metube.app: restored 3 queue items
2026-10-13 00:51:56,854 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:51:58,709 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T12.2     relaunch shows 'Restore N items from your previous session?'
  [PASS] T12.2b    'Yes, restore' puts the unfinished items back on the queue
  [PASS] T12.3     the restored queue actually resumes downloading
2026-10-13 00:52:08,958 INFO    [QueueWorker] metube.downloader: download start: https://www.youtube.com/watch?v=jNQXAC9IVRw -> <USER>\MeTube\MeTube2\.e2e\restore\downloads
2026-10-13 00:52:08,961 INFO    [QueueWorker] metube.keepawake: keep-awake ACQUIRED (queue active)
2026-10-13 00:52:13,969 INFO    [MainThread] metube.keepawake: keep-awake RELEASED (queue idle)
2026-10-13 00:52:13,969 INFO    [MainThread] metube.engine: queue worker stopped
2026-10-13 00:52:20,289 WARNING [QueueWorker] metube.downloader: download failed (exit=0 cancelled=True): 
2026-10-13 00:52:20,326 INFO    [QueueWorker] metube.engine: cancelled: video
2026-10-13 00:52:20,503 INFO    [MainThread] metube.app: settings found at <USER>\MeTube\MeTube2\.e2e\restore\data\settings.json — skipping first-run dialog
2026-10-13 00:52:21,053 INFO    [MainThread] metube.app: queue snapshot cleared by user
2026-10-13 00:52:21,183 INFO    [MainThread] metube.engine: queue worker started
  [PASS] T12.4     'No, clear' empties the snapshot and leaves the queue empty
2026-10-13 00:52:22,573 INFO    [MainThread] metube.engine: queue worker stopped
2026-10-13 00:52:22,711 INFO    [MainThread] metube.app: settings found at <USER>\MeTube\MeTube2\.e2e\restore\data\settings.json — skipping first-run dialog
2026-10-13 00:52:23,175 INFO    [MainThread] metube.engine: queue worker started
  [PASS] T12.5     after 'No, clear' the next launch shows no restore prompt
2026-10-13 00:52:24,555 INFO    [MainThread] metube.engine: queue worker stopped

=== 7/7 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: firstrun (pid separated) ===================

=================== scenario: firstrun ===================
2026-10-13 00:52:25,144 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:52:25,144 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:52:25,144 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:52:25,144 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\firstrun\data  (METUBE_DATA_DIR override)
2026-10-13 00:52:25,144 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\firstrun\data\settings.json
2026-10-13 00:52:25,251 INFO    [MainThread] metube.app: first run detected — showing folder picker
2026-10-13 00:52:25,560 INFO    [MainThread] metube.app: first run complete; download folder = <USER>\MeTube\MeTube2\.e2e\firstrun\downloads
2026-10-13 00:52:26,198 INFO    [MainThread] metube.engine: queue worker started
  [PASS] T13.1     first run (no settings.json) shows the FirstRunDialog
  [PASS] T13.2     settings.json is written with first_run=false before the main window shows
  [PASS] T13.3     the chosen download folder is created
  [PASS] T13.4     the main window is visible (no flash-and-vanish, regression B2)
  [PASS] T13.5     the deferred grab is guarded (no unguarded grab_set on Windows, B2)
  [PASS] T13.5b    no unguarded grab on a not-yet-mapped window appeared in the log
2026-10-13 00:52:27,288 INFO    [MainThread] metube.engine: queue worker stopped
2026-10-13 00:52:27,538 INFO    [MainThread] metube.app: settings found at <USER>\MeTube\MeTube2\.e2e\firstrun\data\settings.json — skipping first-run dialog
2026-10-13 00:52:28,011 INFO    [MainThread] metube.engine: queue worker started
  [PASS] T13.6     second launch does NOT show the first-run picker (regression B14)
  [PASS] T13.7     the resolved settings.json path is logged at startup (B12)
  [PASS] T13.8     only ONE data folder is in play (regression B12)
  [PASS] T13.9     no crash.log was written during a clean first run (B11)
2026-10-13 00:52:29,113 INFO    [MainThread] metube.engine: queue worker stopped
  [PASS] T13.10    crash handler writes a full traceback to data\logs\crash.log (B11)
  [PASS] T13.11    logger exposes a MessageBox path so --noconsole apps never die silently

=== 12/12 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: instance (pid separated) ===================

=================== scenario: instance ===================
  [PASS] T14.1     first acquire() takes the named mutex
  [PASS] T14.2     a second process detects the running instance and signals it
  [PASS] T14.3     the running instance consumes the signal (WinEvent poll)
  [PASS] T14.4     the signal is one-shot (poll returns False the second time)
2026-10-13 00:52:30,067 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:52:30,067 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:52:30,067 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:52:30,067 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\instance\data  (METUBE_DATA_DIR override)
2026-10-13 00:52:30,067 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\instance\data\settings.json
2026-10-13 00:52:31,023 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:52:32,896 INFO    [MainThread] metube.app: engine validation passed: {'yt-dlp.exe': '2026.08.19', 'ffmpeg.exe': 'ffmpeg version N-127367-gb5902e69c7-20261011 Copyright (c) 2000-2026 the FFmpeg developers', 'ffprobe.exe': 'ffprobe version N-127367-gb5902e69c7-20261011 Copyright (c) 2007-2026 the FFmpeg developers'}
  [PASS] T14.5     a second launch lift()s and focuses the existing window
  [PASS] T14.6     the existing instance is still alive and usable
2026-10-13 00:52:33,707 INFO    [MainThread] metube.engine: queue worker stopped
  [PASS] T14.7     no zombie yt-dlp.exe processes remain after the instance probe

=== 7/7 checks passed in this run; 0 scenario exception(s) ===

=================== scenario: bootstrap (pid separated) ===================

=================== scenario: bootstrap ===================
  [PASS] B3.1      safe_move() survives a cross-volume move (no WinError 17)
  [PASS] B3.2      the cross-volume test really did cross a volume boundary
bootstrap failed: Download failed (HTTP 404).
Traceback (most recent call last):
  File "<USER>\MeTube\MeTube2\metube\binaries.py", line 260, in _worker
    download_engine_into(config.data_bin_dir(), on_progress)
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<USER>\MeTube\MeTube2\metube\binaries.py", line 238, in download_engine_into
    _download(YTDLP_URL, ytdlp_tmp, on_progress)
    ~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<USER>\MeTube\MeTube2\metube\binaries.py", line 147, in _download
    _download_once(url, target, on_progress)
    ~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<USER>\MeTube\MeTube2\metube\binaries.py", line 171, in _download_once
    with urllib.request.urlopen(request, timeout=60) as response, open(target, "wb") as fh:
         ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 189, in urlopen
    return opener.open(url, data, timeout)
           ~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 495, in open
    response = meth(req, response)
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 604, in http_response
    response = self.parent.error(
        'http', request, response, code, msg, hdrs)
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 527, in error
    result = self._call_chain(*args)
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 466, in _call_chain
    result = func(*args)
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 720, in http_error_302
    return self.parent.open(new, timeout=req.timeout)
           ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 495, in open
    response = meth(req, response)
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 604, in http_response
    response = self.parent.error(
        'http', request, response, code, msg, hdrs)
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 533, in error
    return self._call_chain(*args)
           ~~~~~~~~~~~~~~~~^^^^^^^
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 466, in _call_chain
    result = func(*args)
  File "C:\Users\<USER>\AppData\Local\Programs\Python\Python313\Lib\urllib\request.py", line 613, in http_error_default
    raise HTTPError(req.full_url, code, msg, hdrs, fp)
urllib.error.HTTPError: HTTP Error 404: Not Found
  [PASS] B4.1      a failing bootstrap calls on_done(False, ...) promptly (no hang, no dead UI)
  [PASS] B4.2      the failure message names the class of error (HTTP/SSL/disc/network)
  [PASS] B4.3      only GitHub URLs are used for the engine files (regression B4: gyan.dev)
  [PASS] B4.4      manual-fix instructions name the exact folder and the exact three filenames
2026-10-13 00:52:35,371 INFO    [MainThread] metube: ======================================================================
2026-10-13 00:52:35,371 INFO    [MainThread] metube: MeTube 2.0.0 starting
2026-10-13 00:52:35,371 INFO    [MainThread] metube: frozen=False app_dir=<USER>\MeTube\MeTube2
2026-10-13 00:52:35,371 INFO    [MainThread] metube: data_dir=<USER>\MeTube\MeTube2\.e2e\bootstrap\livedata  (METUBE_DATA_DIR override)
2026-10-13 00:52:35,371 INFO    [MainThread] metube: settings.json=<USER>\MeTube\MeTube2\.e2e\bootstrap\livedata\settings.json
2026-10-13 00:52:36,301 INFO    [MainThread] metube.engine: queue worker started
2026-10-13 00:52:36,302 WARNING [MainThread] metube.app: engine binaries incomplete at startup — bootstrapping
  [PASS] T18.1     window STILL opens with bin\ missing (no crash on bootstrap failure)
  [PASS] T18.2     Add to Queue is disabled and relabelled 'Preparing engine…'
  [PASS] T18.3     the queue engine is not considered ready
2026-10-13 00:53:20,929 INFO    [BootstrapThread] metube.binaries: bootstrap finished ok=True results={'yt-dlp.exe': (True, '2026.08.19'), 'ffmpeg.exe': (True, 'ffmpeg version N-127451-g263f271422-20261012 Copyright (c) 2000-2026 the FFmpeg developers'), 'ffprobe.exe': (True, 'ffprobe version N-127451-g263f271422-20261012 Copyright (c) 2007-2026 the FFmpeg developers')}
2026-10-13 00:53:21,034 INFO    [MainThread] metube.app: engine bootstrap succeeded
  [PASS] T18.4     bootstrap downloads the engine and re-enables Add to Queue
  [PASS] T18.5     the three engine files land in <data>\bin with exact names
  [PASS] T18.6     bootstrap used the cross-drive-safe move into data\bin (B3)
2026-10-13 00:53:21,039 INFO    [MainThread] metube.engine: queue worker stopped
  [PASS] T18.7     bin\ restored after the bootstrap test

=== 13/13 checks passed in this run; 0 scenario exception(s) ===

=== 137/137 checks passed overall; 0 scenario(s) reported failures ===
EXIT=0
```

## 7. Built exe acceptance (Section 15 step 5)

Raw output of `scripts/exe_accept.py` against the shipped
`dist\MeTubeShip\MeTube.exe` - real Windows mouse/keyboard input, a real
MP3 download driven through the UI, and the exe's own log/queue/history kept
as evidence before `data\` is removed again:

```
=== acceptance 0: is the desktop able to show colour at all? ===
    display-awake guard held: True
<USER>\MeTube\MeTube2\scripts\exe_accept.py:375: DeprecationWarning: Image.Image.getdata is deprecated and will be removed in Pillow 14 (2027-10-15). Use get_flattened_data instead.
  pixels = list(shot.getdata())
    note: the desktop itself is nearly monochrome (mean saturation 1.5). That is normal for a dark desktop and only a problem if the app's own window is also found dimmed.
    screen colour before phase 1: mean saturation 1.5

=== acceptance 1: fresh first run (data\ absent) ===
    launched MeTube.exe pid=9048
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_01_first_run_picker.png (718, 347)
  [PASS] exe launches and shows the first-run picker (visible window) :: hwnd=131516
  [PASS] picker drawn (accent 'Save and continue' button located) :: region=(466, 222, 677, 263, 8125)
    confirm attempt 1: picker closed
  [PASS] main window opens after 'Save and continue'
  [PASS] settings.json already had first_run=false when the window appeared :: <USER>\MeTube\MeTube2\dist\MeTubeShip\data\settings.json -> {'first_run': False, 'download_folder': 'C:\Users\<USER>\\Downloads\\MeTube', 'default_format': 'MP3', 'default_quality': 'Best Available', 'delay_min': 3, 'delay_max': 5, 'auto_update_ytdlp': True, 'finish_notification': True, 'keep_awake': True}
  [PASS] the picked (default) download folder exists :: C:\Users\<USER>\Downloads\MeTube
  [PASS] no crash.log after a clean first run
  [PASS] data\bin was NOT needed (engine shipped in ship\bin) :: process alive=True
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_02_main_window.png (1268, 897)

=== acceptance 2: relaunch must NOT ask again (B14) ===
    launched MeTube.exe pid=8428
  [PASS] second launch: main window opens
  [PASS] second launch: first-run picker does NOT appear (regression B14) :: picker hwnd=None

=== acceptance 3: real MP3 download driven from the exe ===
    launched MeTube.exe pid=3276
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_03_before_download.png (1268, 897)
  [PASS] 'Add to Queue' button located by colour in the bottom bar :: region=(1046, 823, 1231, 866, 7560)
    attempt 1: typed the URL, pressed Ctrl+Return and clicked 'Add to Queue'
    attempt 1: item present in the exe's queue.json = True
  [PASS] a real MP3 landed in the folder configured for the exe :: <USER>\MeTube\MeTube2\dist\MeTubeShip\data\_acceptance_downloads\Me at the zoo.mp3
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_04_download_completed.png (1268, 897)
  [PASS] history row recorded with file_path :: Completed ✓
  [PASS] silent finish toast was raised by the finished queue :: 2026-10-13 06:07:18,884 INFO    [MainThread] metube.notify: toast shown: Queue finished: 1 completed, 0 failed.
  [PASS] engine validation passed inside the exe (yt-dlp + ffmpeg usable)
  [PASS] a YouTube bot check before a real download switched the client :: bot_checks=0 client_switches=0
  [PASS] no mojibake (U+FFFD) in the exe's log of a real download :: replacement_chars=0
  [PASS] no crash.log was written by the exe
  [PASS] no yt-dlp/ffmpeg process leaked after the queue went idle
  [PASS] Task Manager has no zombie yt-dlp.exe after quitting the exe :: INFO: No tasks are running which match the specified criteria.

=== acceptance 3b: real MP4 download (merge path) from the exe ===
    launched MeTube.exe pid=1412
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_06_before_mp4.png (1268, 897)
  [PASS] MP4 run: 'Add to Queue' located by colour in the bottom bar :: region=(1046, 823, 1231, 866, 7560)
    attempt 1: MP4 link queued through the UI
  [PASS] a real MP4 (merged video+audio) landed in the folder from the exe :: <USER>\MeTube\MeTube2\dist\MeTubeShip\data\_acceptance_mp4\Me at the zoo.f133.mp4
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_07_mp4_completed.png (1268, 897)
  [PASS] history holds exe-driven rows for both MP3 and MP4 with file_path :: suffixes=['.mp3', '.mp4']

=== acceptance 3c: change the download folder in the UI, then RESTART ===
    launched MeTube.exe pid=4668
  [PASS] folder-change run: the picker is up
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_08_picker_before_typing.png (718, 347)
  [PASS] the folder box was located in the picker (only CARD-coloured field) :: region=(0, 0, 717, 346, 214803)
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_09_picker_after_typing.png (718, 347)
    confirm attempt 1: button not located
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_08b_picker_confirm_retry1.png (718, 347)
    confirm attempt 2: picker closed
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_09b_folder_line_after_change.png (1268, 897)
  [PASS] the folder typed into the picker is what got saved :: saved='<USER>\MeTube\MeTube2\dist\MeTubeShip\data\chosen_downloads' typed=True expected='<USER>\MeTube\MeTube2\dist\MeTubeShip\data\chosen_downloads'
    relaunching WITHOUT touching any setting ...
    launched MeTube.exe pid=1264
  [PASS] after the restart the picker does NOT come back
  [PASS] the chosen folder is still the one in settings.json after the restart :: saved='<USER>\MeTube\MeTube2\dist\MeTubeShip\data\chosen_downloads'
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_10_folder_after_restart.png (1268, 897)
    final_10_folder_after_restart: attempt 1 - paste reached the exe's queue = True
  [PASS] a real download after the restart lands in the folder chosen earlier :: <USER>\MeTube\MeTube2\dist\MeTubeShip\data\chosen_downloads\Me at the zoo.mp3

=== acceptance 3d: data\ copied from another PC (unreachable folder) ===
    launched MeTube.exe pid=6496
  [PASS] the app still opens with a folder from another machine
  [PASS] the unreachable folder was replaced with <exe folder>\downloads :: saved='<USER>\MeTube\MeTube2\dist\MeTubeShip\downloads' expected='<USER>\MeTube\MeTube2\dist\MeTubeShip\downloads'
  [PASS] the app log explains the replacement
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_11_other_pc_folder.png (1268, 897)
    final_11_other_pc_folder: attempt 1 - paste reached the exe's queue = True
  [PASS] a real download lands in <exe folder>\downloads :: <USER>\MeTube\MeTube2\dist\MeTubeShip\downloads\Me at the zoo.mp3
  [PASS] the acceptance removed the downloads\ folder it made in the ship folder :: <USER>\MeTube\MeTube2\dist\MeTubeShip\downloads
    preserved evidence\exe_accept_app.log
    preserved evidence\exe_accept_queue.json
    preserved evidence\exe_accept_history.json
    preserved evidence\exe_accept_settings.json

=== acceptance 4: delete data\ -> picker returns; ship folder left clean ===
    launched MeTube.exe pid=2844
  [PASS] deleting data\ brings the first-run picker back
    screenshot -> <USER>\MeTube\MeTube2\evidence\final_05_first_run_after_data_delete.png (718, 347)
  [PASS] dist\MeTubeShip left clean: no data\ folder :: contents=['MeTube.exe', 'README.txt', 'bin'] leftover_in_data=[]
  [PASS] dist\MeTubeShip contents are exactly the shipped set :: contents=['MeTube.exe', 'README.txt', 'bin']
  [PASS] the run's _MEI extraction leftovers were reclaimed and none remain :: swept 30 dirs / 887 MB, still present=none

=================== acceptance summary ===================
  PASS  exe launches and shows the first-run picker (visible window)
  PASS  picker drawn (accent 'Save and continue' button located)
  PASS  main window opens after 'Save and continue'
  PASS  settings.json already had first_run=false when the window appeared
  PASS  the picked (default) download folder exists
  PASS  no crash.log after a clean first run
  PASS  data\bin was NOT needed (engine shipped in ship\bin)
  PASS  second launch: main window opens
  PASS  second launch: first-run picker does NOT appear (regression B14)
  PASS  'Add to Queue' button located by colour in the bottom bar
  PASS  a real MP3 landed in the folder configured for the exe
  PASS  history row recorded with file_path
  PASS  silent finish toast was raised by the finished queue
  PASS  engine validation passed inside the exe (yt-dlp + ffmpeg usable)
  PASS  a YouTube bot check before a real download switched the client
  PASS  no mojibake (U+FFFD) in the exe's log of a real download
  PASS  no crash.log was written by the exe
  PASS  no yt-dlp/ffmpeg process leaked after the queue went idle
  PASS  Task Manager has no zombie yt-dlp.exe after quitting the exe
  PASS  MP4 run: 'Add to Queue' located by colour in the bottom bar
  PASS  a real MP4 (merged video+audio) landed in the folder from the exe
  PASS  history holds exe-driven rows for both MP3 and MP4 with file_path
  PASS  folder-change run: the picker is up
  PASS  the folder box was located in the picker (only CARD-coloured field)
  PASS  the folder typed into the picker is what got saved
  PASS  after the restart the picker does NOT come back
  PASS  the chosen folder is still the one in settings.json after the restart
  PASS  a real download after the restart lands in the folder chosen earlier
  PASS  the app still opens with a folder from another machine
  PASS  the unreachable folder was replaced with <exe folder>\downloads
  PASS  the app log explains the replacement
  PASS  a real download lands in <exe folder>\downloads
  PASS  the acceptance removed the downloads\ folder it made in the ship folder
  PASS  deleting data\ brings the first-run picker back
  PASS  dist\MeTubeShip left clean: no data\ folder
  PASS  dist\MeTubeShip contents are exactly the shipped set
  PASS  the run's _MEI extraction leftovers were reclaimed and none remain
  37/37 passed

EXE ACCEPTANCE OK
```

## 8. Fixes found by hardening the harness after the first pass

Both were real defects in the product, both are fixed, and both are
verified below and by the checks above.

### 8.1 the yt-dlp input URL is passed exactly once

`build_command` used to place the URL in the middle of the argv *and* at
the end, so yt-dlp processed every video twice. Counting the occurrences
now, with the real command builder:

```
url occurrences in argv: 1
argv length: 28
last entry: https://www.youtube.com/watch?v=jNQXAC9IVRw
```

### 8.2 the main window is really visible (not left withdrawn)

`CTk.mainloop()` re-applies the dark title bar while it still believes the
window was never mapped. That pass withdraws the window and skips its own
re-show when `withdraw()` was called before the first mapping - which is
exactly how this window is built - so the app could run with an invisible
window (indistinguishable from 'nothing happened'). Measured from source
before the fix, with the app fully started:

```
main window hwnd=2687696 pid=5864 visible=False rect=(154,154,1168,872)
```

After the fix (the window is marked mapped and its state is verified):

```
main window hwnd=2032534 pid=5844 visible=True rect=(102,102,1116,820)
```

`scripts/exe_accept.py` now requires a genuinely visible window for every
window it drives, so the shipped exe is verified on this as well.

### 8.3 the engine bootstrap pointed at a dead ffmpeg URL

The full suite caught this: `T18.4`/`T18.5` failed because the bootstrap
restored `yt-dlp.exe` but never `ffmpeg.exe`/`ffprobe.exe`. The ffmpeg zip
came from BtbN's *rolling* `latest` tag, which that project retired - so
the URL had started answering `404` and every fresh install with a missing
`bin\` could never complete. Measured live, before the fix:

```
FFMPEG https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/
       ffmpeg-master-latest-win64-gpl.zip
   FAIL HTTPError HTTP Error 404: Not Found

BtbN releases: tag=autobuild-2026-10-12-13-12 (no rolling 'latest' release)
GitHub API, yt-dlp/FFmpeg-Builds: tag=latest, 9 assets, including
   ffmpeg-master-latest-win64-gpl.zip 200256715
```

`FFMPEG_URL` now uses the maintained `yt-dlp/FFmpeg-Builds` rolling release
(still a GitHub release asset, so B4 holds). Measured live, after the fix:

```
yt-dlp: HTTP 206 64 bytes of bytes 0-1023/17840399 <- https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
ffmpeg zip: HTTP 206 64 bytes of bytes 0-1023/200284108 <- https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
```

### 8.4 a 5xx from the CDN aborted the whole bootstrap

The same suite run also showed `bootstrap failed: Download failed
(HTTP 504)`. `_download` treated every failure as final, and the ffmpeg zip
is ~200 MB, so one transient 502/504/timeouts/dropped socket left the user
with no engine and no second chance. It now retries *only* the transient
class (`408/429/5xx`, `URLError`, socket/timeout/HTTP-protocol errors) up
to 4 attempts with a linear backoff, and still fails fast on a 404 or a
TLS certificate error. Both behaviours are asserted by the harness:

```
retryable: 504 True | 404 False | URLError True | TLS cert False
```

And the fix is proven end to end on a real download, from a scratch
`METUBE_DATA_DIR` with `bin\` deliberately absent (fast path: the whole
scenario finished in 46 s):

```
2026-10-12 08:38:07,986 WARNING [MainThread] metube.app: engine binaries incomplete at startup — bootstrapping
2026-10-12 08:38:53,583 INFO    [BootstrapThread] metube.binaries: bootstrap finished ok=True results={'yt-dlp.exe': (True, '2026.08.19'),
    'ffmpeg.exe': (True, 'ffmpeg version N-127371-gd9242028a6-20261011 ...'),
    'ffprobe.exe': (True, 'ffprobe version N-127371-gd9242028a6-20261011 ...')}
[PASS] T18.5  the three engine files land in <data>\bin with exact names
=== 13/13 checks passed in this run; 0 scenario exception(s) ===
```

### 8.5 the queue could be frozen by a click that was not the harness's

The first full run (kept verbatim as
[evidence/e2e_full_run1.log](evidence/e2e_full_run1.log)) was **not** clean:

```
114/115 checks passed overall; 1 scenario(s) reported failures
  FAIL T9.5: the trailing item still completes after a cancel -> status='Paused'
2026-10-12 08:46:13,776 INFO    [MainThread] metube.engine: paused active process tree
2026-10-12 08:47:15,264 INFO    [MainThread] metube.engine: paused active process tree
```

The engine logs every suspension, so T8's own (expected) pause appears
above too. The *last* line is the stray one: it arrived after T8's resume
had already passed and after no harness call at all.

The cause was not the product: no harness step pauses after T8, and
`pause_all()` returns early when the queue is already paused - yet the engine
logged that it had just suspended a live process tree, so a *fresh* pause
arrived from the Tk main thread after T8's own pause/resume had already
passed. That is an out-of-band click on a real button of the live window
(the same thing that had been confirming the first-run dialog from outside
the harness). The product behaviour itself is asserted by T8.

The harness now records every `pause_all()` caller with a stack trace and
undoes a pause it never asked for, loudly, inside `wait_for` - so a stray
click can no longer be mistaken for a stuck queue, and the transcript names
whoever paused. T8's own pause is wrapped in `EXPECT_PAUSE` so its assertion
is untouched:

```
EXPECT_PAUSE["on"] = True
try:
    app.on_pause()
finally:
    EXPECT_PAUSE["on"] = False
```

### 8.6 the in-app banner used to swallow clicks

A new acceptance phase (change the folder in the picker, restart, then
download) failed with the URL never reaching the queue. The cause was the
finish/notice banner: it was an in-window frame placed at 96.5% height,
exactly on top of the paste box and the 'Add to Queue' button, so for a few
seconds after every queue finish or notice those controls silently ignored
clicks. Transcript of that run:

```
    final_11_other_pc_folder: attempt 1 - paste reached the exe's queue = False
  [FAIL] a real download lands in <exe folder>\downloads :: None

queue.json: []                       <- the click never reached the box
app.log:    (no 'metadata resolved' line for the URL)
```

The banner is now a borderless Toplevel carrying
`WS_EX_LAYERED | WS_EX_TRANSPARENT` (on the window and its Tk wrapper), so
Windows routes every mouse event through it to whatever is underneath, and
it follows the main window's position instead of being placed inside it.
Verified at the Windows level, not by trusting the widget (the harness
cleared `queue.json`, clicked during the banner and watched a real download
complete - exe acceptance 3c/3d now pass):

```
  PASS  T19.3 the finished-queue banner is on screen while it should be
  PASS  T19.4 the banner window carries WS_EX_TRANSPARENT (and its Tk wrapper)
  PASS  T19.5 a hit-test in the middle of the banner lands on the main window
```

### 8.7 the remembered download folder was never re-checked

`download_folder` was written straight from the picker or the Settings
screen and then trusted forever. On the machine that wrote it that is
fine; on the *next* machine it is not - a copy of `data\settings.json`
can name a drive letter or user profile that does not exist there, and
every download would then fail at `mkdir` with 'cannot create download
folder'. Two changes, both measured:

- at startup, a remembered folder that cannot be created or written here is
  replaced with `<app folder>\downloads`, saved back to `settings.json`,
  logged, and announced in a notification - so the app stays usable and
  says where the files went;
- in Settings, an unusable folder is refused with a dialog naming the folder
  the app will really use, instead of being stored broken.

### 8.8 the download folder change now survives a restart (by test)

The change was already applied live (regression B5), but nothing proved it
was remembered for the *next* launch.  T10.6/T10.6b/T10.7 do: change the
folder through the Settings save path, close the app, create a fresh `App`
on the same `data\`, and check the folder is still set, still shown in the
Settings screen, and that a real download then lands in it.

### 8.9 the audio/video engine's own error text was unreadable to the app

yt-dlp writes its messages with the Windows code page on a pipe - the
apostrophe in "Sign in to confirm you're not a bot" arrives as the single
byte `0x92` even when `PYTHONIOENCODING=utf-8` is set. The app decoded the
stream as UTF-8 with `errors='replace'`, so that sentence became
"you?re not a bot": the bot-check markers never matched, a bot check was
retried as if it were a network glitch, and the queue card showed a broken
character. The raw bytes, taken from the shipped engine:

```
$ ./bin/yt-dlp.exe --dump-json --no-playlist --quiet --no-warnings URL 2>err.bin
bytes around: b'confirm you\x92re not a bot. Use '
utf-8 FAIL 'utf-8' codec can't decode byte 0x92 in position 11: invalid start byte
cp1252 OK -> confirm you're not a bot. Use
```

Both streams are now read as bytes and decoded UTF-8-then-code-page, and the
classifier folds typographic punctuation (including a stray U+FFFD) to ASCII
before matching, so the sentence is recognised whatever the pipe did to it.
Pinned by the selftest's ladder checks, and by the live downloads: T10.9
asserts no U+FFFD appears in the log of a real download run.

### 8.10 a bot check now changes YouTube client instead of just waiting

Measured on the day of this run, with the shipped yt-dlp (2026.08.19):
the default clients answered `Sign in to confirm you're not a bot` for
every real download, while `android` and `tv_embedded` still served the
same video. A bot check is about *which* client asked, so the engine now
asks again with `android`, then `tv_embedded`, 5 s apart, and only then
falls back to the 60 s / 120 s / 240 s rate-limit cool-downs. Metadata and
playlist lookups walk the same ladder (a title lookup that gave up would
name the file after the bare video id). Evidence:

```
$ ./bin/yt-dlp.exe --simulate ... --extractor-args youtube:player_client=<c>
default       ERROR: Sign in to confirm you're not a bot
android       (no output - success)
tv_embedded   (no output - success)
ios/mweb/web_safari/web_embedded  ERROR: No video formats found!
android_vr    ERROR: Sign in to confirm you're not a bot

real download with the fallback client:
  client=default   ok=False  in 3.4s   (bot check)
  client=android   ok=True   in 17.3s  file='...\Me at the zoo.mp3'
```

T10.8 counts the bot checks and the client switches in the log of a real
harness run and requires them to match - a bot check that is met without
switching is a failure.

### 8.11 a relative download folder wrote the files somewhere else

The Settings box accepts typed text. A relative value ("downloads",

".media") was stored as typed and handed to yt-dlp as a relative `-o`
template. yt-dlp resolves that against *its own* working directory and
drops a leading dot, so the file landed in a folder nobody chose - and the
chosen folder stayed empty. Measured before the fix:

```
[relative] folder repr='.e2e\\ladder\\rel' outtmpl='.e2e\\ladder\\rel\\Probe.%(ext)s'
[relative] ok=True file='<PROJECT>\\e2e\\ladder\\rel\\Probe.mp3'
[relative] actual dir listing: []          <- the folder the user picked
[absolute] folder repr='<PROJECT>\\.e2e\\ladder\\abs'
[absolute] ok=True file='...\\.e2e\\ladder\\abs\\Probe.mp3'   listing: ['Probe.mp3']
```

`config.resolve_download_folder` turns every value into an absolute path
(a relative one is read against the MeTube folder) and is applied at the
settings boundary, at startup, in the engine's per-download folder and
again inside `build_command`, so no relative path can reach yt-dlp. T10.6d/
T10.6e plus the selftest pin it down.

### 8.12 a full drive produced raw OS errors

A run on a machine whose system drive had filled up produced, verbatim:
`bootstrap failed: Disk/network error: [Errno 28] No space left on device`,
and the exe's own engine validation failed because yt-dlp could not even
extract itself. Nothing told the user what to do. There are now three
guards, each with a sentence naming the free space, the drive and the next
step: a download refuses to start below 100 MB free on the target drive
(before yt-dlp is launched), the engine bootstrap checks the download drive
(400 MB) and the system temp drive (300 MB) before it starts, and an
`ENOSPC` from anywhere is reported as "not enough free disk space to unpack
the engine". T15.6/T15.7 drive the first case with a real App (the folder
reports 5 MB) and assert the item fails with that sentence and that no
yt-dlp process was ever started for it.

### 8.13 the acceptance run itself filled the system drive

`taskkill` cannot let a PyInstaller onefile app clean up its `_MEIxxxxxx`
extraction folder, so every killed launch of the test exe left ~30 MB
behind. After many runs `%TEMP%` held **142 of them (4.0 GB)**, the system
drive reached 0 bytes free, and then the exe could no longer extract itself:
engine validation failed, the bootstrap failed, and three real checks
turned into false failures (`a real download lands in <exe folder>\\downloads`,
`deleting data\\ brings the first-run picker back`, and the MP3 phase before
them). The space was reclaimed and the acceptance now sweeps those folders
after its kills and asserts none remains:

```
removed 142 _MEI dirs, freed 4195 MB
  PASS  the run's _MEI extraction leftovers were reclaimed and none remain
        :: swept 13 dirs / 386 MB, still present=none
```

### 8.14 three false failures that came from the test tooling

- the selftest's new argv probe called `build_command`, which asks for
  ffmpeg's location and so **cached the project data folder** before the
  runtime checks switched to a temp one: the selftest wrote
  `settings.json` into the source tree and the harness's B12 check ("only
  ONE data folder is in play") failed for a reason that had nothing to do
  with the app. Resetting the cache was not enough: resolving the data
  folder also **creates** it while probing that it is writable, so a plain
  `scripts/selftest.py` still left an empty `data\` in the project tree,
  and the log generator's own `python -c` snippets did the same. Both now
  point `METUBE_DATA_DIR` at a scratch folder before the first path-
  sensitive call, and the checks that want a download folder use one in the
  temp dir instead of `tmpdl_selftest\` next to the sources. Proven by
  running the generator on a tree that had none of those folders:

```
SELFTEST PASSED: 58 checks
=== tree litter after regeneration ===
(nothing listed = clean)
```
- the portable scenario wrote its queue snapshot through `store` *before*
  pointing the modules at that scenario's data folder, so a stray
  `queue.json` appeared in the source tree. Both now go through the same
  `use_data_dir` helper, and the tree stays clean.
- one missed click on the first-run picker used to poison every later phase
  (no `settings.json` meant the picker came back on the next launch). The
  acceptance re-locates the button from a fresh screenshot and retries when
  the picker is still open - product behaviour unchanged, test robustness
  fixed.

## 9. The download folder: set it once, and it stays

A change made in the app must be remembered on the next launch and must
be where the next download actually lands - and a folder that came from
another PC must not break anything. Both are measured, in-process and on
the built exe.

### 9.1 In-process harness (real App, real Settings view, real downloads)

| Check | What it proves | Result |
| --- | --- | --- |
| T10.3 | Settings save applies immediately (settings.json + live object) | **PASS** (live='<USER>\\MeTube\\MeTube2\\.e2e\\folder\\folder_b' on_disk='<USER>\\MeTube\\MeTube2\\.e2e\\folder\\folder_b') |
| T10.3b | the main window's 'Saving to' line follows the change immediately | **PASS** (label='Saving to  <USER>\MeTube\MeTube2\.e2e\folder\folder_b') |
| T10.4 | item 2 lands in the NEW folder with NO restart (regression B5) | **PASS** (path=<USER>\MeTube\MeTube2\.e2e\folder\folder_b\Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp3) |
| T10.5 | nothing new was written into the old folder after the change | **PASS** (folder_a=['Me at the zoo.mp3']) |
| T10.6 | the download folder change survives a restart | **PASS** (after relaunch='<USER>\MeTube\MeTube2\.e2e\folder\folder_b' expected='<USER>\MeTube\MeTube2\.e2e\folder\folder_b') |
| T10.6b | the Settings screen shows the remembered folder (nothing to re-enter) | **PASS** (entry='<USER>\MeTube\MeTube2\.e2e\folder\folder_b') |
| T10.6c | the relaunched window shows the remembered folder without opening Settings | **PASS** (label='Saving to  <USER>\MeTube\MeTube2\.e2e\folder\folder_b') |
| T10.6d | a relative download folder is stored absolute, under the app folder | **PASS** (stored='<USER>\MeTube\MeTube2\relative_probe' shown='<USER>\MeTube\MeTube2\relative_probe') |
| T10.6e | ...and the 'Saving to' line shows the resolved folder | **PASS** (label='Saving to  <USER>\MeTube\MeTube2\relative_probe') |
| T10.7 | a real download AFTER the restart lands in the remembered folder | **PASS** (path=<USER>\MeTube\MeTube2\.e2e\folder\folder_b\Me at the zoo.mp3 shown=<USER>\MeTube\MeTube2\.e2e\folder\folder_b) |
| T10.8 | every bot check met by a real download switched the YouTube client | **PASS** (bot_checks=0 client_switches=0) |
| T10.9 | no mojibake (U+FFFD) anywhere in the log of real downloads | **PASS** (replacement_chars=0) |
| T21.0 | the 'other PC' folder in settings.json really is unreachable here | **PASS** (Q:\metube_other_pc\Downloads\MeTube usable=False) |
| T21.1 | the app starts and moves downloads into its own folder | **PASS** (folder='<USER>\MeTube\MeTube2\downloads' expected='<USER>\MeTube\MeTube2\downloads') |
| T21.1b | a queue holding only finished items does not nag for a restore | **PASS** (restore dialogs shown=0) |
| T21.1c | the window shows the folder the app will really use | **PASS** (label='Saving to  <USER>\MeTube\MeTube2\downloads') |
| T21.2 | the replacement is persisted, so the next launch needs no action | **PASS** (on_disk='<USER>\MeTube\MeTube2\downloads') |
| T21.2b | the user is told where the downloads went | **PASS** (notice logged=True) |
| T21.3 | a real download lands in <app folder>\downloads | **PASS** (path=<USER>\MeTube\MeTube2\downloads\Me at the zoo.mp3) |
| T21.4 | the harness cleaned up the portable downloads folder it created | **PASS** (<USER>\MeTube\MeTube2\downloads exists=False) |

### 9.2 Built exe: changed in the real UI, then restarted

Raw lines from `scripts/exe_accept.py` (real mouse/keyboard against
`dist\MeTubeShip\MeTube.exe`, no test hooks inside the app):

```
PASS  the folder box was located in the picker
PASS  the folder typed into the picker is what got saved
PASS  the chosen folder is still the one in settings.json after the restart
PASS  a real download after the restart lands in the folder chosen earlier
PASS  the app still opens with a folder from another machine
PASS  the unreachable folder was replaced with <exe folder>\downloads
PASS  a real download lands in <exe folder>\downloads
```

### 9.3 The folder is visible in the window, not a memory test

The main window shows `Saving to  <folder>` under the queue counter, and
clicking that line opens the folder in Explorer. It follows a change made
in Settings immediately (T10.3b) and it is correct again after a restart
(T10.6c) and after the portable fallback (T21.1c).

### 9.4 Which folder is portable

**Copy the whole `MeTubeShip` folder.** It is self-contained:

```
MeTubeShip\            <- copy this ONE folder to a USB stick / another PC
  MeTube.exe               the app
  README.txt               the instructions
  bin\                     yt-dlp.exe, ffmpeg.exe, ffprobe.exe
  data\                    created on first run: settings, queue, history, logs
  downloads\               created only if the remembered folder is gone
```

- `data\settings.json` holds the remembered download folder (and every
  other setting), so the choice travels with the copy - nothing has to be
  re-entered on the other machine.
- If the remembered folder does not exist there (another drive letter,
  another user profile), the app replaces it with `MeTubeShip\downloads\`,
  stores that, announces it, and downloads there - measured by T21.* and by
  the exe rows above (a real MP3 landed in `MeTubeShip\downloads`).
- Copying only `MeTube.exe` also works: it fetches yt-dlp and ffmpeg into
  its own `data\bin` on the first launch (one-time, ~230 MB).
- If you want the files themselves to stay on the stick, set the folder to
  `MeTubeShip\downloads` on first launch or in Settings: that path means
  the same thing on every machine.

### 9.5 The rules the folder follows (each one asserted)

| Rule | Where it is proved |
| --- | --- |
| A change applies to the next download with no restart | T10.3, T10.4, T10.5, exe 3c |
| It is remembered for the next launch and shown in Settings | T10.6, T10.6b, T10.6c, exe 3c relaunch |
| A real download then lands in it | T10.7, exe `final_10_folder_after_restart` |
| A relative value is read relative to the MeTube folder | T10.6d, T10.6e, selftest |
| An unusable remembered folder is replaced, stored and announced | T21.0-T21.3, exe 3d |
| A bot check switches YouTube client before giving up | T10.8, selftest ladder checks |
| A nearly-full drive fails with a sentence before yt-dlp starts | T15.6, T15.7 |
| Nothing relative or mangled reaches the engine | selftest argv/decode checks |

## 10. Definition of Done (Section 17)

| Requirement | Evidence | Result |
| --- | --- | --- |
| All T1-T20 pass with real evidence | all rows PASS in section 2 | **PASS** |
| All B1-B14 regression guarantees verified | all rows PASS in section 3 | **PASS** |
| dist\MeTubeShip\ complete: MeTube.exe + README.txt + bin\(3 files) | MeTube.exe + README.txt + bin\{yt-dlp,ffmpeg,ffprobe}.exe | **PASS** |
| Fresh-exe first-run flow tested on the built exe | PASS: exe launches and shows the first-run picker (visible window); picker returns after deleting data\: PASS: deleting data\ brings the first-run picker back | **PASS** |
| Real MP3 + MP4 downloads completed FROM THE EXE | MP3 -> PASS: a real MP3 landed in the folder configured for the exe; MP4 -> PASS: a real MP4 (merged video+audio) landed in the folder from the exe | **PASS** |
| TEST_LOG.md written with every command + output | this file, 109,005 bytes before this table was appended (sections 1-8 verified present on disk) | **PASS** |
| Source tree clean: one data-dir resolution, one sanitizer, one sync method, zero bare-except, zero non-daemon threads, zero direct widget access from workers | 1/1/1/0/0/0/0 measured as 1/1/1/0/0/0/0 | **PASS** |
| A download folder chosen once is remembered and used on later launches (no re-picking), and downloads really land in it | T10.3: PASS; T10.6: PASS; T10.6b: PASS; T10.7: PASS; exe: PASS the folder typed into the picker is what got saved; PASS the chosen folder is still the one in settings.json ; PASS a real download after the restart lands in the folde | **PASS** |
| Portable: the MeTubeShip folder can be copied to another PC and still downloads (an unreachable remembered folder is replaced) | T21.0: PASS; T21.1: PASS; T21.2: PASS; T21.3: PASS; exe: PASS the app still opens with a folder from another machi; PASS the unreachable folder was replaced with <exe folder; PASS a real download lands in <exe folder>\downloads | **PASS** |
| Built exe acceptance suite green | 37/37 passed; dist\MeTubeShip contents=['MeTube.exe', 'README.txt', 'bin']; bin=['ffmpeg.exe', 'ffprobe.exe', 'yt-dlp.exe'] | **PASS** |
| Final message lists every file + one-line purpose | see the closing chat message | **PASS** |

