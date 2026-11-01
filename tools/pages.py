"""Writing a page from a template: the data goes in as JSON, and the page is written either whole (a file a browser
opens) or as a fragment (its head and body content without the document skeleton, the form a published Artifact
takes; the publisher adds the skeleton).

A template is the page's head content (title, styles), a line ``<!--body-->``, then its body content. Its data goes
where the template has ``__DATA_JSON__``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEMPLATES = Path(__file__).resolve().parent / "templates"
BODY_MARK = "<!--body-->"
DATA_MARK = "__DATA_JSON__"
# The same small reset the Artifact skeleton carries, so a page looks the same opened from disk and published.
_RESET = ("<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
          "body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>")


def render(template: str, data: Any, *, fragment: bool) -> str:
    """The page for this template and data. JSON's ``</`` is escaped so the data cannot close its script tag."""
    text = (TEMPLATES / template).read_text(encoding="utf-8")
    if text.count(BODY_MARK) != 1 or text.count(DATA_MARK) != 1:
        raise ValueError(f"{template}: a template needs one {BODY_MARK} and one {DATA_MARK}")
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    head, body = text.replace(DATA_MARK, payload).split(BODY_MARK)
    if fragment:
        return head.rstrip() + "\n" + body.lstrip()
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
            f"{_RESET}\n{head.strip()}\n</head>\n<body>\n{body.strip()}\n</body>\n</html>\n")


def write(path: Path, template: str, data: Any, *, fragment: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(template, data, fragment=fragment), encoding="utf-8")
    return path
