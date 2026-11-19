"""Pannelli pronti: la richiesta web di un pannello del fascicolo risponde dal payload salvato se le fonti non
sono cambiate, altrimenti calcola con il motore del pannello (l'unico), salva e risponde.

Regole:
- l'impronta delle fonti (``pct/pannelli_pronti/impronta.py``) si calcola PRIMA del motore: una scrittura che
  arriva durante il calcolo cambia l'impronta e il payload salvato non sarà più servito;
- la chiave comprende fascicolo, pannello, parametri normalizzati e profilo dei permessi dell'utente;
- una richiesta di scrittura riuscita sul fascicolo (POST/PUT/PATCH/DELETE) incrementa la generazione del
  fascicolo: nessun payload calcolato prima vale più;
- senza trigger preparati, senza utente o senza studio il pannello si calcola come prima, senza salvare.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from flask import current_app, g, has_request_context, request, session

from pct.pannelli_pronti import impronta as impronta_fonti
from pct.pannelli_pronti.archivio import NOME_FILE, ArchivioPannelli, Voce, chiave as chiave_voce
from web.services.pannelli_pronti_catalogo import (
    DIPENDENTI, PANNELLI_SENZA_DATA_DI_CONSULTAZIONE, PARAMETRI_IGNORATI_SEMPRE, PER_ENDPOINT, VERSIONE_PANNELLI,
    Pannello, impronta_del_pannello,
)

logger = logging.getLogger(__name__)
INTESTAZIONE = "X-Iusentra-Pannello"
SECONDI_TRA_RICHIESTE = 30
# Su cache mancante l'inventario legge subito i documenti già registrati.
_PANNELLI_IN_SFONDO = frozenset({"quadro", "lettura", "obblighi-notifica",
                               "scadenze", "letture", "catalogazione-documentale", "passaggi", "conto-economico"})
_INTESTAZIONE_ASINCRONA = "X-Iusentra-Preparazione"
AMBIENTE_RICALCOLO = "iusentra.pannelli_pronti.ricalcolo"
CHIAVI_SESSIONE = ("user_id", "auth_scope", "auth_tenant_slug", "tenant_slug", "superadmin_user_id")
_METODI_SCRITTURA = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_FASCICOLO_NEL_PERCORSO = re.compile(r"/fascicoli/([A-Za-z0-9_-]{4,64})(?:/|$)")
_PARAMETRI_ROTTA_FASCICOLO = ("id_fasc", "fascicolo_id", "id_fascicolo", "fid")


@dataclass(frozen=True)
class Contesto:
    archivio: ArchivioPannelli
    fonti: impronta_fonti.FontiTenant
    profilo: str
    sessione: dict


def file_fonti(data_paths: dict) -> tuple[str, ...]:
    """I file dello studio letti dai pannelli fuori da ``studio.db`` e dal registro delle letture."""
    from web.services.pannelli_pronti_fonti import file_dello_studio

    return file_dello_studio(data_paths)


def archivio_per_percorsi(data_paths: dict) -> ArchivioPannelli | None:
    studio_db = str((data_paths or {}).get("STUDIO_DB") or "")
    if not studio_db:
        return None
    return ArchivioPannelli(Path(studio_db).parent / "intelligence" / NOME_FILE)


def fonti_per_percorsi(data_paths: dict) -> impronta_fonti.FontiTenant | None:
    from web.services.pannelli_pronti_fonti import percorso_pec
    from web.services.registro_letture_runtime import percorso_registro

    studio_db = str((data_paths or {}).get("STUDIO_DB") or "")
    if not studio_db:
        return None
    return impronta_fonti.FontiTenant(studio_db=studio_db, registro_db=percorso_registro(data_paths),
                                      file=file_fonti(data_paths), pec_db=percorso_pec(data_paths))


def _profilo(utente: Any, tenant: str) -> str:
    try:
        permessi = list(getattr(utente, "permessi_effettivi", []) or [])
    except Exception:
        permessi = []
    ruolo = getattr(getattr(utente, "ruolo", ""), "value", getattr(utente, "ruolo", ""))
    grezzo = json.dumps([tenant, str(getattr(utente, "id", "")), str(ruolo), sorted(map(str, permessi)),
                         bool(getattr(utente, "is_admin", False))], ensure_ascii=False)
    return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()[:32]


def contesto_corrente() -> Contesto | None:
    if not has_request_context() or current_app.config.get("PANNELLI_PRONTI_DISATTIVI"):
        return None
    utente = getattr(g, "utente_corrente", None)
    data_paths = dict(getattr(g, "data_paths", {}) or {})
    tenant = str(getattr(g, "tenant_context_slug", "") or "")
    if utente is None or not data_paths or not tenant:
        return None
    archivio, fonti = archivio_per_percorsi(data_paths), fonti_per_percorsi(data_paths)
    if archivio is None or fonti is None:
        return None
    sessione = {k: session.get(k) for k in CHIAVI_SESSIONE if session.get(k)}
    return Contesto(archivio=archivio, fonti=fonti, profilo=_profilo(utente, tenant), sessione=sessione)


def _chiave_pannello(fascicolo_id: str, nome: str, parametri: str, profilo: str) -> str:
    if nome == "obblighi-notifica":
        from web.services.obblighi_notifica_fonti import VERSIONE

        parametri = f"{VERSIONE}\x1f{parametri}"
    elif nome == "redazione-atti-contesto":
        parametri = f"contesto-operativo:v3\x1f{parametri}"
    elif nome == "conto-economico":
        parametri = f"totale-parcella:v3\x1f{parametri}"
    return chiave_voce(fascicolo_id, nome, parametri, profilo)


def parametri_normalizzati(pannello: Pannello) -> str:
    ignorati = PARAMETRI_IGNORATI_SEMPRE | pannello.parametri_ignorati
    coppie = sorted((k, v) for k, v in request.args.items(multi=True) if k not in ignorati)
    return urlencode(coppie)


def impronta_attuale(contesto: Contesto, fascicolo_id: str, pannello: str = "") -> str | None:
    # Quadro, Lettura e Conto economico consultati nello stesso GET devono
    # riferirsi alla medesima revisione. Il worker verifica di nuovo prima di salvare.
    cache = None
    dipende_dal_giorno = pannello not in PANNELLI_SENZA_DATA_DI_CONSULTAZIONE
    chiave = (contesto.fonti, contesto.archivio.percorso, fascicolo_id, dipende_dal_giorno)
    if (has_request_context() and request.method == "GET"
            and not request.environ.get(AMBIENTE_RICALCOLO) and not calcolo_in_corso()):
        cache = g.get("_impronte_pannelli_correnti")
        if cache is None:
            cache = g._impronte_pannelli_correnti = {}
        if chiave in cache:
            return cache[chiave]
    try:
        generazione = contesto.archivio.generazione(fascicolo_id)
        impronta = impronta_fonti.impronta(contesto.fonti, fascicolo_id, generazione=generazione, versione=VERSIONE_PANNELLI,
                                          dipende_dal_giorno=dipende_dal_giorno)
    except Exception as exc:
        logger.warning("Impronta delle fonti del fascicolo %s non calcolata: %s", fascicolo_id, exc)
        return None
    if cache is not None and impronta is not None:
        cache[chiave] = impronta
    return impronta


def _risposta_salvata(stato: int, tipo: str, corpo: bytes, esito: str):
    risposta = current_app.response_class(corpo, status=stato, mimetype=tipo or "application/json")
    risposta.headers["Cache-Control"] = "no-store"
    risposta.headers[INTESTAZIONE] = esito
    return risposta


def richiedi_lettura_dal_quadro(fascicolo_id: str) -> bool:
    """Registra la stessa richiesta della Lettura, anche se il pannello è chiuso."""
    return richiedi_pannello_consultivo(fascicolo_id, "lettura")


def richiedi_pannello_consultivo(fascicolo_id: str, nome: str) -> bool:
    """Prepara il pannello richiesto come fonte di un'altra vista del fascicolo."""
    contesto = contesto_corrente()
    if contesto is None or not contesto.sessione:
        return False
    impronta = impronta_del_pannello(nome, impronta_attuale(contesto, fascicolo_id, nome))
    if impronta is None:
        return False
    tenant = str(getattr(g, "tenant_context_slug", "") or "single-studio")
    return _accoda_pannello_consultivo(contesto, tenant, fascicolo_id, nome, impronta)


