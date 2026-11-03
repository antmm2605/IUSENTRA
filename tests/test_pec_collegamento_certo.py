"""Collegamento certo PEC → fascicolo: ruolo con anno, cliente e ufficio coincidenti (regola dell'avvocato, 02/11/2026).

Base normativa: art. 16 D.L. 179/2012 (comunicazioni di cancelleria via PEC); D.M. 44/2011.
Dati di prova sintetici: nessun dato reale di clienti.
"""

from __future__ import annotations

from email import policy
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.fascicoli import GestioneFascicoli, TipoFascicolo
from pct.pec_collegamento_certo import (
    STATO_CERTO, applica_collegamento_certo, cerca_collegamento_certo, chiave_ruolo, chiave_ufficio, nome_presente,
)
from pct.pec_collegamento_certo_riconvalida import riconvalida_collegamenti
from pct.pec_fascicolo_documenti import recupera_storico
from pct.pec_pipeline import LINK_STATI_CERTIFICATI, PecAuditRepository

UFFICIO_VICENZA = "Per conto di: tribunale.vicenza@civile.ptel.giustiziacert.it <posta-certificata@giustiziacert.it>"
PDF_DECRETO = b"%PDF-1.4\n% decreto di fissazione udienza\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _fascicolo(id_="F1", *, numero_rg="523", anno_rg="2026", cliente="Rossi Mario", tribunale="Tribunale di Vicenza"):
    return SimpleNamespace(id=id_, numero_rg=numero_rg, anno_rg=anno_rg, nome_cliente=cliente, id_cliente="",
                           tribunale=tribunale, codice_ufficio_portale="")


def _pec(*, mittente=UFFICIO_VICENZA, oggetto="POSTA CERTIFICATA: COMUNICAZIONE RG 523/2026",
         corpo="Nel procedimento promosso da Mario Rossi contro Bianchi Luca è stato emesso decreto.", profilo=None):
    return {"headers": {"from": mittente, "subject": oggetto}, "body": {"text": corpo},
            "fields": {"mittente": {"value": {"name": mittente, "email": ""}}}, "rg_candidates": [],
            "procedural_profile": profilo or {}}


# ------------------------------------------------- i tre controlli, uno per uno


def test_ruolo_normalizzato_con_anno_obbligatorio():
    assert chiave_ruolo("RG n. 0523/2026") == chiave_ruolo("523-2026") == chiave_ruolo("523/2026/LAV") == ("523", "2026")
    assert chiave_ruolo("523") is None and chiave_ruolo("") is None


@pytest.mark.parametrize("testo", ["Mario Rossi", "ROSSI MARIO", "rossi, mario", "Sig. Màrio Rossi nato a"])
def test_nome_e_cognome_in_qualunque_ordine_e_forma(testo):
    assert nome_presente("Rossi Mario", [testo])


@pytest.mark.parametrize("testo", ["Rossi", "Mario Bianchi e Luca Rossi", "Mariolino Rossi"])
def test_nome_solo_parziale_o_spezzato_non_basta(testo):
    assert not nome_presente("Rossi Mario", [testo])


def test_cliente_di_una_sola_parola_non_e_nome_e_cognome():
    assert not nome_presente("Rossi", ["Rossi Mario"])
    assert nome_presente("Alfa S.r.l.", ["ricorso di ALFA SRL"])  # sigla puntata ricomposta


@pytest.mark.parametrize(
    ("valore", "attesa"),
    [
        ("Tribunale di Reggio Calabria", "tribunale.reggiocalabria"),
        ("Tribunale Ordinario - Reggio Calabria", "tribunale.reggiocalabria"),
        ("tribunale.reggiocalabria@civile.ptel.giustiziacert.it", "tribunale.reggiocalabria"),
        ("Corte d'Appello di Reggio Calabria", "ca.reggiocalabria"),
        ("corte.appello.reggiocalabria", "ca.reggiocalabria"),
        ("depositoattipenali.gdp.palmi", "gdp.palmi"),
        ("Ufficio del Giudice di Pace di Palmi", "gdp.palmi"),
        ("unep.tribunale.palmi", "unep.tribunalepalmi"),
        ("TRIBUNALE DI MILANO Sezione Lavoro", "tribunale.milano"),
        ("cancelleria", ""),
    ],
)
def test_chiave_ufficio(valore, attesa):
    assert chiave_ufficio(valore) == attesa


