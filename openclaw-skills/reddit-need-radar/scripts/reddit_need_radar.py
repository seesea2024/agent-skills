#!/usr/bin/env python3
"""
Reddit Need Radar - RSS version

搜索 Reddit RSS 中的用户需求信号，去重后通过邮件推送。
不需要 Reddit client_id / client_secret。

使用：
  python reddit_need_radar.py
  python reddit_need_radar.py --dry-run
  python reddit_need_radar.py --config config.yaml
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sqlite3
import smtplib
import socket
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import feedparser
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"
DEFAULT_DB_PATH = BASE_DIR / "reddit_needs.db"


@dataclass
class NeedItem:
    item_id: str
    subreddit: str
    title: str
    text: str
    url: str
    need_score: int
    reddit_score: int
    comments: int
    published: str
    source_query: str


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_items (
            id TEXT PRIMARY KEY,
            first_seen_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def has_seen(db_path: Path, item_id: str) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM seen_items WHERE id = ?", (item_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None


def mark_seen(db_path: Path, item_id: str) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO seen_items (id, first_seen_at) VALUES (?, ?)",
        (item_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def score_need(text: str, need_keywords: list[str]) -> int:
    t = text.lower()
    score = 0

    for kw in need_keywords:
        if kw.lower() in t:
            score += 1

    weighted_phrases = {
        "looking for": 2,
        "is there a tool": 3,
        "i wish there was": 3,
        "any recommendations": 2,
        "does anyone know": 2,
        "alternative to": 2,
        "how do i automate": 3,
        "need help with": 2,
        "frustrating": 1,
        "annoying": 1,
    }
    for phrase, weight in weighted_phrases.items():
        if phrase in t:
            score += weight

    if len(t.strip()) < 40:
        score -= 1

    return max(score, 0)


def strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return " ".join(value.split())


def normalize_reddit_url(url: str) -> str:
    if not url:
        return ""
    # RSS 有时给 old.reddit 或带参数，尽量规范化。
    parsed = urllib.parse.urlparse(url)
    clean = parsed._replace(netloc="www.reddit.com", query="", fragment="")
    return urllib.parse.urlunparse(clean)


def item_id_from_entry(entry: Any) -> str:
    link = normalize_reddit_url(getattr(entry, "link", ""))
    if link:
        return "rss_" + link.rstrip("/").split("/")[-1]
    entry_id = getattr(entry, "id", "") or getattr(entry, "guid", "")
    return "rss_" + str(entry_id)


def build_search_feed_url(subreddit: str, query: str, time_filter: str) -> str:
    params = {
        "q": query,
        "restrict_sr": "1",
        "sort": "new",
        "t": time_filter,
    }
    return f"https://www.reddit.com/r/{urllib.parse.quote(subreddit)}/search.rss?{urllib.parse.urlencode(params)}"


def build_new_feed_url(subreddit: str) -> str:
    return f"https://www.reddit.com/r/{urllib.parse.quote(subreddit)}/new.rss"


def parse_feed(url: str, user_agent: str) -> Any:
    # feedparser 支持 request_headers。适当 UA 可以降低被拒概率。
    return feedparser.parse(url, request_headers={"User-Agent": user_agent})


def search_reddit_rss(config: dict[str, Any], db_path: Path) -> list[NeedItem]:
    subreddits = config.get("subreddits", [])
    queries = config.get("queries", [])
    need_keywords = config.get("need_keywords", [])
    min_need_score = int(config.get("min_need_score", 2))
    time_filter = str(config.get("reddit_time_filter", "day"))
    max_entries = int(config.get("max_entries_per_feed", 50))
    request_timeout = float(config.get("request_timeout_seconds", 10))
    request_delay = float(config.get("request_delay_seconds", 0.1))
    user_agent = str(config.get("http_user_agent", "reddit-need-radar-rss/0.2"))

    # feedparser 底层使用 urllib；设置全局 socket timeout，避免 Reddit RSS 长时间无响应时一直卡住。
    socket.setdefaulttimeout(request_timeout)

    feed_specs: list[tuple[str, str, str]] = []

    for subreddit in subreddits:
        subreddit = str(subreddit).strip()
        if not subreddit:
            continue
        for query in queries:
            query = str(query).strip()
            if not query:
                continue
            feed_specs.append((subreddit, query, build_search_feed_url(subreddit, query, time_filter)))

    for subreddit in config.get("new_post_subreddits", []) or []:
        subreddit = str(subreddit).strip()
        if subreddit:
            feed_specs.append((subreddit, "new", build_new_feed_url(subreddit)))

    results: list[NeedItem] = []

    total_feeds = len(feed_specs)
    for idx, (subreddit, source_query, feed_url) in enumerate(feed_specs, start=1):
        try:
            print(f"[{idx}/{total_feeds}] fetching r/{subreddit} query={source_query!r}", file=sys.stderr, flush=True)
            feed = parse_feed(feed_url, user_agent)
            status = getattr(feed, "status", None)
            if status and int(status) >= 400:
                print(f"[WARN] Reddit RSS returned HTTP {status}: r/{subreddit} query={source_query!r}", file=sys.stderr)

                # 429 是 Reddit 限流。不要继续解析，也不要标记已读；等下次运行再试。
                if int(status) == 429:
                    retry_after = None
                    try:
                        retry_after = getattr(feed, "headers", {}).get("retry-after")
                    except Exception:
                        retry_after = None
                    sleep_seconds = min(int(retry_after), 60) if retry_after and str(retry_after).isdigit() else max(request_delay, 10)
                    print(f"[WARN] rate limited; sleep {sleep_seconds}s then continue", file=sys.stderr)
                    time.sleep(sleep_seconds)
                continue

            if getattr(feed, "bozo", False):
                print(f"[WARN] feed parse warning r/{subreddit} query={source_query!r}: {getattr(feed, 'bozo_exception', '')}", file=sys.stderr)

            entries = list(getattr(feed, "entries", []))[:max_entries]
            for entry in entries:
                item_id = item_id_from_entry(entry)
                if not item_id or has_seen(db_path, item_id):
                    continue

                title = strip_html(getattr(entry, "title", ""))
                summary = strip_html(getattr(entry, "summary", ""))
                url = normalize_reddit_url(getattr(entry, "link", ""))
                published = getattr(entry, "published", "") or getattr(entry, "updated", "")

                combined = f"{title}\n{summary}"
                need_score = score_need(combined, need_keywords)

                if need_score >= min_need_score:
                    results.append(
                        NeedItem(
                            item_id=item_id,
                            subreddit=subreddit,
                            title=title,
                            text=summary,
                            url=url,
                            need_score=need_score,
                            reddit_score=0,
                            comments=0,
                            published=published,
                            source_query=source_query,
                        )
                    )

                # 标记已见，避免反复推送旧帖。
                mark_seen(db_path, item_id)

            # 轻微限速，避免连续请求过快。
            time.sleep(request_delay)

        except Exception as e:
            print(f"[WARN] r/{subreddit} query={source_query!r} failed: {e}", file=sys.stderr)

    unique: dict[str, NeedItem] = {}
    for item in results:
        unique[item.item_id] = item

    return sorted(
        unique.values(),
        key=lambda x: (x.need_score, x.published),
        reverse=True,
    )


def truncate(text: str, max_len: int = 500) -> str:
    clean = " ".join((text or "").split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 1] + "…"


def build_email(results: list[NeedItem], max_items: int) -> tuple[str, str, str]:
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"Reddit 用户需求日报 RSS - {today} - {len(results)} 条"

    if not results:
        text_body = f"Reddit 用户需求日报 RSS - {today}\n\n今天没有发现新的明显用户需求。"
        html_body = f"<h2>Reddit 用户需求日报 RSS - {html.escape(today)}</h2><p>今天没有发现新的明显用户需求。</p>"
        return subject, text_body, html_body

    selected = results[:max_items]
    text_lines = [
        f"Reddit 用户需求日报 RSS - {today}",
        "",
        f"共发现 {len(results)} 条潜在需求，本邮件展示前 {len(selected)} 条。",
        "",
    ]

    html_parts = [
        f"<h2>Reddit 用户需求日报 RSS - {html.escape(today)}</h2>",
        f"<p>共发现 <strong>{len(results)}</strong> 条潜在需求，本邮件展示前 <strong>{len(selected)}</strong> 条。</p>",
        "<ol>",
    ]

    for item in selected:
        snippet = truncate(item.text, 450)
        text_lines.extend(
            [
                f"[r/{item.subreddit}] {item.title}",
                f"需求分数: {item.need_score} | 来源搜索: {item.source_query} | 发布时间: {item.published}",
                f"链接: {item.url}",
            ]
        )
        if snippet:
            text_lines.append(f"摘要: {snippet}")
        text_lines.append("")

        html_parts.append("<li>")
        html_parts.append(f"<p><strong>[r/{html.escape(item.subreddit)}] {html.escape(item.title)}</strong></p>")
        html_parts.append(
            f"<p>需求分数: {item.need_score} | 来源搜索: {html.escape(item.source_query)} | 发布时间: {html.escape(item.published)}</p>"
        )
        if item.url:
            html_parts.append(f'<p><a href="{html.escape(item.url)}">查看原帖</a></p>')
        if snippet:
            html_parts.append(f"<blockquote>{html.escape(snippet)}</blockquote>")
        html_parts.append("</li>")

    html_parts.append("</ol>")
    return subject, "\n".join(text_lines), "\n".join(html_parts)


def send_email(subject: str, text_body: str, html_body: str) -> None:
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_TO"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"缺少邮件环境变量: {', '.join(missing)}")

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    email_from = os.getenv("EMAIL_FROM") or smtp_user
    email_to = os.getenv("EMAIL_TO", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Reddit RSS needs and send email digest.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="配置文件路径")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite 去重数据库路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印邮件内容，不发送邮件")
    parser.add_argument("--reset-seen", action="store_true", help="删除去重数据库，重新扫描。谨慎使用")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(BASE_DIR / ".env")

    config_path = Path(args.config).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()

    if args.reset_seen and db_path.exists():
        db_path.unlink()

    config = load_config(config_path)
    init_db(db_path)

    results = search_reddit_rss(config, db_path)
    max_items = int(config.get("max_email_items", 30))
    subject, text_body, html_body = build_email(results, max_items=max_items)

    if args.dry_run:
        print("Subject:", subject)
        print("-" * 80)
        print(text_body)
    else:
        send_empty_email = bool(config.get("send_empty_email", False))
        if not results and not send_empty_email:
            print("No results; email skipped because send_empty_email=false")
        else:
            send_email(subject, text_body, html_body)
            print(f"Email sent: {subject}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
