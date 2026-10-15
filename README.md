# MeTube

A small, dark-themed Windows app for downloading YouTube links as MP3, M4A or MP4 — one at a time, into the folder you choose.

## Download

Go to the [Releases page](https://github.com/avinabasarker/MeTube/releases/latest) and download `MeTubeShip.zip`. No installation, no account.

- Extract the **whole folder** somewhere (Desktop, `D:\Apps`, a USB stick — not Program Files). Keep `MeTube.exe` and the `bin\` folder together
- Double-click `MeTube.exe`
- Requires Windows 10/11 (64-bit) and an internet connection

**Note:** Windows SmartScreen will show a blue "Windows protected your PC" screen on first run, because the app is not code-signed. Click **More info → Run anyway**. This is normal for unsigned apps and does not mean anything was detected. If your antivirus complains, add the MeTube folder as an exclusion.

## What it does

Paste one or many YouTube links (commas, newlines or semicolons between them), pick a format, and MeTube downloads them one by one with randomised delays, retries, and per-item pause / cancel / retry.

- Formats: MP3 (320 kbps), M4A, MP4 (Best Available / 360p / 480p / 720p / 1080p / 1440p / 2160p). If the picked quality doesn't exist, MP4 falls back to the nearest lower quality instead of failing
- Audio files get an embedded cover picture and title/artist tags
- Bulk paste, automatic playlist expansion, silent duplicate skipping
- History panel, full settings screen, silent Windows notification when the queue finishes
- No accounts, no telemetry, no uploads — everything stays on your PC

## First launch

A small window asks where your downloads should be saved. Browse to a folder or press **Use default** (`Downloads\MeTube`), then **Save and continue**. That's it — the folder is remembered and the picker never appears again unless you use **Settings → Reset settings**.

The main window shows the folder it's using under the queue counter ("Saving to <folder>") — click it to open the folder in Explorer.

## Using MeTube

1. Paste links into the box at the bottom — commas, newlines or semicolons, any mix
2. Pick a format (and quality, for MP4) at the top
3. Click **Add to Queue** (or press `Ctrl+Enter`)
4. Each card shows progress, speed and ETA. The countdown between downloads is the anti-bot delay, not a freeze
5. Completed cards get **Show in folder** and **Open file** buttons

Every card has its own **Pause / Resume / Cancel** while running and **Retry** after a failure. A failed item never blocks the rest of the queue.

Good to know:

- A link like `youtube.com/watch?v=X&list=Y` downloads only that video. Paste a pure playlist URL (`playlist?list=…`) to expand it into all its videos
- The same video pasted twice (even in different link formats) is added once
- Two different videos with the same title are auto-renamed: `Song.mp3`, `Song (1).mp3`, …
- The quality dropdown is greyed out for MP3/M4A — quality only applies to MP4
- Your PC is kept awake while a queue runs, so overnight downloads don't die to sleep mode
- Launching MeTube a second time just brings the running window to the front

## Moving it to another PC

Copy the one `MeTubeShip` folder — that's all it takes. It works immediately on the new machine; it asks once for a download folder and remembers it.

- Copy only `MeTube.exe` instead? The app still runs and fetches the engine files into its data folder by itself on first launch (~230 MB, one time)
- Copy the folder *with* `data\` if you want settings, queue and history to travel too. If the remembered download folder doesn't exist on the new machine, MeTube notices, switches to `MeTubeShip\downloads\`, saves that choice and tells you — nothing fails
- Delete `data\` before copying if you want the new machine to start clean

## Where your data lives

Everything MeTube remembers sits next to the exe:

MeTubeShip
├─ MeTube.exe
├─ README.txt
├─ bin\ yt-dlp.exe · ffmpeg.exe · ffprobe.exe
└─ data\ created on first run
├─ settings.json your settings (download folder, format, delays…)
├─ queue.json queue snapshot (offers a restore after a crash)
├─ history.json download history
├─ thumbs\ cached thumbnails
├─ logs\app.log rolling application log
├─ logs\crash.log only written if the app ever hits an unhandled error
└─ bin\ engine files downloaded at runtime (if needed)



If the exe's folder isn't writable (e.g. Program Files), MeTube falls back to `%APPDATA%\MeTube\` and says so in the log.

## Troubleshooting

| Symptom | What to do |
|---|---|
| **"Add to Queue" stuck on "Preparing engine…"** | Create a `bin\` folder next to MeTube.exe containing `yt-dlp.exe`, `ffmpeg.exe`, `ffprobe.exe` (see below), then restart |
| **"Sign in to confirm you're not a bot" / HTTP 429** | YouTube's bot check, usually after many downloads. MeTube retries with a different client after 5 s, then cools down (60 s / 120 s / 240 s) automatically. Still failing? Wait a while, press **Retry** |
| **Nothing downloads at all** | Check your internet, press **Retry**, then update the engine: Settings → **Check for yt-dlp update now** |
| **"HTTP Error 403"** | Transient YouTube hiccup — MeTube retries automatically (15 s, 30 s) |
| **MP4 conversion fails / "Postprocessing: Error"** | `ffmpeg.exe` or `ffprobe.exe` is missing or damaged → Settings → **Re-download components** |
| **Files land in the wrong folder** | Settings → Download folder → Browse → Save. Applies from the next item, no restart needed |
| **After moving to another PC, downloads go somewhere else** | The remembered folder doesn't exist there — MeTube switched to `MeTubeShip\downloads\` and told you. Pick a new folder in Settings if you prefer |
| **"Not enough free disk space"** | The download drive (or `%TEMP%`) is nearly full. Free space, press **Retry** — nothing half-downloads |
| **The app vanishes on startup** | Open `data\logs\crash.log` — it contains the full error |
| **The queue looks stuck** | Open `data\logs\app.log` — every download logs its start, folder and outcome |
| **Quality dropdown greyed out** | Deliberate — quality only applies to MP4 |

Tip: **Settings → Open logs folder** jumps straight to the logs.

## The engine files (do not rename these)

MeTube looks for three files in a folder named `bin` directly next to `MeTube.exe`:

MeTubeShip
└─ bin
├─ yt-dlp.exe ← EXACT name, lowercase, no suffix
├─ ffmpeg.exe ← EXACT name
└─ ffprobe.exe ← EXACT name


Names matter: `yt-dlp (1).exe`, `FFMPEG.EXE` or `yt-dlp.exe.txt` will not be found.

MeTube checks `<folder of MeTube.exe>\bin` first, then the data folder's `bin`. If neither has all three, it downloads them itself (the Add button shows "Preparing engine…" while it does).

Official sources:

- yt-dlp: `https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe`
- ffmpeg/ffprobe: `https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip` (the zip nests them inside `ffmpeg-master-latest-win64-gpl\bin\` — copy `ffmpeg.exe` and `ffprobe.exe` out of it)

## Personal use

MeTube is a personal-use tool and does not include any content. Downloading material you do not have the right to download may violate YouTube's Terms of Service and/or the rights of the copyright holder. Use it for content you are allowed to save — your own uploads, public-domain material, Creative Commons material, or wherever the rights holder permits it. You are responsible for how you use it.

MeTube has no accounts, no analytics, and sends nothing but the requests required to fetch the videos you ask for.

| Component | Licence |
|---|---|
| yt-dlp | Unlicense (public domain) |
| FFmpeg / FFprobe | LGPL / GPL — see the FFmpeg project |
| MeTube itself | personal use |
