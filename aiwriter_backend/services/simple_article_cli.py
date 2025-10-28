#!/usr/bin/env python3
# simple_article_cli.py

import os
import json
import argparse
import logging
import sys
import re
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI
from aiwriter_backend.core.config import settings

# ---------- Defaults ----------
DEFAULT_TOPIC = "best tools for camping in the snow"
DEFAULT_LANGUAGE = "de"
DEFAULT_LENGTH = "medium"          # short | medium | long
DEFAULT_TEMPERATURE = 1.0
DEFAULT_MODEL = "gpt-4o"           # Stable production model
DEFAULT_SCHEMA_MODE = "json_object"

MAX_TOKENS = 2200

# ---------- Logging ----------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "simple_gen.log"

logger = logging.getLogger("simple-article")
logger.setLevel(logging.INFO)
_log_fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(_log_fmt)
fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
fh.setFormatter(_log_fmt)
logger.addHandler(ch)
logger.addHandler(fh)


# ---------- Helpers ----------
def ensure_key() -> str:
    key = settings.OPENAI_API_KEY
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return key


def length_hint(length: str) -> str:
    mapping = {
        "short":  "3–4 H2-Abschnitte, 600–800 Wörter",
        "medium": "5–6 H2-Abschnitte, 900–1.300 Wörter",
        "long":   "7–8 H2-Abschnitte, 1.400–1.800 Wörter",
    }
    return mapping.get(length, mapping["medium"])


def _extract_first_heading(html: str) -> Optional[str]:
    if not isinstance(html, str):
        return None
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, flags=re.I | re.S)
    if not m:
        m = re.search(r"<h2[^>]*>(.*?)</h2>", html, flags=re.I | re.S)
    if not m:
        return None
    text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return text or None


def normalize_result(raw: Dict[str, Any], topic_fallback: str, language: str) -> Dict[str, Any]:
    """Coerce model output into a consistent JSON shape."""
    if not isinstance(raw, dict):
        raise ValueError("Model did not return a JSON object.")

    candidate = raw
    for wrap in ("article", "result", "data", "payload", "content"):
        if isinstance(candidate.get(wrap), dict):
            candidate = candidate[wrap]
            break

    lower_map = {k.lower(): k for k in candidate.keys()}

    def get_ci(*names: str) -> Optional[Any]:
        for n in names:
            k = lower_map.get(n.lower())
            if k is not None:
                return candidate[k]
        return None

    title = get_ci("title", "titel", "headline")
    article_html = get_ci("article_html", "html", "content")

    meta = get_ci("meta", "metadata")
    if not isinstance(meta, dict):
        meta = {}
    faq = get_ci("faq", "faqs")
    if not isinstance(faq, list):
        faq = []
    schema = get_ci("schema", "jsonld")
    if not isinstance(schema, dict):
        schema = {}

    if not title:
        title = _extract_first_heading(article_html) or topic_fallback
    if not isinstance(article_html, str) or not article_html.strip():
        raise ValueError("Missing or invalid 'article_html'.")

    meta_title = meta.get("title") or title[:60]
    meta_desc = meta.get("description") or f"Erfahren Sie alles über {title}."
    meta = {"title": meta_title, "description": meta_desc[:155]}

    if not schema:
        schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "datePublished": datetime.now(UTC).isoformat(),
            "inLanguage": language,
        }

    return {
        "title": title,
        "article_html": article_html,
        "meta": meta,
        "faq": faq,
        "schema": schema,
    }


