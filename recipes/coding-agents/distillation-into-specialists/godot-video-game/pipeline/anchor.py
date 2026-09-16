"""Calibrate the judge's pass bar against a human — the cheapest high-value step here.

    python pipeline/anchor.py build --run sky1 --out runs/anchor1 --n 24
    # open runs/anchor1/anchor.html, click Accept / Reject, copy the line it builds
    python pipeline/anchor.py score --key runs/anchor1/key.json --labels "anchor1 S01P S02F ..."

An LLM judge gives you a ranking for free but not a threshold: where "good enough" sits is
a product decision. Sampling across the judge's own scores and asking a human to label ~24
outputs takes about ten minutes and tells you two things at once — which bar agrees with
the human, and what each bar would do to the size of your training set.

On this project that single exercise moved one part's usable data from 109 examples to 718
and its pass rate from 13% to 80%; without the labels we could not have told a bar change
from a model improvement. Do it once per part, before you spend on data generation.
"""
import argparse
import base64
import io
import json
import random
from pathlib import Path

CSS = """body{font-family:ui-sans-serif,'Segoe UI',Arial,sans-serif;max-width:60rem;margin:0 auto;padding:2rem 1.5rem;
background:#12141a;color:#e9ebef;line-height:1.55}
h1{font-size:1.5rem;margin:0 0 .6rem}.intro{color:#a8b0ba;margin-bottom:2rem}
.item{border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:1.1rem 1.2rem;margin-bottom:1.6rem;background:#181b21}
.id{font-weight:700;color:#e0a458;letter-spacing:.06em}.brief{margin:.5rem 0 .2rem}
.ask{color:#a8b0ba;font-size:.9rem;margin:0 0 .8rem}
.frames{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem}.frames img{width:100%;border-radius:6px;display:block}
.btns{display:flex;gap:.6rem;margin-top:.9rem}
.btns button{font:inherit;font-size:.9rem;font-weight:600;padding:.45rem 1.1rem;border-radius:8px;cursor:pointer;
border:1px solid rgba(255,255,255,.18);background:#20242c;color:#e9ebef}
.btns button.on.accept{background:#2f7d4f;border-color:#2f7d4f;color:#fff}
.btns button.on.reject{background:#9b3b3b;border-color:#9b3b3b;color:#fff}
#bar{position:sticky;bottom:0;margin-top:2rem;background:#0f1116;border:1px solid rgba(255,255,255,.14);
border-radius:12px;padding:.9rem 1.1rem;display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
#line{font-family:ui-monospace,monospace;font-size:.85rem;color:#e0a458;flex:1;word-break:break-all}
#bar button{font:inherit;font-weight:600;padding:.45rem 1rem;border-radius:8px;border:0;background:#e0a458;color:#15161a;cursor:pointer}
#count{color:#a8b0ba;font-size:.85rem}"""

JS = """
const IDS = %s, marks = {};
function mark(id, v, btn) {
  marks[id] = v;
  const item = document.getElementById('item-' + id);
  item.querySelectorAll('.btns button').forEach(b => b.classList.remove('on'));
  btn.classList.add('on'); render();
}
function line() { return '%s ' + IDS.filter(i => marks[i]).map(i => i + marks[i]).join(' '); }
function render() {
  const n = Object.keys(marks).length;
  document.getElementById('count').textContent = n + ' / ' + IDS.length + ' labelled';
  document.getElementById('line').textContent = n ? line() : 'label the items above and the line appears here';
}
function copyLine() { navigator.clipboard.writeText(line()); }
render();
"""


