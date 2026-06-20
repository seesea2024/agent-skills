---
name: youtube-downloader
description: 从YouTube链接自动下载MP4视频、提取MP3音频、获取SRT字幕文件的完整流程工具
---

# YouTube Downloader Skill

使用此skill来处理YouTube视频下载的完整流程。

## 功能说明

当用户提供YouTube链接时，执行以下步骤：

1. **下载MP4视频** - 使用yt-dlp从YouTube下载视频
2. **提取MP3音频** - 使用ffmpeg从视频中提取高质量音频
3. **获取SRT字幕** - 优先下载YouTube自带字幕，若无则尝试搜索歌词并手动创建SRT

## 使用方式

当用户说类似以下内容时触发此skill：
- "下载这个YouTube视频"
- "从YouTube下载https://..."
- "帮我下载YouTube视频并提取MP3"
- "/youtube-downloader <链接>"

## 执行步骤

### 1. 验证输入
- 检查是否提供了有效的YouTube链接
- 确认用户的需求

### 2. 下载视频
```bash
yt-dlp -f 18 <youtube_url> --no-update
```
（使用格式18下载包含音频和视频的MP4）

### 3. 提取MP3
```bash
ffmpeg -i <video_file> -q:a 0 -map a <output.mp3> -y
```

### 4. 处理字幕
- 首先检查YouTube是否有字幕：`yt-dlp --list-subs <url>`
- 如有字幕，直接下载：`yt-dlp --write-srt --sub-lang zh-Hans,zh-Hant,en --skip-download <url>`
- 如无字幕，根据视频内容搜索歌词并手动创建SRT文件

### 5. 完成交付
列出所有生成的文件并确认完成。

## 注意事项

- 确保yt-dlp和ffmpeg已安装
- 对于音乐视频，若没有官方字幕，可以搜索歌词创建SRT
- 保持文件命名整洁
