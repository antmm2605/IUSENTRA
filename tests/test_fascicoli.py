"""Test per la gestione fascicoli e archivio."""

import pytest
from datetime import date, timedelta
from pathlib import Path

from pct.fascicoli import (
    GestioneFascicoli,
    Fascicolo,
    TipoFascicolo,
    StatoFascicolo,
    TipoDocumento,
    TipoAttivita,
    EsitoAttivita,
    AttivitaProcessuale,
    Documento,
    EsitoDepositoPCT,
    normalizza_stato_deposito_pct,
    stato_fascicolo_da_descrizione_portale,
    _normalizza_esito_controlli,
)


@pytest.fixture
def gf(tmp_path):
    return GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )


@pytest.fixture
def fascicolo_base(gf):
    return gf.nuovo(
        titolo="Rossi c/ Bianchi",
        tipo=TipoFascicolo.CIVILE,
        id_cliente="ABC123",
        nome_cliente="Mario Rossi",
        controparte="Luigi Bianchi",
        tribunale="Tribunale di Milano",
        numero_rg="1234",
        anno_rg=2024,
        avvocato_referente="Avv. Verdi",
    )


# ------------------------------------------------------------------ CRUD

def test_crea_fascicolo(fascicolo_base):
    f = fascicolo_base
    assert f.id is not None
    assert f.numero.startswith(str(date.today().year))
    assert f.titolo == "Rossi c/ Bianchi"
    assert f.stato == StatoFascicolo.APERTO
    assert f.rg_completo == "RG 1234/2024"


def test_numerazione_progressiva(gf):
    f1 = gf.nuovo(titolo="F1", tipo=TipoFascicolo.CIVILE)
    f2 = gf.nuovo(titolo="F2", tipo=TipoFascicolo.PENALE)
    anno = date.today().year
    assert f1.numero == f"{anno}/001"
    assert f2.numero == f"{anno}/002"


def test_titolo_vuoto_errore(gf):
    with pytest.raises(ValueError, match="obbligatorio"):
        gf.nuovo(titolo="  ", tipo=TipoFascicolo.CIVILE)


def test_aggiorna_fascicolo(gf, fascicolo_base):
    f = gf.aggiorna(fascicolo_base.id, giudice="Dott. Neri", sezione="I")
    assert f.giudice == "Dott. Neri"
    assert f.sezione == "I"


def test_aggiorna_flag_controlli_conformita(gf, fascicolo_base):
    gf.aggiorna(fascicolo_base.id, compliance_controls_enabled=False)
    ricaricato = gf.get(fascicolo_base.id)
    assert ricaricato.compliance_controls_enabled is False


def test_elimina_fascicolo(gf, fascicolo_base):
    gf.elimina(fascicolo_base.id)
    assert gf.get(fascicolo_base.id) is None


# ------------------------------------------------------------------ Stato

def test_cambia_stato(gf, fascicolo_base):
    f = gf.cambia_stato(fascicolo_base.id, StatoFascicolo.IN_CORSO, note="Prima udienza")
    assert f.stato == StatoFascicolo.IN_CORSO
    assert len(f.avanzamento) >= 1


def test_avanzamento_registrato(gf, fascicolo_base):
    gf.cambia_stato(fascicolo_base.id, StatoFascicolo.SOSPESO, note="Rinvio d'ufficio")
    f = gf.get(fascicolo_base.id)
    assert any("SOSPESO" in av.stato_nuovo for av in f.avanzamento)


def test_normalizza_stato_fascicolo_da_descrizione_portale():
    assert stato_fascicolo_da_descrizione_portale("PROCEDIMENTO DEFINITO") == StatoFascicolo.DEFINITO
    assert stato_fascicolo_da_descrizione_portale("pendente") == StatoFascicolo.IN_CORSO
    assert stato_fascicolo_da_descrizione_portale("RINVIATO") == StatoFascicolo.SOSPESO
    assert stato_fascicolo_da_descrizione_portale("ESTINTO") == StatoFascicolo.ARCHIVIATO