# ------------------------------------------------- la regola sull'archivio


def test_tre_controlli_e_fascicolo_unico_collegamento_certo():
    esito = cerca_collegamento_certo(_pec(), [_fascicolo(numero_rg="0523"), _fascicolo("F2", numero_rg="9", cliente="Verdi Anna")])
    assert (esito["fascicolo_id"], esito["stato"], esito["ufficio_da"]) == ("F1", STATO_CERTO, "mittente")
    assert STATO_CERTO in LINK_STATI_CERTIFICATI


def test_ufficio_letto_nella_comunicazione_se_il_mittente_non_e_un_ufficio():
    pec = _pec(mittente="Avv. Neri <neri@pec.example.test>", profilo={"ufficio": "TRIBUNALE DI VICENZA"})
    assert cerca_collegamento_certo(pec, [_fascicolo()])["fascicolo_id"] == "F1"


@pytest.mark.parametrize(
    ("pec", "motivo"),
    [
        (_pec(oggetto="COMUNICAZIONE", corpo="Decreto per Mario Rossi."), "ruolo_con_anno_assente"),
        (_pec(corpo="E' stato emesso decreto."), "controlli_incompleti"),  # cliente assente
        (_pec(corpo="Procedimento contro Rossi."), "controlli_incompleti"),  # solo il cognome
        (_pec(mittente="Per conto di: tribunale.bari@civile.ptel.giustiziacert.it <p@giustiziacert.it>"), "controlli_incompleti"),
        (_pec(mittente="Per conto di: unep.tribunale.vicenza@civile.ptel.giustiziacert.it <p@giustiziacert.it>"), "controlli_incompleti"),
        (_pec(mittente="cancelleria@giustiziacert.it"), "controlli_incompleti"),  # ufficio non determinabile
        (_pec(mittente='"Tribunale di Vicenza" <tizio@example.test>'), "controlli_incompleti"),  # nome, non dominio
    ],
)
def test_manca_uno_dei_tre_nessun_collegamento_certo(pec, motivo):
    esito = cerca_collegamento_certo(pec, [_fascicolo()])
    assert (esito["fascicolo_id"], esito["motivo"]) == ("", motivo)


def test_stesso_ruolo_in_uffici_diversi_decide_l_ufficio():
    fascicoli = [_fascicolo("VI"), _fascicolo("BA", tribunale="Tribunale di Bari")]
    assert cerca_collegamento_certo(_pec(), fascicoli)["fascicolo_id"] == "VI"
    # Senza un ufficio riconoscibile i due fascicoli restano indistinti: nessuna certezza.
    assert cerca_collegamento_certo(_pec(mittente="cancelleria@giustiziacert.it"), fascicoli)["fascicolo_id"] == ""


def test_due_fascicoli_che_soddisfano_i_tre_controlli_nessuna_certezza():
    esito = cerca_collegamento_certo(_pec(), [_fascicolo("A"), _fascicolo("B")])
    assert (esito["fascicolo_id"], esito["motivo"]) == ("", "piu_fascicoli")


def test_omonimo_con_ruolo_diverso_non_si_collega():
    esito = cerca_collegamento_certo(_pec(), [_fascicolo("OMONIMO", numero_rg="999")])
    assert (esito["fascicolo_id"], esito["motivo"]) == ("", "ruolo_di_nessun_fascicolo")
    assert cerca_collegamento_certo(_pec(), [_fascicolo("OMONIMO", numero_rg="999"), _fascicolo("GIUSTO")])["fascicolo_id"] == "GIUSTO"


