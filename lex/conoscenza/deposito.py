"""Record versionati delle schede di istituto, registro degli eventi append-only e viste Markdown ricostruibili.

Persistenza canonica (conoscenza giuridica comune, nessun dato degli studi), nello storage del prodotto accanto alle
istantanee delle norme di Lex:
- ``dati/schede_istituto.json``: un record per scheda con ID stabile, revisione, data di generazione e dell'ultimo
  controllo, impronta del contenuto, dipendenze ``fonte → versione`` e cronologia compatta delle revisioni;
- ``dati/registro_conoscenza.jsonl``: eventi append-only (generazione, aggiornamento, rinomina, ritiro, controllo),
  con ID deterministico: una ripetizione dello stesso passaggio non duplica gli eventi.

``index.md`` e ``log.md`` (e le pagine per materia e per scheda) sono proiezioni rigenerate da questi due file.
Le annotazioni dell'avvocato NON stanno qui: vivono nel SQL dello studio (``annotazioni``) legate all'ID stabile.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .generatore import PIPELINE, SEZIONI, impronta
from .istituti import DATI, slug

ROMA = ZoneInfo("Europe/Rome")
ARCHIVIO = DATI / "schede_istituto.json"
REGISTRO = DATI / "registro_conoscenza.jsonl"
VISTE = Path(__file__).resolve().parents[2] / "docs" / "memoria-giuridica" / "conoscenza"
STORIA_MASSIMA = 20


def adesso() -> str:
    return datetime.now(ROMA).isoformat(timespec="seconds")


def leggi_archivio(percorso: Path | None = None) -> dict[str, Any]:
    p = percorso or ARCHIVIO
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema": 1, "pipeline": PIPELINE, "schede": {}}


def leggi_registro(percorso: Path | None = None) -> list[dict[str, Any]]:
    p = percorso or REGISTRO
    eventi = []
    try:
        for riga in p.read_text(encoding="utf-8").splitlines():
            if riga.strip():
                eventi.append(json.loads(riga))
    except OSError:
        pass
    return eventi


def _scrivi_atomico(p: Path, testo: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", dir=str(p.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(testo)
    os.replace(tmp, p)


def _evento(operazione: str, scheda: dict[str, Any] | None, ora: str, **dettaglio) -> dict[str, Any]:
    base = {"operazione": operazione, "scheda": scheda["id"] if scheda else "",
            "revisione": scheda.get("revisione") if scheda else None,
            "impronta": scheda.get("impronta", "")[:16] if scheda else "", **dettaglio}
    if operazione == "controllo":
        base["ora"] = ora  # un controllo per passaggio: l'ora lo distingue
    return {"evento_id": impronta(base)[:20], "ts": ora, "materia": scheda.get("materia", "") if scheda else "",
            "titolo": scheda.get("titolo", "") if scheda else "", "esito": "completato", **base}


def _differenze(prima: dict[str, str], dopo: dict[str, str]) -> dict[str, list[str]]:
    return {"cambiate": sorted(k for k in dopo if k in prima and prima[k] != dopo[k]),
            "aggiunte": sorted(k for k in dopo if k not in prima),
            "tolte": sorted(k for k in prima if k not in dopo)}


def aggiorna(nuove: list[dict[str, Any]], *, ora: str | None = None, archivio: Path | None = None,
             registro: Path | None = None) -> dict[str, Any]:
    """Confronta le schede appena generate con quelle registrate e pubblica una revisione coerente.

    - scheda nuova → revisione 1, evento «generazione»;
    - stesso contenuto → resta la revisione, si aggiorna solo «ultimo controllo»;
    - solo il titolo cambia → nuova revisione «rinomina», l'ID (e quindi collegamenti e annotazioni) non cambia;
    - contenuto cambiato → nuova revisione «aggiornamento» con le fonti cambiate (riconvalida);
    - istituto non più nel catalogo → «ritirata», mai cancellata.
    Scrittura atomica dell'archivio; il registro si allunga solo con eventi nuovi.
    """
    ora = ora or adesso()
    dati = leggi_archivio(archivio)
    precedenti: dict[str, Any] = dati.get("schede", {})
    gia = {e["evento_id"] for e in leggi_registro(registro)}
    eventi: list[dict[str, Any]] = []
    risultato: dict[str, Any] = {}
    conteggi = {"generate": 0, "aggiornate": 0, "rinominate": 0, "invariate": 0, "ritirate": 0}
    for s in nuove:
        p = precedenti.get(s["id"])
        rec = dict(s)
        if p is None:
            rec.update(revisione=1, generata_il=ora, ultimo_controllo=ora, storia=[
                {"revisione": 1, "data": ora, "impronta": s["impronta"][:16], "motivo": "prima generazione"}])
            eventi.append(_evento("generazione", rec, ora, fonti=len(s["dipendenze"])))
            conteggi["generate"] += 1
        elif p.get("impronta") == s["impronta"] and p.get("titolo") == s["titolo"] and p.get("materia") == s["materia"] \
                and p.get("stato_ciclo") != "ritirata":
            rec.update(revisione=p["revisione"], generata_il=p["generata_il"], ultimo_controllo=ora,
                       storia=p.get("storia", []))
            conteggi["invariate"] += 1
        else:
            diff = _differenze(p.get("dipendenze", {}), s["dipendenze"])
            solo_nome = p.get("impronta") == s["impronta"]
            operazione = "rinomina" if solo_nome else "aggiornamento"
            if solo_nome:
                motivo = f"titolo o materia cambiati («{p.get('titolo')}» → «{s['titolo']}»); ID invariato"
            elif any(diff.values()):
                motivo = "fonti cambiate: " + ", ".join(diff["cambiate"] + diff["aggiunte"] + diff["tolte"])[:400]
            else:
                motivo = "contenuto delle regole cambiato con le stesse fonti"
            rev = int(p.get("revisione", 0)) + 1
            storia = (p.get("storia", []) + [{"revisione": rev, "data": ora, "impronta": s["impronta"][:16],
                                               "motivo": motivo}])[-STORIA_MASSIMA:]
            rec.update(revisione=rev, generata_il=ora, ultimo_controllo=ora, storia=storia)
            eventi.append(_evento(operazione, rec, ora, revisione_precedente=p.get("revisione"), motivo=motivo, **diff))
            conteggi["rinominate" if solo_nome else "aggiornate"] += 1
        rec["stato_ciclo"] = "attiva"
        risultato[s["id"]] = rec
    for ident, p in precedenti.items():
        if ident in risultato:
            continue
        rec = dict(p)
        if p.get("stato_ciclo") != "ritirata":
            rec.update(stato_ciclo="ritirata", ultimo_controllo=ora)
            eventi.append(_evento("ritiro", rec, ora, motivo="istituto non più nel catalogo; scheda conservata"))
            conteggi["ritirate"] += 1
        risultato[ident] = rec
    eventi.append(_evento("controllo", None, ora, **conteggi, schede=len(nuove)))
    nuovo = {"schema": 1, "pipeline": PIPELINE, "aggiornato_il": ora, "schede": dict(sorted(risultato.items()))}
    _scrivi_atomico(archivio or ARCHIVIO, json.dumps(nuovo, ensure_ascii=False, indent=1) + "\n")
    nuovi_eventi = [e for e in eventi if e["evento_id"] not in gia]
    if nuovi_eventi:
        p_reg = registro or REGISTRO
        p_reg.parent.mkdir(parents=True, exist_ok=True)
        with p_reg.open("a", encoding="utf-8") as f:
            for e in nuovi_eventi:
                f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
    return {"conteggi": conteggi, "eventi": len(nuovi_eventi)}


# --------------------------------------------------------------------------------------------- viste Markdown
_STATI = {"verificata": "verificata", "lacune": "lacune", "da_riesaminare": "da riesaminare"}


def _data_it(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone(ROMA).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return ""


def _riga_indice(s: dict[str, Any], base: str = "") -> str:
    return (f"| `{s['id']}` | [{s['titolo']}]({base}{s['id']}.md) | {s.get('sintesi', '').replace('|', '/')} | "
            f"{s['fonti_dirette']} | {_STATI.get(s['stato_verifica'], s['stato_verifica'])} | "
            f"{s['sezioni_compilate']}/{len(SEZIONI)} | r{s['revisione']} | {_data_it(s['ultimo_controllo'])} |")


_TESTA = ("| ID | Istituto | Sintesi | Fonti dirette | Stato | Sezioni | Revisione | Ultimo controllo |\n"
          "|---|---|---|---:|---|---:|---:|---|")


def pagina_scheda(s: dict[str, Any]) -> str:
    r = [f"# {s['titolo']}", "", f"- ID: `{s['id']}` · materia: {s['materia']} · revisione {s['revisione']} · "
         f"ultimo controllo {_data_it(s['ultimo_controllo'])}",
         f"- Stato: {_STATI.get(s['stato_verifica'], s['stato_verifica'])} · fonti dirette: {s['fonti_dirette']} · "
         f"tipo di pagina: scheda di istituto generata (vista, non fonte primaria)", "", f"**Sintesi.** {s.get('sintesi', '')}", ""]
    for chiave, titolo in SEZIONI:
        sez = s["sezioni"][chiave]
        r.append(f"## {titolo}")
        if sez["stato"] == "mancante":
            r += [f"_Sezione mancante: {sez.get('motivo', '')}._", ""]
            continue
        for v in sez["voci"]:
            fonti = "; ".join((f.get("citazione", "") + (f", comma {f['comma']}" if f.get("comma") else "")) for f in v["fonti"])
            r.append(f"- {v['testo']}" + (f" — _{fonti}_" if fonti else "") + f" ({v['verifica']})")
        r.append("")
    r.append("## Strumenti del software")
    r += [f"- {x['titolo']}" + (f" — `{x['collegamento']}`" if x.get("collegamento") else "") for x in s["strumenti"]] or ["- nessuno"]
    r += ["", "## Limiti e lacune dichiarate"] + [f"- {x}" for x in s["lacune"]] + ["", "## Fonti con versione"]
    for f in s["fonti"]:
        if f["tipo"] == "norma" and f.get("stato") == "abrogata":
            r.append(f"- {f['citazione']} — NORMA ABROGATA ({f.get('nota_abrogazione', '')}), versione `{f.get('versione', '')}` — "
                     f"{f.get('url', '')}")
        elif f["tipo"] == "norma":
            if f.get("nota_commi"):
                r.append(f"- {f['citazione']}, comma {f.get('comma_pertinente', '')} (pertinente): {f['nota_commi']}")
            r.append(f"- {f['citazione']} ({f.get('rubrica', '')}) — testo vigente, aggiornamento archivio "
                     f"{f.get('aggiornamento') or 'n.d.'}, versione `{f.get('versione', '')}` — {f.get('url', '')}")
        else:
            r.append(f"- {f['citazione']} ({f.get('tipo_testo', '')}) — versione `{f.get('versione', '')}` — {f.get('url', '')}")
    if s.get("norme_abrogate"):
        r += ["", "## Norme abrogate (storico, non norme di riferimento)"]
        r += [f"- {a['citazione']}: abrogato dal {a['abrogata_da']}; decorrenza: {a['decorrenza']}; sede vigente: {a['sede_vigente']}"
              + (f" (fonte letta: {a['fonte_letta']})" if a.get("fonte_letta") else "") for a in s["norme_abrogate"]]
    r += ["", "## Cronologia delle revisioni"] + [f"- r{x['revisione']} · {_data_it(x['data'])} · {x['motivo']}"
                                                  for x in s.get("storia", [])]
    return "\n".join(r) + "\n"


def scrivi_viste(materie: list[str], *, cartella: Path | None = None, archivio: Path | None = None,
                 registro: Path | None = None) -> dict[str, int]:
    """index.md generale e per materia, una pagina per scheda, log.md: tutto ricostruito dai record."""
    cartella = cartella or VISTE
    schede = [s for s in leggi_archivio(archivio)["schede"].values() if s.get("stato_ciclo") != "ritirata"]
    per_materia: dict[str, list[dict[str, Any]]] = {}
    for s in schede:
        per_materia.setdefault(s["materia"], []).append(s)
    ordine = [m for m in materie if m in per_materia] + sorted(m for m in per_materia if m not in materie)
    indice = ["# Conoscenza — schede di istituto", "",
              "Catalogo generato dai record di `lex/conoscenza/dati/schede_istituto.json` (vista ricostruibile, non fonte). "
              "Il numero di fonti non misura la correttezza giuridica.", "",
              f"Schede: {len(schede)} in {len(ordine)} materie. Ultimo aggiornamento: "
              f"{_data_it(leggi_archivio(archivio).get('aggiornato_il', ''))}.", ""]
    pagine = 0
    for m in ordine:
        elenco = sorted(per_materia[m], key=lambda x: x["titolo"].lower())
        cart = cartella / slug(m)
        cart.mkdir(parents=True, exist_ok=True)
        testo_m = [f"# {m[:1].upper()}{m[1:]} — schede di istituto", "", _TESTA] + [_riga_indice(s) for s in elenco]
        _scrivi_atomico(cart / "index.md", "\n".join(testo_m) + "\n")
        indice += [f"## [{m[:1].upper()}{m[1:]}]({slug(m)}/index.md)", "", _TESTA] + [_riga_indice(s, f"{slug(m)}/") for s in elenco] + [""]
        for s in elenco:
            _scrivi_atomico(cart / f"{s['id']}.md", pagina_scheda(s))
            pagine += 1
    _scrivi_atomico(cartella / "index.md", "\n".join(indice) + "\n")
    _scrivi_atomico(cartella / "log.md", log_md(leggi_registro(registro)))
    return {"materie": len(ordine), "pagine": pagine}


def log_md(eventi: list[dict[str, Any]]) -> str:
    r = ["# Registro della conoscenza", "",
         "Proiezione di `lex/conoscenza/dati/registro_conoscenza.jsonl` (eventi append-only). "
         "Ultimi eventi: `rg '^## \\[' log.md | tail -5`.", ""]
    for e in eventi:
        titolo = e.get("titolo") or ("passaggio di controllo" if e["operazione"] == "controllo" else "")
        r.append(f"## [{e['ts']}] {e['operazione']} | {titolo}")
        r.append(f"event_id: {e['evento_id']}")
        if e.get("scheda"):
            r.append(f"scheda: {e['scheda']}")
        r.append(f"status: {e.get('esito', '')}")
        if e.get("revisione_precedente") is not None:
            r.append(f"revision: {e['revisione_precedente']} -> {e['revisione']}")
        elif e.get("revisione") is not None:
            r.append(f"revision: {e['revisione']}")
        for k in ("motivo", "generate", "aggiornate", "rinominate", "invariate", "ritirate", "schede", "fonti"):
            if e.get(k) not in (None, "", []):
                r.append(f"{k}: {e[k]}")
        for k in ("cambiate", "aggiunte", "tolte"):
            if e.get(k):
                r.append(f"fonti_{k}: {', '.join(e[k])}")
        r.append("")
    return "\n".join(r)
