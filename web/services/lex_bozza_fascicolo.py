"""La bozza di Lex nel fascicolo: PDF impaginato da atto, registrato come bozza del passo, mai firmato né inviato.

Usa lo stesso formato e lo stesso registro delle bozze dei passi (``pct/bozze_passi``): il PDF entra nel fascicolo
con i tag «bozza», il testo modificabile resta nel registro e l'editor lo riapre. La stessa bozza (stessa impronta)
non si duplica. Il chiamante ha già verificato che l'utente veda il fascicolo (``lex/fascicolo_accesso``); qui si
verifica anche il permesso di scrittura.

Base: art. 2229 ss. c.c. e art. 13 L. 247/2012 (l'atto è dell'avvocato: il software prepara una bozza da rivedere
e firmare); art. 20 CAD per l'impronta del documento.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Callable

_log = logging.getLogger(__name__)

AUTORE = "Lex (bozza preparata su richiesta dell'avvocato)"
_SEGNAPOSTO = re.compile(r"\[(?:([^\[\]]*?)\s+)?da completare(?::\s*([^\]]*))?\]")


def normalizza_segnaposti(testo: str) -> str:
    """«[da completare]» e «[luogo da completare]» nel formato del registro: «[da completare: dato]»."""
    testo = testo or ""

    def sost(m: re.Match) -> str:
        etichetta = (m.group(2) or m.group(1) or "").strip()
        if not etichetta:
            # «codice fiscale [da completare]»: il dato è nelle parole che precedono, fino alla punteggiatura.
            prima = re.split(r"[,;:.()\]\n–-]", testo[max(0, m.start() - 60):m.start()])[-1]
            parole = re.findall(r"[A-Za-zÀ-ÿ']+", prima)[-3:]
            parole = [p for p in parole if p.lower() not in {"il", "lo", "la", "i", "gli", "le", "di", "del", "della", "in", "a", "e"}]
            etichetta = " ".join(parole[-2:]) or "dato"
        return f"[da completare: {etichetta}]"

    return _SEGNAPOSTO.sub(sost, testo)


def _puo_scrivere() -> bool:
    from flask import g

    utente = g.get("utente_corrente")
    return bool(utente is not None and utente.ha_permesso("fascicoli.scrivi"))


def salva_bozza(fascicolo_id: str, *, titolo: str, testo: str, modello: str, norma: str = "",
                repository: Any = None, archivio: Any = None, puo_scrivere: Callable[[], bool] | None = None) -> dict[str, Any]:
    """Salva la bozza come PDF nel fascicolo e nel registro delle bozze. Restituisce l'esito, mai un'eccezione."""
    try:
        if not (puo_scrivere or _puo_scrivere)():
            return {"salvata": False, "motivo": "permesso di scrittura sul fascicolo assente"}
        from pct.bozze_passi.archivio import VoceBozza, adesso
        from pct.bozze_passi.modello import FONTE_BOZZA_PASSO, da_completare
        from pct.bozze_passi.pdf import bozza_pdf, nome_file_pdf
        from pct.fascicoli import TipoDocumento
        from web.services.bozze_passi_runtime import archivio_corrente, impagina, nota_bozza
        from web.services.document_crypto import encrypt_doc

        if repository is None:
            from web.helpers import get_fascicoli

            repository = get_fascicoli()
        archivio = archivio if archivio is not None else archivio_corrente()
        testo = normalizza_segnaposti(testo)
        impronta_testo = hashlib.sha256(testo.encode("utf-8")).hexdigest()
        chiave = f"lex-{modello or 'atto'}-{impronta_testo[:12]}"
        if archivio is not None:
            gia = next((v for v in archivio.del_fascicolo(fascicolo_id) if v.chiave == chiave), None)
            if gia is not None:
                return {"salvata": True, "gia_presente": True, "documento_id": gia.documento_id, "nome": nome_file_pdf(titolo),
                        "da_completare": list(gia.da_completare)}
        testo_html = impagina(testo)
        grezzo = bozza_pdf(titolo, testo_html)
        nome = nome_file_pdf(titolo)
        mancano = list(da_completare(testo))
        documento = repository.aggiungi_documento(
            fascicolo_id, nome, TipoDocumento.ATTO_GIUDIZIARIO, encrypt_doc(grezzo),
            note=nota_bozza(f"Lex — {modello}" if modello else "Lex", len(mancano)),
            tags=["bozza", "bozza-passo", "bozza-lex", f"bozza-passo:{chiave}"], caricato_da=AUTORE,
            fonte_documento=FONTE_BOZZA_PASSO, nome_originale=nome,
            hash_contenuto_sha256=hashlib.sha256(grezzo).hexdigest(), salvataggio_mirato=True)
        if archivio is not None:
            ora = adesso()
            archivio.salva(VoceBozza(fascicolo_id=fascicolo_id, chiave=chiave, documento_id=documento.id, tipo="lex",
                                     titolo=titolo, modello=modello, modello_titolo=f"Lex — {modello}", norma=norma,
                                     da_completare=mancano, impronta_testo=impronta_testo,
                                     impronta_contenuto=hashlib.sha256(grezzo).hexdigest(), creata_il=ora,
                                     aggiornata_il=ora, testo_html=testo_html, formato="pdf"))
        return {"salvata": True, "documento_id": documento.id, "nome": nome, "da_completare": mancano}
    except Exception as exc:
        _log.exception("Lex: bozza non salvata nel fascicolo %s", fascicolo_id)
        return {"salvata": False, "motivo": f"errore interno ({type(exc).__name__})"}


def nota_nella_risposta(esito: dict[str, Any]) -> str:
    if esito.get("salvata"):
        mancano = len(esito.get("da_completare") or [])
        return (f"\n\n**Bozza nel fascicolo**\n- {'Già presente' if esito.get('gia_presente') else 'Salvata'} come PDF "
                f"«{esito.get('nome')}» tra le bozze del fascicolo"
                + (f", con {mancano} dati da completare evidenziati" if mancano else "")
                + ". È una bozza da rivedere e firmare: non è stata firmata, inviata, depositata né notificata.")
    return f"\n\n**Bozza nel fascicolo**\n- Non salvata: {esito.get('motivo')}. Il testo resta qui sopra."
