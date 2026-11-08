"""Ricevute del deposito telematico: collegamento rigoroso al deposito e quattro PEC di ritorno.

Casi reali anonimizzati (dati dello studio, 8080, 08/11/2026): il 12/10/2026 13:08-13:09 trenta
depositi sono stati portati a CONSEGNATO dal controllo automatico senza alcuna ricevuta di
avvenuta consegna, perche' senza corrispondenze si usavano tutte le PEC della casella.
Norme: d.P.R. 68/2005; D.M. 44/2011 artt. 13-14; Specifiche DGSIA 7/8/2024 art. 17;
art. 196-sexies disp. att. c.p.c.
"""
from __future__ import annotations

import importlib.util
import logging
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.fascicoli import EsitoDepositoPCT
from pct.ricevute_deposito_pct import (
    applica_ricevute,
    classifica,
    criterio_collegamento,
    testo_messaggio as estrai_testo,
)

MSGID = "178644507416.17784.3635212909859078282@pcstudio"


def _deposito(stato: str = "INVIATO", **extra) -> EsitoDepositoPCT:
    valori = dict(
        id="CD8044C6",
        timestamp="2026-08-11T12:44:17",
        stato=stato,
        tipo_atto="RICORSO",
        pec_destinatario="tribunale.esempio@civile.ptel.giustiziacert.it",
        messaggio=f"Busta CD8044C6 inviata via PEC a tribunale.esempio@civile.ptel.giustiziacert.it. Message-ID: <{MSGID}>",
        nome_atto_principale="Ricorso.pdf.p7m",
    )
    valori.update(extra)
    return EsitoDepositoPCT(**valori)


UFFICIO = '"Per conto di: tribunale.esempio@civile.ptel.giustiziacert.it" <posta-certificata@gestore.example>'
ESTRANEO = "truffatore@mail.example"
XML_MITT = f"<EsitoAtto><IdMsgMitt>&lt;{MSGID}&gt;</IdMsgMitt></EsitoAtto>"


GESTORE = "posta-certificata@gestore.example"
UFFICIO_INTERNO = "tribunale.esempio@civile.ptel.giustiziacert.it"


def _ric(subject: str, *, rif: str = "", testo: str = "", date: str = "Tue, 11 Aug 2026 12:45:00 +0200", x: str = "",
         frm: str = GESTORE, interni: list | None = None, trasporto: str = "") -> dict:
    # Le PEC reali del Ministero contengono il messaggio dell'ufficio come postacert.eml.
    if interni is None:
        interni = [UFFICIO_INTERNO] if frm == UFFICIO else []
    return {"subject": subject, "riferimento_message_id": rif, "testo": testo, "date": date,
            "x_ricevuta": x, "x_trasporto": trasporto, "message_id": "<ric-1@gestore.example>", "from": frm,
            "mittenti_interni": interni}


# ---------------------------------------------------------------- casi reali del difetto

@pytest.mark.parametrize(
    "estranea",
    [
        "AVVISO DI MANCATA CONSEGNA: fattura cliente Rossi",
        "CONSEGNA: Re: appuntamento",
        "AVVISO DI NON ACCETTAZIONE: sollecito",
        "ACCETTAZIONE: DEPOSITO TELEMATICO - MEMORIA - RG 12/2026",
        "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO RG 99/2026",
    ],
)
def test_pec_estranee_non_cambiano_lo_stato(estranea):
    dep = _deposito()
    esito = applica_ricevute(dep, [_ric(estranea, rif="<altro@pec.example>")])
    assert esito["aggiornato"] is False
    assert dep.stato == "INVIATO"
    assert dep.ricevuta_consegna == ""


