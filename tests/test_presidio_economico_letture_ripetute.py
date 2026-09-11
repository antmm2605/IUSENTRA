"""Il presidio economico deve smettere di leggere quando ha letto tutto.

Sul server di produzione il presidio girava ogni quindici minuti e rileggeva
ogni volta gli stessi documenti: un core pieno di CPU e raffiche di lettura da
disco fino a 300 MB/s, con l'applicazione che smetteva di rispondere al
controllo di salute e il proxy che restituiva 503.

La causa non era il volume dei documenti ma il modo di riconoscerli: nella
impronta dell'analisi entrava `data_caricamento`, che per i documenti
indicizzati e' l'`updated_at` del servizio Document AI e cambia a ogni
reindicizzazione anche quando il PDF e' identico. Il presidio vedeva quindi
"nuovo" un documento gia' letto, e ricominciava da capo per sempre.

Qui ci sono i due contratti che tengono chiuso il problema: l'impronta cambia
solo quando cambia il contenuto, e il fascicolo conserva l'elenco dei documenti
davvero letti, che e' la condizione di arresto del giro successivo.
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.presidio_documentale_state import (
    READ_DOCUMENTS_KEY,
    READ_DOCUMENTS_VERSION_KEY,
    merge_read_inventory,
    read_document_entry,
    read_inventory,
    unread_document_ids,
)
from web.services import react_fascicoli_bridge

VERSIONE = react_fascicoli_bridge.ECONOMIC_DOCUMENT_ANALYSIS_VERSION


def _documento_indicizzato(*, document_id: str, sha256: str, aggiornato_il: str, size: int = 1024):
    """Un documento come lo costruisce il bridge dai record Document AI."""

    return SimpleNamespace(
        id=document_id,
        document_id=document_id,
        documento_id=document_id,
        nome=f"{document_id}.pdf",
        nome_originale=f"{document_id}.pdf",
        tipo="ALLEGATO",
        hash_sha256=sha256,
        hash_contenuto_sha256=sha256,
        dimensione_bytes=size,
        #  E' questo il campo che si muoveva da solo: e' l'updated_at del
        #  servizio di indicizzazione, non una data del documento.
        data_caricamento=aggiornato_il,
        data_documento=aggiornato_il,
        id_documento_portale="",
        _iusentra_document_ai_server=True,
    )


def _fascicolo(documenti, *, fid: str = "F1", pagamenti: dict | None = None):
    return SimpleNamespace(id=fid, documenti=list(documenti), pagamenti=dict(pagamenti or {}))


#  ---------------------------------------------------------------------------
#  Impronta: cambia con il contenuto, non con l'orologio dell'indicizzazione
#  ---------------------------------------------------------------------------


def test_la_reindicizzazione_non_fa_sembrare_nuovo_un_documento_immutato():
    """Il caso reale: stesso PDF, updated_at diverso."""

    prima = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z")
    ])
    dopo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T15:34:00Z")
    ])

    assert react_fascicoli_bridge._document_analysis_fingerprint(prima) == (
        react_fascicoli_bridge._document_analysis_fingerprint(dopo)
    )


def test_un_documento_sostituito_cambia_l_impronta():
    """La stabilita' non deve diventare cecita': altro contenuto, altra impronta."""

    prima = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z")
    ])
    dopo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="def456", aggiornato_il="2026-09-11T09:00:00Z")
    ])

    assert react_fascicoli_bridge._document_analysis_fingerprint(prima) != (
        react_fascicoli_bridge._document_analysis_fingerprint(dopo)
    )


def test_un_documento_nuovo_cambia_l_impronta():
    prima = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z")
    ])
    dopo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z"),
        _documento_indicizzato(document_id="D2", sha256="zzz999", aggiornato_il="2026-09-11T09:05:00Z"),
    ])

    assert react_fascicoli_bridge._document_analysis_fingerprint(prima) != (
        react_fascicoli_bridge._document_analysis_fingerprint(dopo)
    )


def test_senza_hash_la_data_resta_un_segnale_di_sostituzione():
    """Dove non c'e' l'hash, la data e' l'unico indizio che il file e' cambiato."""

    def documento_locale(caricato_il: str):
        return SimpleNamespace(
            id="D1",
            nome="ricorso.pdf",
            nome_originale="ricorso.pdf",
            tipo="ATTO_GIUDIZIARIO",
            hash_sha256="",
            dimensione_bytes=2048,
            data_caricamento=caricato_il,
            id_documento_portale="",
        )

    prima = _fascicolo([documento_locale("2026-09-01T10:00:00Z")])
    dopo = _fascicolo([documento_locale("2026-09-11T10:00:00Z")])

    assert react_fascicoli_bridge._document_analysis_fingerprint(prima) != (
        react_fascicoli_bridge._document_analysis_fingerprint(dopo)
    )


#  ---------------------------------------------------------------------------
#  Inventario delle letture: la condizione di arresto
#  ---------------------------------------------------------------------------


def test_un_documento_gia_letto_e_immutato_non_torna_fra_quelli_da_leggere():
    fascicolo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z")
    ])
    marker = {
        READ_DOCUMENTS_VERSION_KEY: VERSIONE,
        READ_DOCUMENTS_KEY: [
            read_document_entry(document_id="D1", sha256="abc123", size=1024, source="document_ai", chars=4200)
        ],
    }

    assert react_fascicoli_bridge._presidio_documenti_da_leggere(fascicolo, marker) == []


def test_la_reindicizzazione_non_rimette_in_coda_un_documento_gia_letto():
    """Il cuore del problema: stesso contenuto, timestamp nuovo."""

    fascicolo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T15:34:00Z")
    ])
    marker = {
        READ_DOCUMENTS_VERSION_KEY: VERSIONE,
        READ_DOCUMENTS_KEY: [
            read_document_entry(document_id="D1", sha256="abc123", size=1024, source="document_ai", chars=4200)
        ],
    }

    assert react_fascicoli_bridge._presidio_documenti_da_leggere(fascicolo, marker) == []


def test_un_documento_mai_letto_resta_da_leggere():
    """Un documento presente ma mai aperto non deve essere dato per letto."""

    fascicolo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z"),
        _documento_indicizzato(document_id="D2", sha256="zzz999", aggiornato_il="2026-09-11T09:05:00Z"),
    ])
    marker = {
        READ_DOCUMENTS_VERSION_KEY: VERSIONE,
        READ_DOCUMENTS_KEY: [
            read_document_entry(document_id="D1", sha256="abc123", size=1024, source="document_ai", chars=4200)
        ],
    }

    assert react_fascicoli_bridge._presidio_documenti_da_leggere(fascicolo, marker) == ["D2"]


def test_un_documento_cambiato_torna_da_leggere():
    fascicolo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="nuovo-contenuto", aggiornato_il="2026-09-11T09:00:00Z")
    ])
    marker = {
        READ_DOCUMENTS_VERSION_KEY: VERSIONE,
        READ_DOCUMENTS_KEY: [
            read_document_entry(document_id="D1", sha256="abc123", size=1024, source="document_ai", chars=4200)
        ],
    }

    assert react_fascicoli_bridge._presidio_documenti_da_leggere(fascicolo, marker) == ["D1"]


def test_cambiando_le_regole_di_lettura_tutto_torna_da_leggere():
    """Una nuova versione del lettore puo' trovare cose che prima sfuggivano."""

    fascicolo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z")
    ])
    marker = {
        READ_DOCUMENTS_VERSION_KEY: "versione-precedente-del-lettore",
        READ_DOCUMENTS_KEY: [
            read_document_entry(document_id="D1", sha256="abc123", size=1024, source="document_ai", chars=4200)
        ],
    }

    assert react_fascicoli_bridge._presidio_documenti_da_leggere(fascicolo, marker) == ["D1"]