def _accoda_pannello_consultivo(contesto: Contesto, tenant: str, fascicolo_id: str, nome: str, impronta: str) -> bool:
    from web.services.pannelli_pronti_catalogo import PANNELLI

    pannello = next(p for p in PANNELLI if p.nome == nome)
    chiave = _chiave_pannello(fascicolo_id, nome, "", contesto.profilo)
    try:
        voce = contesto.archivio.voce(chiave)
        soglia = (datetime.now(UTC) - timedelta(seconds=SECONDI_TRA_RICHIESTE)).isoformat(timespec="milliseconds")
        if not voce or voce.richiesto_il < soglia or voce.richiesto_il <= max(voce.calcolato_il, voce.servito_il):
            percorso = pannello.percorso.format(fid=fascicolo_id)
            contesto.archivio.registra_richiesta(
                chiave_voce=chiave, fascicolo_id=fascicolo_id, pannello=nome,
                percorso=percorso, profilo=contesto.profilo, sessione=contesto.sessione,
                servito=False, ritenta=bool(voce and voce.tentata == impronta), differibile=False,
            )
        from web.services.pannelli_pronti_calcolatore import sveglia_calcolatore

        sveglia_calcolatore(tenant, fascicolo_id)
    except (OSError, sqlite3.Error):
        logger.debug("Preparazione del pannello %s rinviata per %s", nome, fascicolo_id, exc_info=True)
    return True


