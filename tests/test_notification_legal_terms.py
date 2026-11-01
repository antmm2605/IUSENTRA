"""Il presidio delle notifiche mostra il termine lungo (art. 327 c.p.c.) già in scadenziario per le sentenze."""

from types import SimpleNamespace

from web.services.notification_legal_terms import termine_lungo_del_fascicolo, termine_per_presidio


class Scadenziario:
    def __init__(self, scadenze):
        self.scadenze = scadenze
        self.chiamate = 0

    def tutte(self, solo_aperte=False, id_fascicolo=""):
        self.chiamate += 1
        return [s for s in self.scadenze if s.id_fascicolo == id_fascicolo]


def _scadenza(id_, data, note, stato="BOZZA", fascicolo="F1"):
    return SimpleNamespace(id=id_, data_scadenza=data, note=note, stato=SimpleNamespace(value=stato), id_fascicolo=fascicolo)


def test_termine_lungo_piu_vicino_ancora_aperto():
    scadenziario = Scadenziario([
        _scadenza("S1", "2027-05-10", "SENTENZA_327:m1 deposito=2026-10-15"),
        _scadenza("S2", "2027-04-20", "SENTENZA_327:m2 deposito=2026-09-20"),
        _scadenza("S3", "2027-03-01", "SENTENZA_327:m3", stato="COMPLETATO"),
        _scadenza("S4", "2026-12-01", "altra scadenza"),
    ])
    termine = termine_lungo_del_fascicolo("F1", scadenziario)
    assert termine["date"] == "2027-04-20" and termine["state"] == "bozza da confermare"
    assert termine["href"] == "/scadenziario/S2" and "termine breve" in termine["note"]


def test_solo_presidi_su_sentenze_e_una_lettura_per_fascicolo(monkeypatch):
    scadenziario = Scadenziario([_scadenza("S1", "2027-05-10", "SENTENZA_327:m1")])
    monkeypatch.setattr("web.helpers.get_scadenziario", lambda: scadenziario)
    cache: dict = {}
    assert termine_per_presidio("judgment_to_notify_review", "F1", cache)["date"] == "2027-05-10"
    assert termine_per_presidio("judgment_short_term_review", "F1", cache)["date"] == "2027-05-10"
    assert termine_per_presidio("delivery_receipt", "F1", cache) is None
    assert scadenziario.chiamate == 1


def test_senza_scadenziario_nessun_termine():
    assert termine_lungo_del_fascicolo("F1", None) is None
    assert termine_lungo_del_fascicolo("", Scadenziario([])) is None


def test_ordine_di_notifica_nel_rito_del_lavoro_mostra_il_termine_dell_art_415(monkeypatch):
    scadenziario = Scadenziario([
        _scadenza("A", "2026-11-20", "PEC_TERMINE_PROPOSTO:m9:LAV_415_NOTIFICA_TRENTA_GIORNI"),
        _scadenza("B", "2026-11-05", "PEC_TERMINE_PROPOSTO:m9:LAV_415_NOTIFICA_DIECI_GIORNI"),
        _scadenza("C", "2027-04-01", "SENTENZA_327:m1"),
    ])
    monkeypatch.setattr("web.helpers.get_scadenziario", lambda: scadenziario)
    cache: dict = {}
    termine = termine_per_presidio("explicit_order", "F1", cache)
    assert termine["date"] == "2026-11-05" and "415" in termine["label"]
    assert termine_per_presidio("judgment_to_notify_review", "F1", cache)["date"] == "2027-04-01"


def test_termine_lungo_proposto_dalla_pec_di_cancelleria():
    """Verifica a vista del 01/11/2026: la sentenza aveva il termine lungo in scadenziario, proposto dalla PEC."""
    note = "PEC_TERMINE_PROPOSTO:msg1:CIV_APPELLO_LUNGO\nTermine proposto: Impugnazione sentenza - termine lungo"
    scadenziario = Scadenziario([
        SimpleNamespace(id="S9", data_scadenza="2027-04-29", note=note, stato=SimpleNamespace(value="BOZZA"),
                        id_fascicolo="F1", titolo="Impugnazione sentenza - termine lungo - RG 1/2026"),
        _scadenza("S8", "2026-12-01", "PEC_TERMINE_PROPOSTO:msg2:LAV_415_NOTIFICA"),
    ])
    termine = termine_lungo_del_fascicolo("F1", scadenziario)
    assert termine["date"] == "2027-04-29" and termine["href"] == "/scadenziario/S9"
    assert termine["label"].endswith("(art. 327 c.p.c.)")
