"""Deposito penale telematico (PDP): catalogo, calendario, controlli, ricevute, export."""

from __future__ import annotations

import datetime as dt
import io
import zipfile

from pct.penale_pdp import calendario, catalogo, stati
from pct.penale_pdp.controlli import Richiesta, avviso_indagini_nei_titoli, controlla
from pct.penale_pdp.controlli_file import FileDeposito, controlla_file
from pct.penale_pdp.export_pdp import leggi_export, leggi_protocolli
from pct.penale_pdp.ricevute import confronta_ricevuta, leggi_ricevuta
from pct.penale_pdp.ricevute import testo_pdf as estrai_testo_pdf
from pct.pec_capienza import valuta

CF = "RSSMRA80A01H501U"


def pdf_testo(testo: str = "Atto di nomina del difensore di fiducia nel procedimento penale n. 1096/2023") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    pagina.drawString(72, 750, testo)
    pagina.drawString(72, 730, testo)
    pagina.save()
    return buffer.getvalue()


def p7m(contenuto: bytes, cf: str = CF) -> bytes:
    """Busta CAdES reale con certificato che porta il codice fiscale nel serialNumber (TINIT-…)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.x509.oid import NameOID

    chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Mario Rossi"), x509.NameAttribute(NameOID.SERIAL_NUMBER, f"TINIT-{cf}")])
    ora = dt.datetime.now(dt.timezone.utc)
    certificato = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chiave.public_key())
                   .serial_number(x509.random_serial_number()).not_valid_before(ora - dt.timedelta(days=1))
                   .not_valid_after(ora + dt.timedelta(days=365)).sign(chiave, hashes.SHA256()))
    return (pkcs7.PKCS7SignatureBuilder().set_data(contenuto).add_signer(certificato, chiave, hashes.SHA256())
            .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary]))


def test_catalogo_segue_le_tabelle_codificate_del_portale():
    assert len(catalogo.voci()) >= 170
    nomina = catalogo.voce("P02")
    assert nomina and nomina.principale and "PM-U" in nomina.uffici and nomina.contestuali == "*"
    # La lista testi non si deposita in Procura (manuale PDP, «Deposito atti successivi»).
    assert "PCZ" not in {v.codice for v in catalogo.atti_ammessi("PM-U")}
    # Il ruolo filtra: la remissione di querela è della persona offesa, non dell'imputato.
    assert "P21" in {v.codice for v in catalogo.atti_ammessi("PM-U", ["OFF"])}
    assert "P21" not in {v.codice for v in catalogo.atti_ammessi("PM-U", ["IND"])}
    # Procedimento avocato: alla Procura Generale gli atti del PM, tranne la richiesta di avocazione.
    avocati = {v.codice for v in catalogo.atti_ammessi("PGCAP-U", avocato_pg=True)}
    assert "P33" in avocati and "P33" not in {v.codice for v in catalogo.atti_ammessi("PGCAP-U")}
    # Menu «Impugnazioni o Ricorsi in Cassazione al Riesame»: atti principali verso il Riesame.
    assert {"PB2", "PB4", "PAO", "PB5", "PB6", "PB7", "PCB"} <= {v.codice for v in catalogo.atti_ammessi("RIE", principali=True)}
    scheda = catalogo.scheda("P18")
    assert [c["chiave"] for c in scheda["campi"]][:1] == ["tipo_pena"]
    assert catalogo.contestuali_per("P20", "DIB-U", ["IND"])[0].codice == "P54"


def test_calendario_degli_obblighi():
    oggi = dt.date(2026, 9, 25)
    assert calendario.canale("DIB-U", oggi)["obbligatorio"] is True
    corte = calendario.canale("CAP-U", oggi)
    assert corte["obbligatorio"] is False and corte["dal"] == "2027-07-01"
    assert calendario.canale("CAP-U", dt.date(2027, 7, 1))["obbligatorio"] is True
    assert calendario.canale("GP-G", oggi)["dal"] == "2028-01-01"
    assert calendario.canale("CAP-U", dt.date(2028, 1, 1), atto="PB8")["obbligatorio"] is False


def test_stati_ufficiali_dal_testo_del_portale():
    assert stati.normalizza("Rifiutato") == "RIGETTATO"
    assert stati.normalizza("In fase di verifica") == "IN_FASE_DI_VERIFICA"
    assert stati.normalizza("Accettato") == "ACCOLTO"
    assert stati.normalizza("Errore Tecnico") == "ERRORE_TECNICO"
    assert stati.normalizza("boh") == ""


def test_firma_cades_e_firmatario():
    atto = p7m(pdf_testo())
    ok = controlla_file(FileDeposito("principale", "nomina.pdf.p7m", atto), cf_avvocato=CF)
    codici = [e.codice for e in ok.esiti]
    assert "FIRMA_OK" in codici or "FIRMA_NON_VERIFICATA" in codici
    assert ok.firmatari[0]["codiceFiscale"] == CF
    altro = controlla_file(FileDeposito("principale", "nomina.pdf.p7m", atto), cf_avvocato="VRDLGI80A01H501X")
    assert "FIRMATARIO_DIVERSO" in [e.codice for e in altro.esiti]
    senza = controlla_file(FileDeposito("principale", "nomina.pdf", pdf_testo()), cf_avvocato=CF)
    assert "FIRMA_ASSENTE" in [e.codice for e in senza.esiti]


def test_file_nome_oggetto_formato():
    lungo = controlla_file(FileDeposito("allegato", "a" * 101 + ".pdf", pdf_testo(), oggetto="x"))
    assert "NOME_LUNGO" in [e.codice for e in lungo.esiti]
    senza_oggetto = controlla_file(FileDeposito("allegato", "prova.pdf", pdf_testo()))
    assert "OGGETTO_MANCANTE" in [e.codice for e in senza_oggetto.esiti]
    formato = controlla_file(FileDeposito("allegato", "prova.docx", b"PK..", oggetto="prova"))
    assert "FORMATO_ALLEGATO" in [e.codice for e in formato.esiti]


def test_deposito_completo_nomina_in_procura():
    atto = FileDeposito("principale", "nomina.pdf.p7m", p7m(pdf_testo()))
    base = dict(atto="P02", ufficio="PM-U", soggetti=[{"nome": "Mario Bianchi", "ruolo": "IND"}], cf_avvocato=CF)
    senza_abilitante = controlla(Richiesta(file=[atto], **base))
    assert "ABILITANTE" in [e["codice"] for e in senza_abilitante["esiti"]] and not senza_abilitante["pronto"]
    con_avviso = controlla(Richiesta(file=[FileDeposito("principale", "nomina.pdf.p7m", atto.dati)], avviso_indagini_presente=True, **base))
    assert "ABILITANTE" not in [e["codice"] for e in con_avviso["esiti"]]
    abilitante = FileDeposito("abilitante", "verbale.pdf", pdf_testo("Verbale di identificazione"), oggetto="Verbale di identificazione")
    pronto = controlla(Richiesta(file=[FileDeposito("principale", "nomina.pdf.p7m", atto.dati), abilitante], **base))
    assert [e for e in pronto["esiti"] if e["livello"] == "errore"] == [] and pronto["pronto"]
    assert len(pronto["file"][0]["sha256"]) == 64


def test_atto_successivo_richiede_procedimento_autorizzato_e_dati():
    atto = FileDeposito("principale", "patteggiamento.pdf.p7m", p7m(pdf_testo("Istanza di patteggiamento")))
    richiesta = Richiesta(atto="P18", ufficio="DIB-U", soggetti=[{"nome": "Mario Bianchi", "ruolo": "IND"}], file=[atto],
                          dati={"tipo_pena": "Arresto", "pena_pecuniaria": "Multa"}, cf_avvocato=CF)
    codici = [e["codice"] for e in controlla(richiesta)["esiti"]]
    assert {"NON_AUTORIZZATO", "PENA", "PENA_PECUNIARIA", "IMPORTO_MANCANTE"} <= set(codici)
    persona_offesa = Richiesta(atto="P18", ufficio="DIB-U", soggetti=[{"nome": "Anna Verdi", "ruolo": "OFF"}], file=[atto],
                               procedimento_autorizzato=True, cf_avvocato=CF)
    assert "RUOLO" in [e["codice"] for e in controlla(persona_offesa)["esiti"]]
    ufficio = Richiesta(atto="PCZ", ufficio="PM-U", soggetti=[{"nome": "Mario Bianchi", "ruolo": "IND"}], file=[atto],
                        procedimento_autorizzato=True, cf_avvocato=CF)
    assert "UFFICIO" in [e["codice"] for e in controlla(ufficio)["esiti"]]


def test_procura_speciale_per_elezione_di_domicilio():
    atto = FileDeposito("principale", "elezione.pdf.p7m", p7m(pdf_testo("Elezione di domicilio")))
    base = dict(atto="P24", ufficio="DIB-U", soggetti=[{"nome": "Mario Bianchi", "ruolo": "IND"}], file=[atto],
                dati={"domicilio": "presso il legale"}, procedimento_autorizzato=True, cf_avvocato=CF)
    assert "PROCURA_SPECIALE" in [e["codice"] for e in controlla(Richiesta(**base))["esiti"]]
    base["file"] = [FileDeposito("principale", "elezione.pdf.p7m", atto.dati)]
    assert "PROCURA_SPECIALE" not in [e["codice"] for e in controlla(Richiesta(procura_speciale_dichiarata=True, **base))["esiti"]]


def test_avviso_indagini_nei_titoli():
    assert avviso_indagini_nei_titoli(["Avviso conclusione indagini ex art. 415 bis.pdf"])
    assert avviso_indagini_nei_titoli(["Richiesta di archiviazione.pdf"])
    assert not avviso_indagini_nei_titoli(["Verbale di sequestro.pdf"])


# Testi delle ricevute reali del PDP 6.11.10 (25/09/2026), con nomi di fantasia e le
# parole spezzate come le impagina il portale (crenatura: «POR T ALE», «pr ocedimento»).
RICEVUTA_DEPOSITO = [
    ["MINISTERO della GIUSTIZIA"], ["POR", "T", "ALE DEPOSITO atti PENALI (PDP)"],
    ["IDENTIFICA", "TIV", "O 2023/0582463 POR", "T", "ALE DEPOSITO atti PENALI"],
    ["L'avvocato ", "ROSSI ", "MARIO ", "RSSMRA80A01H501U ", "ha ", "inviato ", "all'u\ufb03cio ", "TRIBUNALE ", "ORDINARIO ", "DI ", "P", "ALMI ", "in ", "data"],
    ["01/12/2023 ", "alle ", "or", "e ", "16:50:23, ", "in ", "r", "elazione ", "al ", "pr", "ocedimento: ", "REGISTRO ", "NOTI ", "PM ", "nr", ". ", "1096/2023, ",
     "indirizzato ", "al ", "Magistrato"],
    ["VERDI ANNA, ", "l\u2019atto ", "di ", "Nomina ", "a ", "difensor", "e ", "di ", "\ufb01ducia, ", "n", "ell'inter", "esse"],
    ["dei ", "seguenti ", "so", "ggetti ", "rappr", "esentati, ", "in ", "qualit\u00e0 ", "di"], ["IND./IMP", ".", "/RESP", ".AMM.:"],
    ["BIANCHI LUCA 10/11/1987"], ["con nr", ". 0 allegati"],
    ["La presente ricevuta di accettazione attesta il deposito degli atti ai sensi dell\u2019art. 87, comma 6 bis, del decr", "eto legislativo 10"],
    ["ottobr", "e 2022 n. 150"], ["R", "oma, 01/12/2023 16:50"],
]
RICEVUTA_ESITO = [
    ["MINISTERO della GIUSTIZIA"], ["POR", "T", "ALE DEPOSITO atti PENALI (PDP)"], ["Esito deposito POR", "T", "ALE DEPOSITO atti PENALI"],
    ["Il deposito con IDENTIFICA", "TIV", "O 2023/0582463, inviato all'u\ufb03cio TRIBUNALE"],
    ["ORDINARIO DI P", "ALMI in data 01/12/2023 alle ore 16:50,"], ["\u00e8 stato rifiutato"],
    [" in data 04/12/2023 alle ore 09:14 con la seguente motivazione:"], ["U\ufb03cio destinatario non coer", "ente"], ["Roma, 25/09/2026 10:03"],
]


def _pdf_ricevuta(righe: list[list[str]]) -> bytes:
    """Una ricevuta impaginata come quelle del PDP: ogni frammento posizionato da solo."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    foglio = canvas.Canvas(buffer)
    y = 800.0
    for riga in righe:
        x = 20.0
        for frammento in riga:
            testo = frammento.replace("\ufb01", "fi").replace("\ufb03", "ffi")  # Helvetica non ha le legature
            oggetto = foglio.beginText(x, y)
            oggetto.setFont("Helvetica", 10)
            oggetto.textOut(testo)
            foglio.drawText(oggetto)
            x += stringWidth(testo, "Helvetica", 10)
        y -= 16
    foglio.save()
    return buffer.getvalue()


