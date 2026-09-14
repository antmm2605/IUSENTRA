"""La lettura del fascicolo: dai dati alla narrativa, senza inventare nulla.

Ogni caso costruisce un fascicolo di prova con `DatiLettura` e verifica che la
lettura dica solo ciò che i dati sostengono: la fase con la sua prova, i
depositi nella fase corretta (D.M. 44/2011), le notifiche perfezionate solo
con la consegna (L. 53/1994, art. 3-bis), i prossimi passi con la norma che
li fonda e le lacune dichiarate come tali.
"""

from __future__ import annotations

from datetime import date, timedelta

from pct.fascicolo_lettura import DatiLettura, componi, costruisci_lettura, lettura_come_payload
from pct.fascicolo_lettura.narrativa import ORDINE_SEZIONI
from pct.fascicolo_lettura.oggetto import LUNGHEZZA_MASSIMA_PETITUM, petitum

OGGI = date(2026, 9, 14)

TESTO_CITAZIONE = (
    "TRIBUNALE DI MILANO. ATTO DI CITAZIONE. Il sig. Mario Rossi, rappresentato e difeso dall'avv. Bianchi, "
    "premesso che il contratto di appalto del 3 marzo 2025 non è stato adempiuto, "
    "CITA la Alfa S.r.l. a comparire e conclude: voglia il Tribunale condannare la convenuta al pagamento di "
    "euro 25.000,00 oltre interessi e rivalutazione, con vittoria di spese. Si dichiara che il valore della causa è euro 25.000. "
    "Milano, 10 gennaio 2026."
)


def _fascicolo(**extra) -> dict:
    base = {
        "id": "F001",
        "numero": "2026/15",
        "titolo": "Rossi / Alfa S.r.l.",
        "cliente": "Mario Rossi",
        "controparte": "Alfa S.r.l.",
        "oggetto": "Inadempimento contratto di appalto",
        "tribunale": "Tribunale di Milano",
        "numero_rg": "1234",
        "anno_rg": "2026",
        "stato": "IN_CORSO",
        "tipo": "CIVILE",
        "area_pratica": "civile",
        "valore_causa": 25000,
        "data_apertura": "2026-01-05",
    }
    base.update(extra)
    return base


def _documento(id_doc: str, nome: str, testo: str = "", data: str = "2026-01-10", **extra) -> dict:
    documento = {"id": id_doc, "nome": nome, "tipo": "ATTO", "data_documento": data, "lex_read": bool(testo), "lex_text_excerpt": testo}
    documento.update(extra)
    return documento


def _voce_catalogo(id_doc: str, label: str, natura: str, sezione: str, status: str = "confirmed", confidence: int = 96) -> dict:
    return {
        "document_id": id_doc,
        "document_label": label,
        "document_nature": natura,
        "document_section": sezione,
        "status": status,
        "confidence": confidence,
        "legal_area": "civile",
    }


def _deposito(stato: str, atto: str = "Atto di citazione", timestamp: str = "2026-02-01T10:30:00") -> dict:
    return {
        "id": f"D-{stato}",
        "timestamp": timestamp,
        "stato": stato,
        "tipo_atto": "CITAZIONE",
        "nome_atto_principale": atto,
        "pec_destinatario": "tribunale.milano@civile.ptel.giustiziacert.it",
        "ricevuta_accettazione": "RAC-1" if stato != "INVIATO" else "",
        "ricevuta_consegna": "RDC-1" if stato not in {"INVIATO", "ACCETTATO_PEC"} else "",
        "documenti_ids": ["A1"],
    }


def _presidio(status: str, label: str, atto: str = "Atto di citazione", destinatario: str = "Alfa S.r.l.") -> dict:
    return {
        "id": f"N-{status}",
        "status": status,
        "status_label": label,
        "channel_label": "PEC in proprio (L. 53/1994)",
        "recipients": [{"name": destinatario}],
        "document": {"name": atto},
        "source_effective_at": "2026-01-20T09:00:00",
        "next_action": "Acquisire la ricevuta di avvenuta consegna",
        "legal_sources": ["L. 53/1994, art. 3-bis"],
    }


