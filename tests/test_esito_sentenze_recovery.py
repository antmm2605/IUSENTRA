"""Recupero puntuale dell'esito delle sentenze già lette (RG 2962/2023 GdP Palmi, collaudo 08/11/2026)."""

from __future__ import annotations

from types import SimpleNamespace

from pct.archivio_letture.estrazione_esito import VERSIONE_ESTRAZIONE_ESITO
from web.services.esito_sentenze_recovery import CAMPO_CONTROLLO, recupera_esiti

SENTENZA_GDP = (
    "Sentenza n. 376/2026 pubbl. il 13/05/2026 RG n. 2962/2023 UFFICIO DEL GIUDICE DI PACE DI PALMI SENTENZA Il Giudice "
    "di Pace ... ha pronunciato SENTENZA con il seguente dispositivo\nP.Q.M.\nIl Giudice di Pace, definitivamente "
    "pronunciando, così provvede:\naccoglie il ricorso e per l'effetto annulla il verbale di accertamento. Compensa "
    "interamente le spese del giudizio. Motivi della decisione ... Così deciso in PALMI il 04-05-2026\n"
    "Il Giudice di Pace Dott. Giuseppe Caruso")


class _Registro:
    def __init__(self, fatti=()):
        self.oggetto = SimpleNamespace(tipo="documento", oggetto_id="S1", impronta="sha1", presente=True)
        self.fatti = list(fatti)
        self.scritture = []

    def letture(self, tenant, fid, lettore):
        return [SimpleNamespace(oggetto_id="S1", sha256="sha1", stato="letto", versione_lettore="v-vecchia")]

    def oggetti(self, tenant, fid):
        return [self.oggetto, SimpleNamespace(tipo="documento", oggetto_id="R1", impronta="sha2", presente=True)]

    def fatti_oggetto(self, tenant, tipo, oggetto_id):
        return [f for f in self.fatti if f.oggetto_id == oggetto_id]

    def registra_fatti(self, tenant, fid, oggetto, motore, fatti, *, versione=""):
        fatti = list(fatti)
        for fatto in fatti:
            fatto.fascicolo_id = fid  # come fa il registro reale all'inserimento
        self.scritture.append((oggetto.oggetto_id, motore, versione, fatti))
        self.fatti = [f for f in self.fatti if f.oggetto_id != oggetto.oggetto_id] + fatti


def _fascicolo():
    return SimpleNamespace(id="F1", documenti=[SimpleNamespace(id="S1", nome="Atto_3217226.pdf"), SimpleNamespace(id="R1")])


def _ruolo():
    return SimpleNamespace(oggetto_id="S1", fascicolo_id="F1", sha256="sha1", motore="documenti", campo="numero_ruolo",
                           valore="2962/2023", categoria="ruolo")


def test_recupera_esito_e_spese_dal_testo_salvato_solo_per_la_sentenza():
    registro = _Registro([_ruolo()])
    letti = []
    esito = recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"},
                           testo_salvato=lambda d: letti.append(d.id) or SENTENZA_GDP)
    assert esito == {"controllate": 1, "recuperate": 1} and letti == ["S1"]
    oggetto, motore, versione, fatti = registro.scritture[0]
    assert (oggetto, motore, versione) == ("S1", "documenti", "v-vecchia")
    campi = {f.campo: f.valore for f in fatti}
    assert campi["esito_sentenza"] == "accoglimento" and campi["spese_sentenza"] == "compensazione"
    assert campi["numero_ruolo"] == "2962/2023"  # i fatti già letti restano
    # secondo giro: nulla da fare
    assert recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: SENTENZA_GDP)["controllate"] == 0


def test_dispositivo_non_riconosciuto_si_segna_e_non_si_riprova():
    registro = _Registro([_ruolo()])
    recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: "SENTENZA senza dispositivo")
    assert any(f.campo == CAMPO_CONTROLLO and f.valore == VERSIONE_ESTRAZIONE_ESITO for f in registro.fatti)
    assert recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: SENTENZA_GDP)["controllate"] == 0


def test_senza_testo_salvato_non_si_apre_il_file():
    registro = _Registro([_ruolo()])
    assert recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: "") == {"controllate": 0, "recuperate": 0}
    assert registro.scritture == []
