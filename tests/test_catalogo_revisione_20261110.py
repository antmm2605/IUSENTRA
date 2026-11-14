"""Revisione del catalogo del 10/11/2026: regressioni con esempi fittizi (nessun dato dello studio).

Fonti verificate sul testo vigente: art. 415 e 127-ter c.p.c.; art. 136 c.p.c. e art. 16, comma 4, D.L. 179/2012;
art. 13 D.M. 44/2011; artt. 9, 192 e 248 D.P.R. 115/2002; art. 152 disp. att. c.p.c.
"""
from types import SimpleNamespace

from pct.archivio_letture.pertinenza_documentale import natura_documentale
from pct.document_intelligence import DocumentAIRepository
from pct.document_intelligence.catalog_pipeline import FascicoloDocumentCatalogPipeline
from pct.document_intelligence.catalog_resolver import RESOLVER_VERSION, _content_identity, resolve_document_catalog
from pct.document_intelligence.catalog_sources import CATALOG_SOURCES, catalog_source_row
from pct.document_intelligence.catalog_titoli import identita_dal_titolo
from tests.test_fascicolo_document_catalog_pipeline import _lavoro, _ready_source


def _voce(testo, **contesto):
    identita = _content_identity(testo, **contesto)
    return identita.classification.label if identita else None


DECRETO_VISTO = (
    "Fissazione udienza discussione n. cronol. 100/2026 del 02/02/2026 RG n. 10/2026\n\n"
    "TRIBUNALE DI ROMA Sezione Lavoro\n\nIl Giudice del lavoro, dott. Mario Bianchi,\n\n"
    "- visto il ricorso iscritto al n. 10/2026 RG;\n- visto il carico di ruolo;\n"
    "fissa l'udienza del 16/04/2026 e dispone che sia sostituita ai sensi dell'art. 127-ter c.p.c. dal deposito di "
    "note di trattazione scritta entro il termine perentorio; onera parte ricorrente di notificare il ricorso e il "
    "presente decreto.\n\nRoma, 02/02/2026. Il Giudice del Lavoro"
)
DECRETO_SENZA_TITOLO = DECRETO_VISTO.split("\n\n", 1)[1]
NOTE_DI_PARTE = (
    "Tribunale di Milano\n\nSezione Lavoro\n\nDott.ssa Anna Verdi\n\n*Udienza del 30.06.2026* *Trattazione scritta*\n\n"
    "*R.G. 518/2026* *Per*\nLa Prof.ssa *Rossi Maria,* rappresentata e difesa dall'Avv. Paolo Neri con procura a margine, "
    "contro MINISTERO. In osservanza del provvedimento con cui è stata disposta la trattazione scritta dell'udienza, "
    "il sottoscritto difensore precisa le conclusioni ai sensi dell'art. 127-ter c.p.c."
)


def test_decreto_di_fissazione_con_visto_il_ricorso_anche_senza_titolo():
    assert _voce(DECRETO_VISTO) == "Decreto di fissazione udienza"
    assert _voce(DECRETO_SENZA_TITOLO) == "Decreto di fissazione udienza"
    identita = _content_identity(DECRETO_SENZA_TITOLO)
    assert identita.fonte == "normattiva_cpc_art_415_decreto_fissazione"


def test_le_note_di_parte_che_riportano_il_decreto_restano_note():
    assert _voce(NOTE_DI_PARTE) == "Note scritte ex art. 127-ter c.p.c."
    # L'atto di parte che dice «visto il ricorso … fissa» non diventa un decreto.
    assert _voce("TRIBUNALE DI ROMA\nIl Giudice\nvisto il ricorso fissa udienza\n" + "rappresentata e difesa dall'Avv. X") != "Decreto di fissazione udienza"


def test_titolo_con_asterischi_riconosciuto():
    testo = "*Note scritte ex art. 127-ter c.p.c.*\n\nPer la sig.ra Rossi, udienza del 10/03/2026, si precisano le conclusioni."
    esito = identita_dal_titolo(testo)
    assert esito is not None and esito["label"] == "Note scritte ex art. 127-ter c.p.c."


