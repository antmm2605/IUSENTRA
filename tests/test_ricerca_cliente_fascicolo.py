"""Ricerca del fascicolo per nome del cliente: ordine invertito, accenti, parziali."""

from __future__ import annotations

import pytest

from pct.ricerca_cliente_fascicolo import (
    SOGLIA_CERTA,
    cerca_fascicoli,
    normalizza,
    punteggio_cliente,
    punteggio_nome,
    varianti_cliente,
)


class Cliente:
    def __init__(self, identificativo: str, nome: str = "", cognome: str = "", ragione_sociale: str = ""):
        self.id = identificativo
        self.nome = nome
        self.cognome = cognome
        self.ragione_sociale = ragione_sociale

    @property
    def nome_completo(self) -> str:
        return ragione if (ragione := self.ragione_sociale) else " ".join(p for p in (self.nome, self.cognome) if p)


class Fascicolo:
    def __init__(self, identificativo, numero, titolo, id_cliente="", stato="APERTO", nome_cliente=""):
        self.id = identificativo
        self.numero = numero
        self.titolo = titolo
        self.id_cliente = id_cliente
        self.stato = stato
        self.nome_cliente = nome_cliente


@pytest.fixture()
def archivio():
    clienti = {
        "c1": Cliente("c1", nome="Mario", cognome="Rossi"),
        "c2": Cliente("c2", ragione_sociale="Bianchi S.r.l."),
        "c3": Cliente("c3", nome="Anna", cognome="D'Amico"),
    }
    fascicoli = [
        Fascicolo("f1", "2026/001", "Sfratto per morosita'", "c1"),
        Fascicolo("f2", "2026/002", "Recupero crediti", "c2"),
        Fascicolo("f3", "2025/117", "Separazione consensuale", "c3"),
        Fascicolo("f4", "2019/004", "Vecchia causa", "c1", stato="ARCHIVIATO"),
    ]
    return fascicoli, clienti


def cerca(archivio, richiesta):
    fascicoli, clienti = archivio
    return cerca_fascicoli(fascicoli, richiesta=richiesta, clienti_per_id=clienti)


def test_normalizza_toglie_punteggiatura_e_maiuscole():
    assert normalizza("  Bianchi  S.r.l. ") == "bianchi s r l"


def test_il_nome_invertito_vale_quanto_il_nome_diretto():
    assert punteggio_nome("Rossi Mario", "Mario Rossi") == 1.0


def test_le_varianti_del_cliente_comprendono_i_due_ordini():
    varianti = [normalizza(v) for v in varianti_cliente(Cliente("c", nome="Mario", cognome="Rossi"))]
    assert "mario rossi" in varianti
    assert "rossi mario" in varianti


def test_il_solo_cognome_e_una_proposta_non_una_certezza():
    punteggio = punteggio_cliente("Rossi", Cliente("c", nome="Mario", cognome="Rossi"))
    assert 0 < punteggio < SOGLIA_CERTA


def test_il_nome_completo_e_una_corrispondenza_certa(archivio):
    risultati = cerca(archivio, "rossi mario")
    assert [r.fascicolo_id for r in risultati] == ["f1"]
    assert risultati[0].certo is True


def test_la_ricerca_parziale_trova_il_cliente_mentre_si_digita(archivio):
    risultati = cerca(archivio, "ros")
    assert [r.fascicolo_id for r in risultati] == ["f1"]
    assert risultati[0].certo is False


def test_la_ragione_sociale_si_cerca_come_un_nome(archivio):
    assert [r.fascicolo_id for r in cerca(archivio, "Bianchi")] == ["f2"]


def test_gli_accenti_e_gli_apostrofi_non_bloccano_la_ricerca(archivio):
    assert [r.fascicolo_id for r in cerca(archivio, "d amico")] == ["f3"]


