"""Bozze del software in PDF, senza doppioni e senza etichette tecniche (segnalazione dell'avvocato del 21/11/2026).

Fascicolo Carbone (9A681FDF): le due bozze erano già PDF nel fascicolo, ma l'elenco le mostrava «.html» perché la
sostituzione del file non aggiornava il nome mostrato (``nome_originale``); la scheda mostrava i marcatori interni
«bozza, bozza-passo, bozza-passo:precetto_pa:…». Il «create: 2» a ogni giro dello scheduler era la copertura dei
fascicoli (ogni volta un fascicolo diverso, nessun doppione: 75 bozze nei fascicoli, 75 voci del registro). Qui:
nome del PDF, salvataggio mirato con l'archivio caricato in parte, adozione del documento già scritto, doppioni nel
cestino con il motivo, bozze di Lex fuori dal ciclo dei passi, etichette chiare.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from pct.bozze_passi import FONTE_BOZZA_PASSO
from pct.bozze_passi.archivio import ArchivioBozze, VoceBozza
from pct.bozze_passi.modello import ETICHETTA_BOZZA_SOFTWARE, etichette_visibili
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo

OGGI = date(2026, 11, 21)
AUTORE = "IUSENTRA (bozza preparata in automatico)"


# --- Archivio reale dei fascicoli caricato in parte (come nel lavoro in sfondo) ------------------------------------

def _repo(tmp_path: Path, *, carica_tutto: bool) -> GestioneFascicoli:
    from pct.storage import StudioDB

    db = StudioDB.get(str(tmp_path / "studio.db"))
    db.ensure_schema()
    return GestioneFascicoli(db_path=str(tmp_path / "fascicoli" / "fascicoli.json"), studio_db=db, carica_tutto=carica_tutto)


@pytest.fixture()
def archivio_parziale(tmp_path):
    completo = _repo(tmp_path, carica_tutto=True)
    ids = [completo.nuovo(titolo=f"Pratica {i}", tipo=TipoFascicolo.CIVILE, nome_cliente=f"Cliente {i}").id for i in range(3)]
    documento = completo.aggiungi_documento(ids[0], "atto_di_precetto.html", TipoDocumento.ATTO_GIUDIZIARIO, b"<p>Precetto</p>",
                                            nome_originale="atto_di_precetto.html", fonte_documento=FONTE_BOZZA_PASSO,
                                            tags=["bozza", "bozza-passo", "bozza-passo:precetto_pa:x"], caricato_da=AUTORE)
    parziale = _repo(tmp_path, carica_tutto=False)
    assert parziale.get(ids[0]) is not None and not parziale._archivio_completo
    return parziale, ids, documento.id, tmp_path


def test_sostituzione_mirata_con_archivio_parziale_aggiorna_anche_il_nome_mostrato(archivio_parziale):
    repo, ids, documento_id, tmp_path = archivio_parziale
    with pytest.raises(RuntimeError, match="Salvataggio integrale bloccato"):
        repo.sostituisci_documento(ids[0], documento_id, nome_file="atto_di_precetto.pdf", contenuto=b"%PDF-1")
    repo = _repo(tmp_path, carica_tutto=False)
    assert repo.get(ids[0]) is not None  # come nel giro delle bozze: lettura puntuale del solo fascicolo
    repo.sostituisci_documento(ids[0], documento_id, nome_file="atto_di_precetto.pdf", contenuto=b"%PDF-1",
                               caricato_da=AUTORE, nome_originale="atto_di_precetto.pdf", salvataggio_mirato=True)
    assert not repo._archivio_completo  # nessun caricamento dell'intero archivio
    riletto = _repo(tmp_path, carica_tutto=True).get(ids[0])
    [documento] = riletto.documenti
    assert documento.nome == documento.nome_originale == "atto_di_precetto.pdf" and len(documento.versioni) == 1
    # Gli altri fascicoli restano intatti.
    assert {f.id for f in _repo(tmp_path, carica_tutto=True).tutti(archiviati=True)} >= set(ids)


def test_cestino_e_metadati_mirati_con_il_motivo_nella_nota(archivio_parziale):
    repo, ids, documento_id, tmp_path = archivio_parziale
    repo.aggiorna_documento_metadati(ids[0], documento_id, nome_originale="atto_di_precetto.pdf", salvataggio_mirato=True)
    repo.rimuovi_documento(ids[0], documento_id, eliminato_da=AUTORE, motivo="doppione della bozza «Precetto»",
                           salvataggio_mirato=True)
    riletto = _repo(tmp_path, carica_tutto=True).get(ids[0])
    assert riletto.documenti == [] and [d.id for d in riletto.documenti_cestino] == [documento_id]
    [nel_cestino] = riletto.documenti_cestino
    assert nel_cestino.nome_originale == "atto_di_precetto.pdf" and "Nel cestino: doppione della bozza «Precetto»" in nel_cestino.note
    assert nel_cestino.eliminato_da == AUTORE  # cestino, non cancellazione: il file resta


def test_documento_gia_presente_si_aggiorna_con_il_salvataggio_mirato(archivio_parziale):
    """Stesso nome e stesso contenuto: il repository riusa il documento; con l'archivio parziale non deve fallire."""
    repo, ids, documento_id, _tmp = archivio_parziale
    stesso = repo.aggiungi_documento(ids[0], "atto_di_precetto.html", TipoDocumento.ATTO_GIUDIZIARIO, b"<p>Precetto</p>",
                                     tags=["altro"], salvataggio_mirato=True)
    assert stesso.id == documento_id


