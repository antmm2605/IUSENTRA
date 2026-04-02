"""
Simulazione completa del ciclo di deposito telematico per tutti e tre i portali:
  - PCT  → Processo Civile Telematico (PST / polisWeb)
  - PDP  → Portale Deposito Atti Penali
  - PAT  → Processo Amministrativo Telematico (SIGA)

Ogni test verifica le 4 fasi richieste dal Portale Servizi Telematici:
  Fase 1 → Invio atto (INVIATO)
  Fase 2 → Ricevuta accettazione PEC (ACCETTATO_PEC)
  Fase 3 → Ricevuta consegna (CONSEGNATO)
  Fase 4 → Esito controlli automatici (WARN_CONTROLLI / ERRORE_CONTROLLI / OK)
  Fase 5 → Esito cancelleria (ACCETTATO_CANCELLERIA / RIFIUTATO_CANCELLERIA)
"""

import os
import sys
import uuid
import zipfile
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

# Assicura che il progetto sia nel sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pct.busta import BustaTelematica, DatiBusta, Allegato
from pct.fascicoli import EsitoDepositoPCT
from pct.pdp import ClientPDPDemo, crea_client_pdp
from pct.pat import ClientPATDemo, crea_client_pat


# ================================================================== Fixtures

PDF_MINIMO = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"
)


@pytest.fixture
def tmp_atto(tmp_path):
    """PDF minimo come atto principale."""
    p = tmp_path / "memoria_difensiva.pdf"
    p.write_bytes(PDF_MINIMO)
    return str(p)


@pytest.fixture
def tmp_atto_firmato(tmp_path):
    """Simula un PDF firmato digitalmente (.p7m)."""
    p = tmp_path / "memoria_difensiva.pdf.p7m"
    # Contenuto fittizio — in produzione sarebbe il vero CAdES wrapper
    p.write_bytes(b"\x30\x82" + PDF_MINIMO)
    return str(p)


@pytest.fixture
def tmp_allegato(tmp_path):
    """PDF allegato."""
    p = tmp_path / "procura_alle_liti.pdf"
    p.write_bytes(PDF_MINIMO)
    return str(p)


@pytest.fixture
def dati_busta_pct(tmp_atto, tmp_allegato):
    """DatiBusta per una Memoria in un fascicolo civile."""
    return DatiBusta(
        codice_ufficio="0580010",    # Tribunale di Milano
        codice_registro="CIVILE",
        oggetto="Memoria difensiva — RG 1234/2024",
        tipo_atto="MEMORIA",
        atto_principale=tmp_atto,
        allegati=[
            Allegato(
                percorso=tmp_allegato,
                descrizione="Procura alle liti",
                tipo="ALLEGATO",
            )
        ],
        numero_rg="1234",
        anno_rg=2024,
        cf_mittente="RSSMRA80A01H501Z",
        operatore="Avv. Mario Rossi",
    )


# ================================================================== PCT — Busta telematica

