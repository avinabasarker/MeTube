"""Build and assemble the shipped folder (Section 15).

    .venv/Scripts/python.exe scripts/build_ship.py

Steps:
  1. regenerate assets/icon.ico if it is missing (scripts/make_icon.py)
  2. PyInstaller onefile --noconsole build of app.py
  3. assemble dist\\MeTubeShip\\ = MeTube.exe + README.txt + bin\\<3 files>
  4. verify the layout, and that data\\ was NOT pre-shipped
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
SHIP = ROOT / "dist" / "MeTubeShip"
BIN_NAMES = ("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe")
TEXT_KW = {"encoding": "utf-8", "errors": "replace"}


def run(cmd: list[str], timeout: int = 1800) -> tuple[int, str]:
    print(f"$ {' '.join(cmd)}", flush=True)
    started = time.monotonic()
    proc = subprocess.run(
        cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout, **TEXT_KW
    )
    body = ((proc.stdout or "") + (proc.stderr or "")).strip()
    print(body[-4000:], flush=True)
    print(f"  -> exit {proc.returncode} in {time.monotonic() - started:.1f}s", flush=True)
    return proc.returncode, body


def sha256_prefix(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    problems: list[str] = []

    # ---- 0. preconditions -------------------------------------------------
    if not PY.exists():
        print(f"FAIL: venv python not found at {PY}")
        return 2
    for name in BIN_NAMES:
        if not (ROOT / "bin" / name).exists():
            problems.append(f"bin\\{name} is missing (the shipped folder needs all three)")

    # ---- 1. icon ----------------------------------------------------------
    if not (ROOT / "assets" / "icon.ico").exists():
        rc, _ = run([str(PY), "scripts/make_icon.py"])
        if rc != 0:
            problems.append("could not generate assets/icon.ico")

    # ---- 2. PyInstaller ---------------------------------------------------
    for stale in (ROOT / "dist" / "MeTube.exe", ROOT / "build"):
        if stale.is_dir():
            shutil.rmtree(stale, ignore_errors=True)
        elif stale.exists():
            stale.unlink()

    icon = (ROOT / "assets" / "icon.ico").resolve()
    # Absolute source paths: --add-data/--icon are resolved relative to the
    # generated .spec file (build\), not to the project root.
    rc, pyi_out = run(
        [
            str(PY), "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--noconsole",
            "--name", "MeTube",
            "--icon", str(icon),
            "--version-file", str((ROOT / "version_info.txt").resolve()),
            # CustomTkinter ships JSON themes + fonts as package data.
            "--collect-data", "customtkinter",
            # The window icon is loaded at runtime from the bundled copy.
            "--add-data", f"{icon};assets",
            "--distpath", str((ROOT / "dist").resolve()),
            "--workpath", str((ROOT / "build" / "_pyi").resolve()),
            "--specpath", str((ROOT / "build").resolve()),
            str(ROOT / "app.py"),
        ]
    )
    exe = ROOT / "dist" / "MeTube.exe"
    if rc != 0 or not exe.exists():
        problems.append(f"PyInstaller failed (exit {rc}); see output above")
        print("\n".join(problems) if problems else "")
        return 1

    # ---- 3. assemble the ship folder --------------------------------------
    if SHIP.exists():
        shutil.rmtree(SHIP, ignore_errors=True)
    (SHIP / "bin").mkdir(parents=True)

    shutil.copy2(exe, SHIP / "MeTube.exe")
    shutil.copy2(ROOT / "README.txt", SHIP / "README.txt")
    for name in BIN_NAMES:
        source = ROOT / "bin" / name
        if source.exists():
            shutil.copy2(source, SHIP / "bin" / name)
        else:
            problems.append(f"bin\\{name} missing - not copied")

    # ---- 4. verify the layout --------------------------------------------
    expected = {"MeTube.exe", "README.txt", "bin"}
    actual = {p.name for p in SHIP.iterdir()}
    if actual != expected:
        problems.append(f"dist\\MeTubeShip contents are {sorted(actual)}, expected {sorted(expected)}")
    if (SHIP / "data").exists():
        problems.append("data\\ was pre-shipped - it must be created on first run only")
    for name in BIN_NAMES:
        target = SHIP / "bin" / name
        if not target.exists():
            problems.append(f"dist\\MeTubeShip\\bin\\{name} missing")
        elif target.stat().st_size == 0:
            problems.append(f"dist\\MeTubeShip\\bin\\{name} is empty")
    if (SHIP / "bin" / "yt-dlp.exe").exists():
        rc, version = run([str(SHIP / "bin" / "yt-dlp.exe"), "--version"], timeout=120)
        if rc != 0:
            problems.append("the shipped yt-dlp.exe does not run")
        else:
            print(f"shipped yt-dlp.exe reports {version.strip()}")

    print("\n================ shipped layout ================")
    total = 0
    for path in sorted(SHIP.rglob("*")):
        if path.is_file():
            size = path.stat().st_size
            total += size
            print(f"  {path.relative_to(ROOT)}  {size:,} bytes  "
                  f"sha256:{sha256_prefix(path)[:16]}")
    print(f"  total {total:,} bytes")
    print("================================================")

    if problems:
        print("\nPROBLEMS:")
        for item in problems:
            print(f"  - {item}")
        return 1
    print("\nBUILD OK: dist\\MeTubeShip is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