def test_casella_del_12_ottobre_non_porta_trenta_depositi_a_consegnato():
    """Trenta depositi pendenti e una casella piena di ricevute di altri messaggi: nessuno cambia."""
    depositi = [_deposito(id=f"D{n:07d}", messaggio=f"Busta inviata. Message-ID: <dep{n}@pcstudio>") for n in range(30)]
    casella = [_ric(f"CONSEGNA: DEPOSITO TELEMATICO - RICORSO - RG {n}/2026", rif=f"<estraneo{n}@pec.example>") for n in range(40)]
    casella += [_ric("AVVISO DI MANCATA CONSEGNA: fattura")]
    assert not any(applica_ricevute(d, casella)["aggiornato"] for d in depositi)
    assert {d.stato for d in depositi} == {"INVIATO"}


def test_mancata_consegna_del_deposito_non_e_mai_consegnato():
    dep = _deposito()
    applica_ricevute(dep, [_ric("AVVISO DI MANCATA CONSEGNA: DEPOSITO TELEMATICO - RICORSO", rif=f"<{MSGID}>",
                                x="errore-consegna")])
    assert dep.stato == "ERRORE"
    assert "196-sexies" in dep.note


def test_non_accettazione_del_deposito_e_errore():
    dep = _deposito()
    applica_ricevute(dep, [_ric("AVVISO DI NON ACCETTAZIONE: DEPOSITO TELEMATICO - RICORSO", rif=f"<{MSGID}>",
                                x="non-accettazione")])
    assert dep.stato == "ERRORE"


def test_consegna_non_emessa_dal_gestore_pec_ignorata():
    """Una e-mail qualunque con oggetto «CONSEGNA:» e lo stesso riferimento non e' una RdAC."""
    dep = _deposito()
    assert applica_ricevute(dep, [_ric("CONSEGNA: DEPOSITO TELEMATICO", rif=f"<{MSGID}>", frm=ESTRANEO)])["aggiornato"] is False
    assert dep.stato == "INVIATO"


def test_consegna_per_codice_nell_oggetto_non_basta():
    dep = _deposito()
    applica_ricevute(dep, [_ric("CONSEGNA: deposito CD8044C6", x="avvenuta-consegna")])
    assert dep.stato == "INVIATO"


# ---------------------------------------------------------------- le quattro PEC collegate

def test_accettazione_e_consegna_collegate_per_message_id():
    dep = _deposito()
    applica_ricevute(dep, [
        _ric("ACCETTAZIONE: DEPOSITO TELEMATICO - RICORSO", rif=f"<{MSGID}>", x="accettazione"),
        _ric("CONSEGNA: DEPOSITO TELEMATICO - RICORSO", rif=f"<{MSGID}>", x="avvenuta-consegna"),
    ])
    assert dep.stato == "CONSEGNATO"
    assert "Message-ID del messaggio di deposito" in dep.ricevuta_consegna
    assert "Oggetto: CONSEGNA:" in dep.ricevuta_consegna


def test_esito_controlli_fatal_collegato_per_idmsgmitt():
    xml = f"<EsitoAtto><IdMsgMitt>&lt;{MSGID}&gt;</IdMsgMitt><DatiEsito><MsgEsito><CodiceEsito>-5</CodiceEsito>" \
          "<DescrizioneEsito>FATAL Impossibile decifrare la busta</DescrizioneEsito></MsgEsito></DatiEsito></EsitoAtto>"
    dep = _deposito("CONSEGNATO", ricevuta_consegna="RdAC")
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO", testo=xml, frm=UFFICIO)])
    assert dep.stato == "ERRORE_CONTROLLI"
    assert dep.esito_controlli == "FATAL"
    assert "FATAL" in dep.note
    # Il modello accetta e ricarica l'esito FATAL.
    assert EsitoDepositoPCT.from_dict(dep.to_dict()).esito_controlli == "FATAL"
    # Con FATAL un successivo esito «accettazione» non rende accettato il deposito.
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO", testo=xml, frm=UFFICIO)])
    assert dep.stato == "ERRORE_CONTROLLI"


