"""Deposito amministrativo dal fascicolo: quadro Formweb, Excel parti, pacchetto, riepilogo, apertura."""

from __future__ import annotations

import hashlib
import io
import zipfile

from pct.fascicoli import TipoDocumento, TipoFascicolo
from pct.pat_formweb import excel_parti, regole
from pct.soggetti import RuoloSoggetto, TipoSoggetto
from tests.test_pat_formweb import pdf_pades, riepilogo_pdf
from tests.test_penale_pdp import pdf_testo
from tests.test_react_shell import _app

H = {"X-API-Key": "react-test-key"}


def _fascicolo(app):
    from pct.clienti import GestioneClienti, TipoCliente

    with app.app_context():
        rt = app.extensions["core_runtime"]
        cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
            TipoCliente.PERSONA_FISICA, nome="Luca", cognome="Bianchi", codice_fiscale="BNCLCU80A01H501U")
        gf = rt["get_fascicoli"]()
        f = gf.nuovo("Bianchi c/ Comune di Palmi", TipoFascicolo.AMMINISTRATIVO, nome_cliente="Bianchi Luca",
                     id_cliente=cliente.id, tribunale="TAR Calabria - Reggio", numero_rg="123", anno_rg=2026)
        gf.aggiorna(f.id, oggetto="Annullamento della delibera di giunta n. 12/2026")
        soggetti = rt["get_soggetti"]()
        comune = soggetti.crea(TipoSoggetto.PUBBLICA_AMMINISTRAZIONE, ragione_sociale="Comune di Palmi", partita_iva="00282160802")
        impresa = soggetti.crea(TipoSoggetto.PERSONA_GIURIDICA, ragione_sociale="Edil Sud S.r.l.", partita_iva="01234567890")
        soggetti.aggiungi_parte(f.id, comune.id, RuoloSoggetto.CONTROPARTE)
        soggetti.aggiungi_parte(f.id, impresa.id, RuoloSoggetto.CONTROPARTE)
        ricorso = pdf_pades(pdf_testo("Ricorso al TAR"))
        doc_ricorso = gf.aggiungi_documento(f.id, "Ricorso T.A.R. firmato.pdf", TipoDocumento.RICORSO, ricorso, firmato=True)
        doc_procura = gf.aggiungi_documento(f.id, "Procura alle liti.pdf", TipoDocumento.PROCURA,
                                            pdf_pades(pdf_testo("Procura")), firmato=True)
        doc_delibera = gf.aggiungi_documento(f.id, "Delibera n.12-2026.pdf", TipoDocumento.ALLEGATO, pdf_testo("Delibera"))
        return f.id, impresa.id, {"ricorso": doc_ricorso, "procura": doc_procura, "delibera": doc_delibera}


def test_quadro_e_scheda_formweb_dal_fascicolo(tmp_path):
    app = _app(tmp_path)
    fid, impresa, docs = _fascicolo(app)
    base = f"/api/v1/ui/amministrativo/fascicoli/{fid}"
    with app.test_client() as client:
        quadro = client.get(base, headers=H).get_json()
        assert quadro["ok"] and quadro["procedimento"]["sede"] == "tar_rc" and quadro["procedimento"]["nrg"] == "202600123"
        assert [(p["ruolo"], p["tipologia"]) for p in quadro["parti"]] == [
            ("ricorrente", "Persona fisica"), ("resistente", "Amministrazione"), ("controinteressato", "Persona giuridica")]
        documenti = {d["id"]: d for d in quadro["documenti"]}
        assert documenti[docs["ricorso"].id]["ruolo"] == "atto" and documenti[docs["ricorso"].id]["nomeProposto"] == "Ricorso TAR firmato.pdf"
        assert documenti[docs["procura"].id]["ruolo"] == "procura" and not documenti[docs["procura"].id]["bloccante"]
        assert documenti[docs["delibera"].id]["nomeProposto"] == "Delibera n12 2026.pdf"
        assert documenti[docs["ricorso"].id]["sha256"] == docs["ricorso"].hash_sha256.upper()
        bozza = {r["etichetta"]: r["valore"] for r in quadro["scheda"]["sezioni"][0]["righe"]}
        assert bozza["Sede"] == "TAR CALABRIA - REGGIO CALABRIA" and bozza["Tipologia"] == "da indicare"

        salvato = client.post(f"{base}/procedimento", headers=H, json={
            "tipoRicorso": "1", "cuTipologia": "Non esente", "istanze": ["Domanda cautelare collegiale", "Inventata"],
            "attoImpugnato": {"organo": "Comune di Palmi", "tipo": "DELIBERA", "numero": "12", "anno": "2026"}}).get_json()
        assert salvato["procedimento"]["istanze"] == ["Domanda cautelare collegiale"]
        assert salvato["contributo"]["importo"] == 650
        bozza = {r["etichetta"]: r["valore"] for r in salvato["scheda"]["sezioni"][0]["righe"]}
        assert bozza["Tipologia"] == "ORDINARIO"

        errore = client.post(f"{base}/procedimento", headers=H, json={"tipoRicorso": "Z3"})
        assert errore.status_code == 400 and "non previsto" in errore.get_json()["message"]
        assert client.post(f"{base}/procedimento", headers=H, json={"nrg": "12"}).status_code == 400

        escluso = client.post(f"{base}/parti/{impresa}", headers=H, json={"ruolo": "escludi"}).get_json()
        assert [p["ruolo"] for p in escluso["parti"]] == ["ricorrente", "resistente"]
        documento = client.post(f"{base}/documenti/{docs['delibera'].id}", headers=H,
                                json={"ruolo": "allegato", "descrizione": "Delibera impugnata"}).get_json()
        assert next(d for d in documento["documenti"] if d["id"] == docs["delibera"].id)["descrizione"] == "Delibera impugnata"
        assert client.post(f"{base}/documenti/sconosciuto", headers=H, json={"ruolo": "atto"}).status_code == 404


