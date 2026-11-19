"""Notifiche PEC storiche: dalle ricevute verificate del gestore al registro delle notifiche e al ragionamento."""

import hashlib
import sqlite3
from types import SimpleNamespace

import pytest

from pct.notifiche_pec_storiche_prova import Invio, LetturaRelata, prova_spedizioni
from pct.registro_notifiche_storiche import registra_spedizioni
from pct.ricevute_pec_gestore import verifica_ricevuta_gestore
from tests.pec_ricevute_ca_di_prova import STUDIO, daticert, messaggio_inviato, pki, ricevuta

A, B = "ads.rc@pec.test", "ministero@pec.test"
MSGID = "<invio-1@studio.test>"
CF = "MNTGPP94L01G791A"
SENTENZA = b"%PDF-1.7 sentenza firmata"
RELATA = b"%PDF-1.7 relata firmata"
TESTO_RELATA = f"""RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994
Io sottoscritto Avv. GIUSEPPE MONTAGNESE C.F: {CF}, con studio in Taurianova
HO NOTIFICATO A
1) - AVVOCATURA DISTRETTUALE DELLO STATO C.F: 92006980806 mediante inoltro all'indirizzo pec: {A} estratto dal pubblico elenco: RegInde;
2) - MINISTERO C.F: 80185250588 mediante inoltro all'indirizzo pec: {B} estratto dal pubblico elenco: IPA;
I seguenti atti:
A) - Sentenza (File: Sentenza.PDF)
Natura del documento: Copia estratta dal fascicolo informatico
Attesto che il presente documento, da me firmato digitalmente, e' conforme alla copia digitale presente nel fascicolo informatico;
B) - Relata di notifica.
DICHIARO
Che la presente notifica e' stata inviata dal mio indirizzo PEC: studio@pec.example.test
"""


def _sha(dati):
    return hashlib.sha256(dati).hexdigest()


def _lettore(testo=TESTO_RELATA, integra=True, cf=CF):
    return lambda _dati, _nome: LetturaRelata(testo, integra, cf)


@pytest.fixture(scope="module")
def spedizione():
    p = pki()
    invio = messaggio_inviato([A, B], {"Sentenza.PDF": SENTENZA, "Relata di notifica.pdf": RELATA}, message_id=MSGID)
    rac = ricevuta(p, "accettazione", daticert("accettazione", destinatari=[A, B], msgid=MSGID))
    rdac = {d: ricevuta(p, "avvenuta-consegna", daticert("avvenuta-consegna", destinatari=[A, B], msgid=MSGID, consegna=d,
                                                         ora="10:17:24"), originale=invio) for d in (A, B)}
    ricevute = {"RAC": rac, "RDA": rdac[A], "RDB": rdac[B]}
    esiti = [verifica_ricevuta_gestore(raw, riferimento=rif, casella_studio=STUDIO, fiducia=p.fiducia, revoche=p.revoche())
             for rif, raw in ricevute.items()]
    assert all(e.verificata for e in esiti)
    return SimpleNamespace(p=p, invio=invio, esiti=esiti, ricevute=ricevute, documenti={"SEN": _sha(SENTENZA), "ALTRO": "0" * 64})


def _prova(s, *, invii=None, esiti=None, lettore=None, documenti=None):
    return prova_spedizioni(esiti if esiti is not None else s.esiti,
                            invii if invii is not None else [Invio("INV", s.invio)], casella_studio=STUDIO,
                            documenti=documenti or s.documenti, leggi_relata_file=lettore or _lettore())


def test_spedizione_provata_lega_l_atto_della_relata_con_la_stessa_impronta(spedizione):
    [esito] = _prova(spedizione)
    assert esito.provata, esito.motivo
    assert esito.data_consegna == "2026-04-20"
    assert [a["documento_id"] for a in esito.atti] == ["SEN"] and esito.atti[0]["copia_attestata"]
    assert {c["destinatario"] for c in esito.consegne} == {A, B}
    assert esito.relata["codice_fiscale"] == CF


