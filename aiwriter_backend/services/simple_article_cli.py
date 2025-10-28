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
DEFAULT_TEMPERATURE = 1.0          # For GPT-5, only 1.0 is accepted; others omitted
DEFAULT_MODEL = "gpt-5"            # You can pass --model gpt-4o for stability
DEFAULT_SCHEMA_MODE = "json_object"  # none | json_object | json_schema

# token budgets
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


def is_gpt5(model: str) -> bool:
    return model.strip().lower().startswith("gpt-5")


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
    """
    Accept slightly off-structure JSON and coerce to:
    { title, article_html, meta{title,description}, faq[], schema{} }
    """
    if not isinstance(raw, dict):
        raise ValueError("Model did not return a JSON object.")

    candidate = raw
    for wrap in ("article", "result", "data", "payload", "content"):
        if isinstance(candidate.get(wrap), dict):
            candidate = candidate[wrap]
            break

    # case-insensitive getter
    lower_map = {k.lower(): k for k in candidate.keys()}

    def get_ci(*names: str) -> Optional[Any]:
        for n in names:
            k = lower_map.get(n.lower())
            if k is not None:
                return candidate[k]
        return None

    title = get_ci("title", "titel", "headline", "article_title")
    article_html = get_ci("article_html", "html", "content_html", "content", "article")

    # meta
    meta = get_ci("meta", "metadata")
    if not isinstance(meta, dict):
        meta = {}
        mt = get_ci("meta_title", "seo_title", "headline")
        md = get_ci("meta_description", "seo_description", "description")
        if mt:
            meta["title"] = mt
        if md:
            meta["description"] = md

    # faq
    faq = get_ci("faq", "faqs", "faq_list")
    if faq is None:
        faq = []
    if isinstance(faq, dict):
        faq = faq.get("items") or faq.get("list") or faq.get("entries") or []
    if not isinstance(faq, list):
        faq = []

    # schema
    schema = get_ci("schema", "jsonld", "json_ld", "structured_data", "schema_org")
    if not isinstance(schema, dict):
        schema = {}

    # fallbacks
    if not title:
        if isinstance(meta.get("title"), str) and meta["title"].strip():
            title = meta["title"].strip()
    if not title and isinstance(article_html, str):
        title = _extract_first_heading(article_html)
    if not title:
        title = topic_fallback

    if not isinstance(article_html, str) or not article_html.strip():
        raise ValueError("Missing or invalid 'article_html'.")

    meta_title = meta.get("title")
    meta_desc = meta.get("description")
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
        "faq": faq,
        "schema": schema,
    }


