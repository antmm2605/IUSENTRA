"""Il deposito amministrativo telematico di un fascicolo: contesto e quadro per la sezione React.

Raccoglie dal fascicolo amministrativo quello che il Formweb chiede (sede,
NRG, oggetto, parti, documenti, contributo unificato) e lo unisce ai dati del
procedimento PAT salvati dall'avvocato (``pct.pat_formweb.ArchivioPat``). Le
impronte e la firma dei documenti si leggono dai metadati del fascicolo
(calcolate al caricamento): il quadro non rilegge i file (registro letture).
Base: art. 136 c.p.a.; d.P.C.M. 40/2016; manuale del Portale dell'Avvocato.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flask import current_app

from pct.fascicoli import TipoFascicolo
from pct.pat_formweb import ArchivioPat, catalogo, contributo, parti, regole, scheda
from pct.pat_formweb.archivio import RUOLI_DOCUMENTO
from web.services.tenant_paths import tenant_data_path

def _runtime(nome: str) -> Any:
    return current_app.extensions["core_runtime"][nome]()


def archivio() -> ArchivioPat:
    base = Path(tenant_data_path("TELEMATICO_DB", require_tenant=True)).parent
    return ArchivioPat(base / "pat_formweb.json")


def fascicolo_amministrativo(fid: str):
    fascicolo = _runtime("get_fascicoli").get(fid)
    if fascicolo is None:
        raise LookupError("Fascicolo non trovato.")
    if fascicolo.tipo != TipoFascicolo.AMMINISTRATIVO:
        raise ValueError("Il deposito PAT è disponibile solo per i fascicoli amministrativi.")
    return fascicolo


def sede_da_ufficio(nome: str) -> str:
    """Codice sede SIGA dell'ufficio indicato nel fascicolo (TAR, Consiglio di Stato, CGARS)."""
    testo = str(nome or "").strip().casefold()
    if not testo:
        return ""
    try:
        from pct.uffici_giudiziari import get_gestore

        uffici = get_gestore().carica()
    except Exception:
        uffici = []
    voce = next((u for u in uffici if str(u.get("nome") or "").casefold() == testo), None)
    if voce and voce.get("codice") in catalogo.SEDI:
        return catalogo.SEDI[voce["codice"]][0]
    return next((c for c, e in catalogo.SEDI.values() if e.casefold() == testo), "")


def nrg(fascicolo: Any) -> str:
    anno = re.sub(r"\D", "", str(getattr(fascicolo, "anno_rg", "") or ""))
    numero = re.sub(r"\D", "", str(getattr(fascicolo, "numero_rg", "") or ""))
    return f"{anno}{int(numero):05d}" if len(anno) == 4 and numero else ""


def _avvocato() -> dict[str, str]:
    try:
        cfg = _runtime("get_config_studio").config
        return {"nome": cfg.studio.avvocato or cfg.studio.nome, "pec": cfg.pec.indirizzo,
                "codiceFiscale": cfg.studio.codice_fiscale_avvocato or getattr(cfg.firma, "cf_avvocato", "")}
    except Exception:
        return {"nome": "", "pec": "", "codiceFiscale": ""}


def _dati_soggetto(soggetto: Any) -> dict[str, Any]:
    recapiti = getattr(soggetto, "recapiti", None)
    return {"id": soggetto.id, "tipo": getattr(soggetto.tipo, "value", str(soggetto.tipo)), "nome": soggetto.nome,
            "cognome": soggetto.cognome, "ragione_sociale": soggetto.ragione_sociale,
            "codice_fiscale": soggetto.codice_fiscale, "partita_iva": soggetto.partita_iva,
            "pec": getattr(recapiti, "pec", "") or ""}


def _cliente(fascicolo: Any) -> dict[str, Any] | None:
    if not getattr(fascicolo, "id_cliente", ""):
        return {"tipo": "PERSONA_FISICA", "ragione_sociale": fascicolo.nome_cliente} if fascicolo.nome_cliente else None
    cliente = _runtime("get_clienti").get(fascicolo.id_cliente)
    if cliente is None:
        return None
    tipo = str(getattr(cliente.tipo, "value", cliente.tipo)).upper()
    recapiti = getattr(cliente, "recapiti", None)
    return {"tipo": "PERSONA_FISICA" if "FISIC" in tipo else ("PUBBLICA_AMMINISTRAZIONE" if "PUBBLIC" in tipo else "PERSONA_GIURIDICA"),
            "nome": cliente.nome, "cognome": cliente.cognome, "ragione_sociale": cliente.ragione_sociale,
            "codice_fiscale": cliente.codice_fiscale, "partita_iva": cliente.partita_iva,
            "pec": getattr(recapiti, "pec", "") or ""}


def _ruolo_proposto(doc: Any) -> str:
    testo = " ".join(str(x or "") for x in (doc.nome, getattr(doc.tipo, "value", doc.tipo), doc.note)).casefold()
    if "procura" in testo:
        return "procura"
    if "relata" in testo or "notific" in testo:
        return "notifica"
    if "contributo" in testo or "f24" in testo or "pagopa" in testo:
        return "contributo"
    if re.search(r"\b(ricorso|motivi aggiunti|appello|memoria|istanza)\b", testo):
        return "atto"
    return "allegato"