def test_definisci(gf, fascicolo_base):
    f = gf.definisci(fascicolo_base.id, esito_finale="FAVOREVOLE",
                     motivo="Sentenza di primo grado")
    assert f.stato == StatoFascicolo.DEFINITO
    assert f.data_chiusura != ""
    assert f.archivio is not None
    assert f.archivio.esito_finale == "FAVOREVOLE"


def test_archivia_crea_zip(gf, fascicolo_base):
    gf.definisci(fascicolo_base.id, esito_finale="FAVOREVOLE")
    f = gf.archivia(fascicolo_base.id, crea_zip=True)
    assert f.stato == StatoFascicolo.ARCHIVIATO
    assert f.archivio.percorso_zip != ""
    assert Path(f.archivio.percorso_zip).exists()
    assert f.archivio.hash_zip != ""


def test_archivia_senza_zip(gf, fascicolo_base):
    f = gf.archivia(fascicolo_base.id, crea_zip=False)
    assert f.stato == StatoFascicolo.ARCHIVIATO
    assert f.archivio.percorso_zip == ""


def test_ripristina_da_archivio(gf, fascicolo_base):
    gf.archivia(fascicolo_base.id, crea_zip=False)
    f = gf.ripristina_da_archivio(fascicolo_base.id)
    assert f.stato == StatoFascicolo.APERTO
    assert f.data_chiusura == ""


def test_archivia_due_volte_errore(gf, fascicolo_base):
    gf.archivia(fascicolo_base.id, crea_zip=False)
    with pytest.raises(ValueError):
        gf.archivia(fascicolo_base.id, crea_zip=False)


# ------------------------------------------------------------------ Documenti

def test_aggiungi_documento(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="atto.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        contenuto=b"%PDF-1.4 test content",
        note="Atto principale",
    )
    assert doc.id is not None
    assert doc.nome == "atto.pdf"
    assert doc.dimensione_bytes > 0
    assert doc.hash_sha256 != ""
    f = gf.get(fascicolo_base.id)
    assert len(f.documenti) == 1


def test_documento_salvato_su_disco(gf, fascicolo_base):
    gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="memoria.pdf",
        tipo=TipoDocumento.MEMORIA,
        contenuto=b"contenuto memoria",
    )
    f = gf.get(fascicolo_base.id)
    percorso = gf.percorso_documento(fascicolo_base.id, f.documenti[0].id)
    assert percorso.exists()
    assert percorso.read_bytes() == b"contenuto memoria"


def test_aggiungi_documento_con_tag(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="comparsa.pdf",
        tipo=TipoDocumento.COMPARSA,
        contenuto=b"comparsa di risposta",
        tags=["comparsa", "udienza", "comparsa"],
    )

    assert doc.tags == ["comparsa", "udienza", "comparsa"]
    fascicolo = gf.get(fascicolo_base.id)
    assert fascicolo.documenti[0].tags == ["comparsa", "udienza", "comparsa"]


def test_aggiorna_metadati_documento_normalizza_i_tag(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        nome_file="istanza.pdf",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        contenuto=b"istanza",
    )

    aggiornato = gf.aggiorna_documento_metadati(
        fascicolo_base.id,
        doc.id,
        note="Istanza aggiornata",
        data_documento="2026-04-18",
        tags=["istanza", "udienza", "Istanza", "", "udienza"],
    )

    assert aggiornato.note == "Istanza aggiornata"
    assert aggiornato.data_documento == "2026-04-18"
    assert aggiornato.tags == ["istanza", "udienza"]


def test_rimuovi_documento(gf, fascicolo_base):
    doc = gf.aggiungi_documento(
        fascicolo_base.id, "da_eliminare.pdf",
        TipoDocumento.ALTRO, b"contenuto"
    )
    percorso = gf.percorso_documento(fascicolo_base.id, doc.id)
    gf.rimuovi_documento(fascicolo_base.id, doc.id)
    assert not percorso.exists()
    f = gf.get(fascicolo_base.id)
    assert len(f.documenti) == 0


def test_documento_nomi_collisione(gf, fascicolo_base):
    """Nomi duplicati devono essere rinominati automaticamente."""
    gf.aggiungi_documento(fascicolo_base.id, "doc.pdf", TipoDocumento.ALTRO, b"v1")
    gf.aggiungi_documento(fascicolo_base.id, "doc.pdf", TipoDocumento.ALTRO, b"v2")
    f = gf.get(fascicolo_base.id)
    assert len(f.documenti) == 2
    nomi = [d.percorso.split("/")[-1] for d in f.documenti]
    assert len(set(nomi)) == 2  # nomi diversi


