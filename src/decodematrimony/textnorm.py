"""🌸 NLTK-powered label normaliser for Stata value labels (regions, ethnicity, etc.). ✨

DHS value labels arrive as messy strings ("Khyber Pakhtunkhwa ", "KPK/NWFP").
We tokenise with NLTK's rule-based tokenizer (no corpus downloads needed),
casefold, drop punctuation tokens, and apply an explicit alias table. 🎀
"""
from __future__ import annotations

from nltk.tokenize import wordpunct_tokenize

_ALIASES: dict[str, str] = {
    "nwfp": "khyber pakhtunkhwa",
    "kpk": "khyber pakhtunkhwa",
    "khyber": "khyber pakhtunkhwa",
    "fata": "fata",
    "ajk": "azad jammu kashmir",
    "gb": "gilgit baltistan",
}


def normalise_label(label: str) -> str:
    """🧸 'KPK/NWFP ' -> 'khyber pakhtunkhwa'. Unknown labels are just cleaned."""
    tokens = [t.casefold() for t in wordpunct_tokenize(label) if t.isalnum()]
    if not tokens:
        return "unknown"
    joined = " ".join(tokens)
    for t in tokens:
        if t in _ALIASES and len(tokens) <= 2:
            return _ALIASES[t]
    return _ALIASES.get(joined, joined)