def _caso_completo() -> DatiLettura:
    documenti = [
        _documento("A1", "citazione.pdf", TESTO_CITAZIONE),
        _documento("P1", "procura.pdf", "PROCURA ALLE LITI. Io sottoscritto Mario Rossi delego l'avv. Bianchi.", data="2026-01-08"),
        _documento("V1", "verbale_udienza.pdf", "Verbale di udienza del 15 giugno 2026. Il giudice rinvia per l'ammissione dei mezzi di prova.", data="2026-06-15"),
        _documento("S1", "screenshot.png", "", data="2026-06-16"),
    ]
    catalogo = [
        _voce_catalogo("A1", "Atto di citazione", "atto_principale", "atti"),
        _voce_catalogo("P1", "Procura alle liti", "procura", "procure"),
        _voce_catalogo("V1", "Verbale di udienza", "provvedimento", "provvedimenti", status="proposed", confidence=90),
        _voce_catalogo("S1", "Documento", "", "", status="review_required", confidence=0),
    ]
    attivita = [
        {"id": "AT1", "tipo": "UDIENZA", "data": "2026-06-15", "titolo": "Prima udienza di comparizione", "esito": "RINVIATO"},
        {"id": "AT2", "tipo": "NOTIFICA", "data": "2026-01-20", "titolo": "Notifica citazione a Alfa S.r.l.", "esito": "FAVOREVOLE"},
    ]
    scadenze = [
        {"id": "SC1", "titolo": "Memoria istruttoria n. 1 (art. 171-ter c.p.c.)", "data": (OGGI + timedelta(days=5)).isoformat(), "stato": "APERTO"},
        {"id": "SC2", "titolo": "Udienza di ammissione prove", "data": (OGGI + timedelta(days=20)).isoformat(), "stato": "APERTO"},
    ]
    return DatiLettura(
        fascicolo=_fascicolo(data_prossima_udienza=(OGGI + timedelta(days=20)).isoformat()),
        documenti=documenti,
        catalogo=catalogo,
        attivita=attivita,
        depositi=[_deposito("ACCETTATO_CANCELLERIA")],
        notifiche=[_presidio("DELIVERY_COMPLETE", "Consegna completata")],
        scadenze=scadenze,
        appuntamenti=[],
        conformita={"blocking_issues": [], "missing_documents": []},
        regia={"next_action": "Predisporre la memoria istruttoria n. 1"},
        economico={"summary": {"totale_preventivi": 1, "totale_conferimenti": 1, "totale_fatturato": 1500.0, "totale_incassato": 0.0}},
        parti=[{"ruolo": "attore", "nome": "Mario Rossi"}, {"ruolo": "convenuto", "nome": "Alfa S.r.l."}],
        oggi=OGGI,
    )


def test_lettura_completa_dice_quadro_oggetto_fase_e_prossimi_passi():
    lettura = costruisci_lettura(_caso_completo())

    testata = lettura["intestazione"]
    assert testata["rg"] == "1234/2026"
    assert testata["parti"] == {"attore": ["Mario Rossi"], "convenuto": ["Alfa S.r.l."]}
    assert testata["valore_causa"] == "€ 25.000,00"

    # La domanda e' citata dal testo dell'atto principale, non riassunta.
    domanda = lettura["oggetto"]["domanda"]
    assert domanda["etichetta"] == "Atto di citazione"
    assert domanda["petitum"].startswith("conclude: voglia il Tribunale condannare la convenuta")
    assert "Si dichiara" not in domanda["petitum"]

    # La fase la dicono le prove: udienza tenuta -> trattazione.
    assert lettura["fase"]["codice"] == "trattazione"
    assert any("udienza del 15/06/2026" in prova for prova in lettura["fase"]["prove"])
    assert lettura["fase"]["prossima_udienza"] == (OGGI + timedelta(days=20)).strftime("%d/%m/%Y")

    # Deposito perfezionato e notifica consegnata sono letti nella fase giusta.
    assert lettura["depositi"]["perfezionati"][0]["fase"] == "accettato dalla cancelleria"
    assert lettura["depositi"]["in_corso"] == [] and lettura["depositi"]["falliti"] == []
    assert len(lettura["notifiche"]["perfezionate"]) == 2  # presidio consegnato + attivita' favorevole
    assert lettura["notifiche"]["aperte"] == []

    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert azioni[0].startswith("Adempiere a «Memoria istruttoria n. 1")
    assert lettura["prossimi_passi"][0]["urgenza"] == 1
    assert "Predisporre la memoria istruttoria n. 1" in azioni
    # Il documento senza testo lo legge il presidio documentale: nessun compito all'avvocato.
    assert not any("catalogazione" in azione.lower() and "1 documento" in azione for azione in azioni)
    # Il verbale «proposto» è una proposta pronta: la conferma è un clic dell'avvocato.
    assert "Confermare con un clic le 1 proposta di catalogazione pronte" in azioni
    assert "Seguire l'incasso del saldo aperto di € 1.500,00" in azioni
    assert lettura["stato_passi"] == {"attivi": True, "motivo": ""}
    assert len(lettura["prossimi_passi"]) <= 8

    assert lettura["lacune"] == ["1 documento in attesa di lettura dal presidio documentale: la lettura non può ancora citarne il contenuto"]

    narrativa = lettura["narrativa"]
    for titolo in ("Quadro della pratica", "Di che cosa tratta", "Che cosa è stato fatto", "Depositi e notifiche", "A che punto siamo", "Prossimi passaggi", "Lacune da colmare"):
        assert titolo in narrativa, titolo
    assert "RG 1234/2026" in narrativa
    assert "voglia il Tribunale condannare" in narrativa
    assert "Nessuna evidenza" not in narrativa


def test_lettura_e_serializzabile_e_datata_in_italiano():
    lettura = costruisci_lettura(_caso_completo())
    payload = lettura_come_payload(lettura)
    assert payload["generata_il"] == "14/09/2026"
    assert payload["versione"].startswith("2026.")
    import json

    json.dumps(payload)  # nessun oggetto interno nel payload


