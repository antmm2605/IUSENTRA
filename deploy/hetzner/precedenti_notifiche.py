"""Precedenti di notifica dello studio (L. 53/1994 art. 3-bis), eseguito DENTRO il container app. Sola lettura.

Legge dal presidio PEC (pec_audit.sqlite, aperto in sola lettura) le PEC di notificazione inviate dallo studio
e le loro ricevute (accettazione, avvenuta consegna, mancata consegna) e le aggrega per:

    materia del fascicolo × tipo di atto notificato × categoria della controparte → categoria del domicilio usato

Stampa SOLO conteggi e categorie: mai nomi, indirizzi PEC completi, codici fiscali o identificativi di fascicolo.
I domini PEC escono solo come categoria («avvocaturastato», «pec.istruzione.it», «pec ordine avvocati»…).

Con ``cat pct/notifiche_l53_collegamento/daticert.py pct/notifiche_l53_collegamento/regola.py`` davanti, simula in
memoria (senza scrivere) il collegamento certo delle notifiche al fascicolo e la rilettura del daticert.

Uso sul server:
    cat pct/notifiche_l53_collegamento/{daticert,relata,regola}.py deploy/hetzner/precedenti_notifiche.py | docker exec -i iusentra-app python -
"""

import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

MARCATORE = "PRECEDENTI_NOTIFICHE_JSON:"
_L53 = re.compile(r"notificazione\s+ai\s+sensi\s+della\s+legge\s+n\.?\s*53|\[notifica_id:", re.IGNORECASE)
_SCUOLA = re.compile(r"\b(?:istituto\s+(?:comprensivo|d['’]istruzione|di\s+istruzione|superiore|tecnico|professionale|statale|magistrale|omnicomprensivo)"
                     r"|liceo|circolo\s+didattico|scuola|convitto|educandato|direzione\s+didattica|i\.\s?c\.|i\.\s?i\.\s?s\.|cpia)\b", re.IGNORECASE)
_STATALE = re.compile(r"\b(?:ministero|ministro|m\.?i\.?u\.?r|m\.?i\.?m\b|presidenza\s+del\s+consiglio|prefettura|questura|ufficio\s+scolastico|"
                      r"agenzia\s+del\s+demanio|agenzia\s+delle\s+entrate|avvocatura)\b", re.IGNORECASE)
_PA = re.compile(r"\b(?:comune|regione|provincia|citt[aà]\s+metropolitana|inps|inail|azienda\s+sanitaria|asl|asp|universit[aà]|agenzia|istituto|autorit[aà])\b", re.IGNORECASE)
_ATTI = (
    ("decreto_ingiuntivo", re.compile(r"decreto.{0,12}ingiunt|\bd\.?\s?i\.?\b|ingiunzione", re.IGNORECASE)),
    ("sentenza", re.compile(r"sentenz", re.IGNORECASE)),
    ("ordinanza", re.compile(r"ordinanz", re.IGNORECASE)),
    ("decreto", re.compile(r"decret", re.IGNORECASE)),
    ("ricorso", re.compile(r"ricors", re.IGNORECASE)),
    ("atto_di_citazione", re.compile(r"citazion", re.IGNORECASE)),
    ("appello", re.compile(r"appell", re.IGNORECASE)),
    ("precetto", re.compile(r"precett", re.IGNORECASE)),
    ("pignoramento", re.compile(r"pignorament", re.IGNORECASE)),
)


def categoria_controparte(nome: str) -> str:
    testo = " ".join(str(nome or "").split())
    if not testo:
        return "non_indicata"
    if _SCUOLA.search(testo) and not re.search(r"paritari|privat|s\.?r\.?l|s\.?p\.?a|onlus|cooperativ", testo, re.IGNORECASE):
        return "istituto_scolastico_statale" + ("_con_ministero" if _STATALE.search(testo) else "")
    if _STATALE.search(testo):
        return "amministrazione_statale"
    if _PA.search(testo):
        return "ente_pubblico_non_statale"
    return "parte_privata"


def categoria_dominio(indirizzo: str) -> str:
    dominio = str(indirizzo or "").rsplit("@", 1)[-1].strip().strip(">").casefold()
    if not dominio or "@" not in str(indirizzo or ""):
        return "non_letto"
    if dominio.endswith("avvocaturastato.it"):
        return "avvocaturastato"
    if dominio.endswith("pec.istruzione.it"):
        return "pec.istruzione.it (scuole)"
    if dominio.endswith("istruzione.it"):
        return "postacert.istruzione.it (ministero/USR)"
    if "giustizia" in dominio:
        return "ufficio giudiziario"
    if "avvocat" in dominio or "ordineavv" in dominio or "cert.legalmail" in dominio or "pec.ordine" in dominio:
        return "pec ordine avvocati"
    if dominio.endswith("gov.it") or re.search(r"comune|regione|provincia|inps|inail|asl|asp|unive|uni\w*\.it", dominio):
        return "pa altra"
    if re.search(r"legalmail|arubapec|pec\.it|postecert|pecimprese|registerpec|sicurezzapostale|cgn|pec\.", dominio):
        return "pec gestore commerciale"
    return "altro"


