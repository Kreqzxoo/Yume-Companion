"""Block-letter banner in the same style as the original Soul of Waifu start screen
(FIGlet "ANSI Shadow" look, 6 rows high). Unknown characters are skipped."""
from __future__ import annotations

_RAW = r"""
=A
 █████╗
██╔══██╗
███████║
██╔══██║
██║  ██║
╚═╝  ╚═╝
=B
██████╗
██╔══██╗
██████╔╝
██╔══██╗
██████╔╝
╚═════╝
=C
 ██████╗
██╔════╝
██║
██║
╚██████╗
 ╚═════╝
=D
██████╗
██╔══██╗
██║  ██║
██║  ██║
██████╔╝
╚═════╝
=E
███████╗
██╔════╝
█████╗
██╔══╝
███████╗
╚══════╝
=F
███████╗
██╔════╝
█████╗
██╔══╝
██║
╚═╝
=G
 ██████╗
██╔════╝
██║  ███╗
██║   ██║
╚██████╔╝
 ╚═════╝
=H
██╗  ██╗
██║  ██║
███████║
██╔══██║
██║  ██║
╚═╝  ╚═╝
=I
██╗
██║
██║
██║
██║
╚═╝
=J
     ██╗
     ██║
     ██║
██   ██║
╚█████╔╝
 ╚════╝
=K
██╗  ██╗
██║ ██╔╝
█████╔╝
██╔═██╗
██║  ██╗
╚═╝  ╚═╝
=L
██╗
██║
██║
██║
███████╗
╚══════╝
=M
███╗   ███╗
████╗ ████║
██╔████╔██║
██║╚██╔╝██║
██║ ╚═╝ ██║
╚═╝     ╚═╝
=N
███╗   ██╗
████╗  ██║
██╔██╗ ██║
██║╚██╗██║
██║ ╚████║
╚═╝  ╚═══╝
=O
 ██████╗
██╔═══██╗
██║   ██║
██║   ██║
╚██████╔╝
 ╚═════╝
=P
██████╗
██╔══██╗
██████╔╝
██╔═══╝
██║
╚═╝
=Q
 ██████╗
██╔═══██╗
██║   ██║
██║▄▄ ██║
╚██████╔╝
 ╚══▀▀═╝
=R
██████╗
██╔══██╗
██████╔╝
██╔══██╗
██║  ██║
╚═╝  ╚═╝
=S
███████╗
██╔════╝
███████╗
╚════██║
███████║
╚══════╝
=T
████████╗
╚══██╔══╝
   ██║
   ██║
   ██║
   ╚═╝
=U
██╗   ██╗
██║   ██║
██║   ██║
██║   ██║
╚██████╔╝
 ╚═════╝
=V
██╗   ██╗
██║   ██║
██║   ██║
╚██╗ ██╔╝
 ╚████╔╝
  ╚═══╝
=W
██╗    ██╗
██║    ██║
██║ █╗ ██║
██║███╗██║
╚███╔███╔╝
 ╚══╝╚══╝
=X
██╗  ██╗
╚██╗██╔╝
 ╚███╔╝
 ██╔██╗
██╔╝ ██╗
╚═╝  ╚═╝
=Y
██╗   ██╗
╚██╗ ██╔╝
 ╚████╔╝
  ╚██╔╝
   ██║
   ╚═╝
=Z
███████╗
╚══███╔╝
  ███╔╝
 ███╔╝
███████╗
╚══════╝
=0
 ██████╗
██╔═████╗
██║██╔██║
████╔╝██║
╚██████╔╝
 ╚═════╝
=1
 ██╗
███║
╚██║
 ██║
 ██║
 ╚═╝
=2
██████╗
╚════██╗
 █████╔╝
██╔═══╝
███████╗
╚══════╝
=3
██████╗
╚════██╗
 █████╔╝
 ╚═══██╗
██████╔╝
╚═════╝
=4
██╗  ██╗
██║  ██║
███████║
╚════██║
     ██║
     ╚═╝
=5
███████╗
██╔════╝
███████╗
╚════██║
███████║
╚══════╝
=6
 ██████╗
██╔════╝
███████╗
██╔═══██╗
╚██████╔╝
 ╚═════╝
=7
███████╗
╚════██║
    ██╔╝
   ██╔╝
   ██║
   ╚═╝
=8
 █████╗
██╔══██╗
╚█████╔╝
██╔══██╗
╚█████╔╝
 ╚════╝
=9
 █████╗
██╔══██╗
╚██████║
 ╚═══██║
 █████╔╝
 ╚════╝
=-


█████╗
╚════╝


=.




██╗
╚═╝
=_





███████╗
=!
██╗
██║
██║
╚═╝
██╗
╚═╝
=?
██████╗
╚════██╗
  ▄███╔╝
  ▀▀══╝
  ██╗
  ╚═╝
"""

ROWS = 6


def _parse():
    glyphs: dict[str, list[str]] = {}
    current, buf = None, []
    for line in _RAW.split("\n"):
        if line.startswith("="):
            if current is not None:
                glyphs[current] = buf
            current, buf = line[1:2], []
        elif current is not None:
            buf.append(line)
    if current is not None:
        glyphs[current] = buf
    out = {}
    for ch, rows in glyphs.items():
        rows = rows[:ROWS]
        while len(rows) < ROWS:
            rows.append("")
        width = max(len(r) for r in rows)
        out[ch] = [r.ljust(width) for r in rows]
    out[" "] = ["   "] * ROWS
    return out


GLYPHS = _parse()


def render_word(text: str) -> list[str]:
    """Render one line of text; returns ROWS strings (unknown characters skipped)."""
    rows = [""] * ROWS
    for ch in text.upper():
        g = GLYPHS.get(ch)
        if not g:
            continue
        for i in range(ROWS):
            rows[i] += g[i]
    return rows


def render_banner(text: str, max_width: int = 100) -> list[str]:
    """Render text, wrapping at spaces so no row is wider than max_width.

    Returns the banner as text lines (blocks separated by no blank line)."""
    words = text.split()
    lines: list[list[str]] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and max(len(r) for r in render_word(candidate)) > max_width:
            lines.append(render_word(current))
            current = word
        else:
            current = candidate
    if current:
        lines.append(render_word(current))
    out: list[str] = []
    for block in lines:
        out.extend(r.rstrip() for r in block)
    return out if any(l.strip() for l in out) else []