def _testo_spezzato(righe: list[list[str]]) -> str:
    """Il testo come lo restituisce un estrattore che separa ogni frammento."""
    return "\n".join(" ".join(riga) for riga in righe)


def test_ricevuta_di_deposito_reale_letta_e_confrontata():
    for testo in (estrai_testo_pdf(_pdf_ricevuta(RICEVUTA_DEPOSITO)), _testo_spezzato(RICEVUTA_DEPOSITO)):
        letti = leggi_ricevuta(testo)
        assert letti["tipo"] == "deposito" and letti["identificativo"] == "2023/0582463", testo
        assert letti["dataInvio"] == "2023-12-01T16:50:23" and letti["cfAvvocato"] == "RSSMRA80A01H501U"
        assert letti["registro"]["numero"] == "1096" and letti["registro"]["anno"] == "2023"
        assert "PALMI" in letti["ufficio"].replace(" ", "") and letti["allegati"] == 0 and letti["stato"] == "INVIATO"
        assert letti["soggetti"][0]["dataNascita"] == "1987-11-10"
        assert "fiducia" in letti["atto"].replace(" ", "")
    letti = leggi_ricevuta(estrai_testo_pdf(_pdf_ricevuta(RICEVUTA_DEPOSITO)))
    assert letti["atto"] == "Nomina a difensore di fiducia" and letti["magistrato"] == "VERDI ANNA"
    registri = [{"register_number": "1096", "register_year": "2023"}]
    confronto = confronta_ricevuta(letti, identificativo="2023/0582463", cf_avvocato="RSSMRA80A01H501U", ufficio_codice="PM-U",
                                   registri=registri, nome_atto="Nomina difensore di fiducia (artt. 96, 100, 101 cpp)",
                                   soggetti=[{"nome": "Bianchi Luca"}], file_preparati=[{"ruolo": "atto"}])
    # Il caso reale: nomina con registro PM inviata al Tribunale ordinario, rifiutata per ufficio non coerente.
    assert [v["campo"] for v in confronto["voci"] if not v["ok"]] == ["ufficio"]
    assert confronto["totale"] == 7 and "ufficio destinatario" in confronto["messaggio"]
    giusto = confronta_ricevuta(letti, ufficio_codice="DIB-U", registri=registri, file_preparati=[{"ruolo": "allegato"}])
    assert [v["campo"] for v in giusto["voci"] if not v["ok"]] == ["allegati"]