def _ricomponi(pannello: Pannello, corpo: bytes, fascicolo_id: str, *, quadro_precedente: bool = False,
               accoda_lettura: bool = True) -> bytes:
    if not pannello.ricomponi:
        return corpo
    if pannello.ricomponi == "quadro_da_lettura":
        from web.services.fascicolo_quadro_runtime import (
            ROME_TZ,
            esito_dispositivo_da_lettura,
            prossimo_passo_da_lettura,
            riga_economia_materializzata,
            riga_notifiche_da_lettura,
            riga_termini_da_lettura,
        )
        from web.services.obblighi_notifica_sintesi import leggi as sintesi_obblighi
        from web.services.riscontri_processuali_runtime import lettura_consultiva

        dati = json.loads(corpo)
        lettura = lettura_consultiva(fascicolo_id)
        righe = {riga["tema"]: riga for riga in dati["righe"]}
        righe["prossimo_passo"] = prossimo_passo_da_lettura(lettura)
        oggi = datetime.now(ROME_TZ).date()
        agenda = dati.pop("termini_agenda", None)
        dati.pop("termini_agenda_versione", None)
        if quadro_precedente:
            # L'agenda e il catalogo del Quadro precedente potrebbero essere
            # superati. Mostra solo i riscontri ricomposti dalle fonti correnti.
            righe.pop("termini", None)
            if lettura is not None:
                righe["termini"] = riga_termini_da_lettura(None, lettura, oggi)
            righe.pop("documenti", None)
            dati["quadro_in_aggiornamento"] = True
        elif isinstance(agenda, list):
            righe["termini"] = riga_termini_da_lettura(agenda, lettura, oggi)
        if "notifiche" in righe:
            sintesi = sintesi_obblighi(fascicolo_id)
            righe["notifiche"] = riga_notifiche_da_lettura(sintesi, lettura, oggi)
        if "economia" in righe:
            economia = riga_economia_materializzata(fascicolo_id, lettura)
            if economia is not None:
                righe["economia"] = economia
            elif quadro_precedente:
                righe.pop("economia", None)
        dati.pop("lettura_mancante", None)
        dati["lettura_precedente"] = bool((lettura or {}).get("aggiornamento_pendente"))
        lettura_da_aggiornare = lettura is None or dati["lettura_precedente"]
        dati["lettura_in_preparazione"] = lettura_da_aggiornare and (
            richiedi_lettura_dal_quadro(fascicolo_id) if accoda_lettura else quadro_precedente
        )
        dati["esito_dispositivo"] = esito_dispositivo_da_lettura(lettura)
        dati["righe"] = list(righe.values())
        return json.dumps(dati, ensure_ascii=False).encode("utf-8")
    if pannello.ricomponi == "stato_presidi_lettura":
        from web.services.riscontri_processuali_runtime import aggiorna_stato_presidi

        dati = json.loads(corpo)
        lettura = dati.get("lettura") or {}
        prima = bool((lettura.get("verifiche") or {}).get("in_corso"))
        aggiorna_stato_presidi(lettura, fascicolo_id)
        return json.dumps(dati, ensure_ascii=False).encode("utf-8") if prima != bool(
            (lettura.get("verifiche") or {}).get("in_corso")
        ) else corpo
    if pannello.ricomponi == "fase_della_guida":
        if request.args.get("vista") != "scheda":
            return corpo
        from web.services.guida_fase_runtime import fase_per_la_guida
        from web.services.react_guida_pratica_bridge import collega_normativa_guida

        dati = json.loads(corpo)
        if dati.get("ok"):
            collega_normativa_guida(dati.get("guida"))
            dati["faseReale"] = fase_per_la_guida(fascicolo_id, consultiva=True)
            return json.dumps(dati, ensure_ascii=False).encode("utf-8")
        return corpo
    if pannello.ricomponi == "lettura_del_dettaglio":
        sezioni = request.args.get("include", "").lower().replace(";", " ").replace(",", " ").split()
        dati = json.loads(corpo)
        lettura = None
        if not sezioni or {"all", "lettura"}.intersection(sezioni):
            # Il dettaglio e il Quadro mostrano lo stesso esito consultivo mentre
            # le nuove fonti vengono elaborate.
            from web.services.riscontri_processuali_runtime import aggiorna_stato_presidi, lettura_consultiva

            lettura = lettura_consultiva(fascicolo_id)
            if lettura is not None:
                aggiorna_stato_presidi(lettura, fascicolo_id)
            dati["initialLettura"] = lettura
        include_scadenze = not sezioni or bool({"all", "scadenze"}.intersection(sezioni))
        if dati.get("activities") or "relata" in sezioni or include_scadenze:
            from web.services.pannelli_pronti_ricomposizione import (
                allinea_attivita_udienze, allinea_presidio_udienze, allinea_relata_al_riscontro,
            )

            if lettura is None:
                from web.services.riscontri_processuali_runtime import lettura_consultiva

                lettura = lettura_consultiva(fascicolo_id)
            allinea_attivita_udienze(dati, lettura)
            if include_scadenze:
                allinea_presidio_udienze(dati, lettura, fascicolo_id)
            if "relata" in sezioni:
                allinea_relata_al_riscontro(dati, lettura, fascicolo_id)
        corrente = lettura if lettura and not lettura.get("aggiornamento_pendente") else {}
        from pct.fascicolo_lettura._testo import data_da

        udienze = (corrente.get("ragionamento") or {}).get("udienze") or []
        prime_date = [(data, voce) for voce in udienze if voce.get("documento_id") and (data := data_da(voce.get("data")))]
        prima = min(prime_date, key=lambda voce: voce[0], default=None)
        if prima and isinstance(dati.get("profile"), list):
            from urllib.parse import quote
            from pct.formatting import format_date_it

            data_prima = format_date_it(prima[0])
            if data_prima:
                profilo = dati["profile"]
                indice = next((i for i, voce in enumerate(profilo)
                               if voce.get("label") in {"Prima udienza", "Prima udienza fissata"}), len(profilo))
                profilo[indice:indice + 1] = [{
                    "label": "Prima udienza fissata", "value": data_prima, "mono": False,
                    "href": f"/fascicoli/{quote(fascicolo_id, safe='')}/documenti/{quote(prima[1]['documento_id'], safe='')}/visualizza",
                }]
        valore = (corrente.get("intestazione") or {}).get("fonte_valore_causa") or {}
        if not valore and (dati.get("fascicolo") or {}).get("id") == fascicolo_id:
            from web.services.valore_causa_archivio import valore_iscrizione_corrente

            valore = valore_iscrizione_corrente(fascicolo_id)
        documento = valore.get("documento") or {}
        if documento.get("href"):
            from pct.formatting import format_euro_it

            importo = valore["importo"]
            importo_label = format_euro_it(importo)
            profilo = [voce for voce in dati.get("profile") or [] if voce.get("label") not in
                       {"Valore causa", "Valore causa all’iscrizione"}]
            dati["profile"] = [*profilo, {"label": "Valore causa all’iscrizione", "value": importo_label,
                                        "href": documento["href"], "mono": False}]
            dati.get("fascicolo", {}).update(value=importo_label, valueRaw=str(importo))
            for voce in dati.get("economics") or []:
                if voce.get("id") == "valore":
                    voce.update(value=importo_label, note="valore dichiarato all’iscrizione", href=documento["href"])
        return json.dumps(dati, ensure_ascii=False).encode("utf-8")
    from web.services import pannelli_pronti_ricomposizione

    return getattr(pannelli_pronti_ricomposizione, pannello.ricomponi)(corpo, fascicolo_id)