def test_esito_falso_da_mittente_estraneo_con_idbusta_giusto_non_cambia_lo_stato():
    dep = _deposito("CONSEGNATO", id_deposito_esterno="35508878", ricevuta_consegna="RdAC")
    # IdBusta corretto ma mittente estraneo e nessun IdMsgMitt: nessun effetto, solo nota «da verificare».
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO",
                                testo="IDBUSTA: 35508878 deposito accettato", frm=ESTRANEO)])
    assert dep.stato == "CONSEGNATO" and dep.ricevuta_cancelleria == ""
    assert "da verificare" in dep.note
    # Anche con IdMsgMitt giusto, un mittente estraneo non basta.
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO",
                                testo=XML_MITT + " OK controlli terminati con successo", frm=ESTRANEO)])
    assert dep.stato == "CONSEGNATO" and dep.ricevuta_controlli_automatici == ""
    # Busta esterna ministeriale ma postacert.eml interna da un estraneo: non applicato.
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO",
                                testo=XML_MITT + " WARN", frm=UFFICIO, interni=[ESTRANEO])])
    assert dep.stato == "CONSEGNATO"
    # Ufficio ministeriale ma collegamento solo per IdBusta: non applicato.
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO",
                                testo="IDBUSTA: 35508878 WARN", frm=UFFICIO)])
    assert dep.stato == "CONSEGNATO"


def test_esito_vero_da_giustiziacert_con_idmsgmitt_applicato():
    dep = _deposito("CONSEGNATO", ricevuta_consegna="RdAC")
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO",
                                testo=XML_MITT + "\nWARN: manca la procura alle liti", frm=UFFICIO,
                                interni=["tribunale.esempio@civile.ptel.giustiziacert.it"])])
    assert (dep.stato, dep.esito_controlli) == ("WARN_CONTROLLI", "WARN")
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO RG 1733/2026",
                                testo=XML_MITT, frm=UFFICIO)])
    assert dep.stato == "ACCETTATO_CANCELLERIA"


def test_esito_intervento_cancelleria_rifiuto():
    dep = _deposito("ERRORE_CONTROLLI", esito_controlli="ERROR", ricevuta_controlli_automatici="esito")
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ESITO INTERVENTO CANCELLERIA", frm=UFFICIO,
                                testo=XML_MITT + " Il deposito e' stato rifiutato dalla cancelleria")])
    assert dep.stato == "RIFIUTATO_CANCELLERIA"


def test_esito_senza_livello_non_inventa_lo_stato():
    dep = _deposito("CONSEGNATO", ricevuta_consegna="RdAC")
    applica_ricevute(dep, [_ric("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO", frm=UFFICIO,
                                testo=XML_MITT + " Codice esito: -1")])
    assert dep.stato == "CONSEGNATO"
    assert dep.esito_controlli == ""
    assert dep.ricevuta_controlli_automatici


def test_ricevuta_anteriore_all_invio_ignorata_e_rg_non_basta():
    dep = _deposito()
    vecchia = _ric("CONSEGNA: DEPOSITO TELEMATICO", rif=f"<{MSGID}>", date="Mon, 10 Aug 2026 09:00:00 +0200",
                   x="avvenuta-consegna")
    assert applica_ricevute(dep, [vecchia])["aggiornato"] is False
    assert criterio_collegamento(_ric("CONSEGNA: RG 1375/2026 Ricorso.pdf.p7m"), dep) == ""


def test_classifica_distingue_ricevuta_pec_e_esito_del_ministero():
    assert classifica("ACCETTAZIONE: DEPOSITO TELEMATICO - RICORSO")[0] == "accettazione"
    assert classifica("POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO") == ("esito_cancelleria", "ACCETTATO")
    assert classifica("AVVISO DI MANCATA CONSEGNA: x")[0] == "mancata_consegna"
    assert classifica("POSTA CERTIFICATA: Comunicazione di cancelleria RG 1/2026") == ("", "")