def test_fascicolo_vuoto_non_inventa_e_dichiara_le_lacune():
    lettura = costruisci_lettura(DatiLettura(fascicolo={"id": "F0", "titolo": "Nuova pratica", "stato": "APERTO"}, oggi=OGGI))
    assert lettura["fase"]["codice"] == "stragiudiziale"
    assert lettura["oggetto"]["domanda"] is None
    assert lettura["cronologia"] == []
    assert lettura["prossimi_passi"] == []
    assert "ufficio giudiziario non indicato" in lettura["lacune"]
    assert "Nessuna attività, deposito o notifica risulta registrata" in lettura["narrativa"]
    assert "Nessun adempimento risulta aperto" in lettura["narrativa"]
    assert "la materia va dichiarata" in lettura["narrativa"]


def test_sentenza_catalogata_porta_in_fase_decisa_con_passo_di_impugnazione():
    dati = _caso_completo()
    dati.documenti.append(_documento("SE1", "sentenza.pdf", "REPUBBLICA ITALIANA. IN NOME DEL POPOLO ITALIANO. Il Tribunale di Milano ha pronunciato la seguente SENTENZA.", data="2026-09-01"))
    dati.catalogo.append(_voce_catalogo("SE1", "Sentenza", "provvedimento", "provvedimenti"))
    lettura = costruisci_lettura(dati)

    assert lettura["fase"]["codice"] == "decisa"
    assert "Sentenza del 01/09/2026" in lettura["fase"]["descrizione"]
    assert lettura["fase"]["incoerenze"], "stato «in corso» con sentenza va segnalato"
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["azione"].startswith("Valutare l'impugnazione"))
    assert passo["norma"] == "art. 325 c.p.c.; art. 327 c.p.c."
    assert "trenta giorni" in passo["motivo"] and "sei mesi" in passo["motivo"]
    assert passo["template"] == "CIV_APPELLO_BREVE"
    assert all(fonte["url"].startswith("https://www.normattiva.it/") for fonte in passo["fonti"])
    assert passo["urgenza"] == 1


def test_deposito_rifiutato_e_passo_urgente_con_il_motivo_del_rifiuto():
    dati = _caso_completo()
    dati.depositi = [_deposito("RIFIUTATO_CANCELLERIA", atto="Memoria ex art. 171-ter", timestamp="2026-09-10T15:00:00")]
    lettura = costruisci_lettura(dati)

    assert lettura["depositi"]["falliti"][0]["fase"] == "rifiutato dalla cancelleria"
    assert lettura["depositi"]["perfezionati"] == []
    primo = lettura["prossimi_passi"][0]
    assert primo["urgenza"] == 0
    assert primo["azione"] == "Ripetere il deposito di «Memoria ex art. 171-ter»"
    assert "rifiutato dalla cancelleria" in primo["motivo"]
    assert lettura["depositi"]["falliti"][0]["data_ora"] == "10/09/2026 ore 15:00"
    assert "10/09/2026 Memoria ex art. 171-ter: rifiutato dalla cancelleria" in lettura["narrativa"]


def test_deposito_in_corso_lo_controlla_il_presidio_non_l_avvocato():
    dati = _caso_completo()
    dati.depositi = [_deposito("CONSEGNATO", timestamp="2026-09-01T10:00:00")]
    lettura = costruisci_lettura(dati)
    assert lettura["depositi"]["in_corso"][0]["attesa"] == "in attesa dell'esito dei controlli automatici"
    # Senza verifiche automatiche ancora eseguite: nessun compito di verifica all'avvocato.
    assert not any(passo["fonte"] == "presidio depositi" for passo in lettura["prossimi_passi"])
    assert "non ha ancora l'accettazione della cancelleria" in " ".join(lettura["lacune"])
    assert "Non ancora eseguite" in lettura["narrativa"]

    # PEC dello studio non configurata: il passo è configurarla, non leggere le ricevute a mano.
    dati.verifiche = {"eseguita_il": "2026-09-14T10:00:00+02:00", "eseguita_il_it": "14/09/2026 ore 10:00", "esiti": {"depositi": {"pendenti": 1, "esito": "pec_non_configurata"}}}
    lettura = costruisci_lettura(dati)
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["fonte"] == "presidio depositi")
    assert passo["azione"].startswith("Configurare la casella PEC dello studio")
    assert passo["href"] == "/impostazioni" and passo["norma"] == "D.M. 44/2011, art. 13"
    assert "casella PEC dello studio non configurata" in lettura["narrativa"]

    # Ricevute controllate dal presidio e deposito ancora senza esito da giorni: anomalia da decidere.
    dati.verifiche = {"eseguita_il": "2026-09-14T10:00:00+02:00", "eseguita_il_it": "14/09/2026 ore 10:00", "esiti": {"depositi": {"pendenti": 1, "esito": "controllate", "controllati": 1, "aggiornati": 0, "errori": 0}}}
    lettura = costruisci_lettura(dati)
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["fonte"] == "presidio depositi")
    assert passo["azione"] == "Deposito «Atto di citazione» senza esito da 13 giorni nonostante il controllo automatico delle ricevute"
    assert "controllo del 14/09/2026 ore 10:00" in passo["motivo"] and passo["urgenza"] == 1
    assert "ricevute controllate: 1 depositi controllati" in lettura["narrativa"]

    # Deposito di ieri: il presidio ha controllato, è presto per parlare di anomalia.
    dati.depositi = [_deposito("CONSEGNATO", timestamp=(OGGI - timedelta(days=1)).isoformat() + "T10:00:00")]
    lettura = costruisci_lettura(dati)
    assert not any(passo["fonte"] == "presidio depositi" for passo in lettura["prossimi_passi"])