# --- Ciclo delle bozze -------------------------------------------------------------------------------------------

class _Repository:
    def __init__(self, cartella: Path):
        self.cartella = cartella
        self.documenti: dict[str, SimpleNamespace] = {}
        self.cestino: list[tuple[str, str, bool]] = []
        self.sostituzioni: list[dict] = []
        self.metadati: list[dict] = []

    def get(self, fascicolo_id):
        return SimpleNamespace(id=fascicolo_id, id_cliente="", documenti=list(self.documenti.values()))

    def percorso_documento(self, fascicolo_id, documento_id):
        return self.cartella / f"{documento_id}.bin"

    percorso_documento_lettura = percorso_documento

    def aggiungi_documento(self, fascicolo_id, nome_file, tipo, contenuto, **campi):
        documento_id = f"D{len(self.documenti) + len(self.cestino) + 1}"
        self.percorso_documento(fascicolo_id, documento_id).write_bytes(contenuto)
        campi.setdefault("hash_contenuto_sha256", hashlib.sha256(contenuto).hexdigest())
        campi.pop("salvataggio_mirato", None)
        self.documenti[documento_id] = SimpleNamespace(id=documento_id, nome=nome_file, tipo=tipo, versioni=[],
                                                       data_caricamento=f"2026-11-21T10:0{len(self.documenti)}", **campi)
        return self.documenti[documento_id]

    def sostituisci_documento(self, fascicolo_id, documento_id, **campi):
        self.sostituzioni.append(campi)
        documento = self.documenti[documento_id]
        documento.versioni.append(SimpleNamespace(sostituito_da=campi.get("caricato_da", "")))
        self.percorso_documento(fascicolo_id, documento_id).write_bytes(campi["contenuto"])
        documento.nome, documento.hash_contenuto_sha256 = campi["nome_file"], campi["hash_contenuto_sha256"]
        documento.nome_originale = campi.get("nome_originale", getattr(documento, "nome_originale", ""))
        documento.caricato_da = campi.get("caricato_da") or documento.caricato_da
        return documento

    def aggiorna_documento_metadati(self, fascicolo_id, documento_id, **campi):
        self.metadati.append(campi)
        self.documenti[documento_id].nome_originale = campi["nome_originale"]

    def rimuovi_documento(self, fascicolo_id, documento_id, *, eliminato_da="", motivo="", salvataggio_mirato=False):
        self.cestino.append((documento_id, motivo, salvataggio_mirato))
        self.documenti.pop(documento_id)


