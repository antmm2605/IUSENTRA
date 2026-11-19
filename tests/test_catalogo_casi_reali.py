"""Catalogo: i casi che nel fascicolo reale finivano a 55 «da verificare» (testi sintetici).

- una sentenza o ordinanza si riconosce da «ha pronunciato la presente …»;
- la procura alle liti dal titolo e dalla formula di delega;
- la nota di deposito dal foliario del deposito TAR;
- il profilo del catalogo segue il tipo del fascicolo quando area e branca mancano.
"""

from __future__ import annotations

import pytest

from pct.document_intelligence.catalog_resolver import resolve_document_catalog

CTX_AMMINISTRATIVO = {"tipo_fascicolo": "amministrativo", "tribunale": "TAR Lombardia"}


def _cataloga(testo: str, contesto: dict | None = None, nome: str = "documento.pdf"):
    return resolve_document_catalog(
        tenant_id="t", fascicolo_id="F", document_id=nome, document_sha256="", filename=nome,
        extracted_text=testo, document_metadata={}, fascicolo_context=dict(contesto or CTX_AMMINISTRATIVO),
    )


@pytest.mark.parametrize(
    ("testo", "etichetta"),
    [
        (
            "N. 00457/2026 REG.RIC.\nREPUBBLICA ITALIANA\nIN NOME DEL POPOLO ITALIANO\nIl Tribunale Amministrativo Regionale per la Lombardia\n"
            "ha pronunciato la presente SENTENZA sul ricorso numero di registro generale 457 del 2026, proposto da Anna Rosa, "
            "rappresentata e difesa dall'avvocato Carlo Bianchi;\ncontro\nComune di Alfa;",
            "Sentenza",
        ),
        (
            "N. 00458/2026 REG.RIC.\nIl Tribunale Amministrativo Regionale per la Lombardia\nha pronunciato la presente ORDINANZA "
            "sul ricorso numero di registro generale 458 del 2026, proposto da Marco Viola;",
            "Ordinanza",
        ),
        (
            "PROCURA ALLE LITI\nIl sottoscritto Marco Viola, c.f. VLIMRC70A01F205X, delega a rappresentarlo e difenderlo nel presente "
            "procedimento l'Avv. Carlo Bianchi, conferendogli ogni facoltà di legge.",
            "Procura alle liti",
        ),
        (
            "Tribunale Amministrativo Regionale per la Lombardia\nFoliario Deposito ricorso - Atto principale: Ricorso per l'ottemperanza - "
            "Atti secondari: Procura, Sentenza, Notifiche.\n02.03.2026 Avv. Carlo Bianchi",
            "Nota di deposito",
        ),
        (
            "ECC.MO TRIBUNALE AMMINISTRATIVO REGIONALE PER LA LOMBARDIA\nRICORSO PER L'OTTEMPERANZA\nex art. 112 e ss. c.p.a.\n"
            "PER Marco Viola, rappresentato e difeso dall'Avv. Carlo Bianchi\nCONTRO Comune di Alfa\nper l'esecuzione della sentenza "
            "n. 100/2025 passata in giudicato.",
            "Ricorso per l'ottemperanza (art. 114 c.p.a.)",
        ),
    ],
)
def test_casi_del_fascicolo_amministrativo(testo, etichetta):
    esito = _cataloga(testo)
    assert esito.document_label.startswith(etichetta), (esito.document_label, esito.reason)
    assert esito.status == "proposed"
    assert esito.profile_id == "PAT"
    assert esito.confidence > 55


@pytest.mark.parametrize(
    ("tipo", "profilo"),
    [("amministrativo", "PAT"), ("tributario", "TRIB"), ("lavoro", "LAV"), ("civile", "CIV-PCT")],
)
def test_il_profilo_segue_il_tipo_del_fascicolo(tipo, profilo):
    esito = _cataloga("PROCURA ALLE LITI\nIl sottoscritto Marco Viola delega a rappresentarlo e difenderlo l'Avv. Carlo Bianchi.", {"tipo_fascicolo": tipo})
    assert esito.profile_id == profilo



def test_avviso_tar_di_pubblicazione_ha_prova_articolo_89():
    testo = (
        "Mod. AVV015-TAR\nREPUBBLICA ITALIANA\n"
        "Tribunale Amministrativo Regionale del Lazio\n"
        "Avviso di pubblicazione di sentenza\n(ai sensi dell'art. 89, co. 3, cod. proc. amm.)\n"
        "Si comunica che la sentenza sul ricorso indicato è stata pubblicata in data 14/01/2026 con il n. 4/2026.\n"
        "Numero Registro Generale: 170/2025\nIl provvedimento originale è allegato allo stesso messaggio PEC."
    )
    esito = _cataloga(testo, nome="a.pdf")
    assert esito.status == "proposed"
    assert esito.document_nature == "comunicazione_pubblicazione_sentenza"
    assert esito.deposit_role == "fuori_busta"
    fonti = {e.locator for e in esito.evidence if e.evidence_type == "legal_source"}
    assert "normattiva_cpa_art89_comunicazione_sentenza" in fonti
    assert "catalog_pec_ricevute" not in fonti
    citazione = testo.replace("\nAvviso di pubblicazione di sentenza\n", "\nLa parte allega l'avviso di pubblicazione di sentenza.\n")
    assert _cataloga(citazione, nome="AVV015.pdf").document_nature != "comunicazione_pubblicazione_sentenza"


