#!/usr/bin/env python3
"""
speechscore.py — automatic scoring for the 6-Week Articulation Training Plan.

Built for a fluent non-native speaker (Italian L1, English L2): it measures
not just fillers, but WHERE you pause (inside a clause vs at a boundary),
articulation rate, sentence length and self-repairs.

SETUP (once, on your Mac)
    python3 -m pip install faster-whisper
    (first run downloads the Whisper model, ~500 MB for "small")

USE
    python3 speechscore.py recording.m4a --tag "W0-A impromptu"
    python3 speechscore.py talk.mp3 --tag "W6-IT" --lang it
    python3 speechscore.py rec.m4a --model medium      # slower, more accurate

    Accepts m4a, mp3, wav, mov, mp4 (iPhone Voice Memos / video are fine).

OUTPUT
    1. Scorecard printed to the terminal
    2. <recording>.report.md  — scorecard + transcript with pauses marked
       + a ready-to-paste prompt for Claude (time-to-point, structure,
       conciseness, close — the things a script can't judge)
    3. speech_log.csv         — one row per recording, for week-on-week tracking
    4. <recording>.words.json — raw word timings (re-score later with --from-json)

LIMITS (read these)
    - Whisper tends to "clean up" speech and drop um/uh. The script prompts it
      to transcribe verbatim, which helps but is not perfect: filler counts are
      a floor, not an exact number.
    - Boundary vs mid-clause is a heuristic based on Whisper's punctuation and
      a list of clause-starting words. Good enough for trends, not for a paper.
"""

import argparse
import csv
import json
import os
import re
import statistics
import sys
from datetime import datetime

# ---------------------------------------------------------------- word lists