@pytest.fixture()
def ambiente(monkeypatch, tmp_path):
    from web.services import bozze_passi_runtime as runtime

    repository = _Repository(tmp_path)
    archivio = ArchivioBozze(tmp_path / "bozze.sqlite")
    monkeypatch.setattr("web.helpers.get_fascicoli", lambda: repository)
    monkeypatch.setattr(runtime, "dati_studio", dict)
    monkeypatch.setattr(runtime, "_cliente_cf", lambda _f: "")
    monkeypatch.setattr(runtime, "_segnala_documenti", lambda _f: None)
    monkeypatch.setattr(runtime, "archivio_corrente", lambda *_a: archivio)
    app = Flask(__name__)
    with app.test_request_context("/"):
        yield runtime, repository, archivio


def _lettura_note():
    return {
        "intestazione": {"numero": "2026/1", "titolo": "Rossi c. Bianchi", "rg": "1/2026", "ufficio": "TRIBUNALE DI PALMI",
                         "cliente": "Rossi Mario", "controparte": "Bianchi Luca", "tipo": "civile", "stato_codice": "IN_CORSO",
                         "avvocato": "Avv. Giuseppe Montagnese", "parti": {}},
        "ragionamento": {"impronta": "abc", "conclusioni": [{
            "codice": "note_127ter", "stato": "da_fare", "onerato_codice": "tutte_le_parti", "cosa": "Depositare le note scritte",
            "letto": {"documento_id": "DEC1", "documento": "decreto.pdf", "data": "09/10/2026", "tipo": "documento"},
            "termine": {"scadenza_iso": "2027-02-09", "scadenza": "09/02/2027", "ora_assegnata": "14:00"}}],
            "udienze": [{"data": "09/02/2027", "modalita": "sostituita da note scritte (art. 127-ter c.p.c.)", "documento_id": "DEC1"}]},
        "documenti": {}, "economico": {}, "stato_passi": {"attivi": True},
        "prossimi_passi": [{"azione": "Depositare le note scritte ex art. 127-ter c.p.c.", "entro": "09/02/2027"}],
    }


def test_bozza_nuova_in_pdf_e_giro_successivo_senza_nuove_creazioni(ambiente):
    runtime, repository, archivio = ambiente
    assert runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)["create"] == 1
    for _ in range(3):
        esito = runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
        assert esito["create"] == 0 and esito["invariate"] == 1
    [documento] = repository.documenti.values()
    assert documento.nome.endswith(".pdf") and documento.nome_originale == documento.nome
    assert repository.percorso_documento("F1", documento.id).read_bytes().startswith(b"%PDF-")


def test_registro_non_salvato_il_documento_gia_scritto_si_riusa_senza_doppione(ambiente):
    runtime, repository, archivio = ambiente
    runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
    [voce] = archivio.del_fascicolo("F1")
    archivio.elimina("F1", voce.chiave)  # il registro non era stato salvato (per esempio «database is locked»)
    esito = runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
    assert esito["create"] == 1 and len(repository.documenti) == 1 and repository.cestino == []
    [nuova] = archivio.del_fascicolo("F1")
    assert nuova.documento_id == voce.documento_id
    assert runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)["invariate"] == 1


def test_doppioni_mai_toccati_nel_cestino_con_il_motivo_quelli_dell_avvocato_restano(ambiente):
    runtime, repository, archivio = ambiente
    runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
    [voce] = archivio.del_fascicolo("F1")
    marcatori = ["bozza", "bozza-passo", f"bozza-passo:{voce.chiave}"]
    doppione = repository.aggiungi_documento("F1", "note.pdf", "ATTO_GIUDIZIARIO", b"%PDF-x", tags=marcatori,
                                            caricato_da=AUTORE, fonte_documento=FONTE_BOZZA_PASSO)
    dell_avvocato = repository.aggiungi_documento("F1", "note.pdf", "ATTO_GIUDIZIARIO", b"%PDF-y", tags=marcatori,
                                                 caricato_da="avv.montagnese", fonte_documento=FONTE_BOZZA_PASSO)
    assert runtime.riallinea_doppioni(repository, repository.get("F1"), archivio) == 1
    [(tolto, motivo, mirato)] = repository.cestino
    assert tolto == doppione.id and mirato and f"resta il documento {voce.documento_id}" in motivo
    assert set(repository.documenti) == {voce.documento_id, dell_avvocato.id}


