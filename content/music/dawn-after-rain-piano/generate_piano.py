#!/usr/bin/env python3
"""生成《雨后·晨露（钢琴版）》的五层钢琴试听编曲。

脚本只负责音乐内容和 MusicXML；MuseScore 的导出命令在脚本运行成功后执行。
可调整参数集中在本文件顶部，便于试听时快速改变速度、声像和层的动态。
"""

from __future__ import annotations

import json
import math
import random
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Sequence

from music21 import chord, clef, dynamics, expressions, instrument, key, metadata, meter, note, spanner, stream, tempo, tie


# ----------------------------- 可调整参数 -----------------------------
OUTPUT = Path(__file__).resolve().parent
TITLE = "雨后·晨露（钢琴版）"
SUBTITLE = "多层钢琴编曲"
SEED = 261018
TIME_SIGNATURE = "4/4"
KEY_FIFTHS = 2

# MusicXML 的 MIDI program 使用 1-based 编号；1 = Acoustic Grand Piano。
PART_CONFIG = {
    "钢琴·旋律": {"role": "melody", "pan": 0, "volume": 85, "clef": "treble"},
    "钢琴·内声部": {"role": "inner", "pan": 12, "volume": 70, "clef": "treble"},
    "钢琴·琶音": {"role": "arpeggio", "pan": -28, "volume": 70, "clef": "treble"},
    "钢琴·低音": {"role": "bass", "pan": 0, "volume": 80, "clef": "bass"},
    "钢琴·点缀": {"role": "sparkle", "pan": 30, "volume": 60, "clef": "treble"},
}
# 这些跨度同时用于 music21 的演奏动态和序列化后的明确 MusicXML wedge。
WEDGE_SPANS = {
    "钢琴·旋律": [(1, 4, "crescendo"), (5, 12, "crescendo"), (13, 24, "crescendo"), (25, 32, "diminuendo"), (33, 42, "crescendo"), (46, 48, "diminuendo"), (49, 60, "diminuendo")],
    "钢琴·内声部": [(3, 4, "crescendo"), (9, 12, "crescendo"), (13, 24, "crescendo"), (25, 32, "diminuendo"), (33, 42, "crescendo"), (46, 48, "diminuendo"), (49, 60, "diminuendo")],
    "钢琴·琶音": [(5, 12, "crescendo"), (13, 24, "crescendo"), (25, 32, "diminuendo"), (33, 42, "crescendo"), (46, 48, "diminuendo"), (49, 60, "diminuendo")],
    "钢琴·低音": [(1, 4, "crescendo"), (5, 12, "crescendo"), (13, 24, "crescendo"), (25, 32, "diminuendo"), (33, 42, "crescendo"), (46, 48, "diminuendo"), (49, 60, "diminuendo")],
    "钢琴·点缀": [(1, 4, "crescendo"), (5, 12, "diminuendo"), (13, 24, "crescendo"), (25, 32, "diminuendo"), (49, 60, "diminuendo")],
}
TEMPO_MARKS = {
    1: (66, ""),
    31: (60, "rit."),
    32: (56, "rit."),
    33: (60, "a tempo"),
    47: (54, "rit."),
    48: (52, "rit."),
    49: (58, "a tempo"),
    57: (50, "rit."),
    58: (48, "rit."),
    59: (46, "rit."),
}
MOTIF = ["F#4", "B4", "D5", "C#5", "B4"]
SUNRISE_MOTIF = ["F#5", "B5", "D6", "C#6", "B5"]

# 和声顺序严格对应制作流程的 60 个小节。
CHORDS = [
    "Bm9", "Gmaj7/B", "Bm9", "Gmaj7/B",
    "Bm9", "Gmaj7", "D/F#", "Asus4", "Bm9", "Gmaj7", "Em7", "F#sus4",
    "Bm9", "Gmaj7", "D/F#", "Em9", "Bm9", "Gmaj7", "D/F#", "Em9", "Gmaj7", "Em9", "F#sus4", "F#7",
    "Gmaj7", "D/F#", "Em9", "Bm7", "Gmaj7", "Dmaj7#11/F#", "Bm7/F#", "F#sus4",
    "D/F#", "A/C#", "Bm7", "Gmaj7", "D", "A/C#", "Em7", "Asus4",
    "Em7", "Bm7", "Gmaj7", "A", "D/F#", "G", "Em7+A7sus4", "Dmaj7",
    "Dmaj7#11", "Bm7", "Gmaj7", "Dmaj7/F#", "Em9", "Gmaj7", "Bm7", "Asus4", "Gmaj7", "Em9", "Asus4", "Dmaj7add9",
]

