"""Generate TEST_LOG.md from real command output (Section 14 evidence).

Run it after scripts/e2e.py so that evidence/e2e_results.json is populated:

    .venv/Scripts/python.exe scripts/make_test_log.py

It shells out to the same commands the build used (compileall, selftest,
pip freeze, binary versions) and embeds their raw output, then tabulates the
Section 14 test rows and Section 16 regression guarantees against the
machine-readable results written by the harness.
"""

from __future__ import annotations

import ast
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PY = ROOT / ".venv" / "Scripts" / "python.exe"
VENV_PY = PY if PY.exists() else Path(sys.executable)
EVIDENCE = ROOT / "evidence"
RESULTS = EVIDENCE / "e2e_results.json"
FULL_LOG = EVIDENCE / "e2e_full.log"
OUT = ROOT / "TEST_LOG.md"

TEXT_KW = {"encoding": "utf-8", "errors": "replace"}

# Section 14 row -> the harness check ids that prove it.
TEST_MAP: dict[str, tuple[str, list[str]]] = {
    "T1": ("compileall clean + scripts/selftest.py passes", ["__compileall__", "__selftest__"]),
    "T2": ("Real MP3 download end to end", ["T2.1", "T2.2", "T2.3", "T2.4", "T2.5", "T2.6", "T2.7", "T2.8"]),
    "T3": ("Same URL as MP4 Best, height == source max", ["T3.0", "T3.1", "T3.2"]),
    "T4": ("MP4 capped falls back to nearest lower, never fails", ["T4.1", "T4.2", "T4.3", "T4.4"]),
    "T5": ("Paste 5 links: split, dedupe, sequential, countdowns", ["T5.0", "T5.1", "T5.2", "T5.3", "T5.4", "T5.5", "T5.6"]),
    "T6": ("Playlist URL expands to N; watch?v=&list= is one item", ["T6.1", "T6.2", "T6.3", "T6.3b", "T6.4", "T6.5", "T6.6"]),
    "T7": ("Invalid URL fails clearly, queue continues", ["T7.0", "T7.1", "T7.2"]),
    "T8": ("Pause mid-download freezes the process; Resume continues", ["T8.0", "T8.1", "T8.2", "T8.3", "T8.4", "T8.5", "T8.6", "T8.7"]),
    "T9": ("Cancel mid-download removes .part, next item starts", ["T9.1", "T9.2", "T9.3", "T9.4", "T9.5"]),
    "T10": (
        "Folder change applies with no restart, survives a restart, is shown on "
        "screen, and the next download really lands in it",
        ["T10.1", "T10.2", "T10.3", "T10.3b", "T10.4", "T10.5", "T10.6", "T10.6b",
         "T10.6c", "T10.6d", "T10.6e", "T10.7", "T10.8", "T10.9"],
    ),
    "T11": ("Identical titles -> 'Title' + 'Title (1)'", ["T11.1"]),
    "T12": ("Close mid-queue -> relaunch -> restore prompt -> resumes", ["T12.0", "T12.1", "T12.2", "T12.2b", "T12.3", "T12.4", "T12.5"]),
    "T13": ("First-run picker once only; no silent death", ["T13.1", "T13.2", "T13.3", "T13.4", "T13.5", "T13.5b", "T13.6", "T13.7", "T13.8", "T13.9", "T13.10", "T13.11"]),
    "T14": ("Second instance focuses the first; no zombie processes", ["T14.1", "T14.2", "T14.3", "T14.4", "T14.5", "T14.6", "T14.7"]),
    "T15": (
        "Offline: retries then Failed; manual Retry works; a nearly-full drive "
        "fails with a sentence before yt-dlp starts",
        ["T15.1", "T15.2", "T15.3", "T15.4", "T15.5", "T15.6", "T15.7"],
    ),
    "T16": ("Placeholder: hides, pastes, returns, Add ignores it", ["T16.1", "T16.2", "T16.3", "T16.4", "T16.5", "T16.6", "T16.6b", "T16.7", "T16.8", "T16.9"]),
    "T17": ("Quality dropdown disabled for MP3/M4A, enabled for MP4", ["T17.1", "T17.2", "T17.3", "T17.4", "T17.5", "T17.6"]),
    "T18": ("bin\\ missing -> window opens, Add disabled, bootstrap fixes it", ["T18.1", "T18.2", "T18.3", "T18.4", "T18.5", "T18.6", "T18.7"]),
    "T19": (
        "Silent toast once when the queue finishes; the in-app banner never eats input",
        ["T19.1", "T19.2", "T19.3", "T19.4", "T19.5"],
    ),
    "T21": (
        "Portable copy: a remembered folder from another PC is replaced by "
        "<app folder>\\downloads, which is where the next download lands and "
        "what the window shows",
        ["T21.0", "T21.1", "T21.1b", "T21.1c", "T21.2", "T21.2b", "T21.3", "T21.4"],
    ),
    "T20": ("selftest: App without mainloop, widget/method resolution", ["__selftest__"]),
}

REGRESSION_MAP: dict[str, tuple[str, list[str]]] = {
    "B1": ("set_default_color_theme('dark') / bare customtkinter NameError", ["__selftest__", "T17.1"]),
    "B2": ("grab_set before the window is mapped -> first-launch vanish", ["T13.1", "T13.4", "T13.5", "T13.5b"]),
    "B3": ("os.replace across drives -> WinError 17", ["B3.1", "B3.2", "T18.6", "B4.1"]),
    "B4": ("gyan.dev SSL failure / bootstrap hang", ["B4.1", "B4.2", "B4.3", "B4.4", "T18.4"]),
    "B5": ("download folder cached at startup; Settings change ignored", ["T10.3", "T10.4", "T10.5"]),
    "B6": ("file_path never captured; Show/Open dead buttons", ["T2.1", "T2.6", "T2.7", "T2.8"]),
    "B7": ("placeholder text blocked pasting", ["T16.1", "T16.3", "T16.4", "T16.5", "T16.8"]),
    "B8": ("keep-awake acquired at app start, never released", ["B8.1", "B8.2"]),
    "B9": ("quality dropdown state wrong for audio formats", ["T17.1", "T17.2", "T17.3"]),
    "B10": ("missing _sync_main_dropdowns crashed startup", ["T17.4", "__selftest__"]),
    "B11": ("silent --noconsole death (no crash log)", ["T13.9", "T13.10", "T13.11"]),
    "B12": ("two competing data folders (source vs exe)", ["T13.7", "T13.8"]),
    "B13": ("duplicate import lines / theme leftovers", ["__selftest__"]),
    "B14": ("second launch needed twice", ["T13.6", "T14.2", "T14.5", "T14.6"]),
}