def test_testo_messaggio_legge_esitoatto_annidato():
    interno = EmailMessage()
    interno.set_content("corpo")
    interno.add_attachment(f"<EsitoAtto><IdMsgMitt>{MSGID}</IdMsgMitt></EsitoAtto>".encode(), maintype="application",
                           subtype="xml", filename="EsitoAtto.xml")
    esterno = EmailMessage()
    esterno["Subject"] = "POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO"
    esterno.set_content("busta di trasporto")
    esterno.add_attachment(interno, filename="postacert.eml")
    assert MSGID in estrai_testo(esterno)


# ---------------------------------------------------------------- polling e verifica del fascicolo

class _GF:
    def __init__(self, fascicoli):
        self._fascicoli = {f.id: f for f in fascicoli}
        self.salvataggi = 0

    def _salva(self):
        self.salvataggi += 1


def test_polling_solo_fascicolo_indicato_e_prove_escluse(monkeypatch):
    import pct.polling_depositi as polling

    dep_a = _deposito(id="AAAA1111")
    dep_b = _deposito(id="BBBB2222")
    prova = _deposito(id="CCCC3333", note="[PROVA SENZA INVIO REALE - nessun atto realmente inviato]")
    gf = _GF([SimpleNamespace(id="F1", depositi_pct=[dep_a, prova]), SimpleNamespace(id="F2", depositi_pct=[dep_b])])
    casella = [_ric("CONSEGNA: DEPOSITO TELEMATICO", rif=f"<{MSGID}>", x="avvenuta-consegna")]
    monkeypatch.setattr(polling, "_cerca_ricevute_imap", lambda **_k: casella)
    cfg = SimpleNamespace(imap_host="imap.example", imap_port=993, indirizzo="studio@pec.example", password="x")

    report = polling.esegui_polling(gf=gf, config_pec=cfg, fascicolo_id="F1")

    assert report["controllati"] == 1  # la prova senza invio non si controlla
    assert dep_a.stato == "CONSEGNATO"
    assert dep_b.stato == "INVIATO"  # altro fascicolo: non toccato
    assert prova.stato == "INVIATO"
    assert polling.esegui_polling(gf=gf, config_pec=cfg, fascicolo_id="")["controllati"] == 0


def test_polling_pdp_messaggio_controllato_senza_import_inesistente(caplog):
    import pct.polling_depositi as polling

    dep = _deposito(id_deposito_esterno="PDP-1", fonte_portale="PDP")
    with caplog.at_level(logging.WARNING, logger="pct.polling_depositi"):
        assert polling._poll_pdp_deposito(dep, {"p12_path": "x"}) is None
    assert "non espone un servizio" in caplog.text


def test_stima_nuovo_stato_non_modifica_il_deposito():
    import pct.polling_depositi as polling

    dep = _deposito()
    assert polling._stima_nuovo_stato(dep, [_ric("AVVISO DI MANCATA CONSEGNA: fattura cliente Rossi")]) is None
    assert polling._stima_nuovo_stato(dep, [_ric("CONSEGNA: x", rif=f"<{MSGID}>", x="avvenuta-consegna")]) == "CONSEGNATO"
    assert dep.stato == "INVIATO"


# ---------------------------------------------------------------- client PEC

def test_attendi_ricevute_senza_message_id_non_collega_nulla():
    from pct.pec import ClientPEC, ConfigPEC

    client = ClientPEC(ConfigPEC(indirizzo="a@pec.example", password="x", smtp_host="s", imap_host="imap.example"))
    esito = client.attendi_ricevute(timeout=0)
    assert esito["accettazione"] is None and esito["consegna"] is None and "info" in esito


