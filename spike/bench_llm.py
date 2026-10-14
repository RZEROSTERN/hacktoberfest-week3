"""LLM benchmark through Ollama: chunked notes extraction, then proposal drafting.

Usage:
  uv run python bench_llm.py <model> <transcript.json> <label> [--chunk-seconds 480] [--no-proposal]

<transcript.json> is a list of {"start", "end", "text"} segments (see bench_whisper.py).
Writes $SPIKE_OUT/llm-<label>.json (full outputs + metrics) and appends a summary line to
$SPIKE_OUT/llm_results.jsonl. The Ollama URL comes from POSTCALL_OLLAMA_URL.
"""

import argparse
import json
import os
import re
import threading
import time
from pathlib import Path

import httpx
import psutil
from pydantic import BaseModel, ValidationError

OUT = Path(os.environ["SPIKE_OUT"])
OLLAMA = os.environ["POSTCALL_OLLAMA_URL"]
HERE = Path(__file__).parent
NUM_CTX = 8192

# Things nobody said in the sample call. Hits are reviewed by hand (e.g. "out of scope" mentions).
TRAPS = [
    "whatsapp", "delivery", "a domicilio", "pago en línea", "pagos en línea", "pasarela", "stripe",
    "paypal", "mercado pago", "lealtad", "fidelidad", "inventario", "seo", "app móvil",
    "aplicación móvil", "inglés", "analytics", "analítica", "dominio", "hosting", "alojamiento",
    "wordpress", "react", "laravel", "cfdi", "sat ",
]  # fmt: skip


class Item(BaseModel):
    text: str
    quote: str
    segment_ids: list[int]


class Notes(BaseModel):
    client: str
    client_context: list[Item]
    problem: list[Item]
    goals: list[Item]
    requirements: list[Item]
    constraints: list[Item]
    budget_or_deadlines: list[Item]
    risks: list[Item]
    open_questions: list[str]


class ItemNoQuote(BaseModel):
    text: str
    segment_ids: list[int]


class NotesNoQuote(BaseModel):
    """Same as Notes, but the model does not copy quotes: code looks them up from segment_ids."""

    client: str
    client_context: list[ItemNoQuote]
    problem: list[ItemNoQuote]
    goals: list[ItemNoQuote]
    requirements: list[ItemNoQuote]
    constraints: list[ItemNoQuote]
    budget_or_deadlines: list[ItemNoQuote]
    risks: list[ItemNoQuote]
    open_questions: list[str]


class SourcedItem(BaseModel):
    text: str
    segment_ids: list[int]
    assumption: bool


class Proposal(BaseModel):
    summary: str
    problem_understanding: str
    scope: list[SourcedItem]
    deliverables: list[SourcedItem]
    out_of_scope: list[SourcedItem]
    timeline: str
    open_questions: list[str]
    investment: str
    terms: str


NOTE_LISTS = ["client_context", "problem", "goals", "requirements", "constraints", "budget_or_deadlines", "risks"]
SUMMARY_KEYS = [
    "label", "model", "notes_chunks", "notes_s", "proposal_s", "wall_s", "peak_ollama_rss_mb", "peak_system_growth_mb",
    "notes_check", "proposal_check", "trap_hits", "trap_hits_notes",
]  # fmt: skip


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


class Meter:
    """Samples the summed RSS of every Ollama process while a step runs."""

    def __init__(self) -> None:
        self.peak = 0  # summed RSS of the Ollama server and its runner
        self.peak_system = 0  # peak growth of system-wide used memory (covers GPU/wired memory)
        self._baseline = psutil.virtual_memory().used
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            total = 0
            for p in psutil.process_iter(["name", "exe", "memory_info"]):
                ident = f"{p.info['name']} {p.info['exe']}".lower()
                if ("ollama" in ident or "llama-server" in ident) and p.info["memory_info"]:
                    total += p.info["memory_info"].rss
            self.peak = max(self.peak, total)
            self.peak_system = max(self.peak_system, psutil.virtual_memory().used - self._baseline)
            time.sleep(0.5)

    def __enter__(self) -> "Meter":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()


