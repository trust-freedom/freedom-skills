# Freedom Skills

个人维护的 Claude Code 自定义 Skills 集合，通过软链接方式挂载到 `~/.claude/skills/` 目录下使用。

<br>

## Skills 总览

| Skill | 说明 | 触发示例 | 依赖 |
| --- | --- | --- | --- |
| douyin-extract | 抖音视频下载、分段音频转录（faster-whisper）、AI 纠错、生成结构化文档 | "帮我提取下这个抖音视频" | python3, ffmpeg, faster-whisper |

<br>

## Skills 详情

### douyin-extract — 抖音视频提取与转录

**用途：** 下载抖音视频，提取音频，通过 faster-whisper 分段转录为文字，AI 纠错后生成结构化的 Markdown 文档（含核心结论、重点信息、一句话总结、转录原文），可选保存到 Obsidian。

**触发方式：** 向 Claude 提供抖音视频链接并提出相关需求，例如：
- "帮我提取下这个抖音视频"
- "把这个抖音视频转文字"
- "下载这个抖音视频并转录"
- "帮我分析这个抖音视频的内容"

**执行流程：**

1. **下载视频** — 运行 `douyin_dl.py` 脚本，解析抖音分享页提取无水印视频 URL 并下载，输出包含 `title`、`author`、`duration`、`base_name`、`file` 的 JSON
2. **提取音频** — 使用 `ffmpeg` 从视频中提取 MP3 音频
3. **分段转录** — 使用 `transcribe.py`（基于 faster-whisper，large-v3 模型，int8 量化）将音频按 10 分钟切分后并行转录，支持断点续传。转录输出为纯文本段落（无时间戳），按 1.5 秒停顿阈值自动合并为段落
4. **AI 纠错 + 生成文档** — 后台 Agent 一次完成：三阶段纠错（通读术语表 → 逐段纠错 → 全局一致性校验，专有名词/产品名通过 WebSearch 查证）+ 生成含标签、核心结论、重点信息、一句话总结的 Markdown
5. **保存到 Obsidian** — 询问用户是否将文档保存到 Obsidian Vault

**产物命名规则：** 所有产物使用统一的 `{YYYYMMDD-清洁标题}` 作为 `base_name`，仅后缀不同（`.mp4` / `.mp3` / `.txt` / `-correct.txt` / `.md`），均保存在 `~/Downloads/`。

**本机依赖：**
- `python3` — 运行下载脚本和转录脚本
- `ffmpeg` — 音频提取和分段切分（Homebrew 安装，路径 `/opt/homebrew/bin/ffmpeg`）
- `faster-whisper` — CTranslate2 引擎的 Whisper 实现，转录速度约为原版 4 倍（安装在 `~/whisper-env/` 虚拟环境中，使用 large-v3 模型 + int8 量化）
- `requests` — Python HTTP 库（下载脚本依赖）

<br>

## 安装使用

将本项目中的 skill 以软链接方式挂载到 Claude Code 的 skills 目录：

```bash
ln -s /path/to/freedom-skills/skills/<skill-name> ~/.claude/skills/<skill-name>
```

例如：

```bash
ln -s /Users/sunli/code/skills/freedom-skills/skills/douyin-extract ~/.claude/skills/douyin-extract
```
