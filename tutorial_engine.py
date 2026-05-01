from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi


class TutorialBuildError(Exception):
    pass


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "he",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "ours",
    "she",
    "so",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "those",
    "to",
    "too",
    "us",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "you",
    "your",
}

VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")
WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9'-]+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
NOISE_TOKENS = {"[music]", "[applause]", "[laughter]", "(music)", "(applause)"}


@dataclass
class TranscriptChunk:
    start_seconds: float
    text: str
    word_count: int


def build_tutorial_from_url(url: str) -> dict[str, Any]:
    video_id = extract_video_id(url)
    transcript_entries = fetch_transcript(video_id)
    chunks = chunk_transcript(transcript_entries)

    if not chunks:
        raise TutorialBuildError(
            "No tutorial content could be extracted from this video transcript."
        )

    full_text = " ".join(entry["text"] for entry in transcript_entries)
    top_keywords = extract_keywords(full_text, limit=8)
    video_title = fetch_video_title(video_id) or infer_tutorial_title(top_keywords)

    steps = []
    for index, chunk in enumerate(chunks, start=1):
        sentences = split_sentences(chunk.text)
        step_keywords = extract_keywords(chunk.text, limit=4)
        step_summary = summarize_sentences(sentences)
        key_points = select_key_points(sentences)
        focus_term = step_keywords[0] if step_keywords else "the core idea"

        steps.append(
            {
                "id": f"step-{index}",
                "title": make_step_title(index, step_keywords, sentences),
                "timestamp": format_timestamp(chunk.start_seconds),
                "summary": step_summary,
                "key_points": key_points,
                "keywords": [word.title() for word in step_keywords],
                "check_yourself": {
                    "question": f"How does this part explain {focus_term}?",
                    "answer": step_summary,
                },
            }
        )

    total_word_count = sum(chunk.word_count for chunk in chunks)
    estimated_minutes = max(1, round(total_word_count / 180))

    objective_terms = ", ".join(word.title() for word in top_keywords[:3])
    objective = (
        f"Understand the video through {len(steps)} guided steps focused on {objective_terms}."
        if objective_terms
        else "Understand the video through guided concept-focused learning steps."
    )

    return {
        "video_id": video_id,
        "source_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": video_title,
        "objective": objective,
        "estimated_minutes": estimated_minutes,
        "steps": steps,
        "glossary": build_glossary(full_text, top_keywords),
    }


def extract_video_id(url_or_id: str) -> str:
    candidate = url_or_id.strip()
    if VIDEO_ID_RE.fullmatch(candidate):
        return candidate

    try:
        parsed = urllib.parse.urlparse(candidate)
    except Exception as exc:
        raise TutorialBuildError("Invalid YouTube URL.") from exc

    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    video_id = None
    if "youtu.be" in host and path_parts:
        video_id = path_parts[0]
    elif "youtube.com" in host or "youtube-nocookie.com" in host:
        if parsed.path == "/watch":
            video_id = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
        elif path_parts and path_parts[0] in {"embed", "shorts", "live"}:
            video_id = path_parts[1] if len(path_parts) > 1 else None

    if not video_id or not VIDEO_ID_RE.fullmatch(video_id):
        raise TutorialBuildError(
            "Could not parse a valid YouTube video id from the provided URL."
        )

    return video_id


def fetch_transcript(video_id: str) -> list[dict[str, Any]]:
    raw_entries = _read_transcript_entries(video_id)
    cleaned_entries: list[dict[str, Any]] = []

    for entry in raw_entries:
        text = clean_caption_text(str(entry.get("text", "")))
        if not text:
            continue
        cleaned_entries.append(
            {
                "text": text,
                "start": float(entry.get("start", 0.0)),
                "duration": float(entry.get("duration", 0.0)),
            }
        )

    if not cleaned_entries:
        raise TutorialBuildError(
            "Transcript exists, but it did not contain usable educational text."
        )

    return cleaned_entries


def _read_transcript_entries(video_id: str) -> list[dict[str, Any]]:
    preferred_languages = ["en", "en-US", "en-GB"]

    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            return YouTubeTranscriptApi.get_transcript(
                video_id, languages=preferred_languages
            )

        api = YouTubeTranscriptApi()
        try:
            fetched = api.fetch(video_id, languages=preferred_languages)
        except TypeError:
            fetched = api.fetch(video_id)

        normalized: list[dict[str, Any]] = []
        for item in fetched:
            if isinstance(item, dict):
                normalized.append(item)
            else:
                normalized.append(
                    {
                        "text": getattr(item, "text", ""),
                        "start": float(getattr(item, "start", 0.0)),
                        "duration": float(getattr(item, "duration", 0.0)),
                    }
                )
        return normalized
    except Exception as exc:
        message = str(exc).lower()
        if isinstance(exc, ET.ParseError) or "no element found" in message:
            raise TutorialBuildError(
                "Transcript response was empty. Retry in a moment or use a different public video with captions."
            ) from exc
        if "transcript" in message and "disabled" in message:
            raise TutorialBuildError(
                "Transcripts are disabled for this video. Pick a video with captions enabled."
            ) from exc
        if "no transcript" in message or "could not retrieve" in message:
            raise TutorialBuildError(
                "No transcript found for this video. Try one with English captions."
            ) from exc
        if "video unavailable" in message:
            raise TutorialBuildError(
                "Video is unavailable. Check the URL and visibility settings."
            ) from exc
        raise TutorialBuildError(
            "Unable to fetch transcript. Check URL validity and try another video."
        ) from exc


