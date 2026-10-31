from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
import os
import uuid

import pytest

from pct.fascicoli import Fascicolo, GestioneFascicoli, StatoFascicolo, TipoFascicolo
from pct.fascicolo_sentenza_economica import (
    AUTOMATION_KEY,
    ORIGIN,
    SENTENZA_VECTOR_SCHEMA_VERSION,
    analyze_sentenza_tribunale_text,
    apply_contributo_unificato_pdf_evidence,
    apply_sentenza_tribunale_automation,
    extract_contributo_unificato_document_evidence,
)
from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella
from web.services.react_fascicoli_bridge import payment_summary_for_fascicolo, update_react_fascicolo_payment


@pytest.mark.parametrize("kind", ["fondo_spese", "spese_esborsi", "contributo_unificato", "liquidazione_giudice"])
def test_impronta_discordanza_seleziona_solo_campi_pertinenti_senza_cambiare_prove(monkeypatch, kind):
    import hashlib
    import json
    from pct.archivio_letture import fatti_canonici
    from pct.registro_letture import Fatto
    from web.services import react_fascicoli_bridge as bridge

    facts = [
        Fatto(id=f"proof-{index}", fascicolo_id="F1", categoria=category,
              campo=field, valore=value, verifica=verification,
              tipo="documento", oggetto_id=f"source-{index}", sha256=f"sha-{index}")
        for index, (category, field, value, verification) in enumerate([
            ("importo", kind, "250.00", "verificata"),
            ("importo", kind, "300.00", "corretta"),
            ("evento", "fondo_spese_da_verificare", "discordanza", "plausibile"),
            ("evento", kind, "riscontro", "verificata"),
            ("data", "udienza", "2026-10-16", "verificata"),
        ])
    ]
    calls = []

    def read(_fascicolo, **filters):
        calls.append(filters)
        assert filters.get("campo"), "L'elenco non deve rileggere tutti i fatti per una voce."
        return fatti_canonici([f for f in facts if f.campo == filters["campo"]])

    monkeypatch.setattr(bridge, "_fatti_archivio", read)
    relevant = [
        (f.campo, f.id, f.oggetto_id, f.sha256, f.valore)
        for f in fatti_canonici(facts)
        if f.campo == kind or (kind == "fondo_spese" and f.campo == "fondo_spese_da_verificare")
    ]
    relevant.sort(key=lambda row: json.dumps(row, sort_keys=True, default=str))
    expected = hashlib.sha256(json.dumps(relevant, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    actual = bridge._economic_discordance_signature(SimpleNamespace(id="F1", pagamenti={}), kind)
    assert actual == expected
    assert len(calls) == (2 if kind == "fondo_spese" else 1)


@pytest.mark.parametrize("provenienza", ["documento", "allegato_pec"])
@pytest.mark.parametrize("discordanza", ["", "cliente", "numero_rg", "anno_rg", "ufficio", "anno_assente"])
def test_sentenza_documento_o_pec_richiede_identita_congiunta(provenienza, discordanza):
    from pct.archivio_letture.collaudo import contesto_da_fascicolo
    from pct.archivio_letture.motore_documenti import leggi_testo
    from pct.archivio_letture.motore_pec import fatti_da_allegato

    fascicolo = SimpleNamespace(id="IDENTITA-SINTETICA", nome_cliente="Spagnolo Sara",
                               numero_rg="1548", anno_rg=2023, tribunale="Tribunale di Palmi")
    testo = SENTENZA_TEXT
    sostituzioni = {
        "cliente": ("Spagnolo Sara", "Bianchi Anna"),
        "numero_rg": ("1548/2023", "1549/2023"),
        "anno_rg": ("1548/2023", "1548/2022"),
        "ufficio": ("Tribunale di Palmi", "Tribunale di Torino"),
        "anno_assente": ("1548/2023", "1548"),
    }
    if discordanza:
        testo = testo.replace(*sostituzioni[discordanza])
    metadata = {"fascicolo": fascicolo, "documento_id": "SENTENZA-SINTETICA", "tipo_documento": "SENTENZA"}
    contesto = contesto_da_fascicolo(vars(fascicolo))
    if provenienza == "documento":
        fatti = leggi_testo(testo, origine="nativo", contesto=contesto, nome="sentenza.pdf", metadata=metadata)
    else:
        fatti = fatti_da_allegato(testo, nome="sentenza.pdf", contesto=contesto, metadata=metadata)
    importi = [f for f in fatti if f.categoria == "importo" and f.campo == "liquidazione_giudice"]
    if discordanza:
        assert importi == []
    else:
        assert [f.valore for f in importi] == ["1100.00"]


@pytest.mark.parametrize("altra_sentenza", [False, True])
def test_stessa_sentenza_documento_pec_unica_voce_con_due_prove(altra_sentenza):
    from dataclasses import replace
    from pct.archivio_letture import fatti_canonici
    from pct.archivio_letture.collaudo import contesto_da_fascicolo
    from pct.archivio_letture.motore_documenti import leggi_testo
    from pct.archivio_letture.motore_pec import fatti_da_allegato
    from pct.archivio_letture.presidi import importi_letti

    fascicolo = SimpleNamespace(id="F-DOPPIA-FONTE", nome_cliente="Spagnolo Sara",
                               numero_rg="1548", anno_rg=2023, tribunale="Tribunale di Palmi")
    context = contesto_da_fascicolo(vars(fascicolo))
    metadata = {"fascicolo": fascicolo, "tipo_documento": "SENTENZA"}
    documenti = leggi_testo(SENTENZA_TEXT, origine="nativo", contesto=context,
                           nome="originale.pdf", metadata=metadata)
    testo_pec = SENTENZA_TEXT.replace("230/2024", "231/2024") if altra_sentenza else SENTENZA_TEXT
    allegati = fatti_da_allegato(testo_pec, nome="copia.pdf", contesto=context, metadata=metadata)
    raw = [replace(f, id=f"doc-{i}", fascicolo_id=fascicolo.id, tipo="documento", oggetto_id="DOC", sha256="a" * 64, motore="documenti")
           for i, f in enumerate(documenti) if f.categoria == "importo"]
    raw += [replace(f, id=f"pec-{i}", fascicolo_id=fascicolo.id, tipo="allegato_pec", oggetto_id="PEC-ALLEGATO", sha256="b" * 64, motore="pec")
            for i, f in enumerate(allegati) if f.categoria == "importo"]
    prima = deepcopy(raw)
    canonical = fatti_canonici(raw)
    liquidazioni = [f for f in canonical if f.campo == "liquidazione_giudice"]
    assert len(liquidazioni) == (2 if altra_sentenza else 1)
    voce = importi_letti(canonical)["liquidazione_giudice"]
    if altra_sentenza:
        assert voce["importo"] is None and voce["richiede_conferma"]
        assert len(voce["discordanze"]) == 2
        assert len({f.id for f in liquidazioni}) == 2
    else:
        assert voce["importo"] == 1100.00
        prove = next(p["fonti"] for p in liquidazioni[0].prove if p.get("codice") == "fonti_unite")
        assert {p["tipo"] for p in prove} == {"documento", "allegato_pec"}
        assert len(prove) == 2
    assert raw == prima


SENTENZA_TEXT = """
Tribunale di Palmi
Sentenza n. 230/2024 pubbl. il 07/05/2024
RG n. 1548/2023
nel procedimento promosso da Spagnolo Sara contro Ministero dell'Istruzione e del Merito
condanna il Ministero alla rifusione delle spese di lite sostenute dai ricorrenti
liquidando la complessiva somma di € 1.100,00, oltre ad € 98,00 per spese
(sommatoria di tutti i c.u. versati dai ricorrenti), con maggiorazione di spese
generali ed accessori di legge (iva e cpa) e con distrazione della somma in favore
del difensore dichiaratosi antistatario.
"""

MONTAGNESE_TEXT = """
N. R.G 697/2025
REPUBBLICA ITALIANA
IN NOME DEL POPOLO ITALIANO
TRIBUNALE ORDINARIO di VICENZA
Il Tribunale, nella persona del Giudice dott. Caterina Neri ha pronunciato la seguente
SENTENZA
nella causa di lavoro di I Grado iscritta al n. r.g. 697/2025 promossa da:
ROBERTA MONTAGNESE (C.F. MNTRRT98P65G791Q), con il patrocinio dell'avv.
MONTAGNESE GIUSEPPE
P.Q.M.
Il Giudice del Lavoro, definitivamente pronunciando:
- condanna il Ministero a costituire in favore di parte ricorrente la Carta elettronica
con accredito/assegnazione della somma pari a complessivi euro 500,00;
- condanna parte resistente alla rifusione delle spese di lite sostenute dalla parte ricorrente
a tale titolo liquidando la complessiva somma di € 321,50, di cui € 21,50 per esborsi,
oltre a spese generali ed accessori di legge (iva e cpa), con distrazione in favore
del difensore antistatario.
Sentenza resa ex art. 127 ter c.p.c.
Vicenza, 23 settembre 2025
Sentenza n. 465/2025 pubbl. il 23/09/2025
RG n. 697/2025
"""


class FakeFascicoliRepository:
    def __init__(self):
        self.fascicolo = SimpleNamespace(
            id="FASC-1",
            id_cliente="CLI-1",
            titolo="Spagnolo Sara c. MIM",
            nome_cliente="Spagnolo Sara",
            tribunale="Tribunale di Palmi",
            numero_rg="1548/2023",
            anno_rg=2023,
            tipo_procedimento="Lavoro",
            valore_causa=0,
            stato=StatoFascicolo.IN_CORSO,
            data_prossima_udienza="n.d.",
            data_chiusura="",
            pagamenti={},
            avanzamento=[],
        )

    def get(self, fascicolo_id: str):
        return self.fascicolo if fascicolo_id == self.fascicolo.id else None

    def aggiorna(self, fascicolo_id: str, **fields):
        if fascicolo_id != self.fascicolo.id:
            raise KeyError(fascicolo_id)
        for key, value in fields.items():
            setattr(self.fascicolo, key, value)
        return self.fascicolo


def test_estrazione_sentenza_tribunale_con_cu_liquidazione_e_fondo_spese():
    metadata = {
        "tipo_documento": "provvedimento Sentenza Tribunale",
        "contributo_unificato_pdf": {
            "importo": 98.00,
            "filename": "CU.pdf",
            "natura": "pdf_contributo_unificato",
            "label": "Contributo unificato da PDF",
        },
    }
    extraction = analyze_sentenza_tribunale_text(
        SENTENZA_TEXT + "\nFondo spese riconosciuto pari a € 250,00.",
        metadata,
    )
    apply_contributo_unificato_pdf_evidence(extraction, metadata)

    assert extraction.found is True
    assert extraction.sentence_date == "2024-05-07"
    assert extraction.sentence_number == "230"
    assert extraction.rg_number == "1548"
    assert extraction.liquidazione_importo == 1100.00
    assert extraction.contributo_unificato_importo == 98.00
    assert extraction.spese_esborsi_importo is None
    assert extraction.fondo_spese_importo == 250.00
    assert "Fondo spese" in extraction.fondo_spese_titolo
    assert extraction.spese_generali is True
    assert extraction.antistatario is True


@pytest.mark.parametrize("esborsi,fondo", [(21.50, 250.00), (21.50, 21.50)])
def test_fondo_ed_esborsi_conservano_natura_e_importi(esborsi, fondo):
    text = MONTAGNESE_TEXT + f"\nFondo spese riconosciuto pari a € {fondo:.2f}."
    extraction = analyze_sentenza_tribunale_text(text, {})
    assert extraction.spese_esborsi_importo == esborsi
    assert extraction.fondo_spese_importo == fondo
    assert "esborsi" in extraction.spese_esborsi_titolo
    assert "Fondo spese" in extraction.fondo_spese_titolo
    assert not any("assorbito" in warning or "preferito" in warning for warning in extraction.warnings)


@pytest.mark.parametrize("fondo", [21.50, 250.00])
def test_fondo_distinto_applicazione_proforma_e_replay(tmp_path, fondo):
    fascicoli = FakeFascicoliRepository()
    fascicolo = fascicoli.fascicolo
    fascicolo.nome_cliente = "Roberta Montagnese"
    fascicolo.titolo = "Roberta Montagnese c. MIM"
    fascicolo.tribunale = "Tribunale di Vicenza"
    fascicolo.numero_rg = "697/2025"
    fascicolo.anno_rg = 2025
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    text = MONTAGNESE_TEXT + f"\nFondo spese riconosciuto pari a € {fondo:.2f}."
    metadata = {"document_id": "DOC-DISTINTO", "sha256": "e" * 64, "tipo_documento": "Sentenza", "codice_fiscale_cliente": "MNTRRT98P65G791Q"}
    first = apply_sentenza_tribunale_automation(
        proforma_requested=True,
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1", text=text, document_metadata=metadata)
    assert first.applied
    assert fascicolo.pagamenti["spese_esborsi"]["importo"] == 21.50
    assert fascicolo.pagamenti["fondo_spese"]["importo"] == fondo
    assert fascicolo.pagamenti["fondo_spese"]["natura"] == "fondo_spese"
    assert fascicolo.pagamenti["fondo_spese"]["source_sha256"] == "e" * 64
    proforma = fatturazione.get(first.proforma_id)
    assert not any("fondo" in voce.descrizione.lower() for voce in proforma.voci)
    anticipi = [voce.prezzo_unitario for voce in proforma.voci if voce.tipo == "ANTICIPO"]
    assert anticipi == [21.50]
    before = deepcopy(fascicolo.pagamenti)
    second = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1", text=text, document_metadata=metadata)
    assert not second.applied
    assert fascicolo.pagamenti == before
    summary = payment_summary_for_fascicolo(fascicolo)
    assert summary["items"]["spese_esborsi"]["importo"] == 21.50
    assert summary["items"]["fondo_spese"]["importo"] == fondo


@pytest.mark.parametrize("suffix,amounts", [
    ("Fondo spese € 250,00. Fondo spese € 300,00.", [250.00, 300.00]),
    ("Fondo spese da determinare. Compensi € 900,00.", []),
])
def test_fondo_non_univoco_non_prende_importi_vicini(suffix, amounts):
    extraction = analyze_sentenza_tribunale_text(MONTAGNESE_TEXT + "\n" + suffix, {})
    assert extraction.fondo_spese_importo is None
    assert extraction.spese_esborsi_importo == 21.50
    assert extraction.discordanze[0]["motivo"] == "importo_fondo_non_univoco"
    assert extraction.discordanze[0]["importi_letti"] == amounts


def test_archivio_importi_discordanti_non_sceglie_il_primo():
    from pct.archivio_letture.presidi import importi_letti
    from pct.registro_letture.fatti_repository import Fatto

    first = Fatto(categoria="importo", campo="fondo_spese", valore="250.00", verifica="verificata",
                  oggetto_id="DOC-PRIMO", sha256="a" * 64, contesto="Fondo € 250,00")
    second = Fatto(categoria="importo", campo="fondo_spese", valore="300.00", verifica="verificata",
                   oggetto_id="DOC-SECONDO", sha256="b" * 64, contesto="Fondo € 300,00")
    for facts in ([first, second], [second, first]):
        result = importi_letti(facts)["fondo_spese"]
        assert result["importo"] is None
        assert result["richiede_conferma"]
        assert result["importi_letti"] == [250.00, 300.00]
        assert {row["sha256"] for row in result["discordanze"]} == {"a" * 64, "b" * 64}
    first.verifica = "corretta"
    corrected = importi_letti([second, first])["fondo_spese"]
    assert corrected["importo"] == 250.00
    assert corrected["verifica"] == "corretta"
    assert corrected["richiede_conferma"]


def test_archivio_importi_uguali_di_natura_diversa_restano_distinti():
    from pct.archivio_letture.presidi import importi_letti
    from pct.registro_letture.fatti_repository import Fatto

    facts = [Fatto(categoria="importo", campo=kind, valore="250.00", verifica="verificata")
             for kind in ("fondo_spese", "spese_esborsi")]
    results = importi_letti(facts)
    assert results["fondo_spese"]["importo"] == 250.00
    assert results["spese_esborsi"]["importo"] == 250.00
    assert not any(row.get("richiede_conferma") for row in results.values())


def test_archivio_fondo_non_univoco_conserva_evento_verifica():
    from pct.archivio_letture.estrazione_importi import importi_dalla_sentenza

    fascicolo = SimpleNamespace(id="F1", nome_cliente="Roberta Montagnese", numero_rg="697/2025",
                               anno_rg=2025, tribunale="Tribunale di Vicenza")
    facts = importi_dalla_sentenza(MONTAGNESE_TEXT + "\nFondo spese € 250,00. Fondo spese € 300,00.",
                                 metadata={"fascicolo": fascicolo, "codice_fiscale_cliente": "MNTRRT98P65G791Q"}, origine="nativo")
    assert not any(f.categoria == "importo" and f.campo == "fondo_spese" for f in facts)
    pending = next(f for f in facts if f.campo == "fondo_spese_da_verificare")
    assert pending.verifica == "plausibile"
    assert "250" in pending.contesto and "300" in pending.contesto


def test_decisione_importo_esplicita_conserva_audit_e_rifiuta_fonti_cambiate():
    fascicoli = FakeFascicoliRepository()
    fascicolo = fascicoli.fascicolo
    discrepancy = {"kind": "fondo_spese", "importo_registrato": 250.00, "importo_letto": 300.00,
                   "documento_fonte": "document_id:DOC-FONDO", "sha256": "a" * 64, "stato": "da_verificare"}
    fascicolo.pagamenti = {"fondo_spese": {"status": "pagato", "importo": 250.00,
                           "data_pagamento": "2026-06-26", "metodo": "Bonifico", "origine": "manuale"},
                          AUTOMATION_KEY: {"discordanze": [discrepancy]}}
    summary = payment_summary_for_fascicolo(fascicolo)
    signature = summary["items"]["fondo_spese"]["discordanzaVersione"]
    assert summary["items"]["fondo_spese"]["richiedeConferma"]
    payload = {"status": "pagato", "importo": 250.00, "dataPagamento": "2026-06-26", "metodo": "Bonifico",
               "confermaDiscordanza": True, "discordanzaVersione": signature}
    result, status = update_react_fascicolo_payment(get_fascicoli=lambda: fascicoli, id_fasc="FASC-1",
                                                   kind="fondo_spese", payload=payload, actor="Avv. Test")
    assert status == 200
    assert not result["payment"]["richiedeConferma"]
    assert result["payment"]["status"] == "pagato"
    assert result["payment"]["importo"] == 250.00
    decision = fascicolo.pagamenti[AUTOMATION_KEY]["discordanze"][0]
    assert decision["stato"] == "risolta" and decision["risolta_da"] == "Avv. Test"
    assert decision["importo_letto"] == 300.00 and decision["sha256"] == "a" * 64
    fascicolo.pagamenti[AUTOMATION_KEY]["discordanze"].append(dict(discrepancy, sha256="b" * 64))
    before = deepcopy(fascicolo.pagamenti)
    conflict, status = update_react_fascicolo_payment(get_fascicoli=lambda: fascicoli, id_fasc="FASC-1",
                                                     kind="fondo_spese", payload=payload, actor="Avv. Test")
    assert status == 409 and conflict["conflict"]
    assert fascicolo.pagamenti == before


@pytest.mark.parametrize("number,year", [("1234/2026", 2026), ("1234/2026", 0), ("001234/2026", ""), ("1234", 2026)])
def test_contesto_lettura_ruolo_completo_usa_resolver_nativo(number, year):
    from pct.archivio_letture.collaudo import contesto_da_fascicolo

    context = contesto_da_fascicolo({"numero_rg": number, "anno_rg": year, "tribunale": "Tribunale di Milano"})
    assert context.numero_rg == "1234"
    assert context.anno_rg == "2026"


def test_contesto_lettura_anno_discordante_non_diventa_coincidente():
    from pct.archivio_letture.collaudo import contesto_da_fascicolo, collauda
    from pct.registro_letture.fatti_repository import Fatto

    context = contesto_da_fascicolo({"numero_rg": "1234/2026", "anno_rg": 2025})
    source = Fatto(categoria="ruolo", campo="numero_ruolo", valore="1234/2026", origine="nativo")
    checked = collauda(source, context)
    assert checked.verifica != "verificata"


def test_sentenza_non_porta_cu_senza_documento_fascicolo():
    extraction = analyze_sentenza_tribunale_text(
        SENTENZA_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale"},
    )

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1100.00
    assert extraction.contributo_unificato_importo is None
    assert extraction.contributo_unificato_natura == ""


def test_estrazione_contributo_unificato_non_prende_importo_liquidazione():
    text = """
    Firmato Da: CARUSO GIUSEPPE Emesso Da: TRUSTPRO QUALIFIED CA Serial#: 123
    Sentenza n. 2208/2026 pubbl. il 28/04/2026
    RG n. 3685/2026
    condanna il Ministero alla rifusione in favore di parte ricorrente delle spese di lite,
    liquidate in complessivi € 1.100,00 oltre spese generali 15% e accessori di legge,
    oltre rimborso del contributo unificato.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1100.00
    assert extraction.contributo_unificato_importo is None


def test_estrazione_liquidazione_quattro_cifre_senza_punto_migliaia():
    text = """
    Firmato Da: GIUDICE TEST Emesso Da: TRUSTPRO QUALIFIED CA Serial#: 123
    Sentenza n. 588/2025 pubbl. il 04/11/2025
    RG n. 1916/2024
    condanna la resistente alla rifusione delle spese sostenute dalla parte ricorrente
    a tale titolo liquidando la complessiva somma di € 1030,00, oltre a spese
    generali ed accessori di legge.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1030.00


def test_estrazione_liquidazione_preferisce_compensi_professionali_al_totale():
    text = """
    Tribunale di Palmi
    Sentenza n. 10/2026 pubbl. il 01/02/2026
    RG n. 466/2023
    nel procedimento promosso da Rossi Mario contro Ministero dell'Istruzione.
    P.Q.M. condanna al pagamento delle spese processuali che liquida in complessivi
    Euro 2.454,68, di cui Euro 125,00 per spese ed Euro 1.500,00 per compensi
    professionali ed Euro 829,68 per spese generali e accessori.
    """

    extraction = analyze_sentenza_tribunale_text(text, {"tipo_documento": "Sentenza Tribunale"})

    assert extraction.found is True
    assert extraction.liquidazione_importo == 1500.00
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 125.00


def test_estrazione_sentenza_carta_docente_con_esborsi_senza_prendere_beneficio():
    extraction = analyze_sentenza_tribunale_text(
        MONTAGNESE_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    assert extraction.found is True
    assert extraction.sentence_date == "2025-09-23"
    assert extraction.sentence_number == "465"
    assert extraction.rg_number == "697"
    assert extraction.liquidazione_importo == 321.50
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 21.50
    assert extraction.beneficio_cliente_importo == 500.00
    assert extraction.beneficio_cliente_tipo == "carta_docente"
    assert extraction.fondo_spese_importo is None
    assert extraction.spese_generali is True
    assert extraction.antistatario is True


def test_estrazione_sentenza_carta_docente_con_quota_spese_senza_prendere_beneficio():
    text = MONTAGNESE_TEXT.replace("per esborsi", "per spese")

    extraction = analyze_sentenza_tribunale_text(
        text,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    assert extraction.found is True
    assert extraction.sentence_date == "2025-09-23"
    assert extraction.rg_number == "697"
    assert extraction.liquidazione_importo == 321.50
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 21.50
    assert extraction.fondo_spese_importo is None


def test_pdf_contributo_unificato_fornisce_doppia_prova_senza_carta_docente():
    evidence = extract_contributo_unificato_document_evidence(
        "Ricevuta pagamento PagoPA Contributo unificato. Importo versato euro 21,50.",
        {"filename": "CU.pdf", "document_id": "DOC-CU"},
    )
    carta = extract_contributo_unificato_document_evidence(
        "Accredito Carta elettronica docente con importo euro 500,00.",
        {"filename": "Bonifico carta docente.pdf", "document_id": "DOC-CARTA"},
    )

    assert evidence["importo"] == 21.50
    assert evidence["natura"] == "pdf_contributo_unificato"
    assert evidence["document_id"] == "DOC-CU"
    assert carta == {}


def test_pdf_contributo_unificato_legge_campo_rt_pagopa_senza_simbolo_euro():
    evidence = extract_contributo_unificato_document_evidence(
        """
        RICEVUTA TELEMATICA DI PAGAMENTO
        DATI PAGAMENTO
        Importo totale versato: 49.00
        Identificativo versamento: 30003628285360064
        Importo: 49.00
        Commissioni applicate: 0.00
        Data: 17/03/2026
        Causale: Contributo Ricorso carta docente Betti
        Tipo pagamento: Contributo unificato
        Esito: 0
        """,
        {
            "filename": "Pagamento cu.PDF",
            "classification": "Contributo unificato / pagamento",
            "document_id": "DOC-CU-RT",
        },
    )

    assert evidence["importo"] == 49.00
    assert evidence["status"] == "pagato"
    assert evidence["natura"] == "pdf_contributo_unificato"
    assert evidence["label"] == "Contributo unificato da ricevuta PagoPA"
    assert evidence["document_id"] == "DOC-CU-RT"


@pytest.mark.parametrize("testo", [
    "PROMEMORIA DI PAGAMENTO pagoPA - Ministero della Giustizia\nTipo pagamento: Contributo unificato\n"
    "Codice avviso: 301000000000000001\nImporto: 518,00",
    "AVVISO DI PAGAMENTO pagoPA\nTipo pagamento: Contributo unificato\nImporto da pagare: 518,00\nPagabile entro il 30/11/2026",
    "pagoPA\nTipo pagamento: Contributo unificato\nImporto: 518,00",
])
def test_avviso_o_promemoria_pagopa_non_e_contributo_pagato(testo):
    from pct.fascicolo_sentenza_economica import contributo_ricevuta_di_pagamento_eseguito

    assert contributo_ricevuta_di_pagamento_eseguito(testo) is False
    evidence = extract_contributo_unificato_document_evidence(testo, {"filename": "promemoria.pdf", "document_id": "D"})
    assert evidence.get("status") != "pagato"


@pytest.mark.parametrize("testo", [
    "pagoPA - Tipo pagamento: Contributo unificato - Importo: 518,00 - Data pagamento: 02/03/2026",
    "Promemoria pagoPA - Tipo pagamento: Contributo unificato - Importo: 518,00 - Pagamento eseguito",
    "<RT><datiPagamento><datiSingoloPagamento><causaleVersamento>Contributo unificato</causaleVersamento>"
    "<singoloImportoPagato>518.00</singoloImportoPagato></datiSingoloPagamento></datiPagamento></RT>",
])
def test_pagamento_eseguito_pagopa_resta_ricevuta(testo):
    from pct.fascicolo_sentenza_economica import contributo_ricevuta_di_pagamento_eseguito

    assert contributo_ricevuta_di_pagamento_eseguito(testo) is True


def test_patrocinio_a_spese_dello_stato_prenota_a_debito_il_contributo():
    evidence = extract_contributo_unificato_document_evidence(
        "Decreto di ammissione al patrocinio a spese dello Stato della parte ricorrente.",
        {"filename": "ammissione.pdf", "document_id": "D-PSS"},
    )
    assert evidence["status"] == "prenotato_a_debito" and evidence["prenotato_a_debito"] is True


def test_ricevuta_pagopa_esclude_le_commissioni_dal_contributo():
    evidence = extract_contributo_unificato_document_evidence(
        """
        RICEVUTA DI PAGAMENTO AVVISO PAGOPA
        Ente Creditore: MINISTERO DELLA GIUSTIZIA
        Importo: € 21,50
        Commissioni: € 1,50
        Totale: € 23,00
        ID Operazione: 7485018265
        """,
        {"filename": "Ricevuta_PagoPA.pdf", "document_id": "DOC-CU-PAGOPA"},
    )

    assert evidence["importo"] == 21.50
    assert evidence["status"] == "pagato"
    assert evidence["origine"] == "ricevuta_pagamento_contributo_unificato"


def test_avviso_pagopa_legge_importo_e_non_giorno_o_mese_della_scadenza():
    evidence = extract_contributo_unificato_document_evidence(
        """
        AVVISO DI PAGAMENTO
        Contributo unificato
        QUANTO E QUANDO PAGARE?
        49,00 Euro 09/01/2025 PAGA SUL SITO O CON LE APP entro il
        BANCHE E ALTRI CANALI RATA entro il 09/01/2025
        Destinatario Associazione Ricorrente Euro 49,00
        Ente Creditore Ministero della Giustizia
        """,
        {"filename": "Contributo unificato.PDF", "document_id": "DOC-CU-AVVISO"},
    )

    assert evidence["importo"] == 49.00
    assert evidence["status"] == "da_registrare"
    assert evidence["origine"] == "avviso_pagamento_contributo_unificato"


def test_avviso_seguito_da_ricevuta_cbill_preferisce_il_pagamento_concluso():
    evidence = extract_contributo_unificato_document_evidence(
        """
        AVVISO DI PAGAMENTO Contributo unificato
        QUANTO E QUANDO PAGARE? 21,50 Euro 09/06/2024
        Pagamento CBILL numero 29461243, inserito in data 10/05/2024 alle ore 11:15.
        CAUSALE PAGAMENTO: MINISTERO DELLA GIUSTIZIA
        IMPORTO: 21,50 €
        COMMISSIONI: 1,50 €
        TOTALE ADDEBITATO: 23,00 €
        """,
        {"filename": "Pagamento cu.PDF", "document_id": "DOC-CU-CBILL"},
    )

    assert evidence["importo"] == 21.50
    assert evidence["status"] == "pagato"
    assert evidence["origine"] == "ricevuta_pagamento_contributo_unificato"


def test_copia_deposito_con_contributo_e_diritti_prende_la_prima_ricevuta_pertinente():
    evidence = extract_contributo_unificato_document_evidence(
        """
        Oggetto: DEPOSITO TELEMATICO: Contributo unificato
        [Allegato: Contributo unificato.PDF]
        Pagamento bolletta PagoPA
        Codice azienda 80184430587 MINISTERO DELLA GIUSTIZIA
        Importo 49,00
        Commissioni banca 2,50
        Importo totale 51,50
        Stato Pagata
        Esito Pagamento bolletta PagoPA eseguito.
        Informazioni aggiuntive /RFB/30007606087363218/49.00/TXT/Contributo unificato
        [Allegato: Diritti forfettizzati.PDF]
        Pagamento bolletta PagoPA
        Importo 27,00
        Importo totale 29,50
        AVVISO DI PAGAMENTO Diritti di copia
        QUANTO E QUANDO PAGARE? 27,00 Euro 12/02/2025
        """,
        {"filename": "COPIA DEPOSITO: Contributo unificato.EML", "document_id": "DOC-CU-EML"},
    )

    assert evidence["importo"] == 49.00
    assert evidence["status"] == "pagato"
    assert evidence["origine"] == "ricevuta_pagamento_contributo_unificato"


def test_pdf_contributo_unificato_legge_modello_f23_senza_simbolo_euro():
    evidence = extract_contributo_unificato_document_evidence(
        """
        AGENZIA DELLE ENTRATE
        MODELLO DI PAGAMENTO
        TASSE IMPOSTE SANZIONI ED ALTRE ENTRATE
        codice tributo 941T
        CONTRIBUTO UNIFICATO 21,50
        PER UN IMPORTO COMPLESSIVO DI EURO | 21,50
        """,
        {"filename": "Contributo unificato Moscato.PDF"},
    )

    assert evidence["importo"] == 21.50
    assert evidence["natura"] == "modello_f23_f24_contributo_unificato"
    assert evidence["status"] == "pagato"


def test_pdf_contributo_classificato_senza_importo_non_diventa_pagato():
    marker = (
        "Presidio creato automaticamente dall'import pratiche; verificare ricevuta "
        "PagoPA/contributo nel fascicolo importato. Import pratiche"
    )

    assert extract_contributo_unificato_document_evidence(marker, {"filename": marker}) == {}
    assert (
        extract_contributo_unificato_document_evidence(
            "",
            {
                "filename": "Pagamento cu.PDF",
                "classification": "Contributo unificato / pagamento",
                "document_id": "DOC-CU-CLASSIFICATO",
            },
        )
        == {}
    )


def test_pdf_richiesta_versamento_cu_non_diventa_pagato_ne_proforma(tmp_path: Path):
    evidence = extract_contributo_unificato_document_evidence(
        """
        UFFICIO DEL GIUDICE DI PACE DI PALMI
        Oggetto: Richiesta versamento contributo unificato.
        SI INVITA il Sig. Alessi Robertino a pagare entro il termine di 30 gg.
        la somma di euro 98,00 per omesso versamento del contributo unificato.
        Il pagamento dovra' essere effettuato mediante piattaforma tecnologica.
        """,
        {"filename": "attoACQ.pdf", "document_id": "DOC-CU-DOVUTO"},
    )

    assert evidence["importo"] == 98.00
    assert evidence["status"] == "da_registrare"
    assert evidence["natura"] == "richiesta_versamento_contributo_unificato"
    assert evidence["label"] == "Contributo unificato da pagare"

    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={
            "document_id": "DOC-SENTENZA",
            "filename": "Sentenza.pdf",
            "tipo_documento": "Sentenza Tribunale",
            "contributo_unificato_pdf": evidence,
        },
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    assert outcome.applied is True
    assert fascicolo.pagamenti["contributo_unificato"]["status"] == "da_registrare"
    assert fascicolo.pagamenti["contributo_unificato"]["importo"] == 98.00
    assert fascicolo.pagamenti["contributo_unificato"]["data_pagamento"] == ""
    assert fascicolo.pagamenti["contributo_unificato"]["label"] == "Contributo unificato da pagare"
    assert fatturazione.per_fascicolo("FASC-1") == []


def test_pdf_contributo_esenzione_non_prende_carta_docente_500():
    evidence = extract_contributo_unificato_document_evidence(
        """
        Il docente chiede la Carta elettronica per l'aggiornamento e la formazione,
        dell'importo nominale di euro 500,00 annui per ciascun anno scolastico.
        Esenzione dal contributo unificato di iscrizione a ruolo ai sensi
        dell'art. 9 comma 1 bis d.p.r. 30/5/2002 n. 115.
        """,
        {"filename": "ricorso-carta-docente.pdf", "document_id": "DOC-ESENTE-CARTA"},
    )

    assert evidence["esente"] is True
    assert evidence["importo"] is None
    assert evidence["natura"] == "esenzione_contributo_unificato"


def test_pdf_contributo_esenzione_reddituale_non_prende_soglia_reddito():
    evidence = extract_contributo_unificato_document_evidence(
        """
        AUTOCERTIFICAZIONE DELLA SITUAZIONE REDDITUALE.
        ESENZIONE DAL CONTRIBUTO UNIFICATO DI ISCRIZIONE A RUOLO.
        Dichiara che il proprio reddito, compreso quello dei familiari conviventi
        ex art. 76 D.P.R. 115/2002, non supera l'importo di Euro 38.514,03.
        """,
        {"filename": "dichiarazione-reddituale.pdf", "document_id": "DOC-REDDITO"},
    )

    assert evidence["esente"] is True
    assert evidence["importo"] is None
    assert evidence["natura"] == "esenzione_contributo_unificato"


def test_pdf_contributo_rifiuta_sentenza_carta_docente_con_cu_generico():
    evidence = extract_contributo_unificato_document_evidence(
        """
        REPUBBLICA ITALIANA
        IN NOME DEL POPOLO ITALIANO
        SENTENZA
        Condanna il Ministero a costituire la Carta elettronica del docente,
        dell'importo nominale di euro 500,00 annui. Il contributo unificato
        segue il regime previsto dal testo unico spese di giustizia.
        """,
        {"filename": "Sentenza RG 252 2026.pdf", "document_id": "DOC-CARTA-500"},
    )

    assert evidence == {}


def test_pdf_contributo_rifiuta_soglia_reddito_se_non_ce_esenzione_esplicita():
    evidence = extract_contributo_unificato_document_evidence(
        """
        Dichiarazione sostitutiva resa ai sensi dell'art. 76 D.P.R. 115/2002.
        Il reddito complessivo del nucleo familiare non supera Euro 38.514,03.
        """,
        {"filename": "dichiarazione-reddituale.pdf", "document_id": "DOC-REDDITO-SOGLIA"},
    )

    assert evidence == {}


def test_pdf_contributo_rifiuta_iniziali_cu_e_importo_carta_docente():
    evidence = extract_contributo_unificato_document_evidence(
        """
        Il riferimento alla mera natura temporanea del lavoro della signora C.U.
        non puo' costituire una ragione oggettiva. La ricorrente chiede
        il riconoscimento della carta docente per un importo di euro 500,00.
        """,
        {"filename": "sentenza-carta-docente.pdf", "document_id": "DOC-CU-INIZIALI"},
    )

    assert evidence == {}


def test_pdf_contributo_rifiuta_scaglione_e_riporta_esenzione_cu():
    scaglione = extract_contributo_unificato_document_evidence(
        """
        Ricevuta contributo unificato: si dichiara che il valore della domanda e'
        compreso nello scaglione tra euro 5.200,00 ed euro 26.000,00.
        Il contributo unificato dovuto e versato e' pari ad euro.
        """,
        {"filename": "CU-scaglione.pdf", "document_id": "DOC-CU-SCAGLIONE"},
    )
    esente = extract_contributo_unificato_document_evidence(
        "Contributo unificato non dovuto: parte esente dal pagamento.",
        {"filename": "CU-esente.pdf", "document_id": "DOC-CU-ESENTE"},
    )
    patrocinio = extract_contributo_unificato_document_evidence(
        "Decreto di ammissione al patrocinio a spese dello Stato della parte ricorrente.",
        {"filename": "patrocinio-stato.pdf", "document_id": "DOC-PSS"},
    )

    assert scaglione == {}
    assert esente["esente"] is True
    assert esente["importo"] is None
    assert esente["natura"] == "esenzione_contributo_unificato"
    assert esente["label"] == "Contributo unificato esente"
    assert patrocinio["esente"] is True
    assert patrocinio["importo"] is None


@pytest.mark.parametrize("esito,expected", [("Pagamento eseguito - esito positivo", "pagato"),
                                           ("Pagamento non eseguito - esito negativo", "da_registrare")])
def test_ricevuta_cu_con_etichetta_importo_conserva_esito_effettivo(esito, expected):
    text = f"Ricevuta di pagamento contributo unificato\nContributo unificato: euro 49,00\n{esito}\nData pagamento: 12/10/2026"
    evidence = extract_contributo_unificato_document_evidence(text, {"filename": "ricevuta-cu-collaudo.pdf"})
    assert evidence["importo"] == 49
    assert evidence["status"] == expected


def test_riepilogo_ruolo_con_importo_non_diventa_esente_per_una_etichetta_vuota():
    evidence = extract_contributo_unificato_document_evidence(
        """
        OGGETTO solo danni a cose Num. R.G. 139/2023.
        Contributo Unificato: 237,00
        Attori e convenuti - Esente Contributo Unificato
        Data di citazione: 08/06/2023.
        """,
        {"filename": "Documento_69428925.pdf", "document_id": "934AFA20"},
    )

    assert evidence.get("esente") is not True
    assert evidence["importo"] == 237.00
    assert evidence["status"] == "da_registrare"
    assert evidence["origine"] == "riepilogo_ruolo_contributo_unificato"


def test_esenzione_esplicita_prevale_anche_se_il_riepilogo_riporta_un_importo():
    evidence = extract_contributo_unificato_document_evidence(
        """
        Contributo Unificato: 237,00.
        La parte è esente dal pagamento del contributo unificato per ammissione
        al patrocinio a spese dello Stato.
        """,
        {"filename": "provvedimento-esenzione.pdf", "document_id": "DOC-ESENTE"},
    )

    assert evidence["esente"] is True
    assert evidence["importo"] is None


def test_esenzione_cu_da_pdf_viene_salvata_senza_importo_e_senza_voce_proforma(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    metadata = {
        "document_id": "DOC-ESENTE",
        "filename": "sentenza.pdf",
        "tipo_documento": "Sentenza Tribunale",
        "contributo_unificato_pdf": {
            "esente": True,
            "importo": None,
            "titolo": "Contributo unificato non dovuto: parte esente dal pagamento.",
            "filename": "CU-esente.pdf",
            "natura": "esenzione_contributo_unificato",
            "label": "Contributo unificato esente",
        },
    }

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    cu = fascicolo.pagamenti["contributo_unificato"]
    assert outcome.applied is True
    assert outcome.extraction.contributo_unificato_esente is True
    assert outcome.extraction.contributo_unificato_importo is None
    assert cu["status"] == "non_previsto"
    assert cu["previsto"] is False
    assert cu["importo"] is None
    assert cu["data_pagamento"] == ""
    assert cu["natura"] == "esenzione_contributo_unificato"
    assert cu["label"] == "Contributo unificato esente"
    assert fatturazione.per_fascicolo("FASC-1") == []


def test_pdf_contributo_non_sovrascrive_esborsi_sentenza_se_importo_diverge():
    extraction = analyze_sentenza_tribunale_text(
        MONTAGNESE_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    apply_contributo_unificato_pdf_evidence(
        extraction,
        {
            "contributo_unificato_pdf": {
                "importo": 49.00,
                "filename": "CU.pdf",
                "natura": "pdf_contributo_unificato",
                "label": "Contributo unificato da PDF",
            }
        },
    )

    assert extraction.contributo_unificato_importo == 49.00
    assert extraction.contributo_unificato_natura == "pdf_contributo_unificato"
    assert extraction.contributo_unificato_label == "Contributo unificato da PDF"
    assert extraction.spese_esborsi_importo == 21.50
    assert "contributo_unificato_pdf_distinto_da_spese_sentenza" in extraction.warnings


def test_pdf_contributo_esborsi_identici_preserva_fonti_e_segnala_ambiguita():
    extraction = analyze_sentenza_tribunale_text(
        MONTAGNESE_TEXT,
        {"tipo_documento": "provvedimento Sentenza Tribunale", "filename": "Sentenza.pdf"},
    )

    apply_contributo_unificato_pdf_evidence(
        extraction,
        {
            "contributo_unificato_pdf": {
                "importo": 21.50,
                "filename": "CU.pdf",
                "natura": "pdf_contributo_unificato",
                "label": "Contributo unificato da PDF",
            }
        },
    )

    assert extraction.contributo_unificato_importo == 21.50
    assert extraction.contributo_unificato_natura == "pdf_contributo_unificato"
    assert extraction.contributo_unificato_label == "Contributo unificato da PDF"
    assert extraction.spese_esborsi_importo == 21.50
    assert extraction.discordanze[0]["motivo"] == "possibile_sovrapposizione_contributo_esborsi"
    assert extraction.discordanze[0]["fonte_contributo"]["filename"] == "CU.pdf"
    assert "contributo_unificato_da_pdf" in extraction.warnings


def test_pdf_contributo_discordante_non_sovrascrive_la_lettura_precedente():
    extraction = analyze_sentenza_tribunale_text(MONTAGNESE_TEXT, {})
    extraction.contributo_unificato_importo = 49.00
    extraction.contributo_unificato_titolo = "Contributo € 49,00 nella fonte precedente"
    extraction.contributo_unificato_natura = "contributo_unificato"
    metadata = {"contributo_unificato_pdf": {"importo": 98.00, "filename": "ricevuta-sintetica.pdf",
                "sha256": "a" * 64, "document_id": "CU-SINTETICO", "natura": "pdf_contributo_unificato"}}
    apply_contributo_unificato_pdf_evidence(extraction, metadata)
    assert extraction.contributo_unificato_importo == 49.00
    assert extraction.contributo_unificato_titolo == "Contributo € 49,00 nella fonte precedente"
    assert extraction.discordanze[0]["importo_letto"] == 98.00
    assert extraction.discordanze[0]["fonte_contributo"]["sha256"] == "a" * 64
    before = deepcopy(extraction.discordanze)
    apply_contributo_unificato_pdf_evidence(extraction, metadata)
    assert extraction.discordanze == before


def test_ambiguita_cu_esborsi_non_genera_proforma_ne_somma(tmp_path):
    fascicoli = FakeFascicoliRepository()
    fascicolo = fascicoli.fascicolo
    fascicolo.nome_cliente = "Roberta Montagnese"
    fascicolo.titolo = "Roberta Montagnese c. MIM"
    fascicolo.tribunale = "Tribunale di Vicenza"
    fascicolo.numero_rg = "697/2025"
    fascicolo.anno_rg = 2025
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    metadata = {"document_id": "DOC-AMBIGUO", "sha256": "b" * 64, "codice_fiscale_cliente": "MNTRRT98P65G791Q",
                "contributo_unificato_pdf": {"importo": 21.50, "filename": "CU.pdf", "sha256": "c" * 64,
                                             "natura": "pdf_contributo_unificato"}}
    first = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1", text=MONTAGNESE_TEXT, document_metadata=metadata)
    assert first.applied
    assert not first.proforma_id
    assert not first.changes["proformaCreated"]
    assert fatturazione.per_fascicolo("FASC-1") == []
    assert fascicolo.pagamenti["spese_esborsi"]["importo"] == 21.50
    assert fascicolo.pagamenti["contributo_unificato"]["importo"] == 21.50
    assert fascicolo.pagamenti[AUTOMATION_KEY]["discordanze"][0]["sha256"] == "b" * 64
    summary = payment_summary_for_fascicolo(fascicolo)
    assert summary["items"]["spese_esborsi"]["richiedeConferma"]
    second = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1", text=MONTAGNESE_TEXT, document_metadata=metadata)
    assert not second.applied
    assert len(fascicolo.pagamenti[AUTOMATION_KEY]["discordanze"]) == 1


def test_estrazione_sentenza_resa_con_data_testuale_e_rg_iniziale():
    text = """
    N. R.G 697/2025
    TRIBUNALE ORDINARIO di VICENZA
    SENTENZA
    ROBERTA MONTAGNESE contro MINISTERO DELL'ISTRUZIONE E DEL MERITO
    Il Giudice del Lavoro, definitivamente pronunciando:
    condanna parte resistente a tale titolo liquidando la complessiva somma di € 321,50,
    di cui € 21,50 per esborsi, oltre a spese generali ed accessori di legge.
    Sentenza resa ex art. 127 ter c.p.c.
    Vicenza, 23 settembre 2025.
    """

    extraction = analyze_sentenza_tribunale_text(text, {"tipo_documento": "Sentenza Tribunale"})

    assert extraction.found is True
    assert extraction.sentence_date == "2025-09-23"
    assert extraction.sentence_number == ""
    assert extraction.rg_number == "697"
    assert extraction.liquidazione_importo == 321.50
    assert extraction.contributo_unificato_importo is None
    assert extraction.spese_esborsi_importo == 21.50


def test_estrazione_rg_preferisce_intestazione_sentenza():
    text = """
    Nel corpo della motivazione viene richiamato il precedente RG n. 4593/2022.

    Tribunale di Palmi
    Sentenza n. 230/2024 pubbl. il 07/05/2024
    RG n. 1548/2023
    condanna il Ministero liquidando la complessiva somma di € 1.100,00.
    """

    extraction = analyze_sentenza_tribunale_text(
        text,
        {"tipo_documento": "provvedimento Sentenza Tribunale"},
    )

    assert extraction.found is True
    assert extraction.rg_number == "1548"
    assert extraction.rg_year == "2023"


def test_estrazione_sentenza_ufficiale_senza_parola_tribunale():
    text = """
    Firmato Da: CARUSO GIUSEPPE Emesso Da: TRUSTPRO QUALIFIED CA Serial#: 123
    Sentenza n. 376/2026 pubbl. il 13/05/2026
    RG n. 2962/2023
    Sentenza n. cronol. 2516/2026 del 13/05/2026
    P.Q.M. condanna la resistente liquidando la complessiva somma di € 500,00.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is True
    assert extraction.sentence_number == "376"
    assert extraction.sentence_date == "2026-05-13"
    assert extraction.rg_number == "2962"


def test_estrazione_non_scambia_citazione_cassazione_per_sentenza_fascicolo():
    text = """
    Atto di diffida in riferimento alla sentenza n. 16715/2024 della Corte Suprema
    di Cassazione Sezione Lavoro, pubblicata il 17/06/2024.
    La parte chiede il riconoscimento delle somme dovute.
    """

    extraction = analyze_sentenza_tribunale_text(text, {})

    assert extraction.found is False


def test_incasso_manual_preserva_importo_stato_e_prova_della_sentenza(monkeypatch):
    from web.services import react_fascicoli_bridge as bridge

    raw = {"importo": 1100.00, "status": "pagato", "pagato": True,
           "metodo": "Bonifico", "data_pagamento": "2026-10-12", "note": "Incasso confermato",
           "history": [{"by": "Avvocato", "toStatus": "pagato"}]}
    proof = {"documentoId": "DOC-SENTENZA", "sha256": "a" * 64,
             "previewHref": "/fascicoli/FASC-1/documenti/DOC-SENTENZA/visualizza",
             "contesto": "Il giudice liquida € 1.100,00 per compensi."}
    fascicolo = SimpleNamespace(id="FASC-1", pagamenti={"liquidazione_giudice": raw})
    monkeypatch.setattr(bridge, "_importi_dall_archivio", lambda *_: {
        "liquidazione_giudice": {"importo": 1100.00, "status": "da_registrare", "fontiVerifica": [proof], "richiedeConferma": False},
    })
    result = bridge._payments_with_automatic_sources(fascicolo, fascicolo.pagamenti, enabled=True)
    item = result["liquidazione_giudice"]
    assert item["importo"] == 1100.00 and item["status"] == "pagato"
    assert item["data_pagamento"] == "2026-10-12" and item["metodo"] == "Bonifico"
    assert item["fontiVerifica"] == [proof]
    assert raw["note"] == "Incasso confermato" and "fontiVerifica" not in raw


def test_voce_unica_apre_originale_documentale_e_copia_pec(monkeypatch):
    from pct.registro_letture import Fatto
    from web.services import react_fascicoli_bridge as bridge, registro_letture_runtime as runtime

    fonti = [{"fatto_id": "doc-1", "tipo": "documento", "oggetto_id": "DOC", "sha256": "a" * 64,
              "estratto": "Compensi liquidati € 1.100,00."},
             {"fatto_id": "pec-1", "tipo": "allegato_pec", "oggetto_id": "PEC-DOC", "sha256": "b" * 64,
              "estratto": "Compensi liquidati € 1.100,00."}]
    fatto = Fatto(id="canon-1", fascicolo_id="F1", tipo="documento", oggetto_id="DOC", sha256="a" * 64,
                  categoria="importo", campo="liquidazione_giudice", valore="1100.00", verifica="verificata",
                  contesto="Compensi liquidati € 1.100,00.", prove=[{"codice": "fonti_unite", "fonti": fonti}])
    oggetti = {"DOC": SimpleNamespace(presente=True, impronta="a" * 64, sha256="a" * 64,
                                       nome="originale.pdf", oggetto_id="DOC", origine=""),
               "PEC-DOC": SimpleNamespace(presente=True, impronta="b" * 64, sha256="b" * 64,
                                           nome="copia.pdf", oggetto_id="PEC-DOC", origine="PEC-1")}
    monkeypatch.setattr(bridge, "_fatti_archivio", lambda *_args, **_kwargs: [fatto])
    monkeypatch.setattr(runtime, "tenant_corrente", lambda: "TEST-TENANT")
    monkeypatch.setattr(runtime, "registro_corrente", lambda: SimpleNamespace(oggetto=lambda *_args: oggetti[_args[-1]]))
    fascicolo = SimpleNamespace(id="F1", documenti=[SimpleNamespace(id="DOC")], pagamenti={})
    voce = bridge._importi_dall_archivio(fascicolo, {})["liquidazione_giudice"]
    assert voce["importo"] == 1100.00 and not voce["richiedeConferma"]
    prove = voce["fontiVerifica"]
    assert len(prove) == 2
    assert prove[0]["previewHref"] == "/fascicoli/F1/documenti/DOC/visualizza"
    assert prove[1]["previewHref"] == "/api/v1/ui/email/source/PEC-1?name=copia.pdf&sha256=" + "b" * 64


def test_liquidazione_sentenza_automatica_senza_parcella_imposta(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    metadata = {"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"}
    first = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1", text=SENTENZA_TEXT, document_metadata=metadata, actor="Lex AI",
    )
    second = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1", text=SENTENZA_TEXT, document_metadata=metadata, actor="Lex AI",
    )
    assert first.applied and not second.applied
    payment = fascicoli.fascicolo.pagamenti["liquidazione_giudice"]
    assert payment["importo"] == 1100.00
    assert payment["status"] == "da_registrare" and not payment["pagato"]
    assert payment["documento_fonte"] == "document_id:DOC-1"
    assert not first.proforma_id and not first.changes["proformaCreated"]
    assert fatturazione.per_fascicolo("FASC-1") == []
    assert "parcella" not in fascicoli.fascicolo.pagamenti
    summary = payment_summary_for_fascicolo(fascicoli.fascicolo)
    assert not summary["items"]["parcella"]["previsto"]
    assert summary["items"]["parcella"]["statusLabel"] == "Facoltativa"
    assert not summary["proformaPresidio"]["requiresAction"]
    assert summary["proformaPresidio"]["status"] == "facoltativa"


def test_proforma_su_richiesta_esplicita_e_replay_idempotente(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    metadata = {
        "document_id": "DOC-1",
        "filename": "sentenza.pdf",
        "tipo_documento": "Sentenza Tribunale",
        "contributo_unificato_pdf": {
            "importo": 98.00,
            "filename": "CU.pdf",
            "natura": "pdf_contributo_unificato",
            "label": "Contributo unificato da PDF",
        },
    }

    first = apply_sentenza_tribunale_automation(
        proforma_requested=True,
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
        actor="Lex AI",
    )
    second = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    assert first.applied is True
    assert second.applied is False
    assert second.changes["alreadyProcessed"] is True
    assert second.message == "Sentenza Tribunale già applicata al fascicolo."
    assert fascicolo.data_prossima_udienza == "n.d."
    assert fascicolo.data_chiusura == ""
    assert getattr(fascicolo.stato, "value", fascicolo.stato) == StatoFascicolo.IN_CORSO.value
    assert not first.changes["nextDeadlineChanged"]
    assert not first.changes["statusChanged"]
    assert fascicolo.pagamenti["contributo_unificato"]["status"] == "da_registrare"
    assert fascicolo.pagamenti["contributo_unificato"]["data_pagamento"] == ""
    assert fascicolo.pagamenti["contributo_unificato"]["importo"] == 98.00
    assert fascicolo.pagamenti["liquidazione_giudice"]["status"] == "da_registrare"
    assert not fascicolo.pagamenti["liquidazione_giudice"]["pagato"]
    assert fascicolo.pagamenti["liquidazione_giudice"]["data_pagamento"] == ""
    assert fascicolo.pagamenti["liquidazione_giudice"]["metodo"] == ""
    assert fascicolo.pagamenti["liquidazione_giudice"]["importo"] == 1100.00
    assert fascicolo.pagamenti["parcella"]["status"] == "da_emettere"
    assert fascicolo.pagamenti["parcella"]["proforma_id"] == first.proforma_id

    proforme = fatturazione.per_fascicolo("FASC-1")
    assert len(proforme) == 1
    assert proforme[0].numero == "2024/001"
    assert proforme[0].origine == ORIGIN
    assert proforme[0].dati_personalizzati["document"]["documento_operativo"] == "PROFORMA"


@pytest.mark.parametrize('origin', ['', 'manuale', 'riconciliazione_incassi', ORIGIN])
def test_rilettura_sentenza_preserva_incasso_e_parcella_manuali(tmp_path: Path, origin):
    fascicoli = FakeFascicoliRepository()
    manual = {'status':'pagato', 'importo':1100.0, 'pagato':True, 'data_pagamento':'2024-06-10',
              'metodo':'Assegno', 'origine':origin,
              'history':[{'by':'Avvocato', 'toStatus':'pagato', 'note':'Incasso confermato'}]}
    fascicoli.fascicolo.pagamenti = {'liquidazione_giudice':deepcopy(manual), 'parcella':deepcopy(manual)}
    fascicoli.fascicolo.stato = StatoFascicolo.SOSPESO
    fascicoli.fascicolo.data_prossima_udienza = '2024-07-01'
    before = deepcopy(fascicoli.fascicolo.pagamenti)
    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=GestioneFatturazione(str(tmp_path/'parcelle.json')),
        fascicolo_id='FASC-1', text=SENTENZA_TEXT,
        document_metadata={'document_id':'DOC-1', 'filename':'sentenza.pdf', 'tipo_documento':'Sentenza Tribunale'},
        actor='Lex AI')
    for kind in before:
        assert fascicoli.fascicolo.pagamenti[kind] == before[kind]
        assert kind not in outcome.changes['payments']
    assert fascicoli.fascicolo.stato == StatoFascicolo.SOSPESO
    assert fascicoli.fascicolo.data_prossima_udienza == '2024-07-01'
    assert fascicoli.fascicolo.data_chiusura == ''
    assert fascicoli.fascicolo.avanzamento == []


def test_rilettura_sentenza_conserva_stato_pagamento_lex_preesistente(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fascicoli.fascicolo.pagamenti = {'liquidazione_giudice':{
        'status':'pagato', 'pagato':True, 'importo':1100.0, 'data_pagamento':'2024-05-07',
        'metodo':'Bonifico bancario', 'origine':ORIGIN, 'documento_fonte':'document_id:DOC-1',
        'history':[{'origine':ORIGIN, 'toStatus':'pagato'}]}}
    apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=GestioneFatturazione(str(tmp_path/'parcelle.json')),
        fascicolo_id='FASC-1', text=SENTENZA_TEXT,
        document_metadata={'document_id':'DOC-1', 'filename':'sentenza.pdf', 'tipo_documento':'Sentenza Tribunale'},
        actor='Lex AI')
    payment = fascicoli.fascicolo.pagamenti['liquidazione_giudice']
    assert payment['status'] == 'pagato'
    assert payment['pagato'] is True
    assert payment['data_pagamento'] == '2024-05-07'
    assert payment['metodo'] == 'Bonifico bancario'
    assert payment['importo'] == 1100.0
    assert payment['history'] == [{'origine':ORIGIN, 'toStatus':'pagato'}]


@pytest.mark.parametrize('source_changed,manual_amount', [(False, None), (True, None), (False, 333.0)])
def test_rilettura_non_somma_due_liquidazioni_nella_stessa_proforma(tmp_path: Path, source_changed, manual_amount):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path/'parcelle.json'))
    metadata = {'document_id':'DOC-1', 'filename':'sentenza.pdf', 'tipo_documento':'Sentenza Tribunale', 'sha256':'a'*64}
    first = apply_sentenza_tribunale_automation(
        proforma_requested=True,
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione, fascicolo_id='FASC-1',
        text=SENTENZA_TEXT, document_metadata=metadata, actor='Lex AI')
    if manual_amount is not None:
        proforma = fatturazione.get(first.proforma_id)
        proforma.voci[0].prezzo_unitario = manual_amount
        fatturazione.aggiorna(proforma.id, voci=proforma.voci)
    second_metadata = dict(metadata, sha256='b'*64) if source_changed else metadata
    corrected_text = SENTENZA_TEXT.replace('1.100,00', '260,00')
    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione, fascicolo_id='FASC-1',
        text=corrected_text, document_metadata=second_metadata, actor='Lex AI')
    proforma = fatturazione.get(first.proforma_id)
    fees = [v for v in proforma.voci if v.tipo == 'ONORARIO']
    assert len(fees) == 1
    assert fees[0].prezzo_unitario == (manual_amount or 1100.0)
    assert proforma.dati_personalizzati['lex_sentenza_reconciliation']['conflicts'][0]['amount'] == 260.0
    assert 'proforma_importi_discordanti' in outcome.extraction.warnings
    assert fascicoli.fascicolo.pagamenti['liquidazione_giudice']['importo'] == 1100.0
    discordanza = fascicoli.fascicolo.pagamenti[AUTOMATION_KEY]['discordanze'][0]
    assert discordanza['importo_registrato'] == 1100.0
    assert discordanza['importo_letto'] == 260.0
    assert discordanza['sha256'] == second_metadata['sha256']
    summary = payment_summary_for_fascicolo(fascicoli.fascicolo)
    assert summary['items']['liquidazione_giudice']['richiedeConferma'] is True
    assert '€ 260,00' in summary['items']['liquidazione_giudice']['verificheMancanti'][0]
    again = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli, fatturazione_repository=fatturazione, fascicolo_id='FASC-1',
        text=corrected_text, document_metadata=second_metadata, actor='Lex AI')
    assert not again.applied
    assert len([v for v in fatturazione.get(first.proforma_id).voci if v.tipo == 'ONORARIO']) == 1


@pytest.mark.parametrize("backend", ["sqlite", "postgresql"])
@pytest.mark.parametrize("valuta_posposta", [False, True])
def test_fondo_esborsi_sql_persistenza_autorevole_sul_mirror(tmp_path, backend, valuta_posposta):
    from pct.storage import StudioDB

    if backend == "postgresql":
        dsn = os.environ.get("IUSENTRA_ECONOMIC_TEST_POSTGRES_DSN", "")
        if not dsn:
            pytest.skip("PostgreSQL isolato non configurato per questo guardrail")
        from pct.storage_postgres import PostgresStudioDB
        import psycopg2
        from psycopg2 import sql
        from psycopg2.extensions import make_dsn

        schema = "iusentra_test_economico_" + uuid.uuid4().hex
        with psycopg2.connect(dsn) as owner, owner.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        database = PostgresStudioDB(make_dsn(dsn, options=f"-c search_path={schema}"))
    else:
        database = StudioDB(str(tmp_path / "studio.db"))
    try:
        database.conn.execute("INSERT INTO clienti(id,tipo,cognome,nome,codice_fiscale,dati_json) VALUES (?,?,?,?,?,?)",
                              ("CLI-SQL", "PERSONA_FISICA", "Montagnese", "Roberta", "MNTRRT98P65G791Q", "{}"))
        database.conn.execute("COMMIT")
        fascicoli = GestioneFascicoli(str(tmp_path / "fascicoli.json"), studio_db=database)
        fascicolo = Fascicolo(id="FASC-SQL", numero="2025/001", titolo="Roberta Montagnese c. MIM",
                              tipo=TipoFascicolo.CIVILE, nome_cliente="Roberta Montagnese", id_cliente="CLI-SQL",
                              tribunale="Tribunale di Vicenza", numero_rg="697/2025", anno_rg=2025)
        fascicoli._fascicoli[fascicolo.id] = fascicolo
        fascicoli._salva()
        fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"), studio_db=database)
        metadata = {"document_id": "DOC-SQL", "sha256": "f" * 64, "tipo_documento": "Sentenza", "codice_fiscale_cliente": "MNTRRT98P65G791Q"}
        testo = MONTAGNESE_TEXT.replace("€ 321,50", "321,50 euro") if valuta_posposta else MONTAGNESE_TEXT
        first = apply_sentenza_tribunale_automation(
            fascicoli_repository=fascicoli, fatturazione_repository=fatturazione,
            fascicolo_id=fascicolo.id,
            text=testo + "\nFondo spese riconosciuto pari a € 250,00.", document_metadata=metadata)
        assert first.applied
        reopened = GestioneFascicoli(str(tmp_path / "fascicoli.json"), studio_db=database).get(fascicolo.id)
        assert reopened.pagamenti["spese_esborsi"]["importo"] == 21.50
        assert reopened.pagamenti["liquidazione_giudice"]["importo"] == 321.50
        assert reopened.pagamenti["fondo_spese"]["importo"] == 250.00
        assert reopened.pagamenti["fondo_spese"]["source_sha256"] == "f" * 64
        assert reopened.id_cliente == "CLI-SQL"
        # Il mirror nativo è preservato ma non governa la riapertura SQL.
        (tmp_path / "fascicoli.json").write_text("{}", encoding="utf-8")
        assert GestioneFascicoli(str(tmp_path / "fascicoli.json"), studio_db=database).get(fascicolo.id).pagamenti == reopened.pagamenti
        assert not first.proforma_id
        assert GestioneFatturazione(str(tmp_path / "parcelle.json"), studio_db=database).per_fascicolo(fascicolo.id) == []
    finally:
        if backend == "postgresql":
            database.raw_conn.close()
        else:
            database._close_thread_connection()


def test_documento_duplicato_stessa_sentenza_riusa_proforma_esistente(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))

    first = apply_sentenza_tribunale_automation(
        proforma_requested=True,
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"},
        actor="Lex AI",
    )
    duplicate = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={"document_id": "DOC-2", "filename": "sentenza-copia.pdf", "tipo_documento": "Sentenza Tribunale"},
        actor="Lex AI",
    )

    automation = fascicoli.get("FASC-1").pagamenti[AUTOMATION_KEY]
    assert first.proforma_id
    assert duplicate.proforma_id == first.proforma_id
    assert duplicate.changes["proformaCreated"] is False
    assert len(fatturazione.per_fascicolo("FASC-1")) == 1
    assert set(automation["processed_documents"]) == {"document_id:DOC-1", "document_id:DOC-2"}
    assert automation["proforme"]["document_id:DOC-2"] == first.proforma_id


def test_sentenza_gia_processata_completa_esborsi_e_importo_parcella(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fascicoli.fascicolo.titolo = "Montagnese Roberta c. MIM"
    fascicoli.fascicolo.nome_cliente = "Montagnese Roberta"
    fascicoli.fascicolo.tribunale = "Tribunale di Vicenza"
    fascicoli.fascicolo.numero_rg = "697"
    fascicoli.fascicolo.anno_rg = 2025
    fascicoli.fascicolo.stato = StatoFascicolo.DEFINITO
    fascicoli.fascicolo.data_prossima_udienza = "2025-09-23"
    document_key = "document_id:DOC-MONTAGNESE"
    fascicoli.fascicolo.pagamenti = {
        "liquidazione_giudice": {
            "kind": "liquidazione_giudice",
            "status": "pagato",
            "importo": 321.50,
            "data_pagamento": "2025-09-23",
            "origine": ORIGIN,
        },
        "parcella": {
            "kind": "parcella",
            "status": "da_emettere",
            "importo": None,
            "data_pagamento": "2025-09-23",
            "origine": ORIGIN,
        },
        AUTOMATION_KEY: {"processed_documents": [document_key], "proforme": {}},
    }
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    proforma = fatturazione.crea(
        id_cliente="CLI-1",
        id_fascicolo="FASC-1",
        data_emissione="2025-09-23",
        voci=[VoceParcella(descrizione="Compensi liquidati in sentenza", prezzo_unitario=321.50)],
        percentuale_spese_generali=15.0,
        origine=ORIGIN,
        dati_personalizzati={
            "document": {"documento_operativo": "PROFORMA", "tipo_documento_label": "Proforma"},
            "lex_sentenza": {"origin": ORIGIN, "document_key": document_key},
        },
    )
    fascicoli.fascicolo.pagamenti[AUTOMATION_KEY]["proforme"][document_key] = proforma.id

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=MONTAGNESE_TEXT,
        document_metadata={"document_id": "DOC-MONTAGNESE", "filename": "Sentenza.pdf", "tipo_documento": "Sentenza Tribunale", "codice_fiscale_cliente": "MNTRRT98P65G791Q"},
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    updated_proforma = fatturazione.get(proforma.id)
    assert outcome.applied is True
    assert "spese_esborsi" in outcome.changes["payments"]
    assert "parcella" in outcome.changes["payments"]
    assert "contributo_unificato" not in fascicolo.pagamenti
    assert fascicolo.pagamenti["spese_esborsi"]["status"] == "da_registrare"
    assert fascicolo.pagamenti["spese_esborsi"]["data_pagamento"] == ""
    assert fascicolo.pagamenti["spese_esborsi"]["importo"] == 21.50
    assert fascicolo.pagamenti["spese_esborsi"]["natura"] == "spese_esborsi"
    assert fascicolo.pagamenti["spese_esborsi"]["label"] == "Spese/esborsi"
    react_payment = payment_summary_for_fascicolo(fascicolo)["items"]["spese_esborsi"]
    assert react_payment["label"] == "Spese/esborsi"
    assert react_payment["displayLabel"] == "Spese/esborsi"
    assert react_payment["natura"] == "spese_esborsi"
    assert fascicolo.pagamenti["parcella"]["importo"] == updated_proforma.totale
    assert any(
        voce.tipo == "ANTICIPO"
        and voce.prezzo_unitario == 21.50
        and "Spese ed esborsi" in voce.descrizione
        for voce in updated_proforma.voci
    )
    assert updated_proforma.dati_personalizzati["lex_sentenza"]["extraction"]["spese_esborsi_importo"] == 21.50


def test_fondo_spese_preesistente_conserva_natura_senza_doppio_totale():
    fascicolo = SimpleNamespace(
        id="FASC-LEGACY-FONDO",
        pagamenti={
            "fondo_spese": {
                "status": "pagato",
                "importo": 250.0,
                "label": "Fondo spese",
                "natura": "fondo_spese",
                "origine": "manuale",
            }
        },
    )

    summary = payment_summary_for_fascicolo(fascicolo)

    assert summary["totaleRegistrato"] == 250.0
    assert summary["items"]["spese_esborsi"]["label"] == "Spese/esborsi"
    assert summary["items"]["spese_esborsi"]["importo"] is None
    assert summary["items"]["fondo_spese"]["importo"] == 250.0
    assert summary["items"]["fondo_spese"]["status"] == "pagato"


def test_pagamento_fondo_spese_salva_la_voce_distinta():
    fascicoli = FakeFascicoliRepository()

    payload, status = update_react_fascicolo_payment(
        get_fascicoli=lambda: fascicoli,
        get_fatturazione=None,
        id_fasc="FASC-1",
        kind="fondo_spese",
        payload={"status": "pagato", "importo": "250,00", "dataPagamento": "2026-06-26"},
        actor="Avv. Test",
    )

    assert status == 200
    assert payload["payment"]["kind"] == "fondo_spese"
    assert payload["payment"]["label"] == "Fondo spese"
    assert payload["paymentSummary"]["totaleRegistrato"] == 250.0
    assert payload["paymentSummary"]["items"]["fondo_spese"]["importo"] == 250.0
    assert "spese_esborsi" not in fascicoli.fascicolo.pagamenti
    assert fascicoli.fascicolo.pagamenti["fondo_spese"]["importo"] == 250.0


def test_sentenza_strategica_senza_nome_cliente_non_aggiorna_economia(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    sentenza_vicenza_strategica = """
    Tribunale di Vicenza
    Sentenza n. 99/2024 pubbl. il 10/04/2024
    RG n. 1548/2023
    La presente pronuncia viene prodotta come precedente utile alla strategia difensiva.
    Il Tribunale liquidando la complessiva somma di € 2.500,00, oltre rimborso del contributo unificato.
    """

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=sentenza_vicenza_strategica,
        document_metadata={"document_id": "DOC-VICENZA", "filename": "Sentenza Tribunale Vicenza.pdf"},
        actor="Lex AI",
    )

    fascicolo = fascicoli.get("FASC-1")
    assert outcome.applied is False
    assert "cliente_non_presente_nella_sentenza" in outcome.warnings
    assert outcome.changes["context"]["cliente_match"] is False
    assert getattr(fascicolo.stato, "value", fascicolo.stato) == StatoFascicolo.IN_CORSO.value
    assert fascicolo.pagamenti == {}
    assert fatturazione.per_fascicolo("FASC-1") == []


def test_sentenza_con_cliente_ma_rg_diverso_non_aggiorna_economia(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    sentenza_altro_rg = """
    Tribunale di Palmi
    Sentenza n. 231/2024 pubbl. il 08/05/2024
    RG n. 9999/2023
    nel procedimento promosso da Spagnolo Sara contro Ministero dell'Istruzione e del Merito
    liquidando la complessiva somma di € 900,00, oltre ad € 49,00 per spese di c.u.
    """

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=sentenza_altro_rg,
        document_metadata={"document_id": "DOC-RG-DIVERSO", "filename": "sentenza-altro-rg.pdf"},
        actor="Lex AI",
    )

    assert outcome.applied is False
    assert "rg_sentenza_non_coincidente_con_fascicolo" in outcome.warnings
    assert outcome.changes["context"]["rg_match"] is False
    assert fascicoli.get("FASC-1").pagamenti == {}
    assert fatturazione.per_fascicolo("FASC-1") == []


def test_sentenza_con_rg_importato_a_zeri_iniziali_aggiorna_economia(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fascicoli.fascicolo.numero_rg = "00001548/2023"
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))

    outcome = apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata={"document_id": "DOC-RG-ZERI", "filename": "sentenza-rg-zeri.pdf"},
        actor="Lex AI",
    )

    assert outcome.applied is True
    assert "rg_sentenza_non_coincidente_con_fascicolo" not in outcome.warnings
    assert fascicoli.get("FASC-1").pagamenti["liquidazione_giudice"]["importo"] == 1100.00
    assert fatturazione.per_fascicolo("FASC-1") == []


def test_numerazione_configurata_e_conversione_proforma(tmp_path: Path):
    manager = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    numbering = manager.configura_numerazione(2024, 15, updated_by="admin")
    assert numbering["prossimoNumero"] == "2024/016"

    proforma = manager.crea(
        id_cliente="CLI-1",
        id_fascicolo="FASC-1",
        data_emissione="2024-05-07",
        voci=[VoceParcella(descrizione="Compenso", prezzo_unitario=100.0)],
        dati_personalizzati={"document": {"documento_operativo": "PROFORMA", "tipo_documento_label": "Proforma"}},
    )
    assert proforma.numero == "2024/016"
    assert manager.carica_numerazione(2024)["prossimoNumero"] == "2024/017"

    manager.cambia_stato(proforma.id, StatoParcella.EMESSA)
    converted = manager.get(proforma.id)
    assert converted.stato == StatoParcella.EMESSA
    assert converted.dati_personalizzati["document"]["documento_operativo"] == "FATTURA"
    assert converted.dati_personalizzati["document"]["tipo_documento_label"] == "Fattura"


def test_pagamento_parcella_fascicolo_marca_proforma_collegata_pagata(tmp_path: Path):
    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    proforma = fatturazione.crea(
        id_cliente="CLI-1",
        id_fascicolo="FASC-1",
        data_emissione="2024-05-07",
        voci=[VoceParcella(descrizione="Compenso", prezzo_unitario=100.0)],
        dati_personalizzati={"document": {"documento_operativo": "PROFORMA", "tipo_documento_label": "Proforma"}},
    )
    fascicoli.fascicolo.pagamenti = {
        "parcella": {
            "status": "da_emettere",
            "proforma_id": proforma.id,
            "proforma_number": proforma.numero,
            "origine": ORIGIN,
        }
    }

    result, status = update_react_fascicolo_payment(
        get_fascicoli=lambda: fascicoli,
        get_fatturazione=lambda: fatturazione,
        id_fasc="FASC-1",
        kind="parcella",
        payload={"status": "pagato", "dataPagamento": "2024-05-10", "metodo": "Bonifico bancario"},
        actor="Avv. Test",
    )

    updated = fatturazione.get(proforma.id)
    assert status == 200
    assert result["ok"] is True
    assert result["linkedProforma"]["ok"] is True
    assert updated.stato == StatoParcella.PAGATA
    assert updated.data_pagamento == "2024-05-10"
    assert updated.dati_personalizzati["document"]["documento_operativo"] == "FATTURA"
    assert fascicoli.fascicolo.pagamenti["parcella"]["proforma_id"] == proforma.id


def test_sentenza_gia_applicata_alimenta_vector_db_una_sola_volta(tmp_path: Path, monkeypatch):
    from web.services import document_intelligence_runtime as runtime

    fascicoli = FakeFascicoliRepository()
    fatturazione = GestioneFatturazione(str(tmp_path / "parcelle.json"))
    metadata = {"document_id": "DOC-1", "filename": "sentenza.pdf", "tipo_documento": "Sentenza Tribunale"}
    metadata.update(source_id="original", sha256="a"*64)
    fascicoli.fascicolo.documenti = [SimpleNamespace(id="original", nome="sentenza.pdf", hash_sha256="a"*64)]
    from pct.document_intelligence.models import DocumentAIRecord, DocumentAIText, DocumentAIVersion
    from pct.document_intelligence.repository import DocumentAIRepository
    document_repository = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db", storage_root=tmp_path / "blobs")
    document_repository.create_document_record(DocumentAIRecord(
        "DOC-1", "tenant-a", "FASC-1", "sentenza.pdf", "sentenza.pdf", "pdf", "application/pdf",
        100, "a"*64, "ready", "v1", 1, "controlled", "2026-10-08", "2026-10-08"))
    document_repository.create_version(DocumentAIVersion(
        "v1", "tenant-a", "FASC-1", "DOC-1", 1, "upload", "sentenza.pdf", None, None,
        "a"*64, "controlled", "2026-10-08"))
    document_repository.save_extracted_text(DocumentAIText(
        "DOC-1", "v1", "tenant-a", "FASC-1", SENTENZA_TEXT, [], "pdf-native", "2026-10-08"))
    monkeypatch.setattr(runtime, "build_document_ai_service", lambda: SimpleNamespace(repository=document_repository))
    apply_sentenza_tribunale_automation(
        fascicoli_repository=fascicoli,
        fatturazione_repository=fatturazione,
        fascicolo_id="FASC-1",
        text=SENTENZA_TEXT,
        document_metadata=metadata,
        actor="Lex AI",
    )

    class FakeLocalAI:
        def __init__(self):
            self.calls = 0

        def index_text_document(self, **kwargs):
            self.calls += 1
            assert kwargs["source_type"] == "fascicolo_documento"
            assert kwargs["source_id"] == "original"
            assert kwargs["metadata"]["document_ai_id"] == "DOC-1"
            assert kwargs["text"] == SENTENZA_TEXT.strip()
            return {"status": "indexed", "document_id": "rag-sentenza-1", "chunk_count": 2}

        def embed_all_pending_chunks(self, **kwargs):
            assert kwargs["document_id"] == "rag-sentenza-1"
            return {"status": "ready", "embedded": 2, "pending_remaining": 0}

    local_ai = FakeLocalAI()
    monkeypatch.setattr(runtime, "get_fascicoli", lambda: fascicoli)
    monkeypatch.setattr(runtime, "get_fatturazione", lambda: fatturazione)
    monkeypatch.setattr("lex.providers.local_ai_service.get_local_ai_service", lambda: local_ai)

    first = runtime.apply_sentenza_automation_for_document_text(
        fascicolo_id="FASC-1",
        tenant_id="tenant-a",
        document_id="DOC-1",
        text=SENTENZA_TEXT,
        metadata=metadata,
        actor="Lex AI",
    )
    second = runtime.apply_sentenza_automation_for_document_text(
        fascicolo_id="FASC-1",
        tenant_id="tenant-a",
        document_id="DOC-1",
        text=SENTENZA_TEXT,
        metadata=metadata,
        actor="Lex AI",
    )

    vector_key = "document_id:DOC-1"
    vector_state = fascicoli.fascicolo.pagamenti[AUTOMATION_KEY]["vector_indexes"][vector_key]
    assert first["applied"] is False
    assert first["vector_index"]["document_id"] == "rag-sentenza-1"
    assert second["applied"] is False
    assert second["vector_index"]["document_id"] == "rag-sentenza-1"
    assert vector_state["ok"] is True
    assert vector_state["schema_version"] == SENTENZA_VECTOR_SCHEMA_VERSION
    assert local_ai.calls == 1
    document_repository.set_current_version("tenant-a", "FASC-1", "DOC-1", "v2")
    assert not runtime._sentenza_vector_index_ok(fascicoli_repository=fascicoli,
        fascicolo_id="FASC-1", document_key=vector_key, metadata={**metadata, "tenant_id": "tenant-a"})


def test_fondo_importo_precedente_conserva_intera_citazione():
    from pct.fascicolo_sentenza_economica import _extract_fondo_spese

    text = "€ 250,00 a titolo di fondo spese. € 21,50 per esborsi."
    amount, quote, issues = _extract_fondo_spese(text)
    assert amount == 250.0
    assert "€ 250,00 a titolo di fondo spese" in quote
    assert issues == []


def test_sentenza_vector_runtime_usa_testo_originale_completo():
    from pct.rag_sql_document import index_sql_text

    long_text = SENTENZA_TEXT + (" motivazione istruttoria" * 2500)
    captured = []
    def index(**kwargs):
        captured.append(kwargs)
        return {"status": "indexed", "document_id": "rag"}
    result = index_sql_text(SimpleNamespace(index_text_document=index), tenant="tenant", fid="case",
        sid="original", title="sentenza.pdf", sha256="a"*64, backend="sqlite",
        record=SimpleNamespace(id="ai", tenant_id="tenant", fascicolo_id="case", status="ready",
                               sha256="a"*64, current_version_id="v1"),
        extracted=SimpleNamespace(document_id="ai", tenant_id="tenant", fascicolo_id="case", version_id="v1",
                                   text=long_text, extraction_engine="pdf-native", pages=[]))
    assert result["status"] == "indexed"
    assert captured[0]["text"] == long_text.strip()
    assert captured[0]["source_type"] == "fascicolo_documento"
@pytest.mark.parametrize("expected,declared,allowed", [
    ("RSSMRA80A01H501U", "RSSMRA80A01H501U", True),
    ("", "RSSMRA80A01H501U", False),
    ("DIFFERENTE_VALIDO", "RSSMRA80A01H501U", False),
    ("RSSMRA80A01H501U", "RSSMRA80A01H501O", False),
])
def test_sentenza_codice_fiscale_della_parte_deve_essere_valido_e_concordante(expected, declared, allowed):
    from types import SimpleNamespace
    from pct.fascicolo_sentenza_economica import validate_sentenza_fascicolo_context
    if expected == "DIFFERENTE_VALIDO":
        from pct.codice_fiscale import _checksum
        expected = "RSSMRA80A01F205" + _checksum("RSSMRA80A01F205")

    case = SimpleNamespace(id="CF-CONTROLLED", nome_cliente="Mario Rossi", numero_rg="98765", anno_rg=2026,
                           tribunale="Tribunale di Torino", codice_fiscale_cliente=expected)
    text = f"TRIBUNALE DI TORINO\nR.G. n. 98765/2026\nSentenza n. 99/2026 pubbl. il 12/10/2026\nMARIO ROSSI (C.F. {declared}), ricorrente\ncontro Alfa\nP.Q.M. condanna Alfa alle spese che liquida in euro 1.100,00."
    extraction = analyze_sentenza_tribunale_text(text, {"tipo_documento": "SENTENZA"})
    result = validate_sentenza_fascicolo_context(text=text, extraction=extraction, fascicolo=case,
                                                metadata={"codice_fiscale_cliente": expected})
    assert result.ok is allowed
    from pct.sentenza_economic_audit import build_identity_match
    assert build_identity_match(case, text).safe_to_attach is allowed
    from pct.archivio_letture.estrazione_importi import importi_dalla_sentenza
    facts = importi_dalla_sentenza(text, metadata={"fascicolo": case, "codice_fiscale_cliente": expected}, origine="nativo")
    if allowed:
        assert any(f.categoria == "importo" for f in facts)
    else:
        assert not any(f.categoria == "importo" for f in facts)
        assert any(f.campo == "importi_identita_non_verificata" for f in facts)