def test_ricevuta_di_esito_reale():
    for testo in (estrai_testo_pdf(_pdf_ricevuta(RICEVUTA_ESITO)), _testo_spezzato(RICEVUTA_ESITO)):
        esito = leggi_ricevuta(testo)
        assert esito["tipo"] == "esito" and esito["stato"] == "RIGETTATO", testo
        assert esito["identificativo"] == "2023/0582463" and esito["dataInvio"] == "2023-12-01T16:50:00"
        assert esito["dataEsito"] == "2023-12-04T09:14:00"
        assert esito["motivazione"].replace(" ", "") == "Ufficiodestinatariononcoerente"
    accolto = leggi_ricevuta("Il deposito con IDENTIFICATIVO 2024/0001234, inviato all'ufficio PROCURA DELLA REPUBBLICA DI PALMI "
                             "in data 02/02/2024 alle ore 10:00, è stato accettato in data 03/02/2024 alle ore 11:30 Roma, 03/02/2024 12:00")
    assert accolto["stato"] == "ACCOLTO" and accolto["motivazione"] == ""


def _xlsx(righe: list[list[str]]) -> bytes:
    stringhe: list[str] = []
    celle_xml = []
    for r, riga in enumerate(righe, start=1):
        celle = []
        for c, valore in enumerate(riga):
            stringhe.append(valore)
            celle.append(f'<c r="{chr(65 + c)}{r}" t="s"><v>{len(stringhe) - 1}</v></c>')
        celle_xml.append(f'<row r="{r}">{"".join(celle)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archivio:
        archivio.writestr("xl/workbook.xml", f'<workbook {ns} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                          '<sheets><sheet name="Elenco" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archivio.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                          '<Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
        archivio.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in stringhe) + "</sst>")
        archivio.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(celle_xml)}</sheetData></worksheet>')
    return buffer.getvalue()


