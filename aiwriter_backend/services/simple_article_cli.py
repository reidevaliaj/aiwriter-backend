#!/usr/bin/env python3
# simple_article_cli.py

import os
import json
import argparse
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI
from aiwriter_backend.core.config import settings

# ---------- Config ----------
DEFAULT_TOPIC = "best tools for camping in the snow"
DEFAULT_LANGUAGE = "de"       # change to "en" if you want English
DEFAULT_LENGTH = "medium"     # short | medium | long
DEFAULT_TEMPERATURE = 1.0     # GPT-5 only allows the default; anything else will be omitted
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


def validate_minimal_shape(data: Dict[str, Any]) -> None:
    """
    Minimal sanity check (no external deps).
    Ensures the fields we rely on exist and are strings.
    """
    if not isinstance(data, dict):
        raise ValueError("Model did not return a JSON object.")
    if "title" not in data or not isinstance(data["title"], str):
        raise ValueError("Missing or invalid 'title'.")
    if "article_html" not in data or not isinstance(data["article_html"], str):
        raise ValueError("Missing or invalid 'article_html'.")
    if "meta" not in data or not isinstance(data["meta"], dict):
        raise ValueError("Missing or invalid 'meta'.")
    if "title" not in data["meta"] or "description" not in data["meta"]:
        raise ValueError("Missing 'meta.title' or 'meta.description'.")
    if "faq" in data and not isinstance(data["faq"], list):
        raise ValueError("'faq' must be a list when present.")
    if "schema" in data and not isinstance(data["schema"], dict):
        raise ValueError("'schema' must be an object when present.")


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
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        snippet = (raw[:500] + "…") if len(raw) > 500 else raw
        logger.error("JSON decoding failed. Snippet:\n%s", snippet)
        raise

    validate_minimal_shape(data)
    data.setdefault("title", topic)
    data.setdefault(
        "schema",
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": data["title"],
            "datePublished": datetime.now(UTC).isoformat(),
            "inLanguage": language,
        },
    )

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