PEC_DEPOSITO = (
    "Oggetto: DEPOSITO TELEMATICO: Ricorso Rossi [JQ1-L01] [RefID_001_abc]\n"
    "Mittente: \"Avv. Paolo Neri\" <paolo.neri@pec.it>\nDestinatari: tribunale.roma@civile.ptel.giustiziacert.it\n"
    "Data: Wed, 10 Jun 2026 10:34:28 +0200\n\nCorpo email:\nEgregio sig. Cancelliere, allego il file (crittografato) "
    "\"Atto.enc\".\n\nAllegati leggibili:\n[Allegato: Atto.enc]\nBusta cifrata per l'ufficio: non leggibile per legge."
)
COPIA_IN_CHIARO = (
    "Oggetto: DEPOSITO TELEMATICO: Ricorso Rossi [JQ1-L01] [RefID_001_abc]\n"
    "Mittente: \"Avv. Paolo Neri\" <paolo.neri@pec.it>\nDestinatari: tribunale.roma@civile.ptel.giustiziacert.it\n\n"
    "Corpo email:\nEgregio sig. Cancelliere, allego il file (crittografato) \"Atto.enc\".\n\n"
    "[Allegato: DatiAtto.xml.p7m; parte 1.2]\n<?xml version=\"1.0\"?><Ricorso/>"
)
COMUNICAZIONE = (
    "Oggetto: POSTA CERTIFICATA: COMUNICAZIONE 1733/2026/LAV\n"
    "Mittente: \"Per conto di: tribunale.roma@civile.ptel.giustiziacert.it\" <posta-certificata@legalmail.it>\n"
    "Destinatari: paolo.neri@pec.it\nData: Wed, 10 Jun 2026 13:03:22 +0200\n\nCorpo email:\nMessaggio di posta certificata. "
    "Il messaggio originale è incluso in allegato."
)


def test_pec_di_deposito_copia_in_chiaro_e_comunicazione_di_cancelleria():
    assert _voce(PEC_DEPOSITO) == "PEC di deposito telematico"
    assert _voce(COPIA_IN_CHIARO) == "Copia non crittografata del deposito telematico"
    assert _voce(COMUNICAZIONE) == "Comunicazione di cancelleria"
    assert _content_identity(COMUNICAZIONE).fonte == "normattiva_cpc_art_136_comunicazioni"
    # Lo stesso oggetto da un mittente qualsiasi resta un messaggio PEC.
    assert _voce(COMUNICAZIONE.replace("tribunale.roma@civile.ptel.giustiziacert.it", "studio@pec.it")) == "Messaggio PEC"


def test_la_fonte_della_regola_arriva_alle_evidenze():
    esito = resolve_document_catalog(
        tenant_id="t", fascicolo_id="F", document_id="D", document_sha256="a" * 64, filename="x.eml",
        extracted_text=COMUNICAZIONE, document_metadata={"archive_reading": True},
        fascicolo_context={"tipo_fascicolo": "lavoro"})
    fonti = {e.locator for e in esito.evidence if e.evidence_type == "legal_source"}
    assert {"normattiva_cpc_art_136_comunicazioni", "normattiva_dl_179_2012_art16_comunicazioni_telematiche"} <= fonti


F23 = ("Mod. F23 AGENZIA DELLE ENTRATE 1. VERSAMENTO DIRETTO AL CONCESSIONARIO 2. DELEGA IRREVOCABILE A banca "
       "DATI DEL VERSAMENTO 11. CODICE TRIBUTO 12. DESCRIZIONE CONTRIBUTO UNIFICATO 21,50 PER UN IMPORTO COMPLESSIVO")
PAGOPA = ("RICEVUTA DI PAGAMENTO AVVISO PAGOPA\nGentile Maria Rossi, di seguito i dati del pagamento dell'avviso pagoPA da te "
          "disposto in data 27/03/2025. Ente Creditore: Ministero della Giustizia. Causale: contributo unificato. Importo: € 98,00")
EQUITALIA_AVVISO = ("TRIBUNALE DI ROMA Rec.Cred.N.000971/2024 Equitalia Giustizia S.p.A. QUANTO E QUANDO PAGARE? entro un mese "
                    "21,50 Euro sul sito di Equitalia Giustizia S.p.A., con la tua app di pagamento. Codice avviso 3050")
EQUITALIA_PAGATO = ("Pagamento CBILL numero 31459930, inserito in data 25/03/2025. CAUSALE PAGAMENTO: EQUITALIA GIUSTIZIA S.P.A. "
                    "CODICE AVVISO: 305000000068906093 IMPORTO: 49,00 € TOTALE ADDEBITATO: 50,50 €")
