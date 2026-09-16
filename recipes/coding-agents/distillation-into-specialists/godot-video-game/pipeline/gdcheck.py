"""Static checks for GDScript layers, run before Godot loads them. They catch two
mistakes the specialists repeat after seeing Godot's own error, because that
error does not name the fix:

- unknown constants on engine classes (`Environment.AMBIENT_SOURCE_NONE`), with
  the class's valid constants that share the prefix;
- built-in constructors called with a wrong number of arguments
  (`Vector3(x, z)`), with the valid forms.

    from gdcheck import check
    problems = check(code)          # [] when nothing is wrong

Engine constants come from godot_constants.json, dumped from the Godot 4.7.2
binary (ClassDB, inherited constants included). Strings and comments are
blanked before matching, and calls whose parentheses never close are skipped
(the parser reports those).
"""
import json
import re
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent

# built-in Variant constructors: allowed argument counts and the forms, for the message
CONSTRUCTORS = {
    "Vector2": ({0, 1, 2}, "Vector2(), Vector2(from), Vector2(x, y)"),
    "Vector2i": ({0, 1, 2}, "Vector2i(), Vector2i(from), Vector2i(x, y)"),
    "Vector3": ({0, 1, 3}, "Vector3(), Vector3(from), Vector3(x, y, z)"),
    "Vector3i": ({0, 1, 3}, "Vector3i(), Vector3i(from), Vector3i(x, y, z)"),
    "Vector4": ({0, 1, 4}, "Vector4(), Vector4(from), Vector4(x, y, z, w)"),
    "Color": ({0, 1, 2, 3, 4}, "Color(), Color(from | code), Color(from | code, alpha), Color(r, g, b), Color(r, g, b, a)"),
    "Quaternion": ({0, 1, 2, 4}, "Quaternion(), Quaternion(from | basis), Quaternion(axis, angle | arc_from, arc_to), Quaternion(x, y, z, w)"),
    "Basis": ({0, 1, 2, 3}, "Basis(), Basis(from | quaternion), Basis(axis, angle), Basis(x_axis, y_axis, z_axis)"),
    "Transform3D": ({0, 1, 2, 4}, "Transform3D(), Transform3D(from), Transform3D(basis, origin), Transform3D(x_axis, y_axis, z_axis, origin)"),
    "Transform2D": ({0, 1, 2, 3, 4}, "Transform2D(), Transform2D(from), Transform2D(rotation, position), Transform2D(x_axis, y_axis, origin), Transform2D(rotation, scale, skew, position)"),
    "Plane": ({0, 1, 2, 3, 4}, "Plane(), Plane(from | normal), Plane(normal, d | point), Plane(p1, p2, p3), Plane(a, b, c, d)"),
    "AABB": ({0, 1, 2}, "AABB(), AABB(from), AABB(position, size)"),
    "Rect2": ({0, 1, 2, 4}, "Rect2(), Rect2(from), Rect2(position, size), Rect2(x, y, width, height)"),
}
_CTOR_RE = re.compile(r"(?<![\w.])(" + "|".join(sorted(CONSTRUCTORS, key=len, reverse=True)) + r")\s*\(")
_CONST_RE = re.compile(r"(?<![\w.])([A-Z][A-Za-z0-9_]*)\.([A-Z][A-Z0-9_]*)\b(?!\s*\()")


@lru_cache(maxsize=1)
def _classdb() -> dict:
    return json.loads((HERE / "godot_constants.json").read_text())