def test_excel_parti_e_pacchetto_con_nomi_del_formweb(tmp_path):
    app = _app(tmp_path)
    fid, _impresa, docs = _fascicolo(app)
    base = f"/api/v1/ui/amministrativo/fascicoli/{fid}"
    with app.test_client() as client:
        risposta = client.get(f"{base}/excel-parti/resistente", headers=H)
        assert risposta.status_code == 200 and "Excel_Parti_resistenti.xlsx" in risposta.headers["Content-Disposition"]
        assert excel_parti.leggi(risposta.data)[1] == ["Amministrazione", "", "", "00282160802", "", "Comune di Palmi"]
        assert client.get(f"{base}/excel-parti/giudice", headers=H).status_code == 400

        zip_risposta = client.get(f"{base}/pacchetto", headers=H)
        assert zip_risposta.status_code == 200
        archivio = zipfile.ZipFile(io.BytesIO(zip_risposta.data))
        nomi = archivio.namelist()
        assert set(nomi) == {"Ricorso TAR firmato.pdf", "Procura alle liti.pdf", "Delibera n12 2026.pdf", "Indice deposito.csv"}
        assert all(regole.nome_valido(n) for n in nomi)
        indice = archivio.read("Indice deposito.csv").decode("utf-8-sig")
        assert hashlib.sha256(archivio.read("Ricorso TAR firmato.pdf")).hexdigest().upper() in indice
        assert "atto;Ricorso TAR firmato.pdf" in indice and "conforme" in indice


def test_riepilogo_verificato_salvato_e_deposito_registrato(tmp_path):
    app = _app(tmp_path)
    fid, _impresa, docs = _fascicolo(app)
    base = f"/api/v1/ui/amministrativo/fascicoli/{fid}"
    with app.test_client() as client:
        client.post(f"{base}/documenti/{docs['delibera'].id}", headers=H, json={"ruolo": "escludi"})
        righe = ["Giustizia amministrativa", "Riepilogo Deposito Ricorso", "Sede: TAR CALABRIA - REGGIO CALABRIA"]
        for doc in (docs["ricorso"], docs["procura"]):
            impronta = doc.hash_sha256.upper()
            righe += [f"{doc.nome}", impronta[:32], impronta[32:]]
        firmato = pdf_pades(riepilogo_pdf(righe))
        esito = client.post(f"{base}/riepilogo", headers=H, data={
            "file": (io.BytesIO(firmato), "RiepilogoGenerato_3100_24_09_2026.pdf"), "tipo": "ricorso"},
            content_type="multipart/form-data").get_json()
        assert esito["ok"] and esito["esito"]["conforme"], esito
        assert esito["deposito"]["stato"] == "riepilogo verificato"
        did = esito["deposito"]["id"]

        inviato = client.post(f"{base}/depositi", headers=H, json={"id": did, "stato": "inviato", "identificativo": "2026TAR0001"})
        assert inviato.get_json()["deposito"]["identificativo"] == "2026TAR0001"
        quadro = client.get(base, headers=H).get_json()
        assert quadro["depositi"][0]["stato"] == "inviato"
        salvato = next(d for d in quadro["documenti"] if d["nome"].startswith("RiepilogoGenerato"))
        assert salvato["ruolo"] == "escludi"  # la prova del deposito non rientra nei file da depositare
        di_nuovo = client.post(f"{base}/riepilogo", headers=H, data={
            "file": (io.BytesIO(firmato), "RiepilogoGenerato_3100_24_09_2026.pdf"), "tipo": "ricorso", "salva": "0"},
            content_type="multipart/form-data").get_json()
        assert di_nuovo["esito"]["conforme"]

        non_firmato = client.post(f"{base}/riepilogo", headers=H, data={
            "file": (io.BytesIO(riepilogo_pdf(righe[:4])), "Riepilogo.pdf"), "tipo": "ricorso", "salva": "0"},
            content_type="multipart/form-data").get_json()
        assert not non_firmato["esito"]["conforme"] and non_firmato["deposito"]["stato"] == "in preparazione"
        assert client.post(f"{base}/depositi", headers=H, json={"tipo": "ricorso", "stato": "perso"}).status_code == 400