class TestPCTBusta:
    """Fase 1 PCT: creazione e verifica struttura busta .enc."""

    def test_busta_creata(self, dati_busta_pct, tmp_path):
        busta = BustaTelematica(dati_busta_pct)
        path  = busta.crea_busta(str(tmp_path / "output"))
        assert Path(path).exists(), "Il file .enc deve esistere dopo la creazione"
        assert path.endswith(".enc"), "Il file deve avere estensione .enc"

    def test_busta_contiene_datiatto_xml(self, dati_busta_pct, tmp_path):
        busta = BustaTelematica(dati_busta_pct)
        path  = busta.crea_busta(str(tmp_path / "output"))
        with zipfile.ZipFile(path, "r") as zf:
            assert "DatiAtto.xml" in zf.namelist(), "DatiAtto.xml obbligatorio per PST"

    def test_busta_contiene_atto_principale(self, dati_busta_pct, tmp_path):
        busta = BustaTelematica(dati_busta_pct)
        path  = busta.crea_busta(str(tmp_path / "output"))
        with zipfile.ZipFile(path, "r") as zf:
            nomi = zf.namelist()
            assert "memoria_difensiva.pdf" in nomi, "L'atto principale deve essere incluso"

    def test_busta_contiene_allegato(self, dati_busta_pct, tmp_path):
        busta = BustaTelematica(dati_busta_pct)
        path  = busta.crea_busta(str(tmp_path / "output"))
        with zipfile.ZipFile(path, "r") as zf:
            nomi = zf.namelist()
            assert "procura_alle_liti.pdf" in nomi, "L'allegato deve essere incluso"

    def test_datiatto_xml_struttura(self, dati_busta_pct, tmp_path):
        """Verifica che DatiAtto.xml rispetti la struttura PST (D.M. 44/2011)."""
        from lxml import etree

        busta = BustaTelematica(dati_busta_pct)
        path  = busta.crea_busta(str(tmp_path / "output"))

        with zipfile.ZipFile(path, "r") as zf:
            xml_bytes = zf.read("DatiAtto.xml")

        root = etree.fromstring(xml_bytes)
        ns   = {"p": "http://www.giustizia.it/processo_telematico"}

        # Elemento radice
        assert root.tag.endswith("DatiAtto"), "Radice deve essere DatiAtto"

        # IdBusta
        id_el = root.find("p:IdBusta", ns)
        assert id_el is not None and id_el.text, "IdBusta obbligatorio"

        # CodiceUfficio
        cod_el = root.find(".//p:CodiceUfficio", ns)
        assert cod_el is not None and cod_el.text == "0580010"

        # TipoAtto
        tipo_el = root.find(".//p:TipoAtto", ns)
        assert tipo_el is not None and tipo_el.text == "MEMORIA"

        # Attoprincipale — nome corretto per spec PST (NON AttoprincipAle)
        ap_el = root.find(".//p:Attoprincipale", ns)
        assert ap_el is not None, (
            "L'elemento <Attoprincipale> è obbligatorio (spec. D.M. 44/2011). "
            "Il vecchio nome <AttoprincipAle> era errato e verrebbe rifiutato dal PST."
        )

        # Hash SHA-256 presente e lunghezza 64 caratteri
        hash_el = ap_el.find("p:Hash", ns)
        assert hash_el is not None and len(hash_el.text) == 64, "Hash SHA-256 obbligatorio"

    def test_verifica_busta_integrita(self, dati_busta_pct, tmp_path):
        busta    = BustaTelematica(dati_busta_pct)
        path     = busta.crea_busta(str(tmp_path / "output"))
        verifica = busta.verifica_busta(path)
        assert verifica["valida"] is True, f"Busta non valida: {verifica['errori']}"
        assert verifica["id_busta"] is not None, "id_busta deve essere valorizzato"

    def test_id_busta_univoco(self, dati_busta_pct, tmp_path):
        b1 = BustaTelematica(dati_busta_pct)
        b2 = BustaTelematica(dati_busta_pct)
        assert b1.id_busta != b2.id_busta, "Ogni busta deve avere un ID univoco"


# ================================================================== PCT — Ciclo stati EsitoDepositoPCT

