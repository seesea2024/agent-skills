---
name: reddit-need-radar
description: Use this skill when the user asks to search Reddit for user needs, product pain points, SaaS ideas, Reddit demand signals, or to run/configure/schedule the local Reddit needs email digest. It uses a no-Reddit-API RSS workflow, SQLite deduplication, and SMTP email delivery from /Users/stone/py-prj/reddit.
---

# Reddit Need Radar

Find product/user-need signals from Reddit and email a digest. This skill is designed for Boss's local project:

```text
/Users/stone/py-prj/reddit
```

Current implementation is **RSS-based** and does **not** require Reddit API client id/secret.

## Core behavior

When the user asks to run/search/send/schedule Reddit needs:

1. Use the existing project at `/Users/stone/py-prj/reddit` if present.
2. If files are missing, restore from this skill's bundled assets/scripts:
   - script: `/Users/stone/.openclaw/workspace/skills/reddit-need-radar/scripts/reddit_need_radar.py`
   - config template: `/Users/stone/.openclaw/workspace/skills/reddit-need-radar/assets/config.yaml`
   - env template: `/Users/stone/.openclaw/workspace/skills/reddit-need-radar/assets/.env.example`
   - requirements: `/Users/stone/.openclaw/workspace/skills/reddit-need-radar/assets/requirements.txt`
3. Do not ask the user to run commands if you can run them with tools.
4. Never expose or copy `.env` secrets into chat.
5. Prefer `--dry-run` before sending email when changing config.

## Setup / repair workflow

Run internally:

```bash
mkdir -p /Users/stone/py-prj/reddit
cp /Users/stone/.openclaw/workspace/skills/reddit-need-radar/scripts/reddit_need_radar.py /Users/stone/py-prj/reddit/reddit_need_radar.py
cp /Users/stone/.openclaw/workspace/skills/reddit-need-radar/assets/config.yaml /Users/stone/py-prj/reddit/config.yaml
cp /Users/stone/.openclaw/workspace/skills/reddit-need-radar/assets/requirements.txt /Users/stone/py-prj/reddit/requirements.txt
[ -f /Users/stone/py-prj/reddit/.env ] || cp /Users/stone/.openclaw/workspace/skills/reddit-need-radar/assets/.env.example /Users/stone/py-prj/reddit/.env.example
cd /Users/stone/py-prj/reddit && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Only create `.env` from `.env.example` when the user asks or it does not exist; never overwrite an existing `.env`.

## Running

Dry-run, no email:

```bash
cd /Users/stone/py-prj/reddit && .venv/bin/python reddit_need_radar.py --dry-run
```

Send email:

```bash
cd /Users/stone/py-prj/reddit && .venv/bin/python reddit_need_radar.py
```

Reset deduplication and dry-run:

```bash
cd /Users/stone/py-prj/reddit && .venv/bin/python reddit_need_radar.py --dry-run --reset-seen
```

## Current recommended config

Because Reddit often returns HTTP 429 for `search.rss`, prefer low-volume `/new.rss` monitoring and local filtering:

```yaml
send_empty_email: false
request_timeout_seconds: 10
request_delay_seconds: 10
subreddits:
  - SaaS
  - startups
  - Entrepreneur
queries: []
new_post_subreddits:
  - SaaS
  - startups
  - Entrepreneur
```

If 429 persists, reduce sources further, increase `request_delay_seconds`, wait, or suggest using a proxy/search API provider. If results are too broad, raise `min_need_score`; if too few, lower it or add subreddits.

## QQ Mail SMTP defaults

For QQ 邮箱, use SMTP authorization code, not the QQ login password:

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USER=<qq-number>@qq.com
SMTP_PASSWORD=<QQ邮箱SMTP授权码>
EMAIL_FROM=<qq-number>@qq.com
EMAIL_TO=<recipient>
```

The script currently uses STARTTLS, so port 587 is the safest default.

## Scheduling

For local macOS/Linux cron, inspect existing crontab first and merge; do not clobber it. Typical daily 9:00 job:

```cron
0 9 * * * cd /Users/stone/py-prj/reddit && /Users/stone/py-prj/reddit/.venv/bin/python reddit_need_radar.py >> reddit_need_radar.log 2>&1
```

Use OpenClaw `cron` only if the user wants OpenClaw-managed reminders/tasks. For normal local script scheduling, crontab is acceptable but inspect first.

## Verification checklist

Before final response, report evidence from tool output:

- Script path used.
- Whether dry-run/send succeeded.
- Any HTTP 429 warnings.
- Whether email was sent or skipped due to `send_empty_email=false`.
- If scheduling was changed, show the resulting cron entry.
