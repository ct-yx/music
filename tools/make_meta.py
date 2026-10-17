#!/usr/bin/env python3
"""Print MusicXML-derived metadata suggestions without editing meta.json."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    from music21 import chord, converter, dynamics, expressions, note, stream, tempo
except ImportError as error:  # pragma: no cover - depends on the optional local tool
    raise SystemExit("需要先安装 music21：python -m pip install music21") from error


def absolute_offset(element: object, parent: object) -> float:
    try:
        return float(element.getOffsetInHierarchy(parent))
    except (AttributeError, TypeError, ValueError):
        return float(getattr(element, "offset", 0.0))


def measures_and_starts(score: stream.Score) -> tuple[list[tuple[int, float, float]], list[float]]:
    parts = list(score.parts)
    if not parts:
        raise ValueError("MusicXML 中没有乐器声部")
    first_part_measures = list(parts[0].getElementsByClass(stream.Measure))
    if not first_part_measures:
        first_part_measures = list(parts[0].recurse().getElementsByClass(stream.Measure))
    rows: list[tuple[int, float, float]] = []
    cursor = 0.0
    for position, measure in enumerate(first_part_measures, start=1):
        number = int(getattr(measure, "number", position) or position)
        length = float(measure.duration.quarterLength)
        rows.append((number, cursor, length))
        cursor += length
    return rows, [row[1] for row in rows]


def tempo_events(score: stream.Score) -> list[tuple[float, float, str]]:
    events = []
    for mark in score.recurse().getElementsByClass(tempo.MetronomeMark):
        bpm = mark.getQuarterBPM()
        if bpm and math.isfinite(float(bpm)) and float(bpm) > 0:
            events.append((absolute_offset(mark, score), float(bpm), str(mark.text or "")))
    # MusicXML often stores "rit." as a text direction beside the next
    # metronome mark. Keep it as a tempo event so the integration below
    # ramps toward that next mark instead of treating both bars as constant.
    for expression in score.recurse().getElementsByClass(expressions.TextExpression):
        text = str(getattr(expression, "content", "") or getattr(expression, "text", ""))
        if "rit" not in text.casefold():
            continue
        events.append((absolute_offset(expression, score), tempo_at(sorted(events), absolute_offset(expression, score)), text))
    return sorted(events, key=lambda event: event[0])


def tempo_at(events: list[tuple[float, float, str]], position: float) -> float:
    value = 66.0
    for start, bpm, _ in events:
        if start > position:
            break
        value = bpm
    return value


def integrated_seconds(
    start: float,
    end: float,
    events: list[tuple[float, float, str]],
) -> float:
    """Integrate quarter-note time, linearly interpreting marked ritardandi."""
    if end <= start:
        return 0.0
    boundaries = {start, end}
    for position, _, _ in events:
        if start < position < end:
            boundaries.add(position)
    ordered = sorted(boundaries)
    total = 0.0
    for left, right in zip(ordered, ordered[1:]):
        midpoint = (left + right) / 2
        active_index = -1
        for index, event in enumerate(events):
            if event[0] <= midpoint:
                active_index = index
            else:
                break
        if active_index < 0:
            bpm = 66.0
            total += (right - left) * 60.0 / bpm
            continue
        event_start, start_bpm, text = events[active_index]
        if "rit" not in text.lower():
            total += (right - left) * 60.0 / start_bpm
            continue
        next_event = events[active_index + 1] if active_index + 1 < len(events) else None
        target_bpm = next_event[1] if next_event and next_event[1] < start_bpm else start_bpm * 0.9
        ramp_end = next_event[0] if next_event and next_event[0] > event_start else event_start + 8.0
        span = max(ramp_end - event_start, 1e-9)
        bpm_left = start_bpm + (target_bpm - start_bpm) * max(0.0, min(1.0, (left - event_start) / span))
        bpm_right = start_bpm + (target_bpm - start_bpm) * max(0.0, min(1.0, (right - event_start) / span))
        average_bpm = max((bpm_left + bpm_right) / 2, 1e-6)
        total += (right - left) * 60.0 / average_bpm
    return total


def measure_durations(rows: list[tuple[int, float, float]], events: list[tuple[float, float, str]]) -> tuple[list[float], float]:
    starts: list[float] = []
    elapsed = 0.0
    for _, offset, length in rows:
        starts.append(elapsed)
        elapsed += integrated_seconds(offset, offset + length, events)
    return starts, elapsed


def envelope_for_score(score: stream.Score, rows: list[tuple[int, float, float]]) -> list[float]:
    totals = [0.0 for _ in rows]
    weights = [0.0 for _ in rows]
    for part in score.parts:
        events: list[tuple[float, int, object]] = []
        for item in part.recurse().getElementsByClass(dynamics.Dynamic):
            events.append((absolute_offset(item, part), 0, item))
        for item in part.recurse().notes:
            if not isinstance(item, (note.Note, chord.Chord)):
                continue
            events.append((absolute_offset(item, part), 1, item))
        events.sort(key=lambda event: (event[0], event[1]))
        active_level = 0.5
        event_index = 0
        for measure_index, (_, start, length) in enumerate(rows):
            end = start + length
            while event_index < len(events) and events[event_index][0] < start:
                _, kind, item = events[event_index]
                if kind == 0:
                    active_level = float(item.volumeScalar)
                event_index += 1
            cursor = event_index
            while cursor < len(events) and events[cursor][0] < end:
                _, kind, item = events[cursor]
                if kind == 0:
                    active_level = float(item.volumeScalar)
                else:
                    duration = max(float(item.duration.quarterLength), 0.0)
                    if duration > 0:
                        totals[measure_index] += active_level * duration
                        weights[measure_index] += duration
                cursor += 1
            event_index = cursor
    averages = [totals[index] / weights[index] if weights[index] else 0.0 for index in range(len(rows))]
    maximum = max(averages, default=0.0)
    if maximum <= 0:
        return [0.0 for _ in averages]
    return [round(max(0.0, min(1.0, value / maximum)), 3) for value in averages]


def suggestions(path: Path) -> dict[str, object]:
    score = converter.parse(str(path))
    rows, _ = measures_and_starts(score)
    events = tempo_events(score)
    starts, duration = measure_durations(rows, events)
    return {
        "bars": len(rows),
        "duration": round(duration),
        "measureStarts": [round(value, 2) for value in starts],
        "envelope": envelope_for_score(score, rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="读取 MusicXML 并输出 meta.json 字段建议，不会修改现有字段。")
    parser.add_argument("musicxml", type=Path, help="MusicXML 文件路径")
    args = parser.parse_args()
    try:
        print(json.dumps(suggestions(args.musicxml), ensure_ascii=False, indent=2))
    except Exception as error:  # Show a useful CLI error without touching content files.
        print(f"生成建议失败：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