class TestPCTStateMachine:
    """Fasi 2-5 PCT: progressione degli stati del deposito."""

    def _make_esito(self, stato: str, **kwargs) -> EsitoDepositoPCT:
        return EsitoDepositoPCT(
            id=str(uuid.uuid4())[:8].upper(),
            timestamp=datetime.now().isoformat(),
            stato=stato,
            tipo_atto="MEMORIA",
            pec_destinatario="tribunale.milano@giustiziapec.it",
            **kwargs,
        )

    def test_stato_inviato(self):
        """Fase 1: dopo l'invio PEC lo stato iniziale è INVIATO."""
        esito = self._make_esito("INVIATO")
        assert esito.stato == "INVIATO"
        assert esito.ricevuta_accettazione == ""
        assert esito.ricevuta_consegna == ""

    def test_stato_accettato_pec(self):
        """Fase 2: dopo ricevuta di accettazione PEC → ACCETTATO_PEC."""
        esito = self._make_esito(
            "ACCETTATO_PEC",
            ricevuta_accettazione="<acc-id@pec.aruba.it>",
        )
        assert esito.stato == "ACCETTATO_PEC"
        assert esito.ricevuta_accettazione != ""

    def test_stato_consegnato(self):
        """Fase 3: dopo ricevuta di consegna → CONSEGNATO."""
        esito = self._make_esito(
            "CONSEGNATO",
            ricevuta_accettazione="<acc-id@pec.aruba.it>",
            ricevuta_consegna="<cons-id@giustiziapec.it>",
        )
        assert esito.stato == "CONSEGNATO"
        assert esito.ricevuta_consegna != ""

    def test_stato_controlli_ok(self):
        """Fase 4: controlli automatici superati → esito_controlli = OK."""
        esito = self._make_esito(
            "CONSEGNATO",
            ricevuta_accettazione="<acc-id@pec.aruba.it>",
            ricevuta_consegna="<cons-id@giustiziapec.it>",
            ricevuta_controlli_automatici="Controlli OK — firma valida, formato conforme",
            esito_controlli="OK",
        )
        assert esito.esito_controlli == "OK"
        assert esito.ricevuta_controlli_automatici != ""

    def test_stato_controlli_warn(self):
        """Fase 4 (WARN): controlli con anomalie NON bloccanti → WARN_CONTROLLI."""
        esito = self._make_esito(
            "WARN_CONTROLLI",
            ricevuta_controlli_automatici="Anomalia: allegato mancante firma",
            esito_controlli="WARN",
        )
        assert esito.stato == "WARN_CONTROLLI"
        assert esito.esito_controlli == "WARN"

    def test_stato_errore_controlli(self):
        """Fase 4 (ERROR): controlli con errori bloccanti → ERRORE_CONTROLLI."""
        esito = self._make_esito(
            "ERRORE_CONTROLLI",
            ricevuta_controlli_automatici="Errore: firma digitale non valida",
            esito_controlli="ERROR",
        )
        assert esito.stato == "ERRORE_CONTROLLI"
        assert esito.esito_controlli == "ERROR"

    def test_stato_accettato_cancelleria(self):
        """Fase 5: accettato dalla cancelleria → ACCETTATO_CANCELLERIA."""
        esito = self._make_esito(
            "ACCETTATO_CANCELLERIA",
            ricevuta_accettazione="<acc-id@pec.aruba.it>",
            ricevuta_consegna="<cons-id@giustiziapec.it>",
            esito_controlli="OK",
            ricevuta_cancelleria="Deposito accettato — prot. 2024/DEPO/001",
        )
        assert esito.stato == "ACCETTATO_CANCELLERIA"
        assert esito.ricevuta_cancelleria != ""

    def test_stato_rifiutato_cancelleria(self):
        """Fase 5 (rifiuto): rifiutato dalla cancelleria → RIFIUTATO_CANCELLERIA."""
        esito = self._make_esito(
            "RIFIUTATO_CANCELLERIA",
            ricevuta_cancelleria="Deposito rifiutato — atto errato per questo registro",
        )
        assert esito.stato == "RIFIUTATO_CANCELLERIA"

    def test_serializzazione_to_dict(self):
        """EsitoDepositoPCT deve serializzare/deserializzare correttamente."""
        esito = self._make_esito(
            "ACCETTATO_CANCELLERIA",
            ricevuta_accettazione="<acc@pec.it>",
            ricevuta_consegna="<cons@pec.it>",
            esito_controlli="OK",
            ricevuta_cancelleria="Accettato — prot. 001",
            note="Test serializzazione",
        )
        d = esito.to_dict()
        ripristinato = EsitoDepositoPCT.from_dict(d)
        assert ripristinato.stato         == esito.stato
        assert ripristinato.esito_controlli == esito.esito_controlli
        assert ripristinato.ricevuta_cancelleria == esito.ricevuta_cancelleria


# ================================================================== PCT — Invio PEC (mock)

