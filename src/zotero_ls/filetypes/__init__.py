import re

from zotero_ls.filetypes import tex


def get_cite_patterns(filetype: str) -> re.Pattern[str]:
    """Get the cite patterns for the given filetype"""

    match filetype:
        case "tex" | "latex":
            return tex.CITE_PATTERNS
        case _:
            raise ValueError(f"Unknown/unsupported filetype {filetype}")


def get_filetype_from_extension(ext: str) -> str:
    # Remove preceding dot, if any
    if ext[0] == ".":
        ext = ext[1:]

    match ext:
        case "tex" | "latex":
            return ext
        case "md" | "qmd" | "markdown":
            return "markdown"
        case _:
            raise ValueError(f"Unknown/unsupported file extension {ext}")
