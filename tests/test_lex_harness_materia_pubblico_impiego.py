"""Regole del pubblico impiego: 5 frasi libere per regola, diverse da quelle del catalogo di misura."""
from __future__ import annotations

import pytest

from tests.lex_materie_casi import controlla, risposta

CASI = [
    # differenze retributive
    ("Il collaboratore scolastico non ha ricevuto l'indennità di posizione per tre anni: come la chiediamo al Ministero?", "pi_differenze_retributive"),
    ("Infermiera dell'azienda sanitaria provinciale: le hanno pagato lo stipendio con un livello inferiore, vuole gli arretrati.", "pi_differenze_retributive"),
    ("Scrivi il ricorso per le differenze stipendiali di un docente supplente contro il Ministero dell'istruzione e del merito.", "pi_differenze_retributive"),
    ("Una dipendente del comune di Palmi non ha avuto le progressioni economiche riconosciute: possiamo agire?", "pi_differenze_retributive"),
    ("Docente di ruolo: la scuola non ha pagato le ferie non godute alla cessazione. Cosa facciamo?", "pi_differenze_retributive"),
    # carta del docente
    ("Il mio assistito ha fatto supplenze al 30 giugno dal 2019 al 2023 e non ha mai avuto la carta docente: cosa possiamo chiedere?", "pi_carta_docente"),
    ("Prepara il ricorso per il bonus formazione di 500 euro negato a un'insegnante precaria.", "pi_carta_docente"),
    ("Spetta la carta elettronica del docente anche a chi ha avuto solo supplenze annuali?", "pi_carta_docente"),
    ("Un docente ormai in pensione può chiedere i soldi della carta del docente non ricevuta?", "pi_carta_docente"),
    ("Quanto vale la carta docente e per quali anni la possiamo chiedere per la mia cliente?", "pi_carta_docente"),
    # abuso dei contratti a termine
    ("L'insegnante di sostegno ha lavorato con contratti a termine con la scuola per otto anni consecutivi: che risarcimento spetta?", "pi_abuso_termine"),
    ("Un'operatrice dell'ASL è stata assunta a tempo determinato e rinnovata per anni: può ottenere l'assunzione stabile?", "pi_abuso_termine"),
    ("Scrivi il ricorso per abuso della reiterazione dei contratti a termine di un collaboratore scolastico.", "pi_abuso_termine"),
    ("Quante mensilità può liquidare il giudice per la successione di contratti a termine con un ente pubblico?", "pi_abuso_termine"),
    ("Precario della pubblica amministrazione con più di 36 mesi di servizio: quali tutele?", "pi_abuso_termine"),
    # ricostruzione di carriera
    ("Il docente è entrato in ruolo nel 2024 e il decreto di ricostruzione di carriera non conta tutti gli anni di supplenza.", "pi_ricostruzione_carriera"),
    ("Come facciamo valere il servizio pre-ruolo di un'insegnante della scuola secondaria?", "pi_ricostruzione_carriera"),
    ("Prepara il ricorso per il riconoscimento integrale del servizio non di ruolo ai fini economici.", "pi_ricostruzione_carriera"),
    ("La scuola ha riconosciuto solo due terzi del servizio prestato prima del ruolo: si può contestare?", "pi_ricostruzione_carriera"),
    ("Anzianità di servizio del docente immesso in ruolo: valgono le supplenze?", "pi_ricostruzione_carriera"),
    # esecuzione contro la PA
    ("Abbiamo una sentenza del tribunale del lavoro contro il Ministero notificata il 02/09/2026 e non hanno pagato: quando possiamo fare il precetto?", "pi_esecuzione_pa"),
    ("Il Ministero non esegue la sentenza passata in giudicato sulle differenze stipendiali: facciamo l'ottemperanza al TAR?", "pi_esecuzione_pa"),
    ("Scrivi il ricorso per ottemperanza contro l'amministrazione che non paga il decreto ingiuntivo definitivo.", "pi_esecuzione_pa"),
    ("Dove si fa il pignoramento presso terzi contro una pubblica amministrazione che non paga la sentenza?", "pi_esecuzione_pa"),
    ("Contro l'azienda sanitaria condannata a pagare, entro quando possiamo iniziare l'esecuzione?", "pi_esecuzione_pa"),
    # giudice e foro
    ("Un docente assegnato a una scuola di Vibo Valentia ma residente a Palmi: quale tribunale è competente?", "pi_competenza"),
    ("Per i dipendenti pubblici la causa va al TAR o al giudice del lavoro?", "pi_differenze_retributive"),
    ("Qual è il foro competente per il personale ATA trasferito in un'altra provincia?", "pi_differenze_retributive"),
    ("Le cause di lavoro dei dipendenti dell'agenzia delle entrate a quale giudice vanno?", "pi_competenza"),
    ("La giurisdizione sul rapporto di lavoro dei dipendenti delle amministrazioni statali è del giudice ordinario?", "pi_differenze_retributive"),
]


@pytest.mark.parametrize("frase,regola", CASI)
def test_regole_pubblico_impiego(frase, regola):
    controlla(frase, regola)


def test_foro_dell_ufficio_di_assegnazione():
    r = risposta("Il docente presta servizio presso una scuola di Vibo Valentia: dove depositiamo il ricorso per gli scatti?")
    assert "quinto comma" in r.testo and "art. 413 c.p.c." in r.testo


def test_centoventi_giorni_calcolati_dalla_notifica_del_titolo():
    r = risposta("Sentenza contro il Ministero notificata il 02/09/2026, non pagata: quando possiamo notificare il precetto?")
    assert r.regola in {"pi_esecuzione_pa", "esecuzione_contro_pa"}
    assert "31/12/2026" in r.testo
