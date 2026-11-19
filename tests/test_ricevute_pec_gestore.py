"""Verifica crittografica delle ricevute PEC del gestore, con ricevute vere firmate da una CA di prova."""

from datetime import datetime, timezone

import pytest
from cryptography import x509

from tests.pec_ricevute_ca_di_prova import STUDIO, daticert, messaggio_inviato, pki, ricevuta
from pct.ricevute_pec_gestore import esito_da_dizionario, verifica_ricevuta_gestore

DEST = ["controparte@pec.test", "avvocatura@pec.test"]
MSGID = "<invio-1@studio.test>"


@pytest.fixture(scope="module")
def p():
    return pki()


def _verifica(p, raw, revoche=None):
    return verifica_ricevuta_gestore(raw, riferimento="R1", casella_studio=STUDIO, fiducia=p.fiducia,
                                     revoche=revoche or p.revoche())


def _consegna(p, **altro):
    inv = messaggio_inviato(DEST, {"Sentenza.PDF": b"%PDF sentenza"})
    return ricevuta(p, "avvenuta-consegna", daticert("avvenuta-consegna", destinatari=DEST, msgid=MSGID,
                                                     consegna=DEST[0], ora="10:17:20", **altro), originale=inv)


def test_firma_valida_del_gestore_con_daticert_di_primo_livello(p):
    accettazione = _verifica(p, ricevuta(p, "accettazione", daticert("accettazione", destinatari=DEST, msgid=MSGID)))
    assert accettazione.verificata and accettazione.ricevuta.tipo == "accettazione"
    assert accettazione.ricevuta.message_id == "invio-1@studio.test"
    assert accettazione.firmatario["emittente"].endswith("CA dei gestori PEC di prova,C=IT") or "CA dei gestori" in accettazione.firmatario["emittente"]
    assert accettazione.revoche["firmatario"]["esito"] == "non revocato"
    consegna = _verifica(p, _consegna(p))
    assert consegna.verificata and consegna.ricevuta.consegna == DEST[0] and len(consegna.ricevuta.impronte) == 1
    assert consegna.ricevuta.data == datetime(2026, 4, 20, 8, 17, 20, tzinfo=timezone.utc)
    # L'esito salvato si ricostruisce identico: una ricevuta invariata non si riverifica.
    assert esito_da_dizionario(consegna.come_dizionario()).ricevuta == consegna.ricevuta


def test_firma_alterata_non_e_prova(p):
    raw = _consegna(p).replace(b"Ricevuta del gestore di prova.", b"Ricevuta del gestore di prova!")
    esito = _verifica(p, raw)
    assert not esito.verificata and esito.codice == "firma_non_valida"
    assert esito.motivo.startswith("Firma del gestore non verificabile")


def test_daticert_annidato_non_vale(p):
    raw = ricevuta(p, "accettazione", daticert("accettazione", destinatari=DEST, msgid=MSGID), annidato=True)
    esito = _verifica(p, raw)
    assert esito.codice == "daticert_assente" and not esito.verificata


def test_mittente_diverso_dalla_casella_dello_studio(p):
    raw = ricevuta(p, "accettazione", daticert("accettazione", destinatari=DEST, msgid=MSGID, mittente="altro@pec.test"))
    esito = _verifica(p, raw)
    assert esito.codice == "mittente_diverso" and esito.ricevuta is None


def test_firmatario_non_emesso_dalla_ca_dei_gestori(p):
    raw = ricevuta(p, "accettazione", daticert("accettazione", destinatari=DEST, msgid=MSGID), firmatario="estraneo")
    assert _verifica(p, raw).codice == "gestore_non_riconosciuto"


def test_revoche_controllate(p):
    raw = ricevuta(p, "accettazione", daticert("accettazione", destinatari=DEST, msgid=MSGID))
    prima = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dopo = datetime(2026, 6, 1, tzinfo=timezone.utc)
    seriale = p.gestore.serial_number
    assert _verifica(p, raw, p.revoche(((seriale, prima, x509.ReasonFlags.superseded),))).codice == "certificato_revocato"
    assert _verifica(p, raw, p.revoche(((seriale, dopo, x509.ReasonFlags.key_compromise),))).codice == "certificato_revocato"
    # Sostituzione del certificato dopo la ricevuta: la firma anteriore resta valida.
    assert _verifica(p, raw, p.revoche(((seriale, dopo, x509.ReasonFlags.superseded),))).verificata
    senza = _verifica(p, raw, lambda _f: [p.crl("radice")])
    assert senza.codice == "revoche_non_verificabili" and senza.ripetibile


def test_consegna_breve_e_file_qualunque(p):
    breve = ricevuta(p, "avvenuta-consegna", daticert("avvenuta-consegna", destinatari=DEST, msgid=MSGID, consegna=DEST[0]))
    assert _verifica(p, breve).codice == "consegna_non_completa"
    assert _verifica(p, messaggio_inviato(DEST, {"a.pdf": b"x"})).codice == "non_ricevuta"
    assert verifica_ricevuta_gestore(_consegna(p), riferimento="R", casella_studio="", fiducia=p.fiducia,
                                     revoche=p.revoche()).codice == "casella_non_configurata"
