"""Lo stato reale del fascicolo: transizioni automatiche solo con una prova, mai verso o dall'archivio."""

from __future__ import annotations

from pct.fascicoli import EsitoDepositoPCT, GestioneFascicoli, StatoFascicolo, TipoFascicolo
from pct.stato_fascicolo import (
    ammessa,
    applica,
    prova_deposito_accettato,
    prova_iscrizione_a_ruolo,
    prova_registro,
    prova_sentenza,
)


def _gestore(tmp_path) -> GestioneFascicoli:
    return GestioneFascicoli(db_path=str(tmp_path / "fascicoli.json"), documents_dir=str(tmp_path / "doc"), archive_dir=str(tmp_path / "arch"))


def test_le_prove_vanno_solo_avanti_il_registro_fa_fede():
    assert ammessa(StatoFascicolo.APERTO, prova_iscrizione_a_ruolo("12", "2026"))
    assert not ammessa(StatoFascicolo.DEFINITO, prova_iscrizione_a_ruolo("12", "2026"))
    assert ammessa(StatoFascicolo.IN_CORSO, prova_sentenza())
    assert ammessa(StatoFascicolo.IN_CORSO, prova_registro(StatoFascicolo.SOSPESO, "Sospeso"))
    assert ammessa(StatoFascicolo.DEFINITO, prova_registro(StatoFascicolo.IN_CORSO, "Riassunta"))
    assert not ammessa(StatoFascicolo.ARCHIVIATO, prova_registro(StatoFascicolo.IN_CORSO, "Pendente"))
    assert not ammessa(StatoFascicolo.DEFINITO, prova_registro(StatoFascicolo.ARCHIVIATO, "Archiviato"))


def test_deposito_accettato_porta_in_corso_con_la_prova_nell_avanzamento(tmp_path):
    gestore = _gestore(tmp_path)
    fascicolo = gestore.nuovo(titolo="Rosa c/ Viola", tipo=TipoFascicolo.CIVILE, nome_cliente="Anna Rosa")
    assert fascicolo.stato == StatoFascicolo.APERTO
    fascicolo.depositi_pct.append(EsitoDepositoPCT(id="dep1", pec_destinatario="tribunale.alfa@civile.ptel.giustiziacert.it", stato="ACCETTATO_CANCELLERIA", tipo_atto="Atto di citazione", timestamp="2026-09-20T10:00:00"))
    gestore._salva()
    ricaricato = _gestore(tmp_path).get(fascicolo.id)
    assert ricaricato.stato == StatoFascicolo.IN_CORSO
    ultimo = ricaricato.avanzamento[-1]
    assert ultimo.stato_nuovo == "IN_CORSO" and "cancelleria" in ultimo.note


def test_la_sentenza_definisce_ma_non_tocca_un_fascicolo_archiviato(tmp_path):
    gestore = _gestore(tmp_path)
    fascicolo = gestore.nuovo(titolo="Rosa c/ Viola", tipo=TipoFascicolo.CIVILE, nome_cliente="Anna Rosa", numero_rg="10", anno_rg=2026)
    assert applica(gestore, fascicolo, prova_sentenza("2026-09-01", "55"))
    assert gestore.get(fascicolo.id).stato == StatoFascicolo.DEFINITO
    gestore.archivia(fascicolo.id, crea_zip=False)
    assert not applica(gestore, gestore.get(fascicolo.id), prova_registro(StatoFascicolo.IN_CORSO, "Pendente"))
    assert gestore.get(fascicolo.id).stato == StatoFascicolo.ARCHIVIATO


def test_aggiorna_lo_stato_a_mano_lascia_traccia(tmp_path):
    gestore = _gestore(tmp_path)
    fascicolo = gestore.nuovo(titolo="Consulenza", tipo=TipoFascicolo.CIVILE, nome_cliente="Anna Rosa")
    gestore.aggiorna(fascicolo.id, stato=StatoFascicolo.SOSPESO, nota_stato="Sospensione concordata")
    aggiornato = gestore.get(fascicolo.id)
    assert aggiornato.stato == StatoFascicolo.SOSPESO
    assert aggiornato.avanzamento[-1].stato_nuovo == "SOSPESO"
