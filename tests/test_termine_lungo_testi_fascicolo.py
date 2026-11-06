"""Il termine lungo legge i testi dal fascicolo vero: con il solo identificativo la lettura falliva in silenzio (2.484.0)."""

from types import SimpleNamespace

import web.helpers as helpers
import web.services.archivio_letture_runtime as archivio
from web.services import termine_lungo_runtime as runtime


def test_i_testi_si_leggono_dal_fascicolo_con_i_suoi_documenti(monkeypatch):
    fascicolo = SimpleNamespace(id="9DC39668", documenti=[SimpleNamespace(id="D1")])
    ricevuti = []
    monkeypatch.setattr(helpers, "get_fascicoli", lambda: {"9DC39668": fascicolo})

    def testi(f):
        ricevuti.append(f)
        return {"D1": "ha pronunciato in pari data la seguente sentenza"}

    monkeypatch.setattr(archivio, "testi_indice_archivio", testi)
    assert runtime._testi_del_fascicolo("9DC39668") == ["ha pronunciato in pari data la seguente sentenza"]
    assert ricevuti == [fascicolo] and ricevuti[0].documenti


def test_fascicolo_assente_nessun_testo(monkeypatch):
    monkeypatch.setattr(helpers, "get_fascicoli", lambda: {})
    assert runtime._testi_del_fascicolo("XXXX") == []