def test_nota_protocollata_trasmette_la_sentenza_per_eseguirla():
    testo = (
        "m_pi.AOOUSPMI.REGISTRO\nUFFICIALE.U.0000001.10-01-2025.h.10:15\n"
        "Ministero dell’Istruzione e del Merito\nUfficio Scolastico Regionale\n"
        "Oggetto: Contenzioso scolastico. Esecuzione provvedimenti giurisdizionali.\n"
        "Si trasmette in allegato la Sentenza relativa al docente per il successivo invio al Ministero.\n"
        "La liquidazione delle spese seguirà con ordinativo di pagamento."
    )
    esito = _cataloga(testo, nome="nota.pdf")
    assert esito.status == "proposed"
    assert esito.document_nature == "nota_amministrativa_trasmissione_sentenza"
    assert not esito.deposit_candidate
    altra_nota = testo.replace("Esecuzione provvedimenti giurisdizionali.", "Ricognizione delle richieste degli istituti.")
    assert _cataloga(altra_nota, nome="AOOUSP.REGISTRO_UFFICIALE.pdf").document_nature != esito.document_nature



def test_memoria_difensiva_titolo_unito_all_ufficio_e_alla_sezione():
    testo = (
        "Ministero dell'istruzione e del merito\nUfficio Scolastico Regionale\n"
        "TRIBUNALE DI MONZA SEZIONE LAVORO MEMORIA DIFENSIVA\n"
        "RG 18/2025\nAi sensi dell'art. 417 bis c.p.c. si costituisce l'Ufficio territoriale.\n"
        "I resistenti si costituiscono in giudizio e deducono quanto segue."
    )
    esito = _cataloga(testo, {"tipo_fascicolo": "lavoro"}, nome="copia_portale.pdf")
    assert esito.status == "proposed"
    assert esito.document_label == "Memoria difensiva ex art. 416 c.p.c."
    assert esito.deposit_role == "atto_principale"
    fonti = [voce.locator for voce in esito.evidence if voce.evidence_type == "legal_source"]
    assert fonti[0] == "normattiva_cpc_art416_memoria_difensiva"
    assert not any("licenziament" in voce.excerpt.lower() for voce in esito.evidence if voce.evidence_type == "legal_source")
    testo = testo.replace("MEMORIA DIFENSIVA", "Il ricorrente replica alla memoria difensiva")
    assert _cataloga(testo, {"tipo_fascicolo": "lavoro"}).document_label != esito.document_label


def test_istruzioni_avvocatura_distinte_dalla_memoria_e_dal_deposito():
    testo = (
        "UFFICIO SCOLASTICO REGIONALE — AREA LEGALE\nTRIBUNALE DI MONZA\n"
        "DEPOSITO MEMORIA scadenza il 18-11-2026\n"
        "Si trasmette l’unito ricorso ex art. 413 c.p.c.\n"
        "Questa Avvocatura ritiene che il giudizio possa essere trattato direttamente da codesto Ufficio, "
        "ai sensi dell’art. 417 bis c.p.c. ed a tal fine trasmette l’allegato foglio di istruzione.\n"
        "L’Avvocato Distrettuale dello Stato"
    )
    esito = _cataloga(testo, {"tipo_fascicolo": "lavoro"}, nome="allegato.pdf")
    assert esito.status == "proposed"
    assert esito.document_nature == "nota_avvocatura_difesa_pa"
    assert not esito.deposit_candidate
    assert "normattiva_cpc_art417bis_difesa_pa" in {e.locator for e in esito.evidence if e.evidence_type == "legal_source"}
    promemoria = "DEPOSITO MEMORIA scadenza il 18-11-2026. Si ricorda l’art. 417 bis c.p.c."
    assert _cataloga(promemoria, {"tipo_fascicolo": "lavoro"}, nome="delega.pdf").document_nature != esito.document_nature



def test_decreto_del_presidente_assegna_il_ricorso_senza_fissare_udienza():
    testo = (
        "RG n. 233 2026\nTRIBUNALE ORDINARIO DI VARESE\n"
        "Il Presidente di Sezione, ha pronunciato il seguente DECRETO "
        "Assegna il presente ricorso al giudice Anna Neri. Si comunichi."
    )
    esito = _cataloga(testo, {"tipo_fascicolo": "lavoro"}, nome="7600000s.pdf")
    assert esito.document_label == "Decreto di assegnazione del ricorso al giudice"
    assert esito.deposit_role == "fuori_busta"
    dichiarazione = (
        "TRIBUNALE ORDINARIO DI VARESE\nRicorso ex art. 414 c.p.c. "
        "Si richiama il provvedimento del Presidente di Sezione, che assegna il presente ricorso al giudice."
    )
    assert _cataloga(dichiarazione, {"tipo_fascicolo": "lavoro"}).document_label != esito.document_label


