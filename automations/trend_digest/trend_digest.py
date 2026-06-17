#!/usr/bin/env python3
"""Create a niche trend digest from X posts and email it.

The automation intentionally leaves Reddit out for now. It gathers X posts for
predefined Gen Z money, startup, upskilling, and AI niches through a configurable
ScrapperSOGS posts endpoint, asks Gemini to turn the findings into five content
ideas per category, then emails the digest through SMTP.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import textwrap
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

import requests
from dotenv import load_dotenv

CATEGORIES: dict[str, list[str]] = {
    "Personal Finance & Money Mindset for Gen Z": [
        "Gen Z personal finance",
        "money mindset Gen Z",
        "budgeting investing young adults",
    ],
    "Startup Breakdowns & High-Potential Business Ideas": [
        "startup breakdown",
        "high potential business ideas",
        "new startup trends",
    ],
    "Upskilling, Tech Certifications & Freelancing": [
        "tech certifications freelancing",
        "upskilling for remote work",
        "freelance developer creator economy",
    ],
    "Artificial Intelligence & Emerging Tech Updates": [
        "AI emerging tech updates",
        "generative AI tools trend",
        "future technology startups",
    ],
}


@dataclass(frozen=True)
class Settings:
    scrappersogs_api_key: str
    gemini_api_key: str
    recipient_email: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    scraper_base_url: str
    scraper_posts_path: str
    trend_post_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        missing: list[str] = []

        def require(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                missing.append(name)
            return value

        settings = cls(
            scrappersogs_api_key=require("SCRAPPERSOGS_API_KEY"),
            gemini_api_key=require("GEMINI_API_KEY"),
            recipient_email=require("DIGEST_RECIPIENT_EMAIL"),
            smtp_host=require("SMTP_HOST"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=require("SMTP_USERNAME"),
            smtp_password=require("SMTP_PASSWORD"),
            smtp_from=os.getenv("SMTP_FROM", os.getenv("SMTP_USERNAME", "")).strip(),
            scraper_base_url=os.getenv("SCRAPPERSOGS_BASE_URL", "https://api.scrappersogs.com").rstrip("/"),
            scraper_posts_path=os.getenv("SCRAPPERSOGS_X_POSTS_PATH", "/v1/x/posts/search"),
            trend_post_limit=int(os.getenv("TREND_POST_LIMIT", "30")),
        )
        if not settings.smtp_from:
            missing.append("SMTP_FROM or SMTP_USERNAME")
        if missing:
            raise RuntimeError("Missing required environment variables: " + ", ".join(sorted(set(missing))))
        return settings


def normalize_posts(payload: Any) -> list[dict[str, Any]]:
    """Accept common API shapes and return a compact list of post dictionaries."""
    if isinstance(payload, list):
        raw_posts = payload
    elif isinstance(payload, dict):
        raw_posts = (
            payload.get("posts")
            or payload.get("data")
            or payload.get("results")
            or payload.get("items")
            or []
        )
    else:
        raw_posts = []

    posts: list[dict[str, Any]] = []
    for item in raw_posts:
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("content") or item.get("body") or item.get("caption") or ""
        if not text:
            continue
        posts.append(
            {
                "text": str(text)[:800],
                "author": item.get("author") or item.get("username") or item.get("user"),
                "url": item.get("url") or item.get("link"),
                "metrics": item.get("metrics")
                or {
                    "likes": item.get("likes") or item.get("like_count"),
                    "reposts": item.get("reposts") or item.get("retweets") or item.get("retweet_count"),
                    "replies": item.get("replies") or item.get("reply_count"),
                },
            }
        )
    return posts


def fetch_x_posts(settings: Settings, query: str) -> list[dict[str, Any]]:
    url = f"{settings.scraper_base_url}{settings.scraper_posts_path}"
    headers = {
        "Authorization": f"Bearer {settings.scrappersogs_api_key}",
        "X-API-Key": settings.scrappersogs_api_key,
        "Accept": "application/json",
    }
    params = {"query": query, "limit": settings.trend_post_limit, "sort": "trending", "platform": "x"}
    response = requests.get(url, headers=headers, params=params, timeout=45)
    response.raise_for_status()
    return normalize_posts(response.json())


def collect_trends(settings: Settings) -> dict[str, list[dict[str, Any]]]:
    collected: dict[str, list[dict[str, Any]]] = {}
    for category, queries in CATEGORIES.items():
        posts: list[dict[str, Any]] = []
        for query in queries:
            try:
                posts.extend(fetch_x_posts(settings, query))
            except requests.RequestException as exc:
                posts.append({"text": f"Scraper error for '{query}': {exc}", "author": "automation"})
        collected[category] = posts[: settings.trend_post_limit]
    return collected


def build_prompt(trends: dict[str, list[dict[str, Any]]]) -> str:
    return textwrap.dedent(
        f"""
        You are a trend research assistant for a Gen Z audience. Reddit is intentionally excluded.
        Use only the X post summaries below. For each category, identify the most talked-about
        themes and create exactly 5 fresh content ideas. Include a short hook, why it is trending,
        and a suggested format. Keep it practical and concise.

        Categories:
        {json.dumps(trends, indent=2, ensure_ascii=False)}
        """
    ).strip()


def generate_digest(settings: Settings, trends: dict[str, list[dict[str, Any]]]) -> str:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    payload = {"contents": [{"parts": [{"text": build_prompt(trends)}]}]}
    response = requests.post(url, params={"key": settings.gemini_api_key}, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected Gemini response shape: {data}") from exc


def send_email(settings: Settings, subject: str, body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.recipient_email
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def main() -> None:
    parser = argparse.ArgumentParser(description="Email X trend-based content ideas by niche category.")
    parser.add_argument("--dry-run", action="store_true", help="Print the digest instead of sending email.")
    args = parser.parse_args()

    load_dotenv()
    settings = Settings.from_env()
    trends = collect_trends(settings)
    digest = generate_digest(settings, trends)
    subject = "X Trend Digest: 5 Ideas per Niche Category"

    if args.dry_run:
        print(subject)
        print("=" * len(subject))
        print(digest)
    else:
        send_email(settings, subject, digest)
        print(f"Digest sent to {settings.recipient_email}")


if __name__ == "__main__":
    main()
