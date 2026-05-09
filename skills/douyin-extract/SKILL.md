---
name: douyin-extract
description: 当用户提供抖音视频链接并要求提取、转录或处理抖音视频时触发。例如"帮我提取下这个抖音视频"、"把这个抖音视频转文字"、"下载这个抖音视频并转录"等。完整流程：下载视频 → 提取音频 → whisper 转录 → 生成结构化文档（核心结论 + 重点信息 + 一句话总结 + 转录原文）→ 询问是否保存到 Obsidian。
---

# 抖音视频提取与转录

当用户提供抖音视频链接时，执行以下完整工作流。

## 命名规则

所有产物使用统一的 `base_name`（格式 `YYYYMMDD-清洁标题`），仅后缀不同：
- 视频：`{base_name}.mp4`
- 音频：`{base_name}.mp3`
- 转录：`{base_name}.txt`
- 文档：`{base_name}.md`

`base_name` 由下载脚本自动生成并输出，后续步骤直接复用，不要重新计算。

## 步骤一：下载视频

```bash
~/whisper-env/bin/python3 /Users/sunli/.claude/skills/douyin-extract/douyin_dl.py "<抖音链接>" /Users/sunli/Downloads
```

脚本输出一行 JSON，包含 `title`、`author`、`duration`、`base_name`、`file`。解析 JSON 记录 `base_name` 和 `file`。

## 步骤二：提取音频

```bash
/opt/homebrew/bin/ffmpeg -i "<file>" -vn -acodec libmp3lame -q:a 2 "/Users/sunli/Downloads/{base_name}.mp3"
```

## 步骤三：语音转文字

```bash
~/whisper-env/bin/whisper "/Users/sunli/Downloads/{base_name}.mp3" --model large-v3 --language zh --output_format txt --output_dir "/Users/sunli/Downloads/"
```

whisper 默认用输入文件名（不含扩展名）作为输出文件名，所以生成的 txt 文件自动为 `{base_name}.txt`。读取该文件内容作为原文。

## 步骤四：生成结构化文档

根据转录原文生成 Markdown 文档，格式如下：

```
---
tags:
  - 从内容提取的关键主题标签
---

# {title}

- 来源：{抖音原始链接}
- 作者：{author}
- 转录时间：{YYYY-MM-DD}
- 原文时长：{duration}

---

## 核心结论

{1-3句话概括核心观点}

## 重点信息

### 1. {要点标题}
- {要点内容}

### 2. {要点标题}
- {要点内容}

## 一句话总结

> {一句话提炼核心信息}

---

## 转录原文

{完整转录原文，按自然段落分段}
```

保存到 `/Users/sunli/Downloads/{base_name}.md`

## 步骤五：询问保存到 Obsidian

使用 AskUserQuestion 询问用户是否保存到 Obsidian。确认后复制 `{base_name}.md` 到 `~/Documents/Obsidian Vault/douyin_raw/`。

## 注意事项

- 所有产物保存到 `/Users/sunli/Downloads/`，文件名统一使用 `base_name`
- whisper 使用 large-v3 模型和 `--language zh` 确保中文转录质量
- 清理转录中明显的重复段落
- tags 从视频内容中智能提取
- 下载脚本路径：`/Users/sunli/.claude/skills/douyin-extract/douyin_dl.py`
