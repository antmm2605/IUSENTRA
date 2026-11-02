"""Sentenza → proposta di definizione e crediti del capo spese, sempre da confermare.

Esempi costruiti sulle formule ufficiali dei dispositivi: art. 132 c.p.c. (contenuto della
sentenza), art. 279 c.p.c. (sentenza non definitiva), art. 384 c.p.c. (cassazione con rinvio),
art. 88 c.p.a. (sentenza del giudice amministrativo), artt. 91-93 c.p.c. (spese e distrazione),
artt. 325-327 c.p.c. e art. 92 c.p.a. (termini d'impugnazione). Nessun dato reale di clienti.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from pct.archivio_letture.estrazione_economica import estrai_controllo_economico
from pct.archivio_letture.natura_provvedimento import e_provvedimento
from pct.fascicoli import Fascicolo, StatoFascicolo, TipoFascicolo
from pct.fascicolo_sentenza_archiviazione import VERSIONE_PROPOSTA, verifica_sentenza_da_archiviare
from pct.registro_letture import RegistroLetture
from pct.registro_letture.modello import Oggetto
from pct.sentenza_conclusiva import valuta_sentenza

TESTA_TRIBUNALE = (
    "TRIBUNALE DI LOCRI\nREPUBBLICA ITALIANA\nIN NOME DEL POPOLO ITALIANO\nIl Tribunale di Locri, in composizione "
    "monocratica, ha pronunciato la seguente SENTENZA n. 123/2026 pubblicata il 15/10/2026 nella causa iscritta al "
    "R.G. n. 456/2025 tra ROSSI MARIO (attore), rappresentato e difeso dall'avv. Bianchi, e ALFA S.R.L. (convenuta). "
    "Svolgimento del processo. Motivi della decisione. "
)
TESTA_LAVORO = TESTA_TRIBUNALE.replace("in composizione monocratica", "in funzione di giudice del lavoro").replace("(attore)", "(ricorrente)")
TESTA_APPELLO = (
    "CORTE D'APPELLO DI REGGIO CALABRIA REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO La Corte, in grado d'appello, "
    "ha pronunciato la seguente SENTENZA n. 77/2026 pubblicata il 02/10/2026 nella causa R.G. n. 456/2025. Motivi. "
)
TESTA_TAR = (
    "REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO Il Tribunale Amministrativo Regionale per la Calabria ha "
    "pronunciato la presente SENTENZA n. 900/2026 sul ricorso numero di registro generale 456 del 2025. Motivi. "
)

CONCLUSIVE = {
    "civile_condanna": TESTA_TRIBUNALE + "P.Q.M. Il Tribunale, definitivamente pronunciando, accoglie la domanda e condanna "
                       "la convenuta alla rifusione delle spese di lite in favore dell'attore, che liquida in euro 2.500,00 per compensi, oltre accessori.",
    "lavoro_compensate": TESTA_LAVORO + "PQM\nrigetta il ricorso. Spese di lite compensate.",
    "appello_conferma": TESTA_APPELLO + "P.Q.M. La Corte rigetta l'appello e conferma la sentenza impugnata; condanna l'appellante alle spese.",
    "amministrativo": TESTA_TAR + "P.Q.M. Il Tribunale Amministrativo Regionale, definitivamente pronunciando sul ricorso, lo accoglie e annulla il provvedimento impugnato.",
}
NON_CONCLUSIVE = {
    "non_definitiva": TESTA_TRIBUNALE.replace("la seguente SENTENZA", "la seguente SENTENZA NON DEFINITIVA") + "P.Q.M. accoglie la domanda sull'an.",
    "separata_ordinanza": TESTA_TRIBUNALE + "P.Q.M. dichiara la responsabilità della convenuta e dispone come da separata ordinanza per la prosecuzione del giudizio.",
    "istruttoria": TESTA_TRIBUNALE + "P.Q.M. dichiara la giurisdizione e rimette la causa in istruttoria.",
    "cassazione_rinvio": "CORTE SUPREMA DI CASSAZIONE SENTENZA n. 5/2026 R.G. n. 456/2025. Motivi. P.Q.M. La Corte cassa la sentenza impugnata con rinvio alla Corte d'appello.",
    "due_dispositivi": TESTA_TRIBUNALE + "P.Q.M. accoglie la domanda. Si richiama altra pronuncia P.Q.M. rigetta.",
}


@pytest.mark.parametrize("nome", sorted(CONCLUSIVE))
def test_sentenza_conclusiva_in_tutte_le_materie(nome):
    esito = valuta_sentenza(CONCLUSIVE[nome])
    assert esito["conclusiva"], esito["motivo"]
    assert "passaggio in giudicato" in esito["motivo"]


def test_motivo_cita_i_termini_del_proprio_rito():
    assert "art. 92 c.p.a." in valuta_sentenza(CONCLUSIVE["amministrativo"])["motivo"]
    assert "artt. 325-327 c.p.c." in valuta_sentenza(CONCLUSIVE["civile_condanna"])["motivo"]
    assert valuta_sentenza(CONCLUSIVE["appello_conferma"])["grado"] == "appello"
    assert valuta_sentenza(CONCLUSIVE["lavoro_compensate"])["compensate"] is True


@pytest.mark.parametrize("nome", sorted(NON_CONCLUSIVE))
def test_nessuna_proposta_se_il_giudizio_prosegue(nome):
    esito = valuta_sentenza(NON_CONCLUSIVE[nome])
    assert not esito["conclusiva"]
    assert esito["motivo"]


def _fascicolo(stato=StatoFascicolo.IN_CORSO):
    fascicolo = Fascicolo(id="F1", numero="2025/001", titolo="Prova", tipo=list(TipoFascicolo)[0], nome_cliente="Rossi Mario",
                          numero_rg="456", anno_rg="2025", tribunale="Tribunale di Locri")
    fascicolo.stato = stato
    return fascicolo


def _fonte(testo):
    return {"verified_original": True, "sha256": hashlib.sha256(testo.encode()).hexdigest()}


def test_spese_compensate_definiscono_senza_importo():
    testo = TESTA_TRIBUNALE + "P.Q.M. Il Tribunale, definitivamente pronunciando, rigetta la domanda. Spese compensate."
    verifica = verifica_sentenza_da_archiviare(fascicolo=_fascicolo(), testo=testo, fonte=_fonte(testo), cliente={})
    assert verifica["eligible"] and verifica["amount"] is None and verifica["compensate"]


def test_sentenza_di_altra_causa_non_propone_nulla():
    testo = CONCLUSIVE["civile_condanna"].replace("R.G. n. 456/2025", "R.G. n. 999/2024")
    assert not verifica_sentenza_da_archiviare(fascicolo=_fascicolo(), testo=testo, fonte=_fonte(testo), cliente={})["eligible"]


@pytest.mark.parametrize("tipo", ["SENTENZA", "ALLEGATO", "ATTO_GIUDIZIARIO", ""])
def test_controllo_economico_non_dipende_dal_tipo_dato_dal_nome_file(tipo):
    fatti = estrai_controllo_economico(CONCLUSIVE["civile_condanna"], origine="nativo",
                                       metadata={"fascicolo": _fascicolo(), "tipo_documento": tipo, "documento_id": "D1"})
    assert [f.campo for f in fatti] == ["controllo_economico"]


def test_allegato_che_non_e_una_sentenza_resta_fuori():
    assert not e_provvedimento("ALLEGATO", testo="Fattura n. 12 del 2026 per consulenza tecnica.")
    assert e_provvedimento("ALLEGATO", etichetta_catalogo="Provvedimento - sentenza")
    assert not estrai_controllo_economico("Contratto di locazione tra le parti.", origine="nativo",
                                          metadata={"fascicolo": _fascicolo(), "tipo_documento": "ALLEGATO"})


# --- runtime: lettore delle proposte, conferma e respingimento --------------------------------------

class _Gestore:
    def __init__(self, fascicolo):
        self.fascicolo = fascicolo
        self.chiamate = []

    def get(self, fascicolo_id):
        return self.fascicolo if fascicolo_id == self.fascicolo.id else None

    def cambia_stato(self, fascicolo_id, stato, note="", avvocato="", **_):
        self.chiamate.append((fascicolo_id, stato, note, avvocato))
        self.fascicolo.stato = stato


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    import web.helpers
    import web.services.archivio_letture_runtime as archivio
    import web.services.registro_letture_runtime as registro_runtime
    import web.services.sentenza_proposte_runtime as runtime

    testo = CONCLUSIVE["civile_condanna"]
    fascicolo = _fascicolo()
    fascicolo.documenti = [SimpleNamespace(id="D1", tipo="ALLEGATO", nome="12345.pdf")]
    registro = RegistroLetture(tmp_path / "registro.db")
    oggetto = Oggetto(tipo="documento", oggetto_id="D1", nome="12345.pdf", sha256=hashlib.sha256(testo.encode()).hexdigest())
    registro.registra_inventario("studio", "F1", [oggetto])
    gestore = _Gestore(fascicolo)
    testi = {"D1": testo}
    monkeypatch.setattr(archivio, "testi_indice_archivio", lambda _f: testi)
    monkeypatch.setattr(runtime, "_catalogo", lambda _fid: {})
    monkeypatch.setattr(runtime, "_cliente", lambda _f: {})
    monkeypatch.setattr(runtime, "crediti_da_sentenza", lambda *_a, **_k: (True, []))
    monkeypatch.setattr(runtime, "_dopo_decisione", lambda *a, **k: None)
    monkeypatch.setattr(registro_runtime, "registro_corrente", lambda **_: registro)
    monkeypatch.setattr(registro_runtime, "tenant_corrente", lambda: "studio")
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: gestore)
    return SimpleNamespace(runtime=runtime, registro=registro, fascicolo=fascicolo, gestore=gestore, testi=testi)


def test_la_sentenza_propone_e_non_cambia_lo_stato(ambiente):
    report = ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")
    assert report["proposte"] == 1
    assert ambiente.fascicolo.stato == StatoFascicolo.IN_CORSO
    proposte = ambiente.runtime.proposte_sentenza_payload(ambiente.fascicolo)["definizione"]
    assert len(proposte) == 1 and proposte[0]["numero"] == "123" and proposte[0]["importoLabel"] == "€ 2.500,00"
    # Secondo giro: nulla da riesaminare.
    assert ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")["esaminati"] == 0


def test_conferma_definisce_con_la_sentenza_come_fonte(ambiente):
    ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")
    proposta = ambiente.runtime.proposte_sentenza_payload(ambiente.fascicolo)["definizione"][0]
    esito = ambiente.runtime.decidi_definizione(ambiente.fascicolo, proposta["id"], esito="conferma", utente="avv1")
    assert esito["esito"] == "confermata"
    assert ambiente.fascicolo.stato == StatoFascicolo.DEFINITO
    (_, _, nota, autore), = ambiente.gestore.chiamate
    assert "art. 132 c.p.c." in nota and "giudicato" in nota and autore == "avv1"
    assert ambiente.runtime.proposte_sentenza_payload(ambiente.fascicolo)["definizione"] == []


def test_respingi_lascia_lo_stato_e_la_decisione_sopravvive_alla_regola_nuova(ambiente, monkeypatch):
    ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")
    proposta = ambiente.runtime.proposte_sentenza_payload(ambiente.fascicolo)["definizione"][0]
    ambiente.runtime.decidi_definizione(ambiente.fascicolo, proposta["id"], esito="respingi", utente="avv1")
    assert ambiente.fascicolo.stato == StatoFascicolo.IN_CORSO and not ambiente.gestore.chiamate
    # Riconvalida dello storico: con una regola nuova la fonte si riesamina, la decisione resta.
    monkeypatch.setattr(ambiente.runtime, "VERSIONE_PROPOSTA", VERSIONE_PROPOSTA + "+prova")
    assert ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")["esaminati"] == 1
    assert ambiente.runtime.proposte_sentenza_payload(ambiente.fascicolo)["definizione"] == []


def test_storico_letto_prima_della_regola_produce_la_proposta(ambiente):
    oggetto = ambiente.registro.oggetto("studio", "F1", "documento", "D1")
    ambiente.registro.segna_letto("studio", "F1", oggetto, "proposta_definizione", versione="sentenza-propria-da-archiviare-v2-componenti",
                                  esito={"pertinente": True, "proposta": False, "motivo": "Valore liquidato nel dispositivo non determinato."})
    assert ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")["proposte"] == 1


def test_testo_non_ancora_disponibile_resta_in_attesa(ambiente):
    ambiente.testi.clear()
    report = ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")
    assert report["in_attesa_testo"] == 1 and report["esaminati"] == 0


def test_proposta_non_valida_se_il_documento_cambia(ambiente):
    ambiente.runtime.aggiorna_proposte_definizione(ambiente.fascicolo, ambiente.registro, "studio")
    with pytest.raises(ValueError):
        ambiente.runtime.decidi_definizione(ambiente.fascicolo, "D1:" + "0" * 64, esito="conferma")
    with pytest.raises(ValueError):
        ambiente.runtime.decidi_definizione(ambiente.fascicolo, "D1:x", esito="forse")


def test_parcella_da_credito_non_si_duplica(monkeypatch):
    import web.services.sentenza_economic_runtime as economia
    import web.services.sentenza_proposte_runtime as runtime

    evento = {"id": "fee1", "event_type": "apri_credito_avvocato_antistatario", "status": "confirmed", "amount": 2000.0}
    monkeypatch.setattr(economia, "_flag_on", lambda: True)
    monkeypatch.setattr(economia, "_tenant_id", lambda: "studio")
    monkeypatch.setattr(economia, "_repo", lambda: SimpleNamespace(list_economic_events=lambda *a, **k: [evento]))
    monkeypatch.setattr(economia, "_resolve_fascicolo", lambda fid, **_: _fascicolo())
    monkeypatch.setattr(runtime, "_parcelle_per_evento", lambda fid: {"fee1": "2026/0007"})
    esito = economia.genera_parcella_from_event({"eventId": "fee1", "fascicoloId": "F1"})
    assert esito == {"ok": True, "eventId": "fee1", "parcella": "2026/0007", "alreadyPresent": True}


def test_route_parcella_registrata():
    from web.blueprints.api_v1_sentenza_economic import sentenza_economic_parcella

    assert callable(sentenza_economic_parcella)