def _blank(code: str) -> str:
    """Strings and comments replaced by spaces (same length, newlines kept) so
    offsets and line numbers still match the original."""
    out = list(code)
    i, n = 0, len(code)
    while i < n:
        ch = code[i]
        if ch == "#":
            j = code.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif ch in "\"'":
            q = code[i:i + 3] if code[i:i + 3] in ('"""', "'''") else ch
            j = i + len(q)
            while j < n and code[j:j + len(q)] != q:
                j += 2 if code[j] == "\\" else 1
            end = min(n, j + len(q))
            for k in range(i + len(q), min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = end
        else:
            i += 1
    return "".join(out)


def _count_args(text: str, open_idx: int):
    """Number of top-level arguments of the call whose '(' is at open_idx, or None if it never closes."""
    depth, commas, has_content, last_comma = 0, 0, False, False
    for j in range(open_idx, len(text)):
        c = text[j]
        if c in "([{":
            depth += 1
            if depth > 1:
                has_content, last_comma = True, False
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                if not has_content:
                    return 0
                return commas + (0 if last_comma else 1)   # a trailing comma adds no argument
        elif depth == 1 and c == ",":
            commas += 1
            last_comma = True
        elif depth >= 1 and not c.isspace():
            has_content, last_comma = True, False
    return None


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _suggest(name: str, valid: list) -> list:
    parts = name.split("_")
    for k in range(len(parts) - 1, 0, -1):
        prefix = "_".join(parts[:k]) + "_"
        hits = [v for v in valid if v.startswith(prefix)]
        if hits:
            return hits[:12]
    return []


@lru_cache(maxsize=1)
def _project_classes() -> dict:
    """The game's own named classes (not candidates / generated layers):
    class_name -> {"extends": parent name, "consts": const and enum names (enum values included)}."""
    classes = {}
    for f in (HERE.parent / "game").rglob("*.gd"):
        if "candidates" in f.parts or "generated" in f.parts:
            continue
        src = f.read_text(errors="ignore")
        m = re.search(r"^class_name\s+(\w+)", src, re.M)
        if not m:
            continue
        ext = re.search(r"^extends\s+(\w+)", src, re.M)
        consts = set(re.findall(r"^(?:static\s+)?const\s+(\w+)", src, re.M))
        consts |= {n for n in re.findall(r"^(?:static\s+)?var\s+(\w+)", src, re.M) if n.isupper()}
        for em in re.finditer(r"^enum\s+(\w+)?\s*\{([^}]*)\}", src, re.M | re.S):
            if em.group(1):
                consts.add(em.group(1))
            consts.update(v.split("=")[0].strip() for v in em.group(2).split(",") if v.strip())
        classes[m.group(1)] = {"extends": ext.group(1) if ext else None, "consts": consts}
    return classes


def _project_consts(cls: str) -> set:
    """Constants a project class can reach: its own, its project parents', and the engine base's."""
    pc, db, out, seen = _project_classes(), _classdb(), set(), set()
    c = cls
    while c and c not in seen:
        seen.add(c)
        if c in pc:
            out |= pc[c]["consts"]
            c = pc[c]["extends"]
        else:
            if c in db:
                out |= set(db[c]["constants"]) | set(db[c]["enums"])
            break
    return out


def _own_consts(cls: str) -> list:
    """Uppercase names the game's own scripts give a project class and its project parents
    (the engine base's constants, such as Node's CONNECT_*, are noise in a suggestion)."""
    own, pc, c, seen = set(), _project_classes(), cls, set()
    while c in pc and c not in seen:
        seen.add(c)
        own |= pc[c]["consts"]
        c = pc[c]["extends"]
    return sorted(v for v in own if v.isupper())


# C math names the models fall back on from their pretraining. None of these exist in GDScript, and the
# runtime gate reports them as "Function "cosf()" not found in base self", which the 3B then repeated for
# five rounds in the dusk scene (Sep 15) because the message never says what to write instead.
C_FUNCS = {"cosf": "cos", "sinf": "sin", "tanf": "tan", "acosf": "acos", "asinf": "asin", "atanf": "atan",
           "atan2f": "atan2", "sqrtf": "sqrt", "powf": "pow", "expf": "exp", "logf": "log", "log10f": "log",
           "fabsf": "abs", "fabs": "abs", "fmodf": "fmod", "floorf": "floor", "ceilf": "ceil", "roundf": "round",
           "fminf": "min", "fmaxf": "max", "printf": "print"}


def check(code: str) -> list:
    text = _blank(code)
    problems = []
    db = _classdb()
    for m in re.finditer(rf"(?<![\w.])({'|'.join(C_FUNCS)})\s*\(", text):
        name = m.group(1)
        if re.search(rf"\bfunc\s+{name}\b", text):      # the layer defines its own helper with that name
            continue
        problems.append(f"line {_line_of(text, m.start())}: {name}() is C, not GDScript; use {C_FUNCS[name]}()")
    for m in _CONST_RE.finditer(text):
        cls, name = m.group(1), m.group(2)
        line = _line_of(text, m.start())
        if cls in db:
            if name in db[cls]["constants"] or name in db[cls]["enums"]:
                continue
            sug = _suggest(name, db[cls]["constants"])
            hint = f"; valid {cls} constants with that prefix: {', '.join(sug)}" if sug else ""
            problems.append(f"line {line}: {cls}.{name} does not exist in Godot 4.7{hint}")
        elif cls in _project_classes():
            valid = _project_consts(cls)
            if name in valid:
                continue
            own = _own_consts(cls)
            sug = _suggest(name, own) or own[:15]
            hint = f"; {cls} defines: {', '.join(sug)}" if sug else f"; {cls} defines no constants"
            problems.append(f"line {line}: {cls}.{name} does not exist{hint}")
    # uppercase members reached through a context: `sc.CROSSWALK_Z` after `var sc: StreetContext = ctx as
    # StreetContext`, or `(ctx as BeachContext).SAND_COLOR`. An invented one makes Godot report the line's
    # type as uninferable, which hides the real mistake (overnight scene demo, Sep 14).
    pc = _project_classes()
    ctx_vars = {"ctx": "WorldContext"} if "WorldContext" in pc else {}
    for m in re.finditer(r"\bvar\s+(\w+)\s*(?::\s*\w+\s*)?:?=\s*(?:self\.)?ctx\s+as\s+(\w+)", text):
        if m.group(2) in pc:
            ctx_vars[m.group(1)] = m.group(2)
    accesses = []
    if ctx_vars:
        names = "|".join(re.escape(v) for v in ctx_vars)
        accesses += [(m.start(), f"{m.group(1)}.{m.group(2)}", ctx_vars[m.group(1)], m.group(2))
                     for m in re.finditer(rf"(?<![\w.])({names})\.([A-Z][A-Z0-9_]*)\b(?!\s*\()", text)]
    accesses += [(m.start(), f"(ctx as {m.group(1)}).{m.group(2)}", m.group(1), m.group(2))
                 for m in re.finditer(r"\(\s*(?:self\.)?ctx\s+as\s+(\w+)\s*\)\.([A-Z][A-Z0-9_]*)\b(?!\s*\()", text)
                 if m.group(1) in pc]
    for pos, expr, cls, name in accesses:
        if name in _project_consts(cls):
            continue
        own = _own_consts(cls)
        sug = _suggest(name, own) or own[:15]
        hint = f"; {cls} defines: {', '.join(sug)}" if sug else f"; {cls} defines no constants"
        problems.append(f"line {_line_of(text, pos)}: {expr} does not exist on {cls}{hint}")
    for m in _CTOR_RE.finditer(text):
        typ = m.group(1)
        n = _count_args(text, m.end() - 1)
        allowed, forms = CONSTRUCTORS[typ]
        if n is None or n in allowed:
            continue
        snippet = code[m.start():m.start() + 60].splitlines()[0]
        problems.append(f"line {_line_of(text, m.start())}: {typ} has no constructor taking {n} arguments "
                        f"(valid: {forms}): {snippet}")
    return list(dict.fromkeys(problems))