def test_notifica_fallita_e_notifica_senza_consegna_sono_dette_chiaramente():
    dati = _caso_completo()
    dati.attivita = [voce for voce in dati.attivita if voce["tipo"] != "NOTIFICA"]
    dati.notifiche = [
        _presidio("DELIVERY_FAILED", "Consegna fallita", atto="Atto di citazione"),
        _presidio("SENT_WAITING_RAC", "Inviata, in attesa della ricevuta di accettazione", atto="Comparsa", destinatario="Beta S.p.A."),
    ]
    lettura = costruisci_lettura(dati)

    assert len(lettura["notifiche"]["fallite"]) == 1
    assert len(lettura["notifiche"]["aperte"]) == 2
    assert lettura["notifiche"]["perfezionate"] == []
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert "Rinnovare la notifica di «Atto di citazione»" in azioni
    # In attesa della ricevuta: la legge il presidio notifiche, non l'avvocato.
    assert not any("«Comparsa»" in azione for azione in azioni)
    assert "la notifica di «Comparsa» non ha ancora la ricevuta di avvenuta consegna" in lettura["lacune"]
    assert "Beta S.p.A." in lettura["narrativa"]


def test_scadenza_scaduta_e_il_primo_passo():
    dati = _caso_completo()
    dati.scadenze.append({"id": "SC0", "titolo": "Deposito comparsa di risposta", "data": (OGGI - timedelta(days=3)).isoformat(), "stato": "APERTO"})
    dati.scadenze.append({"id": "SC9", "titolo": "Scadenza chiusa", "data": (OGGI - timedelta(days=30)).isoformat(), "stato": "COMPLETATA"})
    lettura = costruisci_lettura(dati)
    primo = lettura["prossimi_passi"][0]
    assert primo["urgenza"] == 0
    assert primo["azione"] == "Chiudere o riallineare la scadenza «Deposito comparsa di risposta»"
    assert all("Scadenza chiusa" not in passo["azione"] for passo in lettura["prossimi_passi"])


def test_fascicolo_chiuso_non_propone_adempimenti_di_fase():
    dati = _caso_completo()
    dati.fascicolo["stato"] = "DEFINITO"
    dati.scadenze = []
    lettura = costruisci_lettura(dati)
    assert lettura["fase"]["codice"] == "chiusa"
    assert "pratica definito" in lettura["fase"]["descrizione"]
    assert not any("impugnazione" in passo["azione"].lower() for passo in lettura["prossimi_passi"])


def test_atto_notificato_senza_deposito_richiama_il_termine_di_costituzione():
    dati = _caso_completo()
    dati.fascicolo.update({"numero_rg": "", "anno_rg": ""})
    dati.depositi = []
    dati.attivita = [voce for voce in dati.attivita if voce["tipo"] == "NOTIFICA"]
    dati.documenti = dati.documenti[:2]
    dati.catalogo = dati.catalogo[:2]
    dati.scadenze = []
    lettura = costruisci_lettura(dati)
    assert lettura["fase"]["codice"] == "atto_notificato"
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["azione"].startswith("Iscrivere la causa a ruolo"))
    assert passo["norma"] == "art. 165 c.p.c.; art. 196-sexies disp. att. c.p.c."
    assert "dieci giorni" in passo["motivo"]
    assert "numero di ruolo non registrato nel fascicolo" in lettura["lacune"]


def test_documenti_letti_dal_catalogo_e_non_dal_nome_del_file():
    lettura = costruisci_lettura(_caso_completo())
    documenti = lettura["documenti"]
    assert documenti["totale"] == 4
    assert documenti["catalogati"] == 3 and documenti["confermati"] == 2
    assert documenti["conteggi"] == {"atti": 1, "provvedimenti": 1, "procure": 1, "da-verificare": 1}
    assert documenti["atto_introduttivo"]["nome"] == "citazione.pdf"
    assert documenti["procura"]["etichetta"] == "Procura alle liti"
    assert documenti["ultimo_provvedimento"]["etichetta"] == "Verbale di udienza"
    assert [voce["nome"] for voce in documenti["da_verificare"]] == ["screenshot.png"]
    assert [voce["nome"] for voce in documenti["non_indicizzati"]] == ["screenshot.png"]


def test_cronologia_in_ordine_di_tempo_con_la_fonte_di_ogni_fatto():
    lettura = costruisci_lettura(_caso_completo())
    eventi = lettura["cronologia"]
    date_iso = [evento["data"] for evento in eventi if evento["data"]]
    assert date_iso == sorted(date_iso)
    categorie = {evento["categoria"] for evento in eventi}
    assert {"deposito", "notifica", "udienza"} <= categorie
    assert all(evento["fonte"] for evento in eventi)
    udienza = next(evento for evento in eventi if evento["categoria"] == "udienza")
    assert udienza["data_it"] == "15/06/2026"


def test_petitum_si_ferma_al_punto_e_rispetta_la_lunghezza_massima():
    assert petitum("") == ""
    assert petitum("Premesso che il contratto è stato stipulato il 3 marzo 2025. Tanto premesso.") == ""
    lungo = "Voglia il Tribunale " + "accogliere la domanda " * 40 + ". Fine."
    estratto = petitum(lungo)
    assert len(estratto) <= LUNGHEZZA_MASSIMA_PETITUM + 1
    assert estratto.endswith("…")