def test_attendi_ricevute_usa_solo_x_riferimento(monkeypatch):
    import pct.pec as pec_mod

    criteri = []

    class _IMAP:
        def __init__(self, *a, **k):
            pass

        def login(self, *a):
            return "OK", []

        def select(self, *a, **k):
            return "OK", [b"2"]

        def search(self, charset, criterio):
            criteri.append(criterio)
            return "OK", [b"1 2"]

        def fetch(self, numeri, domanda):
            return "OK", [
                (b"1 (BODY[HEADER] {10}", f"Subject: CONSEGNA: DEPOSITO\r\nFrom: posta-certificata@gestore.example\r\nX-Ricevuta: avvenuta-consegna\r\nX-Riferimento-Message-ID: <{MSGID}>\r\n\r\n".encode()),
                (b"2 (BODY[HEADER] {10}", b"Subject: CONSEGNA: appuntamento\r\nX-Riferimento-Message-ID: <altro@x>\r\n\r\n"),
                b")",
            ]

        def logout(self):
            return "OK", []

    monkeypatch.setattr(pec_mod.imaplib, "IMAP4_SSL", _IMAP)
    client = pec_mod.ClientPEC(pec_mod.ConfigPEC(indirizzo="a@pec.example", password="x", smtp_host="s", imap_host="i"))
    esito = client.attendi_ricevute(timeout=1, message_id=f"<{MSGID}>")
    assert f'X-Riferimento-Message-ID "{MSGID}"' in criteri[0]
    assert esito["consegna"] and MSGID in esito["consegna"]
    assert len(esito["ricevute"]) == 1


def test_invia_busta_fissa_il_message_id(tmp_path, monkeypatch):
    import pct.pec as pec_mod

    inviati = []

    class _SMTP:
        def __init__(self, *a, **k):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            inviati.append(msg)

        def quit(self):
            pass

    monkeypatch.setattr(pec_mod, "_SMTP_SSLv4", _SMTP)
    busta = tmp_path / "busta.enc"
    busta.write_bytes(b"ENC")
    client = pec_mod.ClientPEC(pec_mod.ConfigPEC(indirizzo="avv@pec.example", password="x", smtp_host="s"))
    esito = client.invia_busta("tribunale@pec.example", str(busta), oggetto="DEPOSITO TELEMATICO - MEMORIA")
    assert esito["message_id"] and esito["message_id"] == inviati[0]["Message-ID"]
    assert inviati[0]["Subject"].startswith("DEPOSITO TELEMATICO")


# ---------------------------------------------------------------- «Controlla ricevute»

def test_controlla_ricevute_non_attribuisce_pec_del_giorno(monkeypatch):
    from flask import Flask

    import pct.polling_depositi as polling
    from web.bootstrap.deposito_receipt_routes import register_deposito_receipt_routes

    dep = _deposito()
    fascicolo = SimpleNamespace(id="F1", depositi_pct=[dep])
    gf = SimpleNamespace(get=lambda i: fascicolo if i == "F1" else None, _salva=lambda: None)
    pec = SimpleNamespace(imap_host="imap.example", imap_port=993, indirizzo="a@pec.example", password="x")
    monkeypatch.setattr(polling, "_cerca_ricevute_imap", lambda **_k: [
        _ric("CONSEGNA: Ricevuta di consegna di altra PEC", rif="<altra@pec.example>"),
        _ric("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO", testo="FATAL IDBUSTA: 999"),
    ])
    app = Flask(__name__)
    register_deposito_receipt_routes(
        app, get_fascicoli=lambda: gf,
        get_config_studio=lambda: SimpleNamespace(config=SimpleNamespace(pec=pec)), audit=lambda *a, **k: None,
    )
    risposta = app.test_client().post("/api/fascicoli/F1/depositi/CD8044C6/controlla").get_json()
    assert risposta["stato"] == "INVIATO" and risposta["aggiornato"] is False
    assert "collegata a questo deposito" in risposta["messaggio"]

    monkeypatch.setattr(polling, "_cerca_ricevute_imap", lambda **_k: [
        _ric("CONSEGNA: DEPOSITO TELEMATICO - RICORSO", rif=f"<{MSGID}>", x="avvenuta-consegna"),
    ])
    risposta = app.test_client().post("/api/fascicoli/F1/depositi/CD8044C6/controlla").get_json()
    assert risposta["stato"] == "CONSEGNATO" and risposta["ricevuta_consegna"] is True


