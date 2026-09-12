"""Разбиение статей базы знаний на фрагменты.

Фрагмент — минимальная единица, на которую помощник имеет право сослаться.
Режем по смысловым блокам, а не по символам: инструкция из пяти шагов
должна остаться целой, иначе ответ соберётся из половинок разных процедур.
"""
import re

MAX_CHARS = 420
MIN_CHARS = 120


def split_article(title: str, body: str) -> list[str]:
    body = (body or "").strip()
    if not body:
        return []

    blocks = _split_by_blocks(body)
    chunks: list[str] = []
    buffer = ""

    for block in blocks:
        if not buffer:
            buffer = block
        elif len(buffer) + len(block) + 1 <= MAX_CHARS:
            buffer = f"{buffer}\n{block}"
        else:
            chunks.append(buffer)
            buffer = block

    if buffer:
        if chunks and len(buffer) < MIN_CHARS:
            chunks[-1] = f"{chunks[-1]}\n{buffer}"
        else:
            chunks.append(buffer)

    return [f"{title}\n{chunk}".strip() if title else chunk for chunk in chunks]


def _split_by_blocks(body: str) -> list[str]:
    """Сначала по абзацам, слишком длинные — по нумерованным пунктам, затем по фразам."""
    blocks: list[str] = []
    for paragraph in re.split(r"\n{2,}", body):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= MAX_CHARS:
            blocks.append(paragraph)
            continue
        for piece in re.split(r"\n(?=\d+[.)]\s)", paragraph):
            piece = piece.strip()
            if not piece:
                continue
            if len(piece) <= MAX_CHARS:
                blocks.append(piece)
            else:
                blocks.extend(_split_sentences(piece))
    return blocks


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    buffer = ""
    for part in parts:
        if len(buffer) + len(part) + 1 <= MAX_CHARS:
            buffer = f"{buffer} {part}".strip()
        else:
            if buffer:
                out.append(buffer)
            buffer = part
    if buffer:
        out.append(buffer)
    return out
