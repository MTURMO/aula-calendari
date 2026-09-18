#!/usr/bin/env python3
"""
Genera docs/aula.ics con los partidos de AE Aula Handbol (Primera Catalana
Sènior Masculina, Grup B, 26/27).

Base: fixtures.json (30 jornadas, rival, local/visitante, pabellón y fecha
provisional). Cada ejecución lee las 30 jornadas de la web de resultados y,
para cada partido de AULA, aplica lo que esté publicado:

  * Partido en casa      -> día de la web, hora fija 19:00
  * Partido fuera        -> día y hora de la web
  * Sin fecha publicada  -> se mantiene el evento provisional (fin de semana
                            para los de fuera, fecha prevista a las 19:00 en casa)

Si la web no responde o cambia de formato, el script termina con error SIN
tocar el calendario publicado (GitHub te avisa por correo del fallo).

Uso:  python update_calendar.py [--html-dir carpeta_con_jornada_N.html]
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
JORNADA_URL = (
    "https://resultadosbalonmano.isquad.es/competicion.php?seleccion=0&id=1038560"
    "&id_ambito=0&id_territorial=17&id_superficie=1&iframe=0&id_categoria=3077"
    "&id_competicion=211807&lang=ca&jornada={j}"
)
HOME_TIME = (19, 0)                 # AULA juega en casa siempre a las 19:00
DURATION = timedelta(minutes=105)   # 19:00 -> 20:45
CAL_NAME = "AE Aula Handbol - Sènior Masculí 26/27"
COMPETITION = "Primera Catalana Sènior Masculina Grup B"
TZID = "Europe/Madrid"

DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")
ID_RE = re.compile(r"id_equipo=(\d+)")


# --------------------------------------------------------------------------
# Lectura de la web
# --------------------------------------------------------------------------
def fetch_html(j, html_dir=None):
    if html_dir:
        return (Path(html_dir) / f"jornada_{j}.html").read_bytes()
    import requests

    headers = {"User-Agent": "Mozilla/5.0 (calendario-aula; uso personal)"}
    last = None
    for attempt in range(3):
        try:
            r = requests.get(JORNADA_URL.format(j=j), headers=headers, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"No se pudo descargar la jornada {j}: {last}")


def parse_jornada(html, opponent_id):
    """Devuelve None si no hay fila AULA-rival; si la hay, {'date','time'}."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        if tr.find("tr"):          # ignora filas que contienen otras tablas
            continue
        ids = {int(x) for a in tr.find_all("a", href=True) for x in ID_RE.findall(a["href"])}
        if AULA_ID in ids and opponent_id in ids:
            text = " ".join(tr.get_text(" ").split())
            m = DATE_RE.search(text)
            if not m:
                return {"date": None, "time": None}
            d = date(int(m[3]), int(m[2]), int(m[1]))
            t = None
            if m[4] is not None:
                t = (int(m[4]), int(m[5]))
                if t == (0, 0):     # 00:00 = "hora sin fijar"
                    t = None
            return {"date": d, "time": t}
    return None


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
    ap.add_argument("--html-dir", help="usar jornada_N.html locales (para pruebas)")
    args = ap.parse_args()

    fixtures = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))
    events, matched, warnings = [], 0, []

    for fx in fixtures:
        j = fx["jornada"]
        try:
            html = fetch_html(j, args.html_dir)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: {e}\nNo se modifica el calendario.", file=sys.stderr)
            return 1
        web = parse_jornada(html, fx["opponent_id"])
        if web is None:
            warnings.append(f"J{j}: no encuentro AULA vs {fx['opponent']} en la web (uso datos base)")
        else:
            matched += 1
        events.append(build_event(fx, web))
        if not args.html_dir:
            time.sleep(1)  # cortesía con el servidor

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
