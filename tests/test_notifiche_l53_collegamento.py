"""Collegamento certo delle notifiche L. 53/1994 già inviate (e delle ricevute) al fascicolo."""

from __future__ import annotations

import json
import sqlite3
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from types import SimpleNamespace

from pct.notifiche_l53_collegamento.daticert import daticert_dal_messaggio, destinatario_da_daticert
from pct.notifiche_l53_collegamento.regola import collega_tutti
from web.services import notifiche_l53_collegamento_runtime as rt

DATICERT = ('<postacert tipo="avvenuta-consegna"><intestazione><destinatari tipo="certificato">x@pec.it</destinatari>'
            '<destinatari tipo="certificato">a@mailcert.avvocaturastato.it</destinatari></intestazione>'
            '<dati><consegna>a@mailcert.avvocaturastato.it</consegna></dati></postacert>')


def _mime(xml: str = DATICERT) -> bytes:
    msg = MIMEMultipart()
    parte = MIMEApplication(xml.encode("utf-8"), "xml")
    parte.add_header("Content-Disposition", "attachment", filename="daticert.xml")
    msg.attach(parte)
    return msg.as_bytes()


def test_destinatario_dal_daticert_solo_se_unico():
    assert destinatario_da_daticert(daticert_dal_messaggio(_mime())) == "a@mailcert.avvocaturastato.it"
    due = DATICERT.replace("<dati><consegna>a@mailcert.avvocaturastato.it</consegna></dati>", "")
    assert destinatario_da_daticert(due) == ""  # due destinatari certificati e nessuna consegna: nessuna scelta
    assert daticert_dal_messaggio(b"non mime") == ""


def _m(i, originale="", sha="", mid=""):
    return {"id": i, "message_id": mid or f"<{i}@x>", "originale": originale, "sha256": sha}


def test_eml_nel_fascicolo_collega_tutto_l_invio():
    messaggi = [_m("S", mid="<orig@x>"), _m("R1", originale="<orig@x>", sha="h1"), _m("R2", originale="orig@x")]
    esito = collega_tutti(messaggi, indice_impronte={"h1": {"F1"}}, indice_message_id={}, certo_per_messaggio=lambda m: "")
    assert esito["R1"] == {"fascicolo_id": "F1", "fonte": "eml_nel_fascicolo", "motivo": "eml_nel_fascicolo"}
    assert esito["S"]["fascicolo_id"] == esito["R2"]["fascicolo_id"] == "F1"
    assert esito["R2"]["fonte"] == "stesso_invio"


def test_fail_closed_su_fascicoli_diversi():
    messaggi = [_m("R1", originale="o", sha="h1"), _m("R2", originale="o", sha="h2")]
    esito = collega_tutti(messaggi, indice_impronte={"h1": {"F1"}, "h2": {"F2"}}, indice_message_id={}, certo_per_messaggio=lambda m: "F1")
    assert all(not v["fascicolo_id"] for v in esito.values())
    stesso_eml = collega_tutti([_m("R1", sha="h1")], indice_impronte={"h1": {"F1", "F2"}}, indice_message_id={}, certo_per_messaggio=lambda m: "")
    assert stesso_eml["R1"]["fascicolo_id"] == ""


def test_tre_controlli_quando_manca_l_eml():
    messaggi = [_m("S", mid="<o@x>"), _m("R1", originale="<o@x>")]
    esito = collega_tutti(messaggi, indice_impronte={}, indice_message_id={}, certo_per_messaggio=lambda m: "F3" if m["id"] == "S" else "")
    assert esito["S"]["fonte"] == "ruolo_cliente_ufficio" and esito["R1"]["fascicolo_id"] == "F3"
    nessuno = collega_tutti([_m("Z")], indice_impronte={}, indice_message_id={}, certo_per_messaggio=lambda m: "")
    assert nessuno["Z"]["motivo"] == "nessuna_fonte_certa"


class _Repo:
    tenant_id = "t"

    def __init__(self, path):
        self.path = path

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


