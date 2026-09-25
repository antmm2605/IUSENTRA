"""Contesto del deposito tributario telematico (PTT/SIGIT) di un fascicolo.

Mette insieme i dati del fascicolo (cliente, controparti, ufficio, documenti
con i metadati già salvati), quelli della nota di iscrizione a ruolo indicati
dall'avvocato e le regole del PTT (``pct/ptt_sigit``): nessun documento viene
aperto qui, i controlli sul contenuto dei PDF si fanno solo su richiesta.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flask import current_app

from pct.fascicoli import TipoFascicolo
from pct.ptt_sigit import ArchivioPtt, catalogo, cut, parti, regole, scheda, termini
from web.services.tenant_paths import tenant_data_path


def _runtime(nome: str) -> Any:
    return current_app.extensions["core_runtime"][nome]()


def archivio() -> ArchivioPtt:
    base = Path(tenant_data_path("TELEMATICO_DB", require_tenant=True)).parent
    return ArchivioPtt(base / "ptt_sigit.json")


def fascicolo_tributario(fid: str):
    fascicolo = _runtime("get_fascicoli").get(fid)
    if fascicolo is None:
        raise LookupError("Fascicolo non trovato.")
    if fascicolo.tipo != TipoFascicolo.TRIBUTARIO:
        raise ValueError("Il deposito PTT è disponibile solo per i fascicoli tributari.")
    return fascicolo


def rg(fascicolo: Any) -> str:
    numero = re.sub(r"\D", "", str(getattr(fascicolo, "numero_rg", "") or ""))
    anno = re.sub(r"\D", "", str(getattr(fascicolo, "anno_rg", "") or ""))
    return f"{int(numero)}/{anno}" if numero and len(anno) == 4 else ""


def _avvocato() -> dict[str, str]:
    try:
        cfg = _runtime("get_config_studio").config
        return {"nome": cfg.studio.avvocato or cfg.studio.nome, "pec": cfg.pec.indirizzo,
                "codiceFiscale": cfg.studio.codice_fiscale_avvocato or getattr(cfg.firma, "cf_avvocato", "")}
    except Exception:
        return {"nome": "", "pec": "", "codiceFiscale": ""}


def _dati_soggetto(soggetto: Any) -> dict[str, Any]:
    recapiti = getattr(soggetto, "recapiti", None)
    indirizzo = getattr(soggetto, "indirizzo", None)
    return {"id": soggetto.id, "tipo": getattr(soggetto.tipo, "value", str(soggetto.tipo)), "nome": soggetto.nome,
            "cognome": soggetto.cognome, "ragione_sociale": soggetto.ragione_sociale, "forma_giuridica": soggetto.forma_giuridica,
            "codice_fiscale": soggetto.codice_fiscale, "partita_iva": soggetto.partita_iva,
            "provincia": str(getattr(indirizzo, "provincia", "") or "").upper(), "pec": getattr(recapiti, "pec", "") or ""}


def _cliente(fascicolo: Any) -> dict[str, Any] | None:
    if not getattr(fascicolo, "id_cliente", ""):
        return {"tipo": "PERSONA_FISICA", "ragione_sociale": fascicolo.nome_cliente} if fascicolo.nome_cliente else None
    cliente = _runtime("get_clienti").get(fascicolo.id_cliente)
    if cliente is None:
        return None
    tipo = str(getattr(cliente.tipo, "value", cliente.tipo)).upper()
    recapiti = getattr(cliente, "recapiti", None)
    return {"tipo": "PERSONA_FISICA" if "FISIC" in tipo else "PERSONA_GIURIDICA", "nome": cliente.nome,
            "cognome": cliente.cognome, "ragione_sociale": cliente.ragione_sociale,
            "forma_giuridica": getattr(cliente, "forma_giuridica", "") or "", "codice_fiscale": cliente.codice_fiscale,
            "partita_iva": cliente.partita_iva, "pec": getattr(recapiti, "pec", "") or ""}


_TIPOLOGIE = (
    (r"accettazione", "RICEVUTA DI ACCETTAZIONE PEC"), (r"consegna", "RICEVUTA DI CONSEGNA PEC"),
    (r"procura|mandato|nomina", "PROCURA-NOMINA DEL DIFENSORE"), (r"relata", "RELATA DI NOTIFICA CARTACEA"),
    (r"\bf23\b|pagopa|contributo unificato|\bcut\b", "RICEVUTA DI PAGAMENTO CUT"),
    (r"avviso di accertamento|cartella|intimazione|avviso di liquidazione|diniego|fermo|ipotec|atto impugnato|irrogazione",
     "ATTO IMPUGNATO"),
    (r"processo verbale|\bpvc\b", "PROCESSO VERBALE DI CONSTATAZIONE"), (r"sentenza.*notificat", "SENTENZA NOTIFICATA"),
    (r"fattur", "FATTURE"), (r"dichiarazion", "DICHIARAZIONI FISCALI"), (r"bilanci|scritture contabili", "BILANCIO E SCRITTURE CONTABILI"),
    (r"contratt", "CONTRATTI"), (r"interpello", "INTERPELLO"), (r"catast", "ATTI CATASTALI"), (r"memori", "MEMORIE"),
)


def _proposta(doc: Any) -> tuple[str, str]:
    testo = " ".join(str(x or "") for x in (doc.nome, getattr(doc.tipo, "value", doc.tipo), doc.note)).casefold()
    if re.search(r"\b(ricorso|appello|controdeduzion)", testo) and not re.search(r"ricevut|relata|notific", testo):
        return "atto", ""
    return "allegato", next((t for modello, t in _TIPOLOGIE if re.search(modello, testo)), "ALTRI DOCUMENTI")


def documenti(fascicolo: Any, scelte: dict[str, Any]) -> list[dict[str, Any]]:
    """I documenti del fascicolo con ruolo PTT, tipologia dell'Appendice B e controlli dai metadati."""
    esito = []
    for doc in [d for d in getattr(fascicolo, "documenti", []) or [] if not getattr(d, "eliminato_il", "")]:
        scelta = scelte.get(doc.id) or {}
        ruolo_proposto, tipologia_proposta = _proposta(doc)
        ruolo = scelta.get("ruolo") or ruolo_proposto
        nome = regole.con_estensione(doc.nome, getattr(doc, "nome_originale", ""), getattr(doc, "percorso", ""))
        firmato = bool(getattr(doc, "firmato_digitalmente", False))
        controllo = regole.controlla_metadati(nome, int(doc.dimensione_bytes or 0), ruolo, firmato)
        tipologia = scelta.get("tipologia") or ("" if ruolo == "atto" else tipologia_proposta)
        esito.append({"id": doc.id, "nome": nome, "ruolo": ruolo, "tipologia": tipologia,
                      "descrizione": scelta.get("descrizione") or (doc.nome[: regole.LIMITE_DESCRIZIONE] if tipologia == "ALTRI DOCUMENTI" else ""),
                      "dimensione": int(doc.dimensione_bytes or 0), "firma": regole.tipo_firma(nome, firmato),
                      "sha256": str(doc.hash_sha256 or "").upper(), "esiti": [e.to_dict() for e in controllo.esiti],
                      "bloccante": controllo.bloccante, "sceltaAvvocato": bool(scelta)})
    return esito