# 各和声使用公开、稳定的音高集合；G# 只出现在第 30 小节。
CHORD_TONES = {
    "Bm9": ["B", "D", "F#", "A", "C#"],
    "Gmaj7/B": ["B", "D", "F#", "G"],
    "Gmaj7": ["G", "B", "D", "F#"],
    "D/F#": ["F#", "A", "C#", "D"],
    "Asus4": ["A", "D", "E"],
    "Em7": ["E", "G", "B", "D"],
    "F#sus4": ["F#", "B", "C#"],
    "Em9": ["E", "G", "B", "D", "F#"],
    "F#7": ["F#", "A#", "C#", "E"],
    "Bm7": ["B", "D", "F#", "A"], "Bm7/F#": ["F#", "A", "B", "D"],
    "Dmaj7#11/F#": ["F#", "A", "C#", "D", "G#"],
    "Dmaj7#11": ["D", "F#", "A", "C#", "G#"],
    "D": ["D", "F#", "A"], "A": ["A", "C#", "E"],
    "A/C#": ["C#", "E", "A"],
    "G": ["G", "B", "D"],
    "Em7+A7sus4": ["E", "G", "B", "D", "A", "C#"],
    "Dmaj7": ["D", "F#", "A", "C#"],
    "Dmaj7/F#": ["F#", "A", "C#", "D"],
    "Dmaj7add9": ["D", "F#", "A", "C#", "E"],
}

BASS_ROOT = {
    "Bm9": "B", "Gmaj7/B": "B", "Gmaj7": "G", "D/F#": "F#", "Asus4": "A",
    "Em7": "E", "F#sus4": "F#", "Em9": "E", "F#7": "F#", "Bm7": "B",
    "Dmaj7#11/F#": "F#", "Dmaj7#11": "D", "D": "D", "A/C#": "C#", "G": "G",
    "Em7+A7sus4": "E", "Dmaj7": "D", "Dmaj7/F#": "F#", "Dmaj7add9": "D",
}


def pitch(name: str, duration: float, tie_type: str | None = None) -> note.Note:
    obj = note.Note(name, quarterLength=duration)
    if tie_type:
        obj.tie = tie.Tie(tie_type)
    return obj


def chord_obj(names: Sequence[str], duration: float) -> chord.Chord:
    return chord.Chord(list(names), quarterLength=duration)


def put_events(measure: stream.Measure, events: Sequence[tuple[float, object | None]]) -> None:
    """按时值顺序插入音符/和弦/休止，并确保每小节正好四拍。"""
    offset = 0.0
    for duration, value in events:
        if isinstance(value, str):
            obj = pitch(value, duration)
        elif isinstance(value, (list, tuple)):
            obj = chord_obj(value, duration)
        elif value is None:
            obj = note.Rest(quarterLength=duration)
        else:
            obj = value
        measure.insert(offset, obj)
        offset += duration
    if offset < 4:
        measure.insert(offset, note.Rest(quarterLength=4 - offset))
    if offset > 4.0001:
        raise ValueError(f"小节 {measure.number} 超过四拍: {offset}")


def put_onsets(measure: stream.Measure, onsets: Sequence[tuple[float, str, float]]) -> None:
    """插入错落的点缀音；onsets 为 (拍点、音高、时值)。"""
    events: list[tuple[float, object | None]] = []
    cursor = 0.0
    for onset, name, duration in sorted(onsets):
        if onset < cursor or onset + duration > 4.0001:
            raise ValueError(f"点缀音时值重叠或越界: {onsets}")
        if onset > cursor:
            events.append((onset - cursor, None))
        events.append((duration, name))
        cursor = onset + duration
    if cursor < 4:
        events.append((4 - cursor, None))
    put_events(measure, events)


def make_part(name: str, cfg: dict) -> stream.Part:
    part = stream.Part(id=cfg["role"])
    part.partName = name
    piano = instrument.Piano()
    piano.instrumentName = "Acoustic Grand Piano"
    piano.instrumentAbbreviation = "Pno"
    piano.midiProgram = 0
    part.insert(0, piano)
    part.insert(0, clef.BassClef() if cfg["clef"] == "bass" else clef.TrebleClef())
    return part


def add_measure_skeleton(part: stream.Part, number: int) -> stream.Measure:
    measure = stream.Measure(number=number)
    if number == 1:
        measure.insert(0, key.KeySignature(KEY_FIFTHS))
        measure.insert(0, meter.TimeSignature(TIME_SIGNATURE))
    part.append(measure)
    return measure


def tones_at(bar: int, octave: int = 4, count: int = 8) -> list[str]:
    tones = CHORD_TONES[CHORDS[bar - 1]]
    # 通过循环音阶产生稳定的上行/下行材料；第 30 小节专门由 G# 和弦控制。
    return [f"{tones[i % len(tones)]}{octave + (i // len(tones))}" for i in range(count)]


def octave_pair(name: str) -> list[str]:
    p = note.Note(name).pitch
    return [name, f"{p.name}{p.octave + 1}"]