def test_componi_seleziona_solo_le_sezioni_richieste_nell_ordine_canonico():
    lettura = costruisci_lettura(_caso_completo())
    testo = componi(lettura, ("prossimi_passi", "quadro"))
    assert testo.index("Quadro della pratica") < testo.index("Prossimi passaggi")
    assert "Di che cosa tratta" not in testo
    assert componi(lettura, ORDINE_SEZIONI) == lettura["narrativa"]


def test_date_miste_aware_e_naive_non_rompono_la_lettura():
    dati = _caso_completo()
    dati.attivita.append({"id": "AT3", "tipo": "PROVVEDIMENTO", "data": "2026-07-01T10:00:00+02:00", "titolo": "Ordinanza ammissione prove", "esito": "NON_APPLICABILE"})
    dati.scadenze.append({"id": "SC3", "titolo": "Termine naive", "data": "2026-09-20T09:00:00", "stato": "APERTO"})
    dati.scadenze.append({"id": "SC4", "titolo": "Termine illeggibile", "data": "domani", "stato": "APERTO"})
    lettura = costruisci_lettura(dati)
    assert any(evento["titolo"] == "Ordinanza ammissione prove" and evento["data_it"] == "01/07/2026" for evento in lettura["cronologia"])
    assert any("Termine naive" in passo["azione"] for passo in lettura["prossimi_passi"])
    assert not any("illeggibile" in passo["azione"] for passo in lettura["prossimi_passi"])


def _pec_messaggio(**extra) -> dict:
    base = {
        "id": "M1", "received_at": "2026-09-10T11:20:00", "subject": "Comunicazione di cancelleria RG 1234/2026 - fissazione udienza",
        "from": "tribunale.milano@civile.ptel.giustiziacert.it", "status": "parsed", "quality_status": "verde", "signature_status": "valida",
        "collegata": True, "corrispondenza": "collegamento", "eventi": [], "termini": [], "udienze": [],
    }
    base.update(extra)
    return base


def test_presidio_pec_entra_nella_lettura_con_termini_e_udienze_da_registrare():
    dati = _caso_completo()
    dati.pec = [
        _pec_messaggio(),
        _pec_messaggio(id="M2", received_at="2026-09-12T09:00:00", subject="Avviso n. 1234/26", collegata=False, corrispondenza="rg", quality_status="giallo",
                       termini=[{"id": "T1", "deadline_type": "memoria_171_ter", "norm_ref": "art. 171-ter c.p.c.", "dies_a_quo_date": "2026-09-12", "deterministic_status": "computed", "scadenziario_id": "", "peremptory": 1, "human_review_required": 1},
                                {"id": "T2", "deadline_type": "comparsa_conclusionale", "norm_ref": "art. 189 c.p.c.", "dies_a_quo_date": "2026-09-12", "deterministic_status": "computed", "scadenziario_id": "", "peremptory": 1, "human_review_required": 0}],
                       udienze=[{"id": "U1", "hearing_date": "2026-11-05", "hearing_time": "09:30", "mode": "presenza", "agenda_id": "", "human_review_required": 0}]),
        _pec_messaggio(id="M3", received_at="2026-09-13T08:00:00", subject="Per Mario Rossi", collegata=False, corrispondenza="cliente", eventi=[{"primary_event": "comunicazione_generica", "family": "cancelleria", "priority": "media", "human_review_required": 1}]),
    ]
    lettura = costruisci_lettura(dati)
    pec = lettura["pec"]
    assert pec["totale"] == 3 and pec["collegate"] == 1
    assert pec["per_corrispondenza"] == {"collegamento": 1, "rg": 1, "cliente": 1}
    assert [voce["id"] for voce in pec["da_controllare"]] == ["M2", "M3"]
    assert pec["da_controllare"][1]["motivi_controllo"] == ["evento da confermare", "non collegata al fascicolo"]
    assert len(pec["termini_da_registrare"]) == 2 and pec["termini_da_registrare"][0]["norma"] == "art. 171-ter c.p.c."
    assert len(pec["udienze_da_registrare"]) == 1
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    # Il termine che il presidio vuole far rivedere è un passo; quello certo lo registra da solo.
    assert any(azione.startswith("Confermare il termine «memoria 171 ter» (art. 171-ter c.p.c.) che il presidio PEC propone dalla PEC del 12/09/2026") for azione in azioni)
    assert not any("comparsa conclusionale" in azione for azione in azioni)
    assert not any("udienza del 05/11/2026" in azione for azione in azioni)
    # La PEC che cita l'assistito: il presidio non collega omonimi, chiede conferma; l'evento incerto va confermato.
    assert any(azione.startswith("Confermare l'evento che il presidio PEC propone per la PEC del 13/09/2026") for azione in azioni)
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["azione"].startswith("Confermare l'evento"))
    assert passo["href"] == "#comunicazioni-notifica" and passo["norma"] == "Specifiche tecniche DGSIA 7/8/2024, art. 21"
    # La PEC per numero di ruolo non collegata (giallo) chiede la verifica di autenticità.
    assert any(azione.startswith("Verificare l'autenticità della PEC del 12/09/2026") for azione in azioni)
    assert "PEC del presidio che riguardano la pratica: 3 (1 collegate, 1 per numero di ruolo, 1 per nome dell'assistito)" in lettura["narrativa"]
    assert "2 PEC del presidio riguardano la pratica ma sono ancora da controllare" in lettura["lacune"]