def test_riallineamento_una_tantum_del_registro_nome_pdf_e_doppioni(ambiente):
    runtime, repository, archivio = ambiente
    runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
    [voce] = archivio.del_fascicolo("F1")
    assert voce.riallineata and archivio.da_riallineare() == []
    # Stato delle bozze del 19-21/11: PDF nel fascicolo, nome mostrato ancora «.html», voce da riallineare.
    documento = repository.documenti[voce.documento_id]
    documento.nome_originale = documento.nome.removesuffix(".pdf") + ".html"
    voce.riallineata = False
    archivio.salva(voce)
    assert [v.chiave for v in archivio.da_riallineare()] == [voce.chiave]
    assert runtime.riallinea_registro(archivio) == {"nomi": 1, "doppioni": 0}
    assert documento.nome_originale == documento.nome and repository.metadati[0]["salvataggio_mirato"] is True
    assert archivio.da_riallineare() == [] and runtime.riallinea_registro(archivio) == {"nomi": 0, "doppioni": 0}


def test_le_voci_del_registro_gia_esistenti_ricevono_la_colonna_da_riallineare(tmp_path):
    import sqlite3

    percorso = tmp_path / "bozze.sqlite"
    with sqlite3.connect(percorso) as conn:  # registro creato prima del 21/11/2026, senza la colonna
        conn.execute("CREATE TABLE bozze_passi (fascicolo_id TEXT NOT NULL, chiave TEXT NOT NULL, documento_id TEXT NOT NULL, "
                     "tipo TEXT NOT NULL, titolo TEXT NOT NULL, modello TEXT NOT NULL, modello_titolo TEXT NOT NULL, "
                     "norma TEXT NOT NULL DEFAULT '', da_completare TEXT NOT NULL DEFAULT '[]', passi TEXT NOT NULL DEFAULT '[]', "
                     "impronta_testo TEXT NOT NULL, impronta_contenuto TEXT NOT NULL, impronta_fonti_attuali TEXT NOT NULL DEFAULT '', "
                     "stato TEXT NOT NULL, creata_il TEXT NOT NULL, aggiornata_il TEXT NOT NULL, dati_cambiati_il TEXT NOT NULL DEFAULT '', "
                     "testo_html TEXT NOT NULL DEFAULT '', formato TEXT NOT NULL DEFAULT '', PRIMARY KEY (fascicolo_id, chiave))")
        conn.execute("INSERT INTO bozze_passi VALUES ('F1','k','D1','t','T','m','M','','[]','[]','a','b','','pronta','x','x','','<p/>','pdf')")
    archivio = ArchivioBozze(percorso)
    [voce] = archivio.da_riallineare()
    assert voce.riallineata is False
    archivio.salva(VoceBozza(fascicolo_id="F1", chiave="nuova", documento_id="D2", tipo="t", titolo="T", modello="m",
                             modello_titolo="M", formato="pdf"))
    assert [v.chiave for v in archivio.da_riallineare()] == ["k"]


def test_le_bozze_di_lex_restano_fuori_dal_ciclo_dei_passi(ambiente):
    runtime, repository, archivio = ambiente
    lex = repository.aggiungi_documento("F1", "atto_lex.pdf", "ATTO_GIUDIZIARIO", b"%PDF-lex", caricato_da=AUTORE,
                                        tags=["bozza", "bozza-passo", "bozza-lex", "bozza-passo:lex-atto-1"],
                                        fonte_documento=FONTE_BOZZA_PASSO)
    archivio.salva(VoceBozza(fascicolo_id="F1", chiave="lex-atto-1", documento_id=lex.id, tipo="lex", titolo="Atto Lex",
                             modello="", modello_titolo="Lex", impronta_contenuto=lex.hash_contenuto_sha256, formato="pdf"))
    esito = runtime.prepara_bozze_fascicolo("F1", lettura=_lettura_note(), archivio=archivio, oggi=OGGI)
    assert esito["superate"] == 0 and lex.id in repository.documenti and repository.cestino == []
    assert {v.chiave for v in archivio.del_fascicolo("F1")} >= {"lex-atto-1"}