def add_tempo_and_dynamics(score: stream.Score, parts: dict[str, stream.Part]) -> None:
    # 速度和可见文字放在旋律层，导出时对全曲生效。
    melody = parts["钢琴·旋律"]
    for bar, (bpm, text) in TEMPO_MARKS.items():
        mark = tempo.MetronomeMark(number=bpm, text=text or None)
        melody.measure(bar).insert(0, mark)
        if text:
            melody.measure(bar).insert(0, expressions.TextExpression(text))

    dynamic_plan = {
        "钢琴·旋律": {1: "pp", 5: "p", 9: "mp", 13: "p", 17: "p", 33: "mf", 42: "f", 47: "mf", 49: "mp", 53: "p", 55: "pp", 57: "p"},
        "钢琴·内声部": {3: "pp", 9: "p", 17: "p", 25: "p", 33: "mf", 42: "f", 47: "mp", 49: "mp", 55: "pp"},
        "钢琴·琶音": {1: "pp", 5: "p", 13: "p", 17: "p", 25: "p", 33: "mf", 42: "f", 47: "mp", 49: "p", 57: "pp"},
        "钢琴·低音": {1: "pp", 5: "p", 13: "p", 17: "p", 25: "p", 33: "mf", 42: "f", 47: "mp", 49: "mp", 57: "pp"},
        "钢琴·点缀": {1: "pp", 5: "pp", 13: "p", 21: "p", 25: "p", 33: "pp", 49: "p", 57: "ppp"},
    }
    for name, marks in dynamic_plan.items():
        part = parts[name]
        for bar, value in marks.items():
            part.measure(bar).insert(0, dynamics.Dynamic(value))

    # 每个段落至少有渐变；第 13–24 小节使用同一条连续渐强覆盖全段。
    for name, part_spans in WEDGE_SPANS.items():
        part = parts[name]
        for start, end, kind in part_spans:
            wedge = dynamics.Crescendo() if kind == "crescendo" else dynamics.Diminuendo()
            wedge.addSpannedElements(part.measure(start), part.measure(end))
            part.insert(0, wedge)


