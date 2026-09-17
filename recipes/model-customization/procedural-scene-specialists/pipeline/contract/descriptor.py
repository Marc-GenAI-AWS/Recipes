"""Derive a host's API surface from its source, instead of describing it by hand.

Every contract bug this project hit was a hand-written description drifting from the code it described: a required
`#define` never mentioned, helpers documented as taking a vec3 that take a vec2, a varying the fragment shader had to
re-declare that the contract implied was free. All three were invisible to the models trained on that host — they had
learned the convention from data — and fatal to a fresh model reading the contract literally.

So the host half of a contract is extracted, not written:

    descriptor("cenote")  ->  HostDescriptor(helpers, uniforms, cur_fields, defines, states, camera, imports)

and rendered into the prompt by contract_text(). A new world then costs an extraction plus a paragraph of intent, and the
description cannot drift from the source because it is generated from it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENES = ROOT / "scenes"   # working-repo layout

GLSL_SIG = re.compile(r"^\s*(float|int|bool|vec[234]|mat[234])\s+(\w+)\s*\(([^)]*)\)", re.M)
GLSL_UNIFORM = re.compile(r"uniform\s+(\w+)\s+(u\w+)")
GLSL_VARYING = re.compile(r"varying\s+(\w+)\s+([\w,\s]+);")
DEFINE_USE = re.compile(r"(?:#if(?:def)?\s+|<\s*)([A-Z][A-Z0-9_]{2,})")
# three.js injects these itself; flagging them would send the model chasing defines it must not set
THREE_BUILTINS = {"USE_INSTANCING", "USE_FOG", "USE_COLOR", "USE_SKINNING", "USE_MORPHTARGETS",
                  "USE_SHADOWMAP", "USE_LOGDEPTHBUF", "USE_UV", "FLIP_SIDED", "DOUBLE_SIDED"}
DEFINE_DECL = re.compile(r"#define\s+([A-Z][A-Z0-9_]+)")
JS_EXPORT_FN = re.compile(r"export\s+(?:function|const)\s+(\w+)")


@dataclass
class HostDescriptor:
    scene: str
    title: str = ""
    states: list[str] = field(default_factory=list)
    helpers: list[tuple[str, str, str]] = field(default_factory=list)      # (ret, name, args)
    uniforms: list[tuple[str, str]] = field(default_factory=list)          # (type, name) declared by the prelude
    published: list[str] = field(default_factory=list)                     # uniforms the host updates per state
    cur_fields: list[str] = field(default_factory=list)                    # ctx.cur members
    cur_types: dict[str, str] = field(default_factory=dict)                # name -> number | vector
    rng: list[str] = field(default_factory=list)                           # ctx.rnd / ctx.rr signatures
    scale: list[str] = field(default_factory=list)                         # world-unit anchors to size against
    varyings: list[tuple[str, str]] = field(default_factory=list)          # provided by the shared vertex shader
    required_defines: list[str] = field(default_factory=list)              # used by the prelude, declared by nobody
    js_helpers: list[str] = field(default_factory=list)                    # e.g. groundH, from field.js
    prelude_exports: list[str] = field(default_factory=list)               # GLSL strings the prelude exports
    export_roles: dict[str, str] = field(default_factory=dict)             # name -> vertex|fragment|snippet|epilogue

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


def _read(p: Path) -> str:
    return p.read_text(errors="ignore") if p.exists() else ""


def _export_bodies(src: str) -> dict[str, str]:
    """Each `export const NAME = ...` body, up to the next export (enough to classify it)."""
    out, hits = {}, list(re.finditer(r"export\s+const\s+(\w+)\s*=", src))
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(src)
        out[m.group(1)] = src[m.end():end]
    return out


def _export_role(body: str) -> str:
    """What kind of GLSL string this is — the thing a model most needs to know and most often gets wrong.

    A prelude mixes whole shaders with snippets meant to be pasted into one. Telling a model to "concatenate into your
    fragmentShader" is right for a snippet and fatal for a complete vertex shader: it redeclares the varyings and gives
    the program two main()s. The distinction is visible in the source, so derive it rather than asserting one rule.
    """
    if re.search(r"\bvoid\s+main\s*\(", body):
        return "vertex" if "gl_Position" in body else "fragment"
    # no main(): either a helper/uniform block, or the tail that closes someone else's main()
    if body.count("}") > body.count("{"):
        return "epilogue"
    return "snippet"


ROLE_NOTE = {
    "vertex": "a COMPLETE vertex shader (it declares its own varyings and its own main()). Pass it as your "
              "`vertexShader` on its own — never paste it into another shader, and never re-declare the varyings "
              "it already declares, or the program fails with \"'vP' : redefinition\".",
    "fragment": "a COMPLETE fragment shader with its own main(). Use it as-is, or read it as a reference — do not "
                "embed it inside a fragment shader of your own.",
    "snippet": "a snippet of uniforms and helper functions, with no main(). Concatenate it into your fragmentShader "
               "BEFORE your own code.",
    "epilogue": "a fragment-shader epilogue that closes main(). Append it as the LAST thing in your fragmentShader, "
                "and do not write your own closing brace after it.",
}


def descriptor(scene: str) -> HostDescriptor:
    d = SCENES / scene
    if not d.exists():
        raise SystemExit(f"no scene at {d}")
    h = HostDescriptor(scene=scene)

    man = _read(d / "manifest.json")
    if man:
        m = json.loads(man)
        h.title = m.get("title", "")
        h.states = list(m.get("states", []))[:24]

    prelude_src = ""
    for name in ("prelude.glsl.js", "prelude.js"):
        if (d / name).exists():
            prelude_src = _read(d / name)
            h.prelude_exports = JS_EXPORT_FN.findall(prelude_src)
            h.export_roles = {n: _export_role(b) for n, b in _export_bodies(prelude_src).items()}
            break

    if prelude_src:
        h.helpers = [(ret, n, args.strip()) for ret, n, args in GLSL_SIG.findall(prelude_src)]
        h.uniforms = sorted(set(GLSL_UNIFORM.findall(prelude_src)))
        declared = set(DEFINE_DECL.findall(prelude_src))
        h.required_defines = sorted({s for s in DEFINE_USE.findall(prelude_src)
                                     if s not in declared and s.isupper() and not s.startswith("GL_")
                                     and s not in THREE_BUILTINS})

    # varyings the shared vertex-shader string hands the fragment shader
    for src in (prelude_src, _read(d / "materials.js"), _read(d / "scene.js")):
        for typ, names in GLSL_VARYING.findall(src):
            for n in [x.strip() for x in names.split(",") if x.strip()]:
                if (typ, n) not in h.varyings:
                    h.varyings.append((typ, n))

    scene_src = _read(d / "scene.js")
    h.published = sorted(set(re.findall(r"U\.(u\w+)", scene_src)))
    h.cur_fields = sorted(set(re.findall(r"cur\.(\w+)", scene_src)))

    # How the host itself moves each cur field into a uniform tells you its type, without trusting a description:
    #   U.uFogTop.value.copy(cur.fogTop)  -> a 3-component value      U.uFogDT.value = cur.fogDT -> a plain number
    # Models that only see the NAME guess, and guess wrong: cur.sunC.r on an array, .setRGB() on a Vector3.
    for name in re.findall(r"U\.u\w+\.value\.(?:copy|set)\(\s*cur\.(\w+)", scene_src):
        h.cur_types[name] = "vector"
    for name in re.findall(r"U\.u\w+\.value\s*=\s*cur\.(\w+)", scene_src):
        h.cur_types.setdefault(name, "number")

    rt = _read(ROOT / "scenes" / "contract" / "runtime.js")
    if re.search(r"\brnd\s*=\s*\(\s*\)\s*=>", rt):
        h.rng.append("rnd()      -> a deterministic pseudo-random number in [0,1). It is a plain function: it has no "
                     "methods, so rnd.anything() throws.")
    if re.search(r"\brr\s*=\s*\(\s*\w+\s*,\s*\w+\s*\)\s*=>", rt):
        h.rng.append("rr(a, b)   -> a deterministic pseudo-random number between a and b.")

    for extra in ("field.js", "materials.js"):
        h.js_helpers += JS_EXPORT_FN.findall(_read(d / extra))
    h.js_helpers = sorted(set(h.js_helpers))

    # Scale anchors. "Make it the right size" is useless without something to measure against, and a layer that is
    # merely too small passes every structural gate while being invisible (measured: a fish layer scored 0.32/0.35/1.45
    # frame-diff against the host's own 1.96/2.44/1.16). Both sources below are already written down, so derive them.
    if man:
        g = json.loads(man).get("groundH") or {}
        if g:
            bits = [f"{g.get('fn', 'the height field')}"]
            if g.get("domain"):
                bits.append(f"domain {g['domain']}")
            if g.get("range"):
                bits.append(f"range {g['range']}")
            h.scale.append(" — ".join(bits))
    for name, val in re.findall(r"export\s+const\s+([A-Z][A-Z0-9_]*)\s*=\s*(-?\d+(?:\.\d+)?)\s*;", _read(d / "field.js")):
        h.scale.append(f"{name} = {val}")
    return h


# ── the invariant: true for every host, so it is written once here rather than per contract ──────
INVARIANT = """Your layer is one ES module that exports a single class. It is constructed once and updated every frame:

  export class <Name> {
    constructor(ctx) { ... }        // build everything here and add it to ctx.scene
    update(dt, t) { ... }           // dt = seconds since last frame, t = seconds since start
  }

  ctx = { THREE, scene, camera, renderer, U, cur, rnd, rr }