class TestPCTInvioPEC:
    """Fase 1 PCT: simulazione invio PEC con mock."""

    def test_invio_pec_simulato(self, dati_busta_pct, tmp_path):
        """Simula un invio PEC verificando la struttura della risposta."""
        from pct.pec import ClientPEC, ConfigPEC

        config = ConfigPEC(
            indirizzo="avv.test@pec.aruba.it",
            password="test_pwd",
            smtp_host="smtp.pec.aruba.it",
            smtp_port=465,
        )
        client = ClientPEC(config)

        # Crea la busta prima di inviare
        busta     = BustaTelematica(dati_busta_pct)
        busta_path = busta.crea_busta(str(tmp_path / "output"))

        # Mocka l'SMTP per evitare connessioni reali
        with patch("pct.pec._SMTP_SSLv4") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            risultato = client.invia_busta(
                destinatario_pec="tribunale.milano@giustiziapec.it",
                busta_path=busta_path,
                oggetto="DEPOSITO - Memoria difensiva RG 1234/2024",
            )

        # La risposta deve contenere i campi attesi dal PST
        assert "inviato"    in risultato, "Campo 'inviato' obbligatorio nella risposta"
        assert "message_id" in risultato or "errore" in risultato

    def test_risposta_invio_ok_struttura(self, dati_busta_pct, tmp_path):
        """Verifica struttura risposta positiva al momento dell'invio."""
        from pct.pec import ClientPEC, ConfigPEC

        config = ConfigPEC(
            indirizzo="avv.test@pec.aruba.it",
            password="test_pwd",
            smtp_host="smtp.pec.aruba.it",
            smtp_port=465,
        )
        client = ClientPEC(config)
        busta   = BustaTelematica(dati_busta_pct)
        path    = busta.crea_busta(str(tmp_path / "output"))

        with patch("pct.pec._SMTP_SSLv4") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server

            risultato = client.invia_busta(
                destinatario_pec="tribunale.milano@giustiziapec.it",
                busta_path=path,
            )

        assert risultato.get("inviato") is True, (
            f"L'invio PEC deve restituire inviato=True. Errore: {risultato.get('errore')}"
        )


# ================================================================== PDP — Simulazione deposito penale