_CAMPI_REVISIONE = ("readRevision", "readRevisionContext", "readFailed")


def _conferma_revisione(pannello: Pannello) -> bool:
    return bool(pannello.domini_revisione) and request.args.get("confirm_revision") == "1"


def _istantanea_revisione(pannello: Pannello) -> dict:
    from web.services.operational_read_revision import read_authorized_revision_snapshot

    return read_authorized_revision_snapshot(g.get("utente_corrente"), requested_domains=set(pannello.domini_revisione))


def _con_revisione(corpo: bytes, istantanea: dict) -> bytes:
    """Payload salvato + revisione letta PRIMA di confermare l'impronta: il payload vale almeno fino a quella revisione."""
    dati = json.loads(corpo.decode("utf-8"))
    dati.update(readRevision=dict(istantanea["revisions"]), readRevisionContext=istantanea["context"], readFailed=False)
    return json.dumps(dati, ensure_ascii=False, default=str).encode("utf-8")


def _senza_revisione(corpo: bytes) -> bytes | None:
    """Il payload confermato senza i campi della revisione letta; ``None`` se la lettura non è riuscita."""
    dati = json.loads(corpo.decode("utf-8"))
    if not isinstance(dati, dict) or dati.get("readFailed") or not dati.get("readRevision"):
        return None
    for campo in _CAMPI_REVISIONE:
        dati.pop(campo, None)
    return json.dumps(dati, ensure_ascii=False, default=str).encode("utf-8")


