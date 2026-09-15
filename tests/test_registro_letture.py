"""Il registro delle letture: che cosa è stato letto, che cosa no, che cosa è dubbio.

Un documento invariato non torna da leggere; un hash diverso rimette in coda
solo quel documento; una versione nuova del lettore rimette in coda tutto per
quel lettore soltanto; le anomalie sulle date restano aperte finché
l'avvocato non le conferma o corregge.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.registro_letture import Oggetto, RegistroLetture, RegistroLettureError, impronta_inventario
from pct.registro_letture.inventario import oggetti_da_fascicolo, oggetti_da_pec
from pct.registro_letture.repository import COLONNE, SCHEMA_POSTGRES, SCHEMA_SQLITE, TABELLE
from pct.registro_letture.verifica import applica_correzioni, verifica_lettura
from pct.registro_letture.verifica_date import (
    date_nel_testo,
    interpreta_data,
    normalizza_data_ocr,
    orizzonte_fascicolo,
    valuta_data,
)

T = "studio-prova"
OGGI = date(2026, 9, 15)


def _registro(tmp_path: Path) -> RegistroLetture:
    return RegistroLetture(tmp_path / "intelligence" / "registro_letture.db")


def _doc(identificativo: str, sha: str, nome: str = "atto.pdf") -> Oggetto:
    return Oggetto(tipo="documento", oggetto_id=identificativo, nome=nome, sha256=sha, sha256_archivio=f"enc-{sha}", dimensione=10, cliente="Anna Bianchi", numero_rg="777", anno_rg="2026")


def test_schema_sqlite_e_postgresql_hanno_lo_stesso_contratto():
    sqlite = SCHEMA_SQLITE.read_text(encoding="utf-8")
    postgres = SCHEMA_POSTGRES.read_text(encoding="utf-8")
    for tabella in TABELLE:
        assert f"CREATE TABLE IF NOT EXISTS {tabella} (" in sqlite
        assert f"CREATE TABLE IF NOT EXISTS {tabella} (" in postgres
        blocco_sqlite = sqlite[sqlite.index(f"CREATE TABLE IF NOT EXISTS {tabella} ("):]
        blocco_sqlite = blocco_sqlite[: blocco_sqlite.index(");")]
        blocco_postgres = postgres[postgres.index(f"CREATE TABLE IF NOT EXISTS {tabella} ("):]
        blocco_postgres = blocco_postgres[: blocco_postgres.index(");")]
        for colonna in COLONNE[tabella]:
            assert f"    {colonna} " in blocco_sqlite, (tabella, colonna)
            assert f"    {colonna} " in blocco_postgres, (tabella, colonna)
    for schema in (sqlite, postgres):
        assert "UNIQUE (tenant_id, tipo, oggetto_id, sha256, lettore)" in schema
        assert "stato IN ('letto', 'in_corso', 'errore', 'non_leggibile')" in schema
        assert "stato IN ('aperta', 'confermata', 'corretta', 'ignorata')" in schema


def test_inventario_nuovi_cambiati_invariati_rimossi(tmp_path: Path):
    registro = _registro(tmp_path)
    esito = registro.registra_inventario(T, "F1", [_doc("d1", "a" * 64), _doc("d2", "b" * 64)])
    assert esito == {"nuovi": 2, "cambiati": 0, "invariati": 0, "rimossi": 0, "ripristinati": 0}
    esito = registro.registra_inventario(T, "F1", [_doc("d1", "a" * 64), _doc("d2", "c" * 64), _doc("d3", "d" * 64)])
    assert esito["invariati"] == 1 and esito["cambiati"] == 1 and esito["nuovi"] == 1
    esito = registro.registra_inventario(T, "F1", [_doc("d1", "a" * 64)])
    assert esito["rimossi"] == 2
    presenti = registro.oggetti(T, "F1")
    assert [o.oggetto_id for o in presenti] == ["d1"]
    assert len(registro.oggetti(T, "F1", solo_presenti=False)) == 3
    # Un altro studio non vede nulla.
    assert registro.oggetti("altro", "F1") == []


def test_da_leggere_segue_hash_e_versione_del_lettore(tmp_path: Path):
    registro = _registro(tmp_path)
    d1, d2 = _doc("d1", "a" * 64), _doc("d2", "b" * 64)
    registro.registra_inventario(T, "F1", [d1, d2])
    assert [o.oggetto_id for o in registro.da_leggere(T, "F1", "ocr", versione="v1")] == ["d1", "d2"]
    registro.segna_letto(T, "F1", d1, "ocr", versione="v1", esito={"caratteri": 120})
    assert [o.oggetto_id for o in registro.da_leggere(T, "F1", "ocr", versione="v1")] == ["d2"]
    registro.segna_letto(T, "F1", d2, "ocr", versione="v1")
    assert registro.da_leggere(T, "F1", "ocr", versione="v1") == []
    # Il documento d1 cambia contenuto: solo lui torna da leggere.
    registro.registra_inventario(T, "F1", [_doc("d1", "e" * 64), d2])
    assert [o.oggetto_id for o in registro.da_leggere(T, "F1", "ocr", versione="v1")] == ["d1"]
    # Un altro lettore non ha letto nulla.
    assert len(registro.da_leggere(T, "F1", "catalogo", versione="c1")) == 2
    # Nuova versione del lettore OCR: tutto da rileggere, ma solo per l'OCR.
    registro.segna_letto(T, "F1", _doc("d1", "e" * 64), "ocr", versione="v1")
    assert registro.da_leggere(T, "F1", "ocr", versione="v1") == []
    assert len(registro.da_leggere(T, "F1", "ocr", versione="v2")) == 2
    # Un errore rimette in coda; «non leggibile» no.
    registro.segna_letto(T, "F1", d2, "ocr", versione="v1", stato="errore")
    assert [o.oggetto_id for o in registro.da_leggere(T, "F1", "ocr", versione="v1")] == ["d2"]
    registro.segna_letto(T, "F1", d2, "ocr", versione="v1", stato="non_leggibile")
    assert registro.da_leggere(T, "F1", "ocr", versione="v1") == []
    with pytest.raises(RegistroLettureError):
        registro.da_leggere(T, "F1", "lettore_inesistente")


def test_impronta_del_fascicolo_evita_di_rileggere(tmp_path: Path):
    registro = _registro(tmp_path)
    oggetti = [_doc("d1", "a" * 64), _doc("d2", "b" * 64)]
    registro.registra_inventario(T, "F1", oggetti)
    impronta = impronta_inventario(oggetti)
    assert registro.fascicolo_invariato(T, "F1", "indice_documentale", impronta, versione="x") is False
    registro.segna_fascicolo(T, "F1", "indice_documentale", impronta=impronta, oggetti_totali=2, oggetti_letti=2, versione="x")
    assert registro.fascicolo_invariato(T, "F1", "indice_documentale", impronta, versione="x") is True
    assert registro.fascicolo_invariato(T, "F1", "indice_documentale", impronta, versione="y") is False
    nuova = impronta_inventario(oggetti + [_doc("d3", "c" * 64)])
    assert nuova != impronta
    assert registro.fascicolo_invariato(T, "F1", "indice_documentale", nuova, versione="x") is False
    registro.segna_fascicolo(T, "F1", "indice_documentale", impronta=impronta, oggetti_totali=2, oggetti_letti=1, stato="parziale", versione="x")
    assert registro.fascicolo_invariato(T, "F1", "indice_documentale", impronta, versione="x") is False


def test_stato_fascicolo_per_lettore_e_per_oggetto(tmp_path: Path):
    registro = _registro(tmp_path)
    d1, d2 = _doc("d1", "a" * 64, "citazione.pdf"), _doc("d2", "b" * 64, "procura.pdf")
    registro.registra_inventario(T, "F1", [d1, d2])
    registro.segna_letto(T, "F1", d1, "ocr")  # versione corrente del lettore
    registro.segna_letto(T, "F1", d1, "catalogo", versione="superata")
    stato = registro.stato_fascicolo(T, "F1", lettori=["ocr", "catalogo"])
    per_lettore = {voce.lettore: voce for voce in stato.lettori}
    assert per_lettore["ocr"].letti == 1 and per_lettore["ocr"].da_leggere == 1 and per_lettore["ocr"].completa is False
    assert per_lettore["ocr"].etichetta == "Testo e ricerca" and per_lettore["ocr"].ultima_lettura
    assert stato.tutto_letto is False and stato.oggetti == 2
    per_oggetto = {voce["oggetto_id"]: voce["letture"] for voce in stato.per_oggetto}
    assert per_oggetto["d1"]["ocr"] == "letto" and per_oggetto["d2"]["ocr"] == "da_leggere"
    # Versione del catalogo cambiata: «da rileggere», non «letto», e solo per quel lettore.
    assert per_oggetto["d1"]["catalogo"] == "da_rileggere" and per_lettore["catalogo"].da_leggere == 2
    registro.segna_letto(T, "F1", d2, "ocr")
    assert registro.stato_fascicolo(T, "F1", lettori=["ocr"]).tutto_letto is True


def test_novita_dall_ultima_apertura_dell_utente(tmp_path: Path):
    registro = _registro(tmp_path)
    registro.registra_inventario(T, "F1", [_doc("d1", "a" * 64)])
    prima = registro.novita_e_segna_visto(T, "F1", "avv")
    assert prima["prima_vista"] is True and prima["nuovi"] == []
    registro.registra_inventario(T, "F1", [_doc("d1", "z" * 64), _doc("d2", "b" * 64)])
    poi = registro.novita_e_segna_visto(T, "F1", "avv")
    assert [v["oggetto_id"] for v in poi["nuovi"]] == ["d2"]
    assert [v["oggetto_id"] for v in poi["cambiati"]] == ["d1"]
    assert poi["visto_il"]
    # Un altro utente parte da zero; l'utente che ha visto non ha più novità.
    assert registro.novita_e_segna_visto(T, "F1", "collega")["prima_vista"] is True
    assert registro.novita_e_segna_visto(T, "F1", "avv")["nuovi"] == []
    registro.registra_inventario(T, "F1", [_doc("d2", "b" * 64)])
    assert registro.novita_e_segna_visto(T, "F1", "avv")["rimossi"] == [{"tipo": "documento", "oggetto_id": "d1"}]


def test_anomalie_si_registrano_una_volta_e_si_risolvono(tmp_path: Path):
    registro = _registro(tmp_path)
    d1 = _doc("d1", "a" * 64)
    registro.registra_inventario(T, "F1", [d1])
    anomalia = {"campo": "udienza", "valore_letto": "1O/O3/2O26", "valore_proposto": "10/03/2026", "motivo": "Lettere nella data.", "codice": "corretta_da_ocr", "gravita": "bassa", "contesto": "udienza del 1O/O3/2O26"}
    prime = registro.registra_anomalie(T, "F1", d1, "ocr", [anomalia, anomalia])
    assert len(prime) == 2 and prime[0].id == prime[1].id
    assert len(registro.anomalie(T, "F1", stato="aperta")) == 1
    risolta = registro.risolvi_anomalia(T, prime[0].id, esito="corretta", utente_id="avv", valore="10/03/2026")
    assert risolta.stato == "corretta" and risolta.valore_confermato == "10/03/2026" and risolta.risolta_da == "avv"
    assert registro.anomalie(T, "F1", stato="aperta") == []
    assert registro.correzioni(T, "F1") == {("d1", "udienza", "1O/O3/2O26"): "10/03/2026"}
    with pytest.raises(RegistroLettureError):
        registro.risolvi_anomalia(T, prime[0].id, esito="corretta", utente_id="avv", valore="")
    with pytest.raises(RegistroLettureError):
        registro.risolvi_anomalia("altro-studio", prime[0].id, esito="ignorata", utente_id="avv")
    assert registro.statistiche()["letture_anomalie"] == 1


def test_impronta_del_contenuto_si_impara_una_volta(tmp_path: Path):
    registro = _registro(tmp_path)
    registro.registra_inventario(T, "F1", [Oggetto(tipo="documento", oggetto_id="d1", nome="x.pdf", sha256="", sha256_archivio="e" * 64)])
    assert registro.impronta_contenuto(T, "documento", "e" * 64) == ""
    registro.registra_impronta_contenuto(T, "F1", "documento", "d1", sha256="f" * 64, sha256_archivio="e" * 64, dimensione=99)
    assert registro.impronta_contenuto(T, "documento", "e" * 64) == "f" * 64
    assert registro.oggetti(T, "F1")[0].dimensione == 99


def test_inventario_dal_fascicolo_e_dalle_pec():
    documento = SimpleNamespace(id="d1", nome="atto.pdf", tipo=SimpleNamespace(value="ATTO"), hash_sha256="a" * 64, hash_contenuto_sha256="b" * 64, dimensione_bytes=12, fonte_documento="PORTALE_TELEMATICO", data_documento="2026-03-10", eliminato_il="")
    cestinato = SimpleNamespace(id="d2", nome="vecchio.pdf", tipo="ALTRO", hash_sha256="c" * 64, hash_contenuto_sha256="c" * 64, dimensione_bytes=1, eliminato_il="2026-01-01")
    fascicolo = SimpleNamespace(id="F1", nome_cliente="Anna Bianchi", numero_rg="777", anno_rg=2026, documenti=[documento, cestinato])
    oggetti = oggetti_da_fascicolo(fascicolo, cifratura_attiva=True)
    assert len(oggetti) == 1
    assert oggetti[0].sha256 == "b" * 64 and oggetti[0].sha256_archivio == "a" * 64
    assert oggetti[0].cliente == "Anna Bianchi" and oggetti[0].numero_rg == "777" and oggetti[0].anno_rg == "2026"
    assert oggetti[0].origine == "PORTALE_TELEMATICO" and oggetti[0].data_oggetto == "2026-03-10"
    # Cifratura attiva e impronte uguali: il contenuto in chiaro non è noto.
    uguale = SimpleNamespace(id="d3", nome="x.pdf", tipo="ALTRO", hash_sha256="c" * 64, hash_contenuto_sha256="c" * 64, dimensione_bytes=5)
    assert oggetti_da_fascicolo(SimpleNamespace(id="F1", documenti=[uguale]), cifratura_attiva=True)[0].sha256 == ""
    assert oggetti_da_fascicolo(SimpleNamespace(id="F1", documenti=[uguale]), cifratura_attiva=False)[0].sha256 == "c" * 64
    pec = oggetti_da_pec([
        {"id": "M1", "mime_sha256": "d" * 64, "mime_size": 4000, "received_at": "2026-09-01T09:00:00", "metadata_json": '{"headers": {"subject": "Udienza", "from": "trib@giustiziacert.it"}}',
         "allegati": [{"id": "A1", "attachment_index": 0, "filename": "decreto.pdf", "sha256": "e" * 64, "size_bytes": 300}]},
    ], fascicolo)
    assert [o.tipo for o in pec] == ["pec", "allegato_pec"]
    assert pec[0].nome == "Udienza" and pec[0].origine == "trib@giustiziacert.it" and pec[0].sha256 == "d" * 64
    assert pec[1].oggetto_id == "A1" and pec[1].origine == "M1" and pec[1].numero_rg == "777"


def test_date_ocr_si_normalizzano_solo_dentro_i_token_a_forma_di_data():
    assert normalizza_data_ocr("udienza del 1O/O3/2O26 alle ore 9.30, art. lO, 3l.l2.2O25") == "udienza del 10/03/2026 alle ore 9.30, art. lO, 31.12.2025"
    assert normalizza_data_ocr("2O26-O3-1O") == "2026-03-10"
    assert normalizza_data_ocr("SOS/OS/OO") == "SOS/OS/OO"  # nessuna cifra: non è una data
    assert interpreta_data("10/03/26") == date(2026, 3, 10)
    assert interpreta_data("12 marzo 2026") == date(2026, 3, 12)
    assert interpreta_data("2026-03-12T10:00:00") == date(2026, 3, 12)
    assert interpreta_data("31/02/2026") is None
    assert date_nel_testo("il 1O/O3/2O26 e il 12 marzo 2026; art. 10/2020 no") == ["1O/O3/2O26", "12 marzo 2026"]
    # Quello che non diventa una data vera non e' una data: niente anomalie inutili per l'avvocato.
    assert date_nel_testo("IS/OB/ZOZS, SOS/OS/OO, l/S/BZ, prot. 12/3/26, vers. 1.2.34, 3O/O2/2O26") == []


def test_giudizio_sulle_date_lette():
    assert valuta_data("10/03/2026", oggi=OGGI).stato == "valida"
    ocr = valuta_data("1O/O3/2O26", oggi=OGGI)
    assert ocr.stato == "sospetta" and ocr.codici == ["corretta_da_ocr"] and ocr.valore_proposto == "10/03/2026" and ocr.gravita == "bassa"
    inesistente = valuta_data("31/02/2026", oggi=OGGI)
    assert inesistente.stato == "non_valida" and inesistente.codici == ["giorno_inesistente"] and inesistente.gravita == "alta"
    invertita = valuta_data("12/25/2026", oggi=OGGI)
    assert invertita.stato == "non_valida" and invertita.codici == ["giorno_mese_invertiti"] and invertita.valore_proposto == "25/12/2026"  # noqa: E501
    futura = valuta_data("10/03/2031", oggi=OGGI)
    assert futura.stato == "sospetta" and "anno_futuro" in futura.codici and futura.gravita == "alta"
    remota = valuta_data("10/03/2019", oggi=OGGI, anno_riferimento=2026, data_minima=date(2026, 1, 1))
    assert remota.codici == ["anno_remoto", "prima_del_fascicolo"] and remota.gravita == "media"
    # Coerenza con un'altra fonte: la PEC è arrivata il 5 marzo, il testo dice 03/05.
    invertita = valuta_data("03/05/2026", oggi=OGGI, data_confronto=date(2026, 3, 5), etichetta_confronto="la data di ricezione della PEC")
    assert invertita.codici == ["giorno_mese_invertiti"] and invertita.valore_proposto == "05/03/2026" and invertita.gravita == "alta"
    diversa = valuta_data("20/03/2026", oggi=OGGI, data_confronto=date(2026, 3, 5), etichetta_confronto="la data di deposito del portale")
    assert diversa.codici == ["incoerente_con_fonte"] and "15 giorni" in diversa.motivi[0]
    assert valuta_data("06/03/2026", oggi=OGGI, data_confronto=date(2026, 3, 5), tolleranza_giorni=1).stato == "valida"


def test_verifica_lettura_produce_anomalie_da_registrare_e_le_correzioni_si_applicano():
    fascicolo = SimpleNamespace(anno_rg=2026, data_apertura="2026-02-01")
    contesto = orizzonte_fascicolo(fascicolo, oggi=OGGI)
    assert contesto["anno_riferimento"] == 2026 and contesto["data_minima"] == date(2025, 2, 1)
    esito = {
        "date_processuali": [
            {"date": "2026-03-10", "raw_date": "1O/O3/2O26", "label": "udienza", "context": "udienza del 1O/O3/2O26"},
            {"date": "2024-03-10", "raw_date": "10/03/2024", "label": "termine", "context": "termine del 10/03/2024"},
            {"date": "2026-04-10", "raw_date": "10/04/2026", "label": "udienza", "context": "ok"},
        ],
        "date": ["31/02/2026", "10/04/2026"],
    }
    anomalie = verifica_lettura(esito, contesto)
    assert [a["codice"] for a in anomalie] == ["corretta_da_ocr", "prima_del_fascicolo", "giorno_inesistente"]
    assert anomalie[0]["campo"] == "udienza" and anomalie[0]["valore_proposto"] == "10/03/2026"
    assert anomalie[1]["gravita"] == "media" and anomalie[2]["gravita"] == "alta"
    # La data generica nel testo non è processuale: niente controllo «prima del fascicolo».
    assert all(a["valore_letto"] != "10/04/2026" for a in anomalie)
    corrette = applica_correzioni(esito["date_processuali"], {("d1", "udienza", "1O/O3/2O26"): "11/03/2026"}, oggetto_id="d1")
    assert corrette[0]["date"] == "2026-03-11" and corrette[0]["valore_corretto"] == "11/03/2026"
    assert "valore_corretto" not in corrette[1]