DICHIARAZIONE_152 = ("STUDIO LEGALE NERI\nAUTOCERTIFICAZIONE DELLA SITUAZIONE REDDITUALE (art. 46 del D.P.R. 445/2000)\n"
                     "La ricorrente dichiara, secondo quanto disposto dall'art. 152, d.a. c.p.c., di essere titolare di un "
                     "reddito imponibile pari o inferiore a due volte l'importo dell'art. 76 D.P.R. 115/2002.")
ESENZIONE_CU = ("AUTOCERTIFICAZIONE DELLA SITUAZIONE REDDITUALE\n(art. 46 del D.P.R. 445/2000)\nESENZIONE DAL CONTRIBUTO "
                "UNIFICATO DI ISCRIZIONE A RUOLO AI SENSI DELL'ART. 9 COMMA 1 BIS D.P.R. 115/2002\nIl sottoscritto dichiara")


def test_contributo_unificato_f23_pagopa_equitalia_e_dichiarazione_152():
    assert _voce(F23) == "Contributo unificato / pagamento"
    assert _voce(PAGOPA) == "Contributo unificato / pagamento"
    assert _voce(EQUITALIA_AVVISO) == "Avviso di pagamento Equitalia Giustizia (recupero crediti di giustizia)"
    assert _voce(EQUITALIA_AVVISO + " contributo unificato") == "Contributo unificato / invito pagamento"
    assert _voce(EQUITALIA_PAGATO) == "Pagamento a Equitalia Giustizia (recupero crediti di giustizia)"
    assert _voce(DICHIARAZIONE_152) == "Dichiarazione di reddito ex art. 152 disp. att. c.p.c."
    assert _voce(ESENZIONE_CU) == "Contributo unificato / esenzione"
    # Un ricorso che allega la ricevuta pagoPA resta un atto della parte.
    ricorso = "RICORSO\nLa sig.ra Rossi, rappresentata e difesa dall'Avv. Neri, " + PAGOPA
    assert _voce(ricorso) != "Contributo unificato / pagamento"


SENTENZA_CASSAZIONE = (
    "Numero registro generale 10072/2023 Numero di raccolta generale 29961/2023 REPUBBLICA ITALIANA IN NOME DEL POPOLO "
    "ITALIANO LA CORTE SUPREMA DI CASSAZIONE SEZIONE LAVORO ha pronunciato la seguente SENTENZA")


def test_precedente_riconosciuto_anche_senza_rg_del_fascicolo():
    natura, _ = natura_documentale(SENTENZA_CASSAZIONE, "", "", "Tribunale di Vicenza")
    assert natura == "precedente_giurisprudenziale"
    assert natura_documentale(SENTENZA_CASSAZIONE, "", "", "Corte di Cassazione")[0] == ""
    assert natura_documentale(SENTENZA_CASSAZIONE, "", "", "")[0] == ""


def test_fonti_nuove_registrate_e_datate():
    for chiave in ("normattiva_cpc_art_136_comunicazioni", "normattiva_dl_179_2012_art16_comunicazioni_telematiche",
                   "normattiva_dm_44_2011_art_13_busta", "normattiva_cpc_art_415_decreto_fissazione",
                   "normattiva_dpr_115_2002_art192_pagamento_cu", "normattiva_dpr_115_2002_art248_invito_pagamento",
                   "normattiva_disp_att_cpc_art152_dichiarazione_reddito"):
        riga = catalog_source_row(chiave)
        assert riga["official_url"].startswith("https://www.normattiva.it/uri-res/N2Ls?urn:nir:")
        assert riga["last_verified_at"] == "2026-11-10"
    assert "normattiva_cpc_art_127ter_note_scritte" in CATALOG_SOURCES


