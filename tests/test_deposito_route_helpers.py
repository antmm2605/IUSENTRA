from types import SimpleNamespace

from web.services.deposito_route_helpers import deposito_oggetto


class _Form(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def test_deposito_oggetto_carta_docente_mim_usa_pubblico_impiego():
    form = _Form({"codice_oggetto_pst": "220050"})
    fascicolo = SimpleNamespace(
        codice_oggetto_pst="220050",
        titolo="Marchetti c. MIM",
        oggetto="Bonus Docente",
        controparte="Avvocatura Distrettuale di Stato di Venezia",
        dati_json={
            "oggetto": "Bonus Docente",
            "codice_oggetto_pst": "220050",
        },
    )

    assert deposito_oggetto(form, fascicolo) == "222050"


def test_deposito_oggetto_non_cambia_retribuzione_privata_senza_mim():
    form = _Form({"codice_oggetto_pst": "220050"})
    fascicolo = SimpleNamespace(
        codice_oggetto_pst="220050",
        titolo="Rossi c. Alfa SRL",
        oggetto="Retribuzione",
        controparte="Alfa SRL",
    )

    assert deposito_oggetto(form, fascicolo) == "220050"
