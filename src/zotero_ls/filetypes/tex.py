import re

CITE_PATTERNS: re.Pattern[str] = re.compile(
    "|".join(  # alternation between patterns
        map(
            lambda pat: f"(?:{pat})",  # non-capture group for the sub-pattern
            [r"\\(?:[a-zA-Z]*cite|Cite)[a-zA-Z]*\*?(?:\s*\[[^]]*\]|\s*\<[^>]*\>){0,2}\s*\{[^}]*$"],
        )
    )
)
"""Compiled regex pattern for potential citation triggers"""