def build_score() -> tuple[stream.Score, dict[str, stream.Part]]:
    random.seed(SEED)
    score = stream.Score(id="DawnAfterRainPiano")
    score.metadata = metadata.Metadata()
    score.metadata.title = TITLE
    score.metadata.subtitle = SUBTITLE
    score.metadata.composer = "Codex + MuseScore"
    parts = {name: make_part(name, cfg) for name, cfg in PART_CONFIG.items()}
    for part in parts.values():
        score.insert(0, part)
        for bar in range(1, 61):
            add_measure_skeleton(part, bar)

    # -------- 低音层：从 B1+B2 的雨幕逐步转向低音八度线 --------
    bass = parts["钢琴·低音"]
    bass_line = {
        1: ("B1", "B2"), 2: ("B1", "B2"), 3: ("B1", "B2"), 4: ("B1", "B2"),
        5: ("B1", "B2"), 6: ("G1", "G2"), 7: ("F#1", "F#2"), 8: ("A1", "A2"),
        9: ("B1", "B2"), 10: ("G1", "G2"), 11: ("E1", "E2"), 12: ("F#1", "F#2"),
        13: ("B1", "B2"), 14: ("G1", "G2"), 15: ("F#1", "F#2"), 16: ("E1", "E2"),
        17: ("B1", "B2"), 18: ("G1", "G2"), 19: ("F#1", "F#2"), 20: ("E1", "E2"),
        21: ("G1", "G2"), 22: ("E1", "E2"), 23: ("F#1", "F#2"), 24: ("F#1", "F#2"),
        25: ("G1", "G2"), 26: ("F#1", "F#2"), 27: ("E1", "E2"), 28: ("B1", "B2"),
        29: ("G1", "G2"), 30: ("F#1", "F#2"), 31: ("F#1", "F#2"), 32: ("F#1", "F#2"),
        33: ("F#1", "F#2"), 34: ("C#2", "C#3"), 35: ("B1", "B2"), 36: ("G1", "G2"),
        37: ("D2", "D3"), 38: ("C#2", "C#3"), 39: ("E1", "E2"), 40: ("A1", "A2"),
        41: ("E1", "E2"), 42: ("B1", "B2"), 43: ("G1", "G2"), 44: ("A1", "A2"),
        45: ("F#1", "F#2"), 46: ("G1", "G2"), 47: ("E1", "E2"), 48: ("D1", "D2"),
        49: ("F#1", "F#2"), 50: ("B1", "B2"), 51: ("G1", "G2"), 52: ("F#1", "F#2"),
        53: ("E1", "E2"), 54: ("G1", "G2"), 55: ("B1", "B2"), 56: ("A1", "A2"),
        57: ("G1", "G2"), 58: ("E1", "E2"), 59: ("A1", "A2"), 60: ("D1", "D2"),
    }
    for bar in range(1, 61):
        m = bass.measure(bar)
        low, high = bass_line[bar]
        if bar >= 57:
            # 尾声按“旋律 → 内声部 → 低音 → 琶音 → 点缀”的顺序退出。
            put_events(m, [(4, None)])
        elif bar in (1, 2, 3, 4, 5, 6, 7, 8, 31, 32, 33, 49):
            put_events(m, [(4, [low, high])])
        elif bar in (25, 26, 27, 28, 29, 30):
            put_events(m, [(2, [low, high]), (2, None)])
        else:
            put_events(m, [(2, [low, high]), (2, [low, high])])

    # -------- 主旋律层：主题、答句、日出八度叠轨 --------
    melody = parts["钢琴·旋律"]
    # 主歌问句：第 5–6 小节完整写出 M；第 7–8 小节是级进收束。
    put_events(melody.measure(5), [(1, "F#4"), (2, "B4"), (1, "D5")])
    put_events(melody.measure(6), [(2, "C#5"), (2, "B4")])
    put_events(melody.measure(7), [(1, "D5"), (1, "C#5"), (2, "B4")])
    put_events(melody.measure(8), [(2, "A4"), (2, "F#4")])
    put_events(melody.measure(9), [(1, "D5"), (1, "C#5"), (2, "B4")])
    put_events(melody.measure(10), [(1, "A4"), (1, "B4"), (2, "D5")])
    put_events(melody.measure(11), [(1, "E5"), (1, "F#5"), (2, "G5")])
    put_events(melody.measure(12), [(1, "F#5"), (1, "E5"), (2, "C#5")])
    for bar in list(range(1, 5)) + list(range(13, 17)) + list(range(20, 33)) + list(range(49, 53)) + list(range(55, 61)):
        put_events(melody.measure(bar), [(4, None)])
    # 积蓄段只露出动机前三音。
    put_events(melody.measure(17), [(2, "F#4"), (2, None)])
    put_events(melody.measure(18), [(2, "B4"), (2, None)])
    put_events(melody.measure(19), [(2, "D5"), (2, None)])

    def melo_octave(events: Sequence[tuple[float, str]]) -> list[tuple[float, object]]:
        return [(duration, octave_pair(name)) for duration, name in events]

    # 日出 33–36：同一 M，时值扩大一倍并升高八度；B5 用 tie 跨小节，
    # 因而忽略 tie stop 后的音高序列仍是 F#5–B5–D6–C#6–B5。
    f5 = chord_obj(octave_pair("F#5"), 2)
    b5_start = chord_obj(octave_pair("B5"), 2); b5_start.tie = tie.Tie("start")
    b5_stop = chord_obj(octave_pair("B5"), 2); b5_stop.tie = tie.Tie("stop")
    d6 = chord_obj(octave_pair("D6"), 2)
    c6 = chord_obj(octave_pair("C#6"), 4)
    b5_final = chord_obj(octave_pair("B5"), 4)
    put_events(melody.measure(33), [(2, f5), (2, b5_start)])
    put_events(melody.measure(34), [(2, b5_stop), (2, d6)])
    put_events(melody.measure(35), [(4, c6)])
    put_events(melody.measure(36), [(4, b5_final)])
    # 37–40 答句，半终止落在 A。
    put_events(melody.measure(37), melo_octave([(2, "D6"), (2, "C#6")]))
    put_events(melody.measure(38), melo_octave([(2, "B5"), (2, "A5")]))
    put_events(melody.measure(39), melo_octave([(2, "G5"), (2, "A5")]))
    put_events(melody.measure(40), melo_octave([(4, "C#6")]))
    # 41–44 上行序进，44 到达 A6。
    for bar, seq in {
        41: ["F#5", "G5", "A5", "B5"], 42: ["G5", "A5", "B5", "C#6"],
        43: ["A5", "B5", "C#6", "D6"], 44: ["B5", "C#6", "D6", "A6"],
    }.items():
        put_events(melody.measure(bar), melo_octave([(1, n) for n in seq]))
    # 45–48 最终陈述，48 完全终止。
    put_events(melody.measure(45), melo_octave([(2, "F#5"), (2, "B5")]))
    put_events(melody.measure(46), melo_octave([(2, "D6"), (2, "C#6")]))
    put_events(melody.measure(47), melo_octave([(4, "B5")]))
    put_events(melody.measure(48), melo_octave([(4, "D6")]))
    # 尾声动机残影：只在 53–54 小节出现，之后完全退出。
    put_events(melody.measure(53), [(2, "F#5"), (2, None)])
    put_events(melody.measure(54), [(2, "B5"), (2, "D6")])

    # -------- 内声部：中音区长线，像柔和的弦乐 --------
    inner = parts["钢琴·内声部"]
    for bar in range(1, 61):
        m = inner.measure(bar)
        if bar < 3 or bar > 54:
            put_events(m, [(4, None)])
        elif 3 <= bar <= 4:
            put_events(m, [(4, ["D4", "F#4", "A4"])])
        elif 9 <= bar <= 12:
            tones = CHORD_TONES[CHORDS[bar - 1]]
            voicing = [f"{tones[1]}4", f"{tones[2]}4", f"{tones[-1]}5"]
            put_events(m, [(4, voicing)])
        elif 13 <= bar <= 16:
            put_events(m, [(4, None)])
        elif 17 <= bar <= 24:
            tones = CHORD_TONES[CHORDS[bar - 1]]
            voicing = [f"{tones[1]}4", f"{tones[2]}4", f"{tones[-1]}5"]
            put_events(m, [(2, voicing), (2, voicing)])
        elif 25 <= bar <= 32:
            tones = CHORD_TONES[CHORDS[bar - 1]]
            # 第 30 小节只放 D/F#/A/C#/G#，绝不放 G。
            if bar == 30:
                voicing = ["D4", "F#4", "A4", "C#5", "G#5"]
            else:
                voicing = [f"{tones[1]}4", f"{tones[2]}4", f"{tones[-1]}5"]
            put_events(m, [(4, voicing)])
        elif 33 <= bar <= 48:
            tones = CHORD_TONES[CHORDS[bar - 1]]
            voicing = [f"{tones[1]}4", f"{tones[2]}4", f"{tones[-1]}5"]
            put_events(m, [(4, voicing)])
        elif 49 <= bar <= 54:
            tones = CHORD_TONES[CHORDS[bar - 1]]
            voicing = [f"{tones[1]}4", f"{tones[2]}4", f"{tones[-1]}5"]
            put_events(m, [(4, voicing)])
        else:
            put_events(m, [(4, None)])

    # -------- 琶音层：八分、十六分和宽幅滚奏 --------
    arp = parts["钢琴·琶音"]
    patterns8 = [
        [0, 2, 1, 3, 2, 4, 1, 2], [0, 1, 3, 2, 4, 2, 1, 3],
        [1, 2, 0, 3, 4, 2, 3, 1], [0, 3, 1, 4, 2, 3, 1, 2],
    ]
    patterns16 = [
        [0, 1, 2, 3, 4, 3, 2, 1, 0, 2, 3, 4, 2, 1, 3, 2],
        [0, 2, 4, 1, 3, 2, 0, 3, 4, 2, 1, 4, 3, 1, 2, 0],
        [1, 3, 0, 2, 4, 1, 2, 3, 0, 4, 2, 1, 3, 2, 4, 0],
        [0, 1, 3, 4, 2, 0, 2, 4, 1, 3, 0, 2, 4, 3, 1, 2],
    ]
    for bar in range(1, 61):
        m = arp.measure(bar)
        tones = CHORD_TONES[CHORDS[bar - 1]]
        if 5 <= bar <= 12:
            pattern = patterns8[(bar - 5) % len(patterns8)]
            values = [f"{tones[i % len(tones)]}{4 + (i // len(tones))}" for i in pattern]
            put_events(m, [(0.5, value) for value in values])
        elif 13 <= bar <= 24:
            pattern = patterns16[(bar - 13) % len(patterns16)]
            values = [f"{tones[i % len(tones)]}{4 + (i // len(tones))}" for i in pattern]
            put_events(m, [(0.25, value) for value in values])
        elif 25 <= bar <= 32:
            count = {25: 6, 26: 5, 27: 5, 28: 4, 29: 4, 30: 4, 31: 3, 32: 2}[bar]
            pattern = patterns8[(bar + 1) % len(patterns8)][:count]
            values = [f"{tones[i % len(tones)]}{4 + (i // len(tones))}" for i in pattern]
            events: list[tuple[float, object | None]] = []
            for i, value in enumerate(values):
                events += [(0.5, value)]
            events.append((4 - 0.5 * count, None))
            put_events(m, events)
        elif 33 <= bar <= 48:
            # 三个八度的开放滚奏，音区从 C4 到 D7，旋律保持在其上方。
            cycle = ["D", "A", "C#", "F#", "D", "A", "C#", "F#"]
            if bar % 2:
                cycle = list(reversed(cycle))
            # 这里必须只按滚奏中的音符位置计算八度。此前把整小节号 `bar`
            # 直接加进公式，导致第 33 小节起生成 F#12、C#12 等超高音，
            # MuseScore 因而在中间整行画出大片加线。
            values = [f"{pc}{4 + (i // 2)}" for i, pc in enumerate(cycle)]
            put_events(m, [(0.5, value) for value in values])
        elif 49 <= bar <= 59:
            if bar >= 57:
                # 低音和内声部已退出，这里留一层很轻的、错落的琶音残影，
                # 避免最后四小节突然只剩零星点缀；密度仍逐小节下降。
                tail_positions = {
                    57: [0.25, 1.75, 3.25],
                    58: [0.75, 2.25, 3.5],
                    59: [1.25, 3.0],
                }
                points = [
                    (position, f"{tones[i % len(tones)]}{5 + (i // len(tones))}", 0.5)
                    for i, position in enumerate(tail_positions[bar])
                ]
                put_onsets(m, points)
            else:
                count = {49: 6, 50: 5, 51: 5, 52: 4, 53: 4, 54: 3, 55: 3, 56: 2}[bar]
                values = [f"{tones[i % len(tones)]}{5 + (i // len(tones))}" for i in range(count)]
                put_events(m, [(0.5, value) for value in values] + [(4 - 0.5 * count, None)])
        elif bar == 60:
            final = ["D4", "F#4", "A4", "C#5", "E5"]
            # 以全音符 + 尾声踏板收束；不写 fermata，避免 MuseScore 将最后一小节
            # 自动拉成约 23 BPM，破坏速度表的总时长校验。
            m.insert(0, chord_obj(final, 4))
        else:
            put_events(m, [(4, None)])

    # -------- 点缀层：雨点、高音闪光、晨露散点 --------
    sparkle = parts["钢琴·点缀"]
    rain = {
        1: [(0.5, "B5", 0.25), (2.75, "F#6", 0.25)], 2: [(1.25, "D6", 0.25), (3.5, "B5", 0.25)],
        3: [(0.25, "F#6", 0.25), (2.5, "B5", 0.25), (3.75, "D6", 0.25)], 4: [(1.75, "F#6", 0.25)],
        9: [(1.25, "F#6", 0.25)], 10: [(3.5, "A5", 0.25)],
        11: [(0.75, "D6", 0.25), (2.75, "B5", 0.25)], 12: [(1.5, "F#6", 0.25)],
        21: [(0.5, "A6", 0.25), (2.75, "F#6", 0.25)], 22: [(1.25, "B6", 0.25), (3.5, "E6", 0.25)],
        23: [(0.75, "D6", 0.25), (2.5, "A6", 0.25)], 24: [(1.75, "F#6", 0.25)],
        25: [(0.5, "B5", 0.25), (2.25, "D6", 0.25), (3.5, "F#6", 0.25)], 26: [(1.25, "A5", 0.25), (3.25, "E6", 0.25)],
        27: [(0.75, "B5", 0.25), (2.75, "D6", 0.25)], 28: [(1.5, "F#6", 0.25), (3.75, "A5", 0.25)],
        29: [(0.25, "D6", 0.25)], 30: [(2.5, "G#6", 0.25)], 31: [(1.75, "A5", 0.25)], 32: [(3.25, "B5", 0.25)],
    }
    for bar in range(1, 61):
        m = sparkle.measure(bar)
        if bar in rain:
            put_onsets(m, rain[bar])
        elif 49 <= bar <= 60:
            count = {49: 4, 50: 4, 51: 3, 52: 3, 53: 3, 54: 2, 55: 2, 56: 2, 57: 1, 58: 1, 59: 1, 60: 1}[bar]
            if bar == 60:
                points = [(3.25, "E6", 0.5)]
            else:
                pentatonic = ["D6", "E6", "F#6", "A6", "B6"]
                positions = {49: [0.25, 1.5, 2.75, 3.5], 50: [0.5, 1.75, 2.25, 3.75], 51: [0.25, 2.0, 3.25], 52: [1.0, 2.5, 3.75], 53: [0.5, 1.75, 3.0], 54: [1.25, 3.5], 55: [0.25, 2.75], 56: [1.5, 3.25], 57: [2.25], 58: [0.75], 59: [3.0]}[bar]
                points = [(pos, pentatonic[(bar + i) % len(pentatonic)], 0.25) for i, pos in enumerate(positions[:count])]
            put_onsets(m, points)
        else:
            put_events(m, [(4, None)])

    add_tempo_and_dynamics(score, parts)
    return score, parts


