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


def test_accoda_solo_il_fascicolo_con_data_decisione_incompleta(tmp_path):
    from pct.registro_letture import Oggetto, RegistroLetture
    from pct.registro_letture.fatti_repository import Fatto
    from web.services.esito_sentenze_recovery import accoda_decisioni_incomplete

    registro = RegistroLetture(tmp_path / "letture.sqlite")
    esito = Fatto(categoria="evento", campo="esito_sentenza", valore="accoglimento", verifica="verificata")
    data = Fatto(categoria="evento", campo="data_decisione_sentenza", valore="2026-10-09", verifica="verificata")
    for fid, fatti in (("F1", [esito]), ("F2", [esito, data])):
        oggetto = Oggetto(tipo="documento", oggetto_id=f"{fid}-S1", nome="sentenza.pdf", sha256="b" * 64)
        registro.registra_inventario("t", fid, [oggetto])
        registro.registra_fatti("t", fid, oggetto, "documenti", fatti)
    assert accoda_decisioni_incomplete(registro, "t", prima_di="2099-01-01", limite=10) == 1
    assert registro.stato_evento("t", "F1") == "pending"
    assert registro.stato_evento("t", "F2") == "idle"


def test_senza_testo_salvato_non_si_apre_il_file():
    registro = _Registro([_ruolo()])
    assert recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: "") == {"controllate": 0, "recuperate": 0}
    assert registro.scritture == []


def test_recupera_il_merito_mancante_senza_sovrascrivere_le_spese():
    spese = SimpleNamespace(
        oggetto_id="S1", fascicolo_id="F1", sha256="sha1", motore="documenti",
        campo="spese_sentenza", valore="compensazione", categoria="evento",
    )
    registro = _Registro([_ruolo(), spese])
    testo = (
        "TRIBUNALE — SENTENZA\nP.Q.M.\n"
        "Condanna il M.I.U.R. all’assegnazione in favore di parte ricorrente del beneficio; "
        "compensa le spese di lite."
    )

    esito = recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: testo)

    assert esito == {"controllate": 1, "recuperate": 1}
    assert [f for f in registro.fatti if f.campo == "spese_sentenza"] == [spese]
    assert [f.valore for f in registro.fatti if f.campo == "esito_sentenza"] == ["accoglimento"]


def test_complete_spese_esistenti_dal_dispositivo_senza_duplicarle():
    dati = dict(oggetto_id="S1", fascicolo_id="F1", sha256="sha1", motore="documenti",
                categoria="evento", verifica="verificata")
    esito_salvato = SimpleNamespace(**dati, campo="esito_sentenza", valore="accoglimento")
    spese_salvate = SimpleNamespace(**dati, campo="spese_sentenza", valore="condanna;distrazione")
    registro = _Registro([_ruolo(), esito_salvato, spese_salvate])
    testo = (
        "SENTENZA\nP.Q.M. accoglie il ricorso e riconosce buoni spesa pari a Euro 500; "
        "condanna il Ministero a rimborsare a parte ricorrente le spese di lite, che si liquidano "
        "complessivamente in \u20ac 258 oltre spese generali al 15%, IVA e CPA con distrazione al difensore."
    )

    esito = recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: testo)

    assert esito == {"controllate": 1, "recuperate": 1}
    assert [f.valore for f in registro.fatti if f.campo == "spese_sentenza"] == ["condanna;importo=258,00;distrazione"]
    assert [f for f in registro.fatti if f.campo == "esito_sentenza"] == [esito_salvato]
    assert recupera_esiti(_fascicolo(), registro, "t", sentenze={"S1"}, testo_salvato=lambda d: testo)["controllate"] == 0