def contesto(fid: str) -> dict[str, Any]:
    fascicolo = fascicolo_tributario(fid)
    salvato = archivio().fascicolo(fid)
    soggetti = [(getattr(p.ruolo, "value", str(p.ruolo)), _dati_soggetto(s)) for p, s in _runtime("get_soggetti").parti_fascicolo(fid)]
    elenco = parti.parti_nir(_cliente(fascicolo), soggetti)
    proposta_corte = catalogo.sede_da_testo(fascicolo.tribunale or "") or next(
        (catalogo.sede_per_provincia(p["provincia"]) for p in elenco["resistenti"] if p.get("provincia")), "")
    proc = {"corte": proposta_corte, "posizione": "ricorrente", "rg": rg(fascicolo), "atti": [],
            **{k: v for k, v in salvato["procedimento"].items() if v not in (None, "")}}
    proc.setdefault("grado", (catalogo.sede(proc.get("corte") or "") or {}).get("grado", "1"))
    avvocato = _avvocato()
    esenzione = proc.get("cutEsenzione") or ""
    contributo = cut.calcola(proc.get("atti") or [], pec_difensore=bool(avvocato.get("pec")),
                             codice_fiscale_parte=all(p["codiceFiscale"] for p in elenco["ricorrenti"]), esenzione=esenzione)
    return {"fascicolo": {"id": fid, "titolo": fascicolo.titolo, "oggetto": fascicolo.oggetto, "ufficio": fascicolo.tribunale},
            "procedimento": proc, "propostaCorte": proposta_corte if not salvato["procedimento"].get("corte") else "",
            "avvocato": avvocato, "parti": elenco, "cut": contributo, "termini": termini.termini(proc),
            "documenti": documenti(fascicolo, salvato.get("documenti") or {}), "depositi": salvato["depositi"]}


def tipo_suggerito(ctx: dict[str, Any]) -> str:
    """Con il numero di ruolo il ricorso è già iscritto: i depositi da fare sono quelli successivi."""
    proc = ctx["procedimento"]
    if proc.get("posizione") == "resistente":
        return "controdeduzioni"
    if proc.get("rg") or any(d.get("stato") in {"depositata", "acquisita"} and d.get("tipo") in {"ricorso", "appello"} for d in ctx["depositi"]):
        return "altri-atti"
    return "appello" if proc.get("grado") == "2" else "ricorso"


def quadro(fid: str, tipo: str = "") -> dict[str, Any]:
    ctx = contesto(fid)
    suggerito = tipo_suggerito(ctx)
    return {"ok": True, **ctx, "tipoSuggerito": suggerito, "scheda": scheda.scheda(ctx, tipo or suggerito),
            "linkPortale": catalogo.PORTALE, "telecontenzioso": catalogo.TELECONTENZIOSO}


__all__ = ["archivio", "contesto", "documenti", "fascicolo_tributario", "quadro", "rg", "tipo_suggerito"]