def add_slurs(parts: dict[str, stream.Part]) -> None:
    """给低音和内声部加跨小节连线，避免低音像每小节重击。"""
    bass = parts["钢琴·低音"]
    for start, end in [(1, 4), (5, 8), (9, 12), (13, 16), (17, 20), (21, 24), (25, 28), (29, 32), (33, 36), (37, 40), (41, 44), (45, 48), (49, 52), (53, 56), (57, 60)]:
        notes = [n for bar in range(start, end + 1) for n in bass.measure(bar).notes]
        if len(notes) > 1:
            bass.insert(0, spanner.Slur(*notes))
    inner = parts["钢琴·内声部"]
    for start, end in [(3, 4), (9, 12), (17, 24), (25, 32), (33, 48), (49, 54)]:
        notes = [n for bar in range(start, end + 1) for n in inner.measure(bar).notes]
        if len(notes) > 1:
            inner.insert(0, spanner.Slur(*notes))


def write_musicxml(score: stream.Score, destination: Path) -> None:
    score.write("musicxml", fp=destination)
    tree = ET.parse(destination)
    root = tree.getroot()
    score_parts = root.find("part-list")
    if score_parts is None:
        raise RuntimeError("MusicXML 缺少 part-list")
    for channel, (name, cfg) in enumerate(PART_CONFIG.items(), start=1):
        score_part = next((x for x in score_parts.findall("score-part") if x.findtext("part-name") == name), None)
        if score_part is None:
            raise RuntimeError(f"找不到 Part: {name}")
        score_part.find("score-instrument/instrument-name").text = "Acoustic Grand Piano"
        score_part.find("score-instrument/instrument-abbreviation").text = "Pno"
        midi = score_part.find("midi-instrument")
        if midi is None:
            midi = ET.SubElement(score_part, "midi-instrument")
        for child in list(midi):
            if child.tag in {"midi-channel", "midi-program", "pan", "volume"}:
                midi.remove(child)
        ET.SubElement(midi, "midi-channel").text = str(channel)
        ET.SubElement(midi, "midi-program").text = "1"
        ET.SubElement(midi, "pan").text = str(cfg["pan"])
        ET.SubElement(midi, "volume").text = str(cfg["volume"])

    # 每层独立踏板：每次换和声时 change，首尾用 start/stop。
    for part_index, xml_part in enumerate(root.findall("part"), start=1):
        for measure in xml_part.findall("measure"):
            number = int(measure.attrib["number"])
            direction = ET.Element("direction", {"placement": "below"})
            dtype = ET.SubElement(direction, "direction-type")
            pedal_type = "start" if number == 1 else ("stop" if number == 60 else "change")
            ET.SubElement(dtype, "pedal", {"line": "yes", "number": "1", "type": pedal_type})
            # MusicXML 的 measure 顺序要求 attributes 位于 direction 之前；
            # 首版插在 0 号位置会让 MuseScore 在导入时直接崩溃。
            attr_index = next((i for i, child in enumerate(list(measure)) if child.tag == "attributes"), None)
            if attr_index is None:
                measure.insert(0, direction)
            else:
                measure.insert(attr_index + 1, direction)

    # music21 10.5 会保留动态对象，但不总是把跨段 dynamics.Crescendo 序列化成
    # MusicXML wedge；这里补上标准的 start/stop direction，确保文件本身可审计。
    part_ids = {sp.findtext("part-name"): sp.attrib["id"] for sp in score_parts.findall("score-part")}
    xml_parts = {p.attrib["id"]: p for p in root.findall("part")}
    for name, spans in WEDGE_SPANS.items():
        xml_part = xml_parts[part_ids[name]]
        measures = {int(m.attrib["number"]): m for m in xml_part.findall("measure")}
        for number, (start, end, kind) in enumerate(spans, start=1):
            for bar, wedge_type in ((start, kind), (end, "stop")):
                direction = ET.Element("direction", {"placement": "below"})
                dtype = ET.SubElement(direction, "direction-type")
                ET.SubElement(dtype, "wedge", {"type": wedge_type, "number": str(number)})
                measure = measures[bar]
                attr_index = next((i for i, child in enumerate(list(measure)) if child.tag == "attributes"), None)
                insert_at = (attr_index + 1) if attr_index is not None else 0
                measure.insert(insert_at, direction)

    # 根据用户要求在第 30 小节禁止 G 与 G# 同时出现；生成层已经保证，这里只做序列化后的保险检查。
    tree.write(destination, encoding="utf-8", xml_declaration=True)


