================================================================================
 MeTube 2.0
 A small, dark-themed Windows desktop app for downloading YouTube links
 as MP3, M4A or MP4 - one at a time, into the folder you choose.
================================================================================

WHAT IT IS
----------
Paste one or many YouTube links (commas, newlines or semicolons between them),
pick a format, and MeTube downloads them one by one with randomised delays,
retries, and per-item pause / cancel / retry.

  - Formats: MP3 (320K), M4A, MP4 (Best Available / 360p / 480p / 720p /
    1080p / 1440p / 2160p; MP4 falls back to the nearest lower quality that
    actually exists, and never fails just because your pick was unavailable).
  - Audio files get an embedded cover picture and title/artist tags.
  - A history panel, a full settings screen, and a silent Windows notification
    when the whole queue finishes.
  - No accounts, no telemetry, no uploads. Everything stays on your PC.
  - The remembered download folder is shown in the main window right under the
    queue counter ("Saving to  <folder>") - click it to open that folder.

MeTube is a personal-use tool. See the note at the very bottom.


FIRST LAUNCH
------------
1. Keep the whole folder together (MeTube.exe AND the bin\ folder next to it).
2. Double-click MeTube.exe.
   - Windows SmartScreen may say "Windows protected your PC" because the app is
     not code-signed. Click "More info", then "Run anyway". See below.
3. A small window asks: "Choose where your downloads will be saved".
   Browse to a folder (or just press "Use default", which is
   %USERPROFILE%\Downloads\MeTube) and click "Save and continue".
4. That is it - the folder is remembered. The picker never appears again
   unless you use Settings -> Reset settings. The main window shows the folder
   it uses under the queue counter ("Saving to  <folder>"); click that line to
   open the folder in Explorer.
5. Paste your links in the box at the bottom and press "Add to Queue"
   (or Ctrl+Enter).


SMARTSCREEN AND ANTIVIRUS
-------------------------
SmartScreen, first run:
  1. The blue "Windows protected your PC" box appears.
  2. Click the underlined "More info" text.
  3. Click the "Run anyway" button that appears.

Why it happens: the .exe is not code-signed (a certificate costs money and this
is a personal-use tool), so Windows cannot verify its publisher. The message
does not mean anything was detected.

If your antivirus quarantines the app or the engine files, add the MeTube
folder as an exclusion, e.g.:
  Windows Security -> Virus & threat protection -> Manage settings ->
  Exclusions -> Add or remove exclusions -> Add an exclusion -> Folder ->
  select the MeTubeShip folder.
Third-party suites use the same idea (exclusions / trusted folder).

A PyInstaller-built executable unpacking itself to a temporary folder is a
common (and harmless) heuristic trigger. yt-dlp.exe and ffmpeg.exe are the
official upstream builds - see the URLs below if you want to verify them.


THE ENGINE FILES (do not rename these)
-------------------------------------
MeTube does not bundle the download engine inside the .exe; it looks for three
files in a folder named "bin" that sits directly next to MeTube.exe:

  MeTubeShip\
    MeTube.exe
    README.txt
    bin\
      yt-dlp.exe      <- EXACT name, lowercase, no suffix
      ffmpeg.exe      <- EXACT name
      ffprobe.exe     <- EXACT name
    data\            created on first run: settings, queue, history, logs

Names matter. "yt-dlp (1).exe", "FFMPEG.EXE" or "yt-dlp.exe.txt" will not be
found.

Where they come from (GitHub only):
  yt-dlp:  https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
  ffmpeg:  https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/
           ffmpeg-master-latest-win64-gpl.zip
           (the zip nests the files inside ffmpeg-master-latest-win64-gpl\bin\
            - copy ffmpeg.exe and ffprobe.exe out of it)

Resolution order: MeTube first looks in <folder of MeTube.exe>\bin, then in
<data folder>\bin. If neither has all three files, it downloads them into
<data folder>\bin by itself (the "Add to Queue" button shows
"Preparing engine..." while it does). If that download fails, MeTube shows you
these same instructions and keeps working otherwise.


MOVING IT TO ANOTHER PC
-----------------------
The whole "MeTubeShip" folder is portable. Copy that one folder and everything
works on the new machine:

  MeTubeShip\            <-- copy this folder, and nothing else is needed
    MeTube.exe               the app
    README.txt               this file
    bin\                     yt-dlp.exe, ffmpeg.exe, ffprobe.exe (the engine)
    data\                    created on first run: your settings + history
    downloads\               created only if the remembered folder is gone
                             (see below) - not normally present

  - Fresh PC, no data\ yet: copy MeTubeShip anywhere (desktop, USB stick,
    D:\Apps\MeTubeShip) and double-click MeTube.exe. It asks once for a download
    folder and remembers it from then on - no per-launch setup.
  - Copy ONLY MeTube.exe -> the app still runs, but on first launch it will
    fetch yt-dlp and ffmpeg into its data folder by itself (one-time, ~230 MB).
    If that is blocked by a firewall, either allow it or create the bin\ folder
    and drop the three files in manually.
  - Keeping data\ inside the copied folder means your settings (including the
    download folder), queue and history travel with it.
  - If you want the files themselves to stay on the stick (or in the copied
    folder) instead of landing on the other PC, set the download folder to
    MeTubeShip\downloads on first launch or in Settings. That path means the
    same thing on every machine, so it never needs re-picking.
  - A download folder you chose on the old PC may not exist on the new one
    (another drive letter, another user profile). MeTube notices at startup,
    moves downloads into MeTubeShip\downloads\ automatically, keeps that choice
    in settings.json, and tells you in a notification and in data\logs\app.log.
    Nothing fails and nothing has to be re-entered.
  - Delete data\ before copying if you want the new machine to start clean and
    ask for a folder again.