def test_fascicolo_definito_o_da_archiviare_non_ha_passaggi():
    dati = _caso_completo()
    dati.fascicolo["stato"] = "DEFINITO"
    lettura = costruisci_lettura(dati)
    assert lettura["prossimi_passi"] == []
    assert lettura["stato_passi"] == {"attivi": False, "motivo": "Fascicolo definito: nessun passaggio da eseguire."}
    assert "- Fascicolo definito: nessun passaggio da eseguire." in lettura["narrativa"]

    dati.fascicolo["archivio_pronto"] = True
    lettura = costruisci_lettura(dati)
    assert lettura["intestazione"]["da_archiviare"] is True
    assert "pronto per l'archivio" in lettura["stato_passi"]["motivo"]

    dati.fascicolo["stato"] = "SOSPESO"
    dati.fascicolo["archivio_pronto"] = False
    lettura = costruisci_lettura(dati)
    assert lettura["stato_passi"]["attivi"] is True and "sospeso" in lettura["stato_passi"]["motivo"]
    assert lettura["prossimi_passi"]


def test_presidio_economico_con_importi_e_parcelle_scadute():
    dati = _caso_completo()
    dati.economico = {
        "summary": {"preventivi_count": 1, "conferimenti_count": 1, "parcelle_count": 3, "totale_preventivato": 3000.0, "totale_conferito": 2800.0, "totale_fatturato": 2500.0, "totale_incassato": 1000.0, "saldo_aperto": 1500.0},
        "parcelle": [
            {"id": "P1", "numero": "2026/001", "stato": "PAGATA", "totale": 1000.0, "data_emissione": "2026-03-01", "data_scadenza": "2026-03-31"},
            {"id": "P2", "numero": "2026/002", "stato": "SCADUTA", "totale": 900.0, "data_emissione": "2026-05-01", "data_scadenza": "2026-05-31"},
            {"id": "P3", "numero": "2026/003", "stato": "EMESSA", "totale": 600.0, "data_emissione": "2026-08-01", "data_scadenza": "2026-08-31"},
        ],
    }
    lettura = costruisci_lettura(dati)
    economico = lettura["economico"]
    assert economico["saldo_aperto_it"] == "€ 1.500,00" and economico["conferito_it"] == "€ 2.800,00"
    assert [voce["numero"] for voce in economico["parcelle_scadute"]] == ["2026/002", "2026/003"]
    assert economico["importo_scaduto_it"] == "€ 1.500,00"
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["azione"].startswith("Sollecitare"))
    assert passo["azione"] == "Sollecitare l'incasso di € 1.500,00 di parcelle scadute"
    assert passo["urgenza"] == 1 and passo["fonte"] == "presidio economico"
    assert "Parcelle scadute: 2 per € 1.500,00 (2026/002 e 2026/003)" in lettura["narrativa"]

    dati.economico = {"summary": {"preventivi_count": 0, "conferimenti_count": 0, "parcelle_count": 0, "totale_fatturato": 0, "totale_incassato": 0}, "parcelle": []}
    lettura = costruisci_lettura(dati)
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["azione"].startswith("Formalizzare preventivo"))
    assert passo["norma"] == "L. 247/2012, art. 13"
    assert "Preventivo e conferimento d'incarico non risultano collegati" in lettura["narrativa"]


def test_deposito_e_notifica_portano_la_fase_procedurale_e_le_norme():
    dati = _caso_completo()
    dati.depositi = [_deposito("CONSEGNATO")]
    dati.notifiche = [_presidio("SENT_WAITING_RAC", "In attesa RAC")]
    lettura = costruisci_lettura(dati)
    deposito = lettura["depositi"]["in_corso"][0]
    assert deposito["canale"] == "PCT_TELEMATICO"
    assert deposito["fase_procedurale"].startswith("Ricevuta di avvenuta consegna")
    assert "dispatt_196sexies" in deposito["fonti_procedurali"]
    notifica = lettura["notifiche"]["aperte"][0]
    assert notifica["fase_procedurale"] == "Ricevuta di accettazione: perfezionata per il notificante"
    assert notifica["fonti_procedurali"] == ["cpc_147"]
    assert not any(passo["fonte"] == "presidio notifiche" for passo in lettura["prossimi_passi"])
    dati.notifiche = [_presidio("RECIPIENTS_TO_VERIFY", "Destinatari da verificare")]
    dati.notifiche[0]["next_action"] = "Verifica destinatari e pubblici elenchi"
    lettura = costruisci_lettura(dati)
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["fonte"] == "presidio notifiche")
    assert passo["azione"] == "Verifica destinatari e pubblici elenchi («Atto di citazione»)"
    assert passo["norma"] == "L. 53/1994, art. 3-bis; D.L. 179/2012, art. 16-ter"
    assert lettura["conoscenza"]["deposito"]["canale"] == "PCT_TELEMATICO"
    assert lettura["conoscenza"]["rito"]["codice"] == "ordinario"
    assert [voce["canale"] for voce in lettura["conoscenza"]["notifiche"]] == ["pec"]


