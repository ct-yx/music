#!/usr/bin/env python3
"""Generate Dawn After Rain and run musical/structural acceptance checks."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from music21 import (  # noqa: E402
    articulations,
    chord,
    clef,
    dynamics,
    expressions,
    instrument,
    key,
    layout,
    metadata,
    meter,
    note,
    spanner,
    stream,
    tempo,
    tie,
)


# Editable musical and export settings.
TITLE = "雨后·晨露 (Dawn After Rain)"
OUTPUT = Path(__file__).resolve().parent
SEED = 241017
TEMPO_BPM = 66
MOTIF = [("F#4", 1), ("B4", 2), ("D5", 1), ("C#5", 2), ("B4", 2)]
MOTIF_SUNRISE = [("F#5", 2), ("B5", 4), ("D6", 2), ("C#6", 4), ("B5", 4)]


CHORDS = [
    "Bm9", "Gmaj7", "Bm9", "Gmaj7", "Em9", "Gmaj7/B", "Bmadd9", "Bmadd9/F#",
    "Gmaj7", "D/F#", "Em9", "Bm7", "Gmaj7#11", "Dmaj7#11/F#", "Bsus4/F#", "F#sus4",
    "D/F#", "A/C#", "Bm7", "Gmaj7#11", "Dmaj7#11", "A/C#", "Bm7", "Gmaj7",
    "Dmaj7#11/F#", "Em9", "Gmaj7", "Asus4",
    "Gmaj7", "D/F#", "Em7", "Bm7", "Gmaj7", "Em9", "Asus4", "Dmaj7add9",
]

CHORD_PCS = {
    "Bm9": ["B", "D", "F#", "A", "C#"], "Bmadd9": ["B", "D", "F#", "C#"],
    "Bmadd9/F#": ["B", "D", "F#", "C#"], "Bm7": ["B", "D", "F#", "A"],
    "Gmaj7": ["G", "B", "D", "F#"], "Gmaj7/B": ["G", "B", "D", "F#"],
    "Gmaj7#11": ["G", "B", "D", "F#", "C#"], "Dmaj7#11/F#": ["D", "F#", "A", "C#", "G#"],
    "Dmaj7": ["D", "F#", "A", "C#"], "Dmaj7#11": ["D", "F#", "A", "C#", "G#"],
    "Dmaj7/F#": ["D", "F#", "A", "C#"], "Dmaj7#11/F#": ["D", "F#", "A", "C#", "G#"],
    "Dmaj7add9": ["D", "F#", "A", "C#", "E"], "D/F#": ["D", "F#", "A"],
    "A/C#": ["A", "C#", "E"], "Asus4": ["A", "D", "E"], "Em9": ["E", "G", "B", "D", "F#"],
    "Em7": ["E", "G", "B", "D"], "Bsus4/F#": ["B", "E", "F#"], "F#sus4": ["F#", "B", "C#"],
}


def pitched(name: str, duration: float, *, tie: str | None = None) -> note.Note:
    n = note.Note(name, quarterLength=duration)
    n.tie = note.Tie(tie) if tie else None
    return n


def put_events(measure: stream.Measure, events: list[tuple[float, str | None]]) -> None:
    """Insert sequential (duration, pitch-or-rest) events, padding to four beats."""
    offset = 0.0
    run: list[note.Note] = []
    for duration, pitch in events:
        obj = pitched(pitch, duration) if pitch else note.Rest(quarterLength=duration)
        measure.insert(offset, obj)
        if isinstance(obj, note.Note):
            run.append(obj)
        elif len(run) > 1:
            measure.insert(0, spanner.Slur(*run))
            run = []
        else:
            run = []
        offset += duration
    if offset < 4:
        measure.insert(offset, note.Rest(quarterLength=4 - offset))
    if offset > 4:
        raise ValueError(f"Measure overflows: {offset} beats")
    if len(run) > 1:
        measure.insert(0, spanner.Slur(*run))


def put_chord_events(measure: stream.Measure, events: list[tuple[float, list[str] | None]]) -> None:
    """Insert sustained open-voicing piano chords and rests."""
    offset = 0.0
    for duration, pitches in events:
        obj = chord.Chord(pitches, quarterLength=duration) if pitches else note.Rest(quarterLength=duration)
        measure.insert(offset, obj)
        offset += duration
    if offset < 4:
        measure.insert(offset, note.Rest(quarterLength=4 - offset))
    if offset > 4:
        raise ValueError(f"Measure overflows: {offset} beats")


def make_part(name: str, inst: instrument.Instrument, clef_obj: clef.Clef) -> stream.PartStaff:
    part = stream.PartStaff(id=name.replace(" ", ""))
    part.partName = name
    part.insert(0, inst)
    part.insert(0, clef_obj)
    return part


def make_score() -> tuple[stream.Score, dict[str, stream.PartStaff]]:
    random.seed(SEED)
    score = stream.Score(id="DawnAfterRain")
    score.insert(0, metadata.Metadata())
    score.metadata.title = TITLE
    score.metadata.composer = ""

    parts = {
        "Flute": make_part("Flute", instrument.Flute(), clef.TrebleClef()),
        "Harp": make_part("Harp", instrument.Harp(), clef.TrebleClef()),
        "Celesta": make_part("Celesta", instrument.Celesta(), clef.TrebleClef()),
        "Violin I": make_part("Violin I", instrument.Violin(), clef.TrebleClef()),
        "Violin II": make_part("Violin II", instrument.Violin(), clef.TrebleClef()),
        "Viola": make_part("Viola", instrument.Viola(), clef.AltoClef()),
        "Cello": make_part("Cello", instrument.Violoncello(), clef.BassClef()),
        "Piano RH": make_part("Piano", instrument.Piano(), clef.TrebleClef()),
        "Piano LH": make_part("Piano", instrument.Piano(), clef.BassClef()),
    }
    for part in parts.values():
        score.insert(0, part)
    score.insert(0, layout.StaffGroup([parts["Piano RH"], parts["Piano LH"]], name="Piano", symbol="brace"))

    # Per-bar upper-register rain pattern and irregular high drops.
    rain_counts = [6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 4, 4, 3, 3, 2, 1]
    drop_counts = [0] * 20 + [2, 1, 3, 2, 1, 4, 2, 3, 3, 3, 2, 2, 1, 1, 1, 1]

    for bar, chord_name in enumerate(CHORDS, start=1):
        chord_pcs = CHORD_PCS[chord_name]
        for part in parts.values():
            m = stream.Measure(number=bar)
            if bar in (1, 17):
                m.insert(0, key.KeySignature(2))
            if bar == 1:
                m.insert(0, meter.TimeSignature("4/4"))
            if part.id == "Flute" and bar == 1:
                m.insert(0, tempo.MetronomeMark(number=TEMPO_BPM))
            part.append(m)

        # Steady pedal bass in the first section; suspend F# through the dawn.
        bass = parts["Piano LH"].measure(bar)
        if bar <= 8:
            put_events(bass, [(2, "B2"), (2, "E3" if bar == 5 else None)])
        elif 15 <= bar <= 16:
            put_events(bass, [(4, "F#2")])
        elif bar in (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28):
            root = {"D": "D2", "A": "A2", "B": "B2", "G": "G2", "E": "E2"}.get(chord_pcs[0], "D2")
            put_chord_events(bass, [(2, [root, "A2", "D3"]), (2, [root, "A2", "D3"])])
        elif bar <= 35:
            put_events(bass, [(2, "D2" if bar >= 17 else "B2"), (2, None)])
        else:
            put_events(bass, [(4, "D2")])

        # Piano RH: open eighth-note arpeggios, progressively fewer notes.
        rh = parts["Piano RH"].measure(bar)
        if bar <= 16:
            count = rain_counts[bar - 1]
            if bar <= 8:
                count = random.choice([5, 6])
            gaps = set(random.sample(range(8), 8 - count))
            pcs = chord_pcs[:]
            random.shuffle(pcs)
            events: list[tuple[float, str | None]] = []
            for i in range(8):
                events.append((0.5, None if i in gaps else f"{pcs[i % len(pcs)]}{5 + (i % 2)}"))
            put_events(rh, events)
        elif bar <= 28:
            pcs = chord_pcs[:]
            random.shuffle(pcs)
            patterns = [
                [0, 1, 2, 3, 1, 2, 3, 4], [0, 2, 1, 3, 4, 2, 1, 0],
                [1, 2, 3, 0, 2, 4, 1, 3], [0, 1, 3, 2, 4, 3, 1, 2],
            ]
            order = patterns[(bar - 17) // 2 % len(patterns)]
            events = [(0.5, f"{pcs[order[i] % len(pcs)]}{5 if i % 2 == 0 else 6}") for i in range(8)]
            put_events(rh, events)
        else:
            echo = {29: "F#5", 30: "B5", 31: "D6", 32: "F#5", 33: "B5", 34: "D6", 35: "F#5"}.get(bar)
            put_events(rh, [(1, echo), (3, None)] if echo else [(4, None)])

        # Motif in B minor, exact pitches/durations; occupy bars 5-6 only.
        if bar in (5, 6):
            for element in list(rh.notesAndRests):
                rh.remove(element)
            motif_events = ([(1, "F#4"), (2, "B4"), (1, "D5")]
                            if bar == 5 else [(2, "C#5"), (2, "B4")])
            put_events(rh, motif_events)

        # Harp enters after the rain, supports with a few low-mid chord tones.
        harp = parts["Harp"].measure(bar)
        if 9 <= bar <= 32:
            if 21 <= bar <= 32:
                scale = ["D", "E", "F#", "A", "B"]
                pitches = ["G#6" if bar in (21, 25) else f"{random.choice(scale)}6"]
                put_events(harp, [(0.5, None), (0.25, pitches[0]), (3.25, None)])
            else:
                pitches = [f"{pc}{5 + (i % 2)}" for i, pc in enumerate(chord_pcs[:3])]
                put_events(harp, [(1, pitches[0]), (1, None), (1, pitches[1]), (1, None)])
        else:
            put_events(harp, [(4, None)])

        # Sustained cello and viola in the accumulation; all strings bloom at dawn.
        cello = parts["Cello"].measure(bar)
        viola = parts["Viola"].measure(bar)
        v1 = parts["Violin I"].measure(bar)
        v2 = parts["Violin II"].measure(bar)
        flute = parts["Flute"].measure(bar)
        if 5 <= bar <= 8:
            put_events(cello, [(2, "B2" if bar <= 6 else "E3"), (2, "E3" if bar == 5 else None)])
            if bar == 6:
                put_events(viola, [(2, "G4"), (2, "D4")])
            else:
                put_events(viola, [(2, f"{chord_pcs[1]}4"), (2, None)])
        elif 9 <= bar <= 14:
            put_events(cello, [(4, "E3" if bar <= 12 else "F#3")])
            put_events(viola, [(2, f"{chord_pcs[1]}4"), (2, f"{chord_pcs[2]}4")])
            put_events(v2, [(2, f"{chord_pcs[1]}4"), (2, f"{chord_pcs[2]}4")])
            if 13 <= bar <= 14:
                put_events(flute, [(3, "F#5"), (1, None)])
        elif 13 <= bar <= 20:
            flute_pitch = "G#5" if bar == 15 else f"{chord_pcs[-1]}5"
            put_events(flute, [(3, flute_pitch), (1, None)])
            put_events(v2, [(2, f"{chord_pcs[1]}4"), (2, f"{chord_pcs[2]}4")])
            if 15 <= bar <= 16:
                put_events(cello, [(4, "F#3")])
            elif 17 <= bar <= 20:
                cello_line = {17: "A3", 18: "E3", 19: "F#3", 20: "B3"}[bar]
                put_events(cello, [(4, cello_line)])
                put_events(viola, [(2, f"{chord_pcs[1]}4"), (2, f"{chord_pcs[2]}4")])
                if bar == 17:
                    put_events(v1, [(2, "F#5"), (2, "B5")])
                    v1.notes[-1].tie = tie.Tie("start")
                elif bar == 18:
                    put_events(v1, [(2, "B5"), (2, "D6")])
                    v1.notes[0].tie = tie.Tie("stop")
                elif bar == 19:
                    put_events(v1, [(4, "C#6")])
                elif bar == 20:
                    put_events(v1, [(4, "B5")])
        elif 21 <= bar <= 24:
            cello_line = {21: "F#3", 22: "E3", 23: "F#3", 24: "B3"}[bar]
            put_events(cello, [(4, cello_line)])
            put_events(viola, [(2, f"{chord_pcs[1]}4"), (2, f"{chord_pcs[2]}4")])
            put_events(v2, [(2, f"{chord_pcs[-1]}4"), (2, None)])
            answer = {21: [(2, "D6"), (1, "C#6"), (1, "B5")],
                      22: [(2, "A5"), (1, "G5"), (1, "F#5")],
                      23: [(2, "D6"), (1, "C#6"), (1, "B5")],
                      24: [(4, "D6")]}[bar]
            put_events(v1, answer)
            put_events(flute, [(d, p.replace("5", "6")) for d, p in answer])
        elif 25 <= bar <= 28:
            cello_line = {25: "A3", 26: "G3", 27: "F#3", 28: "E3"}[bar]
            put_events(cello, [(4, cello_line)])
            put_events(viola, [(2, f"{chord_pcs[1]}4"), (2, f"{chord_pcs[2]}4")])
            put_events(v2, [(2, f"{chord_pcs[-1]}4"), (2, f"{chord_pcs[1]}4")])
            put_events(v1, [(4, "F#5" if bar == 25 else "E5")])
            put_events(flute, [(4, "G#5" if bar == 25 else "F#5")])
        elif 29 <= bar <= 30:
            put_events(cello, [(4, "A3")])
            put_events(viola, [(2, f"{chord_pcs[1]}4"), (2, f"{chord_pcs[2]}4")])
            put_events(v2, [(1, None)])
            put_events(v1, [(1, None)])
        elif 31 <= bar <= 32:
            put_events(cello, [(4, "A3" if bar == 31 else None)])
            put_events(viola, [(1, None)])
            put_events(v2, [(1, None)])
            put_events(v1, [(1, None)])
        else:
            for p in (cello, viola, v1, v2, flute):
                put_events(p, [(4, None)])

        # Celesta drops: syncopated eighth-grid onsets with non-repeating bars.
        celesta = parts["Celesta"].measure(bar)
        if drop_counts[bar - 1]:
            count = drop_counts[bar - 1]
            fixed_tail = {33: [1], 34: [3], 35: [5], 36: [7]}
            positions = fixed_tail.get(bar)
            if positions is None:
                positions = sorted(random.sample(range(1, 8), count))
                previous = sorted({int(n.offset * 2) for n in parts["Celesta"].measure(bar - 1).notes}) if bar > 21 else []
                while positions == previous:
                    positions = sorted(random.sample(range(1, 8), count))
            events = []
            cursor = 0.0
            scale = ["D", "E", "F#", "A", "B"]
            for idx, pos in enumerate(positions):
                onset = pos * 0.5
                if onset > cursor:
                    events.append((onset - cursor, None))
                drop_pitch = "E7" if bar == 36 else f"{random.choice(scale)}6"
                events.append((0.25, drop_pitch))
                cursor = onset + 0.25
            if cursor < 4:
                events.append((4 - cursor, None))
            put_events(celesta, events)
        else:
            put_events(celesta, [(4, None)])

    # Explicitly fill intentionally silent staves so every part has full measures.
    for part in parts.values():
        for m in part.getElementsByClass(stream.Measure):
            remaining = 4 - m.duration.quarterLength
            if remaining > 0:
                m.insert(m.duration.quarterLength, note.Rest(quarterLength=remaining))
            elif remaining < 0:
                raise ValueError(f"{part.partName} bar {m.number} exceeds four beats")

    # Long cello bows: slurs cross barlines so the low line does not re-articulate every measure.
    cello_part = parts["Cello"]
    for first, last in [(9, 12), (13, 16), (17, 20), (21, 24), (25, 28), (29, 31)]:
        line = [cello_part.measure(bar).notes[0] for bar in range(first, last + 1)
                if cello_part.measure(bar).notes]
        if len(line) > 1:
            cello_part.insert(0, spanner.Slur(*line))

    # Independent dynamics and real MusicXML wedges for each instrumental family.
    dynpart = parts["Flute"]
    plans = {
        "strings": ([17, 20, 23, 29, 33], ["mp", "f", "mf", "mp", "pp"]),
        "Flute": ([1, 13, 17, 20, 23, 29, 33], ["pp", "p", "mp", "f", "mf", "mp", "pp"]),
        "Piano RH": ([1, 17, 20, 23, 29, 33], ["pp", "mp", "mf", "mp", "p", "pp"]),
        "Piano LH": ([1, 17, 20, 23, 29, 33], ["pp", "p", "mp", "p", "p", "pp"]),
        "drops": ([1, 21, 29, 33, 36], ["pp", "p", "p", "pp", "ppp"]),
    }
    string_names = {"Violin I", "Violin II", "Viola", "Cello"}
    for name, part in parts.items():
        group = "strings" if name in string_names else ("drops" if name in {"Harp", "Celesta"} else name)
        bars, marks = plans[group]
        for bar, mark in zip(bars, marks):
            part.measure(bar).insert(0, dynamics.Dynamic(mark))
        if name == "Cello":
            spans = [(9, 14, "crescendo"), (17, 22, "crescendo"), (23, 31, "diminuendo")]
        elif group == "strings":
            spans = [(17, 22, "crescendo"), (23, 28, "diminuendo"), (29, 36, "diminuendo")]
        elif group == "drops":
            spans = [(21, 28, "diminuendo"), (29, 36, "diminuendo")]
        else:
            spans = [(17, 22, "crescendo"), (23, 28, "diminuendo"), (29, 36, "diminuendo")]
        for start, end, kind in spans:
            wedge = dynamics.Crescendo() if kind == "crescendo" else dynamics.Diminuendo()
            wedge.addSpannedElements(part.measure(start), part.measure(end))
            part.insert(0, wedge)
    dynpart.measure(35).insert(0, tempo.MetronomeMark(number=62, text="poco rit."))
    dynpart.measure(36).insert(0, tempo.MetronomeMark(number=58, text="rit."))
    final_rh = parts["Piano RH"].measure(36)
    for element in list(final_rh.notesAndRests):
        final_rh.remove(element)
    final_chord = chord.Chord(["D5", "F#5", "A5", "C#6", "E6"], quarterLength=4)
    final_chord.expressions.append(expressions.Fermata())
    final_rh.insert(0, final_chord)
    final_lh = parts["Piano LH"].measure(36)
    for element in list(final_lh.notesAndRests):
        final_lh.remove(element)
    put_events(final_lh, [(4, "D2")])
    dynpart.measure(36).insert(0, expressions.TextExpression("morendo"))

    # Piano sustain pedal, renewed once per harmony through MusicXML pedal marks.
    for bar in range(1, 37):
        m = parts["Piano RH"].measure(bar)
        pedal = expressions.PedalMark(*list(m.notesAndRests))
        pedal.pedalForm = "line"
        m.insert(0, pedal)
    return score, parts


def pitch_ranges(parts: dict[str, stream.PartStaff]) -> dict[str, tuple[int, int]]:
    out = {}
    for name, part in parts.items():
        pitches = [p.midi for p in part.recurse().pitches]
        if pitches:
            out[name] = (min(pitches), max(pitches))
    return out


def run_checks(score: stream.Score, parts: dict[str, stream.PartStaff]) -> None:
    errors = []
    for name, part in parts.items():
        measures = list(part.getElementsByClass(stream.Measure))
        if len(measures) != 36:
            errors.append(f"{name}: {len(measures)} measures")
        for m in measures:
            if m.duration.quarterLength != 4:
                errors.append(f"{name} bar {m.number}: duration {m.duration.quarterLength}")

    all_objects = list(score.recurse())
    forbidden = [a for a in all_objects if isinstance(a, articulations.Articulation)
                 and a.__class__.__name__.lower() in {"accent", "marcato", "strongaccent"}]
    dyns = [d.value for d in all_objects if isinstance(d, dynamics.Dynamic)]
    if forbidden:
        errors.append("forbidden accent/marcato articulation found")
    if any(d in {"ff", "fff", "ffff"} for d in dyns):
        errors.append("dynamic exceeds f")

    key_values = [ks.sharps for ks in score.recurse().getElementsByClass(key.KeySignature)]
    if any(v != 2 for v in key_values):
        errors.append(f"key signature is not uniformly two sharps: {key_values}")
    wedges = list(score.recurse().getElementsByClass((dynamics.Crescendo, dynamics.Diminuendo)))
    if not wedges:
        errors.append("no crescendo/diminuendo wedge found")

    for name in ("Harp", "Celesta"):
        drop_dyns = [d.value for d in parts[name].recurse().getElementsByClass(dynamics.Dynamic)]
        if any(d not in {"ppp", "pp", "p"} for d in drop_dyns):
            errors.append(f"{name} dew dynamics exceeds p: {drop_dyns}")

    for bar in range(17, 29):
        if len(parts["Piano RH"].measure(bar).notes) != 8:
            errors.append(f"Piano RH bar {bar} is not eight eighth notes")
        cello_pitches = {p.nameWithOctave for p in parts["Cello"].measure(bar).recurse().pitches}
        lh_pitches = {p.nameWithOctave for p in parts["Piano LH"].measure(bar).recurse().pitches}
        if cello_pitches & lh_pitches:
            errors.append(f"Cello/Piano LH overlap in bar {bar}: {sorted(cello_pitches & lh_pitches)}")

    # The seed motif appears in bars 5-6; its duration-doubled octave in bars 17-20.
    motif_a = [n.nameWithOctave for b in (5, 6) for n in parts["Piano RH"].measure(b).notes]
    motif_c_notes = [n for b in (17, 18, 19, 20) for n in parts["Violin I"].measure(b).notes
                     if not (n.tie and n.tie.type == "stop")]
    motif_c = [n.nameWithOctave for n in motif_c_notes]
    if motif_a[:5] != [p for p, _ in MOTIF] or motif_c[:5] != [p for p, _ in MOTIF_SUNRISE]:
        errors.append(f"motif mismatch: A={motif_a[:5]}, dawn={motif_c[:5]}")

    # Irregular drops must include off-beat onsets and adjacent patterns must differ.
    cel = parts["Celesta"]
    patterns = []
    offbeat = False
    for bar in range(21, 37):
        m = cel.measure(bar)
        ons = tuple(round(n.offset, 2) for n in m.notes)
        patterns.append(ons)
        offbeat |= any(x % 1 != 0 for x in ons)
    if not offbeat:
        errors.append("no celesta drop lands off the beat")
    if any(a == b for a, b in zip(patterns, patterns[1:])):
        errors.append("adjacent dew-drop rhythm patterns repeat")

    # Range sanity for named parts.
    ranges = pitch_ranges(parts)
    limits = {"Violin I": (55, 127), "Violin II": (55, 127), "Viola": (48, 127),
              "Cello": (36, 127), "Flute": (60, 127), "Harp": (36, 103),
              "Piano RH": (48, 108), "Piano LH": (28, 84)}
    for name, (low, high) in limits.items():
        if name in ranges and not (ranges[name][0] >= low and ranges[name][1] <= high):
            errors.append(f"{name} range out of bounds: {ranges[name]}")

    print("Self-checks:")
    print(f"  Measures/duration: {'PASS' if not errors or not any('measure' in e or 'duration' in e for e in errors) else 'FAIL'}")
    print(f"  Forbidden markings/dynamics: {'PASS' if not forbidden and not any(d.startswith('f') and d != 'f' for d in dyns) else 'FAIL'}")
    print(f"  Motif: {'PASS' if motif_a[:5] == [p for p, _ in MOTIF] and motif_c[:5] == [p for p, _ in MOTIF_SUNRISE] else 'FAIL'}")
    print(f"  Dew rhythm: {'PASS' if offbeat and not any(a == b for a, b in zip(patterns, patterns[1:])) else 'FAIL'}")
    print(f"  Key signatures: {'PASS' if all(v == 2 for v in key_values) else 'FAIL'}")
    print(f"  Hairpins: {'PASS' if wedges else 'FAIL'} ({len(wedges)})")
    print(f"  Dew dynamics: {'PASS' if not any(d not in {'ppp', 'pp', 'p'} for name in ('Harp', 'Celesta') for d in [x.value for x in parts[name].recurse().getElementsByClass(dynamics.Dynamic)]) else 'FAIL'}")
    print(f"  Cello/Piano LH separation: {'PASS' if not any('Cello/Piano LH overlap' in e for e in errors) else 'FAIL'}")
    print("Density by bar (note count across staves):")
    for bar in range(1, 37):
        count = sum(len(part.measure(bar).notes) for part in parts.values())
        print(f"  {bar:02d}: {count:2d}")
    print("Ranges (MIDI): " + ", ".join(f"{k} {v[0]}-{v[1]}" for k, v in ranges.items()))
    if errors:
        raise SystemExit("SELF-CHECK FAILURE: " + "; ".join(errors))


def main() -> None:
    score, parts = make_score()
    run_checks(score, parts)
    destination = OUTPUT / "dawn_after_rain.musicxml"
    score.write("musicxml", fp=destination)
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