# ---------------------------------------------------------------- riesame in sola lettura

def _script_riesame():
    percorso = Path(__file__).resolve().parents[1] / "scripts" / "riesame_stati_depositi_senza_ricevuta.py"
    spec = importlib.util.spec_from_file_location("riesame_depositi", percorso)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_riesame_classifica_i_casi_reali_senza_scrivere(tmp_path):
    riesame = _script_riesame()
    auto = "\n[AUTO 12/10/2026 13:09] Stato aggiornato automaticamente: CONSEGNATO"
    fascicoli = [{
        "id": "F1", "numero_rg": "1375", "anno_rg": "2026",
        "depositi_pct": [
            {"id": "D1", "stato": "CONSEGNATO", "messaggio": f"Message-ID: <{MSGID}>", "note": auto},
            {"id": "D2", "stato": "CONSEGNATO", "note": "[PROVA SENZA INVIO REALE - nessun atto realmente inviato]" + auto},
            {"id": "D3", "stato": "CONSEGNATO", "messaggio": "Deposito telematico: SOSTITUZIONE GIUDICE",
             "note": "PEC_DEPOSIT_CORRELATION:compound:abc" + auto},
            {"id": "D4", "stato": "CONSEGNATO", "ricevuta_consegna": "Oggetto: CONSEGNA: ...", "note": ""},
            {"id": "D5", "stato": "CONSEGNATO", "ricevuta_consegna": "12 15", "ricevuta_accettazione": "Oggetto: ACC"},
        ],
    }]
    export = tmp_path / "fascicoli.json"
    import json

    export.write_text(json.dumps(fascicoli), encoding="utf-8")
    prima = export.read_bytes()
    righe = {r["deposito"]: r for r in riesame.riesame(riesame._carica_da_json(str(export)))}
    assert export.read_bytes() == prima
    assert righe["D1"]["stato_provato"] == "INVIATO"
    assert righe["D2"]["stato_provato"] == "PROVA_SENZA_INVIO"
    assert righe["D3"]["stato_provato"] == "DA_VERIFICARE"
    assert "D4" not in righe  # stato provato dalla RdAC
    assert righe["D5"]["stato_provato"] == "ACCETTATO_PEC"  # numeri IMAP non sono una RdAC
    assert righe["D1"]["aggiornamento_automatico"] == "12/10/2026 13:09"


# ---------------------------------------------------------------- fonti e guardie

def test_fonte_specifiche_e_il_provvedimento_vigente():
    from pct.pst_catalog import PST_DM44_SPECIFICHE_LABEL, PST_DM44_SPECIFICHE_URL

    assert "7/8/2024" in PST_DM44_SPECIFICHE_LABEL and "30/09/2024" in PST_DM44_SPECIFICHE_LABEL
    assert "0004292" in PST_DM44_SPECIFICHE_URL and "04.01.24" not in PST_DM44_SPECIFICHE_URL


def test_deposito_bloccato_se_atto_principale_mancante(tmp_path):
    from pct.busta import DatiBusta
    from pct.deposito import DepositoCivile
    from pct.pec import ConfigPEC

    deposito = DepositoCivile(ConfigPEC(indirizzo="a@pec.example", password="x", smtp_host="s"), output_dir=str(tmp_path))
    dati = DatiBusta(codice_ufficio="0580010", codice_registro="CIVILE", oggetto="Memoria", tipo_atto="MEMORIA",
                     atto_principale=str(tmp_path / "non_esiste.pdf"), allegati=[], numero_rg="1", anno_rg=2026,
                     operatore="Avv. Prova", cf_mittente="RSSMRA80A01H501U")
    esito = deposito.deposita(dati, "0580010", attendi_ricevute=False)
    assert esito.stato == "ERRORE" and "PDF/A" in esito.messaggio


