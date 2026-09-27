"""Azioni del cliente nel portale con link personale (`/portale/<token>`).

Ogni azione è scritta una volta sola e usata dalle pagine storiche (moduli
HTML) e dalle API JSON della pagina React: consenso privacy, invio documenti,
accettazione del preventivo, firma del conferimento, aggiornamento recapiti.
I permessi della scheda portale si verificano prima di chiamarle
(`richiedi_permessi`); qui restano i controlli propri dell'azione.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Mapping

from flask import current_app, request

from web.services.portale_cliente_legacy_contesto import ContestoPortale, fascicoli_cliente, permesso
from web.services.portale_cliente_legacy_dati import conferimento_del_cliente, preventivo_del_cliente

STATI_PREVENTIVO_ACCETTABILI = {"INVIATO", "APERTO", "ACCETTATO", "CONVERTITO"}
ERRORE_CONSENSO = "Devi spuntare la casella per procedere."
ERRORE_NESSUN_FILE = "Nessun file selezionato."
ERRORE_PRATICA = "Pratica non disponibile per questo accesso."


class RisorsaNonTrovata(Exception):
    """Documento economico inesistente o di un altro cliente (404)."""


@dataclass
class EsitoAzione:
    """Esito con i messaggi (categoria, testo) e la sezione da mostrare dopo."""

    ok: bool = True
    messaggi: list[tuple[str, str]] = field(default_factory=list)
    sezione: str = ""
    errore: str = ""


@dataclass
class EsitoCaricamento:
    caricati: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)
    # Errore bloccante (nessun file, pratica non del cliente) e relativo stato HTTP.
    errore: str = ""
    status: int = 200


def _ip() -> str:
    return request.remote_addr or ""


def _user_agent() -> str:
    return request.headers.get("User-Agent", "")


def _avvocato_referente(cliente=None, preventivo=None, conferimento=None) -> str:
    return (
        getattr(conferimento, "avvocato_referente", "")
        or getattr(cliente, "avvocato_referente", "")
        or getattr(preventivo, "creato_da", "")
        or "Avv. referente"
    )


# ------------------------------------------------------------------ privacy

def registra_consenso_privacy(contesto: ContestoPortale, consenso: bool) -> EsitoAzione:
    """Consenso GDPR (art. 7 Reg. UE 2016/679): anagrafica cliente + scheda portale."""
    if not consenso:
        return EsitoAzione(ok=False, errore=ERRORE_CONSENSO)
    from web.helpers import get_clienti

    get_clienti().aggiorna(
        contesto.cliente.id,
        consenso_trattamento=True,
        data_consenso=date.today().isoformat(),
        modalita_consenso="digitale",
    )
    contesto.gestore.registra_firma_privacy(contesto.portale.id, ip=_ip(), user_agent=_user_agent())
    return EsitoAzione(ok=True, sezione="privacy_ok")


# ------------------------------------------------------------------ documenti

def _file_selezionati(files: Iterable[Any]) -> list[Any]:
    return [f for f in files if getattr(f, "filename", "")]


def carica_documenti(contesto: ContestoPortale, files: list[Any], id_fascicolo: str, note: str) -> EsitoCaricamento:
    """Salva i file nel fascicolo scelto (solo pratiche del cliente) o nella cartella del portale."""
    portale, cliente = contesto.portale, contesto.cliente
    max_mb = portale.permessi.max_upload_mb
    max_bytes = max_mb * 1024 * 1024
    id_fascicolo = str(id_fascicolo or "").strip()
    note = str(note or "").strip()

    if not files or all(getattr(f, "filename", "") == "" for f in files):
        return EsitoCaricamento(errore=ERRORE_NESSUN_FILE, status=200)
    # Il fascicolo scelto deve essere del cliente del link e visibile dal portale.
    if id_fascicolo and (
        not permesso(contesto, "vedi_fascicoli")
        or id_fascicolo not in {f.id for f in fascicoli_cliente(cliente.id)}
    ):
        return EsitoCaricamento(errore=ERRORE_PRATICA, status=403)

    esito = EsitoCaricamento()
    if id_fascicolo:
        from pct.fascicoli import TipoDocumento
        from web.helpers import get_fascicoli

        gf = get_fascicoli()
        for f in _file_selezionati(files):
            # Si legge al massimo un byte oltre il limite: un file enorme non finisce in memoria.
            contenuto = f.read(max_bytes + 1)
            if len(contenuto) > max_bytes:
                esito.errori.append(f"{f.filename}: supera il limite di {max_mb} MB")
                continue
            try:
                gf.aggiungi_documento(
                    id_fasc=id_fascicolo,
                    nome_file=f.filename,
                    tipo=TipoDocumento.ALTRO,
                    contenuto=contenuto,
                    note=f"Caricato dal portale cliente. {note}".strip(),
                    caricato_da=f"portale:{cliente.nome_completo}",
                )
                esito.caricati.append(f.filename)
            except Exception:
                current_app.logger.exception("Caricamento dal portale non riuscito")
                esito.errori.append(f"{f.filename}: caricamento non riuscito, riprova o contatta lo studio.")
        return esito

    # Cartella del portale: arrivi per l'avvocato.
    upload_dir = contesto.gestore.upload_dir(cliente.id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for f in _file_selezionati(files):
        # Si legge al massimo un byte oltre il limite: un file enorme non finisce in memoria.
        contenuto = f.read(max_bytes + 1)
        if len(contenuto) > max_bytes:
            esito.errori.append(f"{f.filename}: supera il limite di {max_mb} MB")
            continue
        destinazione = os.path.join(upload_dir, f"{ts}_{os.path.basename(f.filename)}")
        with open(destinazione, "wb") as out:
            out.write(contenuto)
        esito.caricati.append(f.filename)
    return esito


# ------------------------------------------------------------------ economici

def accetta_preventivo(contesto: ContestoPortale, id_preventivo: str) -> EsitoAzione:
    cliente = contesto.cliente
    preventivo, gp_prev = preventivo_del_cliente(cliente.id, id_preventivo)
    if preventivo is None:
        raise RisorsaNonTrovata(id_preventivo)
    stato = str(getattr(getattr(preventivo, "stato", None), "value", getattr(preventivo, "stato", "")))
    if stato not in STATI_PREVENTIVO_ACCETTABILI:
        return EsitoAzione(
            ok=False,
            messaggi=[("warning", "Questo preventivo non è in uno stato accettabile dal portale.")],
            sezione="economici",
        )
    if stato in {"ACCETTATO", "CONVERTITO"} and str(getattr(preventivo, "accettato_il", "") or "").strip():
        # L'accettazione è una prova (data, indirizzo, dispositivo): ripeterla la
        # sovrascriveva e riportava un preventivo convertito ad «accettato».
        return EsitoAzione(
            ok=True,
            messaggi=[("info", "Il preventivo risulta già accettato: resta valida l'accettazione registrata.")],
            sezione="economici",
        )
    _, conferimento = gp_prev.registra_accettazione_preventivo(
        id_preventivo,
        workflow_channel="ONLINE",
        via="PORTALE_CLIENTE",
        ip=_ip(),
        user_agent=_user_agent(),
        avvocato_referente=_avvocato_referente(cliente=cliente, preventivo=preventivo),
        auto_crea_conferimento=True,
        studio_piva=current_app.config.get("STUDIO_PIVA", ""),
        studio_cf=current_app.config.get("STUDIO_CF", ""),
        studio_indirizzo=current_app.config.get("STUDIO_INDIRIZZO", ""),
    )
    messaggi = [("success", "Preventivo accettato correttamente.")]
    if conferimento:
        messaggi.append(("success", "Il conferimento è stato predisposto automaticamente: puoi confermarlo dal portale."))
    return EsitoAzione(ok=True, messaggi=messaggi, sezione="economici")


def firma_conferimento(contesto: ContestoPortale, id_conferimento: str) -> EsitoAzione:
    from pct.workflow_commerciale import apri_fascicolo_automatico
    from web.helpers import get_fascicoli, get_scadenziario

    cliente = contesto.cliente
    conferimento, gp_prev = conferimento_del_cliente(cliente.id, id_conferimento)
    if conferimento is None:
        raise RisorsaNonTrovata(id_conferimento)
    preventivo = gp_prev.get_preventivo(conferimento.id_preventivo) if conferimento.id_preventivo else None
    # La firma già registrata è una prova: non si sovrascrive. Il passaggio
    # successivo (apertura della pratica dopo l'anagrafica completa) resta.
    if not getattr(conferimento, "firma_cliente_eseguita", False):
        gp_prev.registra_firma_conferimento(
            id_conferimento, via="PORTALE_CLIENTE", workflow_channel="ONLINE", ip=_ip(), user_agent=_user_agent(),
        )
    if cliente and not getattr(cliente, "profilo_completo_per_conferimento", True):
        return EsitoAzione(
            ok=True,
            messaggi=[("warning", "Conferimento firmato. Completa prima l'anagrafica per aprire la pratica in automatico.")],
            sezione="economici",
        )
    result = apri_fascicolo_automatico(
        gp=gp_prev,
        gf=get_fascicoli(),
        gs=get_scadenziario(),
        cliente=cliente,
        preventivo=preventivo,
        conferimento=gp_prev.get_conferimento(id_conferimento),
        avvocato=_avvocato_referente(cliente=cliente, preventivo=preventivo, conferimento=conferimento),
    )
    fasc = result["fascicolo"]
    return EsitoAzione(
        ok=True,
        messaggi=[(
            "success",
            f"Conferimento firmato. Fascicolo {fasc.numero} aperto automaticamente con checklist e scadenze iniziali.",
        )],
        sezione="home",
    )


# ------------------------------------------------------------------ anagrafica

def aggiorna_recapiti(contesto: ContestoPortale, valori: Mapping[str, Any]):
    """Solo cellulare, telefono ed email: gli altri dati li modifica lo studio.

    Come il modulo storico, i recapiti si aggiornano quando arriva il campo
    `cellulare`. Restituisce il cliente riletto dall'archivio.
    """
    from web.helpers import get_clienti

    cliente = contesto.cliente
    aggiornamenti: dict[str, Any] = {}
    if valori.get("cellulare") is not None:
        from pct.clienti import Recapiti

        rec = cliente.recapiti or Recapiti()
        rec.cellulare = str(valori.get("cellulare") or "").strip()
        rec.telefono = str(valori.get("telefono") or "").strip()
        rec.email = str(valori.get("email") or "").strip()
        aggiornamenti["recapiti"] = rec
    get_clienti().aggiorna(cliente.id, **aggiornamenti)
    contesto.cliente = get_clienti().get(cliente.id)
    return contesto.cliente


__all__ = [
    "ERRORE_CONSENSO",
    "ERRORE_NESSUN_FILE",
    "ERRORE_PRATICA",
    "EsitoAzione",
    "EsitoCaricamento",
    "RisorsaNonTrovata",
    "accetta_preventivo",
    "aggiorna_recapiti",
    "carica_documenti",
    "firma_conferimento",
    "registra_consenso_privacy",
]