def calcolo_in_corso() -> bool:
    """Vero mentre una vista calcola un pannello pronto: le cache interne della vista non vanno consultate."""
    return bool(has_request_context() and g.get("_pannelli_pronti_calcolo"))


def _calcola(vista: Callable[..., Any], args: tuple, kwargs: dict):
    """Esegue il motore del pannello registrando le letture non riuscite (``_safe`` dei bridge)."""
    precedenti = getattr(g, "_confirmed_projection_failures", None)
    fallimenti: list = [] if precedenti is None else precedenti
    g._confirmed_projection_failures = fallimenti
    g._pannelli_pronti_calcolo = True
    inizio = time.monotonic()
    try:
        risposta = current_app.make_response(vista(*args, **kwargs))
    finally:
        g._pannelli_pronti_calcolo = False
        g._confirmed_projection_failures = precedenti
    return risposta, int((time.monotonic() - inizio) * 1000), bool(fallimenti)


def _in_preparazione():
    risposta = _risposta_salvata(202, "application/json", b'{"stato":"in_preparazione"}', "in-preparazione")
    risposta.headers["Retry-After"] = "2"
    return risposta


def _risposta_consultiva_salvata(pannello: Pannello, voce: Voce | None, fascicolo_id: str, *,
                                 accoda_lettura: bool = True):
    if voce is None or not voce.corpo:
        return None
    corpo = bytes(voce.corpo)
    if not pannello.memorizzabile(corpo):
        return None
    if pannello.ricomponi == "quadro_da_lettura":
        corpo = _ricomponi(pannello, corpo, fascicolo_id, quadro_precedente=True, accoda_lettura=accoda_lettura)
        return _risposta_salvata(200, "application/json", corpo, "precedente")
    if pannello.ricomponi == "stato_presidi_lettura":
        ultimo = json.loads(corpo)
        ultimo["lettura"]["aggiornamento_pendente"] = True
        return _risposta_salvata(200, "application/json", json.dumps(ultimo, ensure_ascii=False).encode("utf-8"), "precedente")
    if pannello.nome == "conto-economico" and request.headers.get("X-Iusentra-Solo-Corrente") != "1":
        ultimo = json.loads(corpo)
        if (ultimo.get("riscontriProcessuali") or {}).get("stato") == "pronto":
            ultimo["aggiornamentoPendente"] = True
            ultimo["percorso"]["prossimoPasso"] = ""
            for passo in ultimo["percorso"]["passi"]:
                passo.pop("azione", None)
            return _risposta_salvata(200, "application/json", json.dumps(ultimo, ensure_ascii=False).encode("utf-8"), "precedente")
    return None


