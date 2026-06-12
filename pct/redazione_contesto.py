"""
pct/redazione_contesto.py - Lettura del contesto reale di fascicolo e cliente
per la Redazione Atti guidata.

Ogni campo esposto proviene dai dati realmente presenti nel gestionale
(fascicolo, cliente, parti processuali, configurazione studio) e porta con se'
la tracciabilita' della fonte (tabella, id, campo). Nessun valore viene
inventato: i campi assenti sono marcati come mancanti.

Basi normative dei calcoli derivati:
- contributo unificato: art. 13 D.P.R. 115/2002 (via pct/strumenti_legali.py);
- condizioni di procedibilita': art. 5 D.Lgs. 28/2010 e art. 3 D.L. 132/2014
  (rilevate dai dati del fascicolo, mai presunte).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

ETICHETTA_DATO_MANCANTE = "DATO MANCANTE"


def _campo(valore: Any, etichetta: str, *, tabella: str = "", record_id: str = "", campo: str = "") -> dict[str, Any]:
    testo = "" if valore is None else str(valore).strip()
    return {
        "etichetta": etichetta,
        "valore": testo,
        "mancante": not testo,
        "fonte": {"tabella": tabella, "id": str(record_id or ""), "campo": campo} if tabella else {},
    }


def _attr(obj: Any, *names: str) -> str:
    for name in names:
        valore = getattr(obj, name, None)
        if valore is None:
            continue
        if hasattr(valore, "value"):
            valore = valore.value
        testo = str(valore).strip()
        if testo:
            return testo
    return ""


def _indirizzo_testo(indirizzo: Any) -> str:
    if indirizzo is None:
        return ""
    parti = [
        _attr(indirizzo, "via"),
        _attr(indirizzo, "civico"),
        _attr(indirizzo, "cap"),
        _attr(indirizzo, "comune"),
    ]
    provincia = _attr(indirizzo, "provincia")
    testo = " ".join([p for p in parti if p])
    if provincia:
        testo = f"{testo} ({provincia})" if testo else provincia
    return testo.strip()


def _scheda_anagrafica(soggetto: Any, *, tabella: str, ruolo: str = "") -> dict[str, Any]:
    """Scheda uniforme per cliente/soggetto, persona fisica o giuridica."""
    record_id = _attr(soggetto, "id")
    tipo = _attr(soggetto, "tipo")
    persona_giuridica = tipo in {"PERSONA_GIURIDICA", "PUBBLICA_AMMINISTRAZIONE", "ENTE", "CONDOMINIO", "ASSOCIAZIONE"}
    recapiti = getattr(soggetto, "recapiti", None)
    scheda: dict[str, Any] = {
        "id": record_id,
        "tipo": tipo,
        "ruolo": ruolo,
        "personaGiuridica": persona_giuridica,
        "denominazione": _campo(
            _attr(soggetto, "nome_completo", "ragione_sociale") or f"{_attr(soggetto, 'nome')} {_attr(soggetto, 'cognome')}".strip(),
            "Denominazione" if persona_giuridica else "Nome e cognome",
            tabella=tabella, record_id=record_id,
            campo="ragione_sociale" if persona_giuridica else "nome,cognome",
        ),
        "codiceFiscale": _campo(_attr(soggetto, "codice_fiscale"), "Codice fiscale", tabella=tabella, record_id=record_id, campo="codice_fiscale"),
        "pec": _campo(_attr(recapiti, "pec"), "PEC", tabella=tabella, record_id=record_id, campo="recapiti.pec"),
        "email": _campo(_attr(recapiti, "email"), "Email", tabella=tabella, record_id=record_id, campo="recapiti.email"),
        "telefono": _campo(_attr(recapiti, "telefono", "cellulare"), "Telefono", tabella=tabella, record_id=record_id, campo="recapiti.telefono"),
    }
    if persona_giuridica:
        scheda["partitaIva"] = _campo(_attr(soggetto, "partita_iva"), "Partita IVA", tabella=tabella, record_id=record_id, campo="partita_iva")
        scheda["legaleRappresentante"] = _campo(_attr(soggetto, "rappresentante_legale"), "Legale rappresentante", tabella=tabella, record_id=record_id, campo="rappresentante_legale")
        scheda["sedeLegale"] = _campo(
            _indirizzo_testo(getattr(soggetto, "indirizzo_sede_legale", None) or getattr(soggetto, "indirizzo", None)),
            "Sede legale", tabella=tabella, record_id=record_id, campo="indirizzo_sede_legale",
        )
    else:
        nascita = _attr(soggetto, "data_nascita")
        luogo = _attr(soggetto, "luogo_nascita")
        provincia = _attr(soggetto, "provincia_nascita")
        luogo_completo = f"{luogo} ({provincia})" if luogo and provincia else luogo
        scheda["dataNascita"] = _campo(nascita, "Data di nascita", tabella=tabella, record_id=record_id, campo="data_nascita")
        scheda["luogoNascita"] = _campo(luogo_completo, "Luogo di nascita", tabella=tabella, record_id=record_id, campo="luogo_nascita")
        scheda["residenza"] = _campo(
            _indirizzo_testo(getattr(soggetto, "indirizzo_residenza", None) or getattr(soggetto, "indirizzo", None)),
            "Residenza", tabella=tabella, record_id=record_id, campo="indirizzo_residenza",
        )
        scheda["domicilio"] = _campo(
            _indirizzo_testo(getattr(soggetto, "indirizzo_domicilio", None)),
            "Domicilio", tabella=tabella, record_id=record_id, campo="indirizzo_domicilio",
        )
    return scheda


def _testo_ricerca_fascicolo(fascicolo: Any) -> str:
    pezzi = [
        _attr(fascicolo, "titolo"),
        _attr(fascicolo, "oggetto"),
        _attr(fascicolo, "note"),
        _attr(fascicolo, "area_pratica"),
        _attr(fascicolo, "id_pratica"),
        _attr(fascicolo, "tipo_procedimento"),
        _attr(fascicolo, "procedura_operativa_nome"),
    ]
    for doc in list(getattr(fascicolo, "documenti", []) or [])[:80]:
        pezzi.append(_attr(doc, "nome"))
        pezzi.append(_attr(doc, "tipo"))
    for attivita in list(getattr(fascicolo, "attivita", []) or [])[:80]:
        pezzi.append(_attr(attivita, "descrizione", "titolo", "tipo"))
    return " ".join([p for p in pezzi if p]).lower()


_PAROLE_CONDIZIONI: dict[str, tuple[str, ...]] = {
    "mediazione": ("mediazione", "organismo di mediazione", "primo incontro di mediazione"),
    "negoziazione": ("negoziazione assistita", "convenzione di negoziazione"),
    "contratto": ("contratto", "contrattuale", "inadempiment", "risoluzione", "preliminare", "locazion", "appalto", "compravendita", "fornitura"),
    "preliminare": ("preliminare", "compromesso", "rogito"),
    "caparra": ("caparra",),
    "clausola_risolutiva": ("clausola risolutiva",),
    "diffida": ("diffida",),
    "termine_essenziale": ("termine essenziale",),
    "sinistro": ("sinistro", "risarciment", "danni", "illecito", "infortunio", "responsabilita"),
    "sinistro_stradale": ("sinistro stradale", "incidente stradale", "circolazione stradale", "tamponament"),
    "condominio": ("condomini", "delibera assembleare", "assemblea condominiale", "oneri condominiali"),
    "locazione": ("locazion", "sfratto", "canone", "morosit", "conduttore", "locatore"),
    "usucapione": ("usucapione",),
    "possesso": ("spoglio", "possesso", "reintegrazione", "manutenzione del possesso"),
    "successioni": ("eredit", "testament", "successione", "legittima", "divisione ereditaria"),
    "immobile": ("immobile", "immobiliare", "fabbricato", "terreno", "appartamento"),
    "tutele_crescenti": ("tutele crescenti",),
}


def condizioni_dal_fascicolo(fascicolo: Any) -> dict[str, bool]:
    """Rileva le condizioni contestuali dai dati reali del fascicolo (mai presunte)."""
    testo = _testo_ricerca_fascicolo(fascicolo)
    condizioni: dict[str, bool] = {}
    for chiave, parole in _PAROLE_CONDIZIONI.items():
        condizioni[chiave] = any(parola in testo for parola in parole)
    tipo = _attr(fascicolo, "tipo")
    if tipo == "SUCCESSIONI":
        condizioni["successioni"] = True
    return condizioni


def _categoria_contributo(fascicolo: Any) -> str:
    tipo = _attr(fascicolo, "tipo")
    testo = _testo_ricerca_fascicolo(fascicolo)
    if tipo == "TRIBUTARIO":
        return "tributario"
    if tipo == "AMMINISTRATIVO":
        return "amministrativo_ordinario"
    if tipo == "LAVORO":
        return "lavoro"
    if "decreto ingiuntivo" in testo:
        return "decreto_ingiuntivo"
    if "separazione consensuale" in testo or "divorzio congiunto" in testo:
        return "separazione_consensuale"
    return "civile_ordinario"


def contributo_unificato_da_fascicolo(fascicolo: Any) -> dict[str, Any]:
    """Contributo unificato ex art. 13 D.P.R. 115/2002 dal valore causa del fascicolo.

    Restituisce un dict con `disponibile`, `totale`, `descrizione`, `fonte`.
    Se il valore causa manca e la categoria lo richiede, il dato resta mancante.
    """
    valore = getattr(fascicolo, "valore_causa", None)
    categoria = _categoria_contributo(fascicolo)
    try:
        valore_num = float(valore or 0)
    except (TypeError, ValueError):
        valore_num = 0.0
    try:
        from pct.strumenti_legali import GestioneStrumentiLegali

        esito = GestioneStrumentiLegali().calcola_contributo_unificato(
            {
                "cu_categoria": categoria,
                "cu_grado": "primo_grado",
                "cu_valore": valore_num if valore_num > 0 else "",
                "cu_valore_tipo": "determinato" if valore_num > 0 else "non_indicato",
            }
        )
    except Exception:
        return {"disponibile": False, "totale": None, "descrizione": "", "categoria": categoria, "fonte": "D.P.R. 115/2002, art. 13"}
    totale = esito.get("totale")
    if valore_num <= 0 and categoria in {"civile_ordinario", "decreto_ingiuntivo", "lavoro", "tributario"}:
        return {
            "disponibile": False,
            "totale": None,
            "descrizione": "Valore causa assente nel fascicolo: contributo non determinabile.",
            "categoria": categoria,
            "fonte": "D.P.R. 115/2002, art. 13",
        }
    return {
        "disponibile": totale is not None,
        "totale": totale,
        "descrizione": f"{esito.get('categoria_label', categoria)} - {esito.get('grado_label', 'Primo grado')}",
        "categoria": categoria,
        "fonte": "D.P.R. 115/2002, art. 13",
    }


def estrai_contesto_fascicolo(
    *,
    fascicolo: Any,
    cliente: Any = None,
    parti: Any = None,
    config: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    """Quadro completo e tracciato dei dati reali utilizzabili nell'atto.

    `parti` e' il namespace prodotto da `_build_parti_template_context`
    (assistiti, controparti, difensori_controparte) basato su pct/soggetti.py.
    """
    config = config or {}
    fid = _attr(fascicolo, "id")

    scheda_cliente = _scheda_anagrafica(cliente, tabella="clienti", ruolo="ASSISTITO") if cliente is not None else None

    controparti: list[dict[str, Any]] = []
    difensori: list[dict[str, Any]] = []
    if parti is not None:
        for item in list(getattr(parti, "controparti", []) or []):
            controparti.append(_scheda_anagrafica(item, tabella="soggetti", ruolo=_attr(item, "ruolo") or "CONTROPARTE"))
        for item in list(getattr(parti, "difensori_controparte", []) or []):
            difensori.append(_scheda_anagrafica(item, tabella="soggetti", ruolo="DIFENSORE_CONTROPARTE"))
    if not controparti and _attr(fascicolo, "controparte"):
        record = {
            "id": "",
            "tipo": "",
            "ruolo": "CONTROPARTE",
            "personaGiuridica": False,
            "denominazione": _campo(_attr(fascicolo, "controparte"), "Denominazione", tabella="fascicoli", record_id=fid, campo="controparte"),
            "codiceFiscale": _campo(_attr(fascicolo, "cf_controparte"), "Codice fiscale", tabella="fascicoli", record_id=fid, campo="cf_controparte"),
            "pec": _campo("", "PEC"),
            "email": _campo("", "Email"),
            "telefono": _campo("", "Telefono"),
        }
        controparti.append(record)

    allegati = [
        {"id": _attr(doc, "id"), "nome": _attr(doc, "nome"), "tipo": _attr(doc, "tipo")}
        for doc in list(getattr(fascicolo, "documenti", []) or [])
        if _attr(doc, "nome")
    ]

    contributo = contributo_unificato_da_fascicolo(fascicolo)
    valore_causa = getattr(fascicolo, "valore_causa", None) or ""
    if isinstance(valore_causa, (int, float)) and not valore_causa:
        valore_causa = ""

    dati_fascicolo = {
        "id": fid,
        "numero": _campo(_attr(fascicolo, "numero"), "Numero fascicolo", tabella="fascicoli", record_id=fid, campo="numero"),
        "titolo": _campo(_attr(fascicolo, "titolo"), "Titolo", tabella="fascicoli", record_id=fid, campo="titolo"),
        "materia": _campo(_attr(fascicolo, "tipo"), "Materia", tabella="fascicoli", record_id=fid, campo="tipo"),
        "areaPratica": _campo(_attr(fascicolo, "area_pratica"), "Area pratica", tabella="fascicoli", record_id=fid, campo="area_pratica"),
        "pratica": _campo(_attr(fascicolo, "id_pratica"), "Pratica collegata", tabella="fascicoli", record_id=fid, campo="id_pratica"),
        "oggetto": _campo(_attr(fascicolo, "oggetto"), "Oggetto", tabella="fascicoli", record_id=fid, campo="oggetto"),
        "ufficioGiudiziario": _campo(_attr(fascicolo, "tribunale"), "Ufficio giudiziario", tabella="fascicoli", record_id=fid, campo="tribunale"),
        "sezione": _campo(_attr(fascicolo, "sezione"), "Sezione", tabella="fascicoli", record_id=fid, campo="sezione"),
        "giudice": _campo(_attr(fascicolo, "giudice"), "Giudice", tabella="fascicoli", record_id=fid, campo="giudice"),
        "rg": _campo(_attr(fascicolo, "rg_completo") or _attr(fascicolo, "numero_rg"), "R.G.", tabella="fascicoli", record_id=fid, campo="numero_rg,anno_rg"),
        "ritoProcedimento": _campo(_attr(fascicolo, "tipo_procedimento"), "Rito / procedimento", tabella="fascicoli", record_id=fid, campo="tipo_procedimento"),
        "prossimaUdienza": _campo(_attr(fascicolo, "data_prossima_udienza") or _attr(fascicolo, "data_prima_udienza"), "Prossima udienza", tabella="fascicoli", record_id=fid, campo="data_prossima_udienza"),
        "stato": _campo(_attr(fascicolo, "stato"), "Stato pratica", tabella="fascicoli", record_id=fid, campo="stato"),
        "valoreCausa": _campo(valore_causa, "Valore causa", tabella="fascicoli", record_id=fid, campo="valore_causa"),
        "note": _campo(_attr(fascicolo, "note"), "Note", tabella="fascicoli", record_id=fid, campo="note"),
    }

    studio = {
        "nome": _campo(config.get("STUDIO_NOME", ""), "Nome studio", tabella="config_studio", record_id="studio", campo="nome"),
        "avvocato": _campo(config.get("STUDIO_AVVOCATO", ""), "Avvocato firmatario", tabella="config_studio", record_id="studio", campo="avvocato"),
        "codiceFiscale": _campo(config.get("STUDIO_CF", ""), "Codice fiscale", tabella="config_studio", record_id="studio", campo="cf"),
        "partitaIva": _campo(config.get("STUDIO_PIVA", ""), "Partita IVA", tabella="config_studio", record_id="studio", campo="piva"),
        "indirizzo": _campo(config.get("STUDIO_INDIRIZZO", ""), "Indirizzo studio", tabella="config_studio", record_id="studio", campo="indirizzo"),
        "pec": _campo(config.get("PCT_STUDIO_PEC", "") or config.get("SMTP_FROM", ""), "PEC studio", tabella="config_studio", record_id="studio", campo="pec"),
        "telefono": _campo(config.get("STUDIO_TELEFONO", ""), "Telefono", tabella="config_studio", record_id="studio", campo="telefono"),
        "ordine": _campo(config.get("STUDIO_ORDINE", ""), "Ordine / Foro", tabella="config_studio", record_id="studio", campo="ordine_avvocati"),
        "qualifica": _campo(config.get("STUDIO_QUALIFICA", ""), "Qualifica professionale", tabella="config_studio", record_id="studio", campo="qualifica_professionale"),
    }

    condizioni = condizioni_dal_fascicolo(fascicolo)

    return {
        "fascicolo": dati_fascicolo,
        "cliente": scheda_cliente,
        "controparti": controparti,
        "difensori": difensori,
        "studio": studio,
        "allegati": allegati,
        "economia": {
            "valoreCausa": dati_fascicolo["valoreCausa"],
            "contributoUnificato": contributo,
        },
        "condizioni": condizioni,
        "condizioniAttive": sorted([chiave for chiave, attiva in condizioni.items() if attiva]),
    }


def anteprima_campi_modello(
    model_code: str,
    payload: Dict[str, Any],
    *,
    prefill_resolution: Optional[Dict[str, Any]] = None,
) -> dict[str, Any]:
    """Per il modello scelto: campi gia' compilati dai dati reali e campi mancanti.

    Il campo trovato espone l'origine (etichetta della fonte di prefill) cosi'
    l'avvocato vede da dove proviene ogni valore prima della generazione.
    """
    from pct.compilatore_atti import campi_modello

    prefill_fields = {}
    if isinstance(prefill_resolution, dict):
        prefill_fields = prefill_resolution.get("fields") if isinstance(prefill_resolution.get("fields"), dict) else {}

    trovati: list[dict[str, Any]] = []
    mancanti: list[dict[str, Any]] = []
    for campo in campi_modello(model_code):
        nome = str(campo.get("name") or "")
        if not nome:
            continue
        valore = payload.get(nome)
        if isinstance(valore, list):
            testo = "\n".join([str(item) for item in valore if str(item).strip()])
        else:
            testo = "" if valore is None else str(valore).strip()
        dettaglio = prefill_fields.get(nome) if isinstance(prefill_fields.get(nome), dict) else {}
        fonte = str(dettaglio.get("source_label") or dettaglio.get("source") or "").strip()
        voce = {
            "name": nome,
            "label": str(campo.get("label") or nome),
            "type": str(campo.get("type") or "text"),
            "value": testo,
            "fonte": fonte,
        }
        if testo:
            trovati.append(voce)
        else:
            voce["motivo"] = str(dettaglio.get("missing_reason") or "Dato non presente nel fascicolo o nelle anagrafiche.")
            mancanti.append(voce)
    return {"trovati": trovati, "mancanti": mancanti}


def marcatore_dato_mancante(etichetta: str) -> str:
    return f"[{ETICHETTA_DATO_MANCANTE}: {str(etichetta or '').strip()}]"


def applica_marcatori_dati_mancanti(model_code: str, payload: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
    """Sostituisce i campi obbligatori vuoti con il marcatore visibile, senza inventare dati.

    Restituisce il payload aggiornato e l'elenco delle etichette marcate.
    """
    from pct.compilatore_atti import campi_modello

    aggiornato = dict(payload)
    marcati: list[str] = []
    for campo in campi_modello(model_code):
        nome = str(campo.get("name") or "")
        if not nome:
            continue
        valore = aggiornato.get(nome)
        vuoto = valore is None or (isinstance(valore, list) and not valore) or (not isinstance(valore, list) and not str(valore).strip())
        if vuoto:
            etichetta = str(campo.get("label") or nome)
            aggiornato[nome] = marcatore_dato_mancante(etichetta)
            marcati.append(etichetta)
    return aggiornato, marcati
