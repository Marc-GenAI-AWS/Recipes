"""Render-and-gate harness for generated single-file Three.js simulations.

Used two ways:
  - inside the SageMaker RLVR reward-function Lambda (handler.py)
  - locally, to filter SFT dataset candidates (data-gen/build_sft_dataset.py)

Contract enforced on generated apps (baked into the task prompt template):
  - one self-contained HTML file (CDN import map allowed)
  - states listed in <meta name="states" content="a,b,c">
  - state selectable via URL hash: page.html#state-name

Gates (each contributes partial credit; see gate_score()):
  parses      -> complete HTML document (has </html>), within size limits,
                 and not a degenerate repetition loop
  runs        -> loads in headless Chromium with no uncaught errors  (HARD GATE)
  renders     -> a canvas exists and the first screenshot is not blank/flat
                 with all non-canvas UI hidden (buttons alone must not pass)
  animates    -> same state changes between t1 and t2
  states      -> different states produce different frames

`runs` is a hard gate: if the page throws, only `parses` credit is awarded
even when a canvas got painted. Without this, a page that dies on load with
a black canvas scores the same (0.35) as almost every other failure, and
GRPO sees no gradient between "broken" and "nearly working".

Offline rendering (training on the GB10, no CDN dependence):
  HARNESS_THREE_LOCAL   path to three.module(.min).js, served for the
                        `three` import-map entry
  HARNESS_THREE_ADDONS  path to a copy of three's examples/jsm directory,
                        served for the `three/addons/` import-map entry
"""

from __future__ import annotations

import io
import os
import re
import tempfile
from dataclasses import dataclass, field

from PIL import Image, ImageChops, ImageStat

MAX_HTML_BYTES = 400_000          # generous cap; blocks base64-blob reward hacking
MAX_LINE_REPEATS = 80             # identical normalized lines -> sampling collapse
                                  # (teacher apps max out at 22, gold seastate 39,
                                  # a collapsed Qwen sample had 703)
VIEWPORT = (800, 500)             # small = fast renders inside Lambda budget
MAX_STATES = 3                    # states sampled per evaluation
PAGE_CALL_TIMEOUT_MS = 10_000     # cap for any single Playwright page call
SETTLE_MS = 2_000                 # let the scene establish before shot 1
EVOLVE_MS = 4_000                 # gap before shot 2 (animation check)
BLANK_STDDEV = 4.0                # below this, a frame is "flat"
DIFF_THRESHOLD = 2.0              # mean abs pixel diff to count as "different"

_FENCE_RE = re.compile(r"```(?:html)?\s*\n(.*?)```", re.S)
_HIDE_UI_CSS = "*:not(canvas):not(:has(canvas)){visibility:hidden !important}"


def max_line_repeats(html: str) -> tuple[str, int]:
    """Most frequent line after normalizing identifiers and numbers."""
    counts: dict[str, int] = {}
    for line in html.split("\n"):
        t = line.strip()
        if len(t) < 12:
            continue
        t = re.sub(r"0x[0-9a-fA-F]+|\d+(\.\d+)?", "N", t)
        t = re.sub(r"[A-Za-z_$][\w$]*", "id", t)
        counts[t] = counts.get(t, 0) + 1
    if not counts:
        return "", 0
    top = max(counts, key=counts.get)
    return top, counts[top]


@dataclass
class GateResult:
    gates: dict = field(default_factory=dict)      # name -> bool
    notes: list = field(default_factory=list)      # human-readable diagnostics
    screenshots: dict = field(default_factory=dict)  # state -> [png bytes, png bytes]
    states: list = field(default_factory=list)

    def gate_score(self) -> float:
        """Weighted partial credit in [0, 1]. Later gates imply earlier ones;
        `runs` is a hard gate (see module docstring)."""
        w = {"parses": 0.10, "runs": 0.25, "renders": 0.25,
             "animates": 0.20, "states": 0.20}
        if not self.gates.get("runs"):
            return w["parses"] if self.gates.get("parses") else 0.0
        return sum(w[k] for k, ok in self.gates.items() if ok)


def extract_html(completion: str) -> str | None:
    """Model output may be raw HTML or fenced in markdown."""
    m = _FENCE_RE.search(completion)
    text = (m.group(1) if m else completion).strip()
    return text if "<html" in text.lower() else None


def _stddev(png: bytes) -> float:
    img = Image.open(io.BytesIO(png)).convert("L")
    return ImageStat.Stat(img).stddev[0]


def _mean_diff(png_a: bytes, png_b: bytes) -> float:
    a = Image.open(io.BytesIO(png_a)).convert("L")
    b = Image.open(io.BytesIO(png_b)).convert("L")
    return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]


def _safe_close(browser) -> None:
    """Never let browser teardown raise into the caller (the trainer)."""
    try:
        browser.close()
    except Exception:  # noqa: BLE001
        pass


