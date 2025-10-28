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
DEFAULT_LANGUAGE = "de"
DEFAULT_LENGTH = "medium"     # short | medium | long
DEFAULT_TEMPERATURE = 1.0     # GPT-5: only default(=1) is accepted; others omitted
MODEL = "gpt-5"               # uses max_completion_tokens

MAX_TOKENS_PRIMARY = 2200
MAX_TOKENS_FALLBACK = 1800

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


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def normalize_and_coerce(raw: Dict[str, Any], topic_fallback: str, language: str) -> Dict[str, Any]:
    """
    Make the model's JSON usable even if keys differ.
    """
    if not isinstance(raw, dict):
        raise ValueError("Model did not return a JSON object.")

    # Unwrap one level
    candidate = raw
    for wrap_key in ("article", "result", "data", "payload", "content"):
        if isinstance(raw.get(wrap_key), dict):
            candidate = raw[wrap_key]
            break

    lower_map = {k.lower(): k for k in candidate.keys()}

    def get_ci(*names: str) -> Optional[Any]:
        for name in names:
            k = lower_map.get(name.lower())
            if k is not None:
                return candidate[k]
        return None

    title = get_ci("title", "titel", "headline", "article_title", "artikel_titel")
    article_html = get_ci("article_html", "html", "content_html", "content", "article")

    meta = get_ci("meta", "metadata")
    if not isinstance(meta, dict):
        meta = {}
        mt = get_ci("meta_title", "metatitle", "seo_title", "headline")
        md = get_ci("meta_description", "metadescription", "seo_description", "description")
        if mt:
            meta["title"] = mt
        if md:
            meta["description"] = md

    faq = get_ci("faq", "faqs", "faq_list")
    if faq is None:
        faq = []
    if isinstance(faq, dict):
        faq = faq.get("items") or faq.get("list") or faq.get("entries") or []
    if not isinstance(faq, list):
        faq = []

    schema = get_ci("schema", "jsonld", "json_ld", "structured_data", "schema_org")
    if not isinstance(schema, dict):
        schema = {}

    # Fallbacks
    if not title:
        if isinstance(meta, dict) and isinstance(meta.get("title"), str) and meta["title"].strip():
            title = meta["title"].strip()
        if not title and isinstance(article_html, str):
            title = _extract_first_heading(article_html)
        if not title:
            title = topic_fallback

    if not isinstance(article_html, str) or not article_html.strip():
        raise ValueError("Missing or invalid 'article_html'.")

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


def _primary_json_schema(language: str) -> Dict[str, Any]:
    return {
        "name": "ArticleBundle",
        "schema": {
            "type": "object",
            "required": ["title", "article_html", "meta", "faq", "schema"],
            "properties": {
                "title": {"type": "string", "minLength": 3},
                "article_html": {"type": "string", "minLength": 50},
                "meta": {
                    "type": "object",
                    "required": ["title", "description"],
                    "properties": {
                        "title": {"type": "string", "maxLength": 60},
                        "description": {"type": "string", "maxLength": 155},
                    },
                },
                "faq": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "required": ["q", "a"],
                        "properties": {
                            "q": {"type": "string", "minLength": 3},
                            "a": {"type": "string", "minLength": 40, "maxLength": 900},
                        },
                    },
                },
                "schema": {
                    "type": "object",
                    "required": ["@context", "@type", "headline", "datePublished", "inLanguage"],
                    "properties": {
                        "@context": {"const": "https://schema.org"},
                        "@type": {"const": "Article"},
                        "headline": {"type": "string"},
                        "datePublished": {"type": "string"},
                        "inLanguage": {"type": "string", "const": language},
                    },
                },
            },
            "additionalProperties": True,
        },
        "strict": True,
    }


def _minimal_json_schema(language: str) -> Dict[str, Any]:
    return {
        "name": "ArticleMinimal",
        "schema": {
            "type": "object",
            "required": ["title", "article_html"],
            "properties": {
                "title": {"type": "string", "minLength": 3},
                "article_html": {"type": "string", "minLength": 50},
            },
            "additionalProperties": True,
        },
        "strict": False,
    }