class TestPDPDeposito:
    """Simulazione completa deposito atti penali via PDP."""

    def test_client_demo_disponibile(self):
        """Il client demo PDP deve essere istanziabile."""
        client = crea_client_pdp(demo=True)
        assert isinstance(client, ClientPDPDemo)

    def test_deposita_atto_risposta_struttura(self, tmp_atto_firmato):
        """Fase 1 PDP: l'invio deve restituire la struttura attesa dal portale."""
        client = ClientPDPDemo()
        risposta = client.deposita_atto(
            codice_ufficio="0580030",   # Procura di Milano
            tipo_atto="MEMORIA",
            atto_path=tmp_atto_firmato,
            numero_rg="4521",
            anno_rg=2024,
            oggetto="Memoria difensiva imputato Verdi",
        )

        # Campi obbligatori per spec RAP (Redattore Atti Penale)
        assert risposta.get("codiceEsito") == "0", (
            f"codiceEsito deve essere '0' per deposito accettato. "
            f"Risposta: {risposta}"
        )
        assert risposta.get("idDeposito"), "idDeposito obbligatorio nella risposta"
        assert risposta.get("dataDeposito"), "dataDeposito obbligatorio nella risposta"
        assert risposta.get("stato") == "INVIATO"

    def test_deposita_atto_id_prefisso_pdp(self, tmp_atto_firmato):
        """Il campo idDeposito deve avere il prefisso PDP-."""
        client = ClientPDPDemo()
        risposta = client.deposita_atto(
            codice_ufficio="0580030",
            tipo_atto="RICHIESTA",
            atto_path=tmp_atto_firmato,
        )
        assert risposta["idDeposito"].startswith("PDP-"), (
            "L'ID deposito PDP deve iniziare con 'PDP-'"
        )

    def test_deposita_atto_ricevuta_accettazione(self, tmp_atto_firmato):
        """Fase 2 PDP: la risposta deve contenere la ricevuta di accettazione PEC."""
        client = ClientPDPDemo()
        risposta = client.deposita_atto(
            codice_ufficio="0580030",
            tipo_atto="MEMORIA",
            atto_path=tmp_atto_firmato,
            numero_rg="4521",
            anno_rg=2024,
        )

        acc = risposta.get("ricevutaAccettazione", {})
        assert acc.get("mittente"), "Mittente PEC obbligatorio nella ricevuta"
        assert acc.get("oggetto"),  "Oggetto PEC obbligatorio nella ricevuta"
        assert acc.get("corpo"),    "Corpo PEC obbligatorio nella ricevuta"
        assert acc.get("messageId"), "Message-ID PEC obbligatorio nella ricevuta"
        assert "pec.giustizia.it" in acc["mittente"].lower(), (
            "Il mittente della ricevuta deve essere del dominio giustizia.it"
        )

    def test_deposita_atto_controlli_automatici(self, tmp_atto_firmato):
        """Fase 3 PDP: la risposta deve contenere l'esito dei controlli automatici."""
        client = ClientPDPDemo()
        risposta = client.deposita_atto(
            codice_ufficio="0580030",
            tipo_atto="MEMORIA",
            atto_path=tmp_atto_firmato,
        )

        ctrl = risposta.get("esitoControlli", {})
        assert ctrl.get("codice") in ("OK", "WARN", "ERROR"), (
            "esitoControlli.codice deve essere OK, WARN o ERROR"
        )
        assert isinstance(ctrl.get("messaggi"), list), (
            "esitoControlli.messaggi deve essere una lista"
        )
        assert len(ctrl["messaggi"]) > 0, "Almeno un messaggio di controllo richiesto"

        # Per la demo il codice è OK — verifica firma e formato
        assert ctrl["codice"] == "OK", "In demo mode i controlli devono risultare OK"
        check_texts = " ".join(ctrl["messaggi"]).lower()
        assert "firma" in check_texts, "I controlli devono includere verifica firma digitale"
        assert "pdf" in check_texts, "I controlli devono includere verifica formato PDF"

    def test_deposita_atto_esito_cancelleria(self, tmp_atto_firmato):
        """Fase 4 PDP: la risposta deve contenere l'esito della cancelleria/procura."""
        client = ClientPDPDemo()
        risposta = client.deposita_atto(
            codice_ufficio="0580030",
            tipo_atto="MEMORIA",
            atto_path=tmp_atto_firmato,
            numero_rg="4521",
            anno_rg=2024,
        )

        canc = risposta.get("esitoCancelleria", {})
        assert canc.get("stato") == "ACCETTATO_CANCELLERIA", (
            "In demo mode l'esito cancelleria deve essere ACCETTATO_CANCELLERIA"
        )
        assert canc.get("oggetto"), "Oggetto PEC cancelleria obbligatorio"
        assert canc.get("corpo"),   "Corpo PEC cancelleria obbligatorio"

    def test_deposita_atto_file_inesistente(self):
        """Un file inesistente deve produrre codiceEsito di errore."""
        client = ClientPDPDemo()
        risposta = client.deposita_atto(
            codice_ufficio="0580030",
            tipo_atto="MEMORIA",
            atto_path="/tmp/file_che_non_esiste.pdf.p7m",
        )
        assert risposta.get("codiceEsito") == "E_FILE", (
            "Un file inesistente deve restituire codiceEsito='E_FILE'"
        )
        assert risposta.get("stato") == "ERRORE"

    def test_deposita_atto_ids_univoci(self, tmp_atto_firmato):
        """Ogni deposito deve avere un idDeposito diverso."""
        client = ClientPDPDemo()
        r1 = client.deposita_atto("0580030", "MEMORIA", tmp_atto_firmato)
        r2 = client.deposita_atto("0580030", "MEMORIA", tmp_atto_firmato)
        assert r1["idDeposito"] != r2["idDeposito"], (
            "Ogni deposito deve avere un ID univoco"
        )


# ================================================================== PAT — Simulazione deposito amministrativo