def test_scrivi_pdf_salva_in_modo_mirato_e_aggiorna_il_nome_mostrato(ambiente):
    runtime, repository, archivio = ambiente
    documento = repository.aggiungi_documento("F1", "precetto.html", "ATTO_GIUDIZIARIO", b"<p>x</p>", caricato_da=AUTORE,
                                              nome_originale="precetto.html")
    runtime.scrivi_pdf(repository, "F1", documento, titolo="Atto di precetto", testo_html="<p>x</p>", note="n")
    [chiamata] = repository.sostituzioni
    assert chiamata["salvataggio_mirato"] is True and chiamata["nome_originale"] == chiamata["nome_file"] == "atto_di_precetto.pdf"


# --- Etichette nella scheda del documento -------------------------------------------------------------------------

def test_la_scheda_non_mostra_i_marcatori_interni_delle_bozze():
    bozza = SimpleNamespace(fonte_documento=FONTE_BOZZA_PASSO,
                            tags=["bozza", "bozza-passo", "bozza-passo:precetto_pa:sentenza-del-17-04-2026", "urgente"])
    assert etichette_visibili(bozza) == [ETICHETTA_BOZZA_SOFTWARE, "urgente"]
    editor = SimpleNamespace(fonte_documento="", tags=["bozza-editor", "editor-nuovo:abc", "editor-richiesta:ff", "ctu"])
    assert etichette_visibili(editor) == ["Bozza", "ctu"]
    normale = SimpleNamespace(fonte_documento="PEC", tags=["PEC", "sentenza"])
    assert etichette_visibili(normale) == ["PEC", "sentenza"]


def test_elenco_dei_documenti_e_editor_mostrano_l_etichetta_chiara():
    from web.services.react_fascicoli_bridge import _visible_document_tags

    bozza = SimpleNamespace(fonte_documento=FONTE_BOZZA_PASSO, nome="atto.pdf", nome_originale="atto.pdf",
                            tags=["bozza", "bozza-passo", "bozza-passo:precetto_pa:sentenza-del-17-04-2026"])
    etichette = _visible_document_tags(bozza, display_name="atto.pdf", technical_name="atto.pdf")
    assert etichette == [ETICHETTA_BOZZA_SOFTWARE]
    assert not any("bozza-passo" in e for e in etichette)


# --- Precetto contro la P.A. riletto da avvocato (fascicolo Carbone, forme ridotte) ----------------------------------

def _lettura_carbone(percorso=(), conclusioni=()):
    return {
        "intestazione": {"numero": "2026/273", "titolo": "Carbone Claudia II ricorso c. MIM", "rg": "161/2026",
                         "ufficio": "TRIBUNALE DI REGGIO DI CALABRIA", "cliente": "Carbone Claudia", "controparte": "MIM",
                         "parti": {"difensore controparte": ["Avvocatura Distrettuale dello Stato di Reggio Calabria"]},
                         "tipo": "lavoro", "stato_codice": "DEFINITO", "avvocato": "Avv. Giuseppe Montagnese"},
        "ragionamento": {"impronta": "abc", "conclusioni": list(conclusioni), "percorso": list(percorso)},
        "documenti": {}, "stato_passi": {"attivi": False}, "prossimi_passi": [],
        "economico": {"liquidazione": {"stato": "da_incassare", "importo": 515.0, "fonte": "Sentenza del 17/04/2026",
                                       "pagato": False, "nota": "che liquida in € 515,00 per compenso di avvocato, oltre rimborso forfettar"}},
    }


_CONSEGNA_SENTENZA = {"tipo": "consegna_notifica", "data": "2026-04-20", "stato": "verificato",
                      "descrizione": "Attestazione di conformit_ sentenza (originale notificato).pdf"}
_STUDIO_CARBONE = {"regime_fiscale": "RF19", "citta": "Taurianova", "pec": "studio@pec.example.it", "cf_avvocato": "MNTGPP94L01G791A",
                   "indirizzo_completo": "Via Nino Bixio 4, 89029 Taurianova (RC)", "iban": "IT00X0000000000000000000000"}
_CONTO = {"righe": [{"voce": "sentenza", "stato": "Distratte in favore dell'avvocato", "dettaglio": ""}]}


