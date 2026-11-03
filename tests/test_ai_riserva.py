"""AI locale: se il modello principale non riesce si scarica e si usa la riserva, con l'esito nel registro."""

from __future__ import annotations

import pytest

from pct.ai_riserva import genera_con_riserva
from pct.scheduler_notturno.registro import RegistroNotte


class Client:
    def __init__(self):
        self.scaricati = []

    def generate_completion(self, modello, prompt, *, keep_alive="10m", timeout=300, **_):
        if keep_alive == "0":
            self.scaricati.append(modello)
        return {}


def test_principale_riuscito_nessuna_riserva():
    client, registrati = Client(), []
    assert genera_con_riserva(client, "a", "b", lambda m: f"ok {m}", registra=registrati.append) == "ok a"
    assert client.scaricati == [] and registrati == []


def test_principale_fallito_si_scarica_e_parte_la_riserva(tmp_path):
    client = Client()
    registro = RegistroNotte(tmp_path / "r.sqlite")

    def chiama(modello):
        if modello == "spark":
            raise TimeoutError("tempo scaduto")
        return "ok riserva"

    esito = genera_con_riserva(client, "spark", "qwen3:4b", chiama,
                               registra=lambda e: registro.scrivi_esito_ai("2026-11-03T23:00:00", e))
    assert esito == "ok riserva" and client.scaricati == ["spark"]
    riga = registro.esiti_ai()[0]
    assert riga["esito"] == "riserva_riuscita" and "TimeoutError" in riga["motivo"]


def test_anche_la_riserva_fallisce():
    client, registrati = Client(), []

    def chiama(modello):
        raise MemoryError("memoria esaurita")

    with pytest.raises(MemoryError):
        genera_con_riserva(client, "a", "b", chiama, registra=registrati.append)
    assert client.scaricati == ["a", "b"] and registrati[0]["esito"] == "riserva_fallita"


def test_senza_riserva_rilancia():
    with pytest.raises(RuntimeError):
        genera_con_riserva(Client(), "a", "", lambda m: (_ for _ in ()).throw(RuntimeError("x")))