class TestPATDeposito:
    """Simulazione completa deposito atti amministrativi via PAT/SIGA."""

    def test_client_demo_disponibile(self):
        """Il client demo PAT deve essere istanziabile."""
        client = crea_client_pat(demo=True)
        assert isinstance(client, ClientPATDemo)

    def test_deposita_atto_risposta_struttura(self, tmp_atto_firmato):
        """Fase 1 PAT: l'invio deve restituire la struttura attesa da SIGA."""
        client = ClientPATDemo()
        risposta = client.deposita_atto(
            codice_ufficio="T0001",   # TAR Lazio - Roma
            tipo_atto="RICORSO",
            atto_path=tmp_atto_firmato,
            numero_ricorso="1876",
            anno=2024,
            oggetto="Annullamento aggiudicazione gara appalto",
        )

        # Campi obbligatori per spec SIGA (D.P.C.M. 16/02/2016)
        assert risposta.get("codiceEsito") == "0", (
            f"codiceEsito deve essere '0' per deposito accettato. "
            f"Risposta: {risposta}"
        )
        assert risposta.get("idDeposito"), "idDeposito obbligatorio nella risposta"
        assert risposta.get("dataDeposito"), "dataDeposito obbligatorio nella risposta"
        assert risposta.get("stato") == "INVIATO"

    def test_deposita_atto_id_prefisso_pat(self, tmp_atto_firmato):
        """Il campo idDeposito deve avere il prefisso PAT-."""
        client = ClientPATDemo()
        risposta = client.deposita_atto(
            codice_ufficio="T0001",
            tipo_atto="RICORSO",
            atto_path=tmp_atto_firmato,
        )
        assert risposta["idDeposito"].startswith("PAT-"), (
            "L'ID deposito PAT deve iniziare con 'PAT-'"
        )

    def test_deposita_atto_ricevuta_accettazione(self, tmp_atto_firmato):
        """Fase 2 PAT: la risposta deve contenere la ricevuta di accettazione PEC."""
        client = ClientPATDemo()
        risposta = client.deposita_atto(
            codice_ufficio="T0001",
            tipo_atto="RICORSO",
            atto_path=tmp_atto_firmato,
            numero_ricorso="1876",
            anno=2024,
        )

        acc = risposta.get("ricevutaAccettazione", {})
        assert acc.get("mittente"), "Mittente PEC obbligatorio nella ricevuta"
        assert acc.get("oggetto"),  "Oggetto PEC obbligatorio nella ricevuta"
        assert acc.get("corpo"),    "Corpo PEC obbligatorio nella ricevuta"
        assert acc.get("messageId"), "Message-ID PEC obbligatorio nella ricevuta"
        assert "giustizia-amministrativa.it" in acc["mittente"].lower(), (
            "Il mittente della ricevuta PAT deve provenire da giustizia-amministrativa.it"
        )

    def test_deposita_atto_controlli_automatici(self, tmp_atto_firmato):
        """Fase 3 PAT: la risposta deve contenere l'esito dei controlli SIGA."""
        client = ClientPATDemo()
        risposta = client.deposita_atto(
            codice_ufficio="T0001",
            tipo_atto="RICORSO",
            atto_path=tmp_atto_firmato,
        )

        ctrl = risposta.get("esitoControlli", {})
        assert ctrl.get("codice") in ("OK", "WARN", "ERROR"), (
            "esitoControlli.codice deve essere OK, WARN o ERROR"
        )
        assert isinstance(ctrl.get("messaggi"), list)
        assert len(ctrl["messaggi"]) > 0

        assert ctrl["codice"] == "OK", "In demo mode i controlli PAT devono risultare OK"
        check_texts = " ".join(ctrl["messaggi"]).lower()
        assert "firma" in check_texts, "I controlli devono includere verifica firma digitale"
        assert "tar" in check_texts or "tipo" in check_texts, (
            "I controlli PAT devono verificare la coerenza tipo atto / registro TAR"
        )

    def test_deposita_atto_esito_cancelleria(self, tmp_atto_firmato):
        """Fase 4 PAT: la risposta deve contenere l'esito della segreteria TAR/CdS."""
        client = ClientPATDemo()
        risposta = client.deposita_atto(
            codice_ufficio="T0001",
            tipo_atto="RICORSO",
            atto_path=tmp_atto_firmato,
            numero_ricorso="1876",
            anno=2024,
        )

        canc = risposta.get("esitoCancelleria", {})
        assert canc.get("stato") == "ACCETTATO_CANCELLERIA", (
            "In demo mode l'esito segreteria TAR deve essere ACCETTATO_CANCELLERIA"
        )
        assert canc.get("oggetto"), "Oggetto PEC segreteria obbligatorio"
        assert canc.get("corpo"),   "Corpo PEC segreteria obbligatorio"

    def test_deposita_atto_file_inesistente(self):
        """Un file inesistente deve produrre codiceEsito di errore."""
        client = ClientPATDemo()
        risposta = client.deposita_atto(
            codice_ufficio="T0001",
            tipo_atto="RICORSO",
            atto_path="/tmp/file_che_non_esiste.pdf.p7m",
        )
        assert risposta.get("codiceEsito") == "E_FILE", (
            "Un file inesistente deve restituire codiceEsito='E_FILE'"
        )
        assert risposta.get("stato") == "ERRORE"

    def test_deposita_atto_ids_univoci(self, tmp_atto_firmato):
        """Ogni deposito deve avere un idDeposito diverso."""
        client = ClientPATDemo()
        r1 = client.deposita_atto("T0001", "RICORSO", tmp_atto_firmato)
        r2 = client.deposita_atto("T0001", "MEMORIA", tmp_atto_firmato)
        assert r1["idDeposito"] != r2["idDeposito"], (
            "Ogni deposito deve avere un ID univoco"
        )


