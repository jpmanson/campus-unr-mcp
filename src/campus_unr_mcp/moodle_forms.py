"""Small, dependency-free helpers for submitting Moodle mforms.

Moodle's course activity editor renders a dynamic form id on every request.
These helpers extract successful controls while preserving the values Moodle
expects on a subsequent POST.
"""

from __future__ import annotations

import html
import re

_ATTRIBUTE_RE = re.compile(
    r"([:\w-]+)(?:\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+)))?"
)


def _attrs(tag: str) -> dict[str, str]:
    return {
        key.lower(): first or second or third or ""
        for key, first, second, third in _ATTRIBUTE_RE.findall(tag)
    }


def extract_form_data(document: str) -> tuple[str, list[tuple[str, str]]]:
    """Return a Moodle editor form action and its successful controls.

    The target form has a generated ``mform1_*`` id. Unchecked checkboxes,
    unchecked radio buttons, file inputs, and submit controls are excluded in
    the same way a browser excludes them from a form submission.
    """
    start = re.search(
        r"<form[^>]*\bid=[\"']mform1_[^\"']+[\"'][^>]*>", document, re.I
    )
    if not start:
        raise ValueError("Moodle editor form not found")
    end = re.search(r"</form\s*>", document[start.end() :], re.I)
    if not end:
        raise ValueError("Moodle editor form is incomplete")

    opening = start.group(0)
    form = document[start.start() : start.end() + end.end()]
    action = html.unescape(_attrs(opening).get("action", "modedit.php"))
    data: list[tuple[str, str]] = []

    for tag in re.findall(r"<input\b[^>]*>", form, re.I):
        attrs = _attrs(tag)
        name = attrs.get("name")
        input_type = attrs.get("type", "text").lower()
        if not name or input_type in {"submit", "button", "reset", "file"}:
            continue
        if input_type in {"checkbox", "radio"} and "checked" not in attrs:
            continue
        data.append((name, html.unescape(attrs.get("value", ""))))

    for match in re.finditer(r"<textarea\b([^>]*)>(.*?)</textarea\s*>", form, re.I | re.S):
        name = _attrs("<textarea " + match.group(1) + ">").get("name")
        if name:
            data.append((name, html.unescape(match.group(2))))

    for match in re.finditer(r"<select\b([^>]*)>(.*?)</select\s*>", form, re.I | re.S):
        name = _attrs("<select " + match.group(1) + ">").get("name")
        if not name:
            continue
        options = re.findall(r"<option\b([^>]*)>(.*?)</option\s*>", match.group(2), re.I | re.S)
        if not options:
            continue
        selected = next(
            (_attrs("<option " + option_attrs + ">").get("value", "")
             for option_attrs, _ in options
             if "selected" in _attrs("<option " + option_attrs + ">")),
            None,
        )
        value = selected if selected is not None else _attrs("<option " + options[0][0] + ">").get("value", "")
        data.append((name, html.unescape(value)))

    return action, data
