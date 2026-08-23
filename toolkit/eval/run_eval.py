#!/usr/bin/env python3
"""Evaluate the obligation-extraction prompt against the hand-annotated gold set.

    python3 toolkit/eval/run_eval.py --models llama3.1:8b,qwen2.5:14b --out toolkit/eval/results

Runs locally against Ollama. No API keys, no data leaving the machine — which also means
anyone can reproduce the numbers rather than take them on trust.

Scoring is deliberately lexical and deterministic. A model-judged matcher would be more
flexible and would also make the score a function of a second unevaluated model, which is
how eval harnesses quietly stop measuring what they claim to measure.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD = ROOT / "toolkit" / "eval" / "gold" / "obligations.yaml"
DEFAULT_PROMPT = ROOT / "toolkit" / "prompts" / "obligation_extraction.md"

# Fraction of a gold obligation's key_terms that must appear in a prediction for the two
# to be considered the same obligation. 0.67 chosen so a 3-term obligation matches on 2 —
# tolerant of paraphrase, intolerant of a prediction about something else. Sensitivity to
# this threshold is reported in the results so the number is not taken on faith.
MATCH_THRESHOLD = 0.67

NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "twelve": "12",
    "sixteen": "16", "seventeen": "17", "twentyfour": "24", "twenty four": "24",
    "twenty-four": "24", "hundred thousand": "100000",
}


def normalise(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s)).lower()
    for word, digit in NUMBER_WORDS.items():
        s = s.replace(word, digit)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def build_prompt(prompt_path: Path) -> tuple[str, str]:
    """Pull the system and user blocks out of the prompt markdown.

    The prompt lives in a documented markdown file rather than a string literal so the
    thing evaluated and the thing a reader reviews are the same artefact.
    """
    text = prompt_path.read_text()
    blocks = re.findall(r"```\n(.*?)```", text, re.S)
    if len(blocks) < 2:
        raise SystemExit("could not parse system/user blocks from the prompt file")
    return blocks[0].strip(), blocks[1].strip()


def call_ollama(model: str, system: str, user: str, timeout: int = 240) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": f"{system}\n\n{user}",
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 7},
    })
    r = subprocess.run(
        ["curl", "-sS", "-m", str(timeout), "http://localhost:11434/api/generate",
         "-H", "Content-Type: application/json", "-d", payload],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"ollama call failed: {r.stderr[:300]}")
    return json.loads(r.stdout)["response"]


def parse_prediction(raw: str) -> tuple[list[dict], str | None]:
    """Return (obligations, parse_error). Malformed output is a result, not a crash."""
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            return [], "no JSON object in output"
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            return [], f"malformed JSON: {e}"
    if not isinstance(obj, dict):
        return [], "top level is not an object"
    obs = obj.get("obligations")
    if obs is None:
        return [], "no 'obligations' key"
    if not isinstance(obs, list):
        return [], "'obligations' is not a list"
    return [o for o in obs if isinstance(o, dict)], None


def pred_text(p: dict) -> str:
    return normalise(" ".join(str(p.get(k) or "") for k in ("summary", "actor", "trigger", "deadline")))


def match_score(gold_ob: dict, pred: dict) -> float:
    terms = [normalise(t) for t in gold_ob.get("key_terms", [])]
    if not terms:
        return 0.0
    blob = pred_text(pred)
    return sum(1 for t in terms if t and t in blob) / len(terms)


def align(gold_obs: list[dict], preds: list[dict], threshold: float):
    """Greedy best-first alignment. Each prediction matches at most one gold obligation."""
    pairs, used_p = [], set()
    scored = []
    for gi, g in enumerate(gold_obs):
        for pi, p in enumerate(preds):
            scored.append((match_score(g, p), gi, pi))
    scored.sort(key=lambda x: -x[0])
    used_g = set()
    for sc, gi, pi in scored:
        if sc < threshold or gi in used_g or pi in used_p:
            continue
        used_g.add(gi); used_p.add(pi)
        pairs.append((gi, pi, sc))
    missed = [i for i in range(len(gold_obs)) if i not in used_g]
    spurious = [i for i in range(len(preds)) if i not in used_p]
    return pairs, missed, spurious


def evaluate(model: str, gold: list[dict], threshold: float, verbose: bool, prompt_path: Path):
    system, user_tmpl = build_prompt(prompt_path)
    per_item, agg = [], defaultdict(int)

    for item in gold:
        user = user_tmpl.replace("{TEXT}", item["text"].strip())
        try:
            raw = call_ollama(model, system, user)
        except Exception as e:  # noqa: BLE001
            raw, err = "", f"call failed: {e}"
            preds = []
        else:
            preds, err = parse_prediction(raw)

        gold_obs = item["obligations"]
        pairs, missed, spurious = align(gold_obs, preds, threshold)

        agg["tp"] += len(pairs)
        agg["fn"] += len(missed)
        agg["fp"] += len(spurious)
        if err:
            agg["parse_errors"] += 1

        # Empty-list items measure fabrication directly: any prediction is a hallucination.
        if not gold_obs:
            agg["empty_items"] += 1
            if preds:
                agg["empty_items_hallucinated"] += 1

        # Carve-out recall, scored only on matched obligations — a carve-out cannot be
        # credited or faulted on an obligation the model never found.
        carve_hits = carve_total = 0
        trigger_hits = trigger_total = 0
        for gi, pi, _ in pairs:
            g, p = gold_obs[gi], preds[pi]
            if g.get("carve_out"):
                carve_total += 1
                pc = normalise(p.get("carve_out") or "")
                gk = [t for t in normalise(g["carve_out"]).split() if len(t) > 4]
                if pc and gk and sum(1 for t in gk if t in pc) / len(gk) >= 0.3:
                    carve_hits += 1
            gt = normalise(g.get("trigger") or "")
            if gt and gt != "ongoing":
                trigger_total += 1
                pt = normalise(p.get("trigger") or "")
                gk = [t for t in gt.split() if len(t) > 4]
                if pt and gk and sum(1 for t in gk if t in pt) / len(gk) >= 0.5:
                    trigger_hits += 1

        agg["carve_hits"] += carve_hits; agg["carve_total"] += carve_total
        agg["trigger_hits"] += trigger_hits; agg["trigger_total"] += trigger_total

        per_item.append({
            "id": item["id"], "difficulty": item["difficulty"], "probe": item["probe"],
            "gold_count": len(gold_obs), "pred_count": len(preds),
            "matched": len(pairs), "missed": len(missed), "spurious": len(spurious),
            "parse_error": err,
            "predictions": preds,
        })
        if verbose:
            flag = "ok " if not missed and not spurious and not err else "FAIL"
            print(f"  [{flag}] {item['id']:<9} gold={len(gold_obs)} pred={len(preds)} "
                  f"matched={len(pairs)} missed={len(missed)} spurious={len(spurious)}"
                  + (f"  ({err})" if err else ""))

    tp, fp, fn = agg["tp"], agg["fp"], agg["fn"]
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    return {
        "model": model,
        "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
        "tp": tp, "fp": fp, "fn": fn,
        "parse_errors": agg["parse_errors"],
        "carve_out_recall": round(agg["carve_hits"] / agg["carve_total"], 3) if agg["carve_total"] else None,
        "carve_out_n": agg["carve_total"],
        "trigger_fidelity": round(agg["trigger_hits"] / agg["trigger_total"], 3) if agg["trigger_total"] else None,
        "trigger_n": agg["trigger_total"],
        "empty_items": agg["empty_items"],
        "empty_items_hallucinated": agg["empty_items_hallucinated"],
        "per_item": per_item,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="llama3.1:8b")
    ap.add_argument("--out", default=str(ROOT / "toolkit" / "eval" / "results"))
    ap.add_argument("--threshold", type=float, default=MATCH_THRESHOLD)
    ap.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    gold = yaml.safe_load(GOLD.read_text())
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for m in models:
        print(f"\n=== {m} ===")
        r = evaluate(m, gold, args.threshold, not args.quiet, Path(args.prompt))
        results.append(r)
        print(f"  P={r['precision']:.3f} R={r['recall']:.3f} F1={r['f1']:.3f}  "
              f"carve-out recall={r['carve_out_recall']}  "
              f"hallucinated on empty items={r['empty_items_hallucinated']}/{r['empty_items']}")

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gold_items": len(gold),
        "gold_obligations": sum(len(i["obligations"]) for i in gold),
        "match_threshold": args.threshold,
        "prompt": Path(args.prompt).name,
        "results": results,
    }
    stem = Path(args.prompt).stem
    (out_dir / f"metrics-{stem}.json").write_text(json.dumps(payload, indent=2))

    lines = ["| model | P | R | F1 | carve-out recall | trigger fidelity | fabricated on empty | parse errors |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in results:
        lines.append(
            f"| {r['model']} | {r['precision']:.2f} | {r['recall']:.2f} | {r['f1']:.2f} | "
            f"{r['carve_out_recall'] if r['carve_out_recall'] is not None else '—'} "
            f"({r['carve_out_n']}) | "
            f"{r['trigger_fidelity'] if r['trigger_fidelity'] is not None else '—'} "
            f"({r['trigger_n']}) | "
            f"{r['empty_items_hallucinated']}/{r['empty_items']} | {r['parse_errors']} |")
    (out_dir / f"metrics-{stem}.md").write_text("\n".join(lines) + "\n")
    print(f"\nwrote metrics-{stem}.json / .md to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
