"""Passaggi spiegabili e regole dello studio dentro l'applicazione Flask.

Qui il dominio ``pct/passaggi`` incontra lo studio corrente: il database delle
regole accanto al registro delle letture (stesso tenant, stesso DSN
PostgreSQL se configurato), i dati del fascicolo letti dagli stessi gestori
della Lettura, l'utente che corregge. Le GET consultano e registrano solo la
prima applicazione di una regola a un caso (audit); nessuna lettura di
documenti o PEC avviene qui: i termini PEC arrivano già estratti dal presidio.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from flask import current_app, g, has_app_context, has_request_context

from pct.passaggi import CorrezioneRifiutata, Passaggio, applica_regole, regola_da_correzione
from pct.passaggi.fascicolo import passaggi_del_fascicolo
from pct.passaggi.repository import RegoleStudioError, RegoleStudioRepository

ROME_TZ = ZoneInfo("Europe/Rome")
CHIAVE_PERCORSO = "REGOLE_STUDIO_DB"
logger = logging.getLogger(__name__)


def oggi_roma() -> date:
    return datetime.now(ROME_TZ).date()


def percorso_regole(paths: Mapping[str, Any] | None = None) -> str:
    mappa = dict(paths or {})
    if not mappa and has_request_context():
        mappa = dict(getattr(g, "data_paths", {}) or {})
    if not mappa and has_app_context():
        mappa = {CHIAVE_PERCORSO: current_app.config.get(CHIAVE_PERCORSO, ""), "FASCICOLI_DB": current_app.config.get("FASCICOLI_DB", "")}
    esplicito = str(mappa.get(CHIAVE_PERCORSO) or "").strip()
    if esplicito:
        return esplicito
    fascicoli = str(mappa.get("FASCICOLI_DB") or "./data/fascicoli/fascicoli.json").strip()
    return str(Path(fascicoli).resolve().parent.parent / "intelligence" / "regole_studio.db")


def _dsn() -> str:
    try:
        from pct.postgres_runtime_support import resolve_runtime_postgres_dsn

        return resolve_runtime_postgres_dsn(env_url_keys=("IUSENTRA_REGOLE_STUDIO_DSN",))
    except Exception:
        return ""


def tenant_corrente() -> str:
    from web.services.registro_letture_runtime import tenant_corrente as tenant

    return tenant()


def repository_corrente() -> RegoleStudioRepository:
    return RegoleStudioRepository(percorso_regole(), tenant_id=tenant_corrente(), postgres_dsn=_dsn())


def utente_corrente() -> tuple[str, str]:
    utente = g.get("utente_corrente") if has_request_context() else None
    identificativo = str(getattr(utente, "id", "") or getattr(utente, "username", "") or "").strip()
    nome = str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or identificativo).strip()
    return identificativo or "api-key", nome or "accesso tramite chiave API"


def _scadenza(voce: Any) -> dict[str, Any]:
    valore = lambda nome: getattr(getattr(voce, nome, ""), "value", getattr(voce, nome, ""))  # noqa: E731
    return {nome: str(valore(nome) or "") for nome in (
        "id", "titolo", "descrizione", "stato", "note", "id_fascicolo", "deadline_profile_code", "operational_due_at", "data_scadenza",
    )} | {"data": str(getattr(voce, "data_scadenza", "") or getattr(voce, "data", "") or "")}


def _parti_delle_note(fascicolo: Any, parti: list[tuple[Any, Any]]) -> dict[str, str]:
    from pct.notifiche_legali import nome_avvocatura_stato

    controparte = str(getattr(fascicolo, "controparte", "") or "").strip()
    nomi = {"controparte": set(), "difensore_controparte": set()}
    for parte, soggetto in parti:
        ruolo = getattr(parte.ruolo, "value", parte.ruolo)
        nome = str(getattr(soggetto, "nome_completo", "") or getattr(soggetto, "ragione_sociale", "") or "").strip()
        if nome and ruolo == "CONTROPARTE" and not nome_avvocatura_stato(nome):
            nomi["controparte"].add(nome)
        if nome and ruolo == "DIFENSORE_CONTROPARTE":
            nomi["difensore_controparte"].add(nome)
    if controparte:
        chiave = "difensore_controparte" if nome_avvocatura_stato(controparte) else "controparte"
        if not nomi[chiave]:
            nomi[chiave].add(controparte)
    difensore_registrato = str(getattr(fascicolo, "avvocato_controparte", "") or "").strip()
    if difensore_registrato and not nomi["difensore_controparte"]:
        nomi["difensore_controparte"].add(difensore_registrato)
    return {campo: next(iter(valori)) if len(valori) == 1 else "" for campo, valori in nomi.items()}


def dati_del_fascicolo(fascicolo_id: str) -> dict[str, Any] | None:
    """Fascicolo, scadenze e termini proposti dal presidio PEC, dagli stessi gestori della Lettura (tenant della richiesta)."""
    from lex.context.fascicolo_lettura_context import _fascicolo_dict
    from web.helpers import get_fascicoli, get_scadenziario, get_soggetti
    from web.services.riscontri_processuali_runtime import lettura_materializzata

    fascicolo = get_fascicoli().get(str(fascicolo_id or "").strip())
    if fascicolo is None:
        return None
    try:
        scadenze = [_scadenza(voce) for voce in get_scadenziario().tutte(id_fascicolo=str(fascicolo.id), solo_aperte=False)]
    except Exception as exc:
        logger.warning("Scadenze del fascicolo %s non disponibili per i passaggi: %s", fascicolo_id, exc)
        scadenze = []
    lettura = lettura_materializzata(fascicolo_id)
    quadro_pec = (lettura or {}).get("pec") or {}
    termini = quadro_pec.get("termini_da_registrare") or []
    ragionamento = (lettura or {}).get("ragionamento") or {}
    conclusioni = None if lettura is None else (ragionamento.get("conclusioni") or [])
    try:
        parti = get_soggetti().parti_fascicolo(str(fascicolo.id))
    except Exception:
        parti = []
    return {"fascicolo": _fascicolo_dict(fascicolo), "fascicolo_originale": fascicolo, "parti_note": _parti_delle_note(fascicolo, parti), "scadenze": scadenze, "termini_pec": termini,
            "conclusioni": conclusioni, "lettura": lettura}


def passaggi_software(dati: dict[str, Any], *, oggi: date | None = None) -> list[Passaggio]:
    return passaggi_del_fascicolo(
        dati["fascicolo"], scadenze=dati["scadenze"], termini_pec=dati["termini_pec"],
        oggi=oggi or oggi_roma(), conclusioni=dati.get("conclusioni", ()),
    )


def passaggi_con_regole(dati: dict[str, Any], *, repository: RegoleStudioRepository, oggi: date | None = None) -> list[Passaggio]:
    """I passaggi del software corretti dalle regole dello studio; la prima applicazione a ogni caso va nel diario."""
    passaggi = passaggi_software(dati, oggi=oggi)
    regole = repository.attive_per({passaggio.regola_id for passaggio in passaggi})
    corretti, applicazioni = applica_regole(passaggi, regole)
    try:
        repository.registra_applicazioni(applicazioni)
    except Exception as exc:  # la vista resta corretta anche se il diario non si scrive
        logger.warning("Applicazioni delle regole dello studio non registrate: %s", exc)
    return corretti


def payload_passaggi(fascicolo_id: str) -> dict[str, Any] | None:
    dati = dati_del_fascicolo(fascicolo_id)
    if dati is None:
        return None
    passaggi = passaggi_con_regole(dati, repository=repository_corrente())
    bozze = _bozze_preparate(dati, passaggi)
    return {"passaggi": [passaggio.come_dizionario() for passaggio in passaggi], "totale": len(passaggi),
            "bozzeNote": bozze, "lettura_in_preparazione": dati.get("conclusioni", ()) is None}


def _ricorso_citato_senza_allegato(lettura: dict[str, Any]) -> dict[str, str] | None:
    """Segnala la busta provata quando nel fascicolo manca una copia leggibile del ricorso."""
    import re

    if any(
        atto.get("appartenenza") == "causa"
        and atto.get("natura") in {"atto_principale", "atto_difensivo"}
        and re.search(r"\bricorso\b", str(atto.get("etichetta") or ""), re.I)
        for atto in (lettura.get("ragionamento") or {}).get("atti") or ()
    ):
        return None
    candidati = {
        str(voce["identificativo_busta"]): {
            "busta": str(voce["identificativo_busta"]),
            "atto": str(voce["atto"]),
            "data": str(voce.get("data_accettazione") or ""),
        }
        for voce in (lettura.get("depositi") or {}).get("perfezionati") or ()
        if voce.get("portale") == "PEC_PCT" and voce.get("stato") == "ACCETTATO_CANCELLERIA"
        and voce.get("identificativo_busta")
        and voce.get("documenti") == 0
        and re.match(r"ricorso\b", str(voce.get("atto") or "").strip(), re.I)
    }
    return next(iter(candidati.values())) if len(candidati) == 1 else None


def _bozze_preparate(dati: dict[str, Any], passaggi: list[Passaggio]) -> dict[str, dict[str, Any]]:
    from pct.note_127_ter.bozza import campi_note_mancanti, proposte_note, sezione_del_provvedimento, testo_note
    from pct.passaggi.produttori.note_127_ter import REGOLA_BOZZA
    from web.services.archivio_letture_runtime import testi_indice_archivio

    lettura = dati.get("lettura")
    proposte = {p["termine"]: p for p in proposte_note(lettura, oggi_roma())}
    if not proposte:
        return {}
    fascicolo = dati["fascicolo"]
    originale = dati.get("fascicolo_originale")
    testi_indicizzati = {}
    if originale is not None:
        try:
            testi_indicizzati = testi_indice_archivio(originale, documento_ids={p["documento_id"] for p in proposte.values()})
        except Exception:
            logger.warning("Indice dei provvedimenti non disponibile per la bozza del fascicolo %s", originale.id)
    parti = dati.get("parti_note") or {}
    ricorso_da_acquisire = _ricorso_citato_senza_allegato(lettura)
    rg = str((lettura.get("intestazione") or {}).get("rg") or "").removeprefix("RG ").removeprefix("R.G. ")
    bozze = {}
    for passaggio in passaggi:
        if passaggio.regola_id != REGOLA_BOZZA or passaggio.stato != "proposto":
            continue
        campo = passaggio.campi.get("termine_note")
        proposta = proposte.pop(campo.valore, None) if campo else None
        if proposta is not None:
            sezione_del_decreto = sezione_del_provvedimento(testi_indicizzati.get(proposta["documento_id"], ""))
            dati_modello = {
                "ufficio": str(fascicolo.get("tribunale") or ""), "rg": rg,
                "giudice": str(fascicolo.get("giudice") or ""), "parte": str(fascicolo.get("cliente") or ""),
                "controparte": parti.get("controparte", str(fascicolo.get("controparte") or "")),
                "difensore_controparte": parti.get("difensore_controparte", ""),
                "difensore": str(fascicolo.get("avvocato_referente") or ""),
                "sezione": sezione_del_decreto or str(fascicolo.get("sezione") or ""),
            }
            testo = testo_note(proposta, **dati_modello)
            bozze[passaggio.chiave] = {
                **proposta, "testo": testo, "campi_da_completare": campi_note_mancanti(testo),
                "dati_modello": dati_modello,
                **({"sezione_provvedimento": sezione_del_decreto} if sezione_del_decreto else {}),
                **({"ricorso_da_acquisire": ricorso_da_acquisire} if ricorso_da_acquisire else {}),
            }
    return bozze


def _impagina_bozza_note(
    testo: str, *, proposta: dict[str, Any] | None = None, fascicolo_id: str = "", cliente_id: str = "",
    schema_studio: bool = False,
) -> str:
    import re
    from lxml import etree, html
    from pct.editor_ai.editor_renderer import legal_markdown_to_editor_html
    from pct.note_127_ter.bozza import testo_note, testo_note_studio
    from pct.procedura_fasi.fonti import FONTI
    from web.blueprints.template_atti import _compiled_editor_html_builder

    campi: dict[str, tuple[str, str]] = {}

    def associa(chiave: str, valore: str) -> str:
        token = f"IULINKEDNOTE{len(campi)}END"
        campi[token] = (chiave, valore)
        return token

    sorgente = testo
    if schema_studio:
        sorgente = testo_note_studio(associa)
    elif proposta and proposta.get("dati_modello"):
        sorgente = testo_note(proposta, associa=associa, **proposta["dati_modello"])
    corpo = html.fragment_fromstring(legal_markdown_to_editor_html(sorgente), create_parent="div")
    for blocco in corpo:
        contenuto = " ".join(blocco.text_content().split())
        if blocco.tag == "h1":
            stile = "text-align:center;font-size:18pt;font-weight:bold"
        elif blocco.tag == "h2" or contenuto.startswith("R.G. ") or contenuto in {"Per", "contro"}:
            stile = "text-align:center;font-size:14pt;font-weight:bold"
        elif contenuto.strip("*").startswith(("Giudice: ", "Udienza del ")):
            blocco.text = contenuto.strip("*")
            stile = "text-align:center;font-style:italic"
            if contenuto.strip("*").startswith("Udienza del "):
                stile += ";text-decoration:underline"
        else:
            stile = "text-align:justify"
        if schema_studio:
            if contenuto.startswith("*") or contenuto.startswith("R.G. ") or contenuto in {"Trattazione scritta", "Per"}:
                stile = "text-align:center;font-size:14pt;font-weight:bold;font-style:italic"
                if contenuto.startswith("*"):
                    blocco.text = contenuto.strip("*")
                    if contenuto.startswith("*Udienza del"):
                        stile = "text-align:center;font-size:12pt;font-style:italic"
            elif contenuto == "CONCLUSIONI":
                stile = "text-align:center;font-size:16pt;font-weight:bold"
            elif contenuto.startswith("✻"):
                blocco.text = "*" * len(contenuto)
                stile = "text-align:center;font-size:14pt"
            elif " | " in contenuto:
                sinistra, destra = contenuto.split(" | ", 1)
                blocco.tag = "table"
                blocco.text = None
                riga = etree.SubElement(etree.SubElement(blocco, "tbody"), "tr")
                for valore, allineamento in ((sinistra, "left"), (destra, "right")):
                    cella = etree.SubElement(riga, "td", style="width:50%;border:0;padding:0")
                    paragrafo = etree.SubElement(cella, "p", style=f"text-align:{allineamento};margin:0;font-style:italic")
                    paragrafo.text = valore
                stile = "width:100%;border:0"
            if stile.startswith("text-align:center"):
                # I titoli Word predefiniti aggiungono colore e interlinea propri.
                # La testata delle note dello studio è in nero con righe compatte.
                stile += ";color:#000000;line-height:1.15"
        blocco.set("style", stile + ";margin:0")
    norma = "art. 127-ter c.p.c."
    pattern = re.compile("|".join(map(re.escape, [*campi, norma])))
    for nodo in list(corpo.iterdescendants()):
        # Il renderer può racchiudere il testo in strong/em: si sostituiscono
        # i soli segmenti, preservando il capoverso e la formattazione nativa.
        for attributo in ("text", "tail"):
            segmenti = list(pattern.finditer(getattr(nodo, attributo) or ""))
            if not segmenti:
                continue
            origine = getattr(nodo, attributo)
            setattr(nodo, attributo, origine[:segmenti[0].start()])
            padre = nodo if attributo == "text" else nodo.getparent()
            posizione = 0 if attributo == "text" else padre.index(nodo) + 1
            for indice, segmento in enumerate(segmenti):
                valore = segmento.group()
                if valore in campi:
                    chiave, testo_campo = campi[valore]
                    elemento = html.Element("span", attrib={
                        "data-iu-linked-field": chiave, "data-iu-linked-matter": fascicolo_id,
                        "data-iu-linked-client": cliente_id, "contenteditable": "false",
                    })
                    if schema_studio and chiave == "note_127ter.udienza":
                        elemento.set("data-iu-date-format", "dots")
                    elemento.text = testo_campo
                else:
                    elemento = html.Element("a", href=FONTI["cpc_127ter"]["url"])
                    elemento.text = norma
                fine = segmenti[indice + 1].start() if indice + 1 < len(segmenti) else len(origine)
                elemento.tail = origine[segmento.end():fine]
                padre.insert(posizione + indice, elemento)
    frammento = "".join(html.tostring(blocco, encoding="unicode") for blocco in corpo)
    # Profilo misurato sull'atto dello studio già depositato nel RG 7646/2023.
    stile = {
        "font_family": "times_new_roman", "heading_font_family": "times_new_roman", "font_size_pt": 12, "line_height": 2,
        "text_align": "justify", "margin_left_mm": 20, "margin_right_mm": 19, "margin_top_mm": 25, "margin_bottom_mm": 22,
    }
    return _compiled_editor_html_builder(testo, frammento, stile)(testo)


def _marcatore_bozza_note(chiave: str, fonte: Any) -> str:
    from hashlib import sha256

    impronta = fonte.hash_contenuto_sha256 or fonte.hash_sha256
    if not impronta:
        raise ValueError("Il provvedimento non ha ancora un’impronta verificabile.")
    return "bozza-note:" + sha256(f"{chiave}:{fonte.id}:{impronta}".encode()).hexdigest()


def modello_da_bozza_note(fascicolo: Any, documento: Any) -> str:
    """Ricostruisce i campi del modello dal provvedimento collegato alla bozza storica."""
    import json
    from web.services.pannelli_pronti_runtime import pannello_del_profilo
    from web.services.riscontri_processuali_runtime import risultato_materializzato

    if documento.fonte_documento != "BOZZA_NOTE_127_TER":
        raise ValueError("Il documento non è una bozza di note generata dal fascicolo.")
    documenti = {doc.id: doc for doc in fascicolo.documenti}
    archivio = risultato_materializzato(fascicolo.id, "passaggi")
    if archivio is None:
        # Il salvataggio trasforma i dati del fascicolo in segnaposto. Per lo
        # schema storico basta l'impronta del provvedimento ancora presente.
        precedente = pannello_del_profilo(fascicolo.id, "passaggi", precedente=True)
        archivio = json.loads(precedente) if precedente else {}
    corrispondenze = []
    for chiave, proposta in (archivio.get("bozzeNote") or {}).items():
        fonte = documenti.get(proposta.get("documento_id"))
        if fonte and proposta.get("dati_modello") and (fonte.hash_contenuto_sha256 or fonte.hash_sha256):
            if _marcatore_bozza_note(chiave, fonte) in (documento.tags or ()):
                corrispondenze.append(proposta)
    if len(corrispondenze) != 1:
        raise ValueError("Il provvedimento della bozza non è più univoco o la Lettura è in aggiornamento.")
    proposta = corrispondenze[0]
    return _impagina_bozza_note(proposta["testo"], schema_studio=True)


def dati_collegati_note(fascicolo_id: str) -> dict[str, str]:
    """Una sola proposta corrente può compilare i dati di un modello di note."""
    from web.services.riscontri_processuali_runtime import risultato_materializzato

    archivio = risultato_materializzato(fascicolo_id, "passaggi") or {}
    proposte = list((archivio.get("bozzeNote") or {}).values())
    if len(proposte) != 1 or not proposte[0].get("dati_modello"):
        return {}
    return _dati_modello_note(proposte[0])


def chiave_bozza_note(pannello: dict[str, Any], documento_id: str, termine_iso: str) -> str:
    """Identifica la bozza già preparata per il termine dello stesso provvedimento."""
    if not documento_id or not termine_iso:
        return ""
    chiavi = [
        chiave for chiave, proposta in (pannello.get("bozzeNote") or {}).items()
        if proposta.get("documento_id") == documento_id and proposta.get("termine") == termine_iso
    ]
    return chiavi[0] if len(chiavi) == 1 else ""


def _dati_modello_note(proposta: dict[str, Any]) -> dict[str, str]:
    from pct.formatting import format_date_it
    from pct.note_127_ter.bozza import termine_nelle_note

    return {
        **proposta["dati_modello"],
        "sezione": proposta.get("sezione_provvedimento") or proposta["dati_modello"].get("sezione", ""),
        "udienza_sostituita": format_date_it(proposta["udienza_sostituita"]) if proposta.get("udienza_sostituita") else "",
        "termine_deposito": termine_nelle_note(proposta),
    }


def _compila_bozza_note(preparata: dict[str, Any], fascicolo: Any) -> str:
    from pct.editor_linked_fields import linked_fields_catalog, template_linked_html
    from web.helpers import get_clienti
    from web.services.editor_studio_context import studio_context_for_editor

    if not preparata.get("dati_modello"):
        return _impagina_bozza_note(preparata["testo"])

    utente = g.get("utente_corrente")
    cliente = None
    if fascicolo.id_cliente and utente and utente.ha_permesso("clienti.leggi"):
        cliente = get_clienti().get(fascicolo.id_cliente)
    campi = linked_fields_catalog(
        cliente=cliente, fascicolo=fascicolo, dati_note_scritte=_dati_modello_note(preparata),
        **studio_context_for_editor(),
    )
    modello = _impagina_bozza_note(preparata["testo"], schema_studio=True)
    html, _mancanti = template_linked_html(
        modello, context=campi, matter_id=fascicolo.id, client_id=fascicolo.id_cliente or "",
    )
    return html


def apri_bozza_note(fascicolo_id: str, chiave: str, documento_id: str) -> dict[str, str]:
    from hashlib import sha256
    from pct.editor_ai.editor_renderer import create_editor_document
    from pct.formatting import format_date_it
    from pct.prima_nota_transition import prima_nota_source_lock
    from web.helpers import get_fascicoli
    from web.services.document_crypto import encrypt_doc
    from web.services.riscontri_processuali_runtime import risultato_materializzato

    if not chiave.startswith(f"127ter.bozza_note:{fascicolo_id}:") or len(chiave) > 200:
        raise ValueError("Passaggio della bozza non riconosciuto.")
    path = Path(percorso_regole()).with_name("bozza-note-" + sha256(chiave.encode()).hexdigest())
    path.parent.mkdir(parents=True, exist_ok=True)
    with prima_nota_source_lock(path):
        g.fascicoli_sql_puntuali = True
        repository = get_fascicoli()
        fascicolo = repository.get(fascicolo_id)
        if fascicolo is None:
            raise LookupError("Fascicolo non trovato.")
        fonte = next((d for d in fascicolo.documenti if d.id == documento_id), None)
        if fonte is None:
            raise ValueError("Provvedimento della bozza non disponibile.")
        marcatore = _marcatore_bozza_note(chiave, fonte)
        for documento in fascicolo.documenti:
            if documento.fonte_documento == "BOZZA_NOTE_127_TER" and marcatore in (documento.tags or ()):
                return {"documentId": documento.id, "openUrl": f"/fascicoli/{fascicolo_id}/documenti/{documento.id}/editor"}
        pannello = risultato_materializzato(fascicolo_id, "passaggi") or {}
        preparata = (pannello.get("bozzeNote") or {}).get(chiave)
        if not preparata or preparata["documento_id"] != documento_id:
            raise ValueError("La bozza attuale dipende dal provvedimento. Attendi che la Lettura sia aggiornata.")
        # La stessa bozza preparata in sfondo per il passo (pct.bozze_passi): si apre quella, senza doppioni.
        from web.services.bozze_passi_runtime import archivio_corrente

        archivio = archivio_corrente()
        gia_pronta = next((v for v in (archivio.del_fascicolo(fascicolo_id) if archivio else [])
                           if v.chiave == f"note_127ter:{preparata['termine']}"), None)
        if gia_pronta and any(d.id == gia_pronta.documento_id for d in fascicolo.documenti):
            return {"documentId": gia_pronta.documento_id,
                    "openUrl": f"/fascicoli/{fascicolo_id}/documenti/{gia_pronta.documento_id}/editor"}
        doc = create_editor_document(
            fascicoli_repository=repository, fascicolo_id=fascicolo_id,
            title=preparata["titolo"] + " " + format_date_it(preparata["termine"]).replace("/", "-"),
            html_content=_compila_bozza_note(preparata, fascicolo),
            created_by=utente_corrente()[0], encrypt=encrypt_doc,
            fonte_documento="BOZZA_NOTE_127_TER",
            note=f"Bozza da rivedere. Provvedimento {preparata['documento']} ({preparata['documento_id']}).",
            tags=["bozza", marcatore], salvataggio_mirato=True, formato="docx",
        )
        return {"documentId": doc["document_id"], "openUrl": doc["open_url"]}


def correggi_passaggio(fascicolo_id: str, chiave: str, richiesta: Mapping[str, Any]) -> dict[str, Any]:
    """La correzione dell'avvocato diventa regola dello studio; il passaggio lo ricalcola il server."""
    dati = dati_del_fascicolo(fascicolo_id)
    if dati is None:
        raise LookupError("Fascicolo non trovato.")
    passaggio = next((voce for voce in passaggi_software(dati) if voce.chiave == chiave), None)
    if passaggio is None:
        raise RegoleStudioError("Il passaggio non è più attuale: aggiorna la vista e riprova.")
    autore_id, autore_nome = utente_corrente()
    repository = repository_corrente()
    try:
        regola = regola_da_correzione(
            passaggio, azione=str(richiesta.get("azione") or ""), ambito=str(richiesta.get("ambito") or ""),
            autore_id=autore_id, autore_nome=autore_nome, campo=str(richiesta.get("campo") or ""),
            valore=str(richiesta.get("valore") or ""), motivo=str(richiesta.get("motivo") or ""),
            materia=str(richiesta.get("materia") or ""),
        )
    except CorrezioneRifiutata as rifiuto:
        repository.registra_rifiuto(rifiuto.regola, rifiuto.rifiuto.motivo)
        raise
    except ValueError as errore:
        raise RegoleStudioError(str(errore)) from errore
    return repository.crea(regola).come_dizionario()