def test_download_pubblico_uffici_senza_percorso_del_pc():
    import json

    from web.bootstrap.telematico_local_signer_routes import pubblica_registro_uffici

    reale = (Path(__file__).resolve().parents[1] / "pct" / "data" / "uffici_ministero.json").read_text(encoding="utf-8")
    pubblico = pubblica_registro_uffici(reale)
    assert "QuickOrganizer" not in pubblico and "C:\\" not in pubblico
    dati = json.loads(pubblico)
    assert "0530010" in dati["uffici"] and dati["fonte"].startswith("Elenco degli uffici")


def test_mittente_interno_letto_da_postacert():
    from pct.ricevute_deposito_pct import mittenti_interni

    interno = EmailMessage()
    interno["From"] = "tribunale.esempio@civile.ptel.giustiziacert.it"
    interno.set_content("esito")
    esterno = EmailMessage()
    esterno.set_content("busta di trasporto")
    esterno.add_attachment(interno, filename="postacert.eml")
    assert mittenti_interni(esterno) == ["tribunale.esempio@civile.ptel.giustiziacert.it"]


# ---------------------------------------------------------------- mittente non falsificabile (revisione 08/11/2026)

ESITO_OGG = "POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO TELEMATICO"
XML_WARN = f"<EsitoAtto><IdMsgMitt>&lt;{MSGID}&gt;</IdMsgMitt><DatiEsito><MsgEsito><CodiceEsito>-1</CodiceEsito>" \
           "<DescrizioneEsito>WARN</DescrizioneEsito></MsgEsito></DatiEsito></EsitoAtto>"


def test_nome_visualizzato_ministeriale_con_indirizzo_estraneo_non_vale():
    dep = _deposito("CONSEGNATO", ricevuta_consegna="RdAC")
    finto = '"tribunale.esempio@civile.ptel.giustiziacert.it" <truffatore@mail.example>'
    applica_ricevute(dep, [_ric(ESITO_OGG, testo=XML_WARN, frm=finto, interni=[finto])])
    assert dep.stato == "CONSEGNATO"


def test_per_conto_di_valido_solo_dal_gestore():
    dep = _deposito("CONSEGNATO", ricevuta_consegna="RdAC")
    finto = '"Per conto di: tribunale.esempio@civile.ptel.giustiziacert.it" <truffatore@mail.example>'
    applica_ricevute(dep, [_ric(ESITO_OGG, testo=XML_WARN, frm=finto, interni=[UFFICIO_INTERNO])])
    assert dep.stato == "CONSEGNATO"


def test_esito_senza_postacert_interno_non_vale():
    dep = _deposito("CONSEGNATO", ricevuta_consegna="RdAC")
    applica_ricevute(dep, [_ric(ESITO_OGG, testo=XML_WARN, frm=UFFICIO, interni=[])])
    assert dep.stato == "CONSEGNATO"


def test_anomalia_del_gestore_non_vale_ne_come_esito_ne_come_ricevuta():
    dep = _deposito("CONSEGNATO", ricevuta_consegna="RdAC")
    applica_ricevute(dep, [_ric(ESITO_OGG, testo=XML_WARN, frm=UFFICIO, trasporto="errore")])
    assert dep.stato == "CONSEGNATO"
    dep2 = _deposito()
    applica_ricevute(dep2, [_ric("CONSEGNA: DEPOSITO TELEMATICO", rif=f"<{MSGID}>", x="avvenuta-consegna", trasporto="errore")])
    assert dep2.stato == "INVIATO"


def test_x_ricevuta_con_valore_non_previsto_non_e_del_gestore():
    dep = _deposito()
    applica_ricevute(dep, [_ric("CONSEGNA: DEPOSITO TELEMATICO", rif=f"<{MSGID}>", x="consegna-finta")])
    assert dep.stato == "INVIATO"