def thumb(path: str, width: int = 420) -> str:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im = im.resize((width, int(im.height * width / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def build(a):
    """Sample across the judge's scores, weighted to the band just under its current bar —
    that band is where the disagreement lives, and it decides the answer."""
    rows = [json.loads(l) for l in (Path("runs") / a.run / "verified.jsonl").open()]
    scored = [r for r in rows if isinstance(r.get("judge"), dict)
              and isinstance(r["judge"].get("overall"), int) and r.get("frames")]
    bar = a.bar
    target = {bar: a.n // 4, bar - 1: a.n // 2, bar - 2: a.n // 4}
    rng = random.Random(a.seed)
    picked = []
    for score, want in target.items():
        pool = [r for r in scored if r["judge"]["overall"] == score]
        rng.shuffle(pool)
        picked += pool[:want]
    rng.shuffle(picked)
    picked = picked[:a.n]
    if not picked:
        raise SystemExit(f"no judged rows with frames in runs/{a.run}/verified.jsonl")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    name = out.name
    key, html = {}, [f"<!DOCTYPE html><meta charset='utf-8'><title>Judge anchor set: {a.run}</title><style>{CSS}</style>",
                     f"<h1>Judge anchor set: {len(picked)} outputs from {a.run}</h1>",
                     "<p class='intro'>For each one, decide whether you would accept it as a good example of its "
                     "brief &mdash; not whether it is perfect. Click Accept or Reject, then copy the line at the "
                     "bottom and pass it to <code>anchor.py score</code>.</p>"]
    for i, r in enumerate(picked, 1):
        sid = f"S{i:02d}"
        b = r.get("brief", {})
        key[sid] = {"candidate": r["candidate"], "judge": r["judge"]["overall"],
                    "judge_pass": bool(r["judge"].get("pass")), "world": b.get("world")}
        frames = "".join(f"<img src='{thumb(f)}' alt='{sid}'>" for f in r["frames"][:3])
        html.append(f"<div class='item' id='item-{sid}'><p class='id'>{sid}</p>"
                    f"<p class='brief'><b>Brief:</b> {b.get('text', '')}</p>"
                    f"<p class='ask'>{a.ask}</p><div class='frames'>{frames}</div>"
                    f"<div class='btns'><button class='accept' onclick=\"mark('{sid}','P',this)\">Accept</button>"
                    f"<button class='reject' onclick=\"mark('{sid}','F',this)\">Reject</button></div></div>")
    html.append("<div id='bar'><span id='count'></span><span id='line'></span>"
                "<button onclick='copyLine()'>Copy line</button></div>"
                f"<script>{JS % (json.dumps(list(key)), name)}</script>")
    (out / "anchor.html").write_text("\n".join(html))
    (out / "key.json").write_text(json.dumps(key, indent=1))
    spread = {}
    for v in key.values():
        spread[v["judge"]] = spread.get(v["judge"], 0) + 1
    print(f"wrote {out / 'anchor.html'} ({len(key)} items, judge scores {dict(sorted(spread.items()))})")
    print("open it, label every item, then run: anchor.py score --key", out / "key.json", '--labels "..."')


def score(a):
    key = json.load(open(a.key))
    marks = {t[:3]: t[3] for t in a.labels.split() if len(t) == 4 and t[3] in "PF"}
    missing = [k for k in key if k not in marks]
    if missing:
        print(f"warning: no label for {', '.join(missing)}")
    accepted = [k for k, v in marks.items() if v == "P"]
    print(f"human accepted {len(accepted)} of {len(marks)} labelled")
    if len(accepted) == len(marks):
        print("NOTE: nothing was rejected, so these labels show the bar is too high but cannot locate "
              "the floor. Prefer the conservative bar, or label a second set that includes weaker output.")
    scores = sorted({v["judge"] for v in key.values()})
    print("\n bar | agrees with the human | judge would pass")
    for bar in reversed(scores):
        agree = sum(1 for sid, v in key.items() if sid in marks and (v["judge"] >= bar) == (marks[sid] == "P"))
        passes = sum(1 for v in key.values() if v["judge"] >= bar)
        print(f"  >={bar} |  {agree:2d}/{len(marks):<2d}               |  {passes:2d}/{len(key)}")
    print("\nSet the winner in SEGMENTS[<part>]['pass_bar'] in pipeline/common.py, then re-score existing "
          "runs for free with: verify.py --rescore (the judge's raw verdicts are already saved).")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="make a labelling page from a verified run")
    b.add_argument("--run", required=True, help="a run directory under runs/ with verified.jsonl")
    b.add_argument("--out", required=True)
    b.add_argument("--n", type=int, default=24)
    b.add_argument("--bar", type=int, default=7, help="the judge's current pass bar")
    b.add_argument("--seed", type=int, default=1)
    b.add_argument("--ask", default="Would you accept this as a good example of the brief?")
    b.set_defaults(func=build)
    s = sub.add_parser("score", help="turn the labels into agreement figures per bar")
    s.add_argument("--key", required=True)
    s.add_argument("--labels", required=True, help='e.g. "anchor1 S01P S02F S03P ..."')
    s.set_defaults(func=score)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