def servi(pannello: Pannello, vista: Callable[..., Any], args: tuple, kwargs: dict):
    fascicolo_id = str(kwargs.get(pannello.parametro_fascicolo) or "").strip()
    ricalcolo = bool(request.environ.get(AMBIENTE_RICALCOLO))
    contesto = contesto_corrente() if fascicolo_id else None
    if contesto is None or any(p in request.args for p in pannello.parametri_di_calcolo):
        return vista(*args, **kwargs)
    if not ricalcolo and pannello.ricomponi == "obblighi_da_lettura":
        from web.services.obblighi_notifica_sintesi import leggi_completi

        obblighi = leggi_completi(fascicolo_id)
        if obblighi is not None:
            # Passa sempre dalla vista autenticata: aggiunge le copie PST e i
            # riscontri consentiti all'utente, senza richiamare il motore.
            g._obblighi_notifica_pronti = (fascicolo_id, obblighi)
            risposta = current_app.make_response(vista(*args, **kwargs))
            if risposta.status_code == 200:
                risposta.headers[INTESTAZIONE] = "pronto"
                risposta.headers["Cache-Control"] = "no-store"
            return risposta
    conferma = _conferma_revisione(pannello)
    parametri = parametri_normalizzati(pannello)
    chiave = _chiave_pannello(fascicolo_id, pannello.nome, parametri, contesto.profilo)
    percorso = request.path + (("?" + parametri) if parametri else "")
    try:
        istantanea = _istantanea_revisione(pannello) if conferma and not ricalcolo else None
    except Exception:
        return vista(*args, **kwargs)
    impronta_fonti_correnti = impronta_attuale(contesto, fascicolo_id, pannello.nome)
    impronta = impronta_del_pannello(pannello.nome, impronta_fonti_correnti)
    if impronta is None:
        return vista(*args, **kwargs)
    differibile = (bool(contesto.sessione) and pannello.nome in _PANNELLI_IN_SFONDO
                   and request.headers.get(_INTESTAZIONE_ASINCRONA) == "sfondo")
    if not ricalcolo:
        voce = None
        try:
            voce = contesto.archivio.voce(chiave)
            valida = bool(voce and voce.impronta == impronta and voce.corpo is not None)
            if valida and pannello.nome == "redazione-atti-contesto":
                valida = pannello.memorizzabile(bytes(voce.corpo))
            if valida and pannello.ricomponi == "quadro_da_lettura":
                valida = json.loads(voce.corpo).get("termini_agenda_versione") == 2
            if valida and pannello.ricomponi == "lettura_del_dettaglio" and not request.args.get("include"):
                valida = json.loads(voce.corpo).get("agendaLoaded") is True
            soglia = (datetime.now(UTC) - timedelta(seconds=SECONDI_TRA_RICHIESTE)).isoformat(timespec="milliseconds")
            recente = bool(voce and voce.richiesto_il >= soglia)
            tentata = bool(voce and voce.tentata == impronta)
            if not valida and differibile and pannello.ricomponi == "stato_presidi_lettura":
                from web.blueprints.api_v1_react import lettura_preparata

                preparata = lettura_preparata(fascicolo_id)
                if preparata is not None:
                    corpo = _ricomponi(pannello, preparata, fascicolo_id)
                    return _risposta_salvata(200, "application/json", corpo, "pronto")
            fonte_da_accodare = (
                not valida and not tentata and pannello.ricomponi in {"stato_presidi_lettura", "quadro_da_lettura"}
                and voce is not None and voce.richiesto_il <= max(voce.calcolato_il, voce.servito_il)
            )
            if valida:
                corpo = _ricomponi(pannello, bytes(voce.corpo), fascicolo_id)
                if istantanea is not None:
                    corpo = _con_revisione(corpo, istantanea)
                risposta = _risposta_salvata(voce.stato, voce.tipo, corpo, "pronto")
                if not recente:
                    # La registrazione della consultazione è utile allo scheduler.
                    # Il commit SQLite non deve ritardare la consegna del pannello.
                    def registra_consultazione():
                        try:
                            contesto.archivio.registra_richiesta(
                                chiave_voce=chiave, fascicolo_id=fascicolo_id, pannello=pannello.nome,
                                percorso=percorso, profilo=contesto.profilo, sessione=contesto.sessione,
                                servito=True, differibile=False,
                            )
                        except (OSError, sqlite3.Error) as exc:
                            logger.debug("Consultazione pannello %s non registrata per %s: %s", pannello.nome, fascicolo_id, exc)

                    risposta.call_on_close(registra_consultazione)
                return risposta
            if differibile and pannello.ricomponi == "quadro_da_lettura":
                precedente = _risposta_consultiva_salvata(pannello, voce, fascicolo_id, accoda_lettura=False)
                if precedente is not None:
                    tenant = str(getattr(g, "tenant_context_slug", "") or "single-studio")
                    prepara_quadro = not recente or fonte_da_accodare
                    prepara_lettura = precedente.get_json()["lettura_in_preparazione"]
                    if prepara_quadro or prepara_lettura:
                        # Il commit di una scrittura può attendere il disco
                        # anche quando il risultato è già disponibile.
                        def accoda_dopo_consegna():
                            if prepara_quadro:
                                try:
                                    contesto.archivio.registra_richiesta(
                                        chiave_voce=chiave, fascicolo_id=fascicolo_id, pannello=pannello.nome,
                                        percorso=percorso, profilo=contesto.profilo, sessione=contesto.sessione,
                                        servito=False, ritenta=tentata, differibile=True,
                                    )
                                except (OSError, sqlite3.Error):
                                    logger.debug("Richiesta Quadro rinviata per %s", fascicolo_id, exc_info=True)
                            if prepara_lettura:
                                _accoda_pannello_consultivo(
                                    contesto, tenant, fascicolo_id, "lettura",
                                    impronta_del_pannello("lettura", impronta_fonti_correnti),
                                )
                            else:
                                from web.services.pannelli_pronti_calcolatore import sveglia_calcolatore

                                try:
                                    sveglia_calcolatore(tenant, fascicolo_id)
                                except OSError:
                                    logger.warning("Avvio immediato del calcolatore non riuscito", exc_info=True)

                        precedente.call_on_close(accoda_dopo_consegna)
                    return precedente
            if not recente or fonte_da_accodare or not differibile:
                try:
                    contesto.archivio.registra_richiesta(
                        chiave_voce=chiave, fascicolo_id=fascicolo_id, pannello=pannello.nome,
                        percorso=percorso, profilo=contesto.profilo, sessione=contesto.sessione,
                        servito=False, ritenta=tentata, differibile=differibile,
                    )
                except sqlite3.OperationalError as exc:
                    if differibile:
                        raise
                    logger.debug("Richiesta pannello %s non registrata per %s: %s", pannello.nome, fascicolo_id, exc)
            if differibile and tentata and recente:
                return _risposta_salvata(503, "application/json",
                                        b'{"ok":false,"message":"Preparazione del pannello non riuscita. Riprova tra poco."}', "errore")
            if differibile:
                if pannello.nome == "conto-economico":
                    from web.services.riscontri_processuali_runtime import lettura_materializzata

                    if lettura_materializzata(fascicolo_id) is None:
                        richiedi_lettura_dal_quadro(fascicolo_id)
                        return _risposta_consultiva_salvata(pannello, voce, fascicolo_id) or _in_preparazione()
                from web.services.pannelli_pronti_calcolatore import sveglia_calcolatore

                try:
                    sveglia_calcolatore(str(getattr(g, "tenant_context_slug", "") or "single-studio"), fascicolo_id)
                except OSError:
                    logger.warning("Avvio immediato del calcolatore non riuscito", exc_info=True)
                return _risposta_consultiva_salvata(pannello, voce, fascicolo_id) or _in_preparazione()
        except sqlite3.OperationalError as exc:
            logger.warning("Archivio pannelli non disponibile per %s: %s", fascicolo_id, exc)
            if differibile:
                return _risposta_consultiva_salvata(pannello, voce, fascicolo_id) or _in_preparazione()
            return vista(*args, **kwargs)
        except Exception as exc:
            logger.warning("Pannelli pronti non consultabili per %s: %s", fascicolo_id, exc)
            return vista(*args, **kwargs)
    risposta, durata, letture_fallite = _calcola(vista, args, kwargs)
    if risposta.is_streamed or risposta.direct_passthrough:
        return risposta
    corpo = risposta.get_data() if risposta.status_code == 200 else b""
    if conferma and corpo:
        corpo = _senza_revisione(corpo) or b""
    if risposta.status_code != 200 or letture_fallite or not corpo or not pannello.memorizzabile(corpo):
        # Un dipendente può attendere la sua fonte. È una preparazione, non
        # un errore definitivo per questa impronta.
        if ricalcolo and risposta.headers.get(INTESTAZIONE) != "in-preparazione":
            try:
                contesto.archivio.segna_tentativo(chiave_voce=chiave, fascicolo_id=fascicolo_id, pannello=pannello.nome,
                                                  percorso=percorso, profilo=contesto.profilo, impronta=impronta,
                                                  motivo=f"risposta {risposta.status_code} non salvabile"
                                                         + (" (letture non riuscite)" if letture_fallite else ""))
            except Exception:
                logger.debug("Tentativo del pannello %s non registrato", pannello.nome)
        return risposta
    if ricalcolo and impronta_del_pannello(pannello.nome, impronta_attuale(contesto, fascicolo_id, pannello.nome)) != impronta:
        return risposta
    try:
        salvato = contesto.archivio.salva(chiave_voce=chiave, fascicolo_id=fascicolo_id, pannello=pannello.nome,
                                percorso=percorso, profilo=contesto.profilo, impronta=impronta,
                                stato=risposta.status_code, tipo=risposta.mimetype, corpo=corpo, durata_ms=durata,
                                timeout=10 if ricalcolo else 0, dipendenti=DIPENDENTI.get(pannello.nome, ()))
        if salvato:
            risposta.headers[INTESTAZIONE] = "calcolato"
        elif ricalcolo:
            contesto.archivio.segna_tentativo(chiave_voce=chiave, fascicolo_id=fascicolo_id, pannello=pannello.nome,
                                              percorso=percorso, profilo=contesto.profilo, impronta=impronta,
                                              motivo="payload troppo grande")
    except Exception as exc:
        logger.warning("Pannello %s del fascicolo %s non salvato: %s", pannello.nome, fascicolo_id, exc)
    if pannello.ricomponi == "lettura_del_dettaglio" or (
        not ricalcolo and pannello.ricomponi in {"obblighi_da_lettura", "attivita_da_lettura", "relata_da_lettura", "fase_della_guida"}
    ):
        risposta.set_data(_ricomponi(pannello, risposta.get_data(), fascicolo_id))
    elif pannello.ricomponi == "quadro_da_lettura":
        dati = json.loads(corpo)
        dati.pop("termini_agenda", None)
        dati.pop("termini_agenda_versione", None)
        lettura_mancante = dati.pop("lettura_mancante", False) or dati.get("lettura_precedente", False)
        dati["lettura_in_preparazione"] = bool(
            lettura_mancante and not ricalcolo and richiedi_lettura_dal_quadro(fascicolo_id)
        )
        risposta.set_data(json.dumps(dati, ensure_ascii=False).encode("utf-8"))
    return risposta


