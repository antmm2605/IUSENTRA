"""Catalogo built-in professionale per il workspace atti."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from pct.compilatore_atti import AREA_LABELS, MODELS, get_essential_docs
from pct.template_atti_compiler_bindings import compiler_binding_map_by_title


def _field(
    name: str,
    label: str,
    *,
    field_type: str = "textarea",
    placeholder: str = "",
    section: str = "Contenuto",
    rows: int = 4,
    help_text: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "type": field_type,
        "placeholder": placeholder,
        "section": section,
        "rows": rows,
        "help_text": help_text,
    }


FIELD_LIBRARY: dict[str, dict[str, Any]] = {
    "autorita_competente": _field(
        "autorita_competente",
        "Autorita competente",
        field_type="text",
        placeholder="es. Tribunale di Milano",
        section="Intestazione",
    ),
    "procedimento_riferimento": _field(
        "procedimento_riferimento",
        "Riferimento procedimento",
        field_type="text",
        placeholder="es. RG 1234/2026",
        section="Intestazione",
    ),
    "oggetto_atto": _field(
        "oggetto_atto",
        "Oggetto dell'atto",
        field_type="text",
        placeholder="Sintesi dell'oggetto o della domanda",
        section="Intestazione",
        rows=1,
    ),
    "controparte_nome": _field(
        "controparte_nome",
        "Controparte / destinatario",
        field_type="text",
        placeholder="Nome e cognome o ragione sociale",
        section="Parti",
        rows=1,
    ),
    "controparte_indirizzo": _field(
        "controparte_indirizzo",
        "Indirizzo controparte",
        field_type="text",
        placeholder="Indirizzo o domicilio digitale",
        section="Parti",
        rows=1,
    ),
    "mandato_oggetto": _field(
        "mandato_oggetto",
        "Oggetto del mandato",
        field_type="text",
        placeholder="Procedimento o attivita per cui si conferisce la procura",
        section="Mandato",
        rows=1,
    ),
    "facolta_speciali": _field(
        "facolta_speciali",
        "Facolta speciali",
        placeholder="Poteri specifici, transigere, conciliare, proporre impugnazioni",
        section="Mandato",
    ),
    "domicilio_eletto": _field(
        "domicilio_eletto",
        "Domicilio eletto",
        field_type="text",
        placeholder="Domicilio presso lo studio o indirizzo indicato",
        section="Mandato",
        rows=1,
    ),
    "domiciliatario_nome": _field(
        "domiciliatario_nome",
        "Domiciliatario",
        field_type="text",
        placeholder="Avv. Nome Cognome",
        section="Mandato",
        rows=1,
    ),
    "fatti_rilevanti": _field(
        "fatti_rilevanti",
        "Fatti rilevanti",
        placeholder="Esposizione sintetica e cronologica dei fatti",
        section="Fatto",
        rows=5,
    ),
    "motivi_in_diritto": _field(
        "motivi_in_diritto",
        "Motivi in diritto",
        placeholder="Norme richiamate, orientamenti, argomenti giuridici",
        section="Diritto",
        rows=5,
    ),
    "domande_conclusioni": _field(
        "domande_conclusioni",
        "Domande e conclusioni",
        placeholder="Richieste al giudice o alla controparte",
        section="Conclusioni",
        rows=4,
    ),
    "mezzi_prova": _field(
        "mezzi_prova",
        "Mezzi di prova",
        placeholder="Testi, documenti, interrogatorio formale, CTU",
        section="Conclusioni",
        rows=4,
    ),
    "documenti_allegati": _field(
        "documenti_allegati",
        "Documenti allegati",
        placeholder="Elenco documenti allegati o da depositare",
        section="Allegati",
        rows=4,
    ),
    "contenuto_istanza": _field(
        "contenuto_istanza",
        "Contenuto dell'istanza",
        placeholder="Contenuto della richiesta o della memoria",
        section="Contenuto",
        rows=5,
    ),
    "motivazione_istanza": _field(
        "motivazione_istanza",
        "Motivazione",
        placeholder="Ragioni in fatto e in diritto della richiesta",
        section="Contenuto",
        rows=4,
    ),
    "provvedimento_impugnato": _field(
        "provvedimento_impugnato",
        "Provvedimento impugnato",
        field_type="text",
        placeholder="Sentenza, ordinanza o decreto impugnato",
        section="Impugnazione",
        rows=1,
    ),
    "motivi_impugnazione": _field(
        "motivi_impugnazione",
        "Motivi di impugnazione",
        placeholder="Censure specifiche e motivi di gravame",
        section="Impugnazione",
        rows=5,
    ),
    "istanza_cautelare": _field(
        "istanza_cautelare",
        "Istanza cautelare",
        placeholder="Fumus, periculum e misura richiesta",
        section="Cautelare",
        rows=4,
    ),
    "termine_assegnato": _field(
        "termine_assegnato",
        "Termine richiesto / assegnato",
        field_type="text",
        placeholder="es. 15 giorni, prossima udienza, termine di legge",
        section="Conclusioni",
        rows=1,
    ),
    "importo_richiesto": _field(
        "importo_richiesto",
        "Importo richiesto",
        field_type="text",
        placeholder="es. Euro 12.500,00",
        section="Dati economici",
        rows=1,
    ),
    "titolo_esecutivo": _field(
        "titolo_esecutivo",
        "Titolo esecutivo",
        field_type="text",
        placeholder="Sentenza, decreto ingiuntivo, verbale di conciliazione",
        section="Esecuzione",
        rows=1,
    ),
    "precetto_riferimento": _field(
        "precetto_riferimento",
        "Riferimento precetto",
        field_type="text",
        placeholder="Data notifica, importo, estremi dell'atto di precetto",
        section="Esecuzione",
        rows=1,
    ),
    "beni_o_crediti": _field(
        "beni_o_crediti",
        "Beni / crediti aggrediti",
        placeholder="Descrizione dei beni o dei crediti pignorati",
        section="Esecuzione",
        rows=4,
    ),
    "richiesta_esecutiva": _field(
        "richiesta_esecutiva",
        "Richiesta esecutiva",
        placeholder="Vendita, assegnazione, ricerca beni, riduzione, conversione",
        section="Esecuzione",
        rows=4,
    ),
    "situazione_familiare": _field(
        "situazione_familiare",
        "Situazione familiare",
        placeholder="Convivenza, separazione, residenza, stato dei rapporti",
        section="Famiglia",
        rows=5,
    ),
    "figli_coinvolti": _field(
        "figli_coinvolti",
        "Figli / soggetti coinvolti",
        placeholder="Nomi, date di nascita, esigenze rilevanti",
        section="Famiglia",
        rows=4,
    ),
    "interesse_minore": _field(
        "interesse_minore",
        "Interesse del minore / beneficiario",
        placeholder="Sintesi delle esigenze di tutela",
        section="Famiglia",
        rows=4,
    ),
    "condizioni_richieste": _field(
        "condizioni_richieste",
        "Condizioni richieste",
        placeholder="Affidamento, mantenimento, assegnazione casa, visite, modifiche",
        section="Famiglia",
        rows=5,
    ),
    "rapporto_lavoro": _field(
        "rapporto_lavoro",
        "Rapporto di lavoro / posizione previdenziale",
        placeholder="Qualifica, decorrenza, contratto collettivo, ente",
        section="Lavoro e previdenza",
        rows=4,
    ),
    "argomentazioni_lavoro": _field(
        "argomentazioni_lavoro",
        "Argomentazioni",
        placeholder="Violazioni, differenze retributive, illegittimita, domande",
        section="Lavoro e previdenza",
        rows=5,
    ),
    "assistito_nome": _field(
        "assistito_nome",
        "Assistito / indagato / imputato",
        field_type="text",
        placeholder="Nome dell'assistito",
        section="Parti",
        rows=1,
    ),
    "argomentazioni_difensive": _field(
        "argomentazioni_difensive",
        "Argomentazioni difensive",
        placeholder="Difese, eccezioni, richieste istruttorie",
        section="Difesa",
        rows=5,
    ),
    "richieste_penali": _field(
        "richieste_penali",
        "Richieste",
        placeholder="Provvedimento richiesto o attivita difensiva da ottenere",
        section="Difesa",
        rows=4,
    ),
    "ente_resistente": _field(
        "ente_resistente",
        "Ente / amministrazione resistente",
        field_type="text",
        placeholder="PA o ente resistente",
        section="Parti",
        rows=1,
    ),
    "atto_impugnato": _field(
        "atto_impugnato",
        "Atto impugnato",
        field_type="text",
        placeholder="Provvedimento amministrativo o tributario impugnato",
        section="Impugnazione",
        rows=1,
    ),
    "motivi_speciali": _field(
        "motivi_speciali",
        "Motivi specifici",
        placeholder="Motivi aggiunti, violazioni tributarie, vizi amministrativi",
        section="Diritto",
        rows=5,
    ),
    "atto_da_notificare": _field(
        "atto_da_notificare",
        "Atto da notificare / attivita richiesta",
        field_type="text",
        placeholder="Documento o attivita per UNEP / notifica in proprio",
        section="Notifiche",
        rows=1,
    ),
    "richiesta_notifica": _field(
        "richiesta_notifica",
        "Richiesta operativa",
        placeholder="Cosa deve fare UNEP o quale attestazione/notifica predisporre",
        section="Notifiche",
        rows=4,
    ),
    "destinatario_nome": _field(
        "destinatario_nome",
        "Destinatario",
        field_type="text",
        placeholder="Controparte o soggetto destinatario",
        section="Destinatario",
        rows=1,
    ),
    "destinatario_indirizzo": _field(
        "destinatario_indirizzo",
        "Indirizzo / PEC destinatario",
        field_type="text",
        placeholder="Indirizzo fisico o domicilio digitale",
        section="Destinatario",
        rows=1,
    ),
    "descrizione_inadempimento": _field(
        "descrizione_inadempimento",
        "Descrizione dei fatti / inadempimento",
        placeholder="Fatti, contestazioni, esposizione del rapporto",
        section="Fatto",
        rows=5,
    ),
    "richiesta_formale": _field(
        "richiesta_formale",
        "Richiesta formale",
        placeholder="Pagamento, adempimento, rettifica, trasmissione documenti",
        section="Richiesta",
        rows=4,
    ),
    "note_finali": _field(
        "note_finali",
        "Note finali / riserve",
        placeholder="Riserve di ulteriori azioni, spese, termini",
        section="Chiusura",
        rows=3,
    ),
}


FAMILY_DEFAULTS: dict[str, dict[str, Any]] = {
    "procura": {
        "field_names": ["mandato_oggetto", "autorita_competente", "facolta_speciali", "domicilio_eletto", "note_finali"],
        "allegati_obbligatori": ["Documento di identita del conferente", "Tessera sanitaria / codice fiscale"],
        "controlli_conformita": ["Verifica sottoscrizione della parte", "Controllo autenticazione firma", "Allineamento dati cliente e fascicolo"],
    },
    "mandato_speciale": {
        "field_names": ["mandato_oggetto", "autorita_competente", "procedimento_riferimento", "facolta_speciali", "domicilio_eletto"],
        "allegati_obbligatori": ["Documento di identita del conferente", "Atto o provvedimento richiamato"],
        "controlli_conformita": ["Coerenza con fase processuale", "Poteri speciali espressi", "Data e firma leggibili"],
    },
    "nomina_domiciliatario": {
        "field_names": ["domiciliatario_nome", "autorita_competente", "procedimento_riferimento", "domicilio_eletto", "note_finali"],
        "allegati_obbligatori": ["Dati del domiciliatario", "Eventuale procura o delega"],
        "controlli_conformita": ["Domicilio coerente con foro", "Richiamo del procedimento", "Firma del difensore o della parte"],
    },
    "revoca_mandato": {
        "field_names": ["mandato_oggetto", "autorita_competente", "procedimento_riferimento", "note_finali"],
        "allegati_obbligatori": ["Documento di identita", "Eventuale comunicazione al precedente difensore"],
        "controlli_conformita": ["Chiarezza dell'effetto revocatorio", "Indicazione del procedimento", "Data certa della comunicazione"],
    },
    "rinuncia_mandato": {
        "field_names": ["mandato_oggetto", "autorita_competente", "procedimento_riferimento", "note_finali"],
        "allegati_obbligatori": ["Comunicazione alla parte", "Eventuale prova di ricezione"],
        "controlli_conformita": ["Rispetto obblighi deontologici", "Indicazione del termine per sostituzione", "Tracciabilita della comunicazione"],
    },
    "elezione_domicilio": {
        "field_names": ["domicilio_eletto", "autorita_competente", "procedimento_riferimento", "note_finali"],
        "allegati_obbligatori": ["Documento di identita", "Eventuale procura collegata"],
        "controlli_conformita": ["Domicilio completo", "Coerenza con atto principale", "Sottoscrizione della parte"],
    },
    "civile_intro": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "oggetto_atto", "controparte_nome", "fatti_rilevanti", "motivi_in_diritto", "domande_conclusioni", "mezzi_prova", "documenti_allegati"],
        "allegati_obbligatori": ["Procura alle liti", "Documenti fondanti la domanda", "Indice allegati se necessario"],
        "controlli_conformita": ["Parti e foro coerenti", "Oggetto e conclusioni completi", "Documenti citati presenti"],
    },
    "civile_processuale": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "oggetto_atto", "contenuto_istanza", "motivazione_istanza", "documenti_allegati"],
        "allegati_obbligatori": ["Atto richiamato", "Eventuali documenti integrativi"],
        "controlli_conformita": ["Riferimento procedimento corretto", "Oggetto dell'istanza chiaro", "Deposito coerente con la fase"],
    },
    "monitorio_cautelare": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "oggetto_atto", "controparte_nome", "fatti_rilevanti", "motivi_in_diritto", "istanza_cautelare", "domande_conclusioni", "documenti_allegati"],
        "allegati_obbligatori": ["Procura alle liti", "Prova scritta o documenti probatori", "Eventuale calcolo importi"],
        "controlli_conformita": ["Presupposti di urgenza o monitori esplicitati", "Conclusioni coerenti con il rito", "Allegazioni istruttorie pertinenti"],
    },
    "impugnazione_civile": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "provvedimento_impugnato", "controparte_nome", "motivi_impugnazione", "domande_conclusioni", "istanza_cautelare", "documenti_allegati"],
        "allegati_obbligatori": ["Copia del provvedimento impugnato", "Procura speciale se richiesta", "Documenti richiamati nei motivi"],
        "controlli_conformita": ["Impugnazione specifica", "Termini verificati", "Organo competente corretto"],
    },
    "esecuzione": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "titolo_esecutivo", "precetto_riferimento", "controparte_nome", "beni_o_crediti", "richiesta_esecutiva", "documenti_allegati"],
        "allegati_obbligatori": ["Titolo esecutivo", "Relata di notifica del titolo", "Relata di notifica del precetto"],
        "controlli_conformita": ["Titolo e precetto coerenti", "Soggetti esecutati corretti", "Richiesta esecutiva determinata"],
    },
    "famiglia": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "controparte_nome", "situazione_familiare", "figli_coinvolti", "interesse_minore", "condizioni_richieste", "documenti_allegati"],
        "allegati_obbligatori": ["Certificato di matrimonio o stato civile", "Documentazione reddituale", "Documenti sui minori e spese"],
        "controlli_conformita": ["Interesse del minore esplicitato", "Condizioni richieste determinate", "Documentazione reddituale aggiornata"],
    },
    "lavoro": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "controparte_nome", "rapporto_lavoro", "fatti_rilevanti", "argomentazioni_lavoro", "domande_conclusioni", "documenti_allegati"],
        "allegati_obbligatori": ["Contratto / buste paga / lettere", "Procura alle liti", "Documentazione contributiva o disciplinare"],
        "controlli_conformita": ["Foro lavoro corretto", "Domande quantificate", "Documenti del rapporto richiamati"],
    },
    "penale": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "assistito_nome", "oggetto_atto", "fatti_rilevanti", "argomentazioni_difensive", "richieste_penali", "documenti_allegati"],
        "allegati_obbligatori": ["Nomina difensore o mandato", "Documenti difensivi", "Eventuale procura speciale"],
        "controlli_conformita": ["Titolo difensivo presente", "Autorita procedente corretta", "Richieste compatibili con la fase"],
    },
    "amministrativo": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "ente_resistente", "atto_impugnato", "fatti_rilevanti", "motivi_speciali", "domande_conclusioni", "istanza_cautelare", "documenti_allegati"],
        "allegati_obbligatori": ["Procura alle liti", "Atto impugnato", "Documenti istruttori e prova di conoscenza"],
        "controlli_conformita": ["Termini decadenziali verificati", "Atto impugnato identificato", "Domande e misura cautelare coerenti"],
    },
    "tributario": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "ente_resistente", "atto_impugnato", "fatti_rilevanti", "motivi_speciali", "domande_conclusioni", "documenti_allegati"],
        "allegati_obbligatori": ["Atto tributario impugnato", "Procura alle liti", "Documentazione fiscale e notifiche"],
        "controlli_conformita": ["Ente resistente corretto", "Valore e atto impugnato determinati", "Motivi tributari circostanziati"],
    },
    "notifica": {
        "field_names": ["autorita_competente", "procedimento_riferimento", "atto_da_notificare", "destinatario_nome", "destinatario_indirizzo", "richiesta_notifica", "documenti_allegati"],
        "allegati_obbligatori": ["Atto da notificare", "Relata / attestazioni", "Eventuali estratti o allegati per UNEP"],
        "controlli_conformita": ["Destinatario e indirizzo completi", "Atto da notificare allegato", "Canale di notifica corretto"],
    },
    "stragiudiziale": {
        "field_names": ["destinatario_nome", "destinatario_indirizzo", "oggetto_atto", "descrizione_inadempimento", "richiesta_formale", "termine_assegnato", "note_finali"],
        "allegati_obbligatori": ["Documenti a supporto della richiesta", "Eventuale contratto o fattura richiamata"],
        "controlli_conformita": ["Destinatario completo", "Richiesta chiara e determinata", "Termine o riserva finale coerenti"],
    },
}


def _copy_fields(*names: str) -> list[dict[str, Any]]:
    return [deepcopy(FIELD_LIBRARY[name]) for name in names]


def _keywords_for(spec: dict[str, Any]) -> list[str]:
    base = [spec.get("area", ""), spec.get("branca", ""), spec.get("sottobranca", ""), spec.get("titolo", "")]
    extras = spec.get("varianti", []) or []
    ordered: list[str] = []
    for item in base + extras:
        value = str(item or "").strip()
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def _description_for(spec: dict[str, Any]) -> str:
    return (
        spec.get("descrizione")
        or f"Bozza built-in per {spec['titolo'].lower()}, con metadati operativi, allegati e controlli di conformita pronti per il workspace."
    )


def _body_procura(title: str, *, special: bool = False) -> str:
    scope = "procura speciale" if special else "procura"
    return "\n".join(
        [
            title.upper(),
            "",
            "Il/La sottoscritto/a {{ cliente.nome_completo or '___________________' }},",
            "{% if cliente.codice_fiscale %}C.F. {{ cliente.codice_fiscale }},{% endif %}",
            "{% if cliente.indirizzo %}residente in {{ cliente.indirizzo }},{% endif %}",
            "",
            f"conferisce {scope} all'Avv. {{ avvocato_nome }} del foro di competenza, con studio in {{ studio_indirizzo or '___________________' }},",
            "per rappresentarlo/a e difenderlo/a in relazione a {{ mandato_oggetto or oggetto_atto or fascicolo.titolo or '___________________' }}",
            "davanti a {{ autorita_competente or fascicolo.tribunale or '___________________' }}",
            "{% if procedimento_riferimento %}nel procedimento {{ procedimento_riferimento }}{% endif %}.",
            "",
            "Si conferiscono tutti i poteri di legge e, in particolare:",
            "{{ facolta_speciali or 'compiere ogni attivita difensiva, introduttiva, istruttoria, cautelare ed esecutiva utile alla tutela della parte.' }}",
            "",
            "Domicilio eletto: {{ domicilio_eletto or studio_indirizzo or '___________________' }}.",
            "",
            "{% if note_finali %}Ulteriori indicazioni: {{ note_finali }}{% endif %}",
            "",
            "Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Firma del conferente: ___________________",
            "",
            "Autentica di firma",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_nomina_domiciliatario(title: str) -> str:
    return "\n".join(
        [
            title.upper(),
            "",
            "Il/La sottoscritto/a difensore Avv. {{ avvocato_nome }}, nell'interesse di {{ cliente.nome_completo or '___________________' }},",
            "nomina domiciliatario l'Avv. {{ domiciliatario_nome or '___________________' }}",
            "con domicilio eletto in {{ domicilio_eletto or '___________________' }}",
            "per il procedimento {{ procedimento_riferimento or fascicolo.numero_rg or '___________________' }}",
            "pendente avanti {{ autorita_competente or fascicolo.tribunale or '___________________' }}.",
            "",
            "{% if note_finali %}Indicazioni operative: {{ note_finali }}{% endif %}",
            "",
            "Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_revoca_rinuncia(title: str, verb: str) -> str:
    return "\n".join(
        [
            title.upper(),
            "",
            "Il/La sottoscritto/a {{ cliente.nome_completo or avvocato_nome or '___________________' }},",
            f"comunica {verb} in relazione al mandato difensivo avente ad oggetto {{ mandato_oggetto or fascicolo.titolo or '___________________' }}",
            "avanti {{ autorita_competente or fascicolo.tribunale or '___________________' }}",
            "{% if procedimento_riferimento %}nel procedimento {{ procedimento_riferimento }}{% endif %}.",
            "",
            "{% if note_finali %}Precisazioni: {{ note_finali }}{% else %}La comunicazione viene resa con ogni effetto di legge e con invito ad assumere le conseguenti determinazioni.{% endif %}",
            "",
            "Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Firma: ___________________",
        ]
    )


def _body_elezione_domicilio(title: str) -> str:
    return "\n".join(
        [
            title.upper(),
            "",
            "Il/La sottoscritto/a {{ cliente.nome_completo or '___________________' }} elegge domicilio",
            "in {{ domicilio_eletto or studio_indirizzo or '___________________' }}",
            "per il procedimento {{ procedimento_riferimento or fascicolo.numero_rg or '___________________' }}",
            "avanti {{ autorita_competente or fascicolo.tribunale or '___________________' }}.",
            "",
            "{% if note_finali %}Ulteriori precisazioni: {{ note_finali }}{% endif %}",
            "",
            "Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Firma: ___________________",
        ]
    )


def _body_giudiziale(title: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or fascicolo.tribunale or 'Autorita competente') | upper }}",
            "",
            title.upper(),
            "",
            "Per: {{ cliente.nome_completo or parti.assistito_principale.nome_completo or '___________________' }}",
            "{% if cliente.codice_fiscale %}C.F. {{ cliente.codice_fiscale }}{% endif %}",
            "",
            "Contro: {{ controparte_nome or parti.controparte_principale.nome_completo or '___________________' }}",
            "{% if controparte_indirizzo %}domiciliato in {{ controparte_indirizzo }}{% endif %}",
            "",
            "{% if procedimento_riferimento %}Riferimento: {{ procedimento_riferimento }}{% endif %}",
            "Oggetto: {{ oggetto_atto or fascicolo.titolo or '___________________' }}",
            "",
            "FATTO",
            "{{ fatti_rilevanti or '___________________' }}",
            "",
            "DIRITTO",
            "{{ motivi_in_diritto or motivi_speciali or '___________________' }}",
            "",
            "{% if istanza_cautelare %}PROFILI CAUTELARI",
            "{{ istanza_cautelare }}",
            "",
            "{% endif %}CONCLUSIONI",
            "{{ domande_conclusioni or richiesta_esecutiva or condizioni_richieste or richieste_penali or '___________________' }}",
            "",
            "{% if mezzi_prova %}MEZZI DI PROVA",
            "{{ mezzi_prova }}",
            "",
            "{% endif %}{% if documenti_allegati %}DOCUMENTI ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_processuale(title: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or fascicolo.tribunale or 'Autorita competente') | upper }}",
            "",
            title.upper(),
            "",
            "{% if procedimento_riferimento %}Procedimento: {{ procedimento_riferimento }}{% endif %}",
            "Parte istante: {{ cliente.nome_completo or parti.assistito_principale.nome_completo or '___________________' }}",
            "{% if controparte_nome %}Controparte: {{ controparte_nome }}{% endif %}",
            "",
            "Oggetto: {{ oggetto_atto or '___________________' }}",
            "",
            "CONTENUTO",
            "{{ contenuto_istanza or fatti_rilevanti or argomentazioni_difensive or '___________________' }}",
            "",
            "{% if motivazione_istanza or motivi_in_diritto %}MOTIVAZIONE",
            "{{ motivazione_istanza or motivi_in_diritto }}",
            "",
            "{% endif %}{% if documenti_allegati %}ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_impugnazione(title: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or 'Giudice dell impugnazione') | upper }}",
            "",
            title.upper(),
            "",
            "Per: {{ cliente.nome_completo or '___________________' }}",
            "Contro: {{ controparte_nome or '___________________' }}",
            "",
            "Provvedimento impugnato: {{ provvedimento_impugnato or atto_impugnato or '___________________' }}",
            "{% if procedimento_riferimento %}Riferimento: {{ procedimento_riferimento }}{% endif %}",
            "",
            "MOTIVI DI IMPUGNAZIONE",
            "{{ motivi_impugnazione or motivi_speciali or '___________________' }}",
            "",
            "CONCLUSIONI",
            "{{ domande_conclusioni or '___________________' }}",
            "",
            "{% if istanza_cautelare %}ISTANZA CAUTELARE / SOSPENSIVA",
            "{{ istanza_cautelare }}",
            "",
            "{% endif %}{% if documenti_allegati %}DOCUMENTI ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_esecuzione(title: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or 'Giudice dell esecuzione') | upper }}",
            "",
            title.upper(),
            "",
            "Creditore / istante: {{ cliente.nome_completo or '___________________' }}",
            "Contro: {{ controparte_nome or '___________________' }}",
            "",
            "Titolo esecutivo: {{ titolo_esecutivo or '___________________' }}",
            "{% if precetto_riferimento %}Precetto: {{ precetto_riferimento }}{% endif %}",
            "{% if procedimento_riferimento %}Procedimento: {{ procedimento_riferimento }}{% endif %}",
            "",
            "{% if beni_o_crediti %}Beni / crediti individuati",
            "{{ beni_o_crediti }}",
            "",
            "{% endif %}RICHIESTA",
            "{{ richiesta_esecutiva or domande_conclusioni or '___________________' }}",
            "",
            "{% if documenti_allegati %}ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_famiglia(title: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or 'Tribunale competente') | upper }}",
            "",
            title.upper(),
            "",
            "Ricorrente / istante: {{ cliente.nome_completo or '___________________' }}",
            "Contro: {{ controparte_nome or '___________________' }}",
            "",
            "SITUAZIONE FAMILIARE",
            "{{ situazione_familiare or fatti_rilevanti or '___________________' }}",
            "",
            "{% if figli_coinvolti %}FIGLI / BENEFICIARI",
            "{{ figli_coinvolti }}",
            "",
            "{% endif %}{% if interesse_minore %}INTERESSE DEL MINORE / BENEFICIARIO",
            "{{ interesse_minore }}",
            "",
            "{% endif %}RICHIESTE",
            "{{ condizioni_richieste or domande_conclusioni or '___________________' }}",
            "",
            "{% if documenti_allegati %}DOCUMENTI ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_lavoro(title: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or 'Tribunale del lavoro competente') | upper }}",
            "",
            title.upper(),
            "",
            "Ricorrente / lavoratore: {{ cliente.nome_completo or '___________________' }}",
            "Contro: {{ controparte_nome or '___________________' }}",
            "",
            "RAPPORTO DI LAVORO / POSIZIONE",
            "{{ rapporto_lavoro or '___________________' }}",
            "",
            "FATTI",
            "{{ fatti_rilevanti or '___________________' }}",
            "",
            "ARGOMENTAZIONI",
            "{{ argomentazioni_lavoro or motivi_in_diritto or '___________________' }}",
            "",
            "DOMANDE",
            "{{ domande_conclusioni or '___________________' }}",
            "",
            "{% if documenti_allegati %}DOCUMENTI ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_penale(title: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or 'Autorita giudiziaria procedente') | upper }}",
            "",
            title.upper(),
            "",
            "Assistito / istante: {{ assistito_nome or parti.assistito_principale.nome_completo or cliente.nome_completo or '___________________' }}",
            "{% if procedimento_riferimento %}Procedimento: {{ procedimento_riferimento }}{% endif %}",
            "",
            "OGGETTO",
            "{{ oggetto_atto or '___________________' }}",
            "",
            "FATTO",
            "{{ fatti_rilevanti or '___________________' }}",
            "",
            "ARGOMENTAZIONI DIFENSIVE",
            "{{ argomentazioni_difensive or '___________________' }}",
            "",
            "RICHIESTE",
            "{{ richieste_penali or domande_conclusioni or '___________________' }}",
            "",
            "{% if documenti_allegati %}ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_amministrativo_tributario(title: str, resistant_label: str) -> str:
    return "\n".join(
        [
            "{{ (autorita_competente or 'Autorita giurisdizionale competente') | upper }}",
            "",
            title.upper(),
            "",
            "Ricorrente / appellante: {{ cliente.nome_completo or '___________________' }}",
            resistant_label + ": {{ ente_resistente or controparte_nome or '___________________' }}",
            "",
            "Atto impugnato / riferimento: {{ atto_impugnato or provvedimento_impugnato or '___________________' }}",
            "{% if procedimento_riferimento %}Procedimento: {{ procedimento_riferimento }}{% endif %}",
            "",
            "FATTI",
            "{{ fatti_rilevanti or '___________________' }}",
            "",
            "MOTIVI",
            "{{ motivi_speciali or motivi_impugnazione or '___________________' }}",
            "",
            "CONCLUSIONI",
            "{{ domande_conclusioni or '___________________' }}",
            "",
            "{% if istanza_cautelare %}ISTANZA CAUTELARE",
            "{{ istanza_cautelare }}",
            "",
            "{% endif %}{% if documenti_allegati %}DOCUMENTI ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_notifica(title: str) -> str:
    return "\n".join(
        [
            title.upper(),
            "",
            "Istante / difensore: {{ avvocato_nome }}",
            "{% if procedimento_riferimento %}Procedimento: {{ procedimento_riferimento }}{% endif %}",
            "{% if autorita_competente %}Autorita: {{ autorita_competente }}{% endif %}",
            "",
            "Atto / attivita richiesta: {{ atto_da_notificare or oggetto_atto or '___________________' }}",
            "Destinatario: {{ destinatario_nome or controparte_nome or '___________________' }}",
            "{% if destinatario_indirizzo %}Indirizzo / PEC: {{ destinatario_indirizzo }}{% endif %}",
            "",
            "RICHIESTA",
            "{{ richiesta_notifica or contenuto_istanza or '___________________' }}",
            "",
            "{% if documenti_allegati %}ALLEGATI",
            "{{ documenti_allegati }}",
            "",
            "{% endif %}Luogo e data: ___________________, {{ data_oggi }}",
            "",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _body_stragiudiziale(title: str) -> str:
    return "\n".join(
        [
            "{{ studio_nome }}",
            "{{ studio_indirizzo }}",
            "",
            title.upper(),
            "",
            "{{ data_oggi }}",
            "",
            "Spett.le {{ destinatario_nome or controparte_nome or '___________________' }}",
            "{{ destinatario_indirizzo or controparte_indirizzo or '___________________' }}",
            "",
            "Oggetto: {{ oggetto_atto or '___________________' }}",
            "",
            "Il/La sottoscritto/a Avv. {{ avvocato_nome }}, nell'interesse di {{ cliente.nome_completo or '___________________' }},",
            "",
            "espone quanto segue:",
            "{{ descrizione_inadempimento or fatti_rilevanti or '___________________' }}",
            "",
            "Pertanto richiede:",
            "{{ richiesta_formale or domande_conclusioni or '___________________' }}",
            "",
            "{% if termine_assegnato %}Si invita ad adempiere entro {{ termine_assegnato }}.{% endif %}",
            "{% if note_finali %}{{ note_finali }}{% endif %}",
            "",
            "Cordiali saluti",
            "Avv. {{ avvocato_nome }}",
        ]
    )


def _render_body(family: str, title: str, spec: dict[str, Any]) -> str:
    if family == "procura":
        return _body_procura(title)
    if family == "mandato_speciale":
        return _body_procura(title, special=True)
    if family == "nomina_domiciliatario":
        return _body_nomina_domiciliatario(title)
    if family == "revoca_mandato":
        return _body_revoca_rinuncia(title, "la revoca del mandato")
    if family == "rinuncia_mandato":
        return _body_revoca_rinuncia(title, "la rinuncia al mandato")
    if family == "elezione_domicilio":
        return _body_elezione_domicilio(title)
    if family in {"civile_intro", "monitorio_cautelare"}:
        return _body_giudiziale(title)
    if family == "civile_processuale":
        return _body_processuale(title)
    if family == "impugnazione_civile":
        return _body_impugnazione(title)
    if family == "esecuzione":
        return _body_esecuzione(title)
    if family == "famiglia":
        return _body_famiglia(title)
    if family == "lavoro":
        return _body_lavoro(title)
    if family == "penale":
        return _body_penale(title)
    if family == "amministrativo":
        return _body_amministrativo_tributario(title, "Amministrazione resistente")
    if family == "tributario":
        return _body_amministrativo_tributario(title, "Ente resistente")
    if family == "notifica":
        return _body_notifica(title)
    if family == "stragiudiziale":
        return _body_stragiudiziale(title)
    return _body_processuale(title)


def _spec(
    codice: str,
    titolo: str,
    *,
    categoria: str,
    collezione: str,
    area: str,
    branca: str,
    sottobranca: str,
    fase: str,
    rito: str,
    grado: str,
    canale_telematico: str,
    profilo_deposito: str,
    family: str,
    varianti: Iterable[str] | None = None,
    link_compilatore_code: str = "",
    descrizione: str = "",
    microtema: str = "",
    field_names: Iterable[str] | None = None,
    allegati_obbligatori: Iterable[str] | None = None,
    controlli_conformita: Iterable[str] | None = None,
) -> dict[str, Any]:
    default_family = FAMILY_DEFAULTS[family]
    names = list(field_names or default_family["field_names"])
    return {
        "id": f"builtin-{codice.lower()}",
        "codice": codice,
        "titolo": titolo,
        "categoria": categoria,
        "collezione": collezione,
        "area": area,
        "branca": branca,
        "sottobranca": sottobranca,
        "microtema": microtema,
        "fase": fase,
        "rito": rito,
        "grado": grado,
        "canale_telematico": canale_telematico,
        "profilo_deposito": profilo_deposito,
        "family": family,
        "field_names": names,
        "varianti": list(varianti or []),
        "link_compilatore_code": link_compilatore_code,
        "descrizione": descrizione,
        "allegati_obbligatori": list(allegati_obbligatori or default_family["allegati_obbligatori"]),
        "controlli_conformita": list(controlli_conformita or default_family["controlli_conformita"]),
    }


def _group(common: dict[str, Any], entries: list[tuple[str, dict[str, Any] | None]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for codice, extra in entries:
        payload = dict(common)
        payload.update(extra or {})
        titolo = payload.pop("titolo")
        items.append(_spec(codice=codice, titolo=titolo, **payload))
    return items


_COMPILER_AREA_DEFAULTS: dict[str, dict[str, str]] = {
    "STRAGIUDIZIALE": {
        "categoria": "Stragiudiziale collegato",
        "collezione": "Stragiudiziale collegato",
        "area": "Stragiudiziale",
        "branca": "Stragiudiziale",
        "sottobranca": "Comunicazioni, accordi e pareri",
        "fase": "Stragiudiziale",
        "rito": "Trasversale",
        "grado": "N/A",
        "canale_telematico": "Misto",
        "profilo_deposito": "uso_studio",
        "family": "stragiudiziale",
    },
    "PENALE": {
        "categoria": "Penale",
        "collezione": "Penale",
        "area": "Penale",
        "branca": "Penale",
        "sottobranca": "Difesa, istanze e impugnazioni",
        "fase": "Indagini / giudizio / impugnazione",
        "rito": "Penale",
        "grado": "Tutti",
        "canale_telematico": "PDP",
        "profilo_deposito": "atto_introduttivo",
        "family": "penale",
    },
    "AMMINISTRATIVO": {
        "categoria": "Amministrativo",
        "collezione": "Amministrativo",
        "area": "Amministrativo",
        "branca": "Amministrativo",
        "sottobranca": "Ricorsi, memorie e cautelare",
        "fase": "Introduttiva / successiva / impugnazione",
        "rito": "PAT / SIGA",
        "grado": "TAR / Consiglio di Stato",
        "canale_telematico": "PAT / SIGA",
        "profilo_deposito": "atto_introduttivo",
        "family": "amministrativo",
    },
    "TRIBUTARIO": {
        "categoria": "Tributario",
        "collezione": "Tributario",
        "area": "Tributario",
        "branca": "Tributario",
        "sottobranca": "Ricorsi, controdeduzioni e appelli",
        "fase": "Introduttiva / successiva / impugnazione",
        "rito": "PTT / SIGIT",
        "grado": "Primo grado / appello",
        "canale_telematico": "PTT / SIGIT",
        "profilo_deposito": "atto_introduttivo",
        "family": "tributario",
    },
    "FAMIGLIA": {
        "categoria": "Famiglia e volontaria giurisdizione",
        "collezione": "Famiglia e volontaria giurisdizione",
        "area": "Famiglia e Persone",
        "branca": "Famiglia e persone",
        "sottobranca": "Separazione, divorzio e volontaria giurisdizione",
        "fase": "Introduttiva / volontaria giurisdizione / impugnazione",
        "rito": "Famiglia e minori",
        "grado": "Tutti",
        "canale_telematico": "PCT",
        "profilo_deposito": "atto_introduttivo",
        "family": "famiglia",
    },
    "LAVORO": {
        "categoria": "Lavoro e previdenza",
        "collezione": "Lavoro e previdenza",
        "area": "Lavoro e Previdenza",
        "branca": "Lavoro e previdenza",
        "sottobranca": "Ricorsi, memorie e previdenza",
        "fase": "Introduttiva / successiva / impugnazione",
        "rito": "Rito lavoro",
        "grado": "Primo grado / appello",
        "canale_telematico": "PCT",
        "profilo_deposito": "atto_introduttivo",
        "family": "lavoro",
    },
    "SOCIETARIO": {
        "categoria": "Societario",
        "collezione": "Societario",
        "area": "Societario",
        "branca": "Societario",
        "sottobranca": "Pareri, contratti e contenzioso",
        "fase": "Consulenza / contenzioso",
        "rito": "Trasversale",
        "grado": "Tutti",
        "canale_telematico": "Misto",
        "profilo_deposito": "uso_studio",
        "family": "stragiudiziale",
    },
    "IMMIGRAZIONE": {
        "categoria": "Immigrazione e cittadinanza",
        "collezione": "Immigrazione e cittadinanza",
        "area": "Immigrazione",
        "branca": "Immigrazione e cittadinanza",
        "sottobranca": "Ricorsi, permessi e protezione",
        "fase": "Amministrativa / giudiziale",
        "rito": "Speciale",
        "grado": "Tutti",
        "canale_telematico": "Misto",
        "profilo_deposito": "atto_introduttivo",
        "family": "amministrativo",
    },
}


def _compiler_profile_for_model(model: dict[str, Any]) -> str:
    code = str(model.get("code", "") or "")
    title = str(model.get("name", "") or "").lower()
    if "procura" in title or "mandato" in title:
        return "procura"
    if any(token in title for token in ("memoria", "note", "controdeduzioni", "deposito", "lista testi", "richiesta copie")):
        return "atto_successivo"
    if "cautel" in title or "sospensione" in title:
        return "atto_cautelare"
    if any(token in title for token in ("appello", "impugnazione", "reclamo", "cassazione", "opposizione")):
        return "impugnazione"
    if code.startswith("STR_") or model.get("area") in {"STRAGIUDIZIALE", "SOCIETARIO"}:
        return "uso_studio"
    return "atto_introduttivo"


def _compiler_family_for_model(model: dict[str, Any]) -> str:
    area = str(model.get("area", "") or "")
    code = str(model.get("code", "") or "")
    title = str(model.get("name", "") or "").lower()
    if code == "CIV_PROCBASE_001":
        return "procura"
    if code == "CIV_NOTIFBASE_001":
        return "notifica"
    if code in {"CIV_PREC_001", "CIV_PPT_001", "CIV_OPESE_001", "CIV_OPATTESE_001", "CIV_PIGBASE_001"} or code.startswith("CIV_ESE_"):
        return "esecuzione"
    if code in {"CIV_RDI_001", "CIV_OPPDI_001", "CIV_RCAUT_001", "CIV_ICAUT_001", "CIV_SFRINT_001", "CIV_CONVSFR_001"} or code.startswith("CIV_INT_"):
        return "monitorio_cautelare"
    if code in {"CIV_APP_001"} or code.startswith("CIV_IMP_"):
        return "impugnazione_civile"
    if code in {"CIV_MEM_001", "CIV_IST_001", "CIV_DEPDOC_001"}:
        return "civile_processuale"
    if code in {"CIV_CIT_001", "CIV_COM_001", "CIV_LAVRIC_001", "CIV_LAVMEM_001"}:
        return "civile_intro"
    if area == "STRAGIUDIZIALE":
        return "stragiudiziale"
    if area == "PENALE":
        return "penale"
    if area == "AMMINISTRATIVO":
        return "amministrativo"
    if area == "TRIBUTARIO":
        return "tributario"
    if area == "FAMIGLIA":
        return "famiglia"
    if area == "LAVORO":
        return "lavoro"
    if area == "IMMIGRAZIONE":
        return "amministrativo"
    if area == "SOCIETARIO":
        if any(token in title for token in ("ricorso", "memoria", "responsabilita")):
            return "civile_intro"
        return "stragiudiziale"
    return "civile_processuale"


def _compiler_civile_meta(model: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    code = str(model.get("code", "") or "")
    title = str(model.get("name", "") or "").lower()
    if code == "CIV_PROCBASE_001":
        meta.update(
            {
                "categoria": "Procure, nomine e deleghe",
                "collezione": "Procure e deleghe",
                "branca": "Procure e deleghe",
                "sottobranca": "Mandati e domiciliazioni",
                "fase": "Mandato difensivo",
                "rito": "Trasversale",
                "grado": "Tutti",
            }
        )
        return meta
    if code in {"CIV_NOTIFBASE_001", "CIV_DEPDOC_001"}:
        meta.update(
            {
                "categoria": "UNEP e notificazioni",
                "collezione": "UNEP e notificazioni",
                "branca": "UNEP e notificazioni",
                "sottobranca": "Notifiche, depositi e fascicolo telematico",
                "fase": "Supporto al deposito",
                "rito": "PCT",
                "grado": "Tutti",
            }
        )
        return meta
    if code in {"CIV_PREC_001", "CIV_PPT_001", "CIV_OPESE_001", "CIV_OPATTESE_001", "CIV_PIGBASE_001"} or code.startswith("CIV_ESE_"):
        meta.update(
            {
                "categoria": "Esecuzioni",
                "collezione": "Esecuzioni",
                "branca": "Esecuzioni",
                "sottobranca": "Precetti, pignoramenti e opposizioni",
                "fase": "Esecuzione forzata",
                "rito": "Esecuzioni",
                "grado": "Primo grado",
                "profilo_deposito": "atto_introduttivo",
            }
        )
        return meta
    if code in {"CIV_RDI_001", "CIV_OPPDI_001", "CIV_RCAUT_001", "CIV_ICAUT_001", "CIV_SFRINT_001", "CIV_CONVSFR_001"} or code.startswith("CIV_INT_"):
        meta.update(
            {
                "categoria": "Monitorio e cautelare",
                "collezione": "Monitorio e cautelare",
                "branca": "Monitorio e cautelare",
                "sottobranca": "Ricorsi d'urgenza, monitori e sfratti",
                "fase": "Introduttiva / cautelare",
                "rito": "Monitorio / cautelare / locatizio",
                "grado": "Primo grado",
                "profilo_deposito": "atto_cautelare" if "cautel" in title or "sospensione" in title else "atto_introduttivo",
            }
        )
        return meta
    if code in {"CIV_APP_001"} or code.startswith("CIV_IMP_"):
        meta.update(
            {
                "categoria": "Impugnazioni civili",
                "collezione": "Impugnazioni civili",
                "branca": "Impugnazioni civili",
                "sottobranca": "Appelli, reclami e rimedi impugnatori",
                "fase": "Impugnazione",
                "rito": "Appello / cassazione / reclamo",
                "grado": "Impugnazione",
                "profilo_deposito": "impugnazione",
            }
        )
        return meta
    meta.update(
        {
            "categoria": "Civile ordinario",
            "collezione": "Civile ordinario",
            "branca": "Civile ordinario",
            "sottobranca": "Introduttivi, difensivi e istanze",
            "fase": "Introduzione e trattazione",
            "rito": "Ordinario / semplificato",
            "grado": "Primo grado",
            "profilo_deposito": "atto_successivo" if any(token in title for token in ("memoria", "istanza", "deposito")) else "atto_introduttivo",
        }
    )
    return meta


def _compiler_meta_for_model(model: dict[str, Any]) -> dict[str, Any]:
    area = str(model.get("area", "") or "")
    meta = dict(
        _COMPILER_AREA_DEFAULTS.get(
            area,
            {
                "categoria": AREA_LABELS.get(area, area.title()),
                "collezione": AREA_LABELS.get(area, area.title()),
                "area": AREA_LABELS.get(area, area.title()),
                "branca": AREA_LABELS.get(area, area.title()),
                "sottobranca": "Atti e modelli",
                "fase": "Operativa",
                "rito": "Trasversale",
                "grado": "Tutti",
                "canale_telematico": "Misto",
                "profilo_deposito": "atto_introduttivo",
                "family": "civile_processuale",
            },
        )
    )
    meta["family"] = _compiler_family_for_model(model)
    meta["profilo_deposito"] = _compiler_profile_for_model(model)
    if area == "CIVILE":
        meta = _compiler_civile_meta(model, meta)
        meta["family"] = _compiler_family_for_model(model)
        return meta
    title = str(model.get("name", "") or "").lower()
    if area == "PENALE" and any(token in title for token in ("memoria", "note", "richiesta copie", "deposito", "lista testi")):
        meta["profilo_deposito"] = "atto_successivo"
    if area == "AMMINISTRATIVO" and any(token in title for token in ("memoria", "note", "deposito", "istanza di segreteria", "motivi aggiunti")):
        meta["profilo_deposito"] = "atto_successivo"
    if area == "TRIBUTARIO" and any(token in title for token in ("controdeduzioni", "memoria", "deposito")):
        meta["profilo_deposito"] = "atto_successivo"
    if area == "FAMIGLIA" and any(token in title for token in ("memoria", "reclamo", "appello")):
        meta["profilo_deposito"] = "atto_successivo" if "memoria" in title else "impugnazione"
    if area == "LAVORO" and "appello" in title:
        meta["profilo_deposito"] = "impugnazione"
    return meta


def _build_compiler_coverage_templates(existing_templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    covered_codes = {
        str(item.get("link_compilatore_code", "") or "").strip()
        for item in existing_templates
        if str(item.get("link_compilatore_code", "") or "").strip()
    }
    generated: list[dict[str, Any]] = []
    for model in MODELS:
        code = str(model.get("code", "") or "").strip()
        if not code or code in covered_codes:
            continue
        meta = _compiler_meta_for_model(model)
        generated.append(
            _spec(
                codice=code,
                titolo=str(model.get("name", "") or code),
                categoria=meta["categoria"],
                collezione=meta["collezione"],
                area=meta["area"],
                branca=meta["branca"],
                sottobranca=meta["sottobranca"],
                fase=meta["fase"],
                rito=meta["rito"],
                grado=meta["grado"],
                canale_telematico=meta["canale_telematico"],
                profilo_deposito=meta["profilo_deposito"],
                family=meta["family"],
                varianti=[AREA_LABELS.get(str(model.get("area", "") or ""), str(model.get("area", "") or "").title())],
                link_compilatore_code=code,
                descrizione=(
                    f"Template built-in derivato dal compilatore guidato per {str(model.get('name', '') or code).lower()}, "
                    f"collocato automaticamente nella collezione {meta['collezione'].lower()}."
                ),
                allegati_obbligatori=get_essential_docs(code),
            )
        )
    return generated


BUILTIN_TEMPLATE_SPECS: list[dict[str, Any]] = []

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Procure, nomine e deleghe",
            "collezione": "Procure e deleghe",
            "area": "Civile",
            "branca": "Procure e deleghe",
            "sottobranca": "Mandati e domiciliazioni",
            "fase": "Mandato difensivo",
            "rito": "Trasversale",
            "grado": "Tutti",
            "canale_telematico": "Misto",
            "profilo_deposito": "procura",
            "family": "procura",
            "varianti": ["mandato difensivo", "conferimento poteri"],
        },
        [
            ("TMP-PROC-001", {"titolo": "Procura alle liti"}),
            ("TMP-PROC-002", {"titolo": "Procura generale alle liti"}),
            ("TMP-PROC-003", {"titolo": "Procura speciale per ricorso monitorio", "family": "mandato_speciale"}),
            ("TMP-PROC-004", {"titolo": "Procura speciale per appello", "family": "mandato_speciale"}),
            ("TMP-PROC-005", {"titolo": "Procura speciale per ricorso per cassazione", "family": "mandato_speciale"}),
            ("TMP-PROC-006", {"titolo": "Procura per fase esecutiva", "family": "mandato_speciale"}),
            ("TMP-PROC-007", {"titolo": "Nomina domiciliatario", "family": "nomina_domiciliatario"}),
            ("TMP-PROC-008", {"titolo": "Revoca del mandato difensivo", "family": "revoca_mandato"}),
            ("TMP-PROC-009", {"titolo": "Rinuncia al mandato", "family": "rinuncia_mandato"}),
            ("TMP-PROC-010", {"titolo": "Elezione di domicilio", "family": "elezione_domicilio"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "UNEP e notificazioni",
            "collezione": "UNEP e notificazioni",
            "area": "Civile",
            "branca": "Notifiche e adempimenti",
            "sottobranca": "UNEP, notifica in proprio e allegati",
            "fase": "Esterna / deposito accessorio",
            "rito": "Trasversale",
            "grado": "Tutti",
            "canale_telematico": "Misto",
            "profilo_deposito": "atto_esterno",
            "family": "notifica",
            "varianti": ["UNEP", "PEC", "notifica in proprio"],
        },
        [
            ("TMP-NOT-001", {"titolo": "Atto UNEP"}),
            ("TMP-NOT-002", {"titolo": "Atto per notificazione in proprio"}),
            ("TMP-NOT-003", {"titolo": "Relata di notifica PEC"}),
            ("TMP-NOT-004", {"titolo": "Deposito telematico documenti", "family": "civile_processuale"}),
            ("TMP-NOT-005", {"titolo": "Visibilita fascicolo telematico", "family": "civile_processuale"}),
            ("TMP-NOT-006", {"titolo": "Fascicolo di parte", "family": "civile_processuale"}),
            ("TMP-NOT-007", {"titolo": "Attestazione di conformita", "family": "notifica"}),
            ("TMP-NOT-008", {"titolo": "Indice allegati", "family": "civile_processuale"}),
            ("TMP-NOT-009", {"titolo": "Note iscrizione ruolo", "family": "civile_processuale"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Stragiudiziale collegato",
            "collezione": "Stragiudiziale collegato",
            "area": "Stragiudiziale",
            "branca": "Diffide e atti stragiudiziali",
            "sottobranca": "Richieste, intimazioni e lettere",
            "fase": "Precontenziosa",
            "rito": "Stragiudiziale",
            "grado": "N/A",
            "canale_telematico": "PEC / analogico",
            "profilo_deposito": "atto_esterno",
            "family": "stragiudiziale",
            "varianti": ["diffida", "messa in mora", "sollecito"],
        },
        [
            ("TMP-STR-001", {"titolo": "Diffida stragiudiziale collegata al fascicolo"}),
            ("TMP-STR-002", {"titolo": "Sollecito di pagamento"}),
            ("TMP-STR-003", {"titolo": "Lettera adeguamento canone locazione"}),
            ("TMP-STR-004", {"titolo": "Diffida ad adempiere"}),
            ("TMP-STR-005", {"titolo": "Richiesta di documentazione"}),
            ("TMP-STR-006", {"titolo": "Comunicazione di riserva diritti"}),
            ("TMP-STR-007", {"titolo": "Invito a negoziazione assistita"}),
            ("TMP-STR-008", {"titolo": "Atto di messa in mora"}),
        ],
    )
)


def build_builtin_templates() -> list[dict[str, Any]]:
    compiler_links = compiler_binding_map_by_title()
    templates: list[dict[str, Any]] = []
    all_specs = list(BUILTIN_TEMPLATE_SPECS)
    all_specs.extend(_build_compiler_coverage_templates(all_specs))
    for order, spec in enumerate(all_specs, start=1):
        item = deepcopy(spec)
        family = item.pop("family")
        field_names = item.pop("field_names")
        item["builtin"] = True
        item["descrizione"] = _description_for(item)
        item["note"] = item["descrizione"]
        item["parole_chiave"] = _keywords_for(item)
        item["campi_guidati"] = _copy_fields(*field_names)
        item["corpo"] = _render_body(family, item["titolo"], item)
        item["ordine"] = order
        if not item.get("link_compilatore_code"):
            binding = compiler_links.get(item["titolo"])
            if binding:
                item["link_compilatore_code"] = binding["compiler_code"]
        templates.append(item)
    return templates

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Lavoro e previdenza",
            "collezione": "Lavoro e previdenza",
            "area": "Lavoro e Previdenza",
            "branca": "Lavoro e previdenza",
            "sottobranca": "Ricorsi e impugnazioni",
            "fase": "Introduttiva / impugnazione",
            "rito": "Rito lavoro",
            "grado": "Primo grado / appello",
            "canale_telematico": "PCT",
            "profilo_deposito": "atto_introduttivo",
            "family": "lavoro",
            "varianti": ["lavoro subordinato", "previdenza", "disciplinare"],
        },
        [
            ("TMP-LAV-001", {"titolo": "Ricorso lavoro", "link_compilatore_code": "LAV_RIC_001"}),
            ("TMP-LAV-002", {"titolo": "Memoria difensiva nel rito lavoro", "profilo_deposito": "atto_successivo", "link_compilatore_code": "LAV_MEM_001"}),
            ("TMP-LAV-003", {"titolo": "Ricorso d'urgenza in materia di lavoro", "family": "monitorio_cautelare"}),
            ("TMP-LAV-004", {"titolo": "Impugnazione licenziamento", "link_compilatore_code": "LAV_IMPLIC_001"}),
            ("TMP-LAV-005", {"titolo": "Ricorso per differenze retributive"}),
            ("TMP-LAV-006", {"titolo": "Ricorso previdenziale", "link_compilatore_code": "LAV_PREV_001"}),
            ("TMP-LAV-007", {"titolo": "Appello nel rito lavoro", "family": "impugnazione_civile", "link_compilatore_code": "LAV_APP_001"}),
            ("TMP-LAV-008", {"titolo": "Ricorso monitorio in materia di lavoro", "family": "monitorio_cautelare"}),
            ("TMP-LAV-009", {"titolo": "Opposizione a decreto ingiuntivo in materia di lavoro", "family": "monitorio_cautelare"}),
            ("TMP-LAV-010", {"titolo": "Ricorso per condotta antisindacale"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Penale",
            "collezione": "Penale",
            "area": "Penale",
            "branca": "Difesa penale",
            "sottobranca": "Atti difensivi e richieste",
            "fase": "Indagini / dibattimento / cautelare",
            "rito": "Penale",
            "grado": "Tutti",
            "canale_telematico": "PDP",
            "profilo_deposito": "atto_difensivo",
            "family": "penale",
            "varianti": ["indagini preliminari", "udienza", "cautelare"],
        },
        [
            ("TMP-PEN-001", {"titolo": "Querela"}),
            ("TMP-PEN-002", {"titolo": "Denuncia"}),
            ("TMP-PEN-003", {"titolo": "Nomina del difensore di fiducia", "link_compilatore_code": "PEN_NOM_001"}),
            ("TMP-PEN-004", {"titolo": "Opposizione alla richiesta di archiviazione"}),
            ("TMP-PEN-005", {"titolo": "Memoria difensiva penale", "link_compilatore_code": "PEN_MEM_001"}),
            ("TMP-PEN-006", {"titolo": "Istanza di riesame di misura cautelare"}),
            ("TMP-PEN-007", {"titolo": "Appello cautelare penale"}),
            ("TMP-PEN-008", {"titolo": "Ricorso per cassazione penale"}),
            ("TMP-PEN-009", {"titolo": "Atto di costituzione di parte civile"}),
            ("TMP-PEN-010", {"titolo": "Lista testi"}),
            ("TMP-PEN-011", {"titolo": "Istanza di incidente probatorio"}),
            ("TMP-PEN-012", {"titolo": "Istanza di revoca o sostituzione della misura cautelare"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Amministrativo",
            "collezione": "Amministrativo",
            "area": "Amministrativo",
            "branca": "Giustizia amministrativa",
            "sottobranca": "Ricorsi e appelli",
            "fase": "Introduttiva / impugnazione",
            "rito": "PAT",
            "grado": "TAR / Consiglio di Stato",
            "canale_telematico": "PAT",
            "profilo_deposito": "atto_introduttivo",
            "family": "amministrativo",
            "varianti": ["TAR", "Consiglio di Stato", "motivi aggiunti"],
        },
        [
            ("TMP-AMM-001", {"titolo": "Ricorso al TAR", "link_compilatore_code": "AMM_RIC_001"}),
            ("TMP-AMM-002", {"titolo": "Motivi aggiunti", "profilo_deposito": "atto_successivo", "link_compilatore_code": "AMM_MOTAGG_001"}),
            ("TMP-AMM-003", {"titolo": "Appello al Consiglio di Stato", "family": "impugnazione_civile", "link_compilatore_code": "AMM_APPCDS_001"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Tributario",
            "collezione": "Tributario",
            "area": "Tributario",
            "branca": "Contenzioso tributario",
            "sottobranca": "Ricorso e difese",
            "fase": "Introduttiva / appello",
            "rito": "PTT",
            "grado": "Primo grado / appello",
            "canale_telematico": "PTT",
            "profilo_deposito": "atto_introduttivo",
            "family": "tributario",
            "varianti": ["ricorso", "controdeduzioni", "appello"],
        },
        [
            ("TMP-TRIB-001", {"titolo": "Ricorso tributario", "link_compilatore_code": "TRIB_RIC_001"}),
            ("TMP-TRIB-002", {"titolo": "Controdeduzioni nel giudizio tributario", "profilo_deposito": "atto_successivo", "link_compilatore_code": "TRIB_CONTRO_001"}),
            ("TMP-TRIB-003", {"titolo": "Appello tributario", "family": "impugnazione_civile", "link_compilatore_code": "TRIB_APP_001"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Impugnazioni civili",
            "collezione": "Impugnazioni civili",
            "area": "Civile",
            "branca": "Impugnazioni",
            "sottobranca": "Appello, cassazione e rimedi",
            "fase": "Impugnazione",
            "rito": "Ordinario",
            "grado": "Appello / legittimita",
            "canale_telematico": "PCT",
            "profilo_deposito": "impugnazione",
            "family": "impugnazione_civile",
            "varianti": ["appello", "cassazione", "revocazione"],
        },
        [
            ("TMP-IMP-001", {"titolo": "Atto di appello", "link_compilatore_code": "CIV_APP_001"}),
            ("TMP-IMP-002", {"titolo": "Comparsa di costituzione in appello", "family": "civile_processuale"}),
            ("TMP-IMP-003", {"titolo": "Ricorso per cassazione", "grado": "Cassazione"}),
            ("TMP-IMP-004", {"titolo": "Controricorso", "grado": "Cassazione"}),
            ("TMP-IMP-005", {"titolo": "Ricorso per revocazione"}),
            ("TMP-IMP-006", {"titolo": "Opposizione di terzo"}),
            ("TMP-IMP-007", {"titolo": "Ricorso per regolamento di competenza"}),
            ("TMP-IMP-008", {"titolo": "Ricorso per regolamento di giurisdizione"}),
            ("TMP-IMP-009", {"titolo": "Istanza di sospensione dell'esecutivita della sentenza"}),
            ("TMP-IMP-010", {"titolo": "Istanza di correzione errore materiale", "family": "civile_processuale"}),
            ("TMP-IMP-011", {"titolo": "Istanza di integrazione del contraddittorio", "family": "civile_processuale"}),
            ("TMP-IMP-012", {"titolo": "Reclamo", "family": "impugnazione_civile"}),
            ("TMP-IMP-013", {"titolo": "Ricorso ex legge Pinto"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Esecuzioni",
            "collezione": "Esecuzioni",
            "area": "Civile",
            "branca": "Esecuzioni civili",
            "sottobranca": "Espropriazione e opposizioni",
            "fase": "Esecutiva",
            "rito": "Esecuzione forzata",
            "grado": "Primo grado",
            "canale_telematico": "PCT",
            "profilo_deposito": "atto_esecutivo",
            "family": "esecuzione",
            "varianti": ["mobiliare", "immobiliare", "terzi"],
        },
        [
            ("TMP-ESE-001", {"titolo": "Atto di precetto", "link_compilatore_code": "CIV_PREC_001"}),
            ("TMP-ESE-002", {"titolo": "Pignoramento mobiliare"}),
            ("TMP-ESE-003", {"titolo": "Pignoramento presso terzi", "link_compilatore_code": "CIV_PPT_001"}),
            ("TMP-ESE-004", {"titolo": "Pignoramento immobiliare"}),
            ("TMP-ESE-005", {"titolo": "Istanza di ricerca telematica dei beni", "family": "civile_processuale"}),
            ("TMP-ESE-006", {"titolo": "Istanza di vendita"}),
            ("TMP-ESE-007", {"titolo": "Istanza di assegnazione"}),
            ("TMP-ESE-008", {"titolo": "Opposizione all'esecuzione", "link_compilatore_code": "CIV_OPESE_001"}),
            ("TMP-ESE-009", {"titolo": "Opposizione agli atti esecutivi", "link_compilatore_code": "CIV_OPATTESE_001"}),
            ("TMP-ESE-010", {"titolo": "Opposizione di terzo all'esecuzione"}),
            ("TMP-ESE-011", {"titolo": "Istanza di conversione del pignoramento"}),
            ("TMP-ESE-012", {"titolo": "Istanza di riduzione del pignoramento"}),
            ("TMP-ESE-013", {"titolo": "Intervento del creditore"}),
            ("TMP-ESE-014", {"titolo": "Istanza di sospensione della procedura esecutiva"}),
            ("TMP-ESE-015", {"titolo": "Nota di precisazione del credito", "family": "civile_processuale"}),
            ("TMP-ESE-016", {"titolo": "Dichiarazione 553 c.p.c.", "family": "civile_processuale"}),
            ("TMP-ESE-017", {"titolo": "Pignoramento stipendio o pensione", "link_compilatore_code": "CIV_PPT_001"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Famiglia e volontaria giurisdizione",
            "collezione": "Famiglia e volontaria giurisdizione",
            "area": "Famiglia e Persone",
            "branca": "Famiglia, persone e volontaria giurisdizione",
            "sottobranca": "Separazione, divorzio e tutele",
            "fase": "Introduttiva / camerale",
            "rito": "Famiglia e VG",
            "grado": "Primo grado",
            "canale_telematico": "PCT",
            "profilo_deposito": "atto_introduttivo",
            "family": "famiglia",
            "varianti": ["separazione", "divorzio", "giudice tutelare"],
        },
        [
            ("TMP-FAM-001", {"titolo": "Ricorso per separazione consensuale", "link_compilatore_code": "FAM_SEPC_001"}),
            ("TMP-FAM-002", {"titolo": "Ricorso per separazione giudiziale", "link_compilatore_code": "FAM_SEPG_001"}),
            ("TMP-FAM-003", {"titolo": "Ricorso per divorzio congiunto", "link_compilatore_code": "FAM_DIVC_001"}),
            ("TMP-FAM-004", {"titolo": "Ricorso per divorzio giudiziale", "link_compilatore_code": "FAM_DIVG_001"}),
            ("TMP-FAM-005", {"titolo": "Ricorso per modifica condizioni di separazione", "link_compilatore_code": "FAM_MOD_001"}),
            ("TMP-FAM-006", {"titolo": "Ricorso per modifica condizioni di divorzio", "link_compilatore_code": "FAM_MOD_001"}),
            ("TMP-FAM-007", {"titolo": "Ricorso per affidamento e mantenimento figli", "link_compilatore_code": "FAM_AFF_001"}),
            ("TMP-FAM-008", {"titolo": "Ricorso per ordine di protezione contro gli abusi familiari"}),
            ("TMP-FAM-009", {"titolo": "Ricorso per autorizzazione ad atto di straordinaria amministrazione del minore"}),
            ("TMP-FAM-010", {"titolo": "Ricorso per amministrazione di sostegno", "link_compilatore_code": "FAM_ADS_001"}),
            ("TMP-FAM-011", {"titolo": "Istanze al giudice tutelare"}),
            ("TMP-FAM-014", {"titolo": "Istanza al giudice tutelare"}),
            ("TMP-FAM-012", {"titolo": "Volontaria giurisdizione"}),
            ("TMP-FAM-013", {"titolo": "Ricorso per decreto tavolare"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Civile ordinario",
            "collezione": "Civile ordinario",
            "area": "Civile",
            "branca": "Civile ordinario",
            "sottobranca": "Introduttivi e difensivi",
            "fase": "Introduzione e trattazione",
            "rito": "Ordinario / semplificato",
            "grado": "Primo grado",
            "canale_telematico": "PCT",
            "profilo_deposito": "atto_introduttivo",
            "family": "civile_intro",
            "varianti": ["civile ordinario", "contenzioso"],
        },
        [
            ("TMP-CIV-001", {"titolo": "Atto di citazione", "link_compilatore_code": "CIV_CIT_001"}),
            ("TMP-CIV-002", {"titolo": "Ricorso ex art. 702-bis / rito semplificato"}),
            ("TMP-CIV-003", {"titolo": "Comparsa di costituzione e risposta", "link_compilatore_code": "CIV_COM_001"}),
            ("TMP-CIV-004", {"titolo": "Memoria n. 1", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-005", {"titolo": "Memoria n. 2", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-006", {"titolo": "Memoria n. 3", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-007", {"titolo": "Memoria generica", "family": "civile_processuale", "profilo_deposito": "atto_successivo", "link_compilatore_code": "CIV_MEM_001"}),
            ("TMP-CIV-008", {"titolo": "Memoria istruttoria", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-009", {"titolo": "Nota di deposito", "family": "civile_processuale", "profilo_deposito": "atto_successivo", "link_compilatore_code": "CIV_DEPDOC_001"}),
            ("TMP-CIV-010", {"titolo": "Istanza di rinvio", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-011", {"titolo": "Istanza di trattazione scritta", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-012", {"titolo": "Note d'udienza", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-019", {"titolo": "Note conclusive", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-013", {"titolo": "Comparsa conclusionale", "family": "civile_processuale", "profilo_deposito": "atto_successivo", "link_compilatore_code": "CIV_CONCL_001"}),
            ("TMP-CIV-014", {"titolo": "Memoria di replica", "family": "civile_processuale", "profilo_deposito": "atto_successivo", "link_compilatore_code": "CIV_REPL_001"}),
            ("TMP-CIV-015", {"titolo": "Istanza di anticipazione udienza", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-016", {"titolo": "Istanza di riunione procedimenti", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-017", {"titolo": "Istanza di separazione procedimenti", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CIV-018", {"titolo": "Riassunzione del giudizio"}),
        ],
    )
)

BUILTIN_TEMPLATE_SPECS.extend(
    _group(
        {
            "categoria": "Monitorio e cautelare",
            "collezione": "Monitorio e cautelare",
            "area": "Civile",
            "branca": "Monitorio, cautelare e possessorio",
            "sottobranca": "Ricorsi speciali",
            "fase": "Introduttiva / cautelare",
            "rito": "Monitorio e cautelare",
            "grado": "Primo grado",
            "canale_telematico": "PCT",
            "profilo_deposito": "atto_introduttivo",
            "family": "monitorio_cautelare",
            "varianti": ["monitorio", "urgenza", "possessorio"],
        },
        [
            ("TMP-CAUT-001", {"titolo": "Ricorso per decreto ingiuntivo", "link_compilatore_code": "CIV_RDI_001"}),
            ("TMP-CAUT-002", {"titolo": "Opposizione a decreto ingiuntivo", "link_compilatore_code": "CIV_OPPDI_001"}),
            ("TMP-CAUT-003", {"titolo": "Istanza di provvisoria esecuzione", "family": "civile_processuale", "profilo_deposito": "atto_successivo"}),
            ("TMP-CAUT-004", {"titolo": "Ricorso cautelare d'urgenza", "link_compilatore_code": "CIV_RCAUT_001"}),
            ("TMP-CAUT-005", {"titolo": "Reclamo cautelare", "family": "impugnazione_civile"}),
            ("TMP-CAUT-006", {"titolo": "Ricorso per sequestro conservativo"}),
            ("TMP-CAUT-007", {"titolo": "Ricorso per sequestro giudiziario"}),
            ("TMP-CAUT-008", {"titolo": "Denuncia di nuova opera"}),
            ("TMP-CAUT-009", {"titolo": "Denuncia di danno temuto"}),
            ("TMP-CAUT-010", {"titolo": "Azione di manutenzione nel possesso"}),
            ("TMP-CAUT-011", {"titolo": "Azione di reintegrazione nel possesso"}),
            ("TMP-CAUT-012", {"titolo": "Ricorso per accertamento tecnico preventivo"}),
        ],
    )
)
