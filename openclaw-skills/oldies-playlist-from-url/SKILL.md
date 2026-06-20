---
name: oldies-playlist-from-url
description: Use this skill when the user provides a Bilibili/YouTube/media URL and asks to add the song to the local macOS Music playlist “老歌精选-2026”, with MP3 extraction, metadata cleanup, lyrics association, playlist renumbering, and M3U + lyrics-folder export. Trigger on requests like “把这个链接加入老歌精选”, “从这个 B 站链接提取 mp3 加到歌单并配歌词”, “添加这首歌到老歌精选-2026”.
---

# Oldies Playlist From URL

You are the operator. The user should only need to provide a source URL, optionally with corrections like song title/artist/genre. Do **not** present this as a command the user must run.

## Goal

Given a media URL, add the song to macOS Music playlist **老歌精选-2026** and keep the local export current:

- Music playlist: `老歌精选-2026`
- M3U export: `/Users/stone/.openclaw/workspace/music-exports/老歌精选-2026.m3u`
- Lyrics folder: `/Users/stone/.openclaw/workspace/music-exports/老歌精选-2026-lyrics/`

## Agent workflow

1. Extract source metadata with the bundled script dry-run or `yt-dlp --dump-json`.
2. Determine title/artist/genre.
   - If source title clearly contains `歌手《歌名》`, proceed.
   - If ambiguous, ask one concise clarification before importing.
3. Run the bundled script yourself via `exec`.
4. Verify and report results.

Bundled script path:

```text
/Users/stone/.openclaw/workspace/skills/oldies-playlist-from-url/scripts/add_song_to_oldies.py
```

Typical internal invocation, run by the agent, not the user:

```bash
python3 /Users/stone/.openclaw/workspace/skills/oldies-playlist-from-url/scripts/add_song_to_oldies.py '<URL>' --title '<title>' --artist '<artist>' --genre '<genre>'
```

If title/artist are unknown, first inspect:

```bash
python3 /Users/stone/.openclaw/workspace/skills/oldies-playlist-from-url/scripts/add_song_to_oldies.py '<URL>' --dry-run
```

## Behavior requirements

- Act in the current turn when possible; do not ask the user to run commands.
- Snapshot the playlist before changing Music. The script does this automatically.
- Do not delete songs unless explicitly asked.
- Avoid duplicates: update an existing track if source ID or exact title/artist already exists.
- For Bilibili 412 errors, retry with Referer/User-Agent. Only use browser cookies with explicit user approval.
- Lyrics are written to the macOS Music `lyrics` field as plain text.
- Lyrics source preference:
  1. LRCLIB high-confidence match.
  2. NetEase public search/lyric API high-confidence match.
  3. If still low confidence, pause and ask before writing lyrics.
- After metadata edits, re-read Music track locations before writing M3U because Music can move/rename files.

## Verification checklist for final response

Report these facts, based on tool output:

- Added/updated track title and artist.
- Playlist track count.
- `missing_paths` count; should be 0.
- `missing_lyrics` count; should be 0 unless user approved otherwise.
- M3U path and lyrics folder path.