def test_sezione_solo_per_fascicoli_amministrativi_e_catalogo(tmp_path, monkeypatch):
    from web.services import pat_formweb_azioni

    app = _app(tmp_path)
    with app.app_context():
        civile = app.extensions["core_runtime"]["get_fascicoli"]().nuovo("Civile", TipoFascicolo.CIVILE)
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/amministrativo/fascicoli/{civile.id}", headers=H)
        assert risposta.status_code == 400 and "amministrativi" in risposta.get_json()["message"]
        assert client.get("/api/v1/ui/amministrativo/fascicoli/inesistente", headers=H).status_code == 404
        catalogo = client.get("/api/v1/ui/amministrativo/catalogo", headers=H).get_json()
        assert catalogo["ok"] and len(catalogo["depositi"]) == 8 and catalogo["tipiRicorsoTar"]
        apertura = client.get("/api/v1/ui/amministrativo/catalogo-apertura?ufficio=TAR Lazio - Latina", headers=H).get_json()
        assert apertura["sede"] == {"codice": "tar_lt", "descrizione": "TAR LAZIO - LATINA", "ambito": "TAR"}

        monkeypatch.setattr(pat_formweb_azioni, "_CONNESSIONE", {})
        monkeypatch.setattr(pat_formweb_azioni, "_leggi", lambda url, limite: (200, b"<html><siga-root></siga-root></html>"))
        assert client.get("/api/v1/ui/amministrativo/connessione", headers=H).get_json()["raggiungibile"] is True
        monkeypatch.setattr(pat_formweb_azioni, "_CONNESSIONE", {})

        def fallisce(url, limite):
            raise OSError("rete")
        monkeypatch.setattr(pat_formweb_azioni, "_leggi", fallisce)
        assert client.get("/api/v1/ui/amministrativo/connessione", headers=H).get_json()["raggiungibile"] is False


def test_apertura_fascicolo_amministrativo_imposta_il_procedimento(tmp_path):
    from pct.clienti import GestioneClienti, TipoCliente
    from tests.test_react_shell import _crea_operatore, _login

    app = _app(tmp_path)
    _crea_operatore(app)
    cliente = GestioneClienti(db_path=app.config["CLIENTI_DB"]).nuovo(
        TipoCliente.PERSONA_FISICA, nome="Luca", cognome="Bianchi", codice_fiscale="BNCLCU80A01H501U")
    with app.test_client() as client:
        _login(client)
        normale = client.post("/fascicoli/nuovo", data={
            "id_cliente": cliente.id, "titolo": "Bianchi c/ Comune", "tipo": TipoFascicolo.AMMINISTRATIVO.value,
            "oggetto": "Annullamento", "tribunale": "TAR Calabria - Reggio",
            "pat_tipo_ricorso": "85", "pat_posizione": "ricorrente", "pat_cu": "Non esente"}, follow_redirects=False)
        assert normale.status_code in {302, 303}
        fid = normale.headers["Location"].split("/fascicoli/", 1)[1].split("/", 1)[0].split("#")[0]
        quadro = client.get(f"/api/v1/ui/amministrativo/fascicoli/{fid}", headers=H).get_json()
        assert quadro["procedimento"]["tipoRicorso"] == "85" and quadro["procedimento"]["sede"] == "tar_rc"
        assert quadro["contributo"]["importo"] == 300

        veloce = client.post("/fascicoli/nuovo", data={
            "id_cliente": cliente.id, "titolo": "Veloce TAR", "tipo": TipoFascicolo.AMMINISTRATIVO.value, "oggetto": "Silenzio",
            "tribunale": "TAR Calabria - Reggio", "controparte": "Comune di Palmi", "cf_controparte": "00282160802",
            "fascicolo_veloce": "1", "pat_sede": "tar_rc", "pat_tipo_ricorso": "86"}, follow_redirects=False)
        assert veloce.status_code in {302, 303}, veloce.get_data(as_text=True)[:300]
        assert veloce.headers["Location"].endswith("#pat-formweb")

        errato = client.post("/fascicoli/nuovo", data={
            "id_cliente": cliente.id, "titolo": "Sede errata", "tipo": TipoFascicolo.AMMINISTRATIVO.value, "oggetto": "x",
            "tribunale": "TAR Calabria - Reggio", "pat_sede": "tar_xx"}, follow_redirects=False)
        assert errato.status_code in {302, 303}  # il fascicolo nasce comunque; il PAT si completa dopo
