---
name: douyin-extract-v2
description: 抖音视频提取与转录 V2（faster-whisper 分段版）。当用户要求使用 v2 版本提取抖音视频时触发。使用 faster-whisper + 固定时长切分实现断点续传，转录速度比原版快约 4 倍。完整流程：下载视频 → 提取音频 → 分段转录（支持断点续传）→ AI 纠错 + 生成结构化文档 → 询问保存到 Obsidian。
---

# 抖音视频提取与转录 V2

当用户提供抖音视频链接时，执行以下完整工作流。

本版本使用 faster-whisper（CTranslate2 引擎），转录速度约为原版 Whisper 的 4 倍，且支持断点续传。

## 命名规则

所有产物使用统一的 `base_name`（格式 `YYYYMMDD-清洁标题`），仅后缀不同：
- 视频：`{base_name}.mp4`
- 音频：`{base_name}.mp3`
- 分段转录：`{base_name}-0000.txt`、`{base_name}-0001.txt`、...（每个分段一个文件）
- 汇总转录：`{base_name}.txt`（所有分段合并后的完整转录）
- 转录纠错：`{base_name}-correct.txt`（AI 纠错后）
- 文档：`{base_name}.md`
- 临时分段音频：`{base_name}-chunks/` 目录（可手动清理）

`base_name` 由下载脚本自动生成并输出，后续步骤直接复用，不要重新计算。

## 步骤一：下载视频

```bash
~/whisper-env/bin/python3 <skill_root>/douyin_dl.py "<抖音链接>" /Users/sunli/Downloads
```

脚本输出一行 JSON，包含 `title`、`author`、`duration`、`base_name`、`file`。解析 JSON 记录 `base_name` 和 `file`。

## 步骤二：提取音频

```bash
/opt/homebrew/bin/ffmpeg -i "<file>" -vn -acodec libmp3lame -q:a 2 "/Users/sunli/Downloads/{base_name}.mp3"
```

## 步骤三：分段转录（后台运行 + 进度监控）

转录耗时长（1-2 小时），使用后台运行 + 定时监控，用户无需等待。

### 3.1 启动转录

使用 `run_in_background: true` 后台启动转录命令：

```bash
~/whisper-env/bin/python3 <skill_root>/transcribe.py \
  "/Users/sunli/Downloads/{base_name}.mp3" \
  "{base_name}" \
  "/Users/sunli/Downloads/" \
  --chunk-size 600 \
  --model large-v3 \
  --workers 2
```

脚本工作流程：
1. 用 ffmpeg 将音频按固定时长（默认 600 秒 = 10 分钟）切分为多个 mp3 分段
2. 用 faster-whisper（large-v3 模型，int8 量化）逐段转录
3. 相邻 segment 按 1.5 秒停顿阈值自动合并为段落（而非每行一个 fragment）
4. 每完成一个分段，将结果写入 `{base_name}-NNNN.txt`
5. 全部完成后合并所有分段为 `{base_name}.txt`

**断点续传**：如果中途被中断（Ctrl+C、断电等），重新运行相同命令即可。每个分段独立检测其 txt 文件是否存在且非空，已完成的自动跳过，未完成的重新转录。

### 3.2 设置进度监控

转录启动后，使用 CronCreate 设置定时监控（每 10 分钟检查一次），监控逻辑：

1. 检查后台任务是否已完成（通过 `cat {base_name}.txt` 是否存在且非空判断）
2. 如果未完成，统计 `{base_name}-NNNN.txt` 已完成的数量，报告进度（如 "8/15 分段已完成"）
3. 如果已完成，取消定时监控，自动进入步骤四

**关于耗时**：faster-whisper 在 CPU 上约为原版 Whisper 速度的 4 倍。142 分钟音频约 1.5-2 小时可完成。

## 步骤四：AI 纠错 + 生成结构化文档（后台 Agent）

转录完成后，使用一个后台 Agent 同时完成 AI 纠错和文档生成，用户只需等一次通知。

### 后台执行方式

```
Agent({
  description: "AI 转录纠错 + 生成文档",
  run_in_background: true,
  prompt: "请完成以下两个任务：

  ## 任务一：AI 纠错

  原文路径：/Users/sunli/Downloads/{base_name}.txt
  纠错输出：/Users/sunli/Downloads/{base_name}-correct.txt

  读取原文，按三阶段纠错流程执行：
  1. 通读全文 + 构建术语表（提取出现 3 次以上的疑似错误词）
  2. 逐段纠错（同音字、专有名词、成语、专业术语、重复行清理、上下文推理）
  3. 全局一致性校验（确保同一术语全文一致）

  纠错注意事项：
  - 只纠错不润色，保持口语风格
  - 不确定的不改，宁可漏改不可错改
  - 产品名/品牌名必须用 WebSearch 查证后再改，不确定的保留原样
  - 保持中文口语风格（不要把「变形金刚」改成「Transformers」）
  - 保持简体中文输出
  - 保持原有段落格式，不要改变排版结构
  - 将纠错结果写入 {base_name}-correct.txt

  ## 任务二：生成结构化文档

  根据纠错后的文本（{base_name}-correct.txt）生成 Markdown 文档，格式：

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

  {完整纠错后的转录原文}

  保存到 /Users/sunli/Downloads/{base_name}.md"
})
```

Agent 完成后会自动通知。收到通知后：
1. 验证 `{base_name}-correct.txt` 已生成且非空
2. 验证 `{base_name}.md` 已生成且非空
3. 进入步骤五

## 步骤五：询问保存到 Obsidian

使用 AskUserQuestion 询问用户是否保存到 Obsidian。确认后复制 `{base_name}.md` 到 `~/Documents/Obsidian Vault/douyin_raw/`。

## 注意事项

- 所有产物保存到 `/Users/sunli/Downloads/`，文件名统一使用 `base_name`
- 使用 faster-whisper（large-v3 模型 + int8 量化），转录速度约为原版 Whisper 的 4 倍
- 转录输出为纯文本段落（无时间戳），相邻 segment 按 1.5 秒停顿阈值自动合并为段落
- 支持断点续传：中断后重新运行相同命令，每个分段独立检测完成状态，自动跳过已完成的分段
- `--workers` 控制并行转录进程数（默认 1，推荐 2），每个进程独立加载模型
- 临时分段音频保存在 `{base_name}-chunks/` 目录，转录完成后可手动删除
- 步骤三后台运行 + 定时进度监控，步骤四后台 Agent 执行纠错+文档生成，全程用户无需等待确认
- tags 从视频内容中智能提取
- 下载脚本路径：`<skill_root>/douyin_dl.py`
- 转录脚本路径：`<skill_root>/transcribe.py`
