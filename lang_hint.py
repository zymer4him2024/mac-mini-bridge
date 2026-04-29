"""Language-detection helpers for prompt-language steering.

Gemma's persona-following is weak when the prompt template is in English but
the email body is in Korean / Japanese / Chinese — the dominant English text
biases output toward English. We compensate by detecting the body's dominant
script and appending an explicit directive in BOTH English and the target
language at the end of the user message.
"""

import re


_HANGUL = re.compile(r"[가-힯ᄀ-ᇿ㄰-㆏]")
_HIRAGANA_KATAKANA = re.compile(r"[぀-ゟ゠-ヿ]")
_CJK_UNIFIED = re.compile(r"[一-鿿]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")


def detect_dominant_script(text: str) -> str:
    """Return one of: 'korean', 'japanese', 'chinese', 'latin', 'unknown'.

    Decision: whichever script has the highest character count, with a
    minimum-presence floor (>=20 chars) so a 2-character snippet doesn't
    flip the directive.
    """
    if not text:
        return "unknown"
    counts = {
        "korean": len(_HANGUL.findall(text)),
        "japanese": len(_HIRAGANA_KATAKANA.findall(text)),
        "chinese": len(_CJK_UNIFIED.findall(text)),
        "latin": len(_LATIN_LETTER.findall(text)),
    }
    # Japanese typically has both kana and CJK; if kana present, count the
    # CJK as Japanese kanji rather than Chinese.
    if counts["japanese"] > 0:
        counts["japanese"] += counts["chinese"]
        counts["chinese"] = 0
    top_script, top_count = max(counts.items(), key=lambda kv: kv[1])
    if top_count < 20:
        return "unknown"
    return top_script


_DIRECTIVES = {
    "korean": (
        "IMPORTANT — language requirement: ALL string values in the JSON output "
        "(context, key_points, asks, suggested_response) MUST be written in Korean. "
        "Do not translate to English.\n"
        "중요 — 언어 요구사항: JSON 출력의 모든 문자열 값(context, key_points, asks, "
        "suggested_response)은 반드시 한국어로 작성해야 합니다. 영어로 번역하지 마십시오."
    ),
    "japanese": (
        "IMPORTANT — language requirement: ALL string values in the JSON output "
        "MUST be written in Japanese. Do not translate to English.\n"
        "重要 — 言語要件: JSON出力のすべての文字列値は必ず日本語で記述してください。"
        "英語に翻訳しないでください。"
    ),
    "chinese": (
        "IMPORTANT — language requirement: ALL string values in the JSON output "
        "MUST be written in Chinese. Do not translate to English.\n"
        "重要 — 语言要求：JSON 输出中所有字符串值必须用中文书写。请勿翻译为英文。"
    ),
}


def language_directive(script: str) -> str:
    """Return a strong language directive for the given script, or '' for
    latin/unknown (no directive needed)."""
    return _DIRECTIVES.get(script, "")
