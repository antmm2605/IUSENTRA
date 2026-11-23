"""Regole di lavoro e previdenza: 5 frasi libere per regola, diverse da quelle del catalogo di misura."""
from __future__ import annotations

import pytest

from tests.lex_materie_casi import controlla, risposta

CASI = [
    ("Il datore propone al dipendente di firmare una transazione per chiudere la vertenza sugli straordinari: dove conviene firmarla?", "lav_conciliazione_rinunce"),
    ("La lavoratrice ha firmato in azienda una rinuncia alle differenze retributive: possiamo ancora contestarla?", "lav_conciliazione_rinunce"),
    ("Il verbale di conciliazione in sede sindacale è impugnabile dal lavoratore?", "lav_conciliazione_rinunce"),
    ("Rapporto cessato il 31/07/2026, rinuncia firmata in ufficio: entro quando la impugniamo?", "lav_conciliazione_rinunce"),
    ("Vogliamo un accordo con il datore di lavoro sul TFR: come si fa la conciliazione davanti all'ispettorato?", "lav_conciliazione_rinunce"),
    ("Il responsabile del reparto umilia la mia cliente davanti ai colleghi da un anno: che azione abbiamo?", "lav_mobbing_demansionamento"),
    ("Dopo la maternità la dipendente è stata messa a fare fotocopie: è un demansionamento?", "lav_mobbing_demansionamento"),
    ("Scrivi il ricorso per straining contro l'azienda che ha isolato il lavoratore in uno sgabuzzino.", "lav_mobbing_demansionamento"),
    ("Il lavoratore è stato svuotato delle mansioni e ora soffre di ansia certificata: chi risponde del danno?", "lav_mobbing_demansionamento"),
    ("Mobbing sul lavoro: quanto tempo abbiamo per chiedere i danni?", "lav_mobbing_demansionamento"),
    ("L'INPS ha respinto la domanda di NASpI del mio cliente con lettera comunicata il 05/10/2026: cosa facciamo?", "prev_ricorso_amministrativo"),
    ("Mi hanno revocato l'assegno sociale, come contesto il provvedimento dell'INPS?", "prev_ricorso_amministrativo"),
    ("L'INPS chiede la restituzione di un indebito pensionistico di 9.000 euro: come ci opponiamo?", "prev_ricorso_amministrativo"),
    ("Il ricorso al comitato provinciale INPS è stato presentato a giugno e nessuno risponde: che succede?", "prev_ricorso_amministrativo"),
    ("Prepara un ricorso amministrativo contro il diniego della pensione di reversibilità.", "prev_ricorso_amministrativo"),
    ("Dobbiamo fare causa all'INPS per la pensione di vecchiaia negata: quale tribunale?", "prev_ricorso_giudiziale"),
    ("Entro quanto si agisce in giudizio contro l'INPS dopo il rigetto del ricorso sulla pensione?", "prev_ricorso_giudiziale"),
    ("L'INAIL non riconosce la malattia professionale: come portiamo la questione davanti al giudice?", "prev_ricorso_giudiziale"),
    ("Causa contro l'INPS per l'indennità di disoccupazione agricola: è procedibile senza ricorso amministrativo?", "prev_ricorso_giudiziale"),
    ("Scrivi il ricorso al tribunale del lavoro contro l'INPS per i contributi previdenziali non accreditati.", "prev_ricorso_giudiziale"),
    ("La commissione medica ha negato l'indennità di accompagnamento a mia madre: come procediamo?", "prev_atp_obbligatorio"),
    ("Per il riconoscimento della legge 104 dopo il verbale negativo serve un ricorso?", "prev_atp_obbligatorio"),
    ("Assegno ordinario di invalidità respinto: prepara il ricorso al giudice.", "prev_atp_obbligatorio"),
    ("La CTU nell'accertamento sull'invalidità civile è sfavorevole: come la contestiamo e in che termine?", "prev_atp_obbligatorio"),
    ("Pensione di inabilità negata dall'INPS per motivi sanitari: cosa facciamo?", "prev_atp_obbligatorio"),
]


@pytest.mark.parametrize("frase,regola", CASI)
def test_regole_lavoro_previdenza(frase, regola):
    controlla(frase, regola)


def test_novanta_giorni_per_il_ricorso_amministrativo():
    r = risposta("L'INPS ha respinto la domanda di NASpI con provvedimento comunicato il 05/10/2026: cosa facciamo?")
    assert "04/01/2027" in r.testo  # 03/01/2027 è domenica: proroga al primo giorno non festivo