def clean_caption_text(text: str) -> str:
    cleaned = text.replace("\n", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if cleaned.lower() in NOISE_TOKENS:
        return ""
    return cleaned


def chunk_transcript(
    entries: list[dict[str, Any]], target_words_per_chunk: int = 160, max_chunks: int = 8
) -> list[TranscriptChunk]:
    chunks: list[TranscriptChunk] = []
    current_text_parts: list[str] = []
    current_start = 0.0
    current_word_count = 0

    for entry in entries:
        words_in_entry = len(WORD_RE.findall(entry["text"]))
        if not current_text_parts:
            current_start = float(entry["start"])

        if (
            current_text_parts
            and current_word_count + words_in_entry > target_words_per_chunk
        ):
            chunk_text = " ".join(current_text_parts).strip()
            if chunk_text:
                chunks.append(
                    TranscriptChunk(
                        start_seconds=current_start,
                        text=chunk_text,
                        word_count=current_word_count,
                    )
                )
            current_text_parts = []
            current_word_count = 0
            current_start = float(entry["start"])

        current_text_parts.append(entry["text"])
        current_word_count += words_in_entry

    if current_text_parts:
        chunk_text = " ".join(current_text_parts).strip()
        if chunk_text:
            chunks.append(
                TranscriptChunk(
                    start_seconds=current_start,
                    text=chunk_text,
                    word_count=current_word_count,
                )
            )

    return chunks[:max_chunks]


def split_sentences(text: str) -> list[str]:
    rough = SENTENCE_SPLIT_RE.split(text)
    return [sentence.strip() for sentence in rough if len(sentence.strip()) > 20]


def summarize_sentences(sentences: list[str]) -> str:
    if not sentences:
        return "This section introduces a key concept from the video."
    selected = sentences[:2]
    summary = " ".join(selected)
    return summary if len(summary) <= 420 else f"{summary[:417]}..."


def select_key_points(sentences: list[str], limit: int = 3) -> list[str]:
    if not sentences:
        return ["Pay attention to the speaker's main explanation in this segment."]

    candidates = []
    seen = set()
    for sentence in sentences:
        normalized = sentence.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if len(sentence) >= 35:
            candidates.append(sentence)
        if len(candidates) == limit:
            break

    if not candidates:
        return [sentences[0]]
    return candidates


def extract_keywords(text: str, limit: int = 6) -> list[str]:
    words = [word.lower() for word in WORD_RE.findall(text)]
    counts = Counter(
        word for word in words if len(word) > 3 and word not in STOP_WORDS and not word.isdigit()
    )
    return [word for word, _ in counts.most_common(limit)]


def make_step_title(index: int, keywords: list[str], sentences: list[str]) -> str:
    if len(keywords) >= 2:
        return f"Step {index}: {keywords[0].title()} and {keywords[1].title()}"
    if keywords:
        return f"Step {index}: Understanding {keywords[0].title()}"
    if sentences:
        trimmed = sentences[0][:52].rstrip(".,:;!?")
        return f"Step {index}: {trimmed}"
    return f"Step {index}: Core Concept"


def infer_tutorial_title(keywords: list[str]) -> str:
    if len(keywords) >= 2:
        return f"Interactive Tutorial: {keywords[0].title()} & {keywords[1].title()}"
    if keywords:
        return f"Interactive Tutorial: {keywords[0].title()}"
    return "Interactive YouTube Concept Tutorial"


def build_glossary(full_text: str, keywords: list[str]) -> list[dict[str, str]]:
    if not keywords:
        return []

    sentences = split_sentences(full_text)
    glossary: list[dict[str, str]] = []

    for keyword in keywords[:6]:
        keyword_lower = keyword.lower()
        context_sentence = next(
            (sentence for sentence in sentences if keyword_lower in sentence.lower()), ""
        )
        if context_sentence:
            definition = context_sentence if len(context_sentence) <= 180 else f"{context_sentence[:177]}..."
        else:
            definition = f"A recurring concept discussed throughout this tutorial."

        glossary.append({"term": keyword.title(), "definition": definition})

    return glossary


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def fetch_video_title(video_id: str) -> str | None:
    oembed_url = (
        "https://www.youtube.com/oembed?"
        + urllib.parse.urlencode(
            {"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}
        )
    )
    try:
        with urllib.request.urlopen(oembed_url, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8"))
            title = str(payload.get("title", "")).strip()
            return title or None
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None
