# speechscore

Automatic speaking-fluency scoring for **fluent non-native English speakers**.

Most speech coaches count "um" and "uh". Fluent non-native speakers often use few fillers. Their tell is different: they pause **inside** a phrase while searching for a word ("we should… prioritise the… settlement layer"). They also tend to carry the rhythm and long sentences of their first language. speechscore measures those patterns as well as the usual ones.

You record yourself, run one command, and get:

- **A scorecard** in the terminal, with targets
- **A report** (`.report.md`): the verbatim transcript with every pause marked, plus a ready-made prompt to paste into an LLM for the things a script can't judge (structure, time to the main point, conciseness)
- **A CSV log** with one row per recording, to track progress week by week

Supports English and Italian (fillers like *eh, cioè, diciamo*). Other languages are easy to add.

## What it measures

| Metric | Why it matters |
|---|---|
| Pauses inside clauses / min | The main fluency marker for non-native speakers. Listeners read mid-phrase pauses as hesitation. |
| Share of pauses inside clauses | Fluent speakers pause mostly at clause boundaries |
| Pace (wpm) and articulation rate | Overall speed vs. speed excluding pauses. Target about 130–150 wpm for talks. |
| Fillers / min (EN + IT) | Credibility drops above about 5/min ([Laske et al., 2024](https://behavioristbookclub.com/aba-research/aba-fundamentals/um--so--like--do-speech-disfluencies-matter--a-parametric-evaluation-o/)) |
| Hedges (*you know, basically, like*) | Discourse markers, counted separately because they are ambiguous |
| Long pauses (≥ 1 s) | Word-search or loss of thread |
| Average and longest sentence length | Long, nested sentences bury the point |
| Repeated words | Self-repairs ("the the", "we we") |

## Install

Requires Python 3.9+.

```bash
git clone https://github.com/Andrea10/speechscore.git
cd speechscore
python3 -m pip install -r requirements.txt
```

The first run downloads a Whisper model (about 500 MB for `small`).

## Use

```bash
python3 speechscore.py recording.m4a --tag "W1-A impromptu"
python3 speechscore.py talk.mp3 --lang it            # Italian
python3 speechscore.py rec.m4a --model medium         # slower, more accurate
python3 speechscore.py rec.words.json --from-json     # re-score saved timings
```

It accepts m4a, mp3, wav, mov and mp4, so iPhone Voice Memos and videos work as they are.

Example scorecard:

```
Pauses inside clauses / min                  5.4   target ≤ 2  ✗
Share of pauses inside clauses (%)            25   target ≤ 30%  ✓
Pace (wpm, overall)                          117   target 130–150  ✗
Articulation rate (wpm, excl. pauses)        161   target info
Fillers / min                                2.7   target ≤ 3  ✓
...
```

In the transcript, `‖` marks a pause inside a clause and `/` marks a pause at a boundary:

```
So the main point is that we should, [/0.6s] prioritise [‖0.8s] the settlement layer.
```

## Suggested routine

1. Record three 2-minute samples each week: an impromptu answer, an explanation and a recommendation.
2. Score them, and look at pauses inside clauses and pace first.
3. Paste the prompt from the report into an LLM to get feedback on structure and conciseness.
4. Pick **one** metric to improve the following week. Watch the trend in `speech_log.csv`.

## Coaching on your phone

The script measures *how* you speak. To improve *what* you say (structure, concision, sounding natural), use the coach in [`coach/`](coach/):

- [`coach/INSTRUCTIONS.md`](coach/INSTRUCTIONS.md): paste into a Claude Project's custom instructions. You then dictate an answer in the Claude app and get back a diagnosis, a rewrite, reusable patterns and a drill. Say "drill me" for a practice prompt.
- [`coach/PLAYBOOK.md`](coach/PLAYBOOK.md): the reference the coach uses. It covers answer structures (PREP, What/So what/Now what, SCQA, STAR+L), sentence patterns, a phrase bank and Italian-to-English traps. Upload it to the Project's knowledge.

Suggested split: coach daily on your phone (10 minutes, anywhere), and score with the script weekly.

## Limits

- **Filler counts are a floor.** Whisper tends to clean up disfluencies. The script prompts it to transcribe verbatim, which helps but does not fix it completely.
- **Boundary vs. mid-clause** is a heuristic based on Whisper's punctuation and a list of clause-starting words. Trust trends over single numbers.
- Targets are practical rules of thumb, not clinical norms. This is a practice tool, not a speech-therapy assessment.

## Privacy

Everything runs locally. No audio leaves your machine. The `.gitignore` excludes recordings, transcripts and logs.

## Tests

```bash
python3 -m unittest discover tests
```

## License

MIT