def test_ruolo_certificato_discordante_blocca():
    pec = _pec(profilo={"numero_ruolo_certificato": "524/2026"})  # l'XML ministeriale dice un altro ruolo
    esito = cerca_collegamento_certo(pec, [_fascicolo(), _fascicolo("ALTRO", numero_rg="524", cliente="Verdi Anna")])
    assert (esito["fascicolo_id"], esito["motivo"]) == ("", "pec_discordante")


def test_applica_solo_sugli_esiti_ordinari():
    certo = {"fascicolo_id": "F1", "stato": STATO_CERTO}
    proposta = {"fascicolo_id": "", "status": "rg_non_sufficiente", "score": 0.58, "reasons": ["RG coincidente"], "rg_only": True}
    assert applica_collegamento_certo(proposta, certo)["status"] == STATO_CERTO
    for status in ("ricevuta_destinatario_non_coincidente", "ricevuta_identificativi_ambigui", "identita_discordante"):
        assert applica_collegamento_certo({"fascicolo_id": "", "status": status}, certo)["status"] == status
    altro = {"fascicolo_id": "F9", "status": "automatico", "score": 0.9}
    assert applica_collegamento_certo(altro, certo) == altro
    assert applica_collegamento_certo(proposta, {"fascicolo_id": ""}) == proposta


# ------------------------------------------------- dal linker ai documenti del fascicolo


def _ambiente(tmp_path: Path, *, cliente="Rossi Mario"):
    gestione = GestioneFascicoli(db_path=str(tmp_path / "fascicoli.json"), documents_dir=str(tmp_path / "docs"))
    fascicolo = gestione.nuovo(titolo="Rossi / Bianchi", tipo=TipoFascicolo.CIVILE, nome_cliente=cliente,
                               tribunale="Tribunale di Vicenza", numero_rg="523", anno_rg="2026")
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="studio-prova", fascicoli_db_path=str(tmp_path / "fascicoli.json"),
                              fascicoli_docs_path=str(tmp_path / "docs"))
    return repo, gestione, fascicolo


def _mime(tag: str, *, oggetto="POSTA CERTIFICATA: COMUNICAZIONE RG 523/2026", mittente=UFFICIO_VICENZA,
          corpo="Comunicazione di cancelleria nel procedimento Rossi Mario c/ Bianchi Luca: decreto di fissazione udienza.") -> bytes:
    msg = EmailMessage()
    msg["From"] = mittente
    msg["To"] = "studio@pec.example.test"
    msg["Subject"] = oggetto
    msg["Date"] = "Mon, 02 Nov 2026 10:30:00 +0100"
    msg["Message-ID"] = f"<{tag}@example.test>"
    msg.set_content(corpo)
    msg.add_attachment(PDF_DECRETO.replace(b"decreto", tag.encode()), maintype="application", subtype="pdf", filename=f"Decreto_{tag}.pdf")
    msg.add_attachment(b"<postacert tipo=\"posta-certificata\"/>", maintype="application", subtype="xml", filename="daticert.xml")
    return msg.as_bytes(policy=policy.SMTP)


def _ingesta(repo: PecAuditRepository, mime: bytes, uid: str) -> str:
    message_id = str(repo.ingest_mime(mime, account_email="studio@pec.example.test", folder="INBOX", imap_uid=uid, actor="pytest")["id"])
    repo.run_pending_jobs(limit=40)
    return message_id


