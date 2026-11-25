#!/usr/bin/env python3
"""
Genera docs/aula.ics con los partidos de AE Aula Handbol (Primera Catalana
Sènior Masculina, Grup B, 26/27).

Base: fixtures.json (jornadas, rival, local/visitante, pabellón y fecha
provisional). Cada ejecución lee el calendario completo del grupo en la API de
la web de resultados (json/beta.php, la que usa la web nueva) y, para cada
partido de AULA, aplica lo que esté publicado (campo "confirmada" de la web):

  * Partido en casa      -> día de la web, hora fija 19:00
  * Partido fuera        -> día y hora de la web
  * Sin fecha publicada  -> se mantiene el evento provisional (fin de semana
                            para los de fuera, fecha prevista a las 19:00 en casa)

Si la web no responde o cambia de formato, el script termina con error SIN
tocar el calendario publicado (GitHub te avisa por correo del fallo).

Uso:  python update_calendar.py [--json-file torneo.json]
"""
import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "aula.ics"

AULA_ID = 215497
API_URL = "https://resultadosbalonmano.isquad.es/maqueta/json/beta.php"
TORNEO_ID = 1038560                 # Primera Catalana Sènior Masc. - Grup B
HOME_TIME = (19, 0)                 # AULA juega en casa siempre a las 19:00
DURATION = timedelta(minutes=105)   # 19:00 -> 20:45
CAL_NAME = "AE Aula Handbol - Sènior Masculí 26/27"
COMPETITION = "Primera Catalana Sènior Masculina Grup B"
TZID = "Europe/Madrid"

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2}))?")


# --------------------------------------------------------------------------
# Lectura de la web
# --------------------------------------------------------------------------
def fetch_torneo(json_file=None):
    """Descarga el calendario completo del grupo (todas las jornadas) en una petición."""
    if json_file:
        return json.loads(Path(json_file).read_text(encoding="utf-8"))
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/130.0 Safari/537.36",
        "Referer": "https://resultadosbalonmano.isquad.es/maqueta/",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    }
    last = None
    for attempt in range(3):
        try:
            r = requests.post(API_URL, data={"tipo": "torneo", "id": TORNEO_ID},
                              headers=headers, timeout=60)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict) or "partidos" not in data:
                raise ValueError(f"respuesta sin 'partidos': {r.text[:300]!r}")
            return data
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"No se pudo leer el calendario de la web: {last}")


def parse_web(data):
    """{jornada: {'date','time'}} solo con los partidos de AULA.

    Si la web marca el partido como no confirmado ("confirmada": 0) su fecha es
    provisional y se ignora (se queda el evento provisional), salvo que ya se
    haya jugado. La hora 00:00 equivale a hora sin fijar.
    """
    out = {}
    for p in data["partidos"]:
        if AULA_ID not in (p["l"]["id"], p["v"]["id"]):
            continue
        j = int(p["j"])
        m = DATE_RE.search(p.get("fecha") or "")
        jugado = p.get("estado") == "Finalizado" or p.get("gl") is not None
        if not m or (p.get("confirmada") == 0 and not jugado):
            out[j] = {"opp": {p["l"]["id"], p["v"]["id"]} - {AULA_ID}, "date": None, "time": None}
            continue
        d = date(int(m[1]), int(m[2]), int(m[3]))
        t = None
        if m[4] is not None:
            t = (int(m[4]), int(m[5]))
            if t == (0, 0):
                t = None
        out[j] = {"opp": {p["l"]["id"], p["v"]["id"]} - {AULA_ID}, "date": d, "time": t}
    return out


# --------------------------------------------------------------------------
# Construcción de eventos
# --------------------------------------------------------------------------
def build_event(fx, web):
    j, home = fx["jornada"], fx["home"]
    default = date.fromisoformat(fx["default_date"])
    web_date = web["date"] if web else None
    web_time = web["time"] if web else None
    opp = fx["opponent"]
    summary = f"AULA vs {opp} (Jornada {j})" if home else f"{opp} vs AULA (Jornada {j})"
    kind = "Partit de lliga" if home else "Partit fora de casa"
    head = f"{kind} (Jornada {j}) - {COMPETITION}."

    ev = {"uid": f"aula-handbol-2627-j{j:02d}@aulahandbol", "summary": summary,
          "location": fx["location"]}

    if home:
        d = web_date or default
        ev["start"] = datetime(d.year, d.month, d.day, *HOME_TIME)
        ev["end"] = ev["start"] + DURATION
        if web_date:
            desc = f"{head} Data confirmada a la web de la federació. Hora habitual d'AULA: 19:00-20:45."
            if web_time and web_time != HOME_TIME:
                desc += f" (Atenció: la web indica {web_time[0]:02d}:{web_time[1]:02d}.)"
        else:
            desc = f"{head} Data prevista, pendent de confirmar a la web. Hora habitual d'AULA: 19:00-20:45."
    else:
        if web_date and web_time:
            ev["start"] = datetime(web_date.year, web_date.month, web_date.day, *web_time)
            ev["end"] = ev["start"] + DURATION
            desc = f"{head} Hora confirmada a la web: {web_time[0]:02d}:{web_time[1]:02d} (durada estimada 1h45)."
        elif web_date:
            ev["allday"] = (web_date, web_date + timedelta(days=1))
            desc = f"{head} Dia confirmat ({web_date:%d/%m}), hora encara no publicada."
        else:
            ev["allday"] = (default, default + timedelta(days=2))
            last = default + timedelta(days=1)
            desc = (f"{head} Hora encara no confirmada per la federació; "
                    f"l'esdeveniment ocupa tot el cap de setmana ({default:%d/%m}-{last:%d/%m}).")
    ev["description"] = desc
    return ev