def test_zip_include_documenti(gf, fascicolo_base):
    gf.aggiungi_documento(
        fascicolo_base.id, "sentenza.pdf",
        TipoDocumento.SENTENZA, b"testo sentenza"
    )
    gf.definisci(fascicolo_base.id)
    f = gf.archivia(fascicolo_base.id, crea_zip=True)
    import zipfile
    with zipfile.ZipFile(f.archivio.percorso_zip, "r") as zf:
        nomi = zf.namelist()
    assert "fascicolo.json" in nomi
    assert "indice_documenti.json" in nomi
    assert any("sentenza.pdf" in n for n in nomi)


def test_registra_import_documenti_portale_collega_documenti_e_attivita(gf, fascicolo_base):
    doc1 = gf.aggiungi_documento(
        fascicolo_base.id,
        "sentenza.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
    )
    doc2 = gf.aggiungi_documento(
        fascicolo_base.id,
        "verbale.pdf",
        TipoDocumento.VERBALE,
        b"verbale",
    )

    esito = gf.registra_import_documenti_portale(
        id_fasc=fascicolo_base.id,
        fonte="PolisWeb / PST",
        documenti_ids=[doc1.id, doc2.id],
        tipo_atto="Acquisizione documenti PolisWeb",
        note="Fascicolo ufficiale acquisito dal portale",
        registrato_da="admin",
        pec_destinatario="tribunale.milano@giustiziapec.it",
        nome_atto_principale=doc1.nome,
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert esito.stato == "IMPORTATO_DA_PORTALE"
    assert len(fascicolo.depositi_pct) == 1
    assert fascicolo.depositi_pct[0].servizio_portale == "DocumentiFascicolo"
    assert fascicolo.documenti[0].id_deposito_pct == esito.id
    assert fascicolo.documenti[1].id_deposito_pct == esito.id
    assert any(
        att.tipo == TipoAttivita.CONSULTAZIONE and att.id_deposito_pct == esito.id
        for att in fascicolo.attivita
    )


def test_sincronizza_deposito_portale_riusa_lotto_generico_e_compila_metadati(gf, fascicolo_base):
    doc1 = gf.aggiungi_documento(
        fascicolo_base.id,
        "SentenzaDefinitiva_33581101.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
    )
    doc2 = gf.aggiungi_documento(
        fascicolo_base.id,
        "Relata_33581101.pdf",
        TipoDocumento.ALLEGATO,
        b"relata",
    )

    lotto = gf.registra_import_documenti_portale(
        id_fasc=fascicolo_base.id,
        fonte="PolisWeb / PST",
        documenti_ids=[doc1.id, doc2.id],
        tipo_atto="Documenti ufficiali PolisWeb",
        note="Lotto locale da catalogare",
        registrato_da="admin",
    )

    esito = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PST",
        id_deposito_esterno="DEP-PORTALE-001",
        tipo_atto="Sentenza definitiva",
        data_deposito="2026-01-08",
        mittente="cancelleria@tribunale.palmi.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "SentenzaDefinitiva_33581101.pdf",
                "tipo": "SentenzaDefinitiva",
                "data_deposito": "2026-01-08",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "DEP-PORTALE-001",
                "tipo_atto": "Sentenza definitiva",
            },
            {
                "id_documento": "DOC-002",
                "nome": "Relata_33581101.pdf",
                "tipo": "ALLEGATO",
                "data_deposito": "2026-01-08",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 8000,
                "disponibile": True,
                "id_deposito": "DEP-PORTALE-001",
                "tipo_atto": "Sentenza definitiva",
            },
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert fascicolo is not None
    assert len(fascicolo.depositi_pct) == 1
    assert esito.id == lotto.id
    assert fascicolo.depositi_pct[0].id_deposito_esterno == "DEP-PORTALE-001"
    assert len(fascicolo.depositi_pct[0].documenti_portale) == 2

    doc1_reload = next(item for item in fascicolo.documenti if item.id == doc1.id)
    doc2_reload = next(item for item in fascicolo.documenti if item.id == doc2.id)
    assert doc1_reload.id_deposito_pct == lotto.id
    assert doc1_reload.classificazione_portale == "SentenzaDefinitiva"
    assert doc1_reload.tipo_atto_portale == "Sentenza definitiva"
    assert doc1_reload.id_documento_portale == "DOC-001"
    assert doc2_reload.classificazione_portale == "ALLEGATO"
    assert doc2_reload.id_documento_portale == "DOC-002"


