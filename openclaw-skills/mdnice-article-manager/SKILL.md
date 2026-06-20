---
name: mdnice-article-manager
description: Manage articles and folders on editor.mdnice.com via mdnice API, especially listing or deleting all articles under a specified mdnice directory/catalog. Use when user asks to delete, clean, list, audit, or manage mdnice/Markdown Nice articles or folders.
---

# mdnice Article Manager

Use this skill for mdnice / Markdown Nice (`https://editor.mdnice.com`) article management through the web API.

## Safety rules

Deletion is destructive and external. Always:

1. Authenticate and **list the target catalog and article count first**.
2. Save the target article list to a local JSON file.
3. Show the user the catalog name, `catalogId`, article count, and a brief sample or full list when feasible.
4. Require explicit confirmation before deleting, e.g. `确认删除 <目录名> 目录下全部 <N> 篇文章`.
5. After deletion, re-query the catalog and report `beforeCount`, `attempted`, `successCount`, `failCount`, `afterCount`.
6. Save deletion results to a local JSON file.
7. Never print full mdnice tokens/cookies.

## API facts

The current mdnice frontend uses:

- API base: `https://api.mdnice.com`
- Auth header: `Authorization: Bearer <token>`
- List catalogs: `GET /catalogs`
- Search articles: `POST /articles/search` with JSON `{currentPage, pageSize, catalogId}`
- Delete article: `DELETE /articles/{outId}`

Chrome stores mdnice login in cookies under `.mdnice.com`. On macOS Chrome, cookies are encrypted with `Chrome Safe Storage`; the bundled script handles this locally and strips Chrome's 32-byte host digest prefix when needed.

## Bundled script

Use `scripts/mdnice_articles.py` for deterministic API work.

Typical flow:

```bash
# List catalogs
python3 ~/.openclaw/workspace/skills/mdnice-article-manager/scripts/mdnice_articles.py catalogs

# List articles in a catalog by exact name and save JSON
python3 ~/.openclaw/workspace/skills/mdnice-article-manager/scripts/mdnice_articles.py list --catalog "2025前" --out /tmp/mdnice_2025pre_articles.json

# After explicit user confirmation, delete exactly the saved list and verify
python3 ~/.openclaw/workspace/skills/mdnice-article-manager/scripts/mdnice_articles.py delete --in /tmp/mdnice_2025pre_articles.json --log /tmp/mdnice_delete_2025pre_result.json
```

Options:

- `--profile "Profile 1"` or `--profile Default` to choose Chrome profile. If omitted, the script tries common profiles.
- `--base https://api.mdnice.com` to override API base.
- `--sleep 0.15` to throttle deletes.

## Response pattern

Before deletion:

```text
我通过 mdnice API 读取到：
- 账号：<username if available>
- 目录：<catalog>
- catalogId：<id>
- 文章数：<N>
- 清单保存到：<path>

如确认删除，请回复：确认删除 <catalog> 目录下全部 <N> 篇文章
```

After deletion:

```text
已完成：
- 删除前：<beforeCount>
- 尝试删除：<attempted>
- 成功：<successCount>
- 失败：<failCount>
- 删除后复查剩余：<afterCount>
- 日志：<log path>
```