RULES THAT HOLD FOR EVERY SCENE:
  - Store what you need: update() receives only (dt, t), so assign `this.ctx = ctx` in the constructor, along with any
    material or geometry you will mutate later. Reading this.ctx without assigning it throws on the first frame.
  - Build in the constructor. Never create geometry, materials or textures inside update() — mutate uniforms instead.
  - Build your material's uniforms with uniformsFor(ctx.U, { ...your own... }) so the shared bag is passed through.
  - A uniform name exists only inside shader source. In JavaScript it is not a variable: reach it as
    `this.uniforms.uMine.value`. Writing `uMine` in a JS function throws "uMine is not defined".
  - Do NOT re-declare anything the host already declares — not in your shader source, and not in your uniformsFor extras.
    A second declaration is a GLSL "redefinition" error.
  - Declare your own varyings in BOTH the vertex and fragment shader, with the same type. A varying the host's vertex
    string provides must still be declared in your fragment shader before you read it.
  - A vec2 has only .x and .y. Only vectors can be swizzled. Match helper argument types exactly.
  - Animate from accumulated time: keep your own accumulator, advance it by dt in update(), and write it into your
    uniform every frame. A uniform nobody updates renders a frozen scene.
  - Assign gl_FragColor as the last statement of the fragment shader. If you never assign it, the surface renders black.
  - Prefer the host's own material helpers over building your own. If the host exports one (listed below), use it for
    every mesh: it carries that world's lighting, fog, palette and per-state response, so your layer sits in the scene
    instead of beside it. Build a raw ShaderMaterial only when the layer genuinely needs its own shading.
  - Size your subject in WORLD UNITS, against this scene's own scale (the constants below). The camera views this world
    from a fixed distance, so a layer whose elements are too small renders as grain, or as nothing at all — and it will
    pass every structural check while being invisible in the frame. Decide what your subject's real-world size is,
    convert it to world units, and sanity-check it against the host's dimensions. If it is a creature or an object with
    a familiar size, say that size in a comment and build to it.
  - Procedural only: no textures, no asset loading, no DOM, no lights, no post-processing passes. Construct every THREE
    class with `new`. Read only the ctx members listed above.
