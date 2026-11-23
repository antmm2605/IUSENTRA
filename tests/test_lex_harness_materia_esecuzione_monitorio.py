"""Regole di esecuzione e monitorio: 5 frasi libere per regola, diverse da quelle del catalogo di misura."""
from __future__ import annotations

import pytest

from tests.lex_materie_casi import controlla

CASI = [
    ("Abbiamo titolo e precetto: l'ufficiale giudiziario può entrare in casa del debitore e pignorare i mobili?", "es_pignoramento_mobiliare"),
    ("Pignoramento mobiliare eseguito ieri: entro quanto devo iscrivere a ruolo?", "es_pignoramento_mobiliare"),
    ("Si può pignorare la merce in negozio del debitore? Quali sono i beni impignorabili in casa?", "es_pignoramento_mobiliare"),
    ("Voglio pignorare gli arredi di pregio del debitore: come si procede?", "es_pignoramento_mobiliare"),
    ("Dopo il verbale di pignoramento dei beni mobili quando va chiesta la vendita?", "es_pignoramento_mobiliare"),
    ("Il debitore possiede un appartamento a Reggio Calabria: come lo pignoriamo?", "es_pignoramento_immobiliare"),
    ("Prepara l'atto di pignoramento immobiliare sul terreno del debitore.", "es_pignoramento_immobiliare"),
    ("Per l'istanza di vendita basta il certificato notarile al posto della documentazione ipocatastale?", "es_pignoramento_immobiliare"),
    ("Pignoramento della casa notificato e trascritto: termine per l'iscrizione a ruolo?", "es_pignoramento_immobiliare"),
    ("Conviene pignorare la villa del debitore anche se c'è un'ipoteca della banca?", "es_pignoramento_immobiliare"),
    ("Possiamo pignorare un quinto dello stipendio del debitore che lavora in un supermercato?", "es_pignoramento_terzi"),
    ("La banca non ha mandato la dichiarazione del terzo nel pignoramento del conto: cosa succede?", "es_pignoramento_terzi"),
    ("Quanto della pensione del debitore è pignorabile?", "es_pignoramento_terzi"),
    ("Scrivi l'atto di pignoramento presso terzi dei canoni che l'inquilino paga al debitore.", "es_pignoramento_terzi"),
    ("Il terzo pignorato è il datore di lavoro: entro quanto si iscrive a ruolo la procedura?", "es_pignoramento_terzi"),
    ("Ci hanno pignorato il conto ma il titolo è stato annullato dalla Corte d'appello: come ci opponiamo?", "es_opposizione_esecuzione"),
    ("Il pignoramento è stato eseguito per un debito già pagato: possiamo chiedere la sospensione dell'esecuzione?", "es_opposizione_esecuzione"),
    ("Hanno pignorato il fondo patrimoniale della famiglia: è impignorabile? come lo contestiamo?", "es_opposizione_esecuzione"),
    ("Esecuzione già iniziata con un credito prescritto: quale opposizione facciamo?", "es_opposizione_esecuzione"),
    ("Dopo il pignoramento possiamo ancora contestare il diritto del creditore? È già fissata la vendita.", "es_opposizione_esecuzione"),
    ("Hanno pignorato in casa di mio figlio un divano che è di mia proprietà: cosa posso fare?", "es_opposizione_terzo"),
    ("L'auto pignorata è intestata alla società della moglie, non al debitore: come la liberiamo?", "es_opposizione_terzo"),
    ("Prepara il ricorso ex art. 619 per il terzo proprietario dei macchinari pignorati.", "es_opposizione_terzo"),
    ("I beni pignorati appartengono a mia sorella: entro quando ci opponiamo?", "es_opposizione_terzo"),
    ("Se la vendita dei mobili pignorati è già avvenuta, il vero proprietario cosa recupera?", "es_opposizione_terzo"),
    ("Il debitore vuole evitare la vendita della casa pagando a rate quanto dovuto: si può?", "es_conversione_pignoramento"),
    ("Istanza di conversione del pignoramento: quanto si versa subito?", "es_conversione_pignoramento"),
    ("Possiamo sostituire i beni pignorati con una somma di denaro?", "es_conversione_pignoramento"),
    ("Conversione ex art. 495: fino a quante rate mensili?", "es_conversione_pignoramento"),
    ("Il cliente esecutato propone di pagare a rate per bloccare la vendita all'asta: come?", "es_conversione_pignoramento"),
    ("Non sappiamo che beni ha il debitore: possiamo interrogare le banche dati?", "es_ricerca_beni"),
    ("Come chiediamo la ricerca telematica dei beni prima del pignoramento?", "es_ricerca_beni"),
    ("Vogliamo scoprire i conti correnti del debitore: c'è l'accesso all'anagrafe dei rapporti finanziari?", "es_ricerca_beni"),
    ("Istanza ex 492-bis con urgenza prima del precetto: chi la autorizza?", "es_ricerca_beni"),
    ("Come faccio a individuare dove lavora il debitore per il pignoramento?", "es_ricerca_beni"),
    ("La sentenza ordina al vicino di rimuovere la tettoia ma non lo fa: come si esegue?", "es_obblighi_fare"),
    ("Il giudice ha condannato la società a consegnare i documenti contabili: come otteniamo la consegna?", "es_obblighi_fare"),
    ("Possiamo chiedere al giudice una somma per ogni giorno di ritardo nell'esecuzione della sentenza di ripristino?", "es_obblighi_fare"),
    ("Prepara il ricorso ex art. 612 per l'esecuzione dell'obbligo di fare.", "es_obblighi_fare"),
    ("Il condannato continua a violare l'obbligo di non fare stabilito dall'ordinanza: misure coercitive?", "es_obblighi_fare"),
    ("Ho scoperto solo ora un decreto ingiuntivo notificato a un vecchio indirizzo: posso ancora oppormi?", "mon_opposizione_tardiva"),
    ("Il cliente era ricoverato quando è stata notificata l'ingiunzione: rimedi?", "mon_opposizione_tardiva"),
    ("Opposizione tardiva ex art. 650: entro quando dopo il pignoramento?", "mon_opposizione_tardiva"),
    ("I quaranta giorni per il decreto ingiuntivo sono scaduti ma la notifica era nulla: cosa facciamo?", "mon_opposizione_tardiva"),
    ("Decreto ingiuntivo mai ricevuto, ora è arrivato il precetto: c'è ancora spazio per opporsi?", "mon_opposizione_tardiva"),
    ("Possiamo chiedere che il decreto ingiuntivo sia provvisoriamente esecutivo?", "mon_provvisoria_esecuzione"),
    ("Abbiamo un riconoscimento di debito firmato: il decreto può essere subito esecutivo?", "mon_provvisoria_esecuzione"),
    ("Nel giudizio di opposizione chiediamo l'esecuzione provvisoria del decreto per le somme non contestate.", "mon_provvisoria_esecuzione"),
    ("Il decreto è stato dichiarato esecutivo ex 642: l'opponente può farlo sospendere?", "mon_provvisoria_esecuzione"),
    ("Quando il giudice concede l'esecutorietà del decreto ingiuntivo in prima udienza?", "mon_provvisoria_esecuzione"),
]


@pytest.mark.parametrize("frase,regola", CASI)
def test_regole_esecuzione_monitorio(frase, regola):
    controlla(frase, regola)