def chat(client: httpx.Client, model: str, system: str, user: str, schema: dict, stats: list) -> str:
    body = {
        "model": model,
        "stream": False,
        "think": False,
        "format": schema,
        "options": {"temperature": 0, "num_ctx": NUM_CTX, "num_predict": 4000},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }  # fmt: skip
    r = client.post(f"{OLLAMA}/api/chat", json=body)
    if r.status_code == 400 and "think" in r.text.lower():  # model without a thinking switch
        body.pop("think")
        r = client.post(f"{OLLAMA}/api/chat", json=body)
    r.raise_for_status()
    data = r.json()
    stats.append(
        {
            "total_s": data["total_duration"] / 1e9,
            "load_s": data["load_duration"] / 1e9,
            "prompt_tokens": data["prompt_eval_count"],
            "prompt_s": data["prompt_eval_duration"] / 1e9,
            "output_tokens": data["eval_count"],
            "output_s": data["eval_duration"] / 1e9,
            "done_reason": data.get("done_reason"),
        }
    )
    return data["message"]["content"]


def structured(client, model, system, user, model_cls, stats, errors):
    """Validate with Pydantic; retry once, then give up (returns None)."""
    schema = model_cls.model_json_schema()
    prompt = f"{user}\n\nJSON schema of the answer:\n{json.dumps(schema)}"
    for attempt in range(2):
        content = chat(client, model, system, prompt, schema, stats)
        try:
            return model_cls.model_validate_json(content)
        except ValidationError as exc:
            errors.append({"attempt": attempt, "error": str(exc)[:300]})
    return None


def chunk_segments(segments: list[dict], seconds: float) -> list[list[tuple[int, dict]]]:
    chunks: list[list[tuple[int, dict]]] = []
    for i, seg in enumerate(segments):
        if not chunks or seg["start"] - chunks[-1][0][1]["start"] >= seconds:
            chunks.append([])
        chunks[-1].append((i, seg))
    return chunks


def merge_notes(parts: list[Notes]) -> dict:
    merged: dict = {"client": next((p.client for p in parts if p.client), "")}
    for key in NOTE_LISTS:
        seen, items = set(), []
        for p in parts:
            for it in getattr(p, key):
                if norm(it.text) not in seen:
                    seen.add(norm(it.text))
                    items.append(it.model_dump())
        merged[key] = items
    seen_q, questions = set(), []
    for p in parts:
        for q in p.open_questions:
            if norm(q) not in seen_q:
                seen_q.add(norm(q))
                questions.append(q)
    merged["open_questions"] = questions
    return merged


def check_notes(notes: dict, segments: list[dict]) -> dict:
    total = bad_ids = unsourced = quote_ok = 0
    for key in NOTE_LISTS:
        for it in notes[key]:
            total += 1
            ids = it["segment_ids"]
            if not ids:
                unsourced += 1
                continue
            if any(not 0 <= i < len(segments) for i in ids):
                bad_ids += 1
                continue
            source = norm(" ".join(segments[i]["text"] for i in ids))
            quote_ok += "quote" in it and norm(it["quote"]) in source
    return {"items": total, "unsourced": unsourced, "bad_segment_ids": bad_ids, "verbatim_quotes": quote_ok}


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def check_proposal(p: Proposal, n_segments: int, profile_text: str) -> dict:
    items = [*p.scope, *p.deliverables, *p.out_of_scope]
    no_source_not_flagged = [i.text for i in items if not i.segment_ids and not i.assumption]
    bad_ids = [i.text for i in items if any(not 0 <= s < n_segments for s in i.segment_ids)]
    return {
        "summary_has_digit_or_currency": bool(re.search(r"\d|\$|mxn|usd|pesos", p.summary.lower())),
        "items_without_source_not_flagged": no_source_not_flagged,
        "items_with_bad_ids": bad_ids,
        "investment_numbers_not_in_profile": sorted(numbers(p.investment) - numbers(profile_text)),
        "assumption_items": sum(i.assumption for i in items),
        "total_items": len(items),
    }