def pannello_pronto(pannello: Pannello) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decoratore: la vista del pannello risponde dal salvato quando le fonti non sono cambiate."""

    def decoratore(vista: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(vista)
        def involucro(*args: Any, **kwargs: Any):
            if request.method != "GET":
                return vista(*args, **kwargs)
            return servi(pannello, vista, args, kwargs)

        involucro.pannello_pronto = pannello  # type: ignore[attr-defined]
        return involucro

    return decoratore


def fascicolo_della_richiesta() -> str:
    for nome in _PARAMETRI_ROTTA_FASCICOLO:
        valore = str((request.view_args or {}).get(nome) or "").strip()
        if valore:
            return valore
    corrispondenza = _FASCICOLO_NEL_PERCORSO.search(request.path or "")
    return corrispondenza.group(1) if corrispondenza else ""


def impronta_fascicolo_corrente(fascicolo_id: str, pannello: str = "") -> str | None:
    """L'impronta delle fonti del fascicolo nello studio della richiesta (anche senza utente, per le cache derivate)."""
    if not has_request_context() or not fascicolo_id:
        return None
    data_paths = dict(getattr(g, "data_paths", {}) or {})
    archivio, fonti = archivio_per_percorsi(data_paths), fonti_per_percorsi(data_paths)
    if archivio is None or fonti is None:
        return None
    try:
        generazione = archivio.generazione(fascicolo_id) if Path(archivio.percorso).exists() else 0
        return impronta_fonti.impronta(fonti, str(fascicolo_id), generazione=generazione, versione=VERSIONE_PANNELLI,
                                      dipende_dal_giorno=pannello not in PANNELLI_SENZA_DATA_DI_CONSULTAZIONE)
    except Exception:
        return None