def build_messages(topic: str, language: str, length: str) -> list:
    """System and user messages for article generation."""
    sys = (
        "Du bist ein deutscher SEO-Redakteur. "
        "Der Artikeltext (HTML) muss klare H2/H3-Struktur enthalten, kurze Absätze (≤120 Wörter), "
        "Listen wo sinnvoll, keine übertriebene Sprache, keine Inline-CSS oder Skripte. "
        "Antworte ausschließlich als gültiges JSON-Objekt ohne zusätzliche Erklärungen."
    )

    user = f"""
Sprache: {language}
Thema: {topic}
Länge: {length_hint(length)}

Gib diese Struktur zurück:
{{
  "title": "string",
  "article_html": "string (vollständiges HTML mit <h2>/<h3>, <p>, <ul>/<ol> wo sinnvoll)",
  "meta": {{
    "title": "string (≤60 Zeichen)",
    "description": "string (≤155 Zeichen)"
  }},
  "faq": [
    {{"q": "string", "a": "string (80–100 Wörter)"}}
  ],
  "schema": {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "string",
    "datePublished": "{datetime.now(UTC).isoformat()}",
    "inLanguage": "{language}"
  }}
}}
Regeln:
- Meta-Title ≤ 60 Zeichen; Meta-Description ≤ 155 Zeichen.
- 3–5 FAQ-Einträge.
- Kein Markdown, keine Codeblöcke, nur JSON-Inhalt.
"""
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]


# ---------- OpenAI Call ----------
def _chat_create(client: OpenAI, *, model: str, messages: list, max_tokens: int, temperature: float) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def generate_article(
    client: OpenAI,
    *,
    topic: str,
    language: str,
    length: str,
    temperature: float,
    include_images: bool,
) -> Dict[str, Any]:
    """Main article generation entry point."""
    logger.info(f"Calling gpt-4o (JSON mode)...")

    messages = build_messages(topic, language, length)
    content = _chat_create(
        client,
        model="gpt-4o",
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=temperature,
    )

    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        logger.error("JSON decode failed. Raw snippet:\n%s", content[:1000])
        raise

    data = normalize_result(raw, topic, language)

    # Optional image
    if include_images:
        try:
            r = client.images.generate(
                model="gpt-image-1",
                prompt=f"Sachliche, moderne Titelillustration zum Thema „{topic}“, flache Illustration, kein Text, neutraler Hintergrund.",
                size="1024x1024",
                n=1,
            )
            url = r.data[0].url
            if url:
                data["featured_image"] = url
        except Exception as e:
            logger.warning(f"Image generation failed: {e}")

    return data


def save_outputs(base_dir: Path, data: Dict[str, Any]) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "article.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (base_dir / "article.html").write_text(data.get("article_html", ""), encoding="utf-8")
    if "featured_image" in data:
        (base_dir / "featured_image.txt").write_text(data["featured_image"], encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description="One-shot article generator using GPT-4o JSON mode.")
    p.add_argument("--topic", default=DEFAULT_TOPIC, help="Topic for the article.")
    p.add_argument("--language", default=DEFAULT_LANGUAGE, help="Article language (e.g., de, en).")
    p.add_argument("--length", default=DEFAULT_LENGTH, choices=["short", "medium", "long"], help="Article length.")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="Model temperature (0–2).")
    p.add_argument("--images", type=int, default=0, help="Generate 1 image if >0.")
    args = p.parse_args()

    try:
        key = ensure_key()
        client = OpenAI(api_key=key)

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        out_dir = Path("out") / ts

        logger.info(f"Topic: {args.topic}")
        logger.info(f"Language: {args.language} | Length: {args.length} | Temp: {args.temperature} | Images: {args.images}")
        logger.info("Model: gpt-4o | Schema: json_object")

        data = generate_article(
            client=client,
            topic=args.topic,
            language=args.language,
            length=args.length,
            temperature=args.temperature,
            include_images=bool(args.images),
        )

        save_outputs(out_dir, data)
        logger.info(f"Saved JSON & HTML to: {out_dir.resolve()}")
        if "featured_image" in data:
            logger.info(f"Featured image URL saved to: {out_dir.resolve()}/featured_image.txt")

        print("\n===== SUMMARY =====")
        print(f"Title: {data.get('title')}")
        meta = data.get("meta", {})
        print(f"Meta Title: {meta.get('title')}")
        print(f"Meta Description: {meta.get('description')}")
        print(f"Output folder: {out_dir.resolve()}")
        print("===================\n")

    except Exception as e:
        logger.exception(f"Failure: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
