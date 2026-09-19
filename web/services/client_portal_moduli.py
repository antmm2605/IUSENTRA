"""I moduli che lo studio manda al cliente: si leggono, si compilano, si scaricano.

Quando lo studio allega un modulo da compilare, il cliente doveva scaricarlo,
aprirlo con un programma suo, compilarlo e ricaricarlo. Chi non ha un lettore
PDF che scrive nei campi — cioe' quasi tutti, sul telefono — restava fermo.

Qui il modulo si compila dentro il portale. Le regole non si riscrivono: i
campi predisposti si leggono e si riempiono con `pct.mediazione_documenti`
(`campi_pdf`, `compila_pdf`), le stesse funzioni gia' usate per i moduli degli
organismi di mediazione, cosi' una regola sui moduli si cambia in un punto
solo. Il compilatore sul fronte e' lo stesso, `PdfModulo`.

Due limiti dichiarati, non aggirati:
- se il PDF **non ha campi predisposti** non lo si trasforma e non lo si
  compila «a occhio»: resta consultabile e scaricabile, e lo si dice;
- la copia compilata e' un **documento nuovo** del portale, accanto
  all'originale, che non viene mai sovrascritto.
"""

from __future__ import annotations

from typing import Any


def _testo(valore: Any) -> str:
    return str(valore if valore is not None else "").strip()


def _documento_del_cliente(repo: Any, invito: dict[str, Any], document_id: str) -> dict[str, Any] | None:
    """Il documento, solo se appartiene alla pratica di chi lo chiede."""
    from web.services.react_client_portal_bridge import _document_row_for_download

    riga = _document_row_for_download(repo, _testo(invito.get("tenant_id")), _testo(document_id))
    if not riga or _testo(riga.get("matter_id")) != _testo(invito.get("matter_id")):
        return None
    return riga


def _contenuto(repo: Any, riga: dict[str, Any]) -> bytes:
    from web.services.react_client_portal_bridge import _document_download_tuple

    percorso, _nome, _tipo = _document_download_tuple(repo, riga)
    return percorso.read_bytes()


def _soglie_superate(grezzo: bytes) -> list[dict[str, Any]]:
    """Gli importi di legge che il modulo cita e che non sono piu' vigenti.

    Un modello preparato prima dell'ultimo decreto continua a riportare la
    soglia di allora: chi lo compila dichiara su un valore che non esiste piu'.
    Il confronto e' con la tabella normativa versionata, non con una stima: se
    non si riesce a leggerla, non si avvisa nulla piuttosto che avvisare a caso.
    """
    try:
        from pct.soglie_nei_documenti import soglie_superate_nel_pdf
        from web.helpers import get_normative_tables

        return soglie_superate_nel_pdf(grezzo, get_normative_tables())
    except Exception:
        return []