def pannello_valido(fascicolo_id: str, pannello: str) -> bytes | None:
    """Il payload salvato di un pannello del fascicolo ancora valido per le fonti attuali (per i pannelli che lo leggono)."""
    impronta = impronta_del_pannello(pannello, impronta_fascicolo_corrente(fascicolo_id, pannello))
    archivio = archivio_per_percorsi(dict(getattr(g, "data_paths", {}) or {})) if impronta else None
    if archivio is None or not Path(archivio.percorso).exists():
        return None
    try:
        return archivio.ultimo_valido(str(fascicolo_id), pannello, impronta)
    except Exception:
        return None


def pannello_del_profilo(fascicolo_id: str, pannello: str, *, precedente: bool = False) -> bytes | None:
    """Legge il payload per il profilo corrente."""
    voce = voce_del_profilo(fascicolo_id, pannello, precedente=precedente)
    return bytes(voce.corpo) if voce and voce.corpo else None


def voce_del_profilo(fascicolo_id: str, pannello: str, *, precedente: bool = False) -> Voce | None:
    """Legge la proiezione e la sua provenienza temporale per il profilo corrente."""
    contesto = contesto_corrente()
    if contesto is None or not Path(contesto.archivio.percorso).exists():
        return None
    impronta = None if precedente else impronta_del_pannello(pannello, impronta_attuale(contesto, fascicolo_id, pannello))
    if impronta is None and not precedente:
        return None
    try:
        voce = contesto.archivio.voce(_chiave_pannello(fascicolo_id, pannello, "", contesto.profilo))
        if voce and voce.corpo and (precedente or voce.impronta == impronta):
            return voce
        return None
    except Exception:
        logger.warning("Pannello %s del profilo non disponibile per %s", pannello, fascicolo_id)
        return None


def segnala_scrittura_fascicolo(fascicolo_id: str) -> None:
    """Invalida e rimette in coda i pannelli dopo una scrittura riuscita, anche dal worker."""
    if not fascicolo_id or not has_request_context():
        return
    try:
        archivio = archivio_per_percorsi(dict(getattr(g, "data_paths", {}) or {}))
        if archivio is not None:
            archivio.invalida_fascicolo(fascicolo_id)
            archivio.segnala_fonti_aggiornate(fascicolo_id)
    except Exception as exc:
        logger.warning("Invalidazione dei pannelli dopo la scrittura non riuscita: %s", exc)


def invalida_dopo_scrittura(risposta):
    """after_request: una scrittura riuscita sul fascicolo invalida subito i suoi pannelli."""
    if request.method in _METODI_SCRITTURA and risposta.status_code < 400:
        fascicolo_id = fascicolo_della_richiesta()
        if fascicolo_id not in {"nuovo", "preferenze-filtri", "archivio", "presidio-economico"}:
            segnala_scrittura_fascicolo(fascicolo_id)
    return risposta


def avvolgi_viste(app) -> list[str]:
    """Applica il decoratore alle viste dei pannelli registrate nell'app; restituisce gli endpoint avvolti."""
    avvolti = []
    for endpoint, pannello in PER_ENDPOINT.items():
        vista = app.view_functions.get(endpoint)
        if vista is None or getattr(vista, "pannello_pronto", None):
            continue
        app.view_functions[endpoint] = pannello_pronto(pannello)(vista)
        avvolti.append(endpoint)
    return avvolti
