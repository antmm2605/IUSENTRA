"""Formweb del Portale dell'Avvocato (PAT): regole sui file, catalogo, foglio parti, scheda, riepilogo."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import tempfile

import pytest

from pct.pat_formweb import catalogo, contributo, excel_parti, parti, regole, riepilogo, scheda
from pct.pat_formweb.archivio import ArchivioPat
from tests.test_penale_pdp import p7m, pdf_testo


def pdf_pades(contenuto: bytes) -> bytes:
    """PDF firmato PAdES con certificato di prova (pyHanko)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers

    chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Avvocato di prova")])
    ora = dt.datetime.now(dt.timezone.utc)
    certificato = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chiave.public_key())
                   .serial_number(x509.random_serial_number()).not_valid_before(ora - dt.timedelta(days=1))
                   .not_valid_after(ora + dt.timedelta(days=30)).sign(chiave, hashes.SHA256()))
    cartella = tempfile.mkdtemp()
    with open(f"{cartella}/k.pem", "wb") as f:
        f.write(chiave.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    with open(f"{cartella}/c.pem", "wb") as f:
        f.write(certificato.public_bytes(serialization.Encoding.PEM))
    firmatario = signers.SimpleSigner.load(f"{cartella}/k.pem", f"{cartella}/c.pem")
    uscita = signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(contenuto)),
                              signers.PdfSignatureMetadata(field_name="Firma"), signer=firmatario)
    return uscita.getvalue()