@pytest.mark.parametrize("variante, motivo", [
    ("senza_invio", "Manca il messaggio inviato"),
    ("riferimento_diverso", "Manca il messaggio inviato"),
    ("senza_consegna_b", f"Manca la ricevuta di avvenuta consegna verificata per {B}"),
    ("relata_altro_indirizzo", "indirizzi dei destinatari nella relata"),
    ("relata_non_firmata", "non è firmata digitalmente"),
    ("relata_firmata_da_altri", "codice fiscale diverso"),
    ("atto_non_nel_fascicolo", "Nessun atto elencato nella relata"),
])
def test_dubbio_con_motivo_preciso(spedizione, variante, motivo):
    s = spedizione
    argomenti = {}
    if variante == "senza_invio":
        argomenti["invii"] = []
    elif variante == "riferimento_diverso":
        argomenti["invii"] = [Invio("INV", messaggio_inviato([A, B], {"Sentenza.PDF": SENTENZA, "Relata di notifica.pdf": RELATA},
                                                              message_id="<altro@studio.test>"))]
    elif variante == "senza_consegna_b":
        argomenti["esiti"] = [e for e in s.esiti if e.riferimento != "RDB"]
    elif variante == "relata_altro_indirizzo":
        argomenti["lettore"] = _lettore(TESTO_RELATA.replace(B, "estraneo@pec.test"))
    elif variante == "relata_non_firmata":
        argomenti["lettore"] = _lettore(integra=False)
    elif variante == "relata_firmata_da_altri":
        argomenti["lettore"] = _lettore(cf="RSSMRA80A01H501U")
    elif variante == "atto_non_nel_fascicolo":
        argomenti["documenti"] = {"ALTRO": "0" * 64}
    [esito] = _prova(s, **argomenti)
    assert not esito.provata and motivo in esito.motivo


def test_ricevuta_di_un_altro_messaggio_non_prova_la_consegna(spedizione):
    s = spedizione
    altra = ricevuta(s.p, "avvenuta-consegna", daticert("avvenuta-consegna", destinatari=[A, B], msgid="<altro@studio.test>",
                                                        consegna=B, ora="10:17:24"), originale=s.invio)
    esito_altra = verifica_ricevuta_gestore(altra, riferimento="RDB", casella_studio=STUDIO, fiducia=s.p.fiducia, revoche=s.p.revoche())
    esiti = [e for e in s.esiti if e.riferimento != "RDB"] + [esito_altra]
    esito = next(e for e in _prova(s, esiti=esiti) if e.msgid == "invio-1@studio.test")
    assert not esito.provata and B in esito.motivo


def _registro_in_memoria(monkeypatch, conn):
    from web import helpers
    from web.services import notification_presidia_runtime

    monkeypatch.setattr(helpers, "_studio_db", lambda _: SimpleNamespace(
        conn=conn, fetchall_readonly=lambda sql, params: conn.execute(sql, params).fetchall()))
    monkeypatch.setattr(notification_presidia_runtime, "_tenant_id", lambda: "studio")


def test_registro_e_consegne_verificate_con_titolo_notificato(spedizione, monkeypatch):
    from web.services.ragionamento_raccolta import _consegne_verificate

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _registro_in_memoria(monkeypatch, conn)
    spedizioni = _prova(spedizione)
    assert registra_spedizioni(conn, tenant="studio", fascicolo_id="F1", casella=STUDIO, spedizioni=spedizioni)["creati"] == 1
    [(bundle,)] = conn.execute("SELECT bundle_id FROM notification_proof_bundles").fetchall()
    assert _consegne_verificate("F1") == {"SEN": {"data": "2026-04-20", "riferimento": bundle, "titolo_esecutivo": "verificato"}}
    # Rieseguito con le stesse prove: nulla cambia.
    assert registra_spedizioni(conn, tenant="studio", fascicolo_id="F1", casella=STUDIO, spedizioni=_prova(spedizione))["invariati"] == 1
    # La ricevuta di consegna a B sparisce: il caso torna da rivedere e la prova non vale più.
    senza_b = _prova(spedizione, esiti=[e for e in spedizione.esiti if e.riferimento != "RDB"])
    assert registra_spedizioni(conn, tenant="studio", fascicolo_id="F1", casella=STUDIO, spedizioni=senza_b)["da_rivedere"] == 1
    assert _consegne_verificate("F1") == {}


