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
from typing import Any, Dict, Optional, Tuple

from openai import OpenAI
from aiwriter_backend.core.config import settings

# ---------- Config ----------
DEFAULT_TOPIC = "best tools for camping in the snow"
DEFAULT_LANGUAGE = "de"       # change to "en" if you want English
DEFAULT_LENGTH = "medium"     # short | medium | long
DEFAULT_TEMPERATURE = 1.0     # GPT-5 only allows default=1; any other value is omitted
MODEL = "gpt-5"               # uses max_completion_tokens (not max_tokens)

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
    # strip tags inside heading
    text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return text or None


def _get_first(d: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[Any]:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def normalize_and_coerce(raw: Dict[str, Any], topic_fallback: str, language: str) -> Dict[str, Any]:
    """
    Make the model's JSON usable even if keys differ.
    - Handles common synonyms / languages (title/titel/headline, content/html/article_html, etc.)
    - Ensures faq is a list and schema is an object
    - Builds fallbacks for missing title and schema
    """
    if not isinstance(raw, dict):
        raise ValueError("Model did not return a JSON object.")

    # Flatten one level if the model wrapped everything: {"article": {...}}
    candidate = raw
    for wrap_key in ("article", "result", "data", "payload", "content"):
        if isinstance(raw.get(wrap_key), dict):
            candidate = raw[wrap_key]
            break

    # Create a case-insensitive view of keys
    lower_map = {k.lower(): k for k in candidate.keys()}
    def get_ci(*names: str) -> Optional[Any]:
        for name in names:
            k = lower_map.get(name.lower())
            if k is not None:
                return candidate[k]
        return None

    # Title candidates
    title = get_ci("title", "titel", "headline", "article_title", "artikel_titel")
    # Article HTML candidates
    article_html = get_ci("article_html", "html", "content_html", "content", "article")

    # Meta can be object or split fields
    meta = get_ci("meta", "metadata")
    if not isinstance(meta, dict):
        meta = {}
        mt = get_ci("meta_title", "metatitle", "seo_title")
        md = get_ci("meta_description", "metadescription", "seo_description", "description")
        if mt or md:
            if mt:
                meta["title"] = mt
            if md:
                meta["description"] = md

    # FAQ candidates
    faq = get_ci("faq", "faqs", "faq_list")
    if faq is None:
        faq = []
    if isinstance(faq, dict):
        # Sometimes {"items":[...]} or {"list":[...]}
        faq = _get_first(faq, ("items", "list", "entries")) or []
    if not isinstance(faq, list):
        faq = []

    # Schema candidates
    schema = get_ci("schema", "jsonld", "json_ld", "structured_data", "schema_org")
    if not isinstance(schema, dict):
        schema = {}

    # Fallbacks
    if not title:
        # try meta.title
        if isinstance(meta, dict) and isinstance(meta.get("title"), str) and meta["title"].strip():
            title = meta["title"].strip()
        # try heading in html
        if not title and isinstance(article_html, str):
            title = _extract_first_heading(article_html)
        # final fallback
        if not title:
            title = topic_fallback

    if not isinstance(article_html, str) or not article_html.strip():
        raise ValueError("Missing or invalid 'article_html'.")

    # Ensure meta has both fields with limits
    meta_title = meta.get("title") if isinstance(meta, dict) else None
    meta_desc = meta.get("description") if isinstance(meta, dict) else None
    if not isinstance(meta_title, str) or not meta_title.strip():
        meta_title = title[:60]
    if not isinstance(meta_desc, str) or not meta_desc.strip():
        meta_desc = f"Erfahren Sie alles über {title}. Umfassende Informationen und praktische Tipps."[:155]
    meta = {"title": meta_title, "description": meta_desc}

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
        "faq": faq if isinstance(faq, list) else [],
        "schema": schema if isinstance(schema, dict) else {},
    }