def _bozze_carbone(**kw):
    from pct.bozze_passi.catalogo import bozze_del_fascicolo

    return bozze_del_fascicolo(_lettura_carbone(**kw), oggi=OGGI, conto=_CONTO, studio=_STUDIO_CARBONE)


def test_precetto_pa_con_le_norme_vigenti_e_i_dati_del_fascicolo():
    richiesta, precetto = _bozze_carbone(percorso=[_CONSEGNA_SENTENZA])
    testo = precetto.testo
    # Titolo in copia attestata conforme, senza formula esecutiva (art. 475 c.p.c. dal 28/02/2023) e notifica del 20/04/2026.
    assert "titolo esecutivo (art. 474 c.p.c.) rilasciato in copia attestata conforme all'originale (art. 475 c.p.c.), notificato il 20/04/2026" in testo
    assert "scaduto il 18/08/2026" in testo and "art. 14, comma 1, D.L. 669/1996" in testo
    # Il precetto (atto stragiudiziale) si notifica direttamente all'amministrazione, non presso l'Avvocatura dello Stato
    # (artt. 480, ultimo comma, e 144, secondo comma, c.p.c.; Cass. civ., sez. V, 19/12/2003, n. 19512).
    assert ("al **Ministero dell'Istruzione e del Merito, in persona del Ministro pro tempore**, da notificarsi direttamente "
            "all'amministrazione (artt. 480, ultimo comma, e 144, secondo comma, c.p.c.; Cass. civ., sez. V, 19 dicembre 2003, n. 19512)") in testo
    assert "presso l'Avvocatura" not in testo and "art. 11" not in testo
    assert "di pagare entro dieci giorni" in testo and "(art. 480, primo comma, c.p.c.)" in testo
    assert "piano del consumatore (art. 480, secondo comma, c.p.c.)" in testo
    assert "studio@pec.example.it (art. 480, terzo comma, c.p.c.)" in testo  # PEC da pubblici elenchi (D.Lgs. 164/2024)
    assert "Indica quale giudice competente per l'esecuzione" in testo
    for importo in ("€ 515,00", "€ 77,25", "€ 23,69", "€ 615,94"):
        assert importo in testo
    assert "I.V.A.: non dovuta (regime forfetario dello studio)" in testo
    assert "Avv. Giuseppe Montagnese** (C.F. MNTGPP94L01G791A), in proprio quale difensore antistatario" in testo
    # Restano da completare: competenze del precetto, ufficio e PEC del Ministero, giudice dell'esecuzione, data.
    assert len(precetto.segnaposti) == 4 and "data della notificazione del titolo esecutivo" not in precetto.segnaposti
    assert "il titolo esecutivo è stato notificato il 20/04/2026" in richiesta.testo and len(richiesta.segnaposti) == 3


def test_notifica_dal_percorso_solo_se_unica_verificata_e_senza_dubbio_del_modello():
    # Senza consegna verificata: la data resta da completare.
    _r, precetto = _bozze_carbone(percorso=[{**_CONSEGNA_SENTENZA, "stato": "da_verificare"}])
    assert "data della notificazione del titolo esecutivo" in precetto.segnaposti
    # Due date diverse: nessuna scelta.
    _r, precetto = _bozze_carbone(percorso=[_CONSEGNA_SENTENZA, {**_CONSEGNA_SENTENZA, "data": "2026-05-02"}])
    assert "data della notificazione del titolo esecutivo" in precetto.segnaposti
    # Il modello ha un dubbio sulla notifica del titolo: la bozza non lo scavalca.
    dubbio = {"codice": "esecuzione_pa", "stato": "dubbio", "termine": None}
    _r, precetto = _bozze_carbone(percorso=[_CONSEGNA_SENTENZA], conclusioni=[dubbio])
    assert "data della notificazione del titolo esecutivo" in precetto.segnaposti
    # Consegna anteriore alla sentenza: non è la notifica del titolo.
    _r, precetto = _bozze_carbone(percorso=[{**_CONSEGNA_SENTENZA, "data": "2026-02-02"}])
    assert "data della notificazione del titolo esecutivo" in precetto.segnaposti
