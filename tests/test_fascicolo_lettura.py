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
    assert any(azione.startswith("Confermare la catalogazione di 1 documento") for azione in azioni)
    assert "Sollecitare l'incasso delle parcelle emesse" in azioni
    assert len(lettura["prossimi_passi"]) <= 8

    assert lettura["lacune"] == ["1 documento senza testo indicizzato: la lettura non può citarne il contenuto"]

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
    assert "artt. 325 e 327 c.p.c." in passo["motivo"]
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


def test_deposito_in_corso_resta_non_perfezionato_e_va_verificato():
    dati = _caso_completo()
    dati.depositi = [_deposito("CONSEGNATO")]
    lettura = costruisci_lettura(dati)
    assert lettura["depositi"]["in_corso"][0]["attesa"] == "in attesa dell'esito dei controlli automatici"
    assert any(passo["azione"].startswith("Verificare le ricevute del deposito") for passo in lettura["prossimi_passi"])
    assert "non ha ancora l'accettazione della cancelleria" in " ".join(lettura["lacune"])


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
    assert any(azione.startswith("Acquisire la ricevuta di avvenuta consegna") and "«Comparsa»" in azione for azione in azioni)
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
    assert "art. 165 c.p.c." in passo["motivo"]
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
