"""Raccoglie gli eventi dalle fonti, tiene quelli nel raggio scelto e scrive app/eventi.json.

Fonti attive:
  - Emilia-Romagna Turismo (open data ufficiale, gratuito, senza chiave)
  - segnalazioni.json (eventi inseriti a mano)
  - Ticketmaster (solo se la variabile d'ambiente TICKETMASTER_KEY e' impostata)

Uso:  python raccogli.py
"""
import html
import json
import math
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
CONFIG = json.loads((CARTELLA / "config.json").read_text(encoding="utf-8"))
OGGI = date.today()
FINE = OGGI + timedelta(days=CONFIG["giorni_avanti"])
UA = {"User-Agent": "RassegnaEventi/0.1 (uso personale)"}


def scarica_testo(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        grezzo = r.read()
        cs = r.headers.get_content_charset()
    for c in [cs, "utf-8", "cp1252"]:
        if not c:
            continue
        try:
            return grezzo.decode(c)
        except (UnicodeDecodeError, LookupError):
            pass
    return grezzo.decode("utf-8", "replace")


def scarica_json(url):
    return json.loads(scarica_testo(url))


# Coordinate dei paesi: si chiedono una volta a OpenStreetMap e si conservano in geocache.json
GEOCACHE_FILE = CARTELLA / "geocache.json"
GEOCACHE = json.loads(GEOCACHE_FILE.read_text(encoding="utf-8")) if GEOCACHE_FILE.exists() else {}


def coordinate(localita):
    k = localita.strip().lower()
    if not k:
        return None
    if k not in GEOCACHE:
        import time
        time.sleep(1.1)  # regola d'uso di OpenStreetMap: al massimo una richiesta al secondo
        # tra i risultati si sceglie il paese o la citta', non la provincia con lo stesso nome
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": localita, "format": "jsonv2", "limit": 8, "countrycodes": "it"})
        try:
            r = scarica_json(url)
            paese = [x for x in r if x.get("addresstype") in ("city", "town", "village", "hamlet", "municipality")]
            scelto = (paese or r or [None])[0]
            GEOCACHE[k] = [float(scelto["lat"]), float(scelto["lon"])] if scelto else None
        except Exception:
            return None  # non si salva: si riprova al prossimo giro
        GEOCACHE_FILE.write_text(json.dumps(GEOCACHE, ensure_ascii=False, indent=0), encoding="utf-8")
    return GEOCACHE[k]


def distanza_km(lat, lng):
    c = CONFIG["centro"]
    r = 6371.0
    p1, p2 = math.radians(c["lat"]), math.radians(lat)
    dp = p2 - p1
    dl = math.radians(lng - c["lng"])
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def pulisci(testo, max_car=280):
    if not testo:
        return ""
    t = re.sub(r"<[^>]+>", " ", testo)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    # le regole di scrittura del workspace escludono le lineette lunghe e medie
    t = t.replace("—", ",").replace("–", "-")
    if len(t) > max_car:
        t = t[:max_car].rsplit(" ", 1)[0] + "..."
    return t


def chiave(titolo, citta):
    t = unicodedata.normalize("NFKD", f"{titolo} {citta}".lower())
    t = re.sub(r"\b(19|20)\d\d\b", "", t)  # "Sagra 2026" e "Sagra" sono lo stesso evento
    return re.sub(r"[^a-z0-9]", "", t)


# ---------------------------------------------------------------- fonti

def fonte_emilia_romagna():
    eventi, pagina = [], 1
    while True:
        url = ("https://emiliaromagnaturismo.it/opendata/v1/events?"
               + urllib.parse.urlencode({"lang": "it", "limit": 100, "page": pagina}))
        d = scarica_json(url)
        for x in d.get("data", []):
            for loc in x.get("locations") or [{}]:
                if loc.get("lat") is None:
                    continue
                img = next((a["url"] for a in x.get("attachments") or [] if a.get("is_primary")), "")
                tick = x.get("ticketing") or {}
                ingresso = tick.get("gratuity") or tick.get("full_rate") or tick.get("entrance") or ""
                eventi.append({
                    "titolo": pulisci(x.get("title"), 140),
                    "sottotitolo": pulisci(x.get("subtitle"), 160),
                    "descrizione": pulisci(x.get("excerpt") or x.get("description")),
                    "categoria": (x.get("category") or [{"name": "Altri eventi"}])[0]["name"],
                    "luogo": pulisci(loc.get("title"), 120),
                    "citta": loc.get("city") or "",
                    "lat": loc["lat"], "lng": loc["lng"],
                    "dal": x["dates"]["from"], "al": x["dates"]["to"] or x["dates"]["from"],
                    "orario": pulisci((x.get("times") or {}).get("friendly_text"), 120),
                    "ingresso": pulisci(ingresso, 80),
                    "link": x.get("permalink") or "",
                    "immagine": img,
                    "fonte": "Emilia-Romagna Turismo",
                })
        if pagina >= d["meta"]["last_page"]:
            break
        pagina += 1
    return eventi


TACCO_PROVINCE = ["parma", "reggio-emilia", "piacenza", "modena", "cremona", "mantova",
                  "brescia", "lodi", "bologna", "la-spezia", "lucca"]
# la pagina generale ("") va per ultima: cosi' un evento gia' trovato in una sezione tiene la sua categoria
TACCO_SEZIONI = ["concerti", "enogastronomia", "mercatini", "spettacoli", "nightlife",
                 "forkids", "sport", "mostre", "jazz", "incontri", ""]
TACCO_CATEGORIE = {"concerti": "Musica", "jazz": "Musica", "enogastronomia": "Eventi enogastronomici",
                   "mercatini": "Mercatini e Mostre Mercato", "spettacoli": "Opera, teatro e danza",
                   "nightlife": "Serate e nightlife", "forkids": "Per bambini", "sport": "Eventi sportivi",
                   "mostre": "Mostre ed Arte", "incontri": "Incontri e libri", "": "Altri eventi"}


def fonte_tacco_di_bacco():
    """Il Tacco di Bacco pubblica nelle pagine i dati degli eventi in formato schema.org.
    Le sue condizioni ammettono l'uso personale e non commerciale."""
    import time
    eventi = []
    for prov in TACCO_PROVINCE:
        for sez in TACCO_SEZIONI:
            url = f"https://iltaccodibacco.it/{prov}/{sez}"
            try:
                pagina = scarica_testo(url)
            except Exception:
                continue
            time.sleep(0.5)
            for blocco in re.findall(r'<script type="application/ld\+json">(.*?)</script>', pagina, re.S):
                try:
                    dati = json.loads(blocco)
                except ValueError:
                    continue
                for x in dati if isinstance(dati, list) else [dati]:
                    if x.get("@type") != "Event" or not x.get("startDate"):
                        continue
                    loc = x.get("location") or {}
                    citta = (loc.get("address") or {}).get("addressLocality") or ""
                    xy = coordinate(citta)
                    if not xy:
                        continue
                    titolo = x.get("name", "")
                    if " | " in titolo:  # "Modena | Titolo" -> "Titolo"
                        titolo = titolo.split(" | ", 1)[1]
                    off = x.get("offers") or {}
                    off = off[0] if isinstance(off, list) and off else off
                    prezzo = off.get("price") if isinstance(off, dict) else None
                    eventi.append({
                        "titolo": pulisci(titolo, 140), "sottotitolo": "",
                        "descrizione": pulisci(x.get("description")),
                        "categoria": TACCO_CATEGORIE.get(sez, "Altri eventi"),
                        "luogo": pulisci(loc.get("name"), 120), "citta": citta,
                        "lat": xy[0], "lng": xy[1],
                        "dal": x["startDate"][:10], "al": (x.get("endDate") or x["startDate"])[:10],
                        "orario": "", "ingresso": ("Gratuito" if str(prezzo) in ("0", "0.00") else ""),
                        "link": x.get("url", ""), "immagine": x.get("image", "") if isinstance(x.get("image"), str) else "",
                        "fonte": "Il Tacco di Bacco",
                    })
    return eventi


def fonte_segnalazioni():
    f = CARTELLA / "segnalazioni.json"
    if not f.exists():
        return []
    out = []
    for x in json.loads(f.read_text(encoding="utf-8")):
        if x.get("_esempio") or not x.get("titolo"):
            continue
        e = {k: v for k, v in x.items() if not k.startswith("_")}
        e.setdefault("al", e.get("dal"))
        e.setdefault("categoria", "Altri eventi")
        e["fonte"] = "Segnalazione"
        out.append(e)
    return out


def fonte_ticketmaster():
    key = os.environ.get("TICKETMASTER_KEY")
    if not key:
        return []
    c = CONFIG["centro"]
    eventi, pagina = [], 0
    while pagina < 5:
        url = "https://app.ticketmaster.com/discovery/v2/events.json?" + urllib.parse.urlencode({
            "apikey": key, "latlong": f"{c['lat']},{c['lng']}", "radius": CONFIG["raggio_km"],
            "unit": "km", "size": 200, "page": pagina, "locale": "*",
            "startDateTime": OGGI.strftime("%Y-%m-%dT00:00:00Z"),
            "endDateTime": FINE.strftime("%Y-%m-%dT23:59:59Z"),
        })
        d = scarica_json(url)
        for x in d.get("_embedded", {}).get("events", []):
            v = (x.get("_embedded", {}).get("venues") or [{}])[0]
            loc = v.get("location") or {}
            if not loc:
                continue
            giorno = x.get("dates", {}).get("start", {}).get("localDate")
            cls = (x.get("classifications") or [{}])[0].get("segment", {}).get("name", "")
            eventi.append({
                "titolo": pulisci(x.get("name"), 140), "sottotitolo": "", "descrizione": "",
                "categoria": {"Music": "Musica", "Sports": "Eventi sportivi",
                              "Arts & Theatre": "Opera, teatro e danza", "Film": "Cinema"}.get(cls, "Altri eventi"),
                "luogo": v.get("name", ""), "citta": v.get("city", {}).get("name", ""),
                "lat": float(loc["latitude"]), "lng": float(loc["longitude"]),
                "dal": giorno, "al": giorno,
                "orario": (x.get("dates", {}).get("start", {}).get("localTime") or "")[:5],
                "ingresso": "", "link": x.get("url", ""),
                "immagine": (x.get("images") or [{}])[0].get("url", ""),
                "fonte": "Ticketmaster",
            })
        if pagina + 1 >= d.get("page", {}).get("totalPages", 0):
            break
        pagina += 1
    return eventi


FONTI = [("Emilia-Romagna Turismo", fonte_emilia_romagna),
         ("Il Tacco di Bacco", fonte_tacco_di_bacco),
         ("Segnalazioni", fonte_segnalazioni),
         ("Ticketmaster", fonte_ticketmaster)]


# ---------------------------------------------------------------- unione

def main():
    tutti, stato = [], {}
    for nome, f in FONTI:
        try:
            ev = f()
            stato[nome] = len(ev)
            tutti.extend(ev)
        except Exception as e:  # una fonte che non risponde non deve fermare le altre
            stato[nome] = f"errore: {e}"
            print(f"[!] {nome}: {e}", file=sys.stderr)

    finali = {}
    for e in tutti:
        try:
            dal = date.fromisoformat(e["dal"])
            al = date.fromisoformat(e["al"] or e["dal"])
            km = distanza_km(float(e["lat"]), float(e["lng"]))
        except (KeyError, TypeError, ValueError):
            continue
        if km > CONFIG["raggio_km"] or al < OGGI or dal > FINE:
            continue
        e["distanza_km"] = round(km, 1)
        e["lungo"] = (al - dal).days >= CONFIG["durata_max_appuntamento_giorni"]
        k = chiave(e["titolo"], e.get("citta", ""))
        if k in finali:  # stesso evento da piu' fonti: si tengono i dati piu' ricchi
            prima = finali[k]
            for campo, val in e.items():
                if val and not prima.get(campo):
                    prima[campo] = val
            if e["fonte"] not in prima["fonte"]:
                prima["fonte"] += ", " + e["fonte"]
        else:
            finali[k] = e

    eventi = sorted(finali.values(), key=lambda e: (max(e["dal"], OGGI.isoformat()), e["distanza_km"]))
    uscita = {
        "aggiornato": datetime.now(timezone.utc).astimezone().strftime("%d/%m/%Y %H:%M"),
        "centro": CONFIG["centro"], "raggio_km": CONFIG["raggio_km"],
        "fonti": stato, "eventi": eventi,
    }
    (CARTELLA / "app" / "eventi.json").write_text(json.dumps(uscita, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Fonti: {stato}")
    print(f"Eventi nel raggio di {CONFIG['raggio_km']} km da {CONFIG['centro']['nome']}, "
          f"prossimi {CONFIG['giorni_avanti']} giorni: {len(eventi)}")


if __name__ == "__main__":
    main()