def test_normalizza_stato_deposito_pct_migra_legacy():
    assert normalizza_stato_deposito_pct("accettato") == "ACCETTATO_PEC"
    assert normalizza_stato_deposito_pct("RIFIUTATO") == "RIFIUTATO_CANCELLERIA"
    assert normalizza_stato_deposito_pct("importato_da_pst") == "IMPORTATO_DA_PST"


def test_normalizza_stato_deposito_pct_rifiuta_valori_non_validi():
    with pytest.raises(ValueError, match="Stato deposito non valido"):
        normalizza_stato_deposito_pct("CHIUSO")


def test_normalizza_esito_controlli_accetta_solo_valori_canonici():
    assert _normalizza_esito_controlli("warn") == "WARN"
    assert _normalizza_esito_controlli("") == ""
    with pytest.raises(ValueError, match="Esito controlli non valido"):
        _normalizza_esito_controlli("KO")


def test_aggiungi_esito_deposito_normalizza_controlli(gf, fascicolo_base):
    esito = gf.aggiungi_esito_deposito(
        fascicolo_base.id,
        tipo_atto="MEMORIA",
        pec_destinatario="tribunale.milano@giustiziapec.it",
        stato="accettato",
        esito_controlli="warn",
    )

    assert esito.stato == "ACCETTATO_PEC"
    assert esito.esito_controlli == "WARN"


def test_caricamento_fascicoli_migra_stati_legacy_su_disco(tmp_path):
    db_path = tmp_path / "fascicoli.json"
    raw = {
        "FASC1234": {
            "id": "FASC1234",
            "numero": "2026/001",
            "titolo": "Migrazione depositi legacy",
            "tipo": "CIVILE",
            "stato": "APERTO",
            "documenti": [],
            "attivita": [],
            "avanzamento": [],
            "depositi_pct": [
                {
                    "id": "DEP00001",
                    "timestamp": "2026-04-04T10:00:00",
                    "stato": "ACCETTATO",
                    "tipo_atto": "MEMORIA",
                    "pec_destinatario": "tribunale.milano@giustiziapec.it",
                    "esito_controlli": "warn",
                }
            ],
        }
    }
    db_path.write_text(__import__("json").dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    gf = GestioneFascicoli(
        db_path=str(db_path),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )

    fascicolo = gf.get("FASC1234")
    assert fascicolo is not None
    assert fascicolo.depositi_pct[0].stato == "ACCETTATO_PEC"
    assert fascicolo.depositi_pct[0].esito_controlli == "WARN"

    persisted = __import__("json").loads(db_path.read_text(encoding="utf-8"))
    assert persisted["FASC1234"]["depositi_pct"][0]["stato"] == "ACCETTATO_PEC"
    assert persisted["FASC1234"]["depositi_pct"][0]["esito_controlli"] == "WARN"


def test_collega_documenti_a_deposito_portale_aggancia_file_locali_al_deposito_ufficiale(gf, fascicolo_base):
    dep = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Sentenza",
        data_deposito="2026-03-29",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "sentenza definitiva.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 20480,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )
    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "sentenza definitiva.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
    )

    gf.collega_documenti_a_deposito_portale(
        fascicolo_base.id,
        dep.id,
        [doc.id],
        note="File ufficiale acquisito dal fascicolo locale",
        registrato_da="admin",
    )

    fascicolo = gf.get(fascicolo_base.id)
    deposito = fascicolo.depositi_pct[0]
    assert deposito.documenti_ids == [doc.id]
    assert deposito.servizio_portale == "DocumentiFascicolo"
    assert "File ufficiale acquisito dal fascicolo locale" in deposito.note
    assert fascicolo.documenti[0].id_deposito_pct == dep.id
    assert fascicolo.documenti[0].classificazione_portale == "PROVVEDIMENTO"
    assert fascicolo.documenti[0].tipo_atto_portale == "Sentenza"
    assert fascicolo.documenti[0].id_documento_portale == "DOC-001"
    assert fascicolo.documenti[0].mittente_portale == "cancelleria@tribunale.giustiziapec.it"
    assert fascicolo.documenti[0].fonte_documento == "PORTALE_TELEMATICO"
    assert not any(
        att.tipo == TipoAttivita.CONSULTAZIONE and att.id_deposito_pct == dep.id
        for att in fascicolo.attivita
    )


