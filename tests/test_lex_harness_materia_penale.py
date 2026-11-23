"""Regole penali: 5 frasi libere per regola, diverse da quelle del catalogo di misura."""
from __future__ import annotations

import pytest

from tests.lex_materie_casi import controlla

CASI = [
    ("Il mio cliente vuole ritirare la querela per lesioni contro il vicino: come si fa?", "pen_remissione_querela"),
    ("Remissione della querela per diffamazione: il querelato deve accettarla?", "pen_remissione_querela"),
    ("Se il querelante non si presenta come testimone all'udienza la querela si considera rimessa?", "pen_remissione_querela"),
    ("Abbiamo fatto pace con il querelato, chi paga le spese del processo dopo la remissione?", "pen_remissione_querela"),
    ("Prepara la dichiarazione di remissione di querela per il reato di minaccia.", "pen_remissione_querela"),
    ("Ci è stato notificato l'avviso della richiesta di archiviazione il 02/11/2026: entro quando ci opponiamo?", "pen_opposizione_archiviazione"),
    ("Il pubblico ministero vuole archiviare la denuncia per truffa: cosa può fare la persona offesa?", "pen_opposizione_archiviazione"),
    ("Prepara l'opposizione alla richiesta di archiviazione con nuove indagini da svolgere.", "pen_opposizione_archiviazione"),
    ("Per i maltrattamenti in famiglia il termine per opporsi all'archiviazione è più lungo?", "pen_opposizione_archiviazione"),
    ("Cosa deve contenere l'opposizione all'archiviazione per non essere inammissibile?", "pen_opposizione_archiviazione"),
    ("L'imputato vuole patteggiare la pena per ricettazione: fino a quando si può?", "pen_patteggiamento"),
    ("Con il patteggiamento si può evitare la confisca dell'auto?", "pen_patteggiamento"),
    ("Qual è il limite di pena per l'applicazione della pena su richiesta delle parti?", "pen_patteggiamento"),
    ("Prepara la richiesta di patteggiamento con il consenso del PM.", "pen_patteggiamento"),
    ("Il patteggiamento richiede la procura speciale del difensore?", "pen_patteggiamento"),
    ("Conviene il rito abbreviato per un furto aggravato? Quanto si riduce la pena?", "pen_abbreviato"),
    ("Ci hanno notificato il decreto di giudizio immediato il 10/11/2026: entro quando chiediamo l'abbreviato?", "pen_abbreviato"),
    ("L'abbreviato è possibile per un omicidio punito con l'ergastolo?", "pen_abbreviato"),
    ("Se non appello la sentenza dell'abbreviato ho un ulteriore sconto?", "pen_abbreviato"),
    ("Prepara la richiesta di giudizio abbreviato condizionato all'esame di un testimone.", "pen_abbreviato"),
    ("Il ragazzo è accusato di spaccio di lieve entità: può chiedere la messa alla prova?", "pen_messa_alla_prova"),
    ("Messa alla prova: serve il risarcimento del danno?", "pen_messa_alla_prova"),
    ("Prepara l'istanza di messa alla prova con il programma dell'UEPE.", "pen_messa_alla_prova"),
    ("Fino a quando si può chiedere la messa alla prova nella citazione diretta a giudizio?", "pen_messa_alla_prova"),
    ("Il PM ha proposto la messa alla prova in udienza: quanto tempo abbiamo per la richiesta?", "pen_messa_alla_prova"),
    ("Il cliente è stato arrestato il 15/11/2026 e messo in custodia cautelare: possiamo fare riesame?", "pen_riesame"),
    ("Il GIP ha respinto la revoca degli arresti domiciliari: come impugniamo?", "pen_riesame"),
    ("Sequestro preventivo del conto aziendale: entro quanto il riesame?", "pen_riesame"),
    ("Prepara la richiesta di riesame contro l'ordinanza di custodia cautelare in carcere.", "pen_riesame"),
    ("Sequestro probatorio del telefono del mio assistito: lo possiamo contestare?", "pen_riesame"),
    ("La vittima dell'incidente vuole il risarcimento nel processo penale contro il conducente: come?", "pen_parte_civile"),
    ("Entro quale momento ci si può costituire parte civile?", "pen_parte_civile"),
    ("Prepara l'atto di costituzione di parte civile per la truffa subita dalla cliente.", "pen_parte_civile"),
    ("Possiamo chiamare l'assicurazione come responsabile civile nel processo penale?", "pen_parte_civile"),
    ("I familiari della vittima possono costituirsi parte civile?", "pen_parte_civile"),
    ("L'imputato vorrebbe incontrare la vittima per chiedere scusa: c'è un programma di giustizia riparativa?", "pen_giustizia_riparativa"),
    ("La giustizia riparativa si può chiedere anche dopo la condanna definitiva?", "pen_giustizia_riparativa"),
    ("Prepara l'istanza di invio al Centro per la giustizia riparativa ex 129-bis.", "pen_giustizia_riparativa"),
    ("Per reati gravi è possibile la giustizia riparativa?", "pen_giustizia_riparativa"),
    ("Esito positivo del programma riparativo: che effetti ha sulla querela?", "pen_giustizia_riparativa"),
    ("È arrivato l'ordine di esecuzione con la sospensione per una pena di due anni: cosa facciamo?", "pen_esecuzione"),
    ("Possiamo chiedere l'affidamento in prova ai servizi sociali dopo la condanna definitiva?", "pen_esecuzione"),
    ("Prepara l'istanza al giudice dell'esecuzione per la continuazione tra due sentenze di condanna.", "pen_esecuzione"),
    ("Il fatto non è più reato dopo la riforma: come revochiamo la sentenza? Abolitio criminis.", "pen_esecuzione"),
    ("Incidente di esecuzione per il cumulo delle pene: a quale giudice?", "pen_esecuzione"),
]


@pytest.mark.parametrize("frase,regola", CASI)
def test_regole_penale(frase, regola):
    controlla(frase, regola)