def test_un_fascicolo_senza_inventario_va_letto_tutto():
    """I fascicoli gia' presenti in produzione non hanno ancora l'inventario."""

    fascicolo = _fascicolo([
        _documento_indicizzato(document_id="D1", sha256="abc123", aggiornato_il="2026-09-11T09:00:00Z"),
        _documento_indicizzato(document_id="D2", sha256="zzz999", aggiornato_il="2026-09-11T09:05:00Z"),
    ])

    assert react_fascicoli_bridge._presidio_documenti_da_leggere(fascicolo, {}) == ["D1", "D2"]


#  ---------------------------------------------------------------------------
#  Helper puri dell'inventario
#  ---------------------------------------------------------------------------


def test_l_inventario_non_conserva_il_testo_dei_documenti():
    """Il marcatore vive dentro i pagamenti del fascicolo: deve restare leggero."""

    riga = read_document_entry(
        document_id="D1",
        nome="sentenza.pdf",
        sha256="abc123",
        size=2048,
        source="document_ai",
        chars=18000,
    )

    assert set(riga) == {"id", "nome", "sha256", "size", "source", "chars"}
    assert riga["chars"] == 18000


def test_una_nuova_lettura_sostituisce_quella_vecchia_sullo_stesso_documento():
    marker = {
        READ_DOCUMENTS_VERSION_KEY: VERSIONE,
        READ_DOCUMENTS_KEY: [read_document_entry(document_id="D1", sha256="vecchio", size=10, source="metadati")],
    }

    righe = merge_read_inventory(
        marker,
        [read_document_entry(document_id="D1", sha256="nuovo", size=20, source="document_ai", chars=900)],
        analysis_version=VERSIONE,
    )

    assert righe == [
        {"id": "D1", "nome": "", "sha256": "nuovo", "size": 20, "source": "document_ai", "chars": 900}
    ]


def test_i_documenti_spariti_escono_dall_inventario():
    """Senza potatura l'elenco crescerebbe a ogni documento eliminato."""

    marker = {
        READ_DOCUMENTS_VERSION_KEY: VERSIONE,
        READ_DOCUMENTS_KEY: [
            read_document_entry(document_id="D1", sha256="a", size=1),
            read_document_entry(document_id="D2", sha256="b", size=2),
        ],
    }

    righe = merge_read_inventory(marker, [], analysis_version=VERSIONE, known_document_ids=["D2"])

    assert [riga["id"] for riga in righe] == ["D2"]


def test_l_inventario_non_supera_il_limite():
    righe = merge_read_inventory(
        {},
        [read_document_entry(document_id=f"D{indice}", sha256=f"h{indice}", size=indice) for indice in range(50)],
        analysis_version=VERSIONE,
        limit=10,
    )

    assert len(righe) == 10


def test_senza_hash_l_identita_di_lettura_usa_la_dimensione():
    marker = {
        READ_DOCUMENTS_VERSION_KEY: VERSIONE,
        READ_DOCUMENTS_KEY: [read_document_entry(document_id="D1", sha256="", size=4096)],
    }

    assert unread_document_ids([{"id": "D1", "sha256": "", "size": 4096}], marker, analysis_version=VERSIONE) == []
    assert unread_document_ids([{"id": "D1", "sha256": "", "size": 8192}], marker, analysis_version=VERSIONE) == ["D1"]


def test_l_inventario_di_una_versione_diversa_non_viene_letto():
    marker = {
        READ_DOCUMENTS_VERSION_KEY: "altra-versione",
        READ_DOCUMENTS_KEY: [read_document_entry(document_id="D1", sha256="abc", size=1)],
    }

    assert read_inventory(marker, analysis_version=VERSIONE) == {}