def test_sincronizza_deposito_portale_registra_metadati_e_attivita(gf, fascicolo_base):
    esito = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Memoria conclusionale",
        data_deposito="2026-03-29",
        mittente="avv.rossi@pec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "memoria_conclusionale.pdf.p7m",
                "tipo": "ATTO",
                "data_deposito": "2026-03-29",
                "mittente": "avv.rossi@pec.it",
                "dimensione_bytes": 20480,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Memoria conclusionale",
            },
            {
                "id_documento": "DOC-002",
                "nome": "nota_spese.pdf.p7m",
                "tipo": "ALLEGATO",
                "data_deposito": "2026-03-29",
                "mittente": "avv.rossi@pec.it",
                "dimensione_bytes": 8192,
                "disponibile": "true",
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Memoria conclusionale",
            },
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert esito.stato == "IMPORTATO_DA_PST"
    assert esito.id_deposito_esterno == "BUSTA-PST-001"
    assert esito.fonte_portale == "PolisWeb / PST"
    assert esito.servizio_portale == "DocumentiFascicolo"
    assert len(esito.documenti_portale) == 2
    assert esito.documenti_portale[1]["disponibile"] is True
    assert len(fascicolo.depositi_pct) == 1
    assert any(
        att.id_deposito_pct == esito.id and att.tipo == TipoAttivita.DEPOSITO_ATTI
        for att in fascicolo.attivita
    )


def test_sincronizza_deposito_portale_aggiorna_senza_duplicare(gf, fascicolo_base):
    gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Sentenza",
        data_deposito="2026-03-29",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "sentenza.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    esito_aggiornato = gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Sentenza definitiva",
        data_deposito="2026-03-30",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "sentenza.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza",
            },
            {
                "id_documento": "DOC-002",
                "nome": "dispositivo.pdf",
                "tipo": "ALLEGATO",
                "data_deposito": "2026-03-30",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 8000,
                "disponibile": False,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Sentenza definitiva",
            },
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    fascicolo = gf.get(fascicolo_base.id)
    assert len(fascicolo.depositi_pct) == 1
    assert esito_aggiornato.tipo_atto == "Sentenza definitiva"
    assert esito_aggiornato.servizio_portale == "DocumentiFascicolo"
    assert len(esito_aggiornato.documenti_portale) == 2
    assert esito_aggiornato.documenti_portale[0]["nome"] in {"dispositivo.pdf", "sentenza.pdf"}
    assert len([att for att in fascicolo.attivita if att.id_deposito_pct == esito_aggiornato.id]) == 1


def test_riconcilia_documenti_portale_allinea_nome_e_metadati(gf, fascicolo_base):
    gf.sincronizza_deposito_portale(
        fascicolo_base.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-002",
        tipo_atto="Verbale di udienza",
        data_deposito="2026-04-06",
        mittente="cancelleria@tribunale.palmi.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-VERB-01",
                "nome": "VerbaleUdienza_33393309.pdf.p7m",
                "tipo": "VERBALE",
                "data_deposito": "2026-04-06",
                "mittente": "cancelleria@tribunale.palmi.giustiziapec.it",
                "dimensione_bytes": 20480,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-002",
                "tipo_atto": "Verbale di udienza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    doc = gf.aggiungi_documento(
        fascicolo_base.id,
        "verbaleudienza_33393309.pdf.p7m",
        TipoDocumento.VERBALE,
        b"verbale firmato",
    )

    report = gf.riconcilia_documenti_portale(fascicolo_base.id)
    fascicolo = gf.get(fascicolo_base.id)
    aggiornato = next(item for item in fascicolo.documenti if item.id == doc.id)

    assert report["documenti_allineati"] == 1
    assert aggiornato.nome == "VerbaleUdienza_33393309.pdf.p7m"
    assert aggiornato.nome_originale == "verbaleudienza_33393309.pdf.p7m"
    assert aggiornato.nome_portale == "VerbaleUdienza_33393309.pdf.p7m"
    assert aggiornato.classificazione_portale == "VERBALE"
    assert aggiornato.tipo_atto_portale == "Verbale di udienza"
    assert aggiornato.id_documento_portale == "DOC-VERB-01"
    assert aggiornato.fonte_documento == "PORTALE_TELEMATICO"