def test_scadenza_che_nomina_la_norma_porta_norma_e_template():
    lettura = costruisci_lettura(_caso_completo())
    passo = lettura["prossimi_passi"][0]
    assert passo["azione"].startswith("Adempiere a «Memoria istruttoria n. 1 (art. 171-ter c.p.c.)»")
    assert passo["norma"] == "art. 171-ter c.p.c." and passo["template"] == "CIV_MEMORIA_171_TER_1" and passo["href"] == "#udienze"


def test_atti_importati_dal_portale_non_sono_depositi_in_corso():
    dati = _caso_completo()
    dati.depositi = [
        {"id": f"I{n}", "timestamp": f"2026-01-0{n}T00:00:00", "stato": "IMPORTATO_DA_PST", "tipo_atto": "Documento", "nome_atto_principale": f"Decreto_{n}.pdf", "fonte_portale": "PolisWeb / PST", "messaggio": "Metadati importati da PolisWeb / PST"}
        for n in range(1, 6)
    ]
    dati.attivita.append({"id": "AT9", "tipo": "CONSULTAZIONE", "data": "2026-04-04", "titolo": "Acquisizione file ufficiali — Decreto", "esito": "NON_APPLICABILE"})
    lettura = costruisci_lettura(dati)
    assert len(lettura["depositi"]["importati"]) == 5
    assert lettura["depositi"]["in_corso"] == [] and lettura["depositi"]["perfezionati"] == []
    assert not any("Verificare le ricevute" in passo["azione"] for passo in lettura["prossimi_passi"])
    assert not any("accettazione della cancelleria" in voce for voce in lettura["lacune"])
    assert not any("Acquisizione file ufficiali" in evento["titolo"] for evento in lettura["cronologia"])
    assert not any(evento["categoria"] == "deposito" for evento in lettura["cronologia"])
    assert "5 atti acquisiti dal fascicolo d'ufficio" in lettura["narrativa"]


def test_molti_depositi_fermi_dopo_il_controllo_diventano_un_solo_passo():
    dati = _caso_completo()
    dati.depositi = [_deposito("CONSEGNATO", atto=f"Atto {n}", timestamp=f"2026-08-0{n}T10:00:00") for n in range(1, 6)]
    dati.verifiche = {"eseguita_il": "2026-09-14T10:00:00+02:00", "eseguita_il_it": "14/09/2026 ore 10:00", "esiti": {"depositi": {"pendenti": 5, "esito": "controllate", "controllati": 5, "aggiornati": 0, "errori": 0}}}
    lettura = costruisci_lettura(dati)
    passi = [passo for passo in lettura["prossimi_passi"] if passo["fonte"] == "presidio depositi"]
    assert len(passi) == 1
    assert passi[0]["azione"] == "5 depositi senza esito della cancelleria dopo il controllo automatico delle ricevute"
    assert "«Atto 5»" in passi[0]["motivo"]
    assert "5 depositi non hanno ancora l'accettazione della cancelleria" in lettura["lacune"]