def trap_hits(text: str) -> list[str]:
    low = text.lower()
    return [t for t in TRAPS if t in low]


def ollama_ps(client: httpx.Client) -> list[dict]:
    return client.get(f"{OLLAMA}/api/ps").json().get("models", [])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("transcript")
    ap.add_argument("label")
    ap.add_argument("--chunk-seconds", type=float, default=480)
    ap.add_argument("--no-proposal", action="store_true")
    ap.add_argument("--timeout", type=float, default=900, help="seconds allowed per Ollama request")
    ap.add_argument("--no-quote", action="store_true", help="notes without model-written quotes (prompt v2)")
    args = ap.parse_args()

    segments = json.loads(Path(args.transcript).read_text())
    profile_text = (HERE / "profile.json").read_text()
    notes_prompt = (HERE / ("prompts/notes_v2.md" if args.no_quote else "prompts/notes_v1.md")).read_text()
    notes_cls = NotesNoQuote if args.no_quote else Notes
    proposal_prompt = (HERE / "prompts/proposal_v0.md").read_text()
    result: dict = {"model": args.model, "label": args.label, "audio_segments": len(segments)}
    errors: list = []

    with httpx.Client(timeout=args.timeout) as client, Meter() as meter:
        wall0 = time.perf_counter()
        note_stats: list = []
        parts = []
        for chunk in chunk_segments(segments, args.chunk_seconds):
            lines = "\n".join(f"[S{i} @ {s['start']:.0f}s] {s['text']}" for i, s in chunk)
            parsed = structured(
                client, args.model, notes_prompt, f"Transcript:\n{lines}", notes_cls, note_stats, errors
            )
            if parsed:
                parts.append(parsed)
        result["notes_chunks"] = len(note_stats)
        notes = merge_notes(parts)
        result["notes_s"] = round(time.perf_counter() - wall0, 1)
        result["notes_check"] = check_notes(notes, segments)
        result["notes"] = notes
        ps = ollama_ps(client)
        result["ollama_ps"] = [{k: m.get(k) for k in ("name", "size", "size_vram", "context_length")} for m in ps]

        if not args.no_proposal:
            t0 = time.perf_counter()
            slim = {k: ([{"text": i["text"], "segment_ids": i["segment_ids"]} for i in v] if k in NOTE_LISTS else v)
                    for k, v in notes.items()}  # fmt: skip
            user = f"Call notes:\n{json.dumps(slim, ensure_ascii=False)}\n\nFreelancer profile:\n{profile_text}"
            prop_stats: list = []
            proposal = structured(
                client, args.model, proposal_prompt.replace("{language}", "es"), user, Proposal, prop_stats, errors
            )
            result["proposal_s"] = round(time.perf_counter() - t0, 1)
            result["proposal_stats"] = prop_stats
            if proposal:
                result["proposal"] = proposal.model_dump()
                result["proposal_check"] = check_proposal(proposal, len(segments), profile_text)
                result["trap_hits"] = trap_hits(json.dumps(result["proposal"], ensure_ascii=False))
        result["wall_s"] = round(time.perf_counter() - wall0, 1)
        client.post(f"{OLLAMA}/api/chat", json={"model": args.model, "keep_alive": 0})  # unload

    result["notes_stats"] = note_stats
    result["trap_hits_notes"] = trap_hits(json.dumps(notes, ensure_ascii=False))
    result["validation_errors"] = errors
    result["peak_ollama_rss_mb"] = round(meter.peak / 1e6)
    result["peak_system_growth_mb"] = round(meter.peak_system / 1e6)
    (OUT / f"llm-{args.label}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
    all_stats = note_stats + result.get("proposal_stats", [])
    summary = {k: result.get(k) for k in SUMMARY_KEYS}
    summary["output_tokens_per_s"] = round(
        sum(s["output_tokens"] for s in all_stats) / max(sum(s["output_s"] for s in all_stats), 1e-9), 1
    )
    summary["validation_errors"] = len(errors)
    summary["ollama_ps"] = result["ollama_ps"]
    with (OUT / "llm_results.jsonl").open("a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