# ------------------------------------------------------------------ Attività

def test_aggiungi_attivita(gf, fascicolo_base):
    att = gf.aggiungi_attivita(
        fascicolo_base.id,
        tipo=TipoAttivita.UDIENZA,
        data=(date.today() + timedelta(days=10)).isoformat(),
        titolo="Prima udienza di comparizione",
        luogo="Aula 3",
    )
    assert att.id is not None
    assert att.tipo == TipoAttivita.UDIENZA
    assert att.esito == EsitoAttivita.IN_ATTESA


def test_aggiungi_attivita_persistendo_contenuto_email(gf, fascicolo_base):
    att = gf.aggiungi_attivita(
        fascicolo_base.id,
        tipo=TipoAttivita.COMUNICAZIONE_CANCELLERIA,
        data=date.today().isoformat(),
        titolo="PEC: ACCETTAZIONE DEPOSITO",
        descrizione="Da: cancelleria@example.pec.it",
        email_mittente="cancelleria@example.pec.it",
        email_oggetto="ACCETTAZIONE DEPOSITO RG 1234/2024",
        email_uid_imap="999",
        email_testo="Corpo completo della PEC di cancelleria",
    )
    gf_reload = GestioneFascicoli(
        db_path=str(gf.db_path),
        documents_dir=str(gf.documents_dir),
        archive_dir=str(gf.archive_dir),
    )
    fascicolo = gf_reload.get(fascicolo_base.id)
    salvata = next(a for a in fascicolo.attivita if a.id == att.id)
    assert salvata.email_mittente == "cancelleria@example.pec.it"
    assert salvata.email_oggetto == "ACCETTAZIONE DEPOSITO RG 1234/2024"
    assert salvata.email_uid_imap == "999"
    assert salvata.email_testo == "Corpo completo della PEC di cancelleria"


def test_attivita_passa_in_corso(gf, fascicolo_base):
    """Aggiungere la prima attività porta il fascicolo IN_CORSO."""
    assert fascicolo_base.stato == StatoFascicolo.APERTO
    gf.aggiungi_attivita(
        fascicolo_base.id,
        TipoAttivita.CONSULTAZIONE,
        date.today().isoformat(),
        "Prima consultazione",
    )
    f = gf.get(fascicolo_base.id)
    assert f.stato == StatoFascicolo.IN_CORSO


def test_aggiorna_esito_attivita(gf, fascicolo_base):
    att = gf.aggiungi_attivita(
        fascicolo_base.id,
        TipoAttivita.UDIENZA,
        date.today().isoformat(),
        "Udienza",
    )
    aggiornata = gf.aggiorna_attivita(
        fascicolo_base.id, att.id,
        esito=EsitoAttivita.FAVOREVOLE,
        note="Sentenza a nostro favore",
    )
    assert aggiornata.esito == EsitoAttivita.FAVOREVOLE


def test_prossima_scadenza(gf, fascicolo_base):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_dieci = (date.today() + timedelta(days=10)).isoformat()
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         tra_dieci, "Udienza lontana")
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.TERMINE_SCADENZA,
                         domani, "Scadenza imminente")
    f = gf.get(fascicolo_base.id)
    sc = f.prossima_scadenza
    assert sc is not None
    assert sc.data == domani


def test_ultima_attivita(gf, fascicolo_base):
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         "2024-01-10", "Prima")
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         "2024-03-15", "Ultima")
    f = gf.get(fascicolo_base.id)
    assert f.ultima_attivita.titolo == "Ultima"