# --------------------------------------------------------------------------
# Escritura ICS (RFC 5545)
# --------------------------------------------------------------------------
def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    """Pliega a 75 octetos sin partir caracteres UTF-8."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        limit = 75 if not out else 74
        if size + n > limit:
            out.append(cur)
            cur, size = ch, n
        else:
            cur += ch
            size += n
    out.append(cur)
    return "\r\n ".join(out)


VTIMEZONE = [
    "BEGIN:VTIMEZONE", f"TZID:{TZID}",
    "BEGIN:STANDARD", "DTSTART:19701025T030000", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100",
    "TZNAME:CET", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
    "BEGIN:DAYLIGHT", "DTSTART:19700329T020000", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200",
    "TZNAME:CEST", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
    "END:VTIMEZONE",
]


def render(events, stamp):
    L = ["BEGIN:VCALENDAR", "VERSION:2.0",
         "PRODID:-//AE Aula Handbol//Calendari Senior Masculi 26-27//CA",
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         f"X-WR-CALNAME:{esc(CAL_NAME)}", f"X-WR-TIMEZONE:{TZID}",
         "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    L += VTIMEZONE
    for e in events:
        L += ["BEGIN:VEVENT", f"UID:{e['uid']}", f"DTSTAMP:{stamp}"]
        if "allday" in e:
            a, b = e["allday"]
            L += [f"DTSTART;VALUE=DATE:{a:%Y%m%d}", f"DTEND;VALUE=DATE:{b:%Y%m%d}"]
        else:
            L += [f"DTSTART;TZID={TZID}:{e['start']:%Y%m%dT%H%M%S}",
                  f"DTEND;TZID={TZID}:{e['end']:%Y%m%dT%H%M%S}"]
        L += [f"SUMMARY:{esc(e['summary'])}", f"LOCATION:{esc(e['location'])}",
              f"DESCRIPTION:{esc(e['description'])}", "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in L) + "\r\n"


def strip_stamp(ics):
    return re.sub(r"^DTSTAMP:.*\r\n", "", ics, flags=re.M)


def starts(ics):
    """{uid: línea DTSTART} para poder mostrar qué ha cambiado."""
    ics = ics.replace("\r\n ", "")
    return dict(re.findall(r"UID:(\S+)\r\nDTSTAMP:\S+\r\n(DTSTART[^\r]*)", ics))


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-file", help="usar un JSON local del torneo (para pruebas)")
    args = ap.parse_args()

    fixtures = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
    events, matched, warnings = [], 0, []

    try:
        web_all = parse_web(fetch_torneo(args.json_file))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}\nNo se modifica el calendario.", file=sys.stderr)
        return 1

    for fx in fixtures:
        j = fx["jornada"]
        web = web_all.get(j)
        if web is not None and fx["opponent_id"] not in web["opp"]:
            warnings.append(f"J{j}: la web tiene otro rival ({sorted(web['opp'])}) y no "
                            f"{fx['opponent']}; revisa fixtures.json (uso datos base)")
            web = None
        elif web is None:
            warnings.append(f"J{j}: no encuentro AULA vs {fx['opponent']} en la web (uso datos base)")
        else:
            matched += 1
        events.append(build_event(fx, web))

    for w in warnings:
        print("AVISO:", w)
    if matched < len(fixtures) // 2:
        print(f"ERROR: solo {matched}/{len(fixtures)} jornadas reconocidas; "
              "posible cambio de formato de la web. No se modifica el calendario.", file=sys.stderr)
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    new = render(events, stamp)
    old = ""
    if OUT.exists():
        with open(OUT, encoding="utf-8", newline="") as f:   # newline="" conserva \r\n
            old = f.read()

    if strip_stamp(new) == strip_stamp(old):
        print(f"Sin cambios ({matched}/{len(fixtures)} jornadas leídas).")
        return 0

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(new)

    o, n = starts(old), starts(new)
    print("Calendario actualizado:")
    for uid in sorted(n):
        if o.get(uid) != n[uid]:
            print(f"  {uid.split('@')[0][-3:].upper()}: {o.get(uid, '(nuevo)')} -> {n[uid]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