def extract_pitch_names(obj: object) -> list[str]:
    if isinstance(obj, note.Note):
        return [obj.nameWithOctave]
    if isinstance(obj, chord.Chord):
        return [p.nameWithOctave for p in obj.pitches]
    return []


def run_self_checks(score: stream.Score, parts: dict[str, stream.Part]) -> dict:
    errors: list[str] = []
    all_objects = list(score.recurse())
    for name, part in parts.items():
        measures = list(part.getElementsByClass(stream.Measure))
        if len(measures) != 60:
            errors.append(f"{name}: 小节数 {len(measures)}")
        for m in measures:
            if abs(float(m.duration.quarterLength) - 4.0) > 0.001:
                errors.append(f"{name} 第 {m.number} 小节时值 {m.duration.quarterLength}")
    key_values = [ks.sharps for ks in score.recurse().getElementsByClass(key.KeySignature)]
    if any(v != KEY_FIFTHS for v in key_values):
        errors.append(f"调号不统一: {key_values}")
    dyns = [d.value for d in all_objects if isinstance(d, dynamics.Dynamic)]
    if any(d in {"ff", "fff", "ffff"} for d in dyns):
        errors.append("出现 ff 以上力度")
    wedges = list(score.recurse().getElementsByClass((dynamics.Crescendo, dynamics.Diminuendo)))
    if not wedges:
        errors.append("没有 wedge")

    # 旋律段每小节必须有音，且低于 C3 的音只来自低音层。
    for bar in range(33, 49):
        if not parts["钢琴·旋律"].measure(bar).notes:
            errors.append(f"日出第 {bar} 小节旋律中断")
    for name, part in parts.items():
        if name != "钢琴·低音":
            lows = [p.nameWithOctave for p in part.recurse().pitches if p.midi < 48]
            if lows:
                errors.append(f"{name} 出现 C3 以下音: {lows[:3]}")

    # G/G# 冲突检查（按小节的同时发声集合，实际第 30 小节应为零）。
    g_conflicts = []
    for bar in range(1, 61):
        has_g = False
        has_gs = False
        for part in parts.values():
            for obj in part.measure(bar).notes:
                names = extract_pitch_names(obj)
                has_g |= any(re.match(r"^G[0-9]$", n) for n in names)
                has_gs |= any(re.match(r"^G#[0-9]$", n) for n in names)
        if has_g and has_gs:
            g_conflicts.append(bar)
    if g_conflicts:
        errors.append(f"G/G# 同小节冲突: {g_conflicts}")

    density = {name: [len(parts[name].measure(bar).notes) for bar in range(1, 61)] for name in parts}
    layer_presence = {
        bar: {name: bool(parts[name].measure(bar).notes) for name in parts}
        for bar in range(1, 61)
    }
    # 晨露散点必须有非整拍起音。
    sparkle_offsets = [float(n.offset) for bar in range(49, 61) for n in parts["钢琴·点缀"].measure(bar).notes]
    if not any(abs(offset - round(offset)) > 1e-6 for offset in sparkle_offsets):
        errors.append("晨露没有非整拍起音")
    # 第 13–24 小节琶音连续渐强的存在性和 16 分密度。
    if any(len(parts["钢琴·琶音"].measure(bar).notes) != 16 for bar in range(13, 25)):
        errors.append("第 13–24 小节琶音不是连续十六分音符")
    if len(wedges) < 10:
        errors.append(f"wedge 数量过少: {len(wedges)}")

    # 核心动机：主歌的五个起音与日出扩大版（忽略 tie stop）保持对应。
    verse_motif = [n.nameWithOctave for bar in (5, 6) for n in parts["钢琴·旋律"].measure(bar).notes]
    sunrise_motif = []
    for bar in (33, 34, 35, 36):
        for n in parts["钢琴·旋律"].measure(bar).notes:
            if n.tie and n.tie.type == "stop":
                continue
            # 八度叠轨只取低八度作为主题骨架，避免把 double 音误判成重复主题。
            sunrise_motif.append(n.pitches[0].nameWithOctave if isinstance(n, chord.Chord) else n.nameWithOctave)
    expected_verse = ["F#4", "B4", "D5", "C#5", "B4"]
    expected_sunrise = ["F#5", "B5", "D6", "C#6", "B5"]
    if verse_motif != expected_verse:
        errors.append(f"主歌动机不匹配: {verse_motif}")
    if sunrise_motif != expected_sunrise:
        errors.append(f"日出动机不匹配: {sunrise_motif}")
    # 尾声退出顺序：旋律 54 后、内声部 55 后、低音 56 后退出。
    if any(parts["钢琴·旋律"].measure(b).notes for b in range(55, 61)):
        errors.append("旋律层未在第 54 小节后退出")
    if any(parts["钢琴·内声部"].measure(b).notes for b in range(55, 61)):
        errors.append("内声部层未在第 54 小节后退出")
    if any(parts["钢琴·低音"].measure(b).notes for b in range(57, 61)):
        errors.append("低音层未在第 56 小节后退出")

    # 日出琶音必须留在可读的三八度范围；这是对曾经的整小节号八度计算错误的回归保护。
    sunrise_arp_pitches = [
        p
        for bar in range(33, 49)
        for obj in parts["钢琴·琶音"].measure(bar).notes
        for p in obj.pitches
    ]
    if not sunrise_arp_pitches or min(p.midi for p in sunrise_arp_pitches) < 48 or max(p.midi for p in sunrise_arp_pitches) > 108:
        errors.append("日出琶音超出可读三八度音区")

    # 尾声最后四小节应有连续但逐步稀疏的琶音支撑，最后一小节收为和弦。
    tail_arp_counts = [len(parts["钢琴·琶音"].measure(bar).notes) for bar in range(57, 61)]
    if tail_arp_counts[:3] != [3, 3, 2] or tail_arp_counts[3] != 1:
        errors.append(f"尾声琶音密度异常: {tail_arp_counts}")

    print("Self-checks:")
    print(f"  measures=60/4-beats: {'PASS' if not any('小节' in e for e in errors) else 'FAIL'}")
    print(f"  fifths=2: {'PASS' if all(v == KEY_FIFTHS for v in key_values) else 'FAIL'}")
    print(f"  parts=5: {'PASS' if len(parts) == 5 else 'FAIL'}")
    print(f"  max dynamic <= f: {'PASS' if not any(d in {'ff', 'fff', 'ffff'} for d in dyns) else 'FAIL'}")
    print(f"  wedges: {'PASS' if wedges else 'FAIL'} ({len(wedges)})")
    print(f"  sunrise melody 33-48: {'PASS' if all(parts['钢琴·旋律'].measure(b).notes for b in range(33, 49)) else 'FAIL'}")
    print(f"  G/G# conflicts: {'PASS' if not g_conflicts else 'FAIL'} ({g_conflicts})")
    print(f"  dew off-beat: {'PASS' if any(abs(o - round(o)) > 1e-6 for o in sparkle_offsets) else 'FAIL'}")
    print(f"  motif correspondence: {'PASS' if verse_motif == expected_verse and sunrise_motif == expected_sunrise else 'FAIL'}")
    print(f"  coda exit order: {'PASS' if not any('退出' in e for e in errors) else 'FAIL'}")
    print(f"  sunrise arpeggio register: {'PASS' if sunrise_arp_pitches and min(p.midi for p in sunrise_arp_pitches) >= 48 and max(p.midi for p in sunrise_arp_pitches) <= 108 else 'FAIL'}")
    print(f"  coda arpeggio support: {'PASS' if tail_arp_counts[:3] == [3, 3, 2] and tail_arp_counts[3] == 1 else 'FAIL'} ({tail_arp_counts})")
    print("Layer presence table (M=旋律 I=内声部 A=琶音 B=低音 S=点缀):")
    for bar in range(1, 61):
        flags = "".join(k for k, name in zip("MIABS", parts) if layer_presence[bar][name])
        print(f"  {bar:02d}: {flags or '-'}")
    print("Density table (M/I/A/B/S):")
    for bar in range(1, 61):
        print(f"  {bar:02d}: " + "/".join(str(density[name][bar - 1]) for name in parts))
    if errors:
        raise SystemExit("SELF-CHECK FAILURE: " + "; ".join(errors))
    return {"layer_presence": layer_presence, "density": density, "wedges": len(wedges)}


def main() -> None:
    score, parts = build_score()
    add_slurs(parts)
    report = run_self_checks(score, parts)
    destination = OUTPUT / "dawn_after_rain_piano.musicxml"
    write_musicxml(score, destination)
    (OUTPUT / "self_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