def test_voce_lex_contraddetta_da_regola_sicura_torna_da_verificare(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    tenant_id, fascicolo_id = "studio-test", "FASC-LEX"
    source = _ready_source(repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-DEC",
                           filename="decreto.pdf", sha256="e" * 64, text=DECRETO_VISTO, tipo_documento="DECRETO")
    pipeline = FascicoloDocumentCatalogPipeline(repo)
    pipeline.run(tenant_id=tenant_id, fascicolo=_lavoro(fascicolo_id), sources=[source], actor="operatore", process=True)
    conn = repo._conn()
    conn.execute(
        "UPDATE document_catalog_assignments SET document_label='Note di trattazione scritta', resolver_version='vecchia', "
        "reason='Seconda lettura Lex: note di parte (la regola proponeva «Contenuto da verificare»).' "
        "WHERE tenant_id=? AND fascicolo_id=?", (tenant_id, fascicolo_id))
    conn.commit()

    pipeline.run(tenant_id=tenant_id, fascicolo=_lavoro(fascicolo_id), sources=[source], actor="operatore", process=True)

    voce = repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-DEC")
    assert voce.resolver_version == RESOLVER_VERSION
    assert voce.status == "review_required" and voce.document_label == "Decreto di fissazione udienza"
    assert voce.metadata["voce_lex_precedente"]["document_label"] == "Note di trattazione scritta"
    assert "seconda lettura Lex aveva proposto «Note di trattazione scritta»" in voce.reason


def test_ricatalogazione_per_versione_a_lotti(monkeypatch):
    import web.services.catalogo_archivio_runtime as runtime

    monkeypatch.setattr(runtime, "LOTTO_RICATALOGAZIONE", 2)
    documenti = [SimpleNamespace(id=f"D{i}", nome=f"d{i}.pdf", fonte_documento="", tipo="", id_deposito_pct="",
                                 nome_portale="", classificazione_portale="") for i in range(5)]
    fascicolo = SimpleNamespace(id="F1", documenti=documenti, tribunale="", numero_rg="", anno_rg="")
    oggetti = [SimpleNamespace(tipo="documento", presente=True, oggetto_id=d.id, sha256=f"{i:064d}", sha256_archivio="")
               for i, d in enumerate(documenti)]
    record = lambda i: SimpleNamespace(id=f"R{i}", sha256=f"{i:064d}", status="ready", updated_at="1", current_version_id="v",
                                       original_filename="x", safe_filename="x", file_type="pdf", mime_type="", size_bytes=1)
    vecchie = [SimpleNamespace(document_id=d.id, document_sha256=f"{i:064d}", updated_at="1", source_state="verified_snapshot",
                               status="proposed", resolver_version="vecchia", document_version_id="v", profile_id=None)
               for i, d in enumerate(documenti)]
    repository = SimpleNamespace(
        backend_kind="sqlite", list_documents=lambda t, f: [record(i) for i in range(5)],
        list_catalog_assignments=lambda t, f: vecchie,
        get_extracted_text=lambda *a: SimpleNamespace(text="testo dell'atto", extraction_engine="pdf"))
    sources, _, report = runtime.prepara_catalogo(fascicolo, oggetti, repository, "t")
    assert len(sources) == 2 and report["deferred_to_next_round"] == 3
    # La rilettura puntuale di documenti scelti non ha il tetto del lotto.
    sources, _, report = runtime.prepara_catalogo(fascicolo, oggetti, repository, "t", document_ids={d.id for d in documenti})
    assert len(sources) == 5 and report["deferred_to_next_round"] == 0


def test_messaggi_falliti_per_la_busta_si_rileggono_una_volta():
    from web.services.archivio_letture_runtime import _messaggi_falliti_per_la_busta

    stato = {"source_notes": [{"filename": "DEPOSITO TELEMATICO: Ricorso.eml"}, {"filename": "Atto.enc"}, {"filename": "Atto.enc.bin"}]}
    assert _messaggi_falliti_per_la_busta(stato) == 1
    assert _messaggi_falliti_per_la_busta({}) == 0


def test_cedolino_prospetto_paga():
    cedolino = ("Ministero dell'Economia e delle Finanze NoiPA RATA: Novembre 2025 ID CEDOLINO: 18C2 Anagrafica del dipendente "
                "Cognome: ROSSI Nome: MARIA Ente di appartenenza: MINISTERO competenze fisse ritenute previdenziali netto")
    identita = _content_identity(cedolino)
    # Stessa voce e stessa fonte della regola del titolo «Cedolino/Prospetto di paga» (art. 1 L. 4/1953).
    assert identita.classification.label == "Prospetto di paga"
    assert identita.fonte == "normattiva_legge_4_1953_prospetto_paga"


def test_documenti_d_ufficio_non_sono_atti_di_parte():
    polis = ("Numero protocollo: m_pi.AOOPOLIS.REGISTRO UFFICIALE.I.100.23-07-2025. INFORMATIZZAZIONE NOMINE SUPPLENZE "
             "AVVERTENZA La compilazione della presente istanza avviene secondo le disposizioni del D.P.R. 28 dicembre 2000, n. 445")
    tabellare = ("Prot. 100/2023 Tribunale di Roma Decreto n. 25/2023 OGGETTO: Variazione tabellare concernente il settore civile. "
                 "IL PRESIDENTE DEL TRIBUNALE dispone")
    giudicato = ("TRIBUNALE ORDINARIO di ROMA - Sezione Lavoro Il sottoscritto Funzionario, esaminati gli atti ed i registri "
                 "informatici di questo Ufficio, CERTIFICA che contro la sentenza n. 1/2024 non è stato proposto appello")
    assert _voce(polis) == "Istanza online al Ministero dell'istruzione (POLIS)"
    assert _voce(tabellare) == "Decreto di variazione tabellare dell'ufficio giudiziario"
    assert _voce(giudicato) == "Certificato della cancelleria sull'impugnazione della sentenza"
    assert _content_identity(giudicato).fonte == "normattiva_disp_att_cpc_art124_giudicato"


def test_autocertificazione_esenzione_cu_anche_con_tabella_ocr_e_non_il_ricorso():
    tabella = ("|residente a|Il/La sottoscritto/a MARIA ROSSI della dichiarazione non veritiera ai sensi dell'art. 75 del D.P.R. "
               "445 del 28/12/2000 l'importo di Euro 38.514,03 relativamente all'anno Dichiara che il proprio nucleo familiare è "
               "composto da:|AUTOCERTIFICAZIONE DELLA SITUAZIONE REDDITUALE (art. 46 del D.P.R. 28/12/2000 n° 445) ESENZIONE DAL "
               "CONTRIBUTO UNIFICATO DI ISCRIZIONE A RUOLO AI SENSI DELL'ART. 9 COMMA 1 BIS D.P.R. 30/05/2002 N. 115 DICHIARA Che il "
               "proprio reddito, compreso quello dei familiari conviventi ex art. 76 D.P.R. 115/2002, non supera")
    esito = resolve_document_catalog(
        tenant_id="t", fascicolo_id="F", document_id="D", document_sha256="a" * 64, filename="x.pdf",
        extracted_text=tabella, document_metadata={"archive_reading": True}, fascicolo_context={"tipo_fascicolo": "lavoro"})
    assert esito.document_label == "Contributo unificato / esenzione"
    assert esito.status == "proposed" and esito.confidence >= 90
    ricorso = ("TRIBUNALE DI ROMA - SEZIONE LAVORO\nRICORSO EX ART. 414 C.P.C.\nLa sig.ra Maria Rossi, rappresentata e difesa "
               "dall'Avv. Paolo Neri, allega l'autocertificazione della situazione reddituale per l'esenzione dal contributo "
               "unificato (art. 9, comma 1-bis, D.P.R. 115/2002), essendo il suo reddito inferiore alla soglia.")
    assert _voce(ricorso) != "Contributo unificato / esenzione"


def test_senza_rg_la_sentenza_da_ottemperare_o_impugnata_non_e_un_precedente():
    sentenza_vicenza = ("Sentenza n. 97/2025 REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO TRIBUNALE ORDINARIO di VICENZA "
                        "Sezione Lavoro Il Tribunale ha pronunciato la seguente SENTENZA")
    assert natura_documentale(sentenza_vicenza, "", "", "TAR Venezia")[0] == ""
    assert natura_documentale(sentenza_vicenza, "", "", "Tribunale amministrativo del Veneto")[0] == ""
    assert natura_documentale(sentenza_vicenza, "", "", "Corte d'Appello di Venezia")[0] == ""
    assert natura_documentale(sentenza_vicenza, "", "", "Tribunale di Palmi")[0] == "precedente_giurisprudenziale"


def test_note_127ter_con_il_ruolo_sulla_riga_del_titolo():
    testo = ("Tribunale di Roma Sezione Lavoro\n\nDott.ssa Anna Verdi\n\nUdienza del 27.11.2025\n\n"
             "RGN 1612/2025 Note scritte in sostituzione dell’udienza\n\nPer la Prof.ssa Rossi, rappresentata e difesa dall'Avv. "
             "Neri, in vista dell'udienza sostituita ai sensi dell'art. 127-ter c.p.c. si precisano le conclusioni.")
    assert _voce(testo) == "Note scritte ex art. 127-ter c.p.c."