def _ultimo_esito(repo: PecAuditRepository, message_id: str) -> tuple[str, str]:
    with repo.connect() as conn:
        riga = conn.execute("SELECT status, fascicolo_id FROM pec_fascicolo_links WHERE message_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                            (message_id,)).fetchone()
    return str(riga["status"]), str(riga["fascicolo_id"])


def _documenti_da_pec(gestione: GestioneFascicoli, fascicolo_id: str, message_id: str):
    """Gli allegati salvati dalla PEC (l'.eml della comunicazione dell'ufficio entra a parte)."""
    return [doc for doc in GestioneFascicoli(db_path=str(gestione.db_path), documents_dir=str(gestione.documents_dir)).get(fascicolo_id).documenti
            if f"iusentra:pec:{message_id}" in doc.tags and not doc.nome.endswith(".eml")]


def test_linker_collega_con_certezza_e_salva_l_allegato_non_gia_presente(tmp_path):
    repo, gestione, fascicolo = _ambiente(tmp_path)
    message_id = _ingesta(repo, _mime("decreto-certo"), "INBOX:UID:1")

    assert _ultimo_esito(repo, message_id) == (STATO_CERTO, fascicolo.id)
    assert [doc.nome_originale for doc in _documenti_da_pec(gestione, fascicolo.id, message_id)] == ["Decreto_decreto-certo.pdf"]
    # Il ricalcolo del linker non sovrascrive il collegamento certo e non duplica il documento.
    risultato = repo.link_fascicolo(message_id, actor="pytest")
    assert (risultato["status"], risultato["fascicolo_documents"]["stato"]) == (STATO_CERTO, "gia_elaborato")
    assert len(_documenti_da_pec(gestione, fascicolo.id, message_id)) == 1


def test_notifica_in_proprio_collegata_con_certezza_conserva_l_eml(tmp_path):
    repo, gestione, fascicolo = _ambiente(tmp_path)
    mime = _mime("notifica-l53", oggetto="POSTA CERTIFICATA: Notificazione ai sensi della legge n. 53 del 1994 - RG 523/2026",
                 mittente="Avv. Neri <neri@pec.example.test>",
                 corpo="TRIBUNALE DI VICENZA\nNotifica dell'atto nel procedimento RG 523/2026 tra Rossi Mario e Bianchi Luca.")
    message_id = _ingesta(repo, mime, "INBOX:UID:2")

    assert _ultimo_esito(repo, message_id) == (STATO_CERTO, fascicolo.id)
    nomi = sorted(doc.nome for doc in GestioneFascicoli(db_path=str(gestione.db_path), documents_dir=str(gestione.documents_dir))
                  .get(fascicolo.id).documenti if f"iusentra:pec:{message_id}" in doc.tags)
    assert len(nomi) == 2 and sum(nome.endswith(".eml") for nome in nomi) == 1  # atto e .eml della notifica


def test_senza_cliente_nella_pec_resta_proposta_e_nulla_entra(tmp_path):
    repo, gestione, fascicolo = _ambiente(tmp_path)
    message_id = _ingesta(repo, _mime("senza-cliente", corpo="Comunicazione di cancelleria: decreto di fissazione udienza."), "INBOX:UID:3")
    assert _ultimo_esito(repo, message_id)[0] != STATO_CERTO
    assert not _documenti_da_pec(gestione, fascicolo.id, message_id)


def test_riconvalida_dello_storico_a_lotti_e_idempotente(tmp_path):
    # Il fascicolo nasce senza cliente: le PEC arrivate restano senza collegamento certo.
    repo, gestione, fascicolo = _ambiente(tmp_path, cliente="")
    ids = [_ingesta(repo, _mime(f"storico-{n}"), f"INBOX:UID:1{n}") for n in range(3)]
    assert all(_ultimo_esito(repo, mid)[0] != STATO_CERTO for mid in ids)
    vuoto = riconvalida_collegamenti(repo, limite=10)
    assert (vuoto["collegati"], vuoto["restano"]) == (0, 0)
    assert riconvalida_collegamenti(repo, limite=10)["esaminati"] == 0  # già verificate, nulla è cambiato

    # L'avvocato completa il fascicolo: l'impronta cambia e lo storico torna in coda da solo.
    gestione.aggiorna(fascicolo.id, nome_cliente="Rossi Mario")
    primo = riconvalida_collegamenti(repo, limite=2)
    assert (primo["esaminati"], primo["collegati"], primo["restano"]) == (2, 2, 1)
    esito = recupera_storico(repo, limite=10, eventi=lambda *a: None)  # il recupero notturno chiude il lotto
    assert esito["riconvalida"]["collegati"] == 1 and esito["riconvalida"]["restano"] == 0
    assert all(_ultimo_esito(repo, mid) == (STATO_CERTO, fascicolo.id) for mid in ids)
    assert all(len(_documenti_da_pec(gestione, fascicolo.id, mid)) == 1 for mid in ids)
    assert riconvalida_collegamenti(repo, limite=10)["esaminati"] == 0


def test_numero_di_ruolo_nelle_forme_ministeriali():
    """Oggetti reali delle comunicazioni di cancelleria e dei depositi (verifica a vista del 02/11/2026)."""
    from pct.pec_collegamento_certo import ruoli_della_pec

    def ruoli(oggetto):
        return ruoli_della_pec({"headers": {"subject": oggetto}, "body": {"text": ""}}, {})

    assert ruoli("POSTA CERTIFICATA: COMUNICAZIONE 2539/2025/LAV") == {("2539", "2025")}
    assert ruoli("DEPOSITO TELEMATICO: Ricorso RG: 2539 - 2025 [JQ205-L01]") == {("2539", "2025")}
    assert ruoli("Comunicazione - procedimento n. 1165/2023") == {("1165", "2023")}
    assert ruoli("Fattura n. 12/2025 del 3/2025") == set()


@pytest.mark.parametrize("testo", [
    "Numero di Ruolo generale: 2539/2025",  # corpo delle comunicazioni SICID
    "Ruolo Generale n. 2539/2025", "Numero Ruolo: 2539/2025", "R.G.L. 2539/2025", "R.G.A.C. n. 2539/2025",
    "nel procedimento iscritto al n. 2539/2025 R.G.", "N. 2539/2025 R.G.L.", "proc. n. 2539/2025",
])
def test_numero_di_ruolo_nelle_formule_per_esteso(testo):
    """Versione 3 della regola: le etichette per esteso e i registri con suffisso, sempre con l'anno a 4 cifre."""
    from pct.pec_collegamento_certo import ruoli_della_pec

    assert ruoli_della_pec({"headers": {"subject": ""}, "body": {"text": f"Tribunale. {testo}. Altro."}}, {}) == {("2539", "2025")}


@pytest.mark.parametrize("testo", ["sentenza n. 1674/2026", "ruolo di cancelliere 12/2025", "n. 12/2025 Rossi Gianni", "RG 2539/25"])
def test_numeri_senza_etichetta_di_ruolo_non_sono_ruoli(testo):
    from pct.pec_collegamento_certo import ruoli_della_pec

    assert ruoli_della_pec({"headers": {"subject": testo}, "body": {}}, {}) == set()


def test_verifiche_con_la_regola_precedente_tornano_in_coda(tmp_path):
    """Cambiata la regola (VERSIONE_REGOLA), le PEC già valutate si rivalutano: l'impronta salvata non vale più."""
    repo, _gestione, _fascicolo = _ambiente(tmp_path, cliente="")
    message_id = _ingesta(repo, _mime("vecchia-regola"), "INBOX:UID:70")
    assert riconvalida_collegamenti(repo, limite=10)["esaminati"] == 1
    with repo.connect() as conn:  # come se l'avesse valutata la versione 2 della regola
        conn.execute("UPDATE pec_collegamento_certo_verifiche SET impronta_fascicoli='impronta-versione-2', esito='ruolo_con_anno_assente'")
    # Stessi fascicoli, stessa lettura della PEC: torna in coda solo perché la regola è cambiata, e una volta sola.
    assert riconvalida_collegamenti(repo, limite=10)["esaminati"] == 1
    assert riconvalida_collegamenti(repo, limite=10)["esaminati"] == 0
    assert _ultimo_esito(repo, message_id)[0] != STATO_CERTO  # senza cliente nel fascicolo resta non certa