def test_export_depositi_xlsx_e_protocolli():
    assert leggi_protocolli("PM: N2023/1096 GIP: N2023/1317") == [
        {"sigla": "PM", "ufficio": "PM-U", "registro": "N", "anno": "2023", "numero": "1096"},
        {"sigla": "GIP", "ufficio": "GIP-U", "registro": "N", "anno": "2023", "numero": "1317"},
    ]
    dati = _xlsx([
        ["Ident. Invio", "Data Invio", "Data Arrivo", "Num. Registro", "Ufficio", "Magistrato", "Soggetti Rappr.", "Tipo Atto", "Stato"],
        ["2023/0582463", "01/12/2023 16:50", "01/12/2023 16:55", "PM: N2023/1096", "TRIBUNALE DI PALMI", "ROSSI", "S. R.",
         "Nomina difensore di fiducia (artt. 96, 100, 101 cpp)", "Rifiutato"],
    ])
    letto = leggi_export(dati)
    assert letto["tipo"] == "depositi"
    riga = letto["righe"][0]
    assert riga["identificativo"] == "2023/0582463" and riga["stato"] == "RIGETTATO" and riga["dataInvio"] == "2023-12-01T16:50"
    assert riga["protocolli"][0]["numero"] == "1096"
    csv = "Data Nomina;Numero Registro;Ufficio;Magistrato;Soggetti Rappresentati\n;PM: N2023/1096;PROCURA DI PALMI;LUCISANO;S. R.\n"
    assert leggi_export(csv.encode("utf-8"))["tipo"] == "procedimenti"