# ------------------------------------------------------------------ Query

def test_filtra_per_stato(gf, fascicolo_base):
    f2 = gf.nuovo(titolo="Altro", tipo=TipoFascicolo.PENALE)
    gf.cambia_stato(f2.id, StatoFascicolo.SOSPESO)
    aperti = gf.tutti(stato=StatoFascicolo.APERTO)
    assert all(f.stato == StatoFascicolo.APERTO for f in aperti)


def test_filtra_per_cliente(gf, fascicolo_base):
    gf.nuovo(titolo="Altro cliente", tipo=TipoFascicolo.CIVILE,
             id_cliente="ZZZ999", nome_cliente="Altro")
    f_cliente = gf.tutti(id_cliente="ABC123")
    assert all(f.id_cliente == "ABC123" for f in f_cliente)


def test_cerca_testo(gf, fascicolo_base):
    gf.nuovo(titolo="Verdi c/ Neri", tipo=TipoFascicolo.PENALE,
             controparte="Carlo Neri")
    risultati = gf.cerca(testo="bianchi")
    assert len(risultati) == 1
    assert "Bianchi" in risultati[0].controparte


def test_archivio_separato(gf, fascicolo_base):
    gf.archivia(fascicolo_base.id, crea_zip=False)
    attivi = gf.tutti()
    archiviati = gf.archivio()
    assert fascicolo_base.id not in [f.id for f in attivi]
    assert fascicolo_base.id in [f.id for f in archiviati]


def test_scadenze_imminenti(gf, fascicolo_base):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_30 = (date.today() + timedelta(days=30)).isoformat()
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.TERMINE_SCADENZA,
                         domani, "Scadenza vicina")
    gf.aggiungi_attivita(fascicolo_base.id, TipoAttivita.UDIENZA,
                         tra_30, "Udienza lontana")
    sc = gf.fascicoli_con_scadenze_imminenti(entro_giorni=7)
    assert len(sc) == 1


# ------------------------------------------------------------------ Persistenza

def test_persistenza(tmp_path):
    db = str(tmp_path / "f.json")
    docs = str(tmp_path / "docs")
    arch = str(tmp_path / "arch")
    gf1 = GestioneFascicoli(db_path=db, documents_dir=docs, archive_dir=arch)
    f = gf1.nuovo(titolo="Test persistenza", tipo=TipoFascicolo.CONSULENZA)
    gf1.aggiungi_documento(f.id, "test.txt", TipoDocumento.ALTRO, b"testo")
    gf2 = GestioneFascicoli(db_path=db, documents_dir=docs, archive_dir=arch)
    caricato = gf2.get(f.id)
    assert caricato is not None
    assert caricato.titolo == "Test persistenza"
    assert len(caricato.documenti) == 1


def test_statistiche(gf, fascicolo_base):
    f2 = gf.nuovo(titolo="F2", tipo=TipoFascicolo.PENALE)
    gf.archivia(f2.id, crea_zip=False)
    stats = gf.statistiche()
    assert stats["totale"] == 2
    assert stats["archiviati"] == 1
    assert stats["attivi"] >= 1


def test_fascicolo_serializza_metadati_sync_portale(gf, fascicolo_base):
    aggiornato = gf.aggiorna(
        fascicolo_base.id,
        source="PST",
        source_external_id="0800570094:1025:2024:CIVILE",
        last_sync_at="2026-04-06T10:45:00",
        sync_status="SINCRONIZZATO",
        import_log_id="PST-20260406104500-ABC123",
        has_conflicts=True,
        document_sync_enabled=True,
        events_sync_enabled=True,
    )

    data = aggiornato.to_dict()
    ripristinato = Fascicolo.from_dict(data)

    assert ripristinato.source == "PST"
    assert ripristinato.source_external_id == "0800570094:1025:2024:CIVILE"
    assert ripristinato.last_sync_at == "2026-04-06T10:45:00"
    assert ripristinato.sync_status == "SINCRONIZZATO"
    assert ripristinato.import_log_id == "PST-20260406104500-ABC123"
    assert ripristinato.has_conflicts is True
    assert ripristinato.document_sync_enabled is True
    assert ripristinato.events_sync_enabled is True