def build_messages(topic: str, language: str, length: str, json_only_hint: bool) -> list:
    sys = (
        "Du bist ein deutscher SEO-Redakteur. "
        "Der Artikeltext (HTML) muss klare H2/H3-Struktur enthalten, kurze Absätze (≤120 Wörter), "
        "Listen wo sinnvoll, keine übertriebene Sprache, keine Inline-CSS oder Skripte."
    )
    if json_only_hint:
        sys += " Antworte ausschließlich als gültiges JSON-Objekt ohne zusätzliche Erklärungen."

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
- Kein Markdown, keine Codeblöcke, nur JSON-Inhalt (bei JSON-Modus).
""".strip()

    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]


# ---------- Response format builders ----------
def schema_article_bundle(language: str) -> Dict[str, Any]:
    """Strict JSON Schema for GPT schema mode — with additionalProperties=false everywhere."""
    return {
        "name": "ArticleBundle",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "article_html", "meta", "faq", "schema"],
            "properties": {
                "title": {"type": "string", "minLength": 3},
                "article_html": {"type": "string", "minLength": 50},
                "meta": {
                    "type": "object",
                    "additionalProperties": False,
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
                        "additionalProperties": False,
                        "required": ["q", "a"],
                        "properties": {
                            "q": {"type": "string", "minLength": 3},
                            "a": {"type": "string", "minLength": 40, "maxLength": 900},
                        },
                    },
                },
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
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
        },
        "strict": True,
    }


# ---------- OpenAI call helpers ----------
def _chat_create(client: OpenAI, *, model: str, messages: list, max_tokens: int, temperature: float,
                 response_format: Optional[Dict[str, Any]] = None) -> str:
    kwargs: Dict[str, Any] = {
        "model": model,
        "messages": messages,
    }

    # GPT-5 uses max_completion_tokens; others ignore safely
    if is_gpt5(model):
        kwargs["max_completion_tokens"] = max_tokens
        if float(temperature) == 1.0:
            kwargs["temperature"] = 1
        # else omit temperature for GPT-5
    else:
        kwargs["temperature"] = float(temperature)
        kwargs["max_tokens"] = max_tokens  # legacy field for non-GPT-5 models

    if response_format is not None:
        kwargs["response_format"] = response_format

    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


# ---------- Generation ----------
def generate_article(
    client: OpenAI,
    *,
    topic: str,
    language: str,
    length: str,
    temperature: float,
    include_images: bool,
    model: str,
    schema_mode: str,  # none | json_object | json_schema
) -> Dict[str, Any]:
    logger.info(f"Calling {model} with schema mode: {schema_mode}")

    if schema_mode == "json_schema":
        # Strict schema mode
        messages = build_messages(topic, language, length, json_only_hint=True)
        rf = {"type": "json_schema", "json_schema": schema_article_bundle(language)}
        content = _chat_create(
            client,
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS_PRIMARY,
            temperature=temperature,
            response_format=rf,
        )
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            snippet = (content[:1500] + "…") if len(content) > 1500 else content
            logger.error("JSON decode failed (schema mode). Raw snippet:\n%s", snippet)
            raw = {}
        if not raw:
            raise ValueError("Empty JSON in schema mode.")
        data = normalize_result(raw, topic, language)

    elif schema_mode == "json_object":
        # JSON mode (forgiving)
        messages = build_messages(topic, language, length, json_only_hint=True)
        rf = {"type": "json_object"}
        content = _chat_create(
            client,
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS_PRIMARY,
            temperature=temperature,
            response_format=rf,
        )
        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            snippet = (content[:1500] + "…") if len(content) > 1500 else content
            logger.error("JSON decode failed (json_object). Raw snippet:\n%s", snippet)
            raw = {}
        if not raw:
            raise ValueError("Empty JSON in json_object mode.")
        data = normalize_result(raw, topic, language)

    else:
        # schema_mode == "none": prompt to return JSON, but accept slight deviations
        messages = build_messages(topic, language, length, json_only_hint=True)
        content = _chat_create(
            client,
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS_PRIMARY,
            temperature=temperature,
            response_format=None,
        )
        # Attempt JSON parse; if fails, try HTML fallback
        try:
            raw = json.loads(content)
            data = normalize_result(raw, topic, language)
        except Exception as e:
            logger.warning("Non-schema JSON parse failed (%s). Trying pure HTML fallback…", e)
            # Ask for JUST HTML as last resort
            sys2 = ("Du bist ein deutscher SEO-Redakteur. "
                    "Gib NUR reines HTML des Artikels aus (kein JSON, kein Markdown, keine Erklärungen). "
                    "Klare H2/H3-Struktur, kurze Absätze (≤120 Wörter), Listen wo sinnvoll, keine Inline-CSS.")
            user2 = f"Sprache: {language}\nThema: {topic}\nLänge: {length_hint(length)}\nNur HTML zurückgeben."
            content2 = _chat_create(
                client,
                model=model,
                messages=[{"role": "system", "content": sys2}, {"role": "user", "content": user2}],
                max_tokens=MAX_TOKENS_FALLBACK,
                temperature=temperature,
                response_format=None,
            )
            html = content2 or ""
            if "<h" not in html.lower():
                snippet = (html[:1500] + "…") if len(html) > 1500 else html
                raise ValueError(f"Plain HTML fallback invalid/empty. Snippet:\n{snippet}")
            title_guess = _extract_first_heading(html) or topic
            data = {
                "title": title_guess,
                "article_html": html,
                "meta": {
                    "title": title_guess[:60],
                    "description": f"Erfahren Sie alles über {title_guess}. Umfassende Informationen und praktische Tipps."[:155],
                },
                "faq": [],
                "schema": {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": title_guess,
                    "datePublished": datetime.now(UTC).isoformat(),
                    "inLanguage": language,
                },
            }

    # Optional image (URL only)
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
    p = argparse.ArgumentParser(description="One-shot article generator with selectable response modes.")
    p.add_argument("--topic", default=DEFAULT_TOPIC, help="Topic for the article.")
    p.add_argument("--language", default=DEFAULT_LANGUAGE, help="Article language (e.g., de, en).")
    p.add_argument("--length", default=DEFAULT_LENGTH, choices=["short", "medium", "long"], help="Article length.")
    p.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE,
                   help="For GPT-5 only 1.0 is accepted; others are omitted.")
    p.add_argument("--images", type=int, default=0, help="Generate 1 image if >0.")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Model name, e.g., gpt-5 or gpt-4o.")
    p.add_argument("--schema", default=DEFAULT_SCHEMA_MODE, choices=["none", "json_object", "json_schema"],
                   help="Response format mode.")
    args = p.parse_args()

    try:
        key = ensure_key()
        client = OpenAI(api_key=key)

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        out_dir = Path("out") / ts

        logger.info(f"Topic: {args.topic}")
        logger.info(f"Language: {args.language} | Length: {args.length} | Temp: {args.temperature} | Images: {args.images}")
        logger.info(f"Model: {args.model} | Schema: {args.schema}")

        data = generate_article(
            client=client,
            topic=args.topic,
            language=args.language,
            length=args.length,
            temperature=args.temperature,
            include_images=bool(args.images),
            model=args.model,
            schema_mode=args.schema,
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