def test_riconvalida_registra_rilegge_il_daticert_e_non_ripete(tmp_path, monkeypatch):
    db = tmp_path / "pec_audit.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript("CREATE TABLE pec_messages (id TEXT, tenant_id TEXT, message_id_header TEXT, mime_sha256 TEXT, original_mime BLOB);"
                       "CREATE TABLE pec_parsed_versions (message_id TEXT, version INTEGER, parsed_json TEXT);")
    oggetto = "CONSEGNA: notificazione ai sensi della legge n. 53 del 1994"
    parsed = {"headers": {"subject": oggetto}, "pec_receipt": {"type": "avvenuta-consegna", "original_message_id": "<o@x>", "recipient_address": ""}}
    conn.execute("INSERT INTO pec_messages VALUES ('R1','t','<r1@x>','h1',?)", (_mime(),))
    conn.execute("INSERT INTO pec_parsed_versions VALUES ('R1',1,?)", (json.dumps(parsed),))
    conn.commit()
    conn.close()
    documento = SimpleNamespace(nome="ricevuta.eml", hash_sha256="h1", hash_contenuto_sha256="")
    fascicoli = [SimpleNamespace(id="F1", documenti=[documento], numero_rg="", anno_rg="", nome_cliente="", id_cliente="", tribunale="", codice_ufficio_portale="")]
    monkeypatch.setattr(rt, "certo_per", lambda f, leggi=None: (lambda m: ""))
    from web.services import notifiche_l53_applicazione_runtime as app_rt

    applicati = []
    monkeypatch.setattr(app_rt, "applica_collegamento", lambda repo, mid, fid, fonte: applicati.append((mid, fid, fonte)) or {"ok": True, "salvati": 2})
    primo = rt.riconvalida_notifiche_l53(_Repo(db), fascicoli=fascicoli)
    assert primo["collegati"] == 1 and primo["destinatari_riletti"] == 1 and primo["restano"] == 0
    riga = sqlite3.connect(db).execute("SELECT fascicolo_id, fonte, destinatario FROM pec_notifiche_l53_collegamenti").fetchone()
    assert riga == ("F1", "eml_nel_fascicolo", "a@mailcert.avvocaturastato.it")
    assert applicati == [("R1", "F1", "eml_nel_fascicolo")] and primo["documenti_salvati"] == 2
    assert rt.riconvalida_notifiche_l53(_Repo(db), fascicoli=fascicoli)["esaminati"] == 0


def _relata_mime(testo: str, nome: str = "relata_notifica.pdf") -> bytes:
    from io import BytesIO

    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pagina = canvas.Canvas(buffer)
    for i, riga in enumerate(testo.split("\n")):
        pagina.drawString(40, 800 - 14 * i, riga)
    pagina.save()
    msg = MIMEMultipart()
    parte = MIMEApplication(buffer.getvalue(), "pdf")
    parte.add_header("Content-Disposition", "attachment", filename=nome)
    msg.attach(parte)
    return msg.as_bytes()


RELATA = ("RELATA DI NOTIFICA ai sensi dell'art. 3-bis L. 53/1994\n"
          "Io sottoscritto avvocato, nel procedimento R.G. n. 1234/2025 pendente\n"
          "dinanzi al Tribunale di Bari Sezione Lavoro, nell'interesse di Mario Rossi\n"
          "contro Ministero dell'Istruzione e del Merito, ho notificato il ricorso.")


def _fascicolo(fid: str, tribunale: str = "Tribunale di Bari", rg: str = "1234", cliente: str = "Mario Rossi"):
    return SimpleNamespace(id=fid, numero_rg=rg, anno_rg="2025", nome_cliente=cliente, id_cliente="", tribunale=tribunale,
                           codice_ufficio_portale="", documenti=[])


def test_relata_allegata_collega_con_l_ufficio_della_relata():
    from pct.notifiche_l53_collegamento.relata import testi_dal_messaggio

    testi = testi_dal_messaggio(_relata_mime(RELATA))
    assert testi and "1234/2025" in testi[0]
    parsed = {"headers": {"subject": "notificazione ai sensi della legge n. 53 del 1994", "from": ["studio@pec.it"]}, "body": {"text": ""}}
    messaggio = {"id": "S", "parsed": parsed}
    giusto = [_fascicolo("F1"), _fascicolo("F2", tribunale="Tribunale di Lecce")]
    assert rt.certo_per(giusto, lambda _id: _relata_mime(RELATA))(messaggio) == "F1"
    assert rt.certo_per(giusto)(messaggio) == ""  # senza relata non c'è ruolo: nessun collegamento


def test_relata_ambigua_non_collega():
    due_uffici = RELATA + "\ne avverso la sentenza della Corte d'Appello di Lecce"
    messaggio = {"id": "S", "parsed": {"headers": {"subject": "x"}, "body": {"text": ""}}}
    assert rt.certo_per([_fascicolo("F1")], lambda _id: _relata_mime(due_uffici))(messaggio) == ""
    stesso_ruolo = [_fascicolo("F1"), _fascicolo("F3")]  # due fascicoli con ruolo, cliente e ufficio uguali
    assert rt.certo_per(stesso_ruolo, lambda _id: _relata_mime(RELATA))(messaggio) == ""