def _proposte_dalla_scheda_studio(invito: dict[str, Any], campi: list[dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    """I valori che lo studio puo' gia' scrivere nel modulo, e da dove vengono.

    Si legge la stessa scheda che riempie il pannello Anagrafica del portale,
    cosi' il modulo e la scheda non possono dire cose diverse. Se la scheda non
    si legge, il modulo resta vuoto: e' un di piu', non una condizione.
    """
    from pct.anagrafica_cliente_portale import anagrafica_dallo_studio, unisci_anagrafica
    from pct.moduli_compilabili import proposte_dalla_scheda

    try:
        from web.services.react_client_portal_bridge import (
            _cliente_by_id,
            _invite_and_repo,
            _profile_anagrafica,
            _current_client_token,
        )

        _invito, repo = _invite_and_repo(_current_client_token())
        cliente_id = _testo(invito.get("client_id"))
        profilo = repo.get_profile(_testo(invito.get("tenant_id")), cliente_id) or {}
        unita = unisci_anagrafica(
            dallo_studio=anagrafica_dallo_studio(_cliente_by_id(cliente_id)),
            dal_cliente=_profile_anagrafica(profilo),
        )
    except Exception:
        return {}, {}
    proposte = proposte_dalla_scheda(campi, unita)
    return proposte, {nome: "studio" for nome in proposte}


def campi_del_modulo(document_id: str, righe: int = 0) -> dict[str, Any]:
    """I campi predisposti del modulo e le misure delle pagine, per compilarlo.

    Con ``righe`` si chiede la tabella del nucleo familiare portata a quel
    numero di righe: si leggono i campi del foglio come sara' davvero, non di
    quello con le sole righe iniziali.
    """
    from pct.mediazione_documenti import campi_pdf, imposta_righe, righe_disponibili
    from pct.moduli_compilabili import righe_da_attivare
    from web.services.react_client_portal_bridge import (
        ClientPortalError,
        _current_client_token,
        _invalid_invite_payload,
        _invite_and_repo,
    )

    try:
        invito, repo = _invite_and_repo(_current_client_token())
    except ClientPortalError:
        return _invalid_invite_payload()
    riga = _documento_del_cliente(repo, invito, document_id)
    if not riga:
        return {"ok": False, "code": "not_found", "message": "Documento non trovato."}
    nome = _testo(riga.get("filename"), )
    if not nome.lower().endswith(".pdf"):
        return {"ok": True, "compilabile": False, "campi": [], "pagine": [], "documento": _testo(riga.get("id")),
                "message": "Questo allegato non è un PDF: si può scaricare, non compilare nel portale."}
    try:
        grezzo = _contenuto(repo, riga)
        if righe:
            grezzo = imposta_righe(grezzo, righe)
        import pymupdf as fitz

        with fitz.open(stream=grezzo, filetype="pdf") as pdf:
            pagine = [{"numero": p.number + 1, "larghezza": p.rect.width, "altezza": p.rect.height} for p in pdf]
        campi = campi_pdf(grezzo)
        righe_attivabili = righe_da_attivare(campi_pdf(grezzo, includi_da_attivare=True))
    except ValueError as errore:
        return {"ok": False, "code": "validation_error", "message": str(errore)}
    except Exception:
        return {"ok": False, "code": "unreadable", "message": "Il modulo non è leggibile. Scaricalo e contatta lo studio."}
    proposte, origini = _proposte_dalla_scheda_studio(invito, campi)
    return {
        "ok": True,
        "compilabile": bool(campi),
        "campi": campi,
        "pagine": pagine,
        "documento": _testo(riga.get("id")),
        "nome": nome,
        "versione": 1,
        # Quello che lo studio sa gia': il cliente conferma invece di riscrivere.
        "proposte": proposte,
        "origini": origini,
        "righeDaAttivare": righe_attivabili,
        "righe": righe_disponibili(grezzo),
        # Importi di legge citati dal modulo e ormai superati.
        "avvisiNormativi": _soglie_superate(grezzo),
        "message": "" if campi else "Questo PDF non contiene campi predisposti: resta consultabile e scaricabile, ma non si compila nel portale.",
    }


def compila_il_modulo(document_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Salva una copia compilata del modulo come nuovo documento del portale."""
    from pct.mediazione_documenti import compila_pdf
    from web.services.react_client_portal_bridge import (
        ClientPortalError,
        _current_client_token,
        _invalid_invite_payload,
        _invite_and_repo,
        _persist_client_upload,
        _public_row,
        client_dashboard_payload,
    )

    try:
        token = _current_client_token()
        invito, repo = _invite_and_repo(token)
    except ClientPortalError:
        return _invalid_invite_payload()
    riga = _documento_del_cliente(repo, invito, document_id)
    if not riga:
        return {"ok": False, "code": "not_found", "message": "Documento non trovato."}
    valori = payload.get("valori")
    if not isinstance(valori, dict) or not valori:
        return {"ok": False, "code": "validation_error", "message": "Nessun campo compilato."}
    try:
        compilato = compila_pdf(_contenuto(repo, riga), valori)
    except ValueError as errore:
        return {"ok": False, "code": "validation_error", "message": str(errore)}
    except Exception:
        return {"ok": False, "code": "unreadable", "message": "Il modulo non è stato compilato. Scaricalo e contatta lo studio."}
    originale = _testo(riga.get("filename"), )
    nuovo_nome = f"{originale[:-4] if originale.lower().endswith('.pdf') else originale}-compilato.pdf"
    # Copia distinta: l'originale mandato dallo studio non si tocca mai.
    item = _persist_client_upload(
        repo,
        invito,
        data=compilato,
        original_name=nuovo_nome,
        content_type="application/pdf",
        request_id=_testo(riga.get("request_id")),
    )
    return {
        "ok": True,
        "message": "Modulo compilato e inviato allo studio. L'originale resta a disposizione.",
        "item": _public_row(item),
        "dashboard": client_dashboard_payload(token=token),
    }


__all__ = ["campi_del_modulo", "compila_il_modulo"]