def tipo_atto(nomi: list[str]) -> str:
    testo = " ".join(n for n in nomi if not re.search(r"relata|procura|daticert|smime|postacert|attestazion", n, re.IGNORECASE))
    for etichetta, schema in _ATTI:
        if schema.search(testo):
            return etichetta
    return "non_determinato"


def _tipo_ricevuta(valore: str, oggetto: str) -> str:
    v = str(valore or "").casefold().replace("_", "-")
    o = str(oggetto or "").casefold()
    if "errore" in v or "non-accett" in v or "mancata" in v or o.startswith(("avviso di mancata", "avviso di non accettazione")):
        return "mancata"
    if "consegna" in v or o.startswith("consegna"):
        return "consegna"
    if "accettazione" in v or o.startswith("accettazione"):
        return "accettazione"
    return ""


def _db_ro(percorso: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _messaggi(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    righe = conn.execute(
        """
        SELECT m.id, m.folder, m.mime_sha256, m.message_id_header AS mid_header, COALESCE(NULLIF(m.linked_fascicolo_id, ''), (SELECT l.fascicolo_id FROM pec_fascicolo_links l WHERE l.message_id = m.id AND l.fascicolo_id != '' ORDER BY l.created_at DESC, l.rowid DESC LIMIT 1), (SELECT d.fascicolo_id FROM pec_fascicolo_documenti_messaggi d WHERE d.message_id = m.id AND d.fascicolo_id != '' LIMIT 1), '') AS linked_fascicolo_id, m.received_at, p.parsed_json
        FROM pec_messages m JOIN pec_parsed_versions p ON p.message_id = m.id
        WHERE p.version = (SELECT MAX(version) FROM pec_parsed_versions WHERE message_id = m.id)
          AND (p.parsed_json LIKE '%legge n. 53%' OR p.parsed_json LIKE '%legge n.53%' OR p.parsed_json LIKE '%otifica_ID%')
        """
    ).fetchall()
    esito = []
    for riga in righe:
        try:
            parsed = json.loads(riga["parsed_json"] or "{}")
        except ValueError:
            continue
        intest = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
        oggetto = str(intest.get("subject") or "")
        if not _L53.search(oggetto):
            continue
        ricevuta = parsed.get("pec_receipt") if isinstance(parsed.get("pec_receipt"), dict) else {}
        destinatari = intest.get("to") or []
        esito.append({
            "id": riga["id"],
            "sha256": str(riga["mime_sha256"] or ""),
            "parsed": parsed,
            "cartella": str(riga["folder"] or "").casefold(),
            "fascicolo": str(riga["linked_fascicolo_id"] or ""),
            "anno": str(riga["received_at"] or "")[:4],
            "oggetto": oggetto,
            "ricevuta": _tipo_ricevuta(str(ricevuta.get("type") or ""), oggetto),
            "originale": str(ricevuta.get("original_message_id") or "").strip("<>").casefold(),
            "indirizzo": str(ricevuta.get("recipient_address") or ""),
            "message_id": str(riga["mid_header"] or intest.get("message_id") or "").strip("<>").casefold(),
            "a": destinatari if isinstance(destinatari, list) else [str(destinatari)],
            "allegati": [str(a.get("filename") or "") for a in parsed.get("attachments") or [] if isinstance(a, dict)],
        })
    return esito


def _fascicoli(paths: dict[str, Any]) -> tuple[dict[str, dict[str, str]], list[Any]]:
    from pct.pec_fascicolo_documenti.flusso import _gestione_fascicoli
    from web.services.pec_pipeline_runtime import repository_from_paths

    gestione = _gestione_fascicoli(repository_from_paths(paths, tenant_label="lettura"))
    esito = {}
    oggetti = list(gestione.tutti(archiviati=True))
    for f in oggetti:
        tipo = getattr(getattr(f, "tipo", ""), "value", getattr(f, "tipo", ""))
        esito[str(f.id)] = {"materia": str(tipo or "non_indicata").lower(), "controparte": categoria_controparte(getattr(f, "controparte", ""))}
    return esito, oggetti


def _simula_collegamento(conn: sqlite3.Connection, messaggi: list[dict[str, Any]], oggetti: list[Any]) -> dict[str, Any]:
    """Collegamento certo e rilettura del daticert in memoria (regola concatenata davanti allo script)."""
    if "collega_tutti" not in globals():
        return {"simulazione": "regola_non_caricata"}
    from pct.pec_collegamento_certo import STATO_CERTO, cerca_collegamento_certo

    impronte: dict[str, set] = {}
    mids: dict[str, set] = {}
    for f in oggetti:
        for d in getattr(f, "documenti", []) or []:
            if str(getattr(d, "nome", "") or "").casefold().endswith(".eml"):
                for campo in ("hash_sha256", "hash_contenuto_sha256"):
                    if getattr(d, campo, ""):
                        impronte.setdefault(str(getattr(d, campo)).casefold(), set()).add(str(f.id))
    try:
        for r in conn.execute("SELECT fascicolo_id, sha256, message_id_header FROM pec_fascicolo_documenti WHERE documento_id<>'' AND lower(nome_originale) LIKE '%.eml'"):
            if r["sha256"]:
                impronte.setdefault(str(r["sha256"]).casefold(), set()).add(str(r["fascicolo_id"]))
            if r["message_id_header"]:
                mids.setdefault(str(r["message_id_header"]).strip("<>").casefold(), set()).add(str(r["fascicolo_id"]))
    except sqlite3.Error:
        pass
    motivi_certo: Counter = Counter()

    from pct.pec_collegamento_certo import _indice_bundle, chiave_ufficio

    def certo(m: dict[str, Any]) -> str:
        trovato = cerca_collegamento_certo(m["parsed"], oggetti)
        if trovato.get("stato") != STATO_CERTO and "testi_dal_messaggio" in globals():
            riga = conn.execute("SELECT original_mime FROM pec_messages WHERE id=?", (m["id"],)).fetchone()
            testi = testi_dal_messaggio(bytes(riga[0] or b"")) if riga else []  # noqa: F821
            motivi_certo["relata_letta" if testi else "relata_assente"] += 1
            if testi:
                ufficio = ufficio_dal_testo(testi, _indice_bundle()[0], chiave_ufficio)  # noqa: F821
                motivi_certo["relata_ufficio_unico" if ufficio else "relata_ufficio_non_unico"] += 1
                trovato = cerca_collegamento_certo(lettura_con_relata(m["parsed"], testi, ufficio), oggetti)  # noqa: F821
                motivi_certo["relata:" + str(trovato.get("motivo") or "") + (":" + trovato["manca"] if trovato.get("manca") else "")] += 1
        motivi_certo[str(trovato.get("motivo") or "") + (":" + trovato["manca"] if trovato.get("manca") else "")] += 1
        return str(trovato.get("fascicolo_id") or "") if trovato.get("stato") == STATO_CERTO else ""

    codici: dict[str, set] = {}
    for f in oggetti:
        for d in getattr(f, "documenti", []) or []:
            codice = notifica_id(" ".join(str(getattr(d, c, "") or "") for c in ("nome", "note", "descrizione")))  # noqa: F821
            if codice:
                codici.setdefault(codice, set()).add(str(f.id))
    decisioni = collega_tutti(messaggi, indice_impronte=impronte, indice_message_id=mids, certo_per_messaggio=certo,  # noqa: F821
                              indice_notifica_id=codici)
    fonti: Counter = Counter()
    for m in messaggi:
        d = decisioni.get(m["id"], {})
        fonti[d.get("fonte") or d.get("motivo") or "nessuna"] += 1
        if d.get("fascicolo_id") and not m["fascicolo"]:
            m["fascicolo"] = d["fascicolo_id"]
    riletti = Counter()
    for m in messaggi:
        if m["ricevuta"] and not m["indirizzo"]:
            riga = conn.execute("SELECT original_mime FROM pec_messages WHERE id=?", (m["id"],)).fetchone()
            m["indirizzo"] = destinatario_da_daticert(daticert_dal_messaggio(bytes(riga[0] or b""))) if riga else ""  # noqa: F821
            riletti["riletti" if m["indirizzo"] else "non_riletti"] += 1
    return {"notifica_id_nei_fascicoli": len(codici), "eml_nei_fascicoli": len(impronte), "message_id_nei_fascicoli": len(mids), "messaggi_per_fonte": dict(fonti),
            "esiti_tre_controlli": dict(motivi_certo), "destinatari_daticert": dict(riletti)}


def _studio(paths: dict[str, Any]) -> dict[str, Any]:
    email_db = Path(str(paths.get("EMAIL_CASELLA_DB") or "./email/casella.json"))
    audit = Path(str(paths.get("PEC_AUDIT_DB") or email_db.parent / "pec_audit.sqlite"))
    if not audit.exists():
        return {"errore": "presidio_pec_assente"}
    fascicoli, oggetti = _fascicoli(paths)
    with _db_ro(audit) as conn:
        messaggi = _messaggi(conn)
        simulazione = _simula_collegamento(conn, messaggi, oggetti)
        presidio = Counter()
        try:
            for r in conn.execute("SELECT pec_address, delivery_status FROM pec_legal_notification_recipients"):
                presidio[f"{categoria_dominio(r['pec_address'])}|{r['delivery_status']}"] += 1
        except sqlite3.Error:
            presidio["tabella_assente"] = 1
    # Un invio = una PEC di notificazione dello studio; le ricevute vi si agganciano per Message-ID originale.
    invii: dict[str, dict[str, Any]] = {}
    ricevute_sciolte = Counter()
    for m in messaggi:
        if not m["ricevuta"] and ("sent" in m["cartella"] or "inviat" in m["cartella"]):
            chiave = m["message_id"] or m["id"]
            voce = invii.setdefault(chiave, {"fascicolo": m["fascicolo"], "anno": m["anno"], "allegati": [], "esiti": {}})
            voce["allegati"] += m["allegati"]
            for indirizzo in m["a"]:
                voce["esiti"].setdefault(str(indirizzo).casefold(), "inviata")
    for m in messaggi:
        if not m["ricevuta"]:
            continue
        chiave = m["originale"] or f"__{m['oggetto']}"
        voce = invii.get(chiave)
        if voce is None:
            voce = invii.setdefault(chiave, {"fascicolo": m["fascicolo"], "anno": m["anno"], "allegati": [], "esiti": {}, "solo_ricevute": True})
        voce["fascicolo"] = voce["fascicolo"] or m["fascicolo"]
        voce["allegati"] += [a for a in m["allegati"] if not re.search(r"daticert|smime|postacert", a, re.IGNORECASE)]
        indirizzo = m["indirizzo"].casefold()
        if not indirizzo and len(voce["esiti"]) == 1:
            indirizzo = next(iter(voce["esiti"]))  # ricevuta senza destinatario: l'unico dell'invio
        if not indirizzo:
            ricevute_sciolte[m["ricevuta"]] += 1
            continue
        precedente = voce["esiti"].get(indirizzo, "inviata")
        ordine = {"inviata": 0, "accettazione": 1, "mancata": 2, "consegna": 3}
        if ordine[m["ricevuta"]] >= ordine.get(precedente, 0):
            voce["esiti"][indirizzo] = m["ricevuta"]
    aggregato: dict[str, Counter] = defaultdict(Counter)
    combinazioni: dict[str, Counter] = defaultdict(Counter)
    fascicoli_per_chiave: dict[str, set] = defaultdict(set)
    anni: dict[str, set] = defaultdict(set)
    conteggi = Counter(messaggi=len(messaggi), invii=len(invii), ricevute_senza_destinatario=sum(ricevute_sciolte.values()))
    for voce in invii.values():
        info = fascicoli.get(voce["fascicolo"], {})
        if not voce["fascicolo"]:
            conteggi["invii_senza_fascicolo"] += 1
        chiave = f"{info.get('materia', 'fascicolo_non_collegato')} | {tipo_atto(voce['allegati'])} | {info.get('controparte', 'non_indicata')}"
        fascicoli_per_chiave[chiave].add(voce["fascicolo"])
        if voce["anno"]:
            anni[chiave].add(voce["anno"])
        categorie = set()
        for indirizzo, esito in voce["esiti"].items():
            categoria = categoria_dominio(indirizzo)
            categorie.add(categoria)
            aggregato[chiave][f"{categoria} → {esito}"] += 1
        combinazioni[chiave][" + ".join(sorted(categorie)) or "nessun_destinatario_letto"] += 1
    tabella = [
        {"tipologia": chiave, "fascicoli": len(fascicoli_per_chiave[chiave] - {""}), "anni": sorted(anni[chiave]),
         "destinatari_per_esito": dict(aggregato[chiave].most_common()), "invii_per_combinazione_domicili": dict(combinazioni[chiave].most_common())}
        for chiave in sorted(fascicoli_per_chiave, key=lambda c: -sum(combinazioni[c].values()))
    ]
    return {"collegamento_simulato": simulazione, "conteggi": dict(conteggi), "presidio_destinatari": dict(presidio), "categorie_controparte_fascicoli": dict(Counter(v["controparte"] for v in fascicoli.values())), "tipologie": tabella}


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_worker import create_scheduler_app
    from web.services.pec_fascicolo_documenti_runtime import studi_attivi

    app = create_scheduler_app()
    esito: dict[str, Any] = {"studi": []}
    with app.app_context():
        for numero, (_etichetta, paths) in enumerate(studi_attivi(app.config), start=1):
            try:
                esito["studi"].append({"studio": f"studio_{numero}", **_studio(paths)})
            except Exception as exc:
                esito["studi"].append({"studio": f"studio_{numero}", "errore": type(exc).__name__})
    print(MARCATORE + json.dumps(esito, ensure_ascii=False), flush=True)
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