"""


def example_layer(scene: str, layer: str) -> str:
    """A worked layer from ANOTHER host, to show the shape the rules describe.

    Five rounds of adding prose rules to this contract each removed their target failure and were replaced by a new
    one, with the pass rate flat — including a rule that induced its own failure, and a class returning after an
    explicit prohibition against it. Prohibitions describe the boundary of correct code; one correct example shows its
    interior. Deliberately drawn from a different world, so what transfers is the contract and not the content.
    """
    p = SCENES / scene / "layers" / layer
    return _read(p).strip()


def contract_text(scene: str, class_name: str, intent: str, imports: str = "", example: tuple[str, str] | None = None) -> str:
    """The unified contract: the invariant (fixed) + this host's surface (derived) + the segment's intent (written)."""
    h = descriptor(scene)
    L = []
    L.append(f"You are writing ONE layer of a procedural Three.js scene: {h.title or h.scene}.")
    L.append(f"Output a single ES module that exports `class {class_name}`. The rest of the scene is frozen.\n")
    L.append(INVARIANT)
    L.append(f"\n── THIS HOST: {h.scene} ──")
    if h.states:
        shown = ", ".join(h.states[:6]) + (f" (+{len(h.states) - 6} more)" if len(h.states) > 6 else "")
        L.append(f"States the scene cycles through: {shown}. Your layer must read well in all of them.")
    if imports:
        L.append(f"\nImports available:\n{imports}")
    if h.prelude_exports:
        L.append("\nGLSL strings exported by the host prelude. They are NOT interchangeable — each says how it must be "
                 "used:")
        for n in h.prelude_exports:
            L.append(f"    {n:12} {ROLE_NOTE.get(h.export_roles.get(n, 'snippet'))}")
    if h.helpers:
        L.append("\nGLSL helpers available once those strings are concatenated — do NOT redefine them:")
        for ret, n, args in h.helpers:
            L.append(f"    {ret} {n}({args})")
    if h.required_defines:
        L.append(f"\nREQUIRED DEFINES: the prelude uses {', '.join(h.required_defines)} but does not declare them. Your "
                 f"ShaderMaterial must supply them via its `defines` object (a small positive integer), or the shader "
                 f"fails to compile with \"undeclared identifier\".")
    if h.uniforms:
        L.append(f"\nUniforms the prelude already declares, with their GLSL types (read them; never re-declare): "
                 f"{', '.join(f'{t} {n}' for t, n in h.uniforms)}")
    extra_pub = [u for u in h.published if u not in {n for _, n in h.uniforms}]
    if extra_pub:
        L.append(f"Also carried in the shared bag U and updated by the host each state: {', '.join(extra_pub)}")
    if h.uniforms or extra_pub:
        L.append("Those two lists are the COMPLETE set of names in ctx.U. Reading any other name gives undefined, and "
                 "`ctx.U.uSomethingElse.value` throws on the first frame. Do not guess a name from a neighbouring one.")
    if h.varyings:
        L.append(f"\nVaryings the host's vertex string provides: "
                 f"{', '.join(f'{t} {n}' for t, n in h.varyings)} — you must still declare them in your fragment "
                 f"shader before reading them.")
    if h.cur_fields:
        nums = [f for f in h.cur_fields if h.cur_types.get(f) == "number"]
        vecs = [f for f in h.cur_fields if h.cur_types.get(f) == "vector"]
        rest = [f for f in h.cur_fields if f not in h.cur_types]
        L.append("\nPer-state values on ctx.cur, refreshed every frame — read these in update() and push them into your "
                 "own uniforms so the layer changes with the scene's state:")
        if nums:
            L.append(f"    plain numbers:      {', '.join(nums)}")
        if vecs:
            L.append(f"    3-component values: {', '.join(vecs)}  — the host moves these with .copy(), so treat them as "
                     f"[x,y,z]/[r,g,b] data. They are NOT THREE.Color objects: cur.sunC.r is undefined.")
        if rest:
            L.append(f"    also present:       {', '.join(rest)}")
        L.append("    The names above are the COMPLETE contents of ctx.cur. ctx.cur and ctx.U are unrelated bags, not "
                 "two spellings of one thing: do not turn a uniform name into a cur name by dropping its `u`, and do "
                 "not expect every uniform to have a cur counterpart — the host computes some of them from these "
                 "values. Any other name gives undefined, and `.copy(undefined)` throws \"Cannot read properties of "
                 "undefined (reading 'x')\".")
    if h.rng:
        L.append("\nRandomness on ctx (seeded, so renders are reproducible):")
        for line in h.rng:
            L.append(f"    {line}")
    if h.scale:
        L.append("\nSCALE OF THIS WORLD, in world units — size your subject against these, not by eye:")
        for line in h.scale:
            L.append(f"    {line}")
    if h.js_helpers:
        L.append(f"\nJavaScript helpers importable from the host: {', '.join(h.js_helpers)}. These are JS functions, "
                 f"not GLSL — they do not exist inside a shader.")
    if example:
        src = example_layer(*example)
        if src:
            L.append(f"\n── A WORKED LAYER FROM A DIFFERENT SCENE ({example[0]}) ──\n"
                     f"This is a complete, working layer for another world. Its uniforms, helpers and subject are that "
                     f"world's, not yours — copy its SHAPE, never its names. Note how it concatenates the prelude "
                     f"strings, writes its own vertex shader, and stores what update() needs.\n"
                     f"```js\n{src}\n```")
    L.append(f"\n── THIS LAYER ──\n{intent.strip()}")
    L.append("\nOutput ONLY a single ```js fenced ES module. Nothing before or after the fence.")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    scene = sys.argv[1] if len(sys.argv) > 1 else "highpark"
    h = descriptor(scene)
    print(json.dumps(h.as_dict(), indent=2)[:2000])
