"""Convierte los bloques de texto de una sesión de carrera en pasos estructurados.

Sirve para rellenar el campo `steps` del plan (lo que se sube al reloj) a partir
de cómo están escritas las sesiones: "2 km a {E} + 4 rectas", "5x800 m a {I},
recuperando 2' trotando", "2x10' a {T}, recuperando 2' trotando"...
Si un bloque no encaja en ningún patrón, devuelve None: hay que escribir los
pasos a mano (mejor fallar que subir al reloj algo distinto a lo planificado).

Uso:  python3 app/steps_from_text.py data/plans/<plan>.json [--write]
      (sin --write solo muestra lo que generaría)
"""

import json
import re
import sys

NUM = r"(\d+(?:[.,]\d+)?)"
CODE = r"\{(E|M|T|I|R|CUR|RP)\}"


def _f(x):
    return float(x.replace(",", "."))


def _dur(text):
    """"2'30\"" / "1'" / "40 s" / "200 m" → {"time_s": …} o {"dist_m": …}."""
    text = text.strip()
    m = re.match(r"(\d+)'(?:(\d+)\")?", text)
    if m:
        return {"time_s": int(m.group(1)) * 60 + int(m.group(2) or 0)}
    m = re.match(r"(\d+)\"", text)
    if m:
        return {"time_s": int(m.group(1))}
    m = re.match(r"(\d+)\s*s\b", text)
    if m:
        return {"time_s": int(m.group(1))}
    m = re.match(NUM + r"\s*(km|m)\b", text)
    if m:
        v = _f(m.group(1))
        return {"dist_m": v * 1000 if m.group(2) == "km" else v}
    return None


def _strides(n, rest="40 s"):
    return {"type": "repeat", "reps": n, "steps": [
        {"type": "interval", "time_s": 20, "note": "Recta progresiva"},
        {"type": "recovery", **_dur(rest), "note": "Trote o andando"}]}


def parse_piece(piece, kind):
    """Una parte de un bloque → lista de pasos, o None si no se entiende."""
    p = piece.strip().rstrip(".")
    # N rectas (de 20 s ... recuperando 40 s andando)
    m = re.match(r"(\d+)\s+rectas", p)
    if m:
        rest = re.search(r"recuperando\s+(\d+\s*s|\d+'(?:\d+\")?)", p)
        return [_strides(int(m.group(1)), rest.group(1) if rest else "40 s")]
    # N' andando / trotando / trote
    m = re.match(r"(\d+'(?:\d+\")?)\s+(andando|trotando|trote)", p)
    if m:
        return [{"type": "recovery", **_dur(m.group(1)), "note": m.group(2).capitalize()}]
    # NxD (m|km|') a {C}, recuperando R (trotando|andando|trote)
    m = re.match(r"(\d+)x" + r"(\d+(?:[.,]\d+)?\s*(?:km|m)\b|\d+'(?:\d+\")?|\d+\")" + r"\s+a\s+" + CODE +
                 r"(?:,?\s*recuperando\s+(\d+(?:\s*m|'(?:\d+\")?|\s*s)))?\s*(trotando|andando|trote)?", p)
    if m:
        reps, work, code, rest = int(m.group(1)), _dur(m.group(2)), m.group(3), m.group(4)
        inner = [{"type": "interval", **work, "intensity": code}]
        if rest:
            inner.append({"type": "recovery", **_dur(rest), "note": (m.group(5) or "trote").capitalize()})
        return [{"type": "repeat", "reps": reps, "steps": inner}]
    # X' (o X'YY") a {C}  — el atleta entrena por tiempo
    m = re.match(r"(\d+'(?:\d+\")?)\s+a\s+" + CODE, p)
    if m:
        return [{"type": kind, **_dur(m.group(1)), "intensity": m.group(2)}]
    # X km (continuos|muy suaves)? a {C}
    m = re.match(NUM + r"\s*km\b[^{]*?a\s+" + CODE, p)
    if m:
        return [{"type": kind, "dist_m": _f(m.group(1)) * 1000, "intensity": m.group(2)}]
    # X km muy suave / suave (sin código)
    m = re.match(NUM + r"\s*km\s+(muy suave|suave)", p)
    if m:
        return [{"type": kind, "dist_m": _f(m.group(1)) * 1000, "intensity": "E"}]
    # X km a tope (test)
    m = re.match(NUM + r"\s*km\s+a tope", p)
    if m:
        return [{"type": "interval", "dist_m": _f(m.group(1)) * 1000, "note": "A tope"}]
    return None


KIND = {"calentamiento": "warmup", "vuelta a la calma": "cooldown"}


def steps_for(session):
    if session.get("sport") not in ("run", "race"):
        return None
    out = []
    for b in session.get("blocks") or []:
        name = b.get("name", "").lower()
        if name in ("antes",):
            continue
        kind = next((v for k, v in KIND.items() if name.startswith(k)), "interval")
        text = b.get("text", "")
        # El "Test" / carrera: el km 1 con aviso de ritmo, el resto a tope (sin avisos)
        if name in ("test",) and re.match(r"5 km a tope", text):
            out += [{"type": "interval", "dist_m": 1000, "intensity": "CUR", "note": "km 1: controla, no más rápido"},
                    {"type": "interval", "dist_m": 4000, "note": "km 2-5: a tope, regular"}]
            continue
        # Partes separadas por " + ", ", y " o ", 2' trote, "
        pieces = re.split(r"\s\+\s|,\s(?=\d+'\s+trote)|,\s+y\s+|\s+y\s+(?=\d+x)", text)
        for piece in pieces:
            piece = re.sub(r"^\d+'\s+trote,\s*", lambda m_: m_.group(0), piece)
            r = parse_piece(piece, kind)
            if r is None:
                return None
            out += r
    return out or None


def describe(steps, ind=""):
    lines = []
    for s in steps:
        if s["type"] == "repeat":
            lines.append(f"{ind}x{s['reps']}:")
            lines += describe(s["steps"], ind + "   ")
        else:
            d = f"{s['dist_m']/1000:g} km" if s.get("dist_m", 0) >= 1000 else (f"{s['dist_m']:g} m" if s.get("dist_m") else f"{s.get('time_s')} s")
            lines.append(f"{ind}{s['type']} {d} {s.get('intensity') or ''} {s.get('note') or ''}".rstrip())
    return lines


def main():
    path, write = sys.argv[1], "--write" in sys.argv
    plan = json.load(open(path))
    failed = []
    for s in plan["sessions"]:
        if s["sport"] not in ("run", "race") or s.get("steps"):
            continue
        st = steps_for(s)
        if st is None:
            failed.append(f"{s['date']} {s.get('title')}")
            continue
        print(f"{s['date']} {s.get('title')}:")
        print("\n".join("   " + l for l in describe(st)))
        if write:
            s["steps"] = st
    if failed:
        print("\nSIN CONVERTIR (escribir pasos a mano):\n  " + "\n  ".join(failed))
    if write:
        json.dump(plan, open(path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