def test_documenti_letti_ma_non_riconosciuti_e_procura_assente_sono_decisioni_dell_avvocato():
    dati = _caso_completo()
    dati.documenti = [voce for voce in dati.documenti if voce["id"] != "P1"]  # senza procura
    dati.catalogo = [voce for voce in dati.catalogo if voce["document_id"] != "P1"]
    lettura = costruisci_lettura(dati)
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    # Un documento non ancora letto: la procura potrebbe essere lì, il presidio deve prima leggerlo.
    assert not any(azione.startswith("Acquisire la procura") for azione in azioni)
    dati.documenti[-1]["lex_read"] = True
    dati.documenti[-1]["lex_text_excerpt"] = "testo letto"
    lettura = costruisci_lettura(dati)
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert "Acquisire la procura alle liti" in azioni
    assert "Classificare 1 documento che il contenuto non identifica" in azioni
    dati.verifiche = {"eseguita_il": "2026-09-14T10:00:00+02:00", "esiti": {"documenti": {"documenti": 3, "indicizzati": 2, "errori": 2, "esito": "indicizzazione_eseguita"}}}
    lettura = costruisci_lettura(dati)
    assert "Fornire una copia leggibile di 2 documenti" in [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert "2 indicizzati ora, 2 non leggibili" in lettura["narrativa"]


def test_lacune_di_conoscenza_sono_dichiarate_nella_lettura():
    dati = _caso_completo()
    dati.fascicolo["tipo"] = "ALTRO"
    dati.fascicolo["tipo_procedimento"] = "Arbitrato rituale"
    dati.scadenze.append({"id": "SC8", "titolo": "Termine ex art. 702-bis c.p.c.", "data": (OGGI + timedelta(days=40)).isoformat(), "stato": "APERTO"})
    lettura = costruisci_lettura(dati)
    lacune = lettura["conoscenza"]["lacune"]
    assert [voce["tipo"] for voce in lacune] == ["rito", "norma"]
    assert lacune[0]["chiave"] == "Arbitrato rituale" and lacune[1]["chiave"] == "art. 702-bis c.p.c."
    assert lettura["conoscenza"]["rito"] == {}
    assert "Conoscenza da completare: Il rito «Arbitrato rituale» non ha ancora una scheda" in lettura["narrativa"]


def test_documenti_censiti_dal_portale_non_scaricati_vanno_acquisiti_non_verificati():
    dati = _caso_completo()
    for documento in dati.documenti:
        documento["lex_read"] = False
        documento["da_acquisire"] = True
    dati.catalogo = []
    lettura = costruisci_lettura(dati)
    assert len(lettura["documenti"]["da_acquisire"]) == 4 and lettura["documenti"]["non_indicizzati"] == []
    passo = next(passo for passo in lettura["prossimi_passi"] if passo["fonte"] == "presidio documentale")
    assert passo["azione"] == "Acquisire dal portale 4 documenti censiti ma non scaricati"
    assert "sessione autenticata sul portale" in passo["motivo"] and passo["href"] == "#documenti"
    assert not any(passo["azione"].startswith("Acquisire la procura") for passo in lettura["prossimi_passi"])
    assert "4 documenti censiti dal portale ma non scaricati" in " ".join(lettura["lacune"])


def test_documento_indicizzato_dal_catalogo_conta_come_letto_anche_senza_estratto():
    dati = _caso_completo()
    dati.documenti[0]["lex_read"] = False
    dati.documenti[0]["lex_text_excerpt"] = ""
    dati.catalogo[0]["indexed"] = True
    lettura = costruisci_lettura(dati)
    assert lettura["documenti"]["tutti"][0]["indicizzato"] is True


def test_liquidazione_del_giudice_e_bonifici_entrano_nel_presidio_economico():
    dati = _caso_completo()
    dati.economico = {
        "summary": {"preventivi_count": 1, "conferimenti_count": 1, "parcelle_count": 1, "totale_preventivato": 3000.0, "totale_conferito": 3000.0, "totale_fatturato": 2000.0, "totale_incassato": 0.0, "saldo_aperto": 2000.0},
        "parcelle": [{"id": "P1", "numero": "2026/001", "stato": "EMESSA", "totale": 2000.0, "data_emissione": "2026-09-05", "data_scadenza": "2026-10-05", "metodo_pagamento": ""}],
        "presidio": {
            "stato": "da_presidiare", "statoLabel": "Da presidiare", "anticipazioniDaRecuperare": 259.0,
            "items": {
                "liquidazione_giudice": {"status": "da_registrare", "statusLabel": "Da registrare", "importo": 4500.0, "dataPagamentoIso": "2026-09-01", "documentoFonte": "SentenzaDefinitiva.pdf", "pagato": False, "previsto": True, "note": "Importo liquidato letto automaticamente dalla sentenza del fascicolo."},
                "contributo_unificato": {"status": "pagato", "statusLabel": "Pagato", "importo": 259.0, "pagato": True, "previsto": True},
            },
        },
        "sentenze": {"totals": {"sentenze_lette": 1}},
    }
    lettura = costruisci_lettura(dati)
    economico = lettura["economico"]
    assert economico["liquidato_it"] == "€ 4.500,00" and economico["liquidazione_incasso"] == "non_incassata"
    assert economico["liquidazione"]["fonte"] == "SentenzaDefinitiva.pdf" and economico["sentenze_lette"] == 1
    azioni = [passo["azione"] for passo in lettura["prossimi_passi"]]
    assert "Confermare nel presidio economico la liquidazione di € 4.500,00 letta dalla sentenza del 01/09/2026" in azioni
    riscossione = next(passo for passo in lettura["prossimi_passi"] if passo["azione"].startswith("Riscuotere la somma liquidata"))
    assert riscossione["urgenza"] == 1 and riscossione["href"] == "/fatturazione" and "incassato finora € 0,00" in riscossione["motivo"]
    assert "Recuperare le anticipazioni (€ 259,00)" in azioni
    assert "Liquidazione del giudice: € 4.500,00 (sentenza del 01/09/2026), da registrare nel presidio; non ancora bonificata sul conto dello studio." in lettura["narrativa"]

    # Il bonifico registrato in Fatturazione chiude la riscossione: stessa fonte, stessa lettura.
    dati.economico["summary"].update({"totale_incassato": 4500.0, "saldo_aperto": 0.0, "totale_fatturato": 4500.0})
    dati.economico["parcelle"] = [{"id": "P1", "numero": "2026/001", "stato": "PAGATA", "totale": 4500.0, "data_emissione": "2026-09-05", "data_scadenza": "2026-10-05", "data_pagamento": "2026-09-10", "metodo_pagamento": "Bonifico bancario"}]
    dati.economico["presidio"]["items"]["liquidazione_giudice"].update({"status": "pagato", "statusLabel": "Pagato", "pagato": True})
    lettura = costruisci_lettura(dati)
    economico = lettura["economico"]
    assert economico["liquidazione_incasso"] == "incassata" and economico["incassato_bonifico_it"] == "€ 4.500,00"
    assert [voce["pagata_il"] for voce in economico["bonifici"]] == ["10/09/2026"]
    assert not any(passo["azione"].startswith(("Riscuotere", "Confermare nel presidio economico")) for passo in lettura["prossimi_passi"])
    assert "Bonifici ricevuti: 1 per € 4.500,00 (2026/001 il 10/09/2026)" in lettura["narrativa"]
    assert "bonificata sul conto dello studio" in lettura["narrativa"]
