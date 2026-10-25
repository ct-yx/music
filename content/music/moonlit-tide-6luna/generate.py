#!/usr/bin/env python3
"""从零生成《月下潮汐6Luna》的五乐器原创总谱。"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Sequence

from music21 import chord, clef, dynamics, duration, expressions, instrument, key, metadata, meter, note, stream, tempo


OUTPUT = Path(__file__).resolve().parent
TITLE = "月下潮汐6Luna"
SUBTITLE = "Moonlit Tide"
COMPOSER = "Codex + MuseScore"
KEY_FIFTHS = -3  # E-flat major / c minor
TIME_SIGNATURE = "6/8"
BARS = 40
DOTTED_QUARTER_BPM = 52

PART_CONFIG = {
    "钢琴": {"id": "piano", "instrument": instrument.Piano, "xml_name": "Acoustic Grand Piano", "abbr": "Pno.", "program": 1, "pan": 0, "volume": 80, "clef": clef.TrebleClef},
    "竖琴": {"id": "harp", "instrument": instrument.Harp, "xml_name": "Orchestral Harp", "abbr": "Hrp.", "program": 47, "pan": -22, "volume": 67, "clef": clef.TrebleClef},
    "大提琴": {"id": "cello", "instrument": instrument.Violoncello, "xml_name": "Violoncello", "abbr": "Vc.", "program": 43, "pan": -8, "volume": 78, "clef": clef.BassClef},
    "长笛": {"id": "flute", "instrument": instrument.Flute, "xml_name": "Flute", "abbr": "Fl.", "program": 74, "pan": 18, "volume": 70, "clef": clef.TrebleClef},
    "钢片琴": {"id": "celesta", "instrument": instrument.Celesta, "xml_name": "Celesta", "abbr": "Cel.", "program": 9, "pan": 30, "volume": 55, "clef": clef.TrebleClef},
}

# 原创六拍动机：月潮的上行与回落。
MOTIF = ["G4", "B-4", "C5", "D5", "C5", "B-4"]
MOTIF_HIGH = ["G5", "B-5", "C6", "D6", "C6", "B-5"]

CHORD_TONES = {
    "Cm9": ["C", "Eb", "G", "Bb", "D"],
    "Abmaj7": ["Ab", "C", "Eb", "G"],
    "Eb/G": ["G", "Bb", "Eb", "F"],
    "Bbadd4": ["Bb", "D", "Eb", "F"],
    "Fm7": ["F", "Ab", "C", "Eb"],
    "G7sus4": ["G", "C", "D", "F"],
    "Ebmaj7": ["Eb", "G", "Bb", "D"],
    "Bb/D": ["D", "F", "Bb", "C"],
    "Cm7": ["C", "Eb", "G", "Bb"],
    "G7": ["G", "B", "D", "F"],
    "Fm9": ["F", "Ab", "C", "Eb", "G"],
    "Bb7": ["Bb", "D", "F", "Ab"],
    "Gm7": ["G", "Bb", "D", "F"],
    "Eb/Bb": ["Bb", "Eb", "G", "D"],
    "Bb7sus4": ["Bb", "Eb", "F", "Ab"],
    "Eb6/9": ["Eb", "G", "Bb", "C", "F"],
}
CHORDS = [
    "Cm9", "Abmaj7", "Eb/G", "Bbadd4", "Cm9", "Abmaj7", "Fm7", "G7sus4",
    "Ebmaj7", "Bb/D", "Cm7", "Abmaj7", "Fm7", "G7", "Cm9", "Bbadd4",
    "Ebmaj7", "Bb/D", "Cm7", "Abmaj7", "Fm9", "G7", "Abmaj7", "Bb7",
    "Ebmaj7", "Gm7", "Cm7", "Fm7", "Abmaj7", "Eb/G", "Fm7", "G7sus4",
    "Cm9", "Abmaj7", "Eb/Bb", "Bb7", "Ebmaj7", "Abmaj7", "Bb7sus4", "Eb6/9",
]
BASS_ROOT = {
    "Cm9": "C", "Abmaj7": "Ab", "Eb/G": "G", "Bbadd4": "Bb", "Fm7": "F", "G7sus4": "G",
    "Ebmaj7": "Eb", "Bb/D": "D", "Cm7": "C", "G7": "G", "Fm9": "F", "Bb7": "Bb",
    "Gm7": "G", "Eb/Bb": "Bb", "Bb7sus4": "Bb", "Eb6/9": "Eb",
}
LOWER_FIFTH = {"C": "G", "Ab": "Eb", "G": "D", "Bb": "F", "F": "C", "Eb": "Bb", "D": "A"}

DYNAMICS = {
    "钢琴": {1: "pp", 9: "p", 17: "mp", 21: "f", 25: "mf", 29: "mp", 37: "pp"},
    "竖琴": {9: "p", 17: "mp", 21: "f", 25: "mf", 29: "mp", 37: "p"},
    "大提琴": {1: "pp", 9: "p", 17: "mf", 21: "f", 25: "mf", 29: "mp", 37: "p"},
    "长笛": {9: "p", 17: "mf", 21: "f", 25: "mf", 29: "mp"},
    "钢片琴": {17: "pp", 21: "f", 25: "mf", 29: "p"},
}

WEDGE_SPANS = {
    "钢琴": [(1, 8, "crescendo"), (9, 20, "crescendo"), (21, 24, "crescendo"), (25, 28, "diminuendo"), (29, 36, "diminuendo"), (37, 40, "diminuendo")],
    "竖琴": [(9, 16, "crescendo"), (17, 24, "crescendo"), (25, 28, "diminuendo"), (29, 36, "diminuendo"), (37, 40, "diminuendo")],
    "大提琴": [(1, 8, "crescendo"), (9, 20, "crescendo"), (21, 24, "crescendo"), (25, 28, "diminuendo"), (29, 36, "diminuendo"), (37, 38, "diminuendo")],
    "长笛": [(9, 16, "crescendo"), (17, 24, "crescendo"), (25, 30, "diminuendo")],
    "钢片琴": [(17, 24, "crescendo"), (25, 32, "diminuendo")],
}


def pitch(name: str, length: float) -> note.Note:
    return note.Note(name, quarterLength=length)


def chord_obj(names: Sequence[str], length: float) -> chord.Chord:
    return chord.Chord(list(names), quarterLength=length)


def put_events(measure: stream.Measure, events: Sequence[tuple[float, object | None]]) -> None:
    """按顺序放入音符、和弦或休止，并将不足一小节的部分补休止。"""
    cursor = 0.0
    for length, value in events:
        if isinstance(value, str):
            obj = pitch(value, length)
        elif isinstance(value, (list, tuple)):
            obj = chord_obj(value, length)
        elif value is None:
            obj = note.Rest(quarterLength=length)
        else:
            obj = value
        measure.insert(cursor, obj)
        cursor += length
    if cursor < 3.0:
        measure.insert(cursor, note.Rest(quarterLength=3.0 - cursor))
    if cursor > 3.0001:
        raise ValueError(f"第 {measure.number} 小节超过 6/8 时值: {cursor}")


def put_onsets(measure: stream.Measure, onsets: Sequence[tuple[float, str, float]]) -> None:
    events: list[tuple[float, object | None]] = []
    cursor = 0.0
    for onset, name, length in sorted(onsets):
        if onset < cursor or onset + length > 3.0001:
            raise ValueError(f"第 {measure.number} 小节音符重叠或越界: {onsets}")
        if onset > cursor:
            events.append((onset - cursor, None))
        events.append((length, name))
        cursor = onset + length
    if cursor < 3.0:
        events.append((3.0 - cursor, None))
    put_events(measure, events)


def make_part(name: str, cfg: dict) -> stream.Part:
    part = stream.Part(id=cfg["id"])
    part.partName = name
    inst = cfg["instrument"]()
    inst.instrumentName = cfg["xml_name"]
    inst.instrumentAbbreviation = cfg["abbr"]
    inst.midiProgram = cfg["program"] - 1
    part.insert(0, inst)
    part.insert(0, cfg["clef"]())
    return part


def add_measure_skeleton(part: stream.Part, number: int) -> stream.Measure:
    measure = stream.Measure(number=number)
    if number == 1:
        measure.insert(0, key.KeySignature(KEY_FIFTHS))
        measure.insert(0, meter.TimeSignature(TIME_SIGNATURE))
    part.append(measure)
    return measure


def arpeggio_values(chord_name: str, pattern: Sequence[int], base_octave: int) -> list[str]:
    tones = CHORD_TONES[chord_name]
    return [f"{tones[index % len(tones)]}{base_octave + index // len(tones)}" for index in pattern]


def add_piano(parts: dict[str, stream.Part]) -> None:
    piano = parts["钢琴"]
    patterns8 = [
        [0, 2, 1, 3, 2, 4],
        [0, 1, 3, 2, 4, 2],
        [1, 2, 0, 3, 4, 1],
        [0, 3, 2, 4, 1, 2],
    ]
    patterns16 = [
        [0, 1, 2, 3, 4, 3, 2, 1, 0, 2, 3, 4],
        [0, 2, 4, 1, 3, 2, 0, 3, 4, 2, 1, 3],
        [1, 3, 0, 2, 4, 1, 2, 3, 0, 4, 2, 1],
        [0, 1, 3, 4, 2, 0, 2, 4, 1, 3, 0, 2],
    ]
    for bar in range(1, BARS + 1):
        measure = piano.measure(bar)
        chord_name = CHORDS[bar - 1]
        if bar == 1:
            put_events(measure, [(0.5, value) for value in MOTIF])
        elif bar == 2:
            put_events(measure, [(0.5, value) for value in ["G4", "F4", "G4", "Bb4", "C5", "Bb4"]])
        elif bar == 3:
            put_events(measure, [(0.5, value) for value in ["G4", "Bb4", "C5", "D5", "Eb5", "D5"]])
        elif bar == 4:
            put_events(measure, [(0.5, value) for value in ["C5", "Bb4", "G4", "F4", "Eb4", "D4"]])
        elif 5 <= bar <= 8:
            pattern = ["G4", "Bb4", "C5", "D5", "C5", "G4"] if bar % 2 else ["F4", "G4", "Bb4", "C5", "Bb4", "G4"]
            put_events(measure, [(0.5, value) for value in pattern])
        elif 9 <= bar <= 16:
            values = arpeggio_values(chord_name, patterns8[(bar - 9) % len(patterns8)], 3)
            put_events(measure, [(0.5, value) for value in values])
        elif 17 <= bar <= 28:
            values = arpeggio_values(chord_name, patterns16[(bar - 17) % len(patterns16)], 3)
            put_events(measure, [(0.25, value) for value in values])
        elif 29 <= bar <= 36:
            count = {29: 6, 30: 5, 31: 5, 32: 4, 33: 4, 34: 3, 35: 3, 36: 2}[bar]
            values = arpeggio_values(chord_name, patterns8[(bar - 29) % len(patterns8)][:count], 3)
            put_events(measure, [(0.5, value) for value in values])
        else:
            final_voicing = {
                37: ["Eb3", "G3", "Bb3", "D4"],
                38: ["Ab3", "C4", "Eb4", "G4"],
                39: ["Bb3", "Eb4", "F4", "Ab4"],
                40: ["Eb3", "G3", "Bb3", "C4", "F4"],
            }[bar]
            put_events(measure, [(3.0, final_voicing)])


def add_harp(parts: dict[str, stream.Part]) -> None:
    harp = parts["竖琴"]
    patterns8 = [[0, 1, 2, 3, 2, 1], [0, 2, 1, 3, 1, 2], [1, 2, 3, 0, 2, 1], [0, 3, 2, 1, 3, 2]]
    patterns16 = [[0, 1, 2, 3, 2, 1, 0, 2, 3, 2, 1, 3], [0, 2, 3, 1, 2, 0, 3, 2, 1, 3, 2, 0]]
    for bar in range(1, BARS + 1):
        measure = harp.measure(bar)
        chord_name = CHORDS[bar - 1]
        if 9 <= bar <= 16:
            values = arpeggio_values(chord_name, patterns8[(bar - 9) % len(patterns8)], 4)
            put_events(measure, [(0.5, value) for value in values])
        elif 17 <= bar <= 28:
            values = arpeggio_values(chord_name, patterns16[(bar - 17) % len(patterns16)], 4)
            put_events(measure, [(0.25, value) for value in values])
        elif 29 <= bar <= 36:
            count = {29: 6, 30: 5, 31: 4, 32: 4, 33: 3, 34: 3, 35: 2, 36: 2}[bar]
            values = arpeggio_values(chord_name, patterns8[(bar - 29) % len(patterns8)][:count], 4)
            put_events(measure, [(0.5, value) for value in values])
        elif 37 <= bar <= 39:
            values = arpeggio_values(chord_name, [0, 2, 1], 4)
            put_onsets(measure, [(0.25, values[0], 0.25), (1.5, values[1], 0.25), (2.5, values[2], 0.25)])
        elif bar == 40:
            put_events(measure, [(3.0, ["Eb4", "G4", "Bb4", "C5", "F5"])])
        else:
            put_events(measure, [(3.0, None)])


def add_cello(parts: dict[str, stream.Part]) -> None:
    cello = parts["大提琴"]
    for bar in range(1, BARS + 1):
        measure = cello.measure(bar)
        root = BASS_ROOT[CHORDS[bar - 1]]
        root_pitch = f"{root}2"
        fifth_pitch = f"{LOWER_FIFTH[root]}2"
        if bar <= 16:
            put_events(measure, [(3.0, root_pitch)])
        elif bar <= 28:
            put_events(measure, [(1.5, root_pitch), (1.5, fifth_pitch)])
        elif bar <= 34:
            put_events(measure, [(3.0, root_pitch)])
        elif bar <= 36:
            put_events(measure, [(1.5, root_pitch), (1.5, None)])
        elif bar <= 38:
            put_events(measure, [(3.0, root_pitch)])
        else:
            put_events(measure, [(3.0, None)])


def add_flute(parts: dict[str, stream.Part]) -> None:
    flute = parts["长笛"]
    material = {
        9: MOTIF_HIGH,
        10: ["G5", "F5", "G5", "Bb5", "C6", "Bb5"],
        11: ["C6", "Bb5", "G5", "F5", "G5", "Bb5"],
        12: ["D6", "C6", "Bb5", "G5", "F5", "G5"],
        13: ["Ab5", "Bb5", "C6", "Eb6", "D6", "C6"],
        14: ["Bb5", "C6", "D6", "Eb6", "D6", "Bb5"],
        15: ["G5", "Bb5", "C6", "D6", "C6", "G5"],
        16: ["F5", "G5", "Bb5", "C6", "Bb5", "G5"],
        17: MOTIF_HIGH,
        18: ["G5", "Bb5", "C6", "D6", "Eb6", "D6"],
        19: ["C6", "Bb5", "G5", "F5", "G5", "Bb5"],
        20: ["D6", "C6", "Bb5", "G5", "F5", "G5"],
        21: ["Bb5", "C6", "D6", "Eb6", "F6", "Eb6"],
        22: ["C6", "D6", "Eb6", "F6", "G6", "F6"],
        23: ["D6", "Eb6", "F6", "G6", "F6", "Eb6"],
        24: ["C6", "Bb5", "C6", "D6", "Eb6", "D6"],
        25: ["G5", "Bb5", "C6", "D6", "C6", "Bb5"],
        26: ["F5", "G5", "Bb5", "C6", "Bb5", "G5"],
        27: ["Eb5", "F5", "G5", "Bb5", "G5", "F5"],
        28: ["D5", "F5", "G5", "Bb5", "G5", "F5"],
        29: ["C5", "Eb5", "F5", "G5", "F5", "Eb5"],
        30: ["Bb4", "C5", "Eb5", "F5", "Eb5", "C5"],
    }
    for bar in range(1, BARS + 1):
        values = material.get(bar)
        if values:
            put_events(flute.measure(bar), [(0.5, value) for value in values])
        else:
            put_events(flute.measure(bar), [(3.0, None)])


def add_celesta(parts: dict[str, stream.Part]) -> None:
    celesta = parts["钢片琴"]
    scale = ["Eb6", "F6", "G6", "Bb6", "C7"]
    positions = {
        17: [0.25, 1.25, 2.25], 18: [0.5, 1.75, 2.5], 19: [0.25, 1.5, 2.75], 20: [0.75, 1.75, 2.5],
        21: [0.25, 0.75, 1.5, 2.25], 22: [0.5, 1.25, 2.0, 2.75], 23: [0.25, 1.0, 1.75, 2.5], 24: [0.5, 1.5, 2.25],
        25: [0.25, 1.5, 2.5], 26: [0.75, 1.75, 2.75], 27: [0.5, 2.0], 28: [1.0, 2.5],
        29: [0.5, 2.25], 30: [1.25, 2.5], 31: [0.75], 32: [2.0],
    }
    for bar in range(1, BARS + 1):
        if bar in positions:
            points = [(pos, scale[(bar + idx) % len(scale)], 0.25) for idx, pos in enumerate(positions[bar])]
            put_onsets(celesta.measure(bar), points)
        else:
            put_events(celesta.measure(bar), [(3.0, None)])


def add_tempo_and_dynamics(score: stream.Score, parts: dict[str, stream.Part]) -> None:
    piano = parts["钢琴"]
    piano.measure(1).insert(0, tempo.MetronomeMark(number=DOTTED_QUARTER_BPM, referent=duration.Duration(1.5)))
    piano.measure(1).insert(0, expressions.TextExpression("Moonlit Tide · calm and breathing"))
    for name, marks in DYNAMICS.items():
        for bar, value in marks.items():
            parts[name].measure(bar).insert(0, dynamics.Dynamic(value))


def build_score() -> tuple[stream.Score, dict[str, stream.Part]]:
    score = stream.Score(id="MoonlitTide6Luna")
    score.metadata = metadata.Metadata()
    score.metadata.title = TITLE
    score.metadata.subtitle = SUBTITLE
    score.metadata.composer = COMPOSER
    parts = {name: make_part(name, cfg) for name, cfg in PART_CONFIG.items()}
    for part in parts.values():
        score.insert(0, part)
        for bar in range(1, BARS + 1):
            add_measure_skeleton(part, bar)
    add_piano(parts)
    add_harp(parts)
    add_cello(parts)
    add_flute(parts)
    add_celesta(parts)
    add_tempo_and_dynamics(score, parts)
    return score, parts


def notes_in(measure: stream.Measure) -> list[object]:
    return list(measure.notes)


def pitch_names(measure: stream.Measure) -> list[str]:
    names: list[str] = []
    for obj in notes_in(measure):
        if isinstance(obj, note.Note):
            names.append(obj.nameWithOctave)
        elif isinstance(obj, chord.Chord):
            names.extend(p.nameWithOctave for p in obj.pitches)
    return names


def run_self_checks(score: stream.Score, parts: dict[str, stream.Part]) -> dict:
    errors: list[str] = []
    for name, part in parts.items():
        measures = list(part.getElementsByClass(stream.Measure))
        if len(measures) != BARS:
            errors.append(f"{name}: 小节数为 {len(measures)}")
        for measure in measures:
            if abs(float(measure.duration.quarterLength) - 3.0) > 0.001:
                errors.append(f"{name} 第 {measure.number} 小节时值为 {measure.duration.quarterLength}")
        key_signatures = list(part.recurse().getElementsByClass(key.KeySignature))
        if not key_signatures or any(item.sharps != KEY_FIFTHS for item in key_signatures):
            errors.append(f"{name}: 调号不是降 E 大调/c 小调")
        time_signatures = list(part.recurse().getElementsByClass(meter.TimeSignature))
        if not time_signatures or any(item.ratioString != TIME_SIGNATURE for item in time_signatures):
            errors.append(f"{name}: 拍号不是 6/8")

    instrument_names = []
    for name, part in parts.items():
        insts = list(part.getElementsByClass(instrument.Instrument))
        if not insts:
            errors.append(f"{name}: 缺少乐器声明")
        else:
            instrument_names.append(insts[0].instrumentName)
    if len(set(instrument_names)) != 5:
        errors.append(f"乐器未保持五种独立音色: {instrument_names}")

    dynamics_found = list(score.recurse().getElementsByClass(dynamics.Dynamic))
    forbidden = {"ff", "fff", "ffff", "sfz", "sffz"}
    if any(item.value in forbidden for item in dynamics_found):
        errors.append("出现超过 f 的力度或强奏标记")
    peak_bars = sorted({item.getContextByClass(stream.Measure).number for item in dynamics_found if item.value == "f"})
    if not peak_bars or any(bar < 21 or bar > 24 for bar in peak_bars):
        errors.append(f"高潮力度 f 不在 21–24 小节: {peak_bars}")

    if pitch_names(parts["钢琴"].measure(1)) != MOTIF:
        errors.append(f"钢琴第 1 小节动机不匹配: {pitch_names(parts['钢琴'].measure(1))}")
    if pitch_names(parts["长笛"].measure(17)) != MOTIF_HIGH:
        errors.append(f"长笛第 17 小节动机发展不匹配: {pitch_names(parts['长笛'].measure(17))}")

    expected_presence = {}
    all_names = set(parts)
    for bar in range(1, 9):
        expected_presence[bar] = {"钢琴", "大提琴"}
    for bar in range(9, 17):
        expected_presence[bar] = {"钢琴", "竖琴", "大提琴", "长笛"}
    for bar in range(17, 31):
        expected_presence[bar] = all_names
    for bar in range(31, 33):
        expected_presence[bar] = {"钢琴", "竖琴", "大提琴", "钢片琴"}
    for bar in range(33, 37):
        expected_presence[bar] = {"钢琴", "竖琴", "大提琴"}
    for bar in range(37, 39):
        expected_presence[bar] = {"钢琴", "竖琴", "大提琴"}
    for bar in range(39, 41):
        expected_presence[bar] = {"钢琴", "竖琴"}

    layer_presence = {}
    for bar in range(1, BARS + 1):
        actual = {name for name, part in parts.items() if notes_in(part.measure(bar))}
        layer_presence[bar] = {name: name in actual for name in parts}
        if actual != expected_presence[bar]:
            errors.append(f"第 {bar} 小节声部在场偏差: 实际 {sorted(actual)}，预期 {sorted(expected_presence[bar])}")

    density = {name: [len(notes_in(parts[name].measure(bar))) for bar in range(1, BARS + 1)] for name in parts}
    if density["钢琴"][20] <= density["钢琴"][8]:
        errors.append("银潮段钢琴密度没有高于月影段")
    if density["钢琴"][39] != 1:
        errors.append(f"尾声最后小节钢琴没有收为单一和弦: {density['钢琴'][39]}")

    # 低音只由大提琴承担，且大提琴最低音保持在清晰的 C2 附近。
    for name, part in parts.items():
        if name == "大提琴":
            continue
        if any(p.midi < 48 for p in part.recurse().stream().pitches):
            errors.append(f"{name} 出现低于 C3 的音")
    cello_low = [p.midi for p in parts["大提琴"].recurse().stream().pitches]
    if not cello_low or min(cello_low) < 24 or max(cello_low) > 60:
        errors.append("大提琴音域超出预设")

    wedge_count = sum(2 * len(spans) for spans in WEDGE_SPANS.values())
    if wedge_count < 20:
        errors.append(f"渐强渐弱数量过少: {wedge_count}")

    report = {
        "title": TITLE,
        "bars": BARS,
        "meter": TIME_SIGNATURE,
        "key_fifths": KEY_FIFTHS,
        "parts": list(parts),
        "instrument_names": instrument_names,
        "peak_dynamic_bars": peak_bars,
        "wedge_plan_count": wedge_count,
        "layer_presence": layer_presence,
        "density": density,
        "errors": errors,
    }
    if errors:
        raise SystemExit("SELF-CHECK FAILURE: " + "; ".join(errors))
    return report


def insert_after_attributes(measure: ET.Element, element: ET.Element) -> None:
    children = list(measure)
    attr_index = next((index for index, child in enumerate(children) if child.tag == "attributes"), None)
    measure.insert(attr_index + 1 if attr_index is not None else 0, element)


def write_musicxml(score: stream.Score, destination: Path) -> dict:
    score.write("musicxml", fp=destination)
    tree = ET.parse(destination)
    root = tree.getroot()
    part_list = root.find("part-list")
    if part_list is None:
        raise RuntimeError("MusicXML 缺少 part-list")

    for channel, (name, cfg) in enumerate(PART_CONFIG.items(), start=1):
        score_part = next((item for item in part_list.findall("score-part") if item.findtext("part-name") == name), None)
        if score_part is None:
            raise RuntimeError(f"找不到声部: {name}")
        score_instrument = score_part.find("score-instrument")
        if score_instrument is None:
            score_instrument = ET.SubElement(score_part, "score-instrument", {"id": f"{cfg['id']}-I1"})
        instrument_name = score_instrument.find("instrument-name")
        if instrument_name is None:
            instrument_name = ET.SubElement(score_instrument, "instrument-name")
        instrument_name.text = cfg["xml_name"]
        midi = score_part.find("midi-instrument")
        if midi is None:
            midi = ET.SubElement(score_part, "midi-instrument")
        for child in list(midi):
            if child.tag in {"midi-channel", "midi-program", "pan", "volume"}:
                midi.remove(child)
        ET.SubElement(midi, "midi-channel").text = str(channel)
        ET.SubElement(midi, "midi-program").text = str(cfg["program"])
        ET.SubElement(midi, "pan").text = str(cfg["pan"])
        ET.SubElement(midi, "volume").text = str(cfg["volume"])

    part_ids = {item.findtext("part-name"): item.attrib["id"] for item in part_list.findall("score-part")}
    xml_parts = {item.attrib["id"]: item for item in root.findall("part")}
    for name, spans in WEDGE_SPANS.items():
        xml_part = xml_parts[part_ids[name]]
        measures = {int(item.attrib["number"]): item for item in xml_part.findall("measure")}
        for index, (start, end, kind) in enumerate(spans, start=1):
            for bar, wedge_type in ((start, kind), (end, "stop")):
                direction = ET.Element("direction", {"placement": "below"})
                direction_type = ET.SubElement(direction, "direction-type")
                ET.SubElement(direction_type, "wedge", {"type": wedge_type, "number": str(index)})
                insert_after_attributes(measures[bar], direction)

    tree.write(destination, encoding="utf-8", xml_declaration=True)
    return validate_musicxml(destination)


def validate_musicxml(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    part_list = root.find("part-list")
    xml_parts = root.findall("part")
    errors: list[str] = []
    if part_list is None or len(part_list.findall("score-part")) != 5:
        errors.append("MusicXML 声部目录不是 5 个")
    for xml_part in xml_parts:
        measures = xml_part.findall("measure")
        if len(measures) != BARS:
            errors.append(f"MusicXML {xml_part.attrib.get('id')} 小节数不是 {BARS}")
        first_attr = measures[0].find("attributes") if measures else None
        if first_attr is None or first_attr.findtext("divisions") is None:
            errors.append(f"MusicXML {xml_part.attrib.get('id')} 缺少首小节 attributes")
    wedge_count = len(root.findall(".//wedge"))
    if wedge_count < 20:
        errors.append(f"MusicXML wedge 数量过少: {wedge_count}")
    tempo_values = [item.attrib.get("tempo") for item in root.findall(".//sound") if item.attrib.get("tempo")]
    if "78" not in tempo_values:
        errors.append(f"MusicXML 未写入附点四分音符=52对应的 tempo=78: {tempo_values}")
    if errors:
        raise SystemExit("XML-CHECK FAILURE: " + "; ".join(errors))
    return {"xml_parts": len(xml_parts), "xml_measures": BARS, "wedge_count": wedge_count, "sound_tempos": tempo_values}


def main() -> None:
    score, parts = build_score()
    report = run_self_checks(score, parts)
    destination = OUTPUT / "moonlit_tide_6luna.musicxml"
    report["musicxml"] = write_musicxml(score, destination)
    (OUTPUT / "self_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["musicxml"], ensure_ascii=False))
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