def generate_article(
    client: OpenAI,
    topic: str,
    language: str,
    length: str,
    temperature: float,
    include_images: bool,
) -> Dict[str, Any]:
    logger.info("Starting article generation...")

    sys_prompt = (
        "Du bist ein deutscher SEO-Redakteur. "
        "Antworte NUR als gültiges JSON-Objekt (keine Erklärungen, kein Markdown). "
        "Der Artikeltext (HTML) muss klare H2/H3-Struktur enthalten, kurze Absätze (≤120 Wörter), "
        "Listen wo sinnvoll, keine übertriebene Sprache, keine Inline-CSS oder Skripte."
    )

    user_prompt = f"""
Sprache: {language}
Thema: {topic}
Länge: {length_hint(length)}

Gib EIN JSON-Objekt mit dieser Struktur zurück:
{{
  "title": "string (Artikel-Titel)",
  "article_html": "string (vollständiger HTML-Artikel mit <h2>/<h3>, <p>, <ul>/<ol> wo sinnvoll)",
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
- Gib ausschließlich JSON zurück.
- `article_html` muss fertiges, sauberes HTML sein (ohne Inline-CSS/Script/iframe).
- `meta.title` ≤ 60 Zeichen, `meta.description` ≤ 155 Zeichen.
- 3–5 FAQ-Einträge.
"""

    logger.info("Calling GPT-5 (JSON mode)...")

    # Build request kwargs, only include temperature if exactly 1 (GPT-5 requirement)
    kwargs: Dict[str, Any] = {
        "model": MODEL,
        "max_completion_tokens": 1800,               # correct for GPT-5
        "response_format": {"type": "json_object"},  # JSON mode
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if float(temperature) == 1.0:
        kwargs["temperature"] = 1  # allowed default
    else:
        logger.info("Non-default temperature provided; omitted to satisfy GPT-5 requirements.")

    resp = client.chat.completions.create(**kwargs)
    raw = resp.choices[0].message.content or "{}"

    # Try to parse and then normalize/coerce
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        snippet = (raw[:1000] + "…") if len(raw) > 1000 else raw
        logger.error("JSON decoding failed. Raw snippet:\n%s", snippet)
        raise

    try:
        data = normalize_and_coerce(parsed, topic_fallback=topic, language=language)
    except Exception as e:
        # Log the parsed object for debugging
        snippet = json.dumps(parsed, ensure_ascii=False)[:1200]
        logger.error("Structured JSON shape error: %s\nParsed snippet: %s", e, snippet)
        raise

    # Optional image
    if include_images:
        url = generate_image(client, topic)
        if url:
            data["featured_image"] = url

    logger.info("Article generated successfully.")
    return data


def generate_image(client: OpenAI, topic: str) -> Optional[str]:
    logger.info("Generating one featured image...")
    try:
        r = client.images.generate(
            model="gpt-image-1",
            prompt=f"Sachliche, moderne Titelillustration zum Thema „{topic}“, flache Illustration, kein Text, neutraler Hintergrund.",
            size="1024x1024",
            n=1,
        )
        url = r.data[0].url
        logger.info("Image generated.")
        return url
    except Exception as e:
        logger.warning(f"Image generation failed: {e}")
        return None


def save_outputs(base_dir: Path, data: Dict[str, Any]) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    # JSON
    (base_dir / "article.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # HTML
    (base_dir / "article.html").write_text(data.get("article_html", ""), encoding="utf-8")
    # Image URL if present
    if "featured_image" in data:
        (base_dir / "featured_image.txt").write_text(data["featured_image"], encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Simple one-shot article generator (JSON mode).")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="Topic for the article.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Article language (e.g., de, en).")
    parser.add_argument("--length", default=DEFAULT_LENGTH, choices=["short", "medium", "long"], help="Article length.")
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="Model temperature (GPT-5 only allows default=1; non-1 will be omitted).",
    )
    parser.add_argument("--images", type=int, default=0, help="Generate 1 image if >0.")
    args = parser.parse_args()

    try:
        key = ensure_key()
        client = OpenAI(api_key=key)

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        out_dir = Path("out") / ts

        logger.info(f"Topic: {args.topic}")
        logger.info(
            f"Language: {args.language} | Length: {args.length} | Temp: {args.temperature} | Images: {args.images}"
        )

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

        # Short console preview
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
