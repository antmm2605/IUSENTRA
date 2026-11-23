"""Costruzione della scheda di istituto dalle fonti canoniche del software.

Fonti usate (nessuna nuova verità): le regole dell'harness di Lex (``lex.harness.fattispecie.REGOLE``) eseguite sul
nome dell'istituto, con il controllore anti-invenzione dell'harness (``verifica_analisi`` per le ancore nel testo
vigente, ``citazioni`` per gli articoli citati nel testo libero); le norme di riferimento del catalogo verificate nella
biblioteca; l'indice delle pronunce per norma con il passaggio letto (``dati/passaggi_pronunce.json``); i modelli
d'atto (``pct/template_atti_schede``); il motore dei termini (``pct/termini_processuali``).

Regole di prudenza:
- una sezione senza fonte resta «mancante» con il motivo, mai riempita a parole;
- un testo libero della regola (avvertenze, questioni) entra solo se cita almeno un articolo e TUTTI gli articoli citati
  esistono nell'archivio; si dichiara che la norma è citata ma l'affermazione non è ancorata al testo;
- una pronuncia entra negli orientamenti solo con il passaggio letto; se c'è solo la massima lo si dichiara;
  nessuna classificazione automatica «favorevole/contrario» e nessuna prevalenza (lo decide l'avvocato).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .istituti import DATI, Istituto

PIPELINE = "schede-istituto/1"
RADICE = Path(__file__).resolve().parents[2]
PASSAGGI = DATI / "passaggi_pronunce.json"

# Sezioni della scheda, nell'ordine di lettura dell'avvocato.
SEZIONI: tuple[tuple[str, str], ...] = (
    ("presupposti", "Presupposti"),
    ("eccezioni", "Eccezioni e tranelli"),
    ("termini", "Termini"),
    ("rimedi", "Rimedi e forme"),
    ("giudice_rito", "Giudice e rito"),
    ("prove_oneri", "Prove e oneri"),
    ("documenti", "Documenti e dati da verificare"),
    ("questioni", "Questioni interpretative"),
    ("orientamenti", "Giurisprudenza che cita le norme (orientamenti da valutare)"),
)
ESSENZIALI = ("presupposti", "rimedi", "giudice_rito", "termini")


def impronta(dati: Any) -> str:
    return hashlib.sha256(json.dumps(dati, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------------------------------------------- fonti: norme
def fonte_norma(chiave: str, *, comma: str = "", ancora: str = "") -> dict[str, Any] | None:
    """La norma con la sua versione: testo vigente letto dall'archivio (impronta SHA-256), URL, data di aggiornamento."""
    from lex.harness.norme import NORME, testo_norma

    n = NORME.get(chiave)
    t = testo_norma(chiave) if n else None
    if n is None or t is None:
        return None
    return {"tipo": "norma", "chiave": chiave, "citazione": n.citazione, "rubrica": n.rubrica, "comma": comma,
            "ancora": ancora, "url": t.url, "aggiornamento": t.aggiornamento, "origine": t.origine,
            "vigente": t.vigente, "versione": hashlib.sha256(t.testo.encode()).hexdigest()[:16]}


def _voce_punto(p, provenienza: str) -> dict[str, Any] | None:
    fonti = [fonte_norma(r.chiave, comma=r.comma, ancora=r.ancora) for r in p.rif]
    if not fonti or any(f is None for f in fonti):
        return None
    # Stessa norma citata con più ancore: una sola fonte (la prima ancora porta al passaggio).
    fonti = [f for i, f in enumerate(fonti) if all((g["chiave"], g["comma"]) != (f["chiave"], f["comma"]) for g in fonti[:i])]
    return {"testo": p.testo, "fonti": fonti, "verifica": "ancora letterale trovata nel testo vigente",
            "provenienza": provenienza}


def _voce_testo_libero(testo: str, provenienza: str) -> tuple[dict[str, Any] | None, str]:
    """Testo libero della regola: entra solo se cita norme e tutte esistono nell'archivio."""
    from lex.harness.controllo import citazioni

    trovate = citazioni(testo)
    if not trovate:
        return None, "senza norma citata"
    fonti = []
    for citata, chiave in trovate:
        f = fonte_norma(chiave) if chiave else None
        if f is None:
            return None, f"cita {citata}, non presente nell'archivio delle norme"
        if f not in fonti:
            fonti.append(f)
    return {"testo": testo, "fonti": fonti, "provenienza": provenienza,
            "verifica": "norme citate esistenti nel testo vigente; affermazione non ancorata parola per parola"}, ""