def test_copia_senza_attestazione_non_e_titolo(spedizione, monkeypatch):
    from web.services.ragionamento_raccolta import _consegne_verificate

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _registro_in_memoria(monkeypatch, conn)
    testo = TESTO_RELATA.replace("Attesto che il presente documento, da me firmato digitalmente, e' conforme alla copia digitale presente nel fascicolo informatico;", "")
    registra_spedizioni(conn, tenant="studio", fascicolo_id="F1", casella=STUDIO, spedizioni=_prova(spedizione, lettore=_lettore(testo)))
    assert "titolo_esecutivo" not in _consegne_verificate("F1")["SEN"]


class _Registro:
    def __init__(self, oggetti):
        self._oggetti, self.righe = oggetti, {}

    def oggetti(self, _t, _f):
        return self._oggetti

    def impronta_fascicolo(self, _t, f, _l):
        return self.righe.get(f, {})

    def fascicolo_invariato(self, _t, f, _l, impronta, versione=None):
        riga = self.righe.get(f)
        return bool(riga) and riga["stato"] == "completa" and riga["impronta"] == impronta

    def segna_fascicolo(self, _t, f, _l, *, impronta, oggetti_totali, oggetti_letti, stato, versione, esito):
        import json
        self.righe[f] = {"impronta": impronta, "stato": stato, "esito_json": json.dumps(esito)}


def test_lavoro_in_sfondo_non_riverifica_cio_che_e_invariato(spedizione, monkeypatch):
    from pct.registro_letture.modello import Oggetto
    from web.services import notifiche_pec_storiche_runtime as runtime

    s = spedizione
    monkeypatch.setattr(runtime, "_ricalcola", lambda _f: None)
    contenuti = {"INV": s.invio, "SEN": SENTENZA, **s.ricevute}
    documenti = [SimpleNamespace(id=k, percorso=f"F1/{k}.{'pdf' if k == 'SEN' else 'eml'}", nome=k, hash_sha256=_sha(v))
                 for k, v in contenuti.items()]
    fascicolo = SimpleNamespace(id="F1", documenti=documenti)
    registro = _Registro([Oggetto("documento", k, sha256=_sha(v)) for k, v in contenuti.items()])
    chiamate = []

    def verifica(raw, **kw):
        chiamate.append(kw["riferimento"])
        return verifica_ricevuta_gestore(raw, fiducia=s.p.fiducia, revoche=s.p.revoche(), **kw)

    conn = sqlite3.connect(":memory:")
    argomenti = dict(conn=conn, tenant="studio", casella=STUDIO, registro=registro, indice=runtime.IndiceCasella(),
                     leggi_bytes=lambda _f, d: contenuti[d.id], verifica=verifica, lettore_relata=_lettore())
    primo = runtime.esamina_fascicolo(fascicolo, **argomenti)
    assert primo["provate"] == 1 and primo["creati"] == 1 and sorted(chiamate) == ["RAC", "RDA", "RDB"]
    assert runtime.esamina_fascicolo(fascicolo, **argomenti) == {"esaminato": False, "invariato": True}
    # Un documento nuovo riapre il fascicolo, ma le ricevute con la stessa impronta non si riverificano.
    registro._oggetti.append(Oggetto("documento", "NUOVO", sha256="1" * 64))
    secondo = runtime.esamina_fascicolo(fascicolo, **argomenti)
    assert secondo["invariati"] == 1 and sorted(chiamate) == ["RAC", "RDA", "RDB"]
    motivi = conn.execute("SELECT esito FROM notification_historic_checks WHERE ambito='spedizione'").fetchall()
    assert [m[0] for m in motivi] == ["provata"]


def test_consegna_dopo_le_21_si_perfeziona_alle_7_del_giorno_dopo(spedizione):
    s = spedizione
    sera = {d: ricevuta(s.p, "avvenuta-consegna", daticert("avvenuta-consegna", destinatari=[A, B], msgid=MSGID, consegna=d,
                                                           ora="21:05:00"), originale=s.invio) for d in (A, B)}
    esiti = [s.esiti[0]] + [verifica_ricevuta_gestore(raw, riferimento=f"S{d}", casella_studio=STUDIO, fiducia=s.p.fiducia,
                                                      revoche=s.p.revoche()) for d, raw in sera.items()]
    [esito] = _prova(s, esiti=esiti)
    assert esito.provata and esito.data_consegna == "2026-04-21"  # art. 147, terzo comma, c.p.c.
