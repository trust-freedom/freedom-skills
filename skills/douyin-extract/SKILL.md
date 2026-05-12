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
- 转录原文：`{base_name}.txt`（whisper 原始输出）
- 转录纠错：`{base_name}-correct.txt`（AI 纠错后）
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

## 步骤 3.5：AI 推理纠错

whisper 转录会产生同音字、专有名词、成语等错误。利用 AI 的语义理解能力，根据上下文推理说话人的真实原意，对转录原文进行纠错。

**处理方式**：读取步骤三生成的 `{base_name}.txt`，直接在当前对话中根据以下规则对全文进行纠错推理，然后将纠错后的文本写入 `{base_name}-correct.txt`（与原文件同目录，不覆盖原文件）。

**纠错规则**：

先通读全文建立上下文理解，再识别并修正转录错误。只改有把握的，不确定的保留原样。

1. **同音字纠错**：根据上下文判断正确用词。例如「高汇报」应为「高回报」、「参断」应为「参战」、「潜水哪来的」应为「钱水哪来的」
2. **专有名词修正**：人名、地名、机构名等。例如「荒姆斯海峡」应为「霍尔木兹海峡」、「罗伯特佩普」应为「Robert Pape」、「银河」在航运语境下应为「运河」（苏伊士运河、巴拿马运河）、「芝博多海峡」应为「直布罗陀海峡」
3. **成语/习语修复**：根据上下文还原被语音混淆的成语。例如「引针止渴」应为「饮鸩止渴」、「沙压着跑路」应为「撒丫子跑路」、「未雨绸幕」应为「未雨绸缪」
4. **专业术语修正**：金融、政治等领域术语。例如「双车制」应为「双赤字」、「法轮」应为「法郎」（法国货币）、「脱势向虚」应为「脱实向虚」
5. **上下文推理**：当某个词在上下文中明显不通时，根据前后文语义推断说话人的真实意图并修正

**注意事项**：

- **只纠错，不润色**：保持说话人的原始口语风格，不要改写成书面语
- **不增删内容**：不添加原话中没有的内容，也不删除任何内容
- **不确定的不改**：如果无法确定原意，保留转录原文，不要猜测
- **保持简体中文**输出
- **保持原有格式**：保留 whisper 输出的换行、段落等原始格式，不要改变排版结构
- 纠错完成后将结果写入 `/Users/sunli/Downloads/{base_name}-correct.txt`，原文件 `{base_name}.txt` 保持不动
- **后续步骤统一使用 `{base_name}-correct.txt`**：步骤四生成结构化文档时，转录原文部分使用 `-correct.txt` 的内容

## 步骤四：生成结构化文档

根据纠错后的转录原文（`{base_name}-correct.txt`）生成 Markdown 文档，格式如下：

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
- 步骤 3.5 的 AI 纠错耗时约 10-20 秒，相对于 whisper 转录可忽略
- 清理转录中明显的重复段落
- tags 从视频内容中智能提取
- 下载脚本路径：`/Users/sunli/.claude/skills/douyin-extract/douyin_dl.py`
