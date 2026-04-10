"""
taste_parser.py — Extract structured taste tags from free-text coffee notes.

Two modes:
  1. Keyword matching (default, no API key needed)
  2. LLM-powered (optional, set OPENAI_API_KEY in .env for smarter parsing)

Usage:
    from recommendation.taste_parser import parse_taste_notes
    tags = parse_taste_notes("It was too bitter and muddy")
    # → ["bitter", "muddy"]
"""

from __future__ import annotations

import os
import re
import json
from typing import List, Optional


# ── All recognized taste descriptors ──────────────────────────

VALID_TAGS = {
    # Under-extracted signals
    "sour", "sharp", "thin", "weak", "hollow", "acidic", "tart",
    "bright", "grassy", "vegetal", "underdeveloped",
    # Over-extracted signals
    "bitter", "harsh", "dry", "astringent", "muddy", "heavy",
    "burnt", "ashy", "woody", "rubbery",
    # Mixed signals
    "sour_and_bitter", "both",
    # Balanced / positive
    "balanced", "sweet", "good", "smooth", "clean", "juicy",
    "complex", "rich", "round", "floral", "fruity", "chocolatey",
    "nutty", "caramel",
}

# ── Keyword synonym mapping (maps common phrases → canonical tags) ──

SYNONYMS = {
    # Under-extracted
    "too sour": "sour",
    "very sour": "sour",
    "sour taste": "sour",
    "acidic": "sour",
    "tart": "sour",
    "sharp": "sharp",
    "too sharp": "sharp",
    "thin": "thin",
    "watery": "thin",
    "too thin": "thin",
    "weak": "weak",
    "too weak": "weak",
    "under extracted": "sour",
    "underextracted": "sour",
    "hollow": "hollow",
    "empty": "hollow",
    "grassy": "grassy",
    "vegetal": "vegetal",
    "underdeveloped": "underdeveloped",
    "not developed": "underdeveloped",
    "bright": "bright",

    # Over-extracted
    "too bitter": "bitter",
    "very bitter": "bitter",
    "bitter taste": "bitter",
    "harsh": "harsh",
    "too harsh": "harsh",
    "dry": "dry",
    "drying": "dry",
    "dry mouth": "dry",
    "astringent": "astringent",
    "puckering": "astringent",
    "muddy": "muddy",
    "cloudy": "muddy",
    "gritty": "muddy",
    "heavy": "heavy",
    "too heavy": "heavy",
    "thick": "heavy",
    "over extracted": "bitter",
    "overextracted": "bitter",
    "burnt": "burnt",
    "burned": "burnt",
    "ashy": "ashy",
    "woody": "woody",
    "rubbery": "rubbery",

    # Mixed
    "sour and bitter": "sour_and_bitter",
    "bitter and sour": "sour_and_bitter",
    "both sour and bitter": "sour_and_bitter",

    # Balanced / positive
    "balanced": "balanced",
    "well balanced": "balanced",
    "good": "good",
    "great": "good",
    "perfect": "good",
    "delicious": "good",
    "tasty": "good",
    "sweet": "sweet",
    "smooth": "smooth",
    "clean": "clean",
    "juicy": "juicy",
    "complex": "complex",
    "rich": "rich",
    "round": "round",
    "floral": "floral",
    "flowery": "floral",
    "fruity": "fruity",
    "fruit": "fruity",
    "chocolatey": "chocolatey",
    "chocolate": "chocolatey",
    "cocoa": "chocolatey",
    "nutty": "nutty",
    "nut": "nutty",
    "caramel": "caramel",
}


def _keyword_parse(text: str) -> List[str]:
    """
    Extract taste tags from free text using keyword/synonym matching.
    Checks longer phrases first to avoid partial matches.
    """
    text_lower = text.lower().strip()
    found_tags = set()

    # Sort synonyms by length (longest first) to match phrases before words
    sorted_synonyms = sorted(SYNONYMS.items(), key=lambda x: -len(x[0]))

    for phrase, tag in sorted_synonyms:
        # Use word boundary matching for single words, substring for phrases
        if " " in phrase:
            if phrase in text_lower:
                found_tags.add(tag)
        else:
            # Match whole word only
            if re.search(r'\b' + re.escape(phrase) + r'\b', text_lower):
                found_tags.add(tag)

    # Also check for any direct VALID_TAGS that appear as whole words
    for tag in VALID_TAGS:
        if re.search(r'\b' + re.escape(tag) + r'\b', text_lower):
            found_tags.add(tag)

    return sorted(found_tags)


def _llm_parse(text: str, api_key: str) -> Optional[List[str]]:
    """
    Use OpenAI GPT-4o-mini to extract taste tags from free text.
    Returns None on any failure (caller falls back to keyword matching).
    """
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        valid_list = ", ".join(sorted(VALID_TAGS))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=200,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a coffee taste note parser. Extract taste descriptors "
                        "from the user's coffee tasting note. Return ONLY a JSON array "
                        "of strings. Use only these allowed values:\n\n"
                        f"{valid_list}\n\n"
                        "Rules:\n"
                        "- If the note describes both sour and bitter flavors, include 'sour_and_bitter'\n"
                        "- If the note is generally positive, include 'balanced' or 'good'\n"
                        "- Return an empty array [] if no taste descriptors are found\n"
                        "- Return ONLY the JSON array, no other text"
                    ),
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
        )

        raw = response.choices[0].message.content.strip()
        tags = json.loads(raw)

        # Validate: only keep tags that are in VALID_TAGS
        return [t for t in tags if t in VALID_TAGS]

    except Exception as e:
        print(f"[TasteParser] LLM parsing failed ({e}), falling back to keywords")
        return None


def parse_taste_notes(
    text: str,
    use_llm: bool = True,
    api_key: Optional[str] = None,
) -> List[str]:
    """
    Parse free-text taste notes into structured tags.

    Args:
        text:    User's tasting note, e.g. "too bitter and muddy, heavy body"
        use_llm: If True and OPENAI_API_KEY is set, uses GPT-4o-mini first
        api_key: Optional OpenAI API key (falls back to env var)

    Returns:
        List of taste tags, e.g. ["bitter", "muddy", "heavy"]
    """
    if not text or not text.strip():
        return []

    # Try LLM first if enabled
    if use_llm:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if key:
            llm_result = _llm_parse(text, key)
            if llm_result is not None:
                print(f"[TasteParser] LLM: {llm_result}")
                return llm_result

    # Fall back to keyword matching
    result = _keyword_parse(text)
    print(f"[TasteParser] Keywords: {result}")
    return result


if __name__ == "__main__":
    # Quick demo
    test_notes = [
        "It was too bitter and muddy, with a heavy body",
        "Sour, thin, and kind of hollow tasting",
        "Really well balanced, sweet chocolate notes",
        "It tasted both sour and bitter at the same time, weird",
        "Pretty good, smooth and clean",
        "Harsh and dry, almost burnt tasting",
        "watery and weak, not much flavor",
    ]

    print("Taste Note Parser Demo (keyword mode)\n")
    for note in test_notes:
        tags = parse_taste_notes(note, use_llm=False)
        print(f"  \"{note}\"")
        print(f"  → {tags}\n")