def elenco_regole() -> list[dict[str, Any]]:
    repository = repository_corrente()
    return [{**regola.come_dizionario(), "applicazioni": len(repository.applicazioni(regola.id))} for regola in repository.elenco()]


def aggiorna_regola(regola_studio_id: str, richiesta: Mapping[str, Any]) -> dict[str, Any]:
    autore_id, _nome = utente_corrente()
    attiva = richiesta.get("attiva")
    return repository_corrente().aggiorna(
        regola_studio_id, autore_id=autore_id,
        valore=str(richiesta["valore"]) if "valore" in richiesta else None,
        motivo=str(richiesta["motivo"]) if "motivo" in richiesta else None,
        attiva=bool(attiva) if isinstance(attiva, bool) else None,
    ).come_dizionario()


def diario_regola(regola_studio_id: str) -> dict[str, Any]:
    repository = repository_corrente()
    regola = repository.leggi(regola_studio_id)
    return {"regola": regola.come_dizionario(), "eventi": repository.eventi(regola.id), "applicazioni": repository.applicazioni(regola.id)}


__all__ = [
    "aggiorna_regola", "correggi_passaggio", "dati_del_fascicolo", "diario_regola", "elenco_regole", "passaggi_con_regole",
    "passaggi_software", "payload_passaggi", "percorso_regole", "repository_corrente",
]