def riepilogo_pdf(righe: list[str]) -> bytes:
    """PDF con l'impaginazione del «Riepilogo Deposito» del Formweb (impronte spezzate come nelle celle)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for riga in righe:
        pagina.drawString(40, y, riga)
        y -= 16
    pagina.save()
    return buffer.getvalue()


def test_nomi_file_come_li_accetta_il_formweb():
    # Controllo del portale 1.15.0: solo lettere, cifre, «_», spazi e ÄäÖöÜüß prima dell'estensione.
    assert regole.nome_valido("Ricorso TAR_2026.pdf") and regole.nome_valido("Beschwerde Müller.pdf")
    assert not regole.nome_valido("Ricorso-TAR.pdf") and not regole.nome_valido("Atto d'appello.pdf")
    assert regole.nome_formweb("Ricorso T.A.R. – Comune d'Àlba (firmato).pdf") == "Ricorso TAR Comune d Alba firmato.pdf"
    assert regole.nome_valido(regole.nome_formweb("àèìòù#@!.pdf"))
    assert regole.nomi_unici(["Allegato.pdf", "allegato.pdf", "Doc#1.pdf"]) == ["Allegato.pdf", "allegato 2.pdf", "Doc 1.pdf"]
    assert len(regole.nome_formweb("x" * 300 + ".pdf")) == regole.LIMITE_NOME


def test_controllo_file_firma_e_formato():
    firmato = pdf_pades(pdf_testo("Ricorso al TAR"))
    assert regole.tipo_firma(firmato, "ricorso.pdf") == "pades"
    assert not regole.controlla_file("Ricorso.pdf", firmato, "atto").bloccante
    assert regole.controlla_file("Ricorso.pdf", pdf_testo(), "atto").esiti[0].codice == "FIRMA_MANCANTE"
    busta = regole.controlla_file("Ricorso.pdf.p7m", p7m(pdf_testo()), "atto")
    assert busta.firma == "cades" and {e.codice for e in busta.esiti} >= {"CADES", "NOME_NON_VALIDO"}
    allegato = regole.controlla_file("Planimetria.dwg", b"x", "allegato")
    assert not allegato.bloccante and allegato.esiti[0].codice == "FORMATO"
    assert allegato.sha256 == hashlib.sha256(b"x").hexdigest().upper()


def test_catalogo_dai_moduli_ufficiali_e_dal_portale():
    dati = catalogo.catalogo()
    assert len(dati["sedi"]) == 29 + 2  # 29 sedi TAR del portale (Roma e Torino hanno due uffici nel bundle) + CdS e CGARS
    assert {"codice": "tar_rc", "descrizione": "TAR CALABRIA - REGGIO CALABRIA", "ambito": "TAR"} in dati["sedi"]
    assert {d["id"] for d in dati["depositi"]} == {"ricorso", "atto-successivo", "documento-successivo", "istanze-giudice",
                                                    "richieste-segreteria", "succ-contr-unificato", "succ-notifiche", "rimborso"}
    assert catalogo.link_deposito("ricorso").endswith("#/depositi/nuovo/ricorso")
    assert catalogo.descrizione("tipoRicorsoTar", "1") == "ORDINARIO"
    assert catalogo.descrizione("tipoRicorsoCds", "Z3") == "APPELLO AVVERSO SENTENZA"
    assert catalogo.tipi_ricorso("cds")[0]["codice"] and catalogo.tipi_ricorso("tar_rc") == dati["tipiRicorsoTar"]
    assert dati["modalitaNotifica"] == ["PEC", "POSTA", "MANI PROPRIE", "ALTRO", "UNEP"]
    with pytest.raises(ValueError):
        catalogo.deposito("sconosciuto")


def test_ogni_tar_del_bundle_ha_la_sede_del_portale():
    from pct.uffici_giudiziari import _build_bundle_completo

    uffici = [u for u in _build_bundle_completo() if u["tipo"] in {"TAR", "CDS", "CGARS"}]
    assert uffici and all(u["codice"] in catalogo.SEDI for u in uffici)


def test_foglio_excel_parti_ufficiale():
    dati = excel_parti.genera([
        {"tipologia": "Amministrazione", "denominazione": "Comune di Palmi", "codiceFiscale": "00000000000"},
        {"tipologia": "Persona fisica", "cognome": "Rossi", "nome": "Mario", "codiceFiscale": "rssmra80a01h501u", "pec": "A@B.IT"},
        {"tipologia": "Minore/Incapacita", "cognome": "Verdi", "nome": "Ada",
         "denominazione": "Luca Verdi in qualità di esercente la responsabilità genitoriale sul minore Ada Verdi"},
    ])
    righe = excel_parti.leggi(dati)
    assert tuple(righe[0]) == excel_parti.INTESTAZIONE
    assert righe[1] == ["Amministrazione", "", "", "00000000000", "", "Comune di Palmi"]
    assert righe[2] == ["Persona fisica", "ROSSI", "MARIO", "RSSMRA80A01H501U", "a@b.it"]
    assert righe[3][0] == "Minore/Incapacita" and righe[3][5].startswith("Luca Verdi")
    with pytest.raises(ValueError):
        excel_parti.genera([])
    with pytest.raises(ValueError):
        excel_parti.genera([{"tipologia": "Ente"}])


def test_ruoli_delle_parti_proposti_e_scelti():
    cliente = {"tipo": "PERSONA_FISICA", "cognome": "Bianchi", "nome": "Luca", "codice_fiscale": "BNCLCU80A01H501U"}
    soggetti = [("CONTROPARTE", {"id": "s1", "tipo": "PUBBLICA_AMMINISTRAZIONE", "ragione_sociale": "Comune di Palmi"}),
                ("CONTROPARTE", {"id": "s2", "tipo": "PERSONA_GIURIDICA", "ragione_sociale": "Impresa Srl"}),
                ("TESTIMONE", {"id": "s3", "tipo": "PERSONA_FISICA", "cognome": "Neri"})]
    elenco = parti.parti_pat(cliente, soggetti)
    assert [(p["ruolo"], p["tipologia"]) for p in elenco] == [
        ("ricorrente", "Persona fisica"), ("resistente", "Amministrazione"), ("controinteressato", "Persona giuridica")]
    scelto = parti.parti_pat(cliente, soggetti, scelte={"s2": "escludi", "s1": "controinteressato"})
    assert [(p["id"], p["ruolo"]) for p in scelto] == [("cliente", "ricorrente"), ("s1", "controinteressato")]
    resistente = parti.parti_pat(cliente, soggetti, posizione="resistente")
    assert resistente[0]["ruolo"] == "resistente" and resistente[1]["ruolo"] == "ricorrente"


def test_contributo_unificato_art_13_comma_6_bis():
    from pct.strumenti_legali import GestioneStrumentiLegali

    calcola = GestioneStrumentiLegali().calcola_contributo_unificato
    assert contributo.proposta("1", False, None, calcola)["importo"] == 650
    assert contributo.proposta("85", False, None, calcola)["importo"] == 300
    assert contributo.proposta("Z3", True, None, calcola)["importo"] == 975  # impugnazione: + metà
    assert contributo.proposta("96", False, None, calcola)["esenzione"] == "RICORSI ELETTORALI"
    assert contributo.proposta("", False, None, calcola)["importo"] is None


def _contesto(**kw):
    ctx = {"fascicolo": {"oggetto": "Annullamento della delibera"}, "avvocato": {"nome": "Avv. Prova"},
           "procedimento": {"sede": "tar_rc", "tipoRicorso": "1", "cuTipologia": "Non esente",
                            "attoImpugnato": {"organo": "Comune di Palmi", "tipo": "DELIBERA", "numero": "12", "anno": "2026"}},
           "parti": parti.parti_pat({"tipo": "PERSONA_FISICA", "cognome": "Bianchi", "nome": "Luca"},
                                    [("CONTROPARTE", {"id": "s1", "tipo": "PUBBLICA_AMMINISTRAZIONE", "ragione_sociale": "Comune"})]),
           "documenti": [{"ruolo": "atto", "nome": "Ricorso.pdf", "nomeProposto": "Ricorso.pdf", "esiti": [], "bloccante": False},
                         {"ruolo": "procura", "nome": "Procura.pdf", "nomeProposto": "Procura.pdf", "esiti": [], "bloccante": False},
                         {"ruolo": "notifica", "nome": "Relata.pdf", "nomeProposto": "Relata.pdf", "esiti": [], "bloccante": False}],
           "contributo": {"importo": 650.0, "nota": "", "versamento": "25/09/2026 · F24 · 650"}}
    ctx.update(kw)
    return ctx


def test_scheda_ricorso_nell_ordine_del_portale():
    esito = scheda.scheda(_contesto(), "ricorso")
    titoli = [s["titolo"] for s in esito["sezioni"]]
    assert titoli == ["Creazione della bozza", "Parti", "Ricorso, procura e allegati", "Segnala istanze/domande",
                      "Notifiche", "Contributo unificato", "Riepilogo, firma e invio"]
    bozza = {r["etichetta"]: r["valore"] for r in esito["sezioni"][0]["righe"]}
    assert bozza["Sede"] == "TAR CALABRIA - REGGIO CALABRIA" and bozza["Tipologia"] == "ORDINARIO"
    assert bozza["Autorità giurisdizionale"] == "TAR" and bozza["Oggetto"] == "Annullamento della delibera"
    assert esito["mancanti"] == [] and esito["daVerificare"] == ["Contributo unificato: Importo dovuto"]
    parti_riga = esito["sezioni"][1]["righe"]
    assert parti_riga[1]["excel"] == "resistente" and parti_riga[2]["stato"] == "facoltativo"


def test_scheda_segnala_quello_che_manca_senza_inventare():
    vuoto = _contesto(procedimento={"sede": "cds"}, documenti=[], parti=[], contributo={})
    esito = scheda.scheda(vuoto, "ricorso")
    assert not esito["pronto"]
    assert "Parti: Ricorrenti" in esito["mancanti"] and "Ricorso, procura e allegati: Ricorso" in esito["mancanti"]
    assert "Creazione della bozza: Cassazionista" in esito["daVerificare"]
    righe = [r for s in esito["sezioni"] for r in s["righe"] if r["stato"] == "manca"]
    assert all(r["valore"] == "da indicare" and not r["copia"] for r in righe)
    successivo = scheda.scheda(_contesto(procedimento={"sede": "tar_rc", "nrg": "202600123"}), "atto-successivo")
    assert {"etichetta": "NRG", "valore": "202600123"}.items() <= next(
        r for r in successivo["sezioni"][0]["righe"] if r["etichetta"] == "NRG").items()


def test_verifica_del_riepilogo_con_le_impronte():
    ricorso = pdf_pades(pdf_testo("Ricorso"))
    procura = pdf_testo("Procura alle liti")
    h1 = hashlib.sha256(ricorso).hexdigest().upper()
    h2 = hashlib.sha256(procura).hexdigest().upper()
    estranea = hashlib.sha256(b"altro").hexdigest().upper()
    testo = ["Giustizia amministrativa", "Riepilogo Deposito Ricorso", "Sede: TAR CALABRIA - REGGIO CALABRIA",
             "Ricorso 1740166806352.pdf", h1[:30], h1[30:],
             "Procura alle liti 1740166791626.pdf 24/04/2026", h2[:25], h2[25:50], h2[50:],
             "Firma digitale"]
    attesi = [{"nome": "Ricorso.pdf", "sha256": h1}, {"nome": "Procura.pdf", "sha256": h2}]
    firmato = pdf_pades(riepilogo_pdf(testo))
    esito = riepilogo.verifica(firmato, "RiepilogoGenerato_3100_firmato.pdf", attesi)
    assert esito.firma == "pades" and esito.titolo == "Ricorso" and esito.sede == "TAR CALABRIA - REGGIO CALABRIA"
    assert esito.impronte == [h1, h2] and esito.conforme
    non_firmato = riepilogo.verifica(riepilogo_pdf(testo), "Riepilogo.pdf", attesi)
    assert non_firmato.firma == "assente" and not non_firmato.conforme
    cambiato = riepilogo.verifica(firmato, "r.pdf", attesi + [{"nome": "Allegato.pdf", "sha256": estranea}])
    assert not cambiato.conforme and cambiato.documenti[2]["nelRiepilogo"] is False
    con_estraneo = riepilogo.verifica(pdf_pades(riepilogo_pdf(testo + [estranea[:32], estranea[32:]])), "r.pdf", attesi)
    assert con_estraneo.estranee == [estranea] and not con_estraneo.conforme
    busta = riepilogo.verifica(p7m(riepilogo_pdf(testo)), "Riepilogo.pdf.p7m", attesi)
    assert busta.firma == "cades" and busta.conforme
    assert not riepilogo.verifica(b"non pdf", "x.pdf", attesi).leggibile


def test_archivio_procedimento_ruoli_e_depositi(tmp_path):
    archivio = ArchivioPat(tmp_path / "pat.json")
    archivio.aggiorna_procedimento("F1", {"sede": "tar_rc", "ignoto": "x"})
    archivio.imposta_ruolo("F1", "s1", "controinteressato")
    archivio.imposta_documento("F1", "d1", "procura", "Procura " * 40)
    deposito = archivio.registra_deposito("F1", {"tipo": "ricorso"})
    archivio.registra_deposito("F1", {"id": deposito["id"], "stato": "inviato", "identificativo": "TAR-1"})
    voce = archivio.fascicolo("F1")
    assert voce["procedimento"]["sede"] == "tar_rc" and "ignoto" not in voce["procedimento"]
    assert voce["ruoli"] == {"s1": "controinteressato"} and len(voce["documenti"]["d1"]["descrizione"]) == 150
    assert [(d["stato"], d["identificativo"]) for d in voce["depositi"]] == [("inviato", "TAR-1")]
    for errato in (lambda: archivio.imposta_ruolo("F1", "s1", "giudice"),
                   lambda: archivio.registra_deposito("F1", {"stato": "perso"}),
                   lambda: archivio.aggiorna_procedimento("F1", {"posizione": "testimone"})):
        with pytest.raises(ValueError):
            errato()