FILLERS = {
    "en": {"um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "mm", "eh"},
    "it": {"eh", "ehm", "ehh", "mmm", "cioè", "diciamo", "tipo", "insomma",
           "praticamente", "vabbè", "boh"},
}
# Multi-word / ambiguous discourse markers: counted separately as "hedges".
HEDGES = {
    "en": ["you know", "i mean", "sort of", "kind of", "basically",
           "actually", "literally", "like"],
    "it": ["come dire", "in pratica", "per così dire", "allora", "niente"],
}
# A pause BEFORE one of these words counts as a clause-boundary pause.
CLAUSE_STARTERS = {
    "en": {"and", "but", "so", "because", "which", "that", "who", "when",
           "where", "if", "although", "though", "while", "whereas", "then",
           "or", "since", "unless", "until", "after", "before", "however",
           "therefore", "first", "second", "third", "finally", "now"},
    "it": {"e", "ma", "però", "quindi", "perché", "che", "quando", "dove",
           "se", "mentre", "anche", "poi", "oppure", "o", "invece", "infatti",
           "dunque", "cioè", "inoltre", "primo", "secondo", "infine"},
}
BOUNDARY_PUNCT = tuple(".,;:?!—–")
VERBATIM_PROMPT = {
    "en": "Umm, so, uh, I was like, you know, thinking about it... Hmm. Er, okay.",
    "it": "Ehm, allora, eh, diciamo che, cioè, stavo pensando... Mmm. Ehm, ok.",
}

PAUSE_MIN = 0.30   # seconds; shorter gaps are normal articulation
LONG_PAUSE = 1.00  # seconds


def norm(w):
    return re.sub(r"[^\w'àèéìòùç]", "", w.lower())


# ---------------------------------------------------------------- transcribe

def transcribe(path, model_name, lang):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper not installed. Run:  python3 -m pip install faster-whisper")
    print(f"Transcribing with Whisper '{model_name}' ({lang}) … first run downloads the model.")
    model = WhisperModel(model_name, device="auto", compute_type="int8")
    segments, info = model.transcribe(
        path, language=lang, word_timestamps=True,
        initial_prompt=VERBATIM_PROMPT.get(lang),
        vad_filter=False,              # keep pauses; don't let VAD hide them
        condition_on_previous_text=False,
    )
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
    return words


# ---------------------------------------------------------------- analyse

def analyse(words, lang):
    if len(words) < 5:
        sys.exit("Too few words recognised to score.")
    fillers_set = FILLERS.get(lang, set()) | FILLERS["en"] if lang != "en" else FILLERS["en"]
    starters = CLAUSE_STARTERS.get(lang, CLAUSE_STARTERS["en"])

    start, end = words[0]["s"], words[-1]["e"]
    dur_min = max((end - start) / 60, 1e-6)
    tokens = [norm(w["w"]) for w in words]
    content = [t for t in tokens if t and t not in fillers_set]

    # fillers
    filler_hits = [t for t in tokens if t in fillers_set]
    text_lc = " " + " ".join(tokens) + " "
    hedge_hits = {h: text_lc.count(f" {h} ") for h in HEDGES.get(lang, [])}
    hedge_hits = {h: n for h, n in hedge_hits.items() if n}

    # pauses
    pauses = []  # (index_after_word, gap, kind)
    for i in range(len(words) - 1):
        gap = words[i + 1]["s"] - words[i]["e"]
        if gap < PAUSE_MIN:
            continue
        prev_raw = words[i]["w"]
        nxt = tokens[i + 1]
        boundary = prev_raw.endswith(BOUNDARY_PUNCT) or nxt in starters \
            or tokens[i] in fillers_set or nxt in fillers_set
        pauses.append((i, gap, "boundary" if boundary else "mid"))
    mid = [p for p in pauses if p[2] == "mid"]
    bnd = [p for p in pauses if p[2] == "boundary"]
    pause_time = sum(p[1] for p in pauses)
    speak_min = max(((end - start) - pause_time) / 60, 1e-6)

    # sentences
    sentences, cur = [], 0
    for w, t in zip(words, tokens):
        if t and t not in fillers_set:
            cur += 1
        if w["w"].endswith((".", "?", "!")):
            if cur:
                sentences.append(cur)
            cur = 0
    if cur:
        sentences.append(cur)

    # self-repairs: immediate word repetitions ("the the", "we we")
    reps = sum(1 for a, b in zip(content, content[1:]) if a == b and len(a) > 0)

    m = {
        "duration_s": round(end - start, 1),
        "words": len(content),
        "wpm": round(len(content) / dur_min),
        "articulation_wpm": round(len(content) / speak_min),
        "fillers": len(filler_hits),
        "fillers_per_min": round(len(filler_hits) / dur_min, 1),
        "hedges": sum(hedge_hits.values()),
        "midclause_pauses": len(mid),
        "midclause_per_min": round(len(mid) / dur_min, 1),
        "boundary_pauses": len(bnd),
        "midclause_share_pct": round(100 * len(mid) / len(pauses)) if pauses else 0,
        "long_pauses_1s": sum(1 for p in pauses if p[1] >= LONG_PAUSE),
        "mean_pause_s": round(statistics.mean([p[1] for p in pauses]), 2) if pauses else 0,
        "avg_sentence_words": round(statistics.mean(sentences), 1) if sentences else 0,
        "max_sentence_words": max(sentences) if sentences else 0,
        "repetitions": reps,
    }
    detail = {"filler_words": filler_hits, "hedges": hedge_hits, "pauses": pauses}
    return m, detail


# ---------------------------------------------------------------- report

TARGETS = [
    ("midclause_per_min", "Pauses inside clauses / min", "≤ 2", lambda v: v <= 2),
    ("midclause_share_pct", "Share of pauses inside clauses (%)", "≤ 30%", lambda v: v <= 30),
    ("wpm", "Pace (wpm, overall)", "130–150", lambda v: 130 <= v <= 150),
    ("articulation_wpm", "Articulation rate (wpm, excl. pauses)", "info", None),
    ("fillers_per_min", "Fillers / min", "≤ 3", lambda v: v <= 3),
    ("hedges", "Hedges (you know, basically, like…)", "info", None),
    ("long_pauses_1s", "Pauses ≥ 1 s", "info", None),
    ("avg_sentence_words", "Avg sentence length (words)", "≤ 20", lambda v: v <= 20),
    ("max_sentence_words", "Longest sentence (words)", "≤ 35", lambda v: v <= 35),
    ("repetitions", "Repeated words (self-repairs)", "info", None),
]


def scorecard_lines(m):
    out = []
    for key, label, target, ok in TARGETS:
        v = m[key]
        flag = "" if ok is None else ("  ✓" if ok(v) else "  ✗")
        out.append(f"{label:<40} {v:>7}   target {target}{flag}")
    return out


def marked_transcript(words, detail):
    pause_after = {i: (g, k) for i, g, k in detail["pauses"]}
    parts = []
    for i, w in enumerate(words):
        parts.append(w["w"])
        if i in pause_after:
            g, k = pause_after[i]
            parts.append(f"[{'‖' if k == 'mid' else '/'}{g:.1f}s]")
    return " ".join(parts)


CLAUDE_PROMPT = """Score this spoken answer (I'm a fluent non-native English speaker; the transcript is verbatim, with pauses marked as [/0.6s] at clause boundaries and [‖0.6s] inside clauses).

1. Time-to-point: at which second / after how many words do I state my main answer or recommendation?
2. Structure: name the 2–3 points a listener would remember. Which structure did I use (What/So what/Now what, Problem/Solution/Benefit, answer-first)? Was it clear?
3. Conciseness: rewrite my answer at half the length, keeping the meaning.
4. Close: did I land a clear final sentence or trail off?
5. Non-native patterns: Italian-style sentence construction, literal translations, unnatural collocations or word choices — list each with a more natural English alternative.
Score 1–5 on items 1–4. Be direct.
"""


def write_outputs(path, words, m, detail, tag, lang, logfile):
    base = os.path.splitext(path)[0]
    with open(base + ".words.json", "w") as f:
        json.dump({"lang": lang, "words": words}, f, ensure_ascii=False)

    lines = scorecard_lines(m)
    md = [f"# Speech score — {tag or os.path.basename(path)}",
          f"{datetime.now():%Y-%m-%d %H:%M} · {m['duration_s']} s · {m['words']} words · lang={lang}", "",
          "## Scorecard", "```", *lines, "```", ""]
    if detail["filler_words"]:
        md.append("Fillers heard: " + ", ".join(detail["filler_words"]))
    if detail["hedges"]:
        md.append("Hedges: " + ", ".join(f"{h} ×{n}" for h, n in detail["hedges"].items()))
    md += ["", "## Transcript (‖ = pause inside a clause, / = pause at a boundary)", "",
           marked_transcript(words, detail), "",
           "## Paste into Claude for the judgement metrics", "", "```",
           CLAUDE_PROMPT, "TRANSCRIPT:", marked_transcript(words, detail), "```"]
    report = base + ".report.md"
    with open(report, "w") as f:
        f.write("\n".join(md))

    new = not os.path.exists(logfile)
    with open(logfile, "a", newline="") as f:
        wr = csv.writer(f)
        if new:
            wr.writerow(["date", "tag", "file", "lang", *m.keys()])
        wr.writerow([f"{datetime.now():%Y-%m-%d %H:%M}", tag, os.path.basename(path), lang, *m.values()])
    return report, lines


def main():
    ap = argparse.ArgumentParser(description="Score a speech recording.")
    ap.add_argument("audio", help="audio/video file, or a .words.json with --from-json")
    ap.add_argument("--tag", default="", help='label, e.g. "W0-A impromptu"')
    ap.add_argument("--lang", default="en", choices=["en", "it"])
    ap.add_argument("--model", default="small", help="tiny | base | small | medium | large-v3")
    ap.add_argument("--log", default="speech_log.csv")
    ap.add_argument("--from-json", action="store_true", help="re-score saved word timings")
    a = ap.parse_args()

    if a.from_json:
        data = json.load(open(a.audio))
        words, lang = data["words"], data.get("lang", a.lang)
        src = a.audio.replace(".words.json", "")
    else:
        words, lang, src = transcribe(a.audio, a.model, a.lang), a.lang, a.audio

    m, detail = analyse(words, lang)
    report, lines = write_outputs(src, words, m, detail, a.tag, lang, a.log)
    print("\n".join(["", *lines, "", f"Report: {report}", f"Log:    {a.log}"]))


if __name__ == "__main__":
    main()
