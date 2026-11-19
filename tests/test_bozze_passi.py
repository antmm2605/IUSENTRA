"""Bozze pronte per i prossimi passi: catalogo, testi a norma, registro e lavoro in sfondo.

I casi riproducono, ridotti, i fascicoli del collaudo del 18/11/2026 (note 127-ter, notifica ex art. 415 c.p.c.
alla P.A. presso l'Avvocatura dello Stato, graduatorie, spese distratte contro la P.A., precetto su decreto
ingiuntivo esecutivo). Nessun dato reale: solo le forme della Lettura.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from flask import Flask

from pct.bozze_passi import FONTE_BOZZA_PASSO, e_bozza_del_software
from pct.bozze_passi.archivio import STATO_DATI_CAMBIATI, STATO_PRONTA, ArchivioBozze, VoceBozza
from pct.bozze_passi.catalogo import bozze_del_fascicolo

OGGI = date(2026, 11, 18)


def _lettura(**sostituzioni):
    lettura = {
        "intestazione": {"numero": "2026/346", "titolo": "Di Mauro Maryam c. MIM", "rg": "1571/2026", "ufficio": "TRIBUNALE DI VICENZA",
                         "giudice": "", "sezione": "", "cliente": "Di Mauro Maryam", "controparte": "Avvocatura Distrettuale di Venezia",
                         "parti": {"difensore controparte": ["Avvocatura Distrettuale di Stato di Venezia"]}, "tipo": "lavoro",
                         "area": "Lavoro e previdenza", "codice_oggetto_pst": "222050", "stato_codice": "IN_CORSO",
                         "avvocato": "Avv. Giuseppe Montagnese"},
        "ragionamento": {"impronta": "abc", "posizione": "il cliente agisce (attore, ricorrente, creditore)", "conclusioni": [],
                         "udienze": [{"data": "09/02/2027", "modalita": "sostituita da note scritte (art. 127-ter c.p.c.)", "documento_id": "DEC1"}]},
        "documenti": {"atto_introduttivo": {"id": "RIC1", "nome": "Ricorso.pdf", "firmato": True}},
        "economico": {}, "stato_passi": {"attivi": True}, "prossimi_passi": [],
    }
    lettura.update(sostituzioni)
    return lettura


def _note(scadenza="2027-02-09", stato="da_fare"):
    giorno = f"{scadenza[8:10]}/{scadenza[5:7]}/{scadenza[:4]}"
    return {"codice": "note_127ter", "stato": stato, "onerato_codice": "tutte_le_parti", "cosa": "Depositare le note scritte",
            "letto": {"documento_id": "DEC1", "documento": "4194926s.pdf", "data": "09/10/2026", "tipo": "documento"},
            "termine": {"scadenza_iso": scadenza, "scadenza": giorno, "ora_assegnata": "14:00"}, "norme": [], "dubbi": []}


def test_note_127_ter_sole_istanze_e_conclusioni_con_dati_certi_e_segnaposti():
    lettura = _lettura(prossimi_passi=[{"azione": "Depositare le note scritte ex art. 127-ter c.p.c. (sole istanze e conclusioni)", "entro": "09/02/2027"}])
    lettura["ragionamento"]["conclusioni"] = [_note()]
    [bozza] = bozze_del_fascicolo(lettura, oggi=OGGI)
    assert bozza.chiave == "note_127ter:2027-02-09" and bozza.modello == "builtin-tmp-civ-012"
    assert "# Tribunale di Vicenza" in bozza.testo and "R.G. n. 1571/2026" in bozza.testo
    assert "sole istanze e conclusioni (art. 127-ter, primo comma, c.p.c.)" in bozza.testo
    assert "09/02/2027 entro le ore 14:00" in bozza.testo
    # L'Avvocatura è il difensore, non la parte: l'amministrazione resta da completare con l'indicazione del titolo.
    assert "[da completare: amministrazione convenuta (nel titolo del fascicolo: «MIM»)]" in bozza.testo
    assert "difesa dall'Avvocatura Distrettuale dello Stato di Venezia" in bozza.testo
    assert "giudice designato" in bozza.segnaposti and "conclusioni, come nell'atto introduttivo e negli scritti successivi" in bozza.segnaposti
    assert bozza.passi(lettura["prossimi_passi"]) == [{"azione": lettura["prossimi_passi"][0]["azione"], "entro": "09/02/2027"}]


def test_nessuna_bozza_per_termine_decorso_adempimento_fatto_o_fascicolo_chiuso():
    lettura = _lettura()
    lettura["ragionamento"]["conclusioni"] = [_note("2026-11-03"), _note("2026-12-16", stato="fatto")]
    assert bozze_del_fascicolo(lettura, oggi=OGGI) == []
    chiuso = _lettura()
    chiuso["ragionamento"]["conclusioni"] = [_note()]
    chiuso["intestazione"]["stato_codice"] = "ARCHIVIATO"
    assert bozze_del_fascicolo(chiuso, oggi=OGGI) == []
    assert bozze_del_fascicolo({"ragionamento": {}}, oggi=OGGI) == []


def test_relata_ex_art_3_bis_alla_pa_presso_l_avvocatura_e_testo_della_pec():
    lettura = _lettura(prossimi_passi=[{"azione": "Completare la notifica ordinata dal giudice entro il 08/01/2027 («4194926s.pdf.zip»)", "entro": "08/01/2027"}])
    lettura["ragionamento"]["conclusioni"] = [{
        "codice": "notifica_ricorso_decreto_415", "stato": "da_fare", "onerato_codice": "noi",
        "letto": {"documento_id": "DEC1", "documento": "4194926s.pdf", "data": "09/10/2026", "tipo": "documento"},
        "termine": {"scadenza_iso": "2026-10-19", "scadenza": "19/10/2026", "scaduto": True}, "norme": [],
    }]
    [bozza] = bozze_del_fascicolo(lettura, oggi=OGGI, studio={"cf_avvocato": "MNTGPP94L01G791A", "pec": "avv@pec.it"})
    assert bozza.modello == "builtin-tmp-not-003"
    assert "RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994" in bozza.testo
    assert "presso l'Avvocatura Distrettuale dello Stato di Venezia" in bozza.testo
    assert "MNTGPP94L01G791A" in bozza.testo and "avv@pec.it" in bozza.testo
    assert "**Oggetto:** notificazione ai sensi della legge n. 53 del 1994" in bozza.testo
    assert "Ricorso.pdf" in bozza.testo and "4194926s.pdf" in bozza.testo
    assert "codice fiscale della parte che ha conferito la procura" in bozza.segnaposti
    assert not any("dato mancante" in voce for voce in bozza.segnaposti)
    assert bozza.passi(lettura["prossimi_passi"])  # il passo del presidio notifiche, con la sua data


def test_nota_di_deposito_una_sola_per_lo_stesso_deposito_richiesto_due_volte():
    def deposito(data_prov, scadenza):
        return {"codice": "deposito_ordinato", "stato": "da_fare", "onerato_codice": "noi",
                "cosa": "Depositare le graduatorie aggiornate o ulteriore prova della permanenza nel sistema scolastico",
                "letto": {"documento_id": f"P{scadenza}", "documento": "prov.pdf", "data": data_prov},
                "termine": {"scadenza_iso": scadenza, "scadenza": f"{scadenza[8:]}/{scadenza[5:7]}/{scadenza[:4]}",
                            "scaduto": True, "natura": "ordinatorio"}}
    lettura = _lettura(prossimi_passi=[{"azione": "Depositare le graduatorie aggiornate", "entro": "23/10/2026"},
                                       {"azione": "Depositare le graduatorie aggiornate nelle quali", "entro": "16/11/2026"}])
    lettura["ragionamento"]["conclusioni"] = [deposito("12/10/2026", "2026-10-23"), deposito("04/11/2026", "2026-11-16")]
    [bozza] = bozze_del_fascicolo(lettura, oggi=OGGI)
    assert bozza.modello == "CIV_ORD_015" and "cpc_421" in bozza.fonti
    assert "in esecuzione del provvedimento del 04/11/2026" in bozza.testo and "fino al 16/11/2026" in bozza.testo
    assert any("è scaduto (ordinatorio)" in voce for voce in bozza.segnaposti)
    assert len(bozza.passi(lettura["prossimi_passi"])) == 2


def test_contributo_da_chiarire_non_produce_bozze():
    lettura = _lettura()
    lettura["ragionamento"]["conclusioni"] = [{"codice": "contributo_unificato", "stato": "dubbio", "onerato_codice": "noi",
                                               "prova_o_motivo": "la ricevuta riporta € 27,00 ... dovuti € 98,00"}]
    assert bozze_del_fascicolo(lettura, oggi=OGGI) == []


def test_spese_distratte_contro_la_pa_richiesta_di_pagamento_e_precetto_dopo_120_giorni():
    lettura = _lettura(stato_passi={"attivi": False, "motivo": "Credito di € 515,00 liquidato dal giudice non ancora incassato"},
                       economico={"liquidazione": {"stato": "da_incassare", "importo": 515.0, "fonte": "Sentenza del 17/04/2026", "pagato": False,
                                                   "nota": "che liquida in € 515,00 per compenso di avvocato, oltre rimborso forfettario"}})
    lettura["intestazione"].update(controparte="MIM", ufficio="TRIBUNALE DI REGGIO DI CALABRIA", rg="161/2026",
                                   parti={"difensore controparte": ["Avvocatura Distrettuale Di Stato Di Reggio Calabria",
                                                                    "Avvocatura Distrettuale dello Stato di Reggio Calabria"]})
    conto = {"righe": [{"voce": "sentenza", "stato": "Distratte in favore dell'avvocato",
                        "dettaglio": "Oltre all'importo spettano gli accessori (senza IVA per il regime forfetario dello studio)"}]}
    richiesta, precetto = bozze_del_fascicolo(lettura, oggi=OGGI, conto=conto, studio={"regime_fiscale": "RF19"})
    assert richiesta.modello == "STR_020" and precetto.modello == "ESE_003"
    for bozza in (richiesta, precetto):
        assert "€ 515,00" in bozza.testo and "€ 77,25" in bozza.testo and "€ 23,69" in bozza.testo and "€ 615,94" in bozza.testo
        assert "non dovuta (regime forfetario dello studio)" in bozza.testo
    assert "antistatario (art. 93 c.p.c.)" in richiesta.testo and "Avvocatura Distrettuale dello Stato di Reggio Calabria" in richiesta.testo
    assert "art. 14, comma 1, D.L. 669/1996" in richiesta.testo
    assert "art. 480, secondo comma, c.p.c." in precetto.testo and "Elegge domicilio in [da completare:" in precetto.testo
    assert any("centoventi giorni" in voce for voce in precetto.segnaposti)
    assert "data della notificazione del titolo esecutivo" in precetto.segnaposti


def test_precetto_su_decreto_ingiuntivo_esecutivo_menziona_l_esecutorieta_art_654():
    lettura = _lettura()
    lettura["intestazione"].update(cliente="Associazione Italiana Maestri Cattolici", controparte="D&M Academy Form srl",
                                   ufficio="GIUDICE DI PACE DI PALMI", rg="4202/2024", tipo="civile", parti={}, area="Procedimenti speciali sommari")
    lettura["ragionamento"]["conclusioni"] = [
        {"codice": "precetto", "stato": "da_fare", "onerato_codice": "noi",
         "letto": {"brano": "Decreto di esecutorieta' n. cronol. 1243/2025 del 12/03/2025 RG n. 4202/2024 Nella causa promossa da: "
                            "ASSOCIAZIONE ITALIANA MAESTRI CATTOLICI (CF 92043820791)-Avv. X contro D&M ACADEMY FORM S.R.L. (CF 03021420801) "
                            "Visto il decreto ingiuntivo n. 1109/2024, emesso"}},
        {"codice": "spese_liquidate", "stato": "da_fare", "onerato_codice": "noi",
         "cosa": "Riscuotere le spese liquidate dal giudice: € 300,00 di compensi e € 76,00 di spese oltre accessori di legge",
         "letto": {"brano": "decreto 1) La somma complessiva di € 2.400,00 oltre interessi come da domanda. 2) Le spese"}},
    ]
    [bozza] = bozze_del_fascicolo(lettura, oggi=OGGI)
    assert bozza.modello == "MON_018" and "cpc_654" in bozza.fonti
    assert "decreto ingiuntivo n. 1109/2024" in bozza.testo
    assert "dichiarato esecutivo con decreto n. cronol. 1243/2025 del 12/03/2025 (art. 654, secondo comma, c.p.c.)" in bozza.testo
    assert "(C.F. 92043820791)" in bozza.testo and "(C.F. 03021420801)" in bozza.testo
    assert "sorte capitale: € 2.400,00" in bozza.testo and "compenso liquidato: € 300,00" in bozza.testo
    # «oltre accessori di legge» non dice il rimborso forfettario: niente 15% supposto, segnaposto (19/11/2026).
    assert "€ 45,00" not in bozza.testo and any("rimborso forfettario" in voce for voce in bozza.segnaposti)
    assert "I.V.A. sul compenso, se dovuta, secondo il regime fiscale" in bozza.segnaposti  # regime non letto: segnaposto


def test_le_bozze_del_software_restano_fuori_dalla_lettura_e_dai_motori():
    from pct.registro_letture.inventario import oggetto_da_documento

    bozza = SimpleNamespace(id="D1", fonte_documento=FONTE_BOZZA_PASSO, nome="precetto.html", hash_sha256="a" * 64,
                            hash_contenuto_sha256="b" * 64, dimensione_bytes=10, tipo="ATTO_GIUDIZIARIO")
    assert e_bozza_del_software(bozza) and e_bozza_del_software({"fonte_documento": "BOZZA_NOTE_127_TER"})
    assert oggetto_da_documento(bozza, {}) is None
    atto = SimpleNamespace(**{**bozza.__dict__, "fonte_documento": "CARICAMENTO_STUDIO"})
    assert oggetto_da_documento(atto, {}) is not None


def test_registro_delle_bozze_conserva_stato_passi_e_impronte(tmp_path):
    archivio = ArchivioBozze(tmp_path / "intelligence" / "bozze_passi.sqlite")
    assert archivio.del_fascicolo("F1") == []
    voce = VoceBozza(fascicolo_id="F1", chiave="note_127ter:2027-02-09", documento_id="D1", tipo="note_127ter", titolo="Note",
                     modello="builtin-tmp-civ-012", modello_titolo="Note d'udienza", da_completare=["conclusioni"],
                     passi=[{"azione": "Depositare", "entro": "09/02/2027"}], impronta_testo="t", impronta_contenuto="c",
                     creata_il="2026-11-18T10:00:00+01:00", aggiornata_il="2026-11-18T10:00:00+01:00")
    archivio.salva(voce)
    voce.stato = STATO_DATI_CAMBIATI
    archivio.salva(voce)
    [letta] = archivio.del_fascicolo("F1")
    assert letta.stato == STATO_DATI_CAMBIATI and letta.passi == voce.passi and letta.da_completare == ["conclusioni"]
    archivio.elimina("F1", voce.chiave)
    assert archivio.del_fascicolo("F1") == []


class _Repository:
    def __init__(self):
        self.documenti: dict[str, SimpleNamespace] = {}
        self.cestino: list[str] = []

    def get(self, fascicolo_id):
        return SimpleNamespace(id=fascicolo_id, id_cliente="", documenti=list(self.documenti.values()))

    def rimuovi_documento(self, fascicolo_id, documento_id, eliminato_da=""):
        self.cestino.append(documento_id)
        self.documenti.pop(documento_id)


@pytest.fixture()
def ambiente(monkeypatch, tmp_path):
    from web.services import bozze_passi_runtime as runtime

    repository = _Repository()
    contatore = {"n": 0, "riscritture": 0}

    def crea(repo, fascicolo_id, bozza):
        contatore["n"] += 1
        documento_id = f"D{contatore['n']}"
        repo.documenti[documento_id] = SimpleNamespace(id=documento_id, nome=f"{documento_id}.pdf", hash_contenuto_sha256=bozza.impronta)
        return documento_id, bozza.impronta, f"<p>{bozza.titolo}</p>"

    def riscrivi(repo, fascicolo_id, documento, bozza):
        contatore["riscritture"] += 1
        documento.hash_contenuto_sha256 = bozza.impronta
        return bozza.impronta, f"<p>{bozza.titolo}</p>"

    monkeypatch.setattr("web.helpers.get_fascicoli", lambda: repository)
    monkeypatch.setattr(runtime, "_crea_documento", crea)
    monkeypatch.setattr(runtime, "_riscrivi_documento", riscrivi)
    monkeypatch.setattr(runtime, "dati_studio", dict)
    monkeypatch.setattr(runtime, "_cliente_cf", lambda _f: "")
    monkeypatch.setattr(runtime, "_segnala_documenti", lambda _f: None)
    app = Flask(__name__)
    with app.test_request_context("/"):
        yield runtime, repository, ArchivioBozze(tmp_path / "bozze.sqlite"), contatore


def test_lavoro_in_sfondo_crea_rigenera_solo_se_non_toccata_e_segnala_i_dati_cambiati(ambiente):
    runtime, repository, archivio, contatore = ambiente
    lettura = _lettura(prossimi_passi=[{"azione": "Depositare le note scritte ex art. 127-ter c.p.c.", "entro": "09/02/2027"}])
    lettura["ragionamento"]["conclusioni"] = [_note()]
    assert runtime.prepara_bozze_fascicolo("F1", lettura=lettura, archivio=archivio, oggi=OGGI)["create"] == 1
    assert runtime.prepara_bozze_fascicolo("F1", lettura=lettura, archivio=archivio, oggi=OGGI)["invariate"] == 1
    # Cambia una fonte (il giudice designato): la bozza non toccata si riscrive.
    lettura["intestazione"]["giudice"] = "Mario Rossi"
    assert runtime.prepara_bozze_fascicolo("F1", lettura=lettura, archivio=archivio, oggi=OGGI)["aggiornate"] == 1
    assert contatore["riscritture"] == 1
    # L'avvocato la salva nell'editor, poi cambiano ancora i dati: la sua versione resta.
    [documento] = repository.documenti.values()
    documento.hash_contenuto_sha256 = "salvata-dall-avvocato"
    lettura["intestazione"]["giudice"] = "Anna Bianchi"
    assert runtime.prepara_bozze_fascicolo("F1", lettura=lettura, archivio=archivio, oggi=OGGI)["dati_cambiati"] == 1
    assert contatore["riscritture"] == 1
    [voce] = archivio.del_fascicolo("F1")
    assert voce.stato == STATO_DATI_CAMBIATI and voce.dati_cambiati_il


def test_passo_chiuso_bozza_non_toccata_nel_cestino_e_vista_del_registro(ambiente, monkeypatch):
    runtime, repository, archivio, _contatore = ambiente
    lettura = _lettura(prossimi_passi=[{"azione": "Depositare le note scritte", "entro": "09/02/2027"}])
    lettura["ragionamento"]["conclusioni"] = [_note()]
    runtime.prepara_bozze_fascicolo("F1", lettura=lettura, archivio=archivio, oggi=OGGI)
    monkeypatch.setattr(runtime, "archivio_corrente", lambda *_a: archivio)
    [vista] = runtime.payload_bozze("F1")["bozze"]
    assert vista["stato"] == STATO_PRONTA and vista["apri"] == "/fascicoli/F1/documenti/D1/editor"
    assert vista["preparataIl"].count("/") == 2 and vista["passi"] == [{"azione": "Depositare le note scritte", "entro": "09/02/2027"}]
    lettura["ragionamento"]["conclusioni"] = [_note(stato="fatto")]
    assert runtime.prepara_bozze_fascicolo("F1", lettura=lettura, archivio=archivio, oggi=OGGI)["superate"] == 1
    assert repository.cestino == ["D1"] and archivio.del_fascicolo("F1") == []


# --- Bozze in PDF (richiesta dell'avvocato del 19/11/2026) -------------------------------------------------------

class _RepositoryReale(_Repository):
    """Archivio minimo con file veri: il PDF della bozza si scrive e si rilegge come nel fascicolo."""

    def __init__(self, cartella):
        super().__init__()
        self.cartella = cartella

    def percorso_documento(self, fascicolo_id, documento_id):
        return self.cartella / f"{documento_id}.bin"

    percorso_documento_lettura = percorso_documento

    def aggiungi_documento(self, fascicolo_id, nome_file, tipo, contenuto, **campi):
        documento_id = f"D{len(self.documenti) + 1}"
        self.percorso_documento(fascicolo_id, documento_id).write_bytes(contenuto)
        self.documenti[documento_id] = SimpleNamespace(id=documento_id, nome=nome_file, tipo=tipo, versioni=[], **campi)
        return self.documenti[documento_id]

    def sostituisci_documento(self, fascicolo_id, documento_id, *, nome_file, contenuto, hash_contenuto_sha256, **campi):
        documento = self.documenti[documento_id]
        documento.versioni.append(documento.nome)
        self.percorso_documento(fascicolo_id, documento_id).write_bytes(contenuto)
        documento.nome, documento.hash_contenuto_sha256 = nome_file, hash_contenuto_sha256
        documento.note = campi.get("note", "")
        return documento


@pytest.fixture()
def ambiente_pdf(monkeypatch, tmp_path):
    from web.services import bozze_passi_runtime as runtime

    repository = _RepositoryReale(tmp_path)
    archivio = ArchivioBozze(tmp_path / "bozze.sqlite")
    monkeypatch.setattr("web.helpers.get_fascicoli", lambda: repository)
    monkeypatch.setattr(runtime, "dati_studio", dict)
    monkeypatch.setattr(runtime, "_cliente_cf", lambda _f: "")
    monkeypatch.setattr(runtime, "_segnala_documenti", lambda _f: None)
    monkeypatch.setattr(runtime, "archivio_corrente", lambda *_a: archivio)
    app = Flask(__name__)
    with app.test_request_context("/"):
        yield runtime, repository, archivio


def _testo_pdf(dati: bytes) -> str:
    import fitz

    with fitz.open(stream=dati, filetype="pdf") as pdf:
        return " ".join(pagina.get_text() for pagina in pdf)


def _lettura_note():
    lettura = _lettura(prossimi_passi=[{"azione": "Depositare le note scritte ex art. 127-ter c.p.c.", "entro": "09/02/2027"}])
    lettura["ragionamento"]["conclusioni"] = [_note()]
    return lettura


def test_la_bozza_entra_nel_fascicolo_come_pdf_con_i_segnaposti_evidenti(ambiente_pdf):
    runtime, repository, archivio = ambiente_pdf
    assert runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)["create"] == 1
    [documento] = repository.documenti.values()
    assert documento.nome.endswith(".pdf") and documento.fonte_documento == FONTE_BOZZA_PASSO
    grezzo = repository.percorso_documento("F1", documento.id).read_bytes()
    assert grezzo.startswith(b"%PDF-")
    testo = _testo_pdf(grezzo)
    assert "BOZZA DA RIVEDERE E FIRMARE" in testo and "non inviata, depositata né notificata" in testo
    [voce] = archivio.del_fascicolo("F1")
    assert voce.formato == "pdf" and "<" in voce.testo_html and voce.da_completare
    # Ogni segnaposto della bozza è nel PDF ed è contato nel riquadro iniziale.
    assert f"{len(voce.da_completare)} dati da completare" in testo or "1 dato da completare" in testo
    assert all(f"[da completare: {m}" in " ".join(testo.split()) for m in voce.da_completare[:2])
    # Il giro successivo non riscrive nulla: il PDF è deterministico.
    assert runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)["invariate"] == 1


def test_pdf_delle_bozze_evidenzia_i_segnaposti_e_e_deterministico():
    from pct.bozze_passi.pdf import blocchi_da_html, bozza_pdf, nome_file_pdf

    html = ("<section><h1>Atto di precetto</h1><p>*(artt. 474 e 480 c.p.c.)*</p>"
            "<p>a <strong>MIM</strong>, <mark>[da completare: sede dell&#x27;amministrazione]</mark></p><ul><li>compenso</li></ul></section>")
    blocchi = blocchi_da_html(html)
    assert blocchi[0][0] == "h1" and blocchi[-1] == ("li", "compenso", True)
    assert bozza_pdf("Precetto", html) == bozza_pdf("Precetto", html)
    testo = _testo_pdf(bozza_pdf("Precetto", html))
    assert "[da completare: sede dell'amministrazione]" in testo and "1 dato da completare" in testo
    assert "*" not in testo  # il corsivo del modello non lascia asterischi
    assert nome_file_pdf("Atto di precetto contro la P.A.") == "atto_di_precetto_contro_la_p.a.pdf"


def test_il_salvataggio_dall_editor_rigenera_il_pdf_e_protegge_la_versione_dell_avvocato(ambiente_pdf):
    runtime, repository, archivio = ambiente_pdf
    runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
    [documento] = repository.documenti.values()
    esito = runtime.salva_dall_editor("F1", documento.id, "<p>Note scritte corrette dall'avvocato.</p>", autore="avv")
    assert esito == {"ok": True, "nome": documento.nome, "formato": "pdf", "daCompletare": []}
    assert "corrette dall'avvocato" in _testo_pdf(repository.percorso_documento("F1", documento.id).read_bytes())
    [voce] = archivio.del_fascicolo("F1")
    assert "corrette dall" in voce.testo_html and voce.stato == "modificata"
    # Cambiano i dati del fascicolo: la versione dell'avvocato resta, la bozza segnala i dati cambiati.
    lettura = _lettura_note()
    lettura["intestazione"]["giudice"] = "Anna Bianchi"
    assert runtime.prepara_bozze_fascicolo("F1", lettura=lettura, archivio=archivio, oggi=OGGI)["dati_cambiati"] == 1
    assert "corrette dall'avvocato" in _testo_pdf(repository.percorso_documento("F1", documento.id).read_bytes())


@pytest.mark.parametrize("toccata", [False, True])
def test_le_bozze_html_gia_create_diventano_pdf_al_giro_senza_perdere_le_modifiche(ambiente_pdf, toccata):
    import hashlib

    runtime, repository, archivio = ambiente_pdf
    html = "<p>Precetto</p><p>Sede: <mark>[da completare: sede]</mark></p>" + ("<p>Aggiunta dell'avvocato.</p>" if toccata else "")
    documento = repository.aggiungi_documento("F1", "atto_di_precetto.html", "ATTO_GIUDIZIARIO", html.encode(),
                                              fonte_documento=FONTE_BOZZA_PASSO)
    originale = hashlib.sha256(b"<p>Precetto</p><p>Sede: <mark>[da completare: sede]</mark></p>").hexdigest()
    documento.hash_contenuto_sha256 = hashlib.sha256(html.encode()).hexdigest()
    archivio.salva(VoceBozza(fascicolo_id="F1", chiave="precetto_pa:x", documento_id=documento.id, tipo="precetto_pa",
                             titolo="Atto di precetto", modello="m", modello_titolo="Precetto", impronta_testo="t",
                             impronta_contenuto=originale, creata_il="2026-11-18T10:00:00+01:00",
                             aggiornata_il="2026-11-18T10:00:00+01:00"))
    assert [v.chiave for v in archivio.da_convertire()] == ["precetto_pa:x"]
    assert runtime.converti_bozze_html(archivio) == 1
    assert documento.nome == "atto_di_precetto.pdf" and documento.versioni == ["atto_di_precetto.html"]
    testo = _testo_pdf(repository.percorso_documento("F1", documento.id).read_bytes())
    assert "[da completare: sede]" in testo and (("Aggiunta dell'avvocato." in testo) is toccata)
    [voce] = archivio.del_fascicolo("F1")
    assert voce.formato == "pdf" and voce.da_completare == ["sede"] and archivio.da_convertire() == []
    assert runtime._toccata(documento, voce) is toccata
    assert runtime.converti_bozze_html(archivio) == 0


def test_l_editor_apre_il_testo_della_bozza_e_non_il_pdf(ambiente_pdf, monkeypatch):
    from web.services.react_document_editor_bridge import build_react_document_editor_payload

    runtime, repository, archivio = ambiente_pdf
    runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
    [documento] = repository.documenti.values()
    documento.tipo, documento.fonte_documento = "ATTO_GIUDIZIARIO", FONTE_BOZZA_PASSO
    payload = build_react_document_editor_payload(get_fascicoli=lambda: repository, id_fasc="F1", id_doc=documento.id)
    assert payload["document"]["editable"] is True and payload["document"]["extension"] == "pdf"
    assert payload["endpoints"]["save"] == payload["endpoints"]["loadHtml"] == f"/api/v1/ui/fascicoli/F1/bozze-passi/{documento.id}/testo"
    assert "pdfOverlay" not in payload["endpoints"] and any("rigenera" in w for w in payload["warnings"])
    [vista] = runtime.payload_bozze("F1")["bozze"]
    assert vista["pdf"] == f"/fascicoli/F1/documenti/{documento.id}/visualizza"



# --- Correzioni del precetto dopo la rilettura da avvocato (19/11/2026) -----------------------------------------

def _lettura_credito_pa(nota="oltre rimborso forfettar", conclusioni=()):  # troncato come nella Lettura reale di 9A681FDF
    lettura = _lettura(stato_passi={"attivi": False},
                       economico={"liquidazione": {"stato": "da_incassare", "importo": 515.0, "fonte": "Sentenza del 17/04/2026",
                                                   "pagato": False, "nota": f"che liquida in € 515,00 per compenso, {nota}"}})
    lettura["intestazione"].update(controparte="MIM", ufficio="TRIBUNALE DI REGGIO DI CALABRIA", rg="161/2026",
                                   parti={"difensore controparte": ["Avvocatura Distrettuale dello Stato di Reggio Calabria"]})
    lettura["ragionamento"]["conclusioni"] = list(conclusioni)
    return lettura


_CONTO_DISTRATTE = {"righe": [{"voce": "sentenza", "stato": "Distratte in favore dell'avvocato", "dettaglio": ""}]}
_STUDIO = {"regime_fiscale": "RF19", "citta": "Taurianova", "indirizzo_completo": "Via Nino Bixio 4, 89029 Taurianova (RC)"}


def test_precetto_elegge_domicilio_nel_comune_del_giudice_dell_esecuzione_art_480_terzo_comma():
    from pct.bozze_passi import testi
    from pct.bozze_passi.contesto import Contesto

    _richiesta, precetto = bozze_del_fascicolo(_lettura_credito_pa(), oggi=OGGI, conto=_CONTO_DISTRATTE, studio=_STUDIO)
    assert "Elegge domicilio in [da completare: indirizzo nel comune sede del giudice dell’esecuzione" in precetto.testo
    assert "(art. 480, terzo comma, c.p.c.)" in precetto.testo and "Giudice competente per l'esecuzione" not in precetto.testo
    # Comune certo e uguale alla sede dello studio: il domicilio è lo studio, senza segnaposto.
    ctx = Contesto(studio=_STUDIO)
    assert testi.elezione_domicilio(ctx, {"comune_esecuzione": "Taurianova"}) == (
        "Elegge domicilio presso lo studio del difensore in Via Nino Bixio 4, 89029 Taurianova (RC) (art. 480, terzo comma, c.p.c.).")
    assert "[da completare:" in testi.elezione_domicilio(ctx, {"comune_esecuzione": "Reggio Calabria"})


def test_il_ministero_si_indica_per_esteso_in_persona_del_ministro():
    from pct.bozze_passi.amministrazioni import denominazione, rappresentante

    richiesta, precetto = bozze_del_fascicolo(_lettura_credito_pa(), oggi=OGGI, conto=_CONTO_DISTRATTE, studio=_STUDIO)
    assert "**Ministero dell'Istruzione e del Merito, in persona del Ministro pro tempore**" in precetto.testo
    assert "Spett.le **Ministero dell'Istruzione e del Merito**" in richiesta.testo
    assert "MIM" not in precetto.testo and "legale rappresentante" not in precetto.testo
    assert denominazione("MINISTERO DELL'ECONOMIA E DELLE FINANZE") == "Ministero dell'Economia e delle Finanze"
    assert rappresentante("Istituto Nazionale della Previdenza Sociale") == "in persona del legale rappresentante pro tempore"
    assert "[da completare: denominazione per esteso" in denominazione("ASP")  # sigla ignota: non si indovina


def test_notifica_del_titolo_provata_riempie_la_data_e_i_centoventi_giorni():
    esecuzione = {"codice": "esecuzione_pa", "stato": "da_fare", "onerato_codice": "noi",
                  "termine": {"decorrenza": "2026-04-20", "scadenza": "2026-08-18", "natura": "attesa minima prima del precetto"}}
    richiesta, precetto = bozze_del_fascicolo(_lettura_credito_pa(conclusioni=[esecuzione]), oggi=OGGI, conto=_CONTO_DISTRATTE, studio=_STUDIO)
    assert "notificato il 20/04/2026" in precetto.testo and "notificato il 20/04/2026" in richiesta.testo
    assert "decorso il termine di centoventi giorni dalla notificazione del titolo, scaduto il 18/08/2026" in precetto.testo
    assert not any("centoventi" in voce or "notificazione del titolo" in voce for voce in precetto.segnaposti)
    assert precetto.dati["precetto_dal"] == "19/08/2026"
    # Notifica non provata (dubbio): la data resta da completare.
    dubbio = {**esecuzione, "stato": "dubbio", "termine": None}
    _r, precetto = bozze_del_fascicolo(_lettura_credito_pa(conclusioni=[dubbio]), oggi=OGGI, conto=_CONTO_DISTRATTE, studio=_STUDIO)
    assert "data della notificazione del titolo esecutivo" in precetto.segnaposti


def test_rimborso_forfettario_e_iva_solo_se_risultano_da_sentenza_e_scheda_dello_studio():
    # Liquidato «oltre rimborso forfettario» e regime forfetario dichiarato nella scheda: importi scritti.
    _r, precetto = bozze_del_fascicolo(_lettura_credito_pa(), oggi=OGGI, conto=_CONTO_DISTRATTE, studio=_STUDIO)
    assert "rimborso forfettario delle spese generali (15%): € 77,25" in precetto.testo and "€ 615,94" in precetto.testo
    assert "I.V.A.: non dovuta (regime forfetario dello studio)" in precetto.testo
    # La sentenza non lo liquida e la scheda non dichiara il regime: segnaposti, nessuna supposizione.
    _r, precetto = bozze_del_fascicolo(_lettura_credito_pa(nota="oltre accessori"), oggi=OGGI, conto=_CONTO_DISTRATTE,
                                       studio={"citta": "Taurianova"})
    assert "€ 77,25" not in precetto.testo and "€ 615,94" not in precetto.testo and "regime forfetario" not in precetto.testo
    assert any("rimborso forfettario" in voce for voce in precetto.segnaposti)
    assert "I.V.A. sul compenso, se dovuta, secondo il regime fiscale" in precetto.segnaposti


def test_il_regime_fiscale_vale_solo_se_dichiarato_nella_scheda_dello_studio(tmp_path):
    import json

    from web.services.bozze_passi_runtime import _regime_dichiarato

    scheda = tmp_path / "studio.json"
    scheda.write_text(json.dumps({"studio": {}, "fatturazione": {"regime_fiscale": "rf19"}}))
    assert _regime_dichiarato(str(scheda)) == "RF19"
    scheda.write_text(json.dumps({"studio": {}}))
    assert _regime_dichiarato(str(scheda)) == ""  # il predefinito RF01 non è un dato dello studio