def test_capienza_pec():
    assert valuta('* QUOTA "" (STORAGE 900 1000)')["livello"] == "attenzione"
    assert valuta('* QUOTA "" (STORAGE 990 1000)')["livello"] == "critico"
    assert valuta('* QUOTA "" (STORAGE 10 1000)')["livello"] == "ok"
    assert valuta("")["supportata"] is False


def test_nomina_verso_ufficio_non_coerente_con_il_registro():
    def esiti(ufficio: str, registri: tuple[str, ...]) -> list[str]:
        richiesta = Richiesta(atto="P02", ufficio=ufficio, soggetti=[{"nome": "Bianchi Luca", "ruolo": "IND"}], file=[],
                              avviso_indagini_presente=True, uffici_registro=registri)
        return [e["codice"] for e in controlla(richiesta)["esiti"]]

    assert "UFFICIO_NON_COERENTE" in esiti("DIB-U", ("PM-U",))  # il rigetto reale del PDP
    assert "UFFICIO_NON_COERENTE" not in esiti("PM-U", ("PM-U",))
    assert "UFFICIO_NON_COERENTE" not in esiti("GIP-U", ("PM-U",))
    assert "UFFICIO_NON_COERENTE" not in esiti("DIB-U", ("PM-U", "DIB-U"))


