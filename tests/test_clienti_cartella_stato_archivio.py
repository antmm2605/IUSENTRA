from types import SimpleNamespace

from pct.clienti import Cliente, TipoCliente
from pct.fascicoli import Fascicolo, StatoFascicolo, TipoFascicolo
from web.services.react_clienti_bridge import build_react_cliente_cartella_payload


def test_cartella_distingue_preparazione_archivio_e_archiviazione_confermata(monkeypatch):
    cliente = Cliente(id='C1', tipo=TipoCliente.PERSONA_FISICA, nome='Anna', cognome='Bianchi')
    cases = [Fascicolo(id=identifier, numero=f'2026/{index}', titolo=identifier,
        tipo=TipoFascicolo.CIVILE, stato=state, id_cliente='C1')
        for index, (identifier, state) in enumerate([
            ('DA_ARCHIVIARE', StatoFascicolo.DEFINITO),
            ('ARCHIVIATO', StatoFascicolo.ARCHIVIATO),
            ('APERTO', StatoFascicolo.APERTO)], 1)]
    cases[0].stato_pratica_operativa = 'Da archiviare'
    # Uno stato nativo esplicito prevale anche su un vecchio flag discordante.
    cases[0].archiviato = True
    monkeypatch.setattr('web.services.identita_cliente_runtime.documenti_identita_cliente', lambda *_: [])
    monkeypatch.setattr('web.services.react_cliente_comunicazioni.pec_collegate_cartella', lambda *_: [])
    empty = SimpleNamespace(lista=lambda **_: [], tutti=lambda **_: [], per_cliente=lambda *_: [],
        preventivi_per_cliente=lambda *_: [], conferimenti_per_cliente=lambda *_: [])
    result = build_react_cliente_cartella_payload(
        get_clienti=lambda: SimpleNamespace(get=lambda _: cliente),
        get_fascicoli=lambda: SimpleNamespace(cerca=lambda **_: cases),
        get_agenda=lambda: empty, get_messaggi=lambda: empty, get_scadenziario=lambda: empty,
        get_preventivi=lambda: empty, get_fatturazione=lambda: empty, id_cliente='C1')
    assert result['summary']['activeMatters'] == 2
    assert result['summary']['archivedMatters'] == 1
    assert [case['id'] for case in result['matters']['active']] == ['DA_ARCHIVIARE', 'APERTO']
    assert [case['id'] for case in result['matters']['archived']] == ['ARCHIVIATO']
    assert cases[0].stato == StatoFascicolo.DEFINITO
    assert cases[1].stato == StatoFascicolo.ARCHIVIATO
