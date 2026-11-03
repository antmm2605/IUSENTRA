"""«Copia originale da scaricare dal PST» per i provvedimenti notificati dallo studio.

Il provvedimento del giudice notificato in proprio (sentenza, decreto, ordinanza) ha la sua copia informatica
originale nel fascicolo telematico dell'ufficio. Il download non può essere autonomo: richiede la sessione
autenticata dell'avvocato (CNS/CIE/SPID) sul Portale dei Servizi Telematici (regola PST di CLAUDE.md; art. 16-bis
D.L. 179/2012 e D.M. 44/2011 per la consultazione del fascicolo informatico). Qui si prepara la voce con gli estremi
già compilati e si dice se il file con quell'impronta è già nel fascicolo.
"""

from __future__ import annotations

from typing import Any, Iterable

PORTALE_PST = "https://pst.giustizia.it/PST/"
ATTI_DEL_GIUDICE = frozenset({"sentenza", "decreto", "decreto_ingiuntivo", "ordinanza"})
DA_SCARICARE = "da_scaricare"
SCARICATA = "scaricata"
ETICHETTE_STATO = {DA_SCARICARE: "Da scaricare dal PST", SCARICATA: "Scaricata"}


def _registro(fascicolo: Any) -> str:
    try:
        from pct.polisWeb import _polisweb_registro_spec

        tipo = getattr(getattr(fascicolo, "tipo", ""), "value", getattr(fascicolo, "tipo", ""))
        spec = _polisweb_registro_spec(getattr(fascicolo, "registro", ""), tipo, getattr(fascicolo, "tribunale", ""))
        return str(getattr(spec, "label", "") or "")
    except Exception:  # noqa: BLE001 - registro non determinabile: lo sceglie l'avvocato sul portale
        return ""


def stato_copia(fascicolo: Any, *, tipo_atto: str, impronte_atto: Iterable[str], documenti_dalla_pec: Iterable[str] = ()) -> str:
    """«Scaricata» quando nel fascicolo compare il file con l'impronta dell'atto (non portato dalla stessa PEC)
    o un documento acquisito dal portale telematico dello stesso tipo di atto; altrimenti «da scaricare»."""
    impronte = {str(i).casefold() for i in impronte_atto if i}
    dalla_pec = {str(i) for i in documenti_dalla_pec if i}
    parola = tipo_atto.split("_")[0]
    for documento in getattr(fascicolo, "documenti", []) or []:
        if getattr(documento, "eliminato_il", "") or str(getattr(documento, "id", "")) in dalla_pec:
            continue
        hash_doc = {str(getattr(documento, c, "") or "").casefold() for c in ("hash_sha256", "hash_contenuto_sha256")} - {""}
        if hash_doc & impronte:
            return SCARICATA
        dal_portale = str(getattr(documento, "fonte_documento", "") or "").upper() == "PORTALE_TELEMATICO"
        descrizione = " ".join(str(getattr(documento, c, "") or "") for c in ("tipo_atto_portale", "nome_portale", "nome")).casefold()
        if dal_portale and parola in descrizione:
            return SCARICATA
    return DA_SCARICARE


def voce_copia_originale(fascicolo: Any, *, tipo_atto: str, impronte_atto: Iterable[str], invio: str,
                         documenti_dalla_pec: Iterable[str] = ()) -> dict[str, Any] | None:
    """La voce per il fascicolo, o None se l'atto notificato non è un provvedimento del giudice."""
    if tipo_atto not in ATTI_DEL_GIUDICE:
        return None
    stato = stato_copia(fascicolo, tipo_atto=tipo_atto, impronte_atto=impronte_atto, documenti_dalla_pec=documenti_dalla_pec)
    numero, anno = str(getattr(fascicolo, "numero_rg", "") or ""), str(getattr(fascicolo, "anno_rg", "") or "")
    return {
        "chiave": f"{getattr(fascicolo, 'id', '')}:{invio}",
        "fascicoloId": str(getattr(fascicolo, "id", "")),
        "titolo": "Copia originale da scaricare dal PST",
        "tipoAtto": tipo_atto.replace("_", " "),
        "ufficio": str(getattr(fascicolo, "tribunale", "") or ""),
        "registro": _registro(fascicolo),
        "ruolo": f"{numero}/{anno}" if numero and anno and "/" not in numero else numero,
        "url": PORTALE_PST,
        "stato": stato,
        "statoEtichetta": ETICHETTE_STATO[stato],
        "avvertenza": ("Il download richiede l'accesso dell'avvocato al Portale dei Servizi Telematici con CNS, CIE o SPID: "
                       "il gestionale prepara gli estremi ma non scarica da solo."),
    }
