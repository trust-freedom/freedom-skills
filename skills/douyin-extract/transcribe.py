#!/usr/bin/env python3
"""
Chunked transcription using faster-whisper with parallel workers and resume support.

Usage:
    ~/whisper-env/bin/python3 transcribe.py <audio_file> <base_name> <output_dir> [--chunk-size 600] [--model large-v3] [--workers 1]

Output:
    - Individual chunk files: {base_name}-0000.txt, {base_name}-0001.txt, ...
    - Merged file: {base_name}.txt (after all chunks complete)
"""

import argparse
import json
import os
import subprocess
from multiprocessing import Pool

# Use HuggingFace mirror for China network
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "/opt/homebrew/bin/ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def split_audio(audio_path: str, chunk_seconds: int, tmp_dir: str) -> list[str]:
    """Split audio into fixed-length chunks using ffmpeg. Returns list of chunk file paths."""
    duration = get_audio_duration(audio_path)
    chunk_paths = []
    start = 0.0
    idx = 0

    while start < duration:
        chunk_path = os.path.join(tmp_dir, f"chunk_{idx:04d}.mp3")
        cmd = [
            "/opt/homebrew/bin/ffmpeg", "-y", "-v", "quiet",
            "-i", audio_path,
            "-ss", str(start),
            "-t", str(chunk_seconds),
            "-acodec", "libmp3lame", "-q:a", "2",
            chunk_path,
        ]
        subprocess.run(cmd, check=True)

        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
            chunk_paths.append(chunk_path)
        start += chunk_seconds
        idx += 1

    return chunk_paths


# --- Worker: each process loads its own model instance ---

_model = None


def _init_worker(model_name: str):
    global _model
    from faster_whisper import WhisperModel
    _model = WhisperModel(model_name, device="cpu", compute_type="int8")


def _transcribe_one(task: tuple) -> tuple:
    """Transcribe a single chunk. Returns (idx, skipped, char_count)."""
    idx, chunk_path, base_name, chunks_dir = task
    chunk_txt = os.path.join(chunks_dir, f"{base_name}-{idx:04d}.txt")

    # Already done? (txt file exists and non-empty)
    if os.path.exists(chunk_txt) and os.path.getsize(chunk_txt) > 0:
        return (idx, True, os.path.getsize(chunk_txt))

    # Transcribe
    segments, _ = _model.transcribe(
        chunk_path,
        language="zh",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
        initial_prompt="以下是普通话的句子，包含标点符号。请使用逗号、句号等标点。",
    )

    # Each segment = one line; pause >= 0.5s = blank line (paragraph break)
    # Force a paragraph break every max_consecutive lines without one
    max_consecutive = 8
    seg_list = list(segments)
    lines = []
    since_break = 0
    for i, seg in enumerate(seg_list):
        text = seg.text.strip()
        if not text:
            continue
        lines.append(text)
        since_break += 1
        do_break = False
        if i + 1 < len(seg_list):
            gap = seg_list[i + 1].start - seg.end
            if gap >= 0.5:
                do_break = True
        if since_break >= max_consecutive:
            do_break = True
        if do_break:
            lines.append("")
            since_break = 0
    text = "\n".join(lines)

    with open(chunk_txt, "w", encoding="utf-8") as f:
        f.write(text)

    return (idx, False, len(text))


def merge_files(chunk_txt_paths: list[str], output_path: str):
    """Merge all chunk txt files into a single file."""
    with open(output_path, "w", encoding="utf-8") as out:
        first = True
        for p in chunk_txt_paths:
            if os.path.exists(p):
                if not first:
                    out.write("\n")
                first = False
                with open(p, "r", encoding="utf-8") as f:
                    out.write(f.read().rstrip("\n"))
                    out.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Chunked faster-whisper transcription")
    parser.add_argument("audio_file", help="Path to audio file")
    parser.add_argument("base_name", help="Base name for output files")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--chunk-size", type=int, default=600, help="Chunk size in seconds (default: 600)")
    parser.add_argument("--model", default="large-v3", help="Whisper model name (default: large-v3)")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers (default: 1)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # --- Split audio ---
    tmp_dir = os.path.join(args.output_dir, f"{args.base_name}-chunks")
    os.makedirs(tmp_dir, exist_ok=True)

    existing_chunks = sorted(
        [os.path.join(tmp_dir, f) for f in os.listdir(tmp_dir) if f.startswith("chunk_") and f.endswith(".mp3")]
    )
    if existing_chunks:
        chunk_paths = existing_chunks
        print(f"[SPLIT] Reusing {len(chunk_paths)} existing chunks")
    else:
        print(f"[SPLIT] Splitting audio into {args.chunk_size}s chunks...")
        chunk_paths = split_audio(args.audio_file, args.chunk_size, tmp_dir)

    total = len(chunk_paths)
    print(f"[SPLIT] Total chunks: {total}")

    # --- Build task list ---
    tasks = []
    for idx, chunk_path in enumerate(chunk_paths):
        tasks.append((idx, chunk_path, args.base_name, tmp_dir))

    # --- Transcribe with parallel workers ---
    print(f"[MODEL] Loading {args.model} into {args.workers} worker(s)...")
    workers = min(args.workers, total)

    completed_count = sum(
        1 for idx in range(total)
        if os.path.exists(os.path.join(tmp_dir, f"{args.base_name}-{idx:04d}.txt"))
        and os.path.getsize(os.path.join(tmp_dir, f"{args.base_name}-{idx:04d}.txt")) > 0
    )
    print(f"[RESUME] {completed_count}/{total} chunks already completed")

    with Pool(workers, initializer=_init_worker, initargs=(args.model,)) as pool:
        results = pool.imap_unordered(_transcribe_one, tasks)

        done = completed_count
        for idx, skipped, chars in results:
            done += 1
            status = "SKIP" if skipped else "DONE"
            print(f"[{status}] Chunk {idx + 1}/{total} ({chars} chars) [{done}/{total} total]")

    # --- Merge ---
    chunk_txt_paths = [
        os.path.join(tmp_dir, f"{args.base_name}-{idx:04d}.txt")
        for idx in range(total)
    ]
    merged_path = os.path.join(args.output_dir, f"{args.base_name}.txt")
    merge_files(chunk_txt_paths, merged_path)
    print(f"[MERGE] All {total} chunks merged into: {merged_path}")
    print("[DONE] Transcription complete.")


if __name__ == "__main__":
    main()
