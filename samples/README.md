# Samples

Role-played, consented discovery calls used to benchmark models and test the pipeline.
Nothing here is real client data.

## What each recording needs

For every recording `NAME.<mp3|m4a|wav|mp4>` there must be a `NAME.facts.json` next to it:

| Field | What it holds |
| --- | --- |
| `key_facts` | What a correct set of call notes must capture: client, problem, goals, requirements, constraints, mentioned budget or deadlines, risks. One short statement each, with an id (`F01`...), a category and an approximate start time in seconds. |
| `expected_open_questions` | Things the call never covered (for example "no budget was mentioned") that the notes and proposal must flag instead of filling in. |
| `must_not_invent` | Traps: things nobody said, so any model output containing them counts as an invented requirement. |
| `uncertain_transcription` | Words the transcript may have wrong, for a person to confirm by ear. |

The benchmark counts how many `key_facts` each model captured (target: at least 90%) and how
many `must_not_invent` items it made up (target: zero). Those two numbers are only as good as
the file, so it must be written from what was actually said, not from what a model produced.

## Optional but useful

- `NAME.reference.txt`: a human-checked transcript of about 1 to 2 minutes. This is the only
  way to measure real transcription word accuracy (word error rate). Without it the
  benchmark can only compare engines against each other.
- A longer recording (about 30 minutes) to test the "30-minute call in under 10 minutes"
  target. Until then the benchmark repeats the short sample to build a 32-minute file, which
  measures speed but not quality.

## Who needs to listen

Someone who was in the call, or who can hear it, has to confirm the facts file once. A model
cannot hear audio: the draft facts here were read from a Whisper transcript, so any
mishearing in the transcript would also be in the facts. If the role-play followed a script
or outline, that is the best source for both `key_facts` and `reference.txt`.

## Current files

| File | State |
| --- | --- |
| `interview.mp3` | 5 min 24 s, Spanish, pizzeria website request. |
| `interview.facts.json` | DRAFT written from the transcript, needs a person to check it. |
