import argparse
import base64
import json
import math
import os
import random
import re
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from xml.etree import ElementTree as ET

import dotenv
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

try:
    from moviepy.editor import AudioFileClip, CompositeVideoClip, ImageClip, VideoClip, VideoFileClip
except ImportError:
    from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, VideoClip, VideoFileClip

from database import SessionLocal
from models import GeneratedReel

dotenv.load_dotenv()

SITEMAP_URL = os.getenv("REEL_SITEMAP_URL", "https://huuli.tech/sitemap.xml")
ARTICLE_PREFIX = os.getenv("REEL_ARTICLE_PREFIX", "https://huuli.tech/articles")
ARTIFACTS_ROOT = Path(
    os.getenv("REEL_ARTIFACTS_DIR", os.path.join(os.getcwd(), "artifacts", "reels"))
)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
VIDEO_SIZE = (720, 1280)
VIDEO_FPS = 24
DEFAULT_CTA = os.getenv("REEL_CALL_TO_ACTION", "Follow for simple legal tips.")
STEP_ORDER = ["topic", "script", "voice", "visuals", "edit"]


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [Reels] {message}")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return normalized or f"reel-{int(datetime.now().timestamp())}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_text(path: Path, value: str) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(value)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def sentence_split(text: str) -> List[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]


def trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).rstrip(",;:-") + "."