def _versamento(fascicolo: Any) -> str:
    pagamenti = getattr(fascicolo, "pagamenti", {}) or {}
    voce = pagamenti.get("contributo_unificato") or pagamenti.get("cu") if isinstance(pagamenti, dict) else None
    if isinstance(voce, dict):
        return " · ".join(str(voce[k]) for k in ("data", "modalita", "iuv", "numero", "importo") if voce.get(k))
    return str(voce or "")


def documenti(fascicolo: Any, scelte: dict[str, Any]) -> list[dict[str, Any]]:
    """I documenti del fascicolo con ruolo, nome accettato dal Formweb e controlli dai metadati."""
    elenco = [d for d in getattr(fascicolo, "documenti", []) or [] if not getattr(d, "eliminato_il", "")]
    nomi = regole.nomi_unici([d.nome for d in elenco])
    esito = []
    for doc, proposto in zip(elenco, nomi):
        scelta = scelte.get(doc.id) or {}
        ruolo = scelta.get("ruolo") or _ruolo_proposto(doc)
        firmato = bool(getattr(doc, "firmato_digitalmente", False))
        voce = regole.ControlloFile(doc.nome, ruolo, int(doc.dimensione_bytes or 0), str(doc.hash_sha256 or "").upper(),
                                    "pades" if firmato and regole.estensione(doc.nome) == "pdf" else ("cades" if firmato else "assente"),
                                    proposto)
        if not regole.nome_valido(doc.nome):
            voce.esiti.append(regole.EsitoFile("NOME_NON_VALIDO", "avviso", f"Nel pacchetto IUSENTRA diventa «{proposto}»."))
        ext = regole.estensione(doc.nome)
        if ruolo in {"atto", "procura"} and (ext != "pdf" or not firmato):
            voce.esiti.append(regole.EsitoFile("FIRMA_MANCANTE", "errore", "Atto e procura: PDF firmato digitalmente (PAdES)."))
        elif ruolo != "escludi" and ext not in regole.ESTENSIONI_ALLEGATI:
            voce.esiti.append(regole.EsitoFile("FORMATO", "avviso", f"Formato .{ext or '?'} ammesso solo se una norma lo richiede."))
        descrizione = str(scelta.get("descrizione") or regole.radice(proposto))[:regole.LIMITE_DESCRIZIONE]
        esito.append({**voce.to_dict(), "id": doc.id, "descrizione": descrizione, "sceltaAvvocato": bool(scelta)})
    return esito


def contesto(fid: str) -> dict[str, Any]:
    fascicolo = fascicolo_amministrativo(fid)
    salvato = archivio().fascicolo(fid)
    proc = {"sede": sede_da_ufficio(fascicolo.tribunale), "nrg": nrg(fascicolo), "posizione": "ricorrente",
            "oggetto": fascicolo.oggetto or fascicolo.titolo, **{k: v for k, v in salvato["procedimento"].items() if v not in (None, "")}}
    soggetti = [(getattr(p.ruolo, "value", str(p.ruolo)), _dati_soggetto(s))
                for p, s in _runtime("get_soggetti").parti_fascicolo(fid)]
    elenco_parti = parti.parti_pat(_cliente(fascicolo), soggetti, proc.get("posizione") or "ricorrente", salvato["ruoli"])
    appello = catalogo.ambito(proc.get("sede") or "") in {"CDS", "CGARS"}
    try:
        from web.services.react_preventivo_wizard_bridge import _strumenti_legali

        cu = contributo.proposta(str(proc.get("tipoRicorso") or ""), appello, proc.get("valore") or None,
                                 _strumenti_legali().calcola_contributo_unificato)
    except Exception:
        current_app.logger.warning("Contributo unificato PAT non calcolato per %s", fid, exc_info=True)
        cu = {"importo": None, "nota": "Calcolo non disponibile: verifica la tabella art. 13 c. 6-bis."}
    cu["versamento"] = _versamento(fascicolo)
    return {"fascicolo": {"id": fid, "titolo": fascicolo.titolo, "oggetto": fascicolo.oggetto, "ufficio": fascicolo.tribunale},
            "procedimento": proc, "avvocato": _avvocato(), "parti": elenco_parti, "contributo": cu,
            "documenti": documenti(fascicolo, salvato.get("documenti") or {}), "depositi": salvato["depositi"]}


def quadro(fid: str, tipo: str = "ricorso") -> dict[str, Any]:
    ctx = contesto(fid)
    return {"ok": True, **ctx, "scheda": scheda.scheda(ctx, tipo),
            "tipiRicorso": catalogo.tipi_ricorso(ctx["procedimento"].get("sede") or ""),
            "linkPortale": catalogo.PORTALE}


__all__ = ["RUOLI_DOCUMENTO", "archivio", "contesto", "documenti", "fascicolo_amministrativo", "nrg", "quadro", "sede_da_ufficio"]