def render_and_gate(completion: str) -> GateResult:
    res = GateResult()

    html = extract_html(completion)
    if html is None or len(html.encode()) > MAX_HTML_BYTES:
        res.gates["parses"] = False
        res.notes.append("no <html> found or size cap exceeded")
        return res
    if "</html>" not in html.lower():
        # truncated output (hit the token limit); Chromium silently skips an
        # unclosed <script> at EOF, so this would otherwise pass `runs`
        res.gates["parses"] = False
        res.notes.append("incomplete document: no </html> (truncated output)")
        return res
    pattern, reps = max_line_repeats(html)
    if reps > MAX_LINE_REPEATS:
        res.gates["parses"] = False
        res.notes.append(f"degenerate repetition: {reps} near-identical lines ({pattern[:40]!r})")
        return res
    res.gates["parses"] = True

    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "app.html")
        with open(path, "w") as f:
            f.write(html)
        url = f"file://{path}"

        launch_args = ["--enable-unsafe-swiftshader", "--no-sandbox",
                       "--disable-dev-shm-usage"]
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            # Lambda restricts process spawning and mounts / read-only
            launch_args += ["--no-zygote", "--single-process"]
            os.environ.setdefault("HOME", "/tmp")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=os.environ.get("HARNESS_CHROMIUM_PATH") or None,
                args=launch_args,
            )
            page = browser.new_page(
                viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
            # bound EVERY page call (get_attribute, evaluate, screenshot, ...):
            # a page whose JS pegs the main thread otherwise hangs each call for
            # the 30 s default and, if unguarded, raises through the trainer
            page.set_default_timeout(PAGE_CALL_TIMEOUT_MS)

            # offline mode: serve the three.js CDN imports from local copies
            local_three = os.environ.get("HARNESS_THREE_LOCAL")
            if local_three:
                three_src = open(local_three).read()
                page.route(
                    "**/npm/three@*/build/three.module.js",
                    lambda route: route.fulfill(
                        content_type="application/javascript", body=three_src))
            local_addons = os.environ.get("HARNESS_THREE_ADDONS")
            if local_addons:
                def _serve_addon(route):
                    rel = route.request.url.split("/examples/jsm/", 1)[-1].split("?")[0]
                    fp = os.path.normpath(os.path.join(local_addons, rel))
                    if fp.startswith(os.path.abspath(local_addons)) and os.path.isfile(fp):
                        route.fulfill(content_type="application/javascript",
                                      body=open(fp, "rb").read())
                    else:
                        route.fulfill(status=404, body="")
                page.route("**/npm/three@*/examples/jsm/**", _serve_addon)

            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console",
                    lambda m: errors.append(m.text) if m.type == "error" else None)
            # Chromium's console text for a failed fetch omits the URL; record it
            # so reward logs show WHAT the app tried to load (asset, bad addon path)
            failed_urls: list[str] = []
            page.on("response",
                    lambda r: failed_urls.append(f"{r.status} {r.url}") if r.status >= 400 else None)
            page.on("requestfailed",
                    lambda rq: failed_urls.append(f"{rq.failure} {rq.url}"))

            try:
                page.goto(url, wait_until="load", timeout=15_000)
                page.wait_for_timeout(SETTLE_MS)
            except Exception as e:  # noqa: BLE001 — any load failure fails the gate
                res.gates["runs"] = False
                res.notes.append(f"load failed: {e}")
                _safe_close(browser)
                return res

            # ignore benign warnings; fail on real errors
            fatal = [e for e in errors if "favicon" not in e.lower()]
            res.gates["runs"] = not fatal
            if fatal:
                res.notes.append(f"console/page errors: {fatal[:3]}")
                bad = [u for u in failed_urls if "favicon" not in u.lower()]
                if bad:
                    res.notes.append(f"failed resources: {[u[:120] for u in bad[:3]]}")

            try:
                meta = page.get_attribute('meta[name="states"]', "content") or ""
                has_canvas = bool(page.evaluate(
                    "!!document.querySelector('canvas') && document.querySelector('canvas').width > 0"))
            except Exception as e:  # noqa: BLE001 — unresponsive page (JS busy-loop etc.)
                res.gates["runs"] = False
                res.notes.append(f"page unresponsive after load: {type(e).__name__}: {str(e).splitlines()[0][:120]}")
                _safe_close(browser)
                return res
            res.states = [s.strip() for s in meta.split(",") if s.strip()][:MAX_STATES]
            if not res.states:
                res.states = ["default"]
                res.notes.append("no <meta name=states> — contract violation")
            if not has_canvas:
                res.notes.append("no <canvas> in the page after load")

            for state in res.states:
                shots = []
                try:
                    page.goto("about:blank")
                    page.goto(f"{url}#{state}", wait_until="load", timeout=15_000)
                    page.wait_for_timeout(SETTLE_MS)
                    # judge the rendered scene only: hide buttons/captions so a
                    # black canvas behind a bright UI cannot pass `renders`
                    page.add_style_tag(content=_HIDE_UI_CSS)
                    shots.append(page.screenshot())
                    page.wait_for_timeout(EVOLVE_MS)
                    shots.append(page.screenshot())
                except Exception as e:  # noqa: BLE001
                    res.notes.append(f"state {state} failed: {e}")
                res.screenshots[state] = shots

            _safe_close(browser)

    first = [s[0] for s in res.screenshots.values() if s]
    res.gates["renders"] = (has_canvas and bool(first)
                            and all(_stddev(p) > BLANK_STDDEV for p in first))
    if not res.gates["renders"]:
        res.notes.append("blank or flat frames")

    pairs = [s for s in res.screenshots.values() if len(s) == 2]
    res.gates["animates"] = bool(pairs) and all(
        _mean_diff(a, b) > DIFF_THRESHOLD for a, b in pairs)
    if not res.gates["animates"]:
        res.notes.append("scene does not evolve over time")

    if len(first) >= 2:
        res.gates["states"] = all(
            _mean_diff(first[i], first[i + 1]) > DIFF_THRESHOLD
            for i in range(len(first) - 1))
    else:
        res.gates["states"] = False
        res.notes.append("fewer than 2 renderable states")
    if not res.gates.get("states"):
        res.notes.append("states are visually identical")

    return res
