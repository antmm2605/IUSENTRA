from types import SimpleNamespace

from pct import uffici_giudiziari as offices


def test_alias_catalogo_riusati_senza_conservare_record_o_query(monkeypatch):
    offices._slug_alias_catalogo.cache_clear()
    catalog = [{'codice': 'TRIB_TEST', 'tipo': 'TRIBUNALE', 'nome': 'Tribunale di Località Prima',
                'comune_ministero': 'Località Prima'}]
    monkeypatch.setattr(offices, 'get_gestore', lambda _: SimpleNamespace(carica=lambda: catalog))
    try:
        first = offices.risolvi_ufficio('TRIBUNALE ORDINARIO DI LOCALITÀ PRIMA', tipo='TRIBUNALE')
        assert first == catalog[0]
        misses = offices._slug_alias_catalogo.cache_info().misses
        assert offices.risolvi_ufficio('TRIBUNALE ORDINARIO DI LOCALITÀ PRIMA', tipo='TRIBUNALE') == first
        assert offices._slug_alias_catalogo.cache_info().misses == misses
        # A changed source must change the result despite the cached normalization.
        catalog[0] = {'codice': 'TRIB_TEST', 'tipo': 'TRIBUNALE', 'nome': 'Tribunale di Località Seconda',
                      'comune_ministero': 'Località Seconda'}
        assert offices.risolvi_ufficio('Tribunale di Località Seconda', tipo='TRIBUNALE') == catalog[0]
        assert offices.risolvi_ufficio('Tribunale di Località Prima', tipo='TRIBUNALE') is None
        assert offices.risolvi_ufficio('Tribunale di Località Seconda', tipo='GDP') is None
    finally:
        offices._slug_alias_catalogo.cache_clear()


def test_valori_lunghi_non_restano_nella_cache_del_catalogo(monkeypatch):
    offices._slug_alias_catalogo.cache_clear()
    normalize = offices._slug_alias_ufficio
    calls = []
    def counted(value):
        calls.append(value)
        return normalize(value)
    monkeypatch.setattr(offices, '_slug_alias_ufficio', counted)
    name = 'Tribunale ' + 'A' * 600
    try:
        first = offices._alias_ufficio({'nome': name})
        assert offices._alias_ufficio({'nome': name}) == first
        assert calls.count(name) == 2
        assert offices._slug_alias_catalogo.cache_info().maxsize == 8192
    finally:
        offices._slug_alias_catalogo.cache_clear()