def select_font_path() -> Optional[str]:
    candidates = [
        os.getenv("REEL_FONT_PATH"),
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


FONT_PATH = select_font_path()


def load_font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    if FONT_PATH:
        try:
            return ImageFont.truetype(FONT_PATH, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def get_articles_from_sitemap() -> List[str]:
    log(f"Fetching sitemap: {SITEMAP_URL}")
    response = requests.get(SITEMAP_URL, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: List[str] = []
    for node in root.findall("ns:url/ns:loc", namespace):
        url = clean_text(node.text or "")
        if url.startswith(ARTICLE_PREFIX):
            urls.append(url)
    return urls


def extract_article_text(soup: BeautifulSoup) -> str:
    selectors = [
        "article",
        "main article",
        "main",
        ".post-content",
        ".entry-content",
        ".article-content",
        ".prose",
    ]
    paragraphs: List[str] = []
    for selector in selectors:
        container = soup.select_one(selector)
        if not container:
            continue
        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in container.select("p")
            if len(clean_text(node.get_text(" ", strip=True))) >= 40
        ]
        if paragraphs:
            break

    if not paragraphs:
        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in soup.select("p")
            if len(clean_text(node.get_text(" ", strip=True))) >= 40
        ]

    unique_paragraphs: List[str] = []
    seen = set()
    for paragraph in paragraphs:
        if paragraph not in seen:
            seen.add(paragraph)
            unique_paragraphs.append(paragraph)

    return "\n\n".join(unique_paragraphs[:12])


def fetch_article(url: str) -> Dict[str, Any]:
    log(f"Fetching article: {url}")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title_candidates = [
        soup.select_one('meta[property="og:title"]'),
        soup.select_one("title"),
        soup.select_one("h1"),
    ]
    title = ""
    for candidate in title_candidates:
        if candidate:
            title = clean_text(candidate.get("content") or candidate.get_text(" ", strip=True))
            if title:
                break

    article_text = extract_article_text(soup)
    excerpt = trim_words(article_text.replace("\n", " "), 60)
    return {
        "url": url,
        "title": title or slugify(url).replace("-", " ").title(),
        "text": article_text,
        "excerpt": excerpt,
        "fetched_at": datetime.now().isoformat(),
    }


def build_fallback_sections(article: Dict[str, Any]) -> Dict[str, str]:
    title = article["title"]
    sentences = sentence_split(article["text"])
    core = sentences[0] if sentences else title
    support = sentences[1] if len(sentences) > 1 else article["excerpt"]

    lower_title = title.lower()
    if "phone" in lower_title or "digital" in lower_title:
        hook = "Your phone is not just another pocket item."
    elif "police" in lower_title:
        hook = "Police powers usually stop where your rights begin."
    elif "contract" in lower_title:
        hook = "A bad contract can cost more than most people expect."
    elif "court" in lower_title:
        hook = "Court rules often matter before your case even starts."
    else:
        hook = f"One legal detail in this story can change what happens next."

    problem = trim_words(core, 16)
    explanation = trim_words(support or article["excerpt"], 22)
    takeaway = trim_words(
        "Pause before you act, confirm the rule, and get advice if the facts are not clear.",
        16,
    )

    return {
        "hook": trim_words(hook, 12),
        "problem": problem,
        "explanation": explanation,
        "takeaway": takeaway,
    }


def call_openai_for_script(article: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if not OPENAI_API_KEY or not OPENAI_MODEL:
        return None

    prompt = (
        "Write a 30-second legal educational reel script as strict JSON with keys "
        '"hook", "problem", "explanation", "takeaway". '
        "Use very simple language, one legal insight, a strong hook, and keep the total "
        f"spoken words across all values under 80.\n\nTitle: {article['title']}\n\n"
        f"Article excerpt:\n{article['excerpt']}\n\nArticle text:\n{article['text'][:4000]}"
    )
    response = requests.post(
        f"{OPENAI_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write short legal education scripts for mobile reels. "
                        "Return only valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return {
        "hook": clean_text(parsed.get("hook", "")),
        "problem": clean_text(parsed.get("problem", "")),
        "explanation": clean_text(parsed.get("explanation", "")),
        "takeaway": clean_text(parsed.get("takeaway", "")),
    }


def normalize_sections(sections: Dict[str, str]) -> Dict[str, str]:
    budgets = {
        "hook": 12,
        "problem": 16,
        "explanation": 24,
        "takeaway": 16,
    }
    normalized = {}
    for key in ["hook", "problem", "explanation", "takeaway"]:
        value = clean_text(sections.get(key, ""))
        normalized[key] = trim_words(value, budgets[key]) if value else ""

    combined = " ".join(normalized.values()).strip()
    words = combined.split()
    if len(words) > 80:
        trimmed = words[:80]
        rebuilt = " ".join(trimmed)
        parts = sentence_split(rebuilt)
        normalized["hook"] = trim_words(normalized["hook"], 10)
        normalized["problem"] = trim_words(normalized["problem"], 14)
        normalized["explanation"] = trim_words(normalized["explanation"], 18)
        normalized["takeaway"] = trim_words(normalized["takeaway"], 12)
        if not parts:
            normalized["explanation"] = trim_words(rebuilt, 18)
    return normalized


def narration_text_from_sections(sections: Dict[str, str]) -> str:
    return " ".join(
        clean_text(sections[key])
        for key in ["hook", "problem", "explanation", "takeaway"]
        if clean_text(sections.get(key, ""))
    ).strip()


def build_even_word_timestamps(text: str, total_duration: float) -> List[Dict[str, Any]]:
    words = re.findall(r"\S+", text)
    if not words:
        return []
    duration = max(total_duration, len(words) * 0.35)
    slot = duration / len(words)
    timestamps = []
    cursor = 0.0
    for word in words:
        start = cursor
        end = min(duration, cursor + slot)
        timestamps.append({"word": word, "start": round(start, 3), "end": round(end, 3)})
        cursor = end
    return timestamps


def character_alignment_to_words(text: str, alignment: Dict[str, Any]) -> List[Dict[str, Any]]:
    characters = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or alignment.get("character_start_times") or []
    ends = alignment.get("character_end_times_seconds") or alignment.get("character_end_times") or []
    if not characters or not starts:
        return []

    words: List[Dict[str, Any]] = []
    current_word: List[str] = []
    current_start: Optional[float] = None
    current_end: Optional[float] = None

    for index, character in enumerate(characters):
        start = float(starts[index])
        end = float(ends[index]) if index < len(ends) else start + 0.12
        if character.isspace():
            if current_word:
                words.append(
                    {
                        "word": "".join(current_word),
                        "start": round(current_start or start, 3),
                        "end": round(current_end or end, 3),
                    }
                )
                current_word = []
                current_start = None
                current_end = None
            continue

        if current_start is None:
            current_start = start
        current_end = end
        current_word.append(character)

    if current_word:
        words.append(
            {
                "word": "".join(current_word),
                "start": round(current_start or 0.0, 3),
                "end": round(current_end or (current_start or 0.0) + 0.12, 3),
            }
        )

    if not words:
        return build_even_word_timestamps(text, 30.0)
    return words


def build_caption_groups(word_timestamps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    buffer: List[Dict[str, Any]] = []

    def flush() -> None:
        if not buffer:
            return
        words = [item["word"] for item in buffer]
        highlight = max(
            words,
            key=lambda word: (len(re.sub(r"[^A-Za-z0-9А-Яа-яҮүӨөЁё]", "", word)), word),
        )
        groups.append(
            {
                "text": " ".join(words),
                "start": buffer[0]["start"],
                "end": buffer[-1]["end"],
                "highlight": highlight,
                "words": words,
            }
        )
        buffer.clear()

    for item in word_timestamps:
        cleaned = clean_text(item["word"])
        if not cleaned:
            continue
        buffer.append({"word": cleaned, "start": item["start"], "end": item["end"]})
        current_text = " ".join(entry["word"] for entry in buffer)
        punctuation_break = cleaned.endswith((".", "!", "?", ",", ";", ":"))
        if len(buffer) >= 5 or len(current_text) >= 22 or punctuation_break:
            flush()

    flush()
    return groups


def create_silent_wav(path: Path, duration: float, sample_rate: int = 44100) -> None:
    frames = int(duration * sample_rate)
    ensure_dir(path.parent)
    silence_frame = (0).to_bytes(2, byteorder="little", signed=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        chunk = silence_frame * min(frames, sample_rate)
        remaining = frames
        while remaining > 0:
            current = min(remaining, sample_rate)
            handle.writeframes(chunk[: current * 2])
            remaining -= current


def choose_palette(seed: str) -> List[List[int]]:
    palettes = [
        [[244, 93, 72], [255, 202, 88], [255, 244, 214]],
        [[17, 93, 89], [64, 170, 146], [235, 244, 229]],
        [[18, 42, 66], [66, 91, 122], [240, 225, 200]],
        [[77, 28, 79], [188, 108, 37], [250, 237, 205]],
    ]
    rng = random.Random(seed)
    return rng.choice(palettes)


def clip_with_fps(clip: Any, fps: int) -> Any:
    if hasattr(clip, "set_fps"):
        return clip.set_fps(fps)
    return clip.with_fps(fps)


def clip_with_duration(clip: Any, duration: float) -> Any:
    if hasattr(clip, "set_duration"):
        return clip.set_duration(duration)
    return clip.with_duration(duration)


def clip_with_start(clip: Any, start: float) -> Any:
    if hasattr(clip, "set_start"):
        return clip.set_start(start)
    return clip.with_start(start)


def clip_with_position(clip: Any, position: Any) -> Any:
    if hasattr(clip, "set_position"):
        return clip.set_position(position)
    return clip.with_position(position)


def clip_with_audio(clip: Any, audio: Any) -> Any:
    if hasattr(clip, "set_audio"):
        return clip.set_audio(audio)
    return clip.with_audio(audio)


def make_image_clip(image: np.ndarray) -> Any:
    try:
        return ImageClip(image, transparent=True)
    except TypeError:
        return ImageClip(image)


def gradient_frame_factory(size: tuple[int, int], palette: List[List[int]]):
    width, height = size
    x = np.linspace(0.0, 1.0, width)
    y = np.linspace(0.0, 1.0, height)
    grid_x, grid_y = np.meshgrid(x, y)
    color_a = np.array(palette[0], dtype=np.float32)
    color_b = np.array(palette[1], dtype=np.float32)
    color_c = np.array(palette[2], dtype=np.float32)

    def make_frame(time_point: float) -> np.ndarray:
        wave_a = 0.5 + 0.5 * np.sin((grid_x * 2.4 + time_point * 0.12) * math.pi * 2)
        wave_b = 0.5 + 0.5 * np.sin((grid_y * 1.8 - time_point * 0.09) * math.pi * 2)
        swirl = 0.5 + 0.5 * np.sin(((grid_x + grid_y) * 1.1 + time_point * 0.05) * math.pi * 2)

        frame = (
            color_a * wave_a[..., None] * 0.45
            + color_b * wave_b[..., None] * 0.35
            + color_c * swirl[..., None] * 0.40
        )
        vignette = 1.0 - 0.18 * ((grid_x - 0.5) ** 2 + (grid_y - 0.5) ** 2)
        frame = np.clip(frame * vignette[..., None], 0, 255)
        return frame.astype(np.uint8)

    return make_frame


def render_text_block(
    text: str,
    highlight_word: Optional[str],
    size: tuple[int, int],
    font_size: int,
    y_ratio: float,
    fill: str = "#FFF8EA",
    highlight_fill: str = "#FFD166",
    box_fill: tuple[int, int, int, int] = (14, 18, 24, 180),
) -> np.ndarray:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = load_font(font_size)
    shadow_fill = (0, 0, 0, 160)
    words = text.split()

    lines: List[List[str]] = []
    current: List[str] = []
    for word in words:
        trial = current + [word]
        bbox = draw.textbbox((0, 0), " ".join(trial), font=font, stroke_width=2)
        if current and (bbox[2] - bbox[0]) > int(width * 0.72):
            lines.append(current)
            current = [word]
        else:
            current = trial
    if current:
        lines.append(current)

    line_boxes = []
    line_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), " ".join(line), font=font, stroke_width=2)
        line_boxes.append(bbox)
        line_height = max(line_height, bbox[3] - bbox[1])

    total_height = len(lines) * line_height + max(0, len(lines) - 1) * int(font_size * 0.22)
    top = int(height * y_ratio - total_height / 2)
    box_margin_x = int(width * 0.08)
    box_padding_x = 26
    box_padding_y = 20

    widest_line = max((bbox[2] - bbox[0]) for bbox in line_boxes) if line_boxes else 0
    left = max(box_margin_x, int((width - widest_line) / 2) - box_padding_x)
    right = min(width - box_margin_x, int((width + widest_line) / 2) + box_padding_x)
    bottom = min(height - 40, top + total_height + box_padding_y * 2)
    draw.rounded_rectangle(
        [(left, top - box_padding_y), (right, bottom)],
        radius=28,
        fill=box_fill,
    )

    y = top
    for line in lines:
        line_text = " ".join(line)
        line_bbox = draw.textbbox((0, 0), line_text, font=font, stroke_width=2)
        x = int((width - (line_bbox[2] - line_bbox[0])) / 2)
        cursor_x = x
        for index, word in enumerate(line):
            rendered = word if index == len(line) - 1 else f"{word} "
            word_bbox = draw.textbbox((0, 0), rendered, font=font, stroke_width=2)
            color = highlight_fill if highlight_word and word.strip(".,!?").lower() == highlight_word.strip(".,!?").lower() else fill
            draw.text(
                (cursor_x + 2, y + 3),
                rendered,
                font=font,
                fill=shadow_fill,
                stroke_width=0,
            )
            draw.text(
                (cursor_x, y),
                rendered,
                font=font,
                fill=color,
                stroke_width=2,
                stroke_fill="#101418",
            )
            cursor_x += word_bbox[2] - word_bbox[0]
        y += line_height + int(font_size * 0.22)

    return np.array(image)


class ReelPipeline:
    def __init__(self, db, reel: GeneratedReel, force: bool = False):
        self.db = db
        self.reel = reel
        self.force = force
        self.artifact_dir = Path(reel.artifact_dir)
        ensure_dir(self.artifact_dir)

    def artifact(self, filename: str) -> Path:
        return self.artifact_dir / filename

    def update_reel(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self.reel, key, value)
        self.db.add(self.reel)
        self.db.commit()
        self.db.refresh(self.reel)

    def run_until(self, step: str) -> None:
        target_index = len(STEP_ORDER) - 1 if step == "all" else STEP_ORDER.index(step)
        for current_step in STEP_ORDER[: target_index + 1]:
            getattr(self, f"step_{current_step}")()

    def step_topic(self) -> None:
        topic_path = self.artifact("topic.json")
        article_path = self.artifact("article.txt")
        if not self.force and topic_path.exists() and article_path.exists() and self.reel.topic_generated_at:
            log(f"Skipping topic step for reel #{self.reel.id}; artifacts already exist.")
            return

        article = fetch_article(self.reel.source_url)
        write_json(topic_path, article)
        write_text(article_path, article["text"])
        self.update_reel(
            title=article["title"],
            status="topic",
            error_message=None,
            topic_generated_at=datetime.now(),
        )
        log(f"Topic selected for reel #{self.reel.id}: {article['title']}")

    def step_script(self) -> None:
        script_path = self.artifact("script.json")
        if not self.force and script_path.exists() and self.reel.script_generated_at:
            log(f"Skipping script step for reel #{self.reel.id}; artifact already exists.")
            return

        article = read_json(self.artifact("topic.json"))
        provider = "fallback"
        try:
            sections = call_openai_for_script(article)
            if sections:
                provider = "openai"
            else:
                sections = build_fallback_sections(article)
        except Exception as exc:
            log(f"OpenAI script generation failed, using fallback: {exc}")
            sections = build_fallback_sections(article)

        sections = normalize_sections(sections)
        narration_text = narration_text_from_sections(sections)
        payload = {
            "provider": provider,
            "generated_at": datetime.now().isoformat(),
            "sections": sections,
            "narration_text": narration_text,
            "word_count": len(narration_text.split()),
        }
        write_json(script_path, payload)
        write_text(
            self.artifact("script.txt"),
            "\n".join(
                [
                    f"Hook: {sections['hook']}",
                    f"Problem: {sections['problem']}",
                    f"Explanation: {sections['explanation']}",
                    f"Takeaway: {sections['takeaway']}",
                ]
            ),
        )
        self.update_reel(
            status="script",
            script_word_count=payload["word_count"],
            error_message=None,
            script_generated_at=datetime.now(),
        )
        log(f"Script generated for reel #{self.reel.id} ({payload['word_count']} words).")

    def step_voice(self) -> None:
        voice_manifest_path = self.artifact("voice.json")
        if not self.force and voice_manifest_path.exists() and self.reel.voice_generated_at:
            log(f"Skipping voice step for reel #{self.reel.id}; artifact already exists.")
            return

        script_payload = read_json(self.artifact("script.json"))
        narration_text = script_payload["narration_text"]
        provider = "fallback_silence"
        duration_seconds = max(20.0, min(35.0, len(narration_text.split()) * 0.42))
        audio_path = self.artifact("voice.wav")
        word_timestamps: List[Dict[str, Any]]

        if ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            try:
                response = requests.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/with-timestamps",
                    headers={
                        "xi-api-key": ELEVENLABS_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": narration_text,
                        "model_id": ELEVENLABS_MODEL_ID,
                    },
                    timeout=120,
                )
                response.raise_for_status()
                payload = response.json()
                audio_bytes = base64.b64decode(payload["audio_base64"])
                elevenlabs_audio_path = self.artifact("voice.mp3")
                elevenlabs_audio_path.write_bytes(audio_bytes)
                audio_path = elevenlabs_audio_path
                alignment = payload.get("alignment") or payload.get("normalized_alignment") or {}
                word_timestamps = character_alignment_to_words(narration_text, alignment)
                if word_timestamps:
                    duration_seconds = max(duration_seconds, word_timestamps[-1]["end"])
                else:
                    word_timestamps = build_even_word_timestamps(narration_text, duration_seconds)
                provider = "elevenlabs"
            except Exception as exc:
                log(f"ElevenLabs voice generation failed, using silent fallback: {exc}")
                audio_path = self.artifact("voice.wav")
                word_timestamps = build_even_word_timestamps(narration_text, duration_seconds)
                create_silent_wav(audio_path, duration_seconds)
        else:
            word_timestamps = build_even_word_timestamps(narration_text, duration_seconds)
            create_silent_wav(audio_path, duration_seconds)

        captions = build_caption_groups(word_timestamps)
        write_json(self.artifact("captions.json"), {"captions": captions})
        write_json(
            voice_manifest_path,
            {
                "provider": provider,
                "generated_at": datetime.now().isoformat(),
                "audio_path": str(audio_path),
                "duration_seconds": round(duration_seconds, 3),
                "word_timestamps": word_timestamps,
            },
        )
        self.update_reel(
            status="voice",
            duration_seconds=math.ceil(duration_seconds),
            error_message=None,
            voice_generated_at=datetime.now(),
        )
        log(f"Voice step completed for reel #{self.reel.id} using {provider}.")

    def step_visuals(self) -> None:
        visuals_manifest_path = self.artifact("visuals.json")
        background_path = self.artifact("background.mp4")
        if not self.force and visuals_manifest_path.exists() and background_path.exists() and self.reel.visuals_generated_at:
            log(f"Skipping visuals step for reel #{self.reel.id}; artifact already exists.")
            return

        voice_payload = read_json(self.artifact("voice.json"))
        duration_seconds = float(voice_payload["duration_seconds"])
        palette = choose_palette(self.reel.slug)
        make_frame = gradient_frame_factory(VIDEO_SIZE, palette)
        clip = clip_with_fps(VideoClip(make_frame, duration=duration_seconds), VIDEO_FPS)
        clip.write_videofile(
            str(background_path),
            fps=VIDEO_FPS,
            audio=False,
            codec="libx264",
            preset="medium",
            logger=None,
        )
        clip.close()
        write_json(
            visuals_manifest_path,
            {
                "generated_at": datetime.now().isoformat(),
                "background_path": str(background_path),
                "palette": palette,
                "size": list(VIDEO_SIZE),
                "fps": VIDEO_FPS,
            },
        )
        self.update_reel(
            status="visuals",
            error_message=None,
            visuals_generated_at=datetime.now(),
        )
        log(f"Visuals generated for reel #{self.reel.id}.")

    def step_edit(self) -> None:
        edit_manifest_path = self.artifact("edit.json")
        final_reel_path = self.artifact("reel.mp4")
        if not self.force and edit_manifest_path.exists() and final_reel_path.exists() and self.reel.edited_at:
            log(f"Skipping edit step for reel #{self.reel.id}; artifact already exists.")
            return

        script_payload = read_json(self.artifact("script.json"))
        voice_payload = read_json(self.artifact("voice.json"))
        captions_payload = read_json(self.artifact("captions.json"))
        visuals_payload = read_json(self.artifact("visuals.json"))

        background_clip = clip_with_duration(
            VideoFileClip(visuals_payload["background_path"]),
            float(voice_payload["duration_seconds"]),
        )
        audio_clip = AudioFileClip(voice_payload["audio_path"])
        overlays: List[Any] = []

        source_tag = clip_with_position(
            clip_with_duration(
                make_image_clip(render_text_block("HUULI.TECH", None, VIDEO_SIZE, 34, 0.10, fill="#F9F4DA")),
                audio_clip.duration,
            ),
            ("center", "center"),
        )
        overlays.append(source_tag)

        hook = script_payload["sections"]["hook"].upper()
        hook_clip = clip_with_position(
            clip_with_duration(
                clip_with_start(
                    make_image_clip(render_text_block(hook, None, VIDEO_SIZE, 56, 0.22, fill="#FFF8EA")),
                    0,
                ),
                min(3.0, audio_clip.duration),
            ),
            ("center", "center"),
        )
        overlays.append(hook_clip)

        for caption in captions_payload["captions"]:
            clip = make_image_clip(
                render_text_block(
                    caption["text"].upper(),
                    caption["highlight"].upper(),
                    VIDEO_SIZE,
                    66,
                    0.63,
                    fill="#FFF8EA",
                    highlight_fill="#FFB703",
                )
            )
            clip = clip_with_position(
                clip_with_duration(
                    clip_with_start(clip, float(caption["start"])),
                    max(0.2, float(caption["end"]) - float(caption["start"])),
                ),
                ("center", "center"),
            )
            overlays.append(clip)

        cta_clip = clip_with_position(
            clip_with_duration(
                clip_with_start(
                    make_image_clip(
                        render_text_block(DEFAULT_CTA.upper(), None, VIDEO_SIZE, 40, 0.87, fill="#EAF4F4")
                    ),
                    max(0.0, audio_clip.duration - 5.0),
                ),
                min(5.0, audio_clip.duration),
            ),
            ("center", "center"),
        )
        overlays.append(cta_clip)

        final_clip = clip_with_audio(CompositeVideoClip([background_clip] + overlays, size=VIDEO_SIZE), audio_clip)
        final_clip.write_videofile(
            str(final_reel_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            logger=None,
        )
        final_duration = final_clip.duration
        final_clip.close()
        audio_clip.close()
        background_clip.close()
        for clip in overlays:
            clip.close()

        write_json(
            edit_manifest_path,
            {
                "generated_at": datetime.now().isoformat(),
                "video_path": str(final_reel_path),
                "duration_seconds": round(final_duration, 3),
                "caption_count": len(captions_payload["captions"]),
            },
        )
        self.update_reel(
            status="edited",
            error_message=None,
            edited_at=datetime.now(),
        )
        log(f"Final reel assembled for reel #{self.reel.id}: {final_reel_path}")


def create_reel_record(db, source_url: str) -> GeneratedReel:
    base_slug = slugify(source_url.rstrip("/").split("/")[-1])
    slug = base_slug
    suffix = 2
    while db.query(GeneratedReel).filter(GeneratedReel.slug == slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    artifact_dir = ARTIFACTS_ROOT / slug
    reel = GeneratedReel(
        source_url=source_url,
        slug=slug,
        artifact_dir=str(artifact_dir),
        status="topic",
    )
    db.add(reel)
    db.commit()
    db.refresh(reel)
    return reel


def resolve_reel(db, source_url: Optional[str], reel_id: Optional[int]) -> Optional[GeneratedReel]:
    if reel_id is not None:
        return db.query(GeneratedReel).filter(GeneratedReel.id == reel_id).first()

    if source_url:
        existing = db.query(GeneratedReel).filter(GeneratedReel.source_url == source_url).first()
        return existing or create_reel_record(db, source_url)

    existing_incomplete = (
        db.query(GeneratedReel)
        .filter(GeneratedReel.status != "edited")
        .order_by(GeneratedReel.created_at.asc(), GeneratedReel.id.asc())
        .first()
    )
    if existing_incomplete:
        log(f"Resuming incomplete reel #{existing_incomplete.id} ({existing_incomplete.source_url})")
        return existing_incomplete

    urls = get_articles_from_sitemap()
    used_urls = {row[0] for row in db.query(GeneratedReel.source_url).all()}
    for url in urls:
        if url not in used_urls:
            return create_reel_record(db, url)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate short legal reels from huuli.tech articles.")
    parser.add_argument(
        "--step",
        default="all",
        choices=["all"] + STEP_ORDER,
        help="Run the pipeline through the specified step.",
    )
    parser.add_argument("--source-url", help="Use a specific article URL.")
    parser.add_argument("--reel-id", type=int, help="Resume a specific generated reel row.")
    parser.add_argument("--force", action="store_true", help="Regenerate the requested step artifacts.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_dir(ARTIFACTS_ROOT)
    db = SessionLocal()
    try:
        reel = resolve_reel(db, args.source_url, args.reel_id)
        if not reel:
            log("No eligible articles found for reel generation.")
            return 0

        pipeline = ReelPipeline(db, reel, force=args.force)
        pipeline.run_until(args.step)
        log(f"Pipeline finished for reel #{reel.id} with status '{pipeline.reel.status}'.")
        return 0
    except Exception as exc:
        log(f"Pipeline failed: {exc}")
        if "reel" in locals() and reel is not None:
            reel.error_message = clean_text(str(exc))[:500]
            db.add(reel)
            db.commit()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
