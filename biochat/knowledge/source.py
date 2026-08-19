"""Knowledge source model and Markdown parser.

A :class:`KnowledgeSource` is the canonical in-memory representation of a
know-how document.  The parser recognises the Biochat know-how Markdown
layout::

    # Title
    ---
    ## Metadata
    **Short Description**: ...
    **License**: ...
    **Commercial Use**: ✅ Allowed
    ## Overview
    ...

It replaces the upstream ``biochat/know_how/loader.py`` parsing loops with a
section-based parser producing the same metadata dictionary and the same
``content_without_metadata`` output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Section / field patterns ──────────────────────────────────────────
_H1_RE = re.compile(r"^# (.+)$")
_H2_RE = re.compile(r"^##\s+(.+)$")
_FIELD_RE = re.compile(r"^\*\*(?P<field>[^*]+)\*\*\s*:\s*(?P<value>.*)$")
_SEPARATOR = "---"

_DESCRIPTION_MAX_LEN = 200
_SKIP_FILENAMES = {"README.MD", "QUICK_START.MD"}


@dataclass
class KnowledgeSource:
    """A single knowledge document registered with the agent."""

    id: str
    name: str
    description: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)
    origin: str | None = None          # source file path; None for programmatic docs
    content_without_metadata: str = ""


def should_load_file(filename: str) -> bool:
    """Skip meta documentation (README, QUICK_START, ALL-CAPS filenames)."""
    stem = filename.rsplit(".", 1)[0]
    return filename not in _SKIP_FILENAMES and not stem.isupper()


def _fallback_title(filename: str) -> str:
    return filename.replace("_", " ").replace(".md", "").title()


def _parse_metadata_block(lines: list[str], start: int, end: int) -> dict[str, str]:
    """Parse ``**Field**: value`` entries (with continuation lines) from the
    metadata block spanning lines [start, end)."""
    metadata: dict[str, str] = {}
    current_field: str | None = None
    for line in lines[start:end]:
        match = _FIELD_RE.match(line.strip())
        if match:
            current_field = match.group("field").lower().replace(" ", "_")
            metadata[current_field] = match.group("value").strip()
        elif current_field and line.strip() and line.strip() != _SEPARATOR:
            if line.lstrip().startswith("- "):
                item = line.lstrip()[2:].strip()
                metadata[current_field] = (
                    metadata[current_field] + ", " + item
                    if metadata[current_field] else item
                )
            elif not line.lstrip().startswith("```"):
                metadata[current_field] = (
                    metadata[current_field] + " " + line.strip()
                    if metadata[current_field] else line.strip()
                )
    return metadata


def _extract_description(lines: list[str], metadata_end: int) -> str:
    """Description = the ``## Overview`` section, or the first paragraph
    after the title.  Truncated to ``_DESCRIPTION_MAX_LEN`` chars."""
    overview_parts: list[str] = []
    in_overview = False
    for line in lines:
        h2 = _H2_RE.match(line.strip())
        if h2 and h2.group(1) == "Overview":
            in_overview = True
            continue
        if h2:
            in_overview = False
            continue
        if in_overview and line.strip():
            overview_parts.append(line.strip())
    if overview_parts:
        description = " ".join(overview_parts)
    else:
        description = ""
        found_title = False
        for line in lines:
            if _H1_RE.match(line.strip()):
                found_title = True
                continue
            if found_title and line.strip() and not line.startswith("#"):
                description = line.strip()
                break
    if len(description) > _DESCRIPTION_MAX_LEN:
        description = description[: _DESCRIPTION_MAX_LEN - 3] + "..."
    return description


def _strip_metadata_block(lines: list[str]) -> str:
    """Content without the metadata block and its surrounding separators.

    Mirrors the historical loader's behavior exactly so the document body
    the agent sees is unchanged:
    - the separator run above the block (blank lines included) is removed;
    - the ``## Metadata`` heading and its fields are removed;
    - a closing ``---`` run also ends the removal, but blank lines between
      that run and the next section are kept;
    - without a closing separator, removal stops at the next ``##`` heading.
    """
    keep: list[str] = []
    found_first_h1 = False
    in_metadata = False
    skip_until_heading = False

    for line in lines:
        stripped = line.strip()

        # Keep the document title (first H1)
        if stripped.startswith("# ") and not found_first_h1:
            keep.append(line)
            found_first_h1 = True
            continue

        if stripped.startswith("## Metadata"):
            in_metadata = True
            continue

        if stripped == _SEPARATOR:
            if not in_metadata:
                # Separator above (or after) the block — drop it and
                # everything until the next section heading.
                skip_until_heading = True
                continue
            in_metadata = False
            skip_until_heading = False
            continue

        if in_metadata or skip_until_heading:
            # End of the skipped region at a non-Metadata heading
            if stripped.startswith("##") and "Metadata" not in stripped:
                in_metadata = False
                skip_until_heading = False
                keep.append(line)
            continue

        keep.append(line)

    result = "\n".join(keep)
    while "\n\n\n\n" in result:
        result = result.replace("\n\n\n\n", "\n\n\n")
    return result.strip()


def parse_markdown_source(raw: str, filename: str, origin: str | None = None) -> KnowledgeSource:
    """Parse one know-how Markdown document into a :class:`KnowledgeSource`."""
    lines = raw.split("\n")

    title: str | None = None
    metadata_start: int | None = None
    metadata_end: int | None = None
    for i, line in enumerate(lines):
        if title is None:
            h1 = _H1_RE.match(line.strip())
            if h1:
                title = h1.group(1).strip()
        h2 = _H2_RE.match(line.strip())
        if h2 and h2.group(1) == "Metadata" and metadata_start is None:
            metadata_start = i
        elif h2 and metadata_start is not None and metadata_end is None:
            metadata_end = i

    if title is None:
        title = _fallback_title(filename)
    if metadata_start is None:
        metadata_start, metadata_end = 0, 0

    metadata = _parse_metadata_block(lines, metadata_start, metadata_end)
    description = (
        metadata.get("short_description")
        if metadata.get("short_description")
        else _extract_description(lines, metadata_end)
    )

    doc_id = filename.rsplit(".", 1)[0]
    return KnowledgeSource(
        id=doc_id,
        name=title,
        description=description,
        content=raw,
        metadata=metadata,
        origin=origin,
        content_without_metadata=_strip_metadata_block(lines),
    )