def test_memoria_di_costituzione_pa_prevale_sulle_istanze_contenute():
    testo = (
        "TRIBUNALE DI VARESE - SEZIONE LAVORO -\n"
        "Nella causa RG 200/2026 promossa con ricorso ex art. 414 c.p.c. "
        "CONTRO Ministero dell'Istruzione e del Merito = AMMINISTRAZIONE RESISTENTE =\n"
        "MEMORIA DI COSTITUZIONE EX ART. 417 BIS, COMMA I, COD. PROC. CIV. PER L'AMMINISTRAZIONE "
        "CON ISTANZA DI SVOLGIMENTO UDIENZA A TRATTAZIONE SCRITTA O DA REMOTO E ISTANZA DI RIUNIONE\n"
        "Conclusioni: respingere il ricorso."
    )
    esito = _cataloga(testo, {"tipo_fascicolo": "lavoro"}, nome="depositato.pdf.p7m")
    assert esito.document_label == "Memoria di costituzione della PA ex art. 417-bis c.p.c."
    assert esito.deposit_role == "atto_principale"
    citazione = testo.replace("MEMORIA DI COSTITUZIONE", "La ricorrente richiama la MEMORIA DI COSTITUZIONE")
    assert _cataloga(citazione, {"tipo_fascicolo": "lavoro"}).document_label != esito.document_label



def test_mime_storico_appiattito_destinatario_pct_e_busta_allegata():
    testo = (
        "MIME-Version: 1.0 From: avvocato@pec.example To: tribunale.varese@civile.ptel.giustiziacert.it "
        "Subject: DEPOSITO TELEMATICO: Memoria di costituzione Date: Thu, 9 Apr 2026 09:00:00 +0200 "
        "Content-Type: multipart/mixed Content-Disposition: attachment; filename=Atto.enc"
    )
    esito = _cataloga(testo, {"tipo_fascicolo": "lavoro"}, nome="export.eml")
    assert esito.document_label == "Messaggio di deposito telematico (busta PCT)"
    assert esito.deposit_role == "fuori_busta"
    assert not esito.deposit_candidate
    assert _cataloga(testo.replace("filename=Atto.enc", "filename=Nota.pdf"), {"tipo_fascicolo": "lavoro"}).document_label == "Messaggio email"
    assert _cataloga(testo.replace("civile.ptel.giustiziacert.it", "example.org"), {"tipo_fascicolo": "lavoro"}).document_label == "Messaggio email"


def test_messaggio_indicizzato_con_busta_distinto_dall_autocertificazione_allegata():
    testo = (
        "Oggetto: DEPOSITO TELEMATICO: Autocertificazione aggiornata\n"
        "Mittente: Studio legale <studio@pec.example>\n"
        "Destinatari: tribunale.varese@civile.ptel.giustiziacert.it\n"
        "Data: 03/04/2026\n\nCorpo email:\nSi trasmette la busta.\n"
        "[Allegato: Atto.enc; parte 2]\n"
    )
    esito = _cataloga(testo, {"tipo_fascicolo": "lavoro"}, nome="archivio.eml")
    assert esito.document_label == "Messaggio di deposito telematico (busta PCT)"
    assert esito.document_section == "comunicazioni"
    assert esito.status == "proposed"



def test_invito_ufficio_riporta_anno_reddito_richiesto_dalla_fonte():
    testo = (
        "TRIBUNALE ORDINARIO DI VARESE\nSezione Lavoro\n"
        "SI INVITA A RIDEPOSITARE L’ AUTOCERTIFICAZIONE ATTESTANTE IL DIRITTO "
        "ALL’ESENZIONE DAL PAGAMENTO DEL CONTRIBUTO UNIFICATO, IN QUANTO QUELLA "
        "ALLEGATA AL RICORSO SI RIFERISCE AI REDDITI PERCEPITI NEL 2024 E NON NEL 2023."
    )
    esito = _cataloga(testo, {"tipo_fascicolo": "lavoro"}, nome="atto.pdf")
    assert esito.document_nature == "invito_rettifica_esenzione_contributo"
    assert esito.status == "proposed"
    assert "redditi del 2024 e chiede la dichiarazione per il 2023" in esito.reason
    assert not esito.deposit_candidate
    atto = "Nella causa promossa dal ricorrente il Tribunale invita a depositare la dichiarazione di esenzione."
    assert _cataloga(atto, {"tipo_fascicolo": "lavoro"}, nome="ANNO REDDITO ERRATO.pdf").document_nature != esito.document_nature