def test_distretto_e_circondario_per_la_maschera_del_pdp():
    from pct.penale_pdp.sede import sede_pdp
    from pct.uffici_giudiziari import _build_bundle_completo

    uffici = _build_bundle_completo()
    # Scritture e codici dei codificati del PDP 6.11.10 (distretti/circondari/sediuffici).
    assert sede_pdp("Procura della Repubblica presso il Tribunale di Palmi", uffici) == {
        "distretto": "REGGIO CALABRIA", "circondario": "PALMI",
        "sede": "PROCURA DELLA REPUBBLICA DI PALMI", "codiceSede": "08005702100"}
    assert sede_pdp("Tribunale di Reggio Calabria", uffici)["distretto"] == "REGGIO CALABRIA"
    assert sede_pdp("Tribunale di Milano", uffici, "DIB-U")["sede"] == "TRIBUNALE DI MILANO"
    assert sede_pdp("Tribunale di Bolzano", uffici)["circondario"] == "BOLZANO/BOZEN"
    assert sede_pdp("Tribunale di Massa Carrara", uffici)["circondario"] == "MASSA"
    assert sede_pdp("Tribunale di Napoli Nord", uffici)["circondario"] == "NAPOLI NORD"
    assert sede_pdp("TRIBUNALE DI CUNEO ex TRIBUNALE DI MONDOVI", uffici)["circondario"] == "CUNEO"
    assert sede_pdp("Tribunale di Chiavari", uffici)["circondario"] == "GENOVA"  # D.Lgs. 155/2012
    gip = sede_pdp("Tribunale di Milano", uffici, "GIP-U")
    assert gip["circondario"] == "MILANO" and gip["sede"] == ""  # sede non in catalogo: si sceglie sul PDP
    assert sede_pdp("Ufficio sconosciuto", uffici) == {"distretto": "", "circondario": "", "sede": "", "codiceSede": ""}
    tribunali = [u for u in uffici if u["tipo"] == "TRIBUNALE"]
    assert all(sede_pdp(u["nome"], uffici, "DIB-U")["codiceSede"] for u in tribunali)


def _server_imap(quota: bool, comandi: list[str]) -> tuple[int, object]:
    """Un server IMAP minimo (RFC 3501 + QUOTA RFC 2087) che registra i comandi ricevuti."""
    import socket
    import threading

    ascolto = socket.socket()
    ascolto.bind(("127.0.0.1", 0))
    ascolto.listen(1)

    def servi() -> None:
        conn, _ = ascolto.accept()
        flusso = conn.makefile("rwb")
        capacita = b"IMAP4rev1 AUTH=PLAIN" + (b" QUOTA" if quota else b"")
        flusso.write(b"* OK [CAPABILITY " + capacita + b"] pronto\r\n"); flusso.flush()
        for riga in flusso:
            etichetta, comando = (riga.decode().strip().split(" ", 2) + [""])[:2]
            comandi.append(comando.upper())
            if comando.upper() == "CAPABILITY":
                flusso.write(b"* CAPABILITY " + capacita + b"\r\n")
            elif comando.upper() == "GETQUOTAROOT":
                flusso.write(b'* QUOTAROOT INBOX ""\r\n* QUOTA "" (STORAGE 1900000 2000000)\r\n')
            elif comando.upper() == "LOGOUT":
                flusso.write(b"* BYE\r\n" + etichetta.encode() + b" OK fatto\r\n"); flusso.flush()
                break
            flusso.write(etichetta.encode() + b" OK fatto\r\n"); flusso.flush()
        conn.close()
        ascolto.close()

    filo = threading.Thread(target=servi, daemon=True)
    filo.start()
    return ascolto.getsockname()[1], filo


def test_capienza_pec_via_imap_senza_scrivere_nulla():
    from pct.pec_capienza import leggi_capienza

    comandi: list[str] = []
    porta, filo = _server_imap(True, comandi)
    esito = leggi_capienza("127.0.0.1", porta, "studio@pec.it", "segreta", ssl=False, timeout=5)
    filo.join(5)
    assert esito == {"supportata": True, "usatiKb": 1900000, "limiteKb": 2000000, "percentuale": 95.0, "livello": "critico"}
    # Solo lettura: nessun APPEND, STORE, EXPUNGE, DELETE o SELECT in scrittura.
    assert set(comandi) <= {"CAPABILITY", "LOGIN", "GETQUOTAROOT", "LOGOUT"}, comandi

    comandi = []
    porta, filo = _server_imap(False, comandi)
    assert leggi_capienza("127.0.0.1", porta, "studio@pec.it", "segreta", ssl=False, timeout=5) == {"supportata": False}
    filo.join(5)
    assert "GETQUOTAROOT" not in comandi
