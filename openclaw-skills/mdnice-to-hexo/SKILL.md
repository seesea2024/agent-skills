---
name: mdnice-to-hexo
description: Sync Markdown articles from mdnice editor to local Hexo blog. Use when user asks to "sync mdnice", "publish to hexo", "mdnice 同步", or wants to move articles from mdnice to their Hexo blog.
---

# mdnice 文章同步到 Hexo 博客

## 功能描述

将 mdnice 编辑器中的 Markdown 文章同步到本地 Hexo 博客仓库，自动处理格式、添加 YAML front matter、保存到 source/_posts 目录。

## 工具脚本

博客仓库已内置同步脚本：`tools/mdnice_sync.py`

## 使用步骤

### Step 1: 从 mdnice 复制文章

1. 打开 mdnice 编辑器：`https://editor.mdnice.com/?outId=xxx`
2. 点击右上角 **"导出"** → 选择 **"Markdown"**
3. 全选复制所有 Markdown 内容

### Step 2: 粘贴到临时文件

将复制的内容粘贴到：
```
blog/tools/mdnice_content.txt
```

### Step 3: 运行同步脚本

```bash
cd blog

# 基础用法
python tools/mdnice_sync.py "文章标题"

# 带标签
python tools/mdnice_sync.py "技术分享" "Python,博客,OpenClaw"

# 带标签和分类
python tools/mdnice_sync.py "云原生实践" "K8s,Docker" "技术"
```

### Step 4: 提交部署

```bash
git add source/_posts/文章标题.md
git commit -m "post: 文章标题"
git push
```

## 脚本功能

✅ 自动清理 mdnice 导出格式（多余空行、<br>标记）
✅ 自动检测并移除重复标题
✅ 自动生成 Hexo YAML front matter（日期、标签、分类）
✅ 自动生成安全的文件名
✅ 自动保存到 source/_posts 目录

## 手动操作（备选）

如果脚本不能用，手动操作：

1. 创建文章文件：`source/_posts/文章标题.md`
2. 添加 front matter：
```yaml
---
title: 文章标题
date: YYYY-MM-DD HH:MM:SS
tags: [标签1, 标签2]
categories: [分类]
---
```
3. 粘贴 Markdown 内容
4. 提交 git

## 注意事项

- 🖼️ 图片链接：mdnice 的图片是临时的，建议下载后上传到自己的图床
- 💻 代码块：检查代码块语言标识是否正确
- 📎 链接：检查所有链接是否有效
- 🌏 编码：中文文件名在各系统都兼容，但建议用拼音或英文更保险

## 快速命令

```bash
# 一键流程（复制内容后执行）
cd blog && python tools/mdnice_sync.py "文章标题" && git add source/_posts/*.md && git commit -m "post: 文章标题" && git push
```