def _build_messages(topic: str, language: str, length: str) -> list:
    sys_prompt = (
        "Du bist ein deutscher SEO-Redakteur. "
        "Antworte NUR als JSON entsprechend des Schemas (keine Erklärungen, kein Markdown). "
        "Der Artikeltext (HTML) muss klare H2/H3-Struktur enthalten, kurze Absätze (≤120 Wörter), "
        "Listen wo sinnvoll, keine übertriebene Sprache, keine Inline-CSS oder Skripte."
    )

    user_prompt = f"""
Sprache: {language}
Thema: {topic}
Länge: {length_hint(length)}

Richtlinien:
- HTML sauber, semantisch, keine Inline-CSS, keine Skripte/iframes.
- Meta-Title ≤ 60 Zeichen; Meta-Description ≤ 155 Zeichen.
- 3–5 FAQ-Einträge mit prägnanten Antworten.
"""

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _call_json_schema(
    client: OpenAI,
    schema_obj: Dict[str, Any],
    messages: list,
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "max_completion_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": schema_obj,
        },
    }
    if float(temperature) == 1.0:
        kwargs["temperature"] = 1
    else:
        logger.info("Non-default temperature provided; omitted to satisfy GPT-5 requirements.")

    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        snippet = (content[:1500] + "…") if len(content) > 1500 else content
        logger.error("JSON decode failed (schema mode). Raw snippet:\n%s", snippet)
        return {}


def _call_plain_text_fallback(
    client: OpenAI,
    topic: str,
    language: str,
    length: str,
    temperature: float,
) -> str:
    """
    As a last resort, ask for pure HTML (no JSON), then we will wrap it.
    """
    sys_prompt = (
        "Du bist ein deutscher SEO-Redakteur. "
        "Gib NUR reines HTML des Artikels aus (kein JSON, kein Markdown, keine Erklärungen). "
        "Klare H2/H3-Struktur, kurze Absätze (≤120 Wörter), Listen wo sinnvoll, keine Inline-CSS."
    )
    user_prompt = f"Sprache: {language}\nThema: {topic}\nLänge: {length_hint(length)}\nNur HTML zurückgeben."

    kwargs: Dict[str, Any] = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": MAX_TOKENS_FALLBACK,
    }
    if float(temperature) == 1.0:
        kwargs["temperature"] = 1

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def generate_article(
    client: OpenAI,
    topic: str,
    language: str,
    length: str,
    temperature: float,
    include_images: bool,
) -> Dict[str, Any]:
    logger.info("Starting article generation...")

    messages = _build_messages(topic, language, length)

    # 1) Primary strict JSON schema
    primary_schema = _primary_json_schema(language)
    logger.info("Calling GPT-5 (JSON Schema: primary)…")
    data1 = _call_json_schema(client, primary_schema, messages, MAX_TOKENS_PRIMARY, temperature)

    if data1:
        try:
            normalized = normalize_and_coerce(data1, topic_fallback=topic, language=language)
            data = normalized
        except Exception as e:
            snippet = json.dumps(data1, ensure_ascii=False)[:1200]
            logger.error("Structured JSON shape error (primary): %s\nParsed snippet: %s", e, snippet)
            data = {}
    else:
        data = {}

    # 2) Minimal schema fallback
    if not data:
        minimal_schema = _minimal_json_schema(language)
        logger.info("Retrying with minimal JSON schema…")
        data2 = _call_json_schema(client, minimal_schema, messages, MAX_TOKENS_FALLBACK, temperature)
        if data2:
            try:
                normalized = normalize_and_coerce(data2, topic_fallback=topic, language=language)
                data = normalized
            except Exception as e:
                snippet = json.dumps(data2, ensure_ascii=False)[:1200]
                logger.error("Structured JSON shape error (minimal): %s\nParsed snippet: %s", e, snippet)

    # 3) Plain text (HTML) last resort
    if not data:
        logger.info("Final fallback: plain HTML request (no schema).")
        html = _call_plain_text_fallback(client, topic, language, length, temperature)
        if html and "<h" in html.lower():
            title_guess = _extract_first_heading(html) or topic
            meta_title = title_guess[:60]
            meta_desc = f"Erfahren Sie alles über {title_guess}. Umfassende Informationen und praktische Tipps."[:155]
            data = {
                "title": title_guess,
                "article_html": html,
                "meta": {"title": meta_title, "description": meta_desc},
                "faq": [],
                "schema": {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": title_guess,
                    "datePublished": datetime.now(UTC).isoformat(),
                    "inLanguage": language,
                },
            }
        else:
            snippet = (html[:1500] + "…") if len(html) > 1500 else html
            logger.error("Plain-text fallback returned empty/invalid HTML. Snippet:\n%s", snippet)
            raise ValueError("Model returned empty JSON and fallback HTML was invalid.")

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
    parser = argparse.ArgumentParser(description="Simple one-shot article generator (JSON mode with schema + fallbacks).")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="Topic for the article.")
    parser.add_argument("--language", default=DEFAULT_LANGUAGE, help="Article language (e.g., de, en).")
    parser.add_argument("--length", default=DEFAULT_LENGTH, choices=["short", "medium", "long"], help="Article length.")
    parser.add_argument(
        "--temperature",
        type=float,
        default=DEFAULT_TEMPERATURE,
        help="GPT-5 only allows default=1; non-1 will be omitted.",
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