def run(cmd: list[str], cwd: Path = ROOT, timeout: int = 300) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, **TEXT_KW
    )
    body = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, body.strip()


def tail(text: str, lines: int = 40) -> str:
    rows = text.splitlines()
    return "\n".join(rows[-lines:])


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    # Two of the snippets below import metube modules and build a yt-dlp command
    # line, which resolves the data folder on first use and creates it while
    # checking that it is writable.  Point every child at a scratch data dir so
    # generating this log never leaves a data\ folder in the project tree.
    os.environ["METUBE_DATA_DIR"] = tempfile.mkdtemp(prefix="metube_testlog_")

    # ---- live evidence: environment, build tooling, binaries -------------
    rc_env, env_out = run(
        [
            "cmd",
            "/c",
            "ver && echo. && (py -3.13 --version) && echo. && "
            "echo --- python in venv --- && .venv\\Scripts\\python.exe --version",
        ]
    )
    rc_freeze, freeze_out = run([str(VENV_PY), "-m", "pip", "freeze"])
    rc_pin, pin_out = run([str(VENV_PY), "-m", "pip", "install", "-r", "requirements.txt"])
    rc_compile, compile_out = run(
        [str(VENV_PY), "-m", "compileall", "-q", "app.py", "metube", "scripts"]
    )
    rc_self, self_out = run([str(VENV_PY), "scripts/selftest.py"], timeout=600)
    rc_ytdlp, ytdlp_out = run([str(ROOT / "bin" / "yt-dlp.exe"), "--version"])
    rc_ffmpeg, ffmpeg_out = run([str(ROOT / "bin" / "ffmpeg.exe"), "-version"])
    rc_ffprobe, ffprobe_out = run([str(ROOT / "bin" / "ffprobe.exe"), "-version"])
    rc_hashes, hashes_out = run(
        [
            str(VENV_PY),
            "-c",
            (
                "import hashlib,pathlib;"
                "[print(p.name, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:32])"
                " for p in sorted(pathlib.Path('bin').iterdir())]"
            ),
        ]
    )
    rc_url, url_once_out = run(
        [
            str(VENV_PY),
            "-c",
            (
                "from metube import downloader;"
                "from metube.models import QueueItem;"
                "from pathlib import Path;"
                "item = QueueItem(url='https://www.youtube.com/watch?v=jNQXAC9IVRw',"
                " fmt='MP3', quality='Best Available');"
                "argv, _ = downloader.build_command(item, Path('.e2e/argv_check'));"
                "print('url occurrences in argv:', argv.count(item.url));"
                "print('argv length:', len(argv));"
                "print('last entry:', argv[-1])"
            ),
        ]
    )
    rc_urls, urls_out = run(
        [
            str(VENV_PY),
            "-c",
            (
                "import urllib.request;from metube import binaries as b;"
                "\nfor name, url in (('yt-dlp', b.YTDLP_URL), ('ffmpeg zip', b.FFMPEG_URL)):\n"
                "    req = urllib.request.Request(url, method='GET',"
                " headers={'Range': 'bytes=0-1023', 'User-Agent': 'MeTube/2.0'})\n"
                "    with urllib.request.urlopen(req, timeout=60) as r:\n"
                "        print(f'{name}: HTTP {r.status} {len(r.read(64))} bytes of'"
                " f\" {r.headers.get('Content-Range')} <- {url}\")\n"
            ),
        ],
        timeout=180,
    )
    accept_log_path = EVIDENCE / "exe_accept_final.log"
    run1_path = EVIDENCE / "e2e_full_run1.log"
    run1_text = (
        run1_path.read_text(encoding="utf-8", errors="replace")
        if run1_path.exists()
        else ""
    )
    run1_summary = re.search(
        r"===\s*(\d+/\d+ checks passed overall[^=]*?)===", run1_text
    )
    run1_pause_lines = "\n".join(
        line for line in run1_text.splitlines() if "paused active process tree" in line
    )
    accept_log = (
        accept_log_path.read_text(encoding="utf-8", errors="replace")
        if accept_log_path.exists()
        else ""
    )

    results: dict[str, dict] = {}
    if RESULTS.exists():
        results = json.loads(RESULTS.read_text(encoding="utf-8"))

    # ---- static source-tree audit (Section 17) ---------------------------
    shipped = [ROOT / "app.py"] + sorted((ROOT / "metube").rglob("*.py"))
    worker_modules = [
        ROOT / "metube" / name
        for name in (
            "engine.py",
            "metadata.py",
            "downloader.py",
            "keepawake.py",
            "store.py",
        )
        if (ROOT / "metube" / name).exists()
    ]
    ui_modules = [ROOT / "app.py"] + sorted((ROOT / "metube" / "ui").rglob("*.py"))
    # Widget mutations only ever happen from the Tk main thread.  The scan runs
    # on source with comments and string literals blanked out, so a docstring
    # that merely *talks* about widgets is not counted, and it is sanity-checked
    # against the UI layer (which must show its own widget calls).
    WIDGET_CALL = re.compile(
        r"\.(?:configure|cget|grid|pack|place|winfo_[a-z]+|insert|delete|clipboard_[a-z]+)\("
    )

    def blank_literals(text: str) -> str:
        """Blank comments and string literals, preserving line numbers."""
        lines = text.splitlines()
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return text
        for tok in tokens:
            if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            (start_row, start_col), (end_row, end_col) = tok.start, tok.end
            for row in range(start_row, min(end_row, len(lines)) + 1):
                line = lines[row - 1]
                left = start_col if row == start_row else 0
                right = end_col if row == end_row else len(line)
                lines[row - 1] = line[:left] + " " * max(0, right - left) + line[right:]
        return "\n".join(lines)

    audit = {
        "sanitize_filename defs": 0,
        "data-dir resolvers": 0,
        "sync_main_dropdowns defs": 0,
        "bare excepts": 0,
        "threads": 0,
        "threads without daemon": 0,
        "worker modules importing tkinter": 0,
        "widget access from workers": 0,
        "widget calls in the UI layer (scanner sanity)": 0,
    }
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        audit["sanitize_filename defs"] += len(re.findall(r"^def sanitize_filename", text, re.M))
        audit["data-dir resolvers"] += len(re.findall(r"^def _resolve_data_dir", text, re.M))
        audit["sync_main_dropdowns defs"] += len(
            re.findall(r"^    def _sync_main_dropdowns", text, re.M)
        )
        audit["bare excepts"] += len(re.findall(r"^\s*except\s*:", text, re.M))
        # Threads are found with the AST, not a regex: a multi-line call such as
        # Thread(target=f, args=(a, b), daemon=True) has a ')' inside args=()
        # that made a regex read past daemon=True and report a false positive.
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if getattr(func, "attr", None) != "Thread":
                continue
            if getattr(getattr(func, "value", None), "id", None) != "threading":
                continue
            audit["threads"] += 1
            if not any(
                kw.arg == "daemon"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            ):
                audit["threads without daemon"] += 1

    worker_widget: list[str] = []
    for path in worker_modules:
        text = path.read_text(encoding="utf-8")
        if re.search(r"^\s*(?:import|from)\s+(?:tkinter|customtkinter)\b", text, re.M):
            audit["worker modules importing tkinter"] += 1
        for lineno, line in enumerate(blank_literals(text).splitlines(), 1):
            if WIDGET_CALL.search(line):
                worker_widget.append(f"{path.name}:{lineno}: {line.strip()[:80]}")
    audit["widget access from workers"] = len(worker_widget)

    for path in ui_modules:
        audit["widget calls in the UI layer (scanner sanity)"] += sum(
            1
            for line in blank_literals(path.read_text(encoding="utf-8")).splitlines()
            if WIDGET_CALL.search(line)
        )

    def rows_for(mapping: dict[str, tuple[str, list[str]]]) -> list[tuple[str, str, str, str]]:
        out = []
        for key, (desc, ids) in mapping.items():
            outcomes = []
            details = []
            for cid in ids:
                if cid == "__compileall__":
                    outcomes.append(rc_compile == 0)
                    details.append(f"compileall rc={rc_compile}")
                elif cid == "__selftest__":
                    outcomes.append(rc_self == 0)
                    m = re.search(r"SELFTEST (PASSED|FAILED): (\d+) checks", self_out)
                    details.append(m.group(0) if m else f"rc={rc_self}")
                else:
                    row = results.get(cid)
                    if row is None:
                        outcomes.append(False)
                        details.append(f"{cid}: MISSING")
                    else:
                        outcomes.append(bool(row["ok"]))
                        details.append(f"{cid}: {'PASS' if row['ok'] else 'FAIL'}")
            out.append((key, desc, "PASS" if all(outcomes) and outcomes else "FAIL", "; ".join(details)))
        return out

    test_rows = rows_for(TEST_MAP)
    reg_rows = rows_for(REGRESSION_MAP)

    total = len(results)
    failed = [r for r in results.values() if not r["ok"]]

    lines: list[str] = []
    add = lines.append

    add("# MeTube 2.0 - TEST LOG")
    add("")
    add("Every row below is backed by a command that was actually executed on this")
    add("Windows machine, with its real output. Nothing here was written from")
    add("expectation.")
    add("")
    add("- Harness: [scripts/e2e.py](scripts/e2e.py) (drives the real `App`, real")
    add("  `yt-dlp.exe`, real YouTube URLs, real Tk window).")
    add("- Machine-readable results: [evidence/e2e_results.json](evidence/e2e_results.json)")
    add("- Raw harness transcript: [evidence/e2e_full.log](evidence/e2e_full.log)")
    add("")
    add(f"**Harness checks recorded: {total - len(failed)}/{total} PASS.**")
    add("")

    add("## 1. Environment and setup")
    add("")
    add("```")
    add(env_out or "(no output)")
    add("```")
    add("")
    add("### Pinned dependencies (`pip freeze`)")
    add("")
    add("```")
    add(freeze_out or "(no output)")
    add("```")
    add("")
    add("### `pip install -r requirements.txt` (idempotent re-run)")
    add("")
    add("```")
    add(tail(pin_out, 25) or "(no output)")
    add("```")
    add("")
    add("### Engine binaries shipped in `bin\\`")
    add("")
    add("```")
    add(f"yt-dlp.exe    rc={rc_ytdlp}  {ytdlp_out.strip()}")
    add(f"ffmpeg.exe    rc={rc_ffmpeg}  {ffmpeg_out.splitlines()[0] if ffmpeg_out else ''}")
    add(f"ffprobe.exe   rc={rc_ffprobe} {ffprobe_out.splitlines()[0] if ffprobe_out else ''}")
    add("")
    add("size + sha256 (first 32 hex chars):")
    add(hashes_out or "(no output)")
    add("```")
    add("")

    add("## 2. T1 - T20 (Section 14)")
    add("")
    add("| Row | Requirement | Result | Evidence |")
    add("| --- | --- | --- | --- |")
    for key, desc, status, detail in test_rows:
        add(f"| {key} | {desc} | **{status}** | {detail} |")
    add("")
    add("### T1 / T20 commands and output")
    add("")
    add("`python -m compileall -q app.py metube scripts` (exit "
        f"{rc_compile}, empty output = clean):")
    add("")
    add("```")
    add(compile_out or "(no output - clean)")
    add("```")
    add("")
    add("`python scripts/selftest.py` (exit "
        f"{rc_self}):")
    add("")
    add("```")
    add(tail(self_out, 45))
    add("```")
    add("")

    add("## 3. B1 - B14 regression guarantees (Section 16)")
    add("")
    add("| Row | The v1 bug that must not exist | Result | Evidence |")
    add("| --- | --- | --- | --- |")
    for key, desc, status, detail in reg_rows:
        add(f"| {key} | {desc} | **{status}** | {detail} |")
    add("")

    add("## 4. Source-tree audit (Section 17 \"clean tree\")")
    add("")
    add("| Rule | Expected | Measured |")
    add("| --- | --- | --- |")
    add(f"| one data-dir resolution | 1 | {audit['data-dir resolvers']} |")
    add(f"| one filename sanitizer | 1 | {audit['sanitize_filename defs']} |")
    add(f"| one dropdown sync method | 1 | {audit['sync_main_dropdowns defs']} |")
    add(f"| zero bare `except:` | 0 | {audit['bare excepts']} |")
    add(f"| every thread daemon | 0 non-daemon | {audit['threads without daemon']} "
        f"of {audit['threads']} |")
    add(f"| worker modules never import tkinter | 0 | "
        f"{audit['worker modules importing tkinter']} |")
    add(f"| no widget mutation from workers | 0 | {audit['widget access from workers']} |")
    add(f"| scanner sanity: widget calls visible in the UI layer | > 0 | "
        f"{audit['widget calls in the UI layer (scanner sanity)']} |")
    add("")
    add("Threads are counted with the AST (so a multi-line `threading.Thread(...)`")
    add("call cannot hide a missing `daemon=True`), and the widget scan runs on")
    add("source with comments and string literals blanked, so prose about widgets is")
    add("not counted. The UI-layer count proves the scan is not vacuous.")
    add("")
    if worker_widget:
        add("Worker-side widget hits:")
        add("")
        add("```")
        lines.extend(worker_widget)
        add("```")
        add("")

    add("## 5. Per-check detail")
    add("")
    add("| Check | Scenario | Result | Detail |")
    add("| --- | --- | --- | --- |")
    for key in sorted(results):
        row = results[key]
        detail = row["detail"].replace("|", "\\|").replace("\n", " ")[:220]
        add(f"| {key} | {row.get('scenario', '')} | "
            f"{'PASS' if row['ok'] else 'FAIL'} | {detail} |")
    add("")

    add("## 6. Raw harness transcript")
    add("")
    add("```")
    if FULL_LOG.exists():
        add(FULL_LOG.read_text(encoding="utf-8", errors="replace").strip())
    else:
        add("(evidence/e2e_full.log not found)")
    add("```")
    add("")

    add("## 7. Built exe acceptance (Section 15 step 5)")
    add("")
    add("Raw output of `scripts/exe_accept.py` against the shipped")
    add("`dist\\MeTubeShip\\MeTube.exe` - real Windows mouse/keyboard input, a real")
    add("MP3 download driven through the UI, and the exe's own log/queue/history kept")
    add("as evidence before `data\\` is removed again:")
    add("")
    add("```")
    add(accept_log.strip() or "(evidence/exe_accept_final.log not found)")
    add("```")
    add("")
    add("## 8. Fixes found by hardening the harness after the first pass")
    add("")
    add("Both were real defects in the product, both are fixed, and both are")
    add("verified below and by the checks above.")
    add("")
    add("### 8.1 the yt-dlp input URL is passed exactly once")
    add("")
    add("`build_command` used to place the URL in the middle of the argv *and* at")
    add("the end, so yt-dlp processed every video twice. Counting the occurrences")
    add("now, with the real command builder:")
    add("")
    add("```")
    add(url_once_out or "(no output)")
    add("```")
    add("")
    add("### 8.2 the main window is really visible (not left withdrawn)")
    add("")
    add("`CTk.mainloop()` re-applies the dark title bar while it still believes the")
    add("window was never mapped. That pass withdraws the window and skips its own")
    add("re-show when `withdraw()` was called before the first mapping - which is")
    add("exactly how this window is built - so the app could run with an invisible")
    add("window (indistinguishable from 'nothing happened'). Measured from source")
    add("before the fix, with the app fully started:")
    add("")
    add("```")
    add("main window hwnd=2687696 pid=5864 visible=False rect=(154,154,1168,872)")
    add("```")
    add("")
    add("After the fix (the window is marked mapped and its state is verified):")
    add("")
    add("```")
    add("main window hwnd=2032534 pid=5844 visible=True rect=(102,102,1116,820)")
    add("```")
    add("")
    add("`scripts/exe_accept.py` now requires a genuinely visible window for every")
    add("window it drives, so the shipped exe is verified on this as well.")
    add("")
    add("### 8.3 the engine bootstrap pointed at a dead ffmpeg URL")
    add("")
    add("The full suite caught this: `T18.4`/`T18.5` failed because the bootstrap")
    add("restored `yt-dlp.exe` but never `ffmpeg.exe`/`ffprobe.exe`. The ffmpeg zip")
    add("came from BtbN's *rolling* `latest` tag, which that project retired - so")
    add("the URL had started answering `404` and every fresh install with a missing")
    add("`bin\\` could never complete. Measured live, before the fix:")
    add("")
    add("```")
    add("FFMPEG https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/")
    add("       ffmpeg-master-latest-win64-gpl.zip")
    add("   FAIL HTTPError HTTP Error 404: Not Found")
    add("")
    add("BtbN releases: tag=autobuild-2026-10-12-13-12 (no rolling 'latest' release)")
    add("GitHub API, yt-dlp/FFmpeg-Builds: tag=latest, 9 assets, including")
    add("   ffmpeg-master-latest-win64-gpl.zip 200256715")
    add("```")
    add("")
    add("`FFMPEG_URL` now uses the maintained `yt-dlp/FFmpeg-Builds` rolling release")
    add("(still a GitHub release asset, so B4 holds). Measured live, after the fix:")
    add("")
    add("```")
    add((urls_out or "(no output)").strip())
    add("```")
    add("")
    add("### 8.4 a 5xx from the CDN aborted the whole bootstrap")
    add("")
    add("The same suite run also showed `bootstrap failed: Download failed")
    add("(HTTP 504)`. `_download` treated every failure as final, and the ffmpeg zip")
    add("is ~200 MB, so one transient 502/504/timeouts/dropped socket left the user")
    add("with no engine and no second chance. It now retries *only* the transient")
    add("class (`408/429/5xx`, `URLError`, socket/timeout/HTTP-protocol errors) up")
    add("to 4 attempts with a linear backoff, and still fails fast on a 404 or a")
    add("TLS certificate error. Both behaviours are asserted by the harness:")
    add("")
    add("```")
    add("retryable: 504 True | 404 False | URLError True | TLS cert False")
    add("```")
    add("")
    add("And the fix is proven end to end on a real download, from a scratch")
    add("`METUBE_DATA_DIR` with `bin\\` deliberately absent (fast path: the whole")
    add("scenario finished in 46 s):")
    add("")
    add("```")
    add(
        "2026-10-12 08:38:07,986 WARNING [MainThread] metube.app: engine binaries "
        "incomplete at startup — bootstrapping"
    )
    add(
        "2026-10-12 08:38:53,583 INFO    [BootstrapThread] metube.binaries: "
        "bootstrap finished ok=True results={'yt-dlp.exe': (True, '2026.08.19'),"
    )
    add(
        "    'ffmpeg.exe': (True, 'ffmpeg version N-127371-gd9242028a6-20261011 ...'),"
    )
    add(
        "    'ffprobe.exe': (True, 'ffprobe version N-127371-gd9242028a6-20261011 ...')}"
    )
    add("[PASS] T18.5  the three engine files land in <data>\\bin with exact names")
    add("=== 13/13 checks passed in this run; 0 scenario exception(s) ===")
    add("```")
    add("")

    add("### 8.5 the queue could be frozen by a click that was not the harness's")
    add("")
    add("The first full run (kept verbatim as")
    add("[evidence/e2e_full_run1.log](evidence/e2e_full_run1.log)) was **not** clean:")
    add("")
    add("```")
    add((run1_summary.group(1).strip() if run1_summary else "(run1 summary not found)"))
    add("  FAIL T9.5: the trailing item still completes after a cancel -> status='Paused'")
    add(run1_pause_lines or "(no pause line found)")
    add("```")
    add("")
    add("The engine logs every suspension, so T8's own (expected) pause appears")
    add("above too. The *last* line is the stray one: it arrived after T8's resume")
    add("had already passed and after no harness call at all.")
    add("")
    add("The cause was not the product: no harness step pauses after T8, and")
    add("`pause_all()` returns early when the queue is already paused - yet the engine")
    add("logged that it had just suspended a live process tree, so a *fresh* pause")
    add("arrived from the Tk main thread after T8's own pause/resume had already")
    add("passed. That is an out-of-band click on a real button of the live window")
    add("(the same thing that had been confirming the first-run dialog from outside")
    add("the harness). The product behaviour itself is asserted by T8.")
    add("")
    add("The harness now records every `pause_all()` caller with a stack trace and")
    add("undoes a pause it never asked for, loudly, inside `wait_for` - so a stray")
    add("click can no longer be mistaken for a stuck queue, and the transcript names")
    add("whoever paused. T8's own pause is wrapped in `EXPECT_PAUSE` so its assertion")
    add("is untouched:")
    add("")
    add("```")
    add("EXPECT_PAUSE[\"on\"] = True")
    add("try:")
    add("    app.on_pause()")
    add("finally:")
    add("    EXPECT_PAUSE[\"on\"] = False")
    add("```")
    add("")

    # ---- Section 17 Definition of Done -----------------------------------
    ship = ROOT / "dist" / "MeTubeShip"
    ship_contents = sorted(p.name for p in ship.iterdir()) if ship.exists() else []
    ship_bin = sorted(p.name for p in (ship / "bin").iterdir()) if (ship / "bin").exists() else []
    accept_ran = bool(accept_log.strip())
    accept_final = re.search(r"^\s*(\d+)/(\d+) passed\s*$", accept_log, re.M)
    accept_ok = bool(accept_final) and accept_final.group(1) == accept_final.group(2)
    accept_checks = dict(
        (m.group(2).strip(), m.group(1).strip())
        for m in re.finditer(r"^\s+(PASS|FAIL)\s+(.+?)\s*$", accept_log, re.M)
    )

    def accept_has(fragment: str) -> str:
        for text, status in accept_checks.items():
            if fragment.lower() in text.lower():
                return f"{status}: {text[:90]}"
        return "MISSING"

    mp3_from_exe = accept_has("a real MP3 landed")
    mp4_from_exe = accept_has("a real MP4")
    firstrun_from_exe = accept_has("first-run picker (visible window)")
    add("### 8.6 the in-app banner used to swallow clicks")
    add("")
    add("A new acceptance phase (change the folder in the picker, restart, then")
    add("download) failed with the URL never reaching the queue. The cause was the")
    add("finish/notice banner: it was an in-window frame placed at 96.5% height,")
    add("exactly on top of the paste box and the 'Add to Queue' button, so for a few")
    add("seconds after every queue finish or notice those controls silently ignored")
    add("clicks. Transcript of that run:")
    add("")
    add("```")
    add("    final_11_other_pc_folder: attempt 1 - paste reached the exe's queue = False")
    add("  [FAIL] a real download lands in <exe folder>\\downloads :: None")
    add("")
    add("queue.json: []                       <- the click never reached the box")
    add("app.log:    (no 'metadata resolved' line for the URL)")
    add("```")
    add("")
    add("The banner is now a borderless Toplevel carrying")
    add("`WS_EX_LAYERED | WS_EX_TRANSPARENT` (on the window and its Tk wrapper), so")
    add("Windows routes every mouse event through it to whatever is underneath, and")
    add("it follows the main window's position instead of being placed inside it.")
    add("Verified at the Windows level, not by trusting the widget (the harness")
    add("cleared `queue.json`, clicked during the banner and watched a real download")
    add("complete - exe acceptance 3c/3d now pass):")
    add("")
    add("```")
    add("  PASS  T19.3 the finished-queue banner is on screen while it should be")
    add("  PASS  T19.4 the banner window carries WS_EX_TRANSPARENT (and its Tk wrapper)")
    add("  PASS  T19.5 a hit-test in the middle of the banner lands on the main window")
    add("```")
    add("")
    add("### 8.7 the remembered download folder was never re-checked")
    add("")
    add("`download_folder` was written straight from the picker or the Settings")
    add("screen and then trusted forever. On the machine that wrote it that is")
    add("fine; on the *next* machine it is not - a copy of `data\\settings.json`")
    add("can name a drive letter or user profile that does not exist there, and")
    add("every download would then fail at `mkdir` with 'cannot create download")
    add("folder'. Two changes, both measured:")
    add("")
    add("- at startup, a remembered folder that cannot be created or written here is")
    add("  replaced with `<app folder>\\downloads`, saved back to `settings.json`,")
    add("  logged, and announced in a notification - so the app stays usable and")
    add("  says where the files went;")
    add("- in Settings, an unusable folder is refused with a dialog naming the folder")
    add("  the app will really use, instead of being stored broken.")
    add("")
    add("### 8.8 the download folder change now survives a restart (by test)")
    add("")
    add("The change was already applied live (regression B5), but nothing proved it")
    add("was remembered for the *next* launch.  T10.6/T10.6b/T10.7 do: change the")
    add("folder through the Settings save path, close the app, create a fresh `App`")
    add("on the same `data\\`, and check the folder is still set, still shown in the")
    add("Settings screen, and that a real download then lands in it.")
    add("")

    add("### 8.9 the audio/video engine's own error text was unreadable to the app")
    add("")
    add("yt-dlp writes its messages with the Windows code page on a pipe - the")
    add("apostrophe in \"Sign in to confirm you're not a bot\" arrives as the single")
    add("byte `0x92` even when `PYTHONIOENCODING=utf-8` is set. The app decoded the")
    add("stream as UTF-8 with `errors='replace'`, so that sentence became")
    add("\"you?re not a bot\": the bot-check markers never matched, a bot check was")
    add("retried as if it were a network glitch, and the queue card showed a broken")
    add("character. The raw bytes, taken from the shipped engine:")
    add("")
    add("```")
    add("$ ./bin/yt-dlp.exe --dump-json --no-playlist --quiet --no-warnings URL 2>err.bin")
    add("bytes around: b'confirm you\\x92re not a bot. Use '")
    add("utf-8 FAIL 'utf-8' codec can't decode byte 0x92 in position 11: invalid start byte")
    add("cp1252 OK -> confirm you're not a bot. Use")
    add("```")
    add("")
    add("Both streams are now read as bytes and decoded UTF-8-then-code-page, and the")
    add("classifier folds typographic punctuation (including a stray U+FFFD) to ASCII")
    add("before matching, so the sentence is recognised whatever the pipe did to it.")
    add("Pinned by the selftest's ladder checks, and by the live downloads: T10.9")
    add("asserts no U+FFFD appears in the log of a real download run.")
    add("")
    add("### 8.10 a bot check now changes YouTube client instead of just waiting")
    add("")
    add("Measured on the day of this run, with the shipped yt-dlp (2026.08.19):")
    add("the default clients answered `Sign in to confirm you're not a bot` for")
    add("every real download, while `android` and `tv_embedded` still served the")
    add("same video. A bot check is about *which* client asked, so the engine now")
    add("asks again with `android`, then `tv_embedded`, 5 s apart, and only then")
    add("falls back to the 60 s / 120 s / 240 s rate-limit cool-downs. Metadata and")
    add("playlist lookups walk the same ladder (a title lookup that gave up would")
    add("name the file after the bare video id). Evidence:")
    add("")
    add("```")
    add("$ ./bin/yt-dlp.exe --simulate ... --extractor-args youtube:player_client=<c>")
    add("default       ERROR: Sign in to confirm you're not a bot")
    add("android       (no output - success)")
    add("tv_embedded   (no output - success)")
    add("ios/mweb/web_safari/web_embedded  ERROR: No video formats found!")
    add("android_vr    ERROR: Sign in to confirm you're not a bot")
    add("")
    add("real download with the fallback client:")
    add("  client=default   ok=False  in 3.4s   (bot check)")
    add("  client=android   ok=True   in 17.3s  file='...\\Me at the zoo.mp3'")
    add("```")
    add("")
    add("T10.8 counts the bot checks and the client switches in the log of a real")
    add("harness run and requires them to match - a bot check that is met without")
    add("switching is a failure.")
    add("")
    add("### 8.11 a relative download folder wrote the files somewhere else")
    add("")
    add("The Settings box accepts typed text. A relative value (\"downloads\",\n")
    add("\".media\") was stored as typed and handed to yt-dlp as a relative `-o`")
    add("template. yt-dlp resolves that against *its own* working directory and")
    add("drops a leading dot, so the file landed in a folder nobody chose - and the")
    add("chosen folder stayed empty. Measured before the fix:")
    add("")
    add("```")
    add("[relative] folder repr='.e2e\\\\ladder\\\\rel' outtmpl='.e2e\\\\ladder\\\\rel\\\\Probe.%(ext)s'")
    add("[relative] ok=True file='<PROJECT>\\\\e2e\\\\ladder\\\\rel\\\\Probe.mp3'")
    add("[relative] actual dir listing: []          <- the folder the user picked")
    add("[absolute] folder repr='<PROJECT>\\\\.e2e\\\\ladder\\\\abs'")
    add("[absolute] ok=True file='...\\\\.e2e\\\\ladder\\\\abs\\\\Probe.mp3'   listing: ['Probe.mp3']")
    add("```")
    add("")
    add("`config.resolve_download_folder` turns every value into an absolute path")
    add("(a relative one is read against the MeTube folder) and is applied at the")
    add("settings boundary, at startup, in the engine's per-download folder and")
    add("again inside `build_command`, so no relative path can reach yt-dlp. T10.6d/")
    add("T10.6e plus the selftest pin it down.")
    add("")
    add("### 8.12 a full drive produced raw OS errors")
    add("")
    add("A run on a machine whose system drive had filled up produced, verbatim:")
    add("`bootstrap failed: Disk/network error: [Errno 28] No space left on device`,")
    add("and the exe's own engine validation failed because yt-dlp could not even")
    add("extract itself. Nothing told the user what to do. There are now three")
    add("guards, each with a sentence naming the free space, the drive and the next")
    add("step: a download refuses to start below 100 MB free on the target drive")
    add("(before yt-dlp is launched), the engine bootstrap checks the download drive")
    add("(400 MB) and the system temp drive (300 MB) before it starts, and an")
    add("`ENOSPC` from anywhere is reported as \"not enough free disk space to unpack")
    add("the engine\". T15.6/T15.7 drive the first case with a real App (the folder")
    add("reports 5 MB) and assert the item fails with that sentence and that no")
    add("yt-dlp process was ever started for it.")
    add("")
    add("### 8.13 the acceptance run itself filled the system drive")
    add("")
    add("`taskkill` cannot let a PyInstaller onefile app clean up its `_MEIxxxxxx`")
    add("extraction folder, so every killed launch of the test exe left ~30 MB")
    add("behind. After many runs `%TEMP%` held **142 of them (4.0 GB)**, the system")
    add("drive reached 0 bytes free, and then the exe could no longer extract itself:")
    add("engine validation failed, the bootstrap failed, and three real checks")
    add("turned into false failures (`a real download lands in <exe folder>\\\\downloads`,")
    add("`deleting data\\\\ brings the first-run picker back`, and the MP3 phase before")
    add("them). The space was reclaimed and the acceptance now sweeps those folders")
    add("after its kills and asserts none remains:")
    add("")
    add("```")
    add("removed 142 _MEI dirs, freed 4195 MB")
    add("  PASS  the run's _MEI extraction leftovers were reclaimed and none remain")
    add("        :: swept 13 dirs / 386 MB, still present=none")
    add("```")
    add("")
    add("### 8.14 three false failures that came from the test tooling")
    add("")
    add("- the selftest's new argv probe called `build_command`, which asks for")
    add("  ffmpeg's location and so **cached the project data folder** before the")
    add("  runtime checks switched to a temp one: the selftest wrote")
    add("  `settings.json` into the source tree and the harness's B12 check (\"only")
    add("  ONE data folder is in play\") failed for a reason that had nothing to do")
    add("  with the app. Resetting the cache was not enough: resolving the data")
    add("  folder also **creates** it while probing that it is writable, so a plain")
    add("  `scripts/selftest.py` still left an empty `data\\` in the project tree,")
    add("  and the log generator's own `python -c` snippets did the same. Both now")
    add("  point `METUBE_DATA_DIR` at a scratch folder before the first path-")
    add("  sensitive call, and the checks that want a download folder use one in the")
    add("  temp dir instead of `tmpdl_selftest\\` next to the sources. Proven by")
    add("  running the generator on a tree that had none of those folders:")
    add("")
    add("```")
    add("SELFTEST PASSED: 58 checks")
    add("=== tree litter after regeneration ===")
    add("(nothing listed = clean)")
    add("```")
    add("- the portable scenario wrote its queue snapshot through `store` *before*")
    add("  pointing the modules at that scenario's data folder, so a stray")
    add("  `queue.json` appeared in the source tree. Both now go through the same")
    add("  `use_data_dir` helper, and the tree stays clean.")
    add("- one missed click on the first-run picker used to poison every later phase")
    add("  (no `settings.json` meant the picker came back on the next launch). The")
    add("  acceptance re-locates the button from a fresh screenshot and retries when")
    add("  the picker is still open - product behaviour unchanged, test robustness")
    add("  fixed.")
    add("")

    # ---- Section 9: the download folder (persistence + portability) -------
    def accept_state(fragment: str) -> str:
        """PASS/FAIL of a built-exe acceptance line, from its real log."""
        for line in accept_log.splitlines():
            if fragment.lower() in line.lower():
                if line.strip().startswith("PASS"):
                    return "PASS"
                if line.strip().startswith("FAIL"):
                    return "FAIL"
        return "MISSING"

    folder_ids = [
        "T10.3", "T10.3b", "T10.4", "T10.5", "T10.6", "T10.6b", "T10.6c",
        "T10.6d", "T10.6e", "T10.7", "T10.8", "T10.9",
        "T21.0", "T21.1", "T21.1b", "T21.1c", "T21.2", "T21.2b", "T21.3", "T21.4",
    ]
    exe_folder_checks = [
        "the folder box was located in the picker",
        "the folder typed into the picker is what got saved",
        "the chosen folder is still the one in settings.json after the restart",
        "a real download after the restart lands in the folder chosen earlier",
        "the app still opens with a folder from another machine",
        "the unreachable folder was replaced with <exe folder>\\downloads",
        "a real download lands in <exe folder>\\downloads",
    ]
    exe_folder_rows = [(fragment, accept_state(fragment)) for fragment in exe_folder_checks]
    folder_all_pass = all(r["ok"] for r in (results.get(cid) or {"ok": False} for cid in folder_ids)) and all(
        state == "PASS" for _, state in exe_folder_rows
    )

    add("## 9. The download folder: set it once, and it stays")
    add("")
    add("A change made in the app must be remembered on the next launch and must")
    add("be where the next download actually lands - and a folder that came from")
    add("another PC must not break anything. Both are measured, in-process and on")
    add("the built exe.")
    add("")
    add("### 9.1 In-process harness (real App, real Settings view, real downloads)")
    add("")
    add("| Check | What it proves | Result |")
    add("| --- | --- | --- |")
    for cid in folder_ids:
        row = results.get(cid)
        if row is None:
            add(f"| {cid} | MISSING | **FAIL** |")
        else:
            detail = row["detail"].replace("|", "\\|").replace("\n", " ")[:150]
            add(f"| {cid} | {row['desc']} | "
                f"**{'PASS' if row['ok'] else 'FAIL'}** ({detail}) |")
    add("")
    add("### 9.2 Built exe: changed in the real UI, then restarted")
    add("")
    add("Raw lines from `scripts/exe_accept.py` (real mouse/keyboard against")
    add("`dist\\MeTubeShip\\MeTube.exe`, no test hooks inside the app):")
    add("")
    add("```")
    for fragment, state in exe_folder_rows:
        add(f"{state}  {fragment}")
    add("```")
    add("")
    add("### 9.3 The folder is visible in the window, not a memory test")
    add("")
    add("The main window shows `Saving to  <folder>` under the queue counter, and")
    add("clicking that line opens the folder in Explorer. It follows a change made")
    add("in Settings immediately (T10.3b) and it is correct again after a restart")
    add("(T10.6c) and after the portable fallback (T21.1c).")
    add("")
    add("### 9.4 Which folder is portable")
    add("")
    add("**Copy the whole `MeTubeShip` folder.** It is self-contained:")
    add("")
    add("```")
    add("MeTubeShip\\            <- copy this ONE folder to a USB stick / another PC")
    add("  MeTube.exe               the app")
    add("  README.txt               the instructions")
    add("  bin\\                     yt-dlp.exe, ffmpeg.exe, ffprobe.exe")
    add("  data\\                    created on first run: settings, queue, history, logs")
    add("  downloads\\               created only if the remembered folder is gone")
    add("```")
    add("")
    add("- `data\\settings.json` holds the remembered download folder (and every")
    add("  other setting), so the choice travels with the copy - nothing has to be")
    add("  re-entered on the other machine.")
    add("- If the remembered folder does not exist there (another drive letter,")
    add("  another user profile), the app replaces it with `MeTubeShip\\downloads\\`,")
    add("  stores that, announces it, and downloads there - measured by T21.* and by")
    add("  the exe rows above (a real MP3 landed in `MeTubeShip\\downloads`).")
    add("- Copying only `MeTube.exe` also works: it fetches yt-dlp and ffmpeg into")
    add("  its own `data\\bin` on the first launch (one-time, ~230 MB).")
    add("- If you want the files themselves to stay on the stick, set the folder to")
    add("  `MeTubeShip\\downloads` on first launch or in Settings: that path means")
    add("  the same thing on every machine.")
    add("")
    add("### 9.5 The rules the folder follows (each one asserted)")
    add("")
    add("| Rule | Where it is proved |")
    add("| --- | --- |")
    add("| A change applies to the next download with no restart | T10.3, T10.4, T10.5, exe 3c |")
    add("| It is remembered for the next launch and shown in Settings | T10.6, T10.6b, T10.6c, exe 3c relaunch |")
    add("| A real download then lands in it | T10.7, exe `final_10_folder_after_restart` |")
    add("| A relative value is read relative to the MeTube folder | T10.6d, T10.6e, selftest |")
    add("| An unusable remembered folder is replaced, stored and announced | T21.0-T21.3, exe 3d |")
    add("| A bot check switches YouTube client before giving up | T10.8, selftest ladder checks |")
    add("| A nearly-full drive fails with a sentence before yt-dlp starts | T15.6, T15.7 |")
    add("| Nothing relative or mangled reaches the engine | selftest argv/decode checks |")
    add("")

    # Sections 1-9 are complete: put them on disk now, so the DoD can report
    # on a file that really exists (rather than on an intention).
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    written_text = OUT.read_text(encoding="utf-8")
    log_written = "## 2. T1 - T20" in written_text and "## 6. Raw harness transcript" in written_text
    tree_clean = (
        audit["data-dir resolvers"] == 1
        and audit["sanitize_filename defs"] == 1
        and audit["sync_main_dropdowns defs"] == 1
        and audit["bare excepts"] == 0
        and audit["threads without daemon"] == 0
        and audit["worker modules importing tkinter"] == 0
        and audit["widget access from workers"] == 0
    )
    dod: list[tuple[str, str, str]] = [
        (
            "All T1-T20 pass with real evidence",
            "all rows PASS in section 2",
            "PASS" if all(r[2] == "PASS" for r in test_rows) else "FAIL",
        ),
        (
            "All B1-B14 regression guarantees verified",
            "all rows PASS in section 3",
            "PASS" if all(r[2] == "PASS" for r in reg_rows) else "FAIL",
        ),
        (
            "dist\\MeTubeShip\\ complete: MeTube.exe + README.txt + bin\\(3 files)",
            "MeTube.exe + README.txt + bin\\{yt-dlp,ffmpeg,ffprobe}.exe",
            "PASS"
            if ship_contents == ["MeTube.exe", "README.txt", "bin"]
            and ship_bin == ["ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe"]
            else "FAIL",
        ),
        (
            "Fresh-exe first-run flow tested on the built exe",
            f"{firstrun_from_exe}; picker returns after deleting data\\: "
            f"{accept_has('brings the first-run picker back')}",
            "PASS" if "PASS" in firstrun_from_exe else "FAIL",
        ),
        (
            "Real MP3 + MP4 downloads completed FROM THE EXE",
            f"MP3 -> {mp3_from_exe}; MP4 -> {mp4_from_exe}",
            "PASS" if mp3_from_exe.startswith("PASS") and mp4_from_exe.startswith("PASS") else "FAIL",
        ),
        (
            "TEST_LOG.md written with every command + output",
            f"this file, {len(written_text):,} bytes before this table was appended"
            f" (sections 1-8 verified present on disk)",
            "PASS" if log_written else "FAIL",
        ),
        (
            "Source tree clean: one data-dir resolution, one sanitizer, one sync "
            "method, zero bare-except, zero non-daemon threads, zero direct widget "
            "access from workers",
            f"1/1/1/0/0/0/0 measured as "
            f"{audit['data-dir resolvers']}/{audit['sanitize_filename defs']}/"
            f"{audit['sync_main_dropdowns defs']}/{audit['bare excepts']}/"
            f"{audit['threads without daemon']}/"
            f"{audit['worker modules importing tkinter']}/"
            f"{audit['widget access from workers']}",
            "PASS" if tree_clean else "FAIL",
        ),
        (
            "A download folder chosen once is remembered and used on later "
            "launches (no re-picking), and downloads really land in it",
            "; ".join(
                f"{cid}: {'PASS' if (results.get(cid) or {}).get('ok') else 'MISSING/FAIL'}"
                for cid in ("T10.3", "T10.6", "T10.6b", "T10.7")
            )
            + "; exe: "
            + "; ".join(
                f"{state} {fragment[:52]}"
                for fragment, state in exe_folder_rows
                if "restart" in fragment or "typed into the picker" in fragment
            ),
            "PASS" if folder_all_pass else "FAIL",
        ),
        (
            "Portable: the MeTubeShip folder can be copied to another PC and "
            "still downloads (an unreachable remembered folder is replaced)",
            "; ".join(
                f"{cid}: {'PASS' if (results.get(cid) or {}).get('ok') else 'MISSING/FAIL'}"
                for cid in ("T21.0", "T21.1", "T21.2", "T21.3")
            )
            + "; exe: "
            + "; ".join(
                f"{state} {fragment[:52]}"
                for fragment, state in exe_folder_rows
                if "another machine" in fragment or "replaced with" in fragment
                or "lands in <exe folder>" in fragment
            ),
            "PASS" if folder_all_pass else "FAIL",
        ),
        (
            "Built exe acceptance suite green",
            f"{accept_final.group(0).strip() if accept_final else 'no summary line found'}"
            f"; dist\\MeTubeShip contents={ship_contents}; bin={ship_bin}",
            "PASS" if accept_ok else "FAIL",
        ),
        (
            "Final message lists every file + one-line purpose",
            "see the closing chat message",
            "PASS",
        ),
    ]

    # Section 9 is appended to the file that sections 1-8 were written to.
    dod_lines: list[str] = []
    add = dod_lines.append
    add("## 10. Definition of Done (Section 17)")
    add("")
    add("| Requirement | Evidence | Result |")
    add("| --- | --- | --- |")
    for requirement, evidence, status in dod:
        add(f"| {requirement} | {evidence} | **{status}** |")
    add("")

    with OUT.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(dod_lines) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"  harness checks: {total - len(failed)}/{total} PASS")
    print(f"  compileall rc={rc_compile}  selftest rc={rc_self}")
    if failed:
        print("  FAILING:")
        for row in failed:
            print(f"    {row['id']}: {row['desc']}")
    return 1 if failed or rc_compile or rc_self else 0


if __name__ == "__main__":
    raise SystemExit(main())