def test_notifica_id_nel_fascicolo():
    documento = SimpleNamespace(nome="relata.pdf", note="Notifica_ID: Ab12Cd34", descrizione="", tags=[])
    indice = rt.indice_notifica_id([SimpleNamespace(id="F9", documenti=[documento])])
    messaggi = [{"id": "S", "message_id": "<o@x>", "originale": "", "sha256": "", "oggetto": "notificazione [Notifica_ID:Ab12Cd34]"}]
    esito = collega_tutti(messaggi, indice_impronte={}, indice_message_id={}, certo_per_messaggio=lambda m: "", indice_notifica_id=indice)
    assert esito["S"] == {"fascicolo_id": "F9", "fonte": "notifica_id", "motivo": "notifica_id"}


class _RepoLink(_Repo):
    def latest_parsed_row(self, conn, message_id):
        return {"id": "v1"}

    def append_audit(self, conn, **kwargs):
        self.audit = kwargs


def _db_link(percorso, stato_precedente="", fascicolo_precedente=""):
    conn = sqlite3.connect(percorso)
    conn.executescript("CREATE TABLE pec_messages (id TEXT, tenant_id TEXT, linked_fascicolo_id TEXT, linked_fascicolo_score REAL, status TEXT);"
                       "CREATE TABLE pec_fascicolo_links (id TEXT, message_id TEXT, parsed_version_id TEXT, fascicolo_id TEXT, score REAL, "
                       "status TEXT, seeds_json TEXT, candidates_json TEXT, created_at TEXT);"
                       "INSERT INTO pec_messages VALUES ('M','t','',0,'ingested');")
    if stato_precedente:
        conn.execute("INSERT INTO pec_fascicolo_links VALUES ('L','M','v0',?,1,?,'{}','[]','2026-01-01')", (fascicolo_precedente, stato_precedente))
    conn.commit()
    conn.close()


def test_applica_collegamento_certificato_e_documenti(tmp_path, monkeypatch):
    from pct.notifiche_l53_collegamento.regola import STATO_CERTIFICATO
    from pct.pec_fascicolo_documenti import flusso
    from pct.pec_pipeline import LINK_STATI_CERTIFICATI
    from web.services.notifiche_l53_applicazione_runtime import applica_collegamento

    assert STATO_CERTIFICATO in LINK_STATI_CERTIFICATI
    chiamate = []
    monkeypatch.setattr(flusso, "processa_messaggio", lambda repo, mid, **kw: chiamate.append((mid, kw["fascicolo_id"])) or {"ok": True, "salvati": 3})
    db = tmp_path / "a.sqlite"
    _db_link(db, "proposte", "F2")
    esito = applica_collegamento(_RepoLink(db), "M", "F1", fonte="relata")
    assert esito["salvati"] == 3 and chiamate == [("M", "F1")]
    stato = sqlite3.connect(db).execute("SELECT status, fascicolo_id FROM pec_fascicolo_links ORDER BY created_at DESC LIMIT 1").fetchone()
    assert stato == (STATO_CERTIFICATO, "F1")
    altro = tmp_path / "b.sqlite"
    _db_link(altro, "manuale", "F2")
    assert applica_collegamento(_RepoLink(altro), "M", "F1", fonte="relata")["stato"] == "certificato_ad_altro_fascicolo"


def test_copia_originale_da_scaricare_e_scaricata():
    from pct.notifiche_l53_collegamento.copia_originale import voce_copia_originale

    dalla_pec = SimpleNamespace(id="D1", hash_sha256="hx", hash_contenuto_sha256="", fonte_documento="", eliminato_il="", nome="sentenza.pdf")
    fascicolo = SimpleNamespace(id="F1", numero_rg="1234", anno_rg="2025", tribunale="Tribunale di Bari", tipo="LAVORO", documenti=[dalla_pec])
    voce = voce_copia_originale(fascicolo, tipo_atto="sentenza", impronte_atto=["hx"], invio="i", documenti_dalla_pec=["D1"])
    assert voce["stato"] == "da_scaricare" and voce["ruolo"] == "1234/2025" and voce["url"].startswith("https://pst.giustizia.it/")
    assert "CNS" in voce["avvertenza"]
    dal_portale = SimpleNamespace(id="D2", hash_sha256="hy", hash_contenuto_sha256="", fonte_documento="PORTALE_TELEMATICO",
                                  eliminato_il="", nome="x.pdf", tipo_atto_portale="Sentenza", nome_portale="")
    fascicolo.documenti.append(dal_portale)
    assert voce_copia_originale(fascicolo, tipo_atto="sentenza", impronte_atto=["hx"], invio="i", documenti_dalla_pec=["D1"])["stato"] == "scaricata"
    assert voce_copia_originale(fascicolo, tipo_atto="ricorso", impronte_atto=[], invio="i") is None  # atto dello studio
