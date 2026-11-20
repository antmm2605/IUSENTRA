"""Il provvedimento del giudice non è «Istanze e conclusioni» (revisione del catalogo del 20/11/2026).

Caso reale A8B49265: due decreti ex art. 127-ter c.p.c. («… note contenenti le sole istanze e conclusioni») catalogati
come atto di parte. Il decreto ingiuntivo caricato dalla pagina, con le righe unite dall'estrazione del PDF, restava
«Contenuto da verificare». Fonti verificate su Normattiva il 20/11/2026: artt. 127-ter, 134, 135 e 641 c.p.c.
Esempi fittizi.
"""
from pct.document_intelligence.catalog_resolver import _content_identity
from pct.document_intelligence.catalog_sources import CATALOG_SOURCES


def _voce(testo):
    identita = _content_identity(testo)
    return (identita.classification.label, identita.classification.role) if identita else None


DECRETO_127TER = (
    "TRIBUNALE DI LOCRI Sezione Civile Controversie in materia di lavoro e previdenza\n"
    "DECRETO PER LA SOSTITUZIONE DELL'UDIENZA CON IL DEPOSITO DI NOTE SCRITTE EX ART. 127 TER C.P.C. NRG 1854/2026\n"
    "Il Giudice del lavoro, nella persona del dottor Mario Bianchi, con riferimento al procedimento in epigrafe; "
    "-richiamato il disposto dell'art. 127 c.p.c., comma 3 c.p.c., come introdotto dall'art. 3, comma 10, d.lgs. 10 ottobre "
    "2022 n. 149, secondo cui “*Il giudice può disporre, nei casi e secondo* *le disposizioni di cui agli articoli 127-bis e "
    "127-ter, che l'udienza si svolga mediante collegamenti* *audiovisivi a distanza o sia sostituita dal deposito di note "
    "scritte”;* -letto l'art. 127-ter c.p.c.; DISPONE che l'udienza sia sostituita dal deposito di note scritte contenenti le "
    "sole istanze e conclusioni entro il termine perentorio del 14/04/2027. Manda alla cancelleria per le comunicazioni.\n"
    "Locri, 10/09/2026 Il Giudice dott. Mario Bianchi")
ORDINANZA = (
    "TRIBUNALE DI PALMI Sezione Lavoro ORDINANZA R.G. 77/2026 Il Giudice, a scioglimento della riserva, letti gli atti, "
    "rilevato che occorre integrare la documentazione, assegna alle parti termine per note contenenti istanze e conclusioni. "
    "Palmi, 02/11/2026 Il Giudice dott.ssa Anna Verdi")
NOTE_DI_PARTE = (
    "TRIBUNALE DI LOCRI Sezione Lavoro R.G. 1854/2026\nNOTE SCRITTE CONTENENTI ISTANZE E CONCLUSIONI\n"
    "per la prof.ssa Rossi Maria, rappresentata e difesa dall'Avv. Luca Neri, in riscontro al decreto con cui il Giudice, "
    "nella persona del dott. Mario Bianchi, ha sostituito l'udienza. Si insiste nelle conclusioni. Avv. Luca Neri")


def test_decreto_127ter_e_ordinanza_sono_provvedimenti():
    assert _voce(DECRETO_127TER)[1] == "provvedimento" and _voce(DECRETO_127TER)[0] != "Istanze e conclusioni"
    assert _voce(ORDINANZA) == ("Ordinanza dell'ufficio giudiziario", "provvedimento")


def test_le_note_della_parte_restano_atti_di_parte():
    assert _voce(NOTE_DI_PARTE)[1] == "atto_difensivo"


def test_fonte_registrata():
    assert "normattiva_cpc_artt_134_135_sottoscrizione_giudice" in CATALOG_SOURCES


# Il testo come lo estrae il PDF caricato dalla pagina: un'unica riga (fix-catena, pratiche monitorie).
DECRETO_INGIUNTIVO = (
    "Decreto ingiuntivo n. 1109/2026 RG n. 4202/2026 UFFICIO DEL GIUDICE DI PACE DI PALMI DECRETO INGIUNTIVO Il Giudice, "
    "letto il ricorso per la concessione del decreto ingiuntivo depositato da Alfa srl-Avv. MARIO ROSSI; INGIUNGE a Beta srl "
    "di pagare entro quaranta giorni dalla notifica del presente decreto la somma di euro 2.400,00. Le spese di questa "
    "procedura, liquidate in euro 145,50 per spese ed euro 540,00 per compensi. AVVERTE la parte ingiunta che puo' proporre "
    "opposizione nel termine perentorio di quaranta giorni dalla notifica. Si comunichi. Palmi, 20/11/2026")


def test_decreto_ingiuntivo_su_una_riga_e_riconosciuto():
    identita = _content_identity(DECRETO_INGIUNTIVO)
    assert identita.classification.label == "Decreto ingiuntivo" and identita.classification.role == "provvedimento"
    assert identita.fonte == "cpc_procedimento_monitorio"
    # intestazione con l'ufficio prima del titolo
    intestato = "TRIBUNALE ORDINARIO DI TORINO DECRETO INGIUNTIVO N. 3344/2026 Il Giudice" + DECRETO_INGIUNTIVO.split("Il Giudice", 1)[1]
    assert _voce(intestato)[0] == "Decreto ingiuntivo"


def test_ricorso_e_opposizione_non_diventano_il_decreto():
    ricorso = ("TRIBUNALE DI MILANO RICORSO PER DECRETO INGIUNTIVO (artt. 633 e ss. c.p.c.) Alfa srl, rappresentata e difesa "
               "dall'Avv. Mario Rossi, chiede che il Giudice ingiunga a Beta srl il pagamento. Avv. Mario Rossi")
    assert (_voce(ricorso) or ("", ""))[0] != "Decreto ingiuntivo"
    opposizione = ("ATTO DI CITAZIONE IN OPPOSIZIONE A DECRETO INGIUNTIVO Beta srl si oppone al decreto con cui il giudice "
                   "ingiunge a Beta srl il pagamento. Avv. Neri")
    assert (_voce(opposizione) or ("", ""))[0] != "Decreto ingiuntivo"