WHERE YOUR DATA LIVES
---------------------
Next to the exe:

  data\settings.json      your settings (download folder, format, delays...)
  data\queue.json         queue snapshot, used to offer a restore after a crash
  data\history.json       your download history
  data\thumbs\            cached thumbnails
  data\logs\app.log       rolling application log (1 MB x 5)
  data\logs\crash.log     written only if the app ever hits an unhandled error
  data\bin\               engine files downloaded at runtime (if needed)

If the folder containing MeTube.exe is not writable (e.g. you put it in
Program Files), MeTube falls back to %APPDATA%\MeTube\ and says so in the log.

MeTubeShip\downloads\ is created only when your remembered download folder is
not usable on this machine (see the portability section above).


TROUBLESHOOTING
---------------
| Symptom                              | What to do                          |
|--------------------------------------|-------------------------------------|
| "Add to Queue" says "Preparing       | Let it finish. If it stays like     |
| engine..." forever                   | that, create bin\ next to           |
|                                      | MeTube.exe with yt-dlp.exe,         |
|                                      | ffmpeg.exe and ffprobe.exe in it,   |
|                                      | then restart MeTube.                |
|                                      |                                     |
| Item fails: "Sign in to confirm      | YouTube's bot check, usually after  |
| you're not a bot" / "HTTP 429"       | too many downloads. MeTube asks     |
|                                      | again with a different YouTube      |
|                                      | client after 5s, and if that does   |
|                                      | not help it cools down (60s / 120s  |
|                                      | / 240s) and retries automatically.  |
|                                      | If it still fails, wait a while and |
|                                      | press Retry.                        |
|                                      |                                     |
| Nothing downloads at all             | Check your internet, then press     |
|                                      | Retry on the item. Keep yt-dlp up   |
|                                      | to date (Settings -> Check for      |
|                                      | yt-dlp update now).                 |
|                                      |                                     |
| "Unable to download video data:      | Transient YouTube hiccup. MeTube    |
| HTTP Error 403"                      | retries automatically (15s, 30s).   |
|                                      |                                     |
| MP4 conversion fails /              | bin\ffmpeg.exe or bin\ffprobe.exe   |
| "Postprocessing: Error"              | is missing or damaged. Settings ->  |
|                                      | "Re-download components".           |
|                                      |                                     |
| Files land in the wrong folder       | Settings -> Download folder ->      |
|                                      | Browse -> Save. A change applies to |
|                                      | the next item straight away, and is |
|                                      | remembered for every later launch;  |
|                                      | no restart needed. A relative path  |
|                                      | you type (e.g. "downloads") is read |
|                                      | relative to the MeTube folder.      |
|                                      |                                     |
| After moving MeTube to another PC    | Only happens when the saved folder  |
| the downloads go somewhere else      | does not exist there: MeTube says   |
| (or a "Saved download folder is      | so in a notification and uses       |
| unavailable" notification appears)   | MeTubeShip\downloads\. Pick a new   |
|                                      | folder in Settings if you prefer.   |
|                                      |                                     |
| "Failed: not enough free disk space"  | The drive you download to (or the   |
|                                      | drive holding %TEMP%) is nearly     |
|                                      | full. Free some space and press     |
|                                      | Retry on the item. MeTube checks    |
|                                      | this before it starts, so nothing   |
|                                      | half-downloads.                     |
|                                      |                                     |
| The app vanishes on startup          | Open data\logs\crash.log - it holds |
|                                      | the full traceback. Also check      |
|                                      | data\logs\app.log.                  |
|                                      |                                     |
| The queue looks stuck                | Open data\logs\app.log. Each        |
|                                      | download logs its start, the folder |
|                                      | it uses and its outcome.            |
|                                      |                                     |
| Quality dropdown is greyed out       | That is deliberate: quality only    |
|                                      | applies to MP4. Switch the format   |
|                                      | to MP4 and it becomes available.    |
|                                      |                                     |
| Second launch does nothing new       | MeTube is single-instance: the      |
|                                      | already-running window is brought   |
|                                      | to the front instead.               |
|                                      |                                     |
| Playlist URL added only one item     | A link with ?v=...&list=... is a    |
|                                      | single video by design. Paste the   |
|                                      | pure playlist URL (only ?list=...)  |
|                                      | to expand it into all its videos.   |

Tip: Settings -> "Open logs folder" jumps straight to data\logs.


PERSONAL USE
------------
MeTube is a personal-use tool and does not include any content. Downloading
material you do not have the right to download may violate YouTube's Terms of
Service and/or the rights of the copyright holder. Use it for content you are
allowed to save (your own uploads, public-domain material, Creative Commons
material, or wherever the rights holder permits it). You are responsible for
how you use it. MeTube has no accounts, no analytics and sends nothing but the
requests required to fetch the videos you ask for.

Engine components and their licences:
  yt-dlp            - Unlicense (public domain)
  FFmpeg / FFprobe  - LGPL/GPL, see the FFmpeg project for details
  MeTube itself     - personal use
================================================================================