# --------------------------------------------------------------------------------------------- fonti: pronunce
@lru_cache(maxsize=1)
def _passaggi() -> dict[str, Any]:
    try:
        return json.loads(PASSAGGI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def pronunce_per_norma(chiave: str) -> list[dict[str, Any]]:
    return list((_passaggi().get("norme") or {}).get(chiave, []))


# --------------------------------------------------------------------------------------------- regole
@lru_cache(maxsize=1)
def _regole() -> dict[str, Any]:
    from lex.harness.fattispecie import REGOLE

    return {r[0]: r for r in REGOLE}


@lru_cache(maxsize=1)
def _schede_harness() -> dict[str, Any]:
    from lex.harness.fattispecie.materie import SCHEDE

    return {s.regola: s for s in SCHEDE}


@dataclass
class _Esito:
    analisi: Any
    tolte: list[str]
    errore: str = ""


def _esegui_regola(regola: str, testi: list[str], oggi: date) -> _Esito:
    """La regola dell'harness sul nome dell'istituto (o sulla frase d'esempio), poi il controllore delle ancore."""
    from lex.harness.comprensione import Comprensione
    from lex.harness.controllo import verifica_analisi
    from lex.harness.fatti import leggi_fatti

    voce = _regole().get(regola)
    if voce is None:
        return _Esito(None, [], f"regola «{regola}» non presente nell'harness")
    ultimo = ""
    for testo in testi:
        if not testo:
            continue
        try:
            a = voce[2](Comprensione("parere", giuridica=True), leggi_fatti(testo, oggi=oggi))
        except Exception as exc:  # noqa: BLE001 - una regola che chiede fatti concreti non blocca la scheda
            ultimo = f"la regola «{regola}» richiede fatti concreti ({type(exc).__name__})"
            continue
        esito = verifica_analisi(a)
        return _Esito(a, list(esito.affermazioni_tolte))
    return _Esito(None, [], ultimo or f"regola «{regola}» non eseguibile")


# --------------------------------------------------------------------------------------------- strumenti
@lru_cache(maxsize=256)
def _modello_atto(codice: str) -> dict[str, str] | None:
    p = RADICE / "pct" / "template_atti_schede" / f"{codice}.json"
    if not codice or not p.is_file():
        return None
    try:
        dati = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {"tipo": "modello_atto", "id": codice, "titolo": str(dati.get("titolo") or codice),
            "collegamento": f"/template-atti?scheda={codice}"}


def _termine_calcolabile(s, regola: str) -> dict[str, Any] | None:
    fonti = [fonte_norma(r.chiave, comma=r.comma, ancora=r.ancora) for r in s.rif]
    if not fonti or any(f is None for f in fonti):
        return None
    from lex.harness.norme import contiene

    if any(not contiene(r.chiave, r.ancora) for r in s.rif):
        return None
    feriale = "con sospensione feriale" if s.sospensione_feriale and not s.sostanziale else "senza sospensione feriale"
    return {"testo": f"{s.descrizione[:1].upper()}{s.descrizione[1:]} {s.quantita} {s.unita}, con la decorrenza indicata dalla "
                     f"norma citata ({feriale}); la data si calcola dal fatto del fascicolo con il motore dei termini.",
            "fonti": fonti, "verifica": "ancora letterale trovata nel testo vigente", "provenienza": f"regola {regola}",
            "calcolo": {"quantita": s.quantita, "unita": s.unita, "sospensione_feriale": bool(s.sospensione_feriale),
                        "sostanziale": bool(s.sostanziale), "modello_motore": s.modello,
                        "calcolatore": "/scadenziario/calcola-termini"}}


# --------------------------------------------------------------------------------------------- scheda
def _sezione(voci: list[dict[str, Any]], motivo: str) -> dict[str, Any]:
    if voci:
        return {"stato": "compilata", "voci": voci}
    return {"stato": "mancante", "voci": [], "motivo": motivo}


_PROVE = re.compile(r"\bonere\b|\boneri\b|\bprov[ae] (?:del|della|dei|che)\b|\bdeve provare\b|\bpresunzion", re.I)


def _aggiungi(lista: list[dict[str, Any]], voce: dict[str, Any] | None, tutte: dict[str, list] | None = None) -> None:
    """Ogni dato in un solo punto: una voce già presente in un'altra sezione non si ripete; le voci verificate che
    parlano di oneri e prove vanno nella sezione «Prove e oneri»."""
    if not voce:
        return
    if tutte is not None:
        if any(v["testo"] == voce["testo"] for lst in tutte.values() for v in lst):
            return
        if voce.get("verifica", "").startswith("ancora") and _PROVE.search(voce["testo"]):
            lista = tutte["prove_oneri"]
    if all(v["testo"] != voce["testo"] for v in lista):
        lista.append(voce)


def genera_scheda(ist: Istituto, *, oggi: date | None = None) -> dict[str, Any]:
    oggi = oggi or date.today()
    sez: dict[str, list[dict[str, Any]]] = {k: [] for k, _ in SEZIONI}
    lacune: list[str] = []
    strumenti: list[dict[str, Any]] = []
    rimedi_sintesi: list[str] = []
    giudici: list[str] = []
    norme_usate: list[str] = []
    for regola in ist.regole:
        es = _esegui_regola(regola, [ist.nome, ist.frase_esempio], oggi)
        if es.analisi is None:
            lacune.append(es.errore)
            continue
        a = es.analisi
        prov = f"regola {regola}"
        strumenti.append({"tipo": "regola_lex", "id": regola, "titolo": f"Regola di Lex «{regola}»", "collegamento": ""})
        for p in a.competenza + a.rito:
            _aggiungi(sez["giudice_rito"], _voce_punto(p, prov), sez)
        for p in a.termini:
            _aggiungi(sez["termini"], _voce_punto(p, prov), sez)
        for p in a.inquadramento:
            _aggiungi(sez["presupposti"], _voce_punto(p, prov), sez)
        for p in a.procedibilita:
            v = _voce_punto(p, prov)
            if v:
                v["etichetta"] = "Condizione di procedibilità"
            _aggiungi(sez["presupposti"], v, sez)
        for p in a.conclusione:
            _aggiungi(sez["rimedi"], _voce_punto(p, prov), sez)
        if a.conclusione and a.rimedio:
            rimedi_sintesi.append(a.rimedio)
        if (a.competenza or a.rito) and a.giudice:
            giudici.append(a.giudice)
        scheda_h = _schede_harness().get(regola)
        for s in (scheda_h.scadenze if scheda_h else []):
            _aggiungi(sez["termini"], _termine_calcolabile(s, regola), sez)
        for testo in a.avvertenze:
            v, perche = _voce_testo_libero(testo, prov)
            _aggiungi(sez["eccezioni"], v, sez)
            if v is None:
                lacune.append(f"Avvertenza della regola {regola} non riportata ({perche}): «{testo[:140]}»")
        for testo in a.dubbi:
            if testo.startswith("Non affermato perché") or testo.startswith("Vigenza:"):
                continue
            v, perche = _voce_testo_libero(testo, prov)
            _aggiungi(sez["questioni"], v, sez)
            if v is None:
                lacune.append(f"Questione della regola {regola} non riportata ({perche}): «{testo[:140]}»")
        for testo in a.dati_mancanti:
            _aggiungi(sez["documenti"], {"testo": testo, "fonti": [], "provenienza": prov,
                                         "verifica": "dato da raccogliere indicato dalla regola (non è un'affermazione giuridica)"})
        lacune += [f"Affermazione esclusa dal controllore ({regola}): {t}" for t in es.tolte]
        m = _modello_atto(a.modello)
        if m and m not in strumenti:
            strumenti.append(m)
        elif a.modello and not m:
            lacune.append(f"Modello d'atto «{a.modello}» indicato dalla regola ma assente dal catalogo dei modelli.")
    for lista in sez.values():
        for v in lista:
            for f in v["fonti"]:
                if f["chiave"] not in norme_usate:
                    norme_usate.append(f["chiave"])
    if sez["termini"]:
        strumenti.append({"tipo": "calcolatore", "id": "calcola-termini", "titolo": "Calcolo dei termini processuali",
                          "collegamento": "/scadenziario/calcola-termini"})
    if any(c.startswith("dpr115:") for c in norme_usate):
        strumenti.append({"tipo": "calcolatore", "id": "contributo-unificato", "titolo": "Contributo unificato e spese",
                          "collegamento": "/strumenti-legali/"})

    # Norme di riferimento del catalogo dell'istituto: fonti dirette anche senza regola.
    riferimento = []
    for n in ist.norme:
        f = fonte_norma(n.chiave)
        if f is None:
            lacune.append(f"Norma di riferimento {n.citazione or n.chiave} presente in biblioteca ma non nel registro delle "
                          f"norme di Lex: testo non letto dalla scheda.")
            continue
        f["stato_biblioteca"] = n.stato_biblioteca
        riferimento.append(f)
        if n.stato_biblioteca and n.stato_biblioteca != "vigente":
            lacune.append(f"{f['citazione']}: in biblioteca «{n.stato_biblioteca}»; verificare il comma applicabile.")

    # Orientamenti: solo pronunce con il passaggio letto che cita la norma; prima le norme della conclusione.
    for chiave in list(dict.fromkeys([f["chiave"] for v in sez["rimedi"] + sez["presupposti"] for f in v["fonti"]]
                                     + [f["chiave"] for f in riferimento])):
        for p in pronunce_per_norma(chiave):
            if not p.get("passaggio"):
                continue
            voce = {"testo": p["passaggio"], "provenienza": f"pronuncia che cita {p.get('citazione_norma') or chiave}",
                    "verifica": ("massima: fatti e motivazione della decisione non letti" if p.get("tipo_testo") == "massima"
                                 else "passaggio letto nel testo integrale della pronuncia"),
                    "orientamento": "non classificato (lo valuta l'avvocato; nessuna prevalenza automatica)",
                    "fonti": [{"tipo": "pronuncia", "chiave": f"{p['organo']}|{p['numero']}/{p['anno']}",
                               "citazione": p["estremi"], "url": p.get("url", ""), "tipo_testo": p.get("tipo_testo", ""),
                               "data": p.get("data", ""), "versione": p.get("versione", ""), "norma": chiave}]}
            _aggiungi(sez["orientamenti"], voce)
            if p.get("tipo_testo") == "massima":
                lacune.append(f"{p['estremi']}: disponibile solo la massima; fatti e motivazione non letti.")
        if len(sez["orientamenti"]) >= 6:
            break

    motivi = {
        "presupposti": "nessuna regola con inquadramento ancorato al testo vigente",
        "eccezioni": "nessuna avvertenza della regola con norma citata verificata",
        "termini": "nessun termine ancorato al testo vigente nelle regole dell'istituto",
        "rimedi": "nessuna conclusione verificata nelle regole dell'istituto",
        "giudice_rito": "nessun punto su competenza o rito verificato",
        "prove_oneri": "nessuna affermazione su oneri e prove ancorata al testo vigente nelle regole dell'istituto",
        "documenti": "nessun dato da raccogliere indicato dalle regole",
        "questioni": "nessuna questione interpretativa con norma citata verificata",
        "orientamenti": "nessuna pronuncia con il passaggio letto che cita le norme dell'istituto",
    }
    sezioni = {k: _sezione(sez[k], motivi[k]) for k, _ in SEZIONI}
    fonti: dict[str, dict[str, Any]] = {}
    for f in riferimento + [f for s in sezioni.values() for v in s["voci"] for f in v["fonti"]]:
        fonti.setdefault(f["tipo"] + ":" + f["chiave"], {k: v for k, v in f.items() if k not in ("comma", "ancora")})
    mancanti = [titolo for k, titolo in SEZIONI if sezioni[k]["stato"] == "mancante"]
    if mancanti:
        lacune.insert(0, "Sezioni senza fonte: " + ", ".join(mancanti) + ".")
    if not ist.regole:
        lacune.insert(0, "Nessuna regola di Lex per questo istituto: la scheda riporta solo le norme di riferimento.")
    sintesi = _sintesi(ist, rimedi_sintesi, giudici, riferimento)
    contenuto = {"sezioni": sezioni, "fonti": list(fonti.values()), "strumenti": strumenti, "lacune": lacune,
                 "sintesi": sintesi}
    return {
        "id": ist.id_scheda, "istituto": ist.id, "materia": ist.materia, "titolo": ist.nome,
        "regole": list(ist.regole), "pipeline": PIPELINE, **contenuto,
        "fonti_dirette": len(fonti), "sezioni_compilate": len(SEZIONI) - len(mancanti),
        "sezioni_mancanti": mancanti, "stato_verifica": stato_verifica(sezioni, lacune),
        "dipendenze": {k: v.get("versione", "") for k, v in fonti.items()},
        "impronta": impronta(contenuto),
    }


def _sintesi(ist: Istituto, rimedi: list[str], giudici: list[str], riferimento: list[dict[str, Any]]) -> str:
    parti = []
    if rimedi:
        parti.append(rimedi[0].rstrip("."))
    if giudici and giudici[0] not in " ".join(parti):
        parti.append(giudici[0].rstrip("."))
    if parti:
        return "; ".join(parti) + "."
    if riferimento:
        return "Norme di riferimento: " + ", ".join(f["citazione"] for f in riferimento[:4]) + "."
    return "Scheda in attesa di fonti."


def stato_verifica(sezioni: dict[str, Any], lacune: list[str]) -> str:
    """«lacune» se manca una sezione essenziale o un'affermazione è stata esclusa; altrimenti «verificata».
    «da_riesaminare» lo decide la riconvalida, quando cambia una fonte dopo la generazione."""
    if any(sezioni[k]["stato"] == "mancante" for k in ESSENZIALI):
        return "lacune"
    if any(x.startswith("Affermazione esclusa") for x in lacune):
        return "lacune"
    return "verificata"


def testi_ricerca(scheda: dict[str, Any]) -> str:
    """Il testo su cui si cerca (senza embeddings): titolo, materia, sintesi, voci e citazioni delle fonti."""
    parti = [scheda["titolo"], scheda["materia"], scheda.get("sintesi", ""), scheda["istituto"].replace("_", " ")]
    for s in scheda["sezioni"].values():
        for v in s["voci"]:
            parti.append(v["testo"])
    parti += [f.get("citazione", "") + " " + f.get("rubrica", "") for f in scheda["fonti"]]
    return re.sub(r"\s+", " ", " ".join(parti))
