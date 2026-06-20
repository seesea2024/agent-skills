---
name: guitar-tab-downloader
description: 从吉他谱网站下载吉他谱图片，支持通过URL直接下载或通过歌名搜索下载（支持jitafen.com、21qupu.com）
---

# 吉他谱下载器 Skill

使用此skill从吉他谱网站下载吉他谱图片。支持两种方式：通过URL直接下载，或通过歌名搜索下载。

## 功能说明

### 方式一：通过URL下载
当用户提供吉他谱页面URL时，执行以下步骤：

1. **解析页面** - 使用Python脚本解析吉他谱页面HTML
2. **提取信息** - 自动提取歌曲名、歌手、调式、拍子、速度、难度等信息
3. **下载图片** - 批量下载所有吉他谱图片到当前目录
4. **自动命名** - 使用歌曲名+序号自动命名文件

### 方式二：通过歌名搜索下载
当用户提供歌名时，执行以下步骤：

1. **搜索曲谱** - 在jitafen.com搜索该歌名
2. **显示结果** - 显示搜索结果数量
3. **选择并下载** - 自动选择第一个搜索结果并下载

## 支持的网站

- 吉他粉 (jitafen.com) - m.jitafen.com, www.jitafen.com（支持搜索和URL下载）
- 21曲谱 (21qupu.com) - www.21qupu.com（仅支持URL下载）

## 使用方式

当用户说类似以下内容时触发此skill：

### URL下载方式：
- "下载这个吉他谱：http://m.jitafen.com/pu/lxp/133267.html"
- "下载吉他谱 https://..."
- "帮我下载这个吉他谱"
- "/guitar-tab-downloader <链接>"

### 搜索下载方式：
- "搜索并下载《青春》吉他谱"
- "下载《一生所爱》吉他谱"
- "找一下《童年》的吉他谱"
- "/guitar-tab-downloader <歌名>"

## 执行步骤

### 1. 验证输入
- 检查输入是URL还是歌名
- 确认当前工作目录

### 2. 使用下载脚本

#### 如果是URL：
```bash
python3 /Users/stone/git-code/guitar-sheet/img-sheet/download_guitar_tab.py <guitar_tab_url>
```

#### 如果是歌名（搜索）：
```bash
python3 /Users/stone/git-code/guitar-sheet/img-sheet/download_guitar_tab.py --search <song_name>
```

脚本会自动：
- 如果是URL：获取页面内容、解析歌曲信息、找到并下载图片
- 如果是歌名：搜索曲谱、显示结果、选择第一个并下载

### 3. 完成交付
列出所有下载的图片文件并确认完成。

## 注意事项

- 确保Python 3和requests库已安装
- 下载的图片会保存在当前工作目录
- 支持PNG、JPG、WEBP、GIF等图片格式
- 如果文件名已存在，会自动添加序号避免覆盖
- 搜索功能目前仅支持jitafen.com