# ================================================================== Coerenza tra portali

class TestCoerenzaPortali:
    """Verifica che i tre portali restituiscano risposte strutturalmente equivalenti."""

    CAMPI_OBBLIGATORI = ["codiceEsito", "idDeposito", "dataDeposito", "stato",
                         "ricevutaAccettazione", "esitoControlli", "esitoCancelleria"]

    def test_pdp_pat_stessi_campi_risposta(self, tmp_atto_firmato):
        """PDP e PAT devono restituire gli stessi campi nella risposta di deposito."""
        pdp = ClientPDPDemo().deposita_atto("0580030", "MEMORIA", tmp_atto_firmato)
        pat = ClientPATDemo().deposita_atto("T0001",   "MEMORIA", tmp_atto_firmato)

        for campo in self.CAMPI_OBBLIGATORI:
            assert campo in pdp, f"PDP: campo '{campo}' mancante nella risposta"
            assert campo in pat, f"PAT: campo '{campo}' mancante nella risposta"

    def test_pdp_pat_stesso_schema_ricevuta(self, tmp_atto_firmato):
        """La struttura della ricevuta di accettazione deve essere uguale per PDP e PAT."""
        pdp = ClientPDPDemo().deposita_atto("0580030", "MEMORIA", tmp_atto_firmato)
        pat = ClientPATDemo().deposita_atto("T0001",   "MEMORIA", tmp_atto_firmato)

        for portale, risposta in [("PDP", pdp), ("PAT", pat)]:
            acc = risposta.get("ricevutaAccettazione", {})
            for campo in ["mittente", "oggetto", "corpo", "messageId"]:
                assert campo in acc, f"{portale}: campo '{campo}' mancante in ricevutaAccettazione"

    def test_pct_stato_macchina_completa(self):
        """Verifica che tutti gli stati PCT siano definiti e distinti."""
        stati_attesi = {
            "INVIATO",
            "ACCETTATO_PEC",
            "CONSEGNATO",
            "WARN_CONTROLLI",
            "ERRORE_CONTROLLI",
            "ACCETTATO_CANCELLERIA",
            "RIFIUTATO_CANCELLERIA",
            # legacy
            "ACCETTATO",
            "RIFIUTATO",
            "ERRORE",
        }
        # Crea un EsitoDepositoPCT per ogni stato e verifica che sia serializzabile
        for stato in stati_attesi:
            esito = EsitoDepositoPCT(
                id=str(uuid.uuid4())[:8].upper(),
                timestamp=datetime.now().isoformat(),
                stato=stato,
                tipo_atto="MEMORIA",
                pec_destinatario="test@pec.it",
            )
            d = esito.to_dict()
            assert d["stato"] == stato, f"Stato '{stato}' non serializzato correttamente"

    def test_documento_pdp_ha_campi_busta(self):
        """DocumentoPDP deve avere id_deposito e tipo_atto (allineato a DocumentoPolisWeb)."""
        from pct.pdp import DocumentoPDP
        import dataclasses
        campi = {f.name for f in dataclasses.fields(DocumentoPDP)}
        assert "id_deposito" in campi, "DocumentoPDP deve avere il campo id_deposito"
        assert "tipo_atto"   in campi, "DocumentoPDP deve avere il campo tipo_atto"

    def test_documento_pat_ha_campi_busta(self):
        """DocumentoPAT deve avere id_deposito e tipo_atto (allineato a DocumentoPolisWeb)."""
        from pct.pat import DocumentoPAT
        import dataclasses
        campi = {f.name for f in dataclasses.fields(DocumentoPAT)}
        assert "id_deposito" in campi, "DocumentoPAT deve avere il campo id_deposito"
        assert "tipo_atto"   in campi, "DocumentoPAT deve avere il campo tipo_atto"
