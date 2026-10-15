"""Embed screenshots into a single HTML page (base64) so they can be reviewed.

Usage: python scripts/make_view.py OUT.html SHOT.png [SHOT2.png ...]
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path


def embed(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<figure><figcaption>{path.name}</figcaption><img src="data:image/png;base64,{data}"></figure>'


def main() -> int:
    out = Path(sys.argv[1])
    shots = [Path(p) for p in sys.argv[2:]]
    body = "\n".join(embed(s) for s in shots if s.is_file())
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>MeTube evidence</title>
<style>
body {{ background:#111; color:#ddd; font:14px/1.4 Segoe UI, sans-serif; margin:16px; }}
figure {{ margin:0 0 24px; }}
figcaption {{ font-weight:600; margin-bottom:6px; color:#9ad; }}
img {{ max-width:100%; border:1px solid #444; display:block; }}
</style></head><body>
<h1>MeTube evidence</h1>
{body}
</body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