def test_si_puo_cercare_anche_per_numero_o_per_oggetto(archivio):
    assert [r.fascicolo_id for r in cerca(archivio, "2026/002")] == ["f2"]
    assert [r.fascicolo_id for r in cerca(archivio, "sfratto")] == ["f1"]


def test_i_fascicoli_archiviati_restano_fuori(archivio):
    assert all(r.fascicolo_id != "f4" for r in cerca(archivio, "rossi mario"))


def test_una_richiesta_troppo_corta_non_propone_nulla(archivio):
    assert cerca(archivio, "r") == []


def test_i_candidati_arrivano_dal_piu_sicuro_al_meno(archivio):
    fascicoli, clienti = archivio
    fascicoli = [*fascicoli, Fascicolo("f5", "2026/009", "Causa collegata Mario Rossi", "c2")]
    risultati = cerca_fascicoli(fascicoli, richiesta="Mario Rossi", clienti_per_id=clienti)
    assert [r.fascicolo_id for r in risultati] == ["f1", "f5"]
    assert risultati[0].punteggio > risultati[1].punteggio


def test_il_limite_taglia_la_lista(archivio):
    fascicoli, clienti = archivio
    risultati = cerca_fascicoli(fascicoli, richiesta="rossi", clienti_per_id=clienti, limite=1)
    assert len(risultati) == 1


def test_senza_anagrafica_si_usa_il_nome_scritto_sul_fascicolo():
    fascicoli = [Fascicolo("f9", "2026/030", "Opposizione", nome_cliente="Giulia Verdi")]
    risultati = cerca_fascicoli(fascicoli, richiesta="verdi giulia")
    assert [r.fascicolo_id for r in risultati] == ["f9"]
    assert risultati[0].cliente == "Giulia Verdi"


def test_il_candidato_serializzato_porta_tutto_il_necessario_alla_ui(archivio):
    voce = cerca(archivio, "rossi mario")[0].come_dizionario()
    assert voce["value"] == "f1"
    assert voce["numero"] == "2026/001"
    assert voce["cliente"] == "Mario Rossi"
    assert voce["certo"] is True
    assert "2026/001" in voce["label"]


class GestoreFascicoli:
    def __init__(self, fascicoli):
        self._fascicoli = fascicoli
        self.archiviati_richiesti = None

    def tutti(self, archiviati=False):
        self.archiviati_richiesti = archiviati
        return [f for f in self._fascicoli if archiviati or f.stato != "ARCHIVIATO"]


class GestoreClienti:
    def __init__(self, clienti):
        self._clienti = clienti

    def tutti(self):
        return list(self._clienti.values())


def _servizio(archivio, richiesta, **extra):
    from web.services.fascicolo_lookup import cerca_fascicoli_per_cliente

    fascicoli, clienti = archivio
    gestore = GestoreFascicoli(fascicoli)
    return (
        cerca_fascicoli_per_cliente(
            richiesta,
            gestore_fascicoli=lambda: gestore,
            gestore_clienti=lambda: GestoreClienti(clienti),
            **extra,
        ),
        gestore,
    )


def test_il_servizio_restituisce_candidati_serializzati(archivio):
    risultati, gestore = _servizio(archivio, "rossi mario")
    assert [voce["value"] for voce in risultati] == ["f1"]
    assert gestore.archiviati_richiesti is False


def test_il_servizio_ignora_le_richieste_troppo_corte(archivio):
    risultati, _ = _servizio(archivio, " r ")
    assert risultati == []


def test_il_servizio_regge_l_anagrafica_non_disponibile(archivio):
    from web.services.fascicolo_lookup import cerca_fascicoli_per_cliente

    fascicoli, _ = archivio

    def clienti_rotti():
        raise RuntimeError("anagrafica non raggiungibile")

    risultati = cerca_fascicoli_per_cliente(
        "sfratto",
        gestore_fascicoli=lambda: GestoreFascicoli(fascicoli),
        gestore_clienti=clienti_rotti,
    )
    assert [voce["value"] for voce in risultati] == ["f1"]
