"""Regole di civile ordinario, cautelare e possessorio: 5 frasi libere per regola, diverse dal catalogo di misura."""
from __future__ import annotations

import pytest

from tests.lex_materie_casi import controlla, risposta

CASI = [
    ("Dobbiamo citare in giudizio il costruttore per i difetti della casa: cosa deve contenere l'atto di citazione?", "civ_citazione"),
    ("Quanto tempo deve passare tra la notifica della citazione e l'udienza se il convenuto vive in Germania?", "civ_citazione"),
    ("Il cliente vuole fare causa all'ex socio per la restituzione di un prestito di 40.000 euro: come si imposta l'atto introduttivo?", "civ_citazione"),
    ("Termini a comparire nel nuovo rito ordinario davanti al tribunale?", "civ_citazione"),
    ("Entro quando l'attore deve costituirsi dopo aver notificato la citazione?", "civ_citazione"),
    ("Udienza di prima comparizione fissata al 20/04/2027: quando scadono le memorie integrative?", "civ_memorie_171ter"),
    ("Nella seconda memoria del 171-ter possiamo produrre nuovi documenti?", "civ_memorie_171ter"),
    ("Prepara la prima memoria integrativa con la modifica delle domande.", "civ_memorie_171ter"),
    ("La terza memoria serve solo per la prova contraria?", "civ_memorie_171ter"),
    ("Le tre memorie del rito Cartabia si contano a ritroso dall'udienza?", "civ_memorie_171ter"),
    ("La sentenza del tribunale di Catania notificata il 10/07/2026 ci condanna: entro quando appelliamo?", "civ_appello"),
    ("Abbiamo perso davanti al giudice di pace di Palmi: chi decide l'appello?", "civ_appello"),
    ("Come vanno scritti i motivi dell'appello civile per non essere dichiarati inammissibili?", "civ_appello"),
    ("Sentenza civile pubblicata il 03/02/2026 e mai notificata: c'è ancora tempo per appellare?", "civ_appello"),
    ("Prepara l'atto di appello contro la sentenza del tribunale sul risarcimento.", "civ_appello"),
    ("Vogliamo impugnare in cassazione la sentenza civile della corte d'appello di Reggio Calabria: entro quando?", "civ_cassazione"),
    ("Quali motivi si possono far valere con il ricorso per cassazione contro la sentenza civile?", "civ_cassazione"),
    ("Il ricorso in cassazione può firmarlo un avvocato non cassazionista?", "civ_cassazione"),
    ("Entro quanti giorni si deposita il ricorso per cassazione dopo la notifica?", "civ_cassazione"),
    ("Sentenza d'appello notificata il 15/09/2026: termine per la cassazione?", "civ_cassazione"),
    ("La sentenza d'appello si basa su un documento falso scoperto ieri: possiamo chiederne la revocazione?", "civ_revocazione"),
    ("Il giudice ha commesso un errore revocatorio sulla data del contratto: cosa facciamo?", "civ_revocazione"),
    ("Abbiamo ritrovato documenti decisivi che la controparte aveva nascosto dopo la sentenza: rimedi?", "civ_revocazione"),
    ("Revocazione per dolo della controparte: davanti a chi?", "civ_revocazione"),
    ("Scrivi la citazione per revocazione ex art. 395 n. 3 c.p.c.", "civ_revocazione"),
    ("La sentenza tra due fratelli pregiudica i diritti del mio cliente che non era parte del giudizio: rimedio?", "civ_opposizione_terzo"),
    ("Il creditore può impugnare una sentenza frutto di collusione tra debitore e terzo?", "civ_opposizione_terzo"),
    ("Opposizione di terzo contro una sentenza esecutiva sul confine: davanti a chi?", "civ_opposizione_terzo"),
    ("Prepara l'opposizione ex art. 404 c.p.c. per il proprietario pregiudicato dalla sentenza.", "civ_opposizione_terzo"),
    ("Una sentenza pronunciata tra altri soggetti ha disposto del nostro terreno: come reagiamo?", "civ_opposizione_terzo"),
    ("Il tribunale si è dichiarato incompetente con ordinanza comunicata il 05/11/2026: regolamento di competenza?", "civ_regolamento_competenza"),
    ("Il giudice ha sospeso la causa per pregiudizialità: come lo impugniamo?", "civ_regolamento_competenza"),
    ("Regolamento necessario di competenza: chi lo decide e in che termine?", "civ_regolamento_competenza"),
    ("Il giudice di pace ha declinato la competenza: meglio regolamento o riassunzione?", "civ_regolamento_competenza"),
    ("Prepara un ricorso per regolamento di competenza.", "civ_regolamento_competenza"),
    ("Ordinanza cautelare comunicata il 12/11/2026 che rigetta il 700: entro quando reclamiamo?", "cau_reclamo"),
    ("Reclamo contro l'ordinanza di sequestro concesso alla controparte: a chi va?", "cau_reclamo"),
    ("Prepara un reclamo cautelare contro il provvedimento d'urgenza.", "cau_reclamo"),
    ("Si possono dedurre fatti nuovi nel reclamo ex 669-terdecies?", "cau_reclamo"),
    ("Il giudice ha accolto il ricorso possessorio dell'avversario: reclamo?", "cau_reclamo"),
    ("Vogliamo un ATP sulle infiltrazioni prima che il vicino ripari: come si chiede?", "cau_atp"),
    ("Consulenza tecnica preventiva ex 696-bis per i danni dell'impianto: serve l'urgenza?", "cau_atp"),
    ("Prepara un ricorso per accertamento tecnico preventivo sullo stato dei luoghi.", "cau_atp"),
    ("Prima di demolire bisogna cristallizzare lo stato dell'edificio: che strumento c'è?", "cau_atp"),
    ("Il CTU nell'ATP conciliativo può tentare la conciliazione?", "cau_atp"),
    ("Il testimone chiave ha novant'anni ed è malato: possiamo sentirlo prima della causa?", "cau_istruzione_preventiva"),
    ("Audizione di testimoni a futura memoria: a quale giudice?", "cau_istruzione_preventiva"),
    ("Prepara il ricorso ex art. 692 c.p.c.", "cau_istruzione_preventiva"),
    ("Il teste sta per trasferirsi all'estero per sempre: come assumiamo la testimonianza prima della causa?", "cau_istruzione_preventiva"),
    ("L'istruzione preventiva vincola il giudice del merito?", "cau_istruzione_preventiva"),
    ("La banca minaccia di chiudere il conto aziendale domani: possiamo ottenere un provvedimento d'urgenza?", "cau_700"),
    ("Requisiti del ricorso ex art. 700 c.p.c.?", "cau_700"),
    ("Pregiudizio imminente e irreparabile alla salute per l'antenna installata dal vicino: tutela urgente?", "cau_700"),
    ("Prepara un ricorso d'urgenza per riattivare il gas.", "cau_700"),
    ("Dopo il 700 accolto bisogna iniziare per forza la causa di merito?", "cau_700"),
    ("Il fratello ha cambiato la serratura della casa di famiglia e mia madre non può più entrare: cosa facciamo?", "pos_reintegrazione"),
    ("Spoglio clandestino scoperto ieri: entro quando l'azione?", "pos_reintegrazione"),
    ("Prepara il ricorso per reintegrazione nel possesso del magazzino.", "pos_reintegrazione"),
    ("Il locatore ha staccato la luce all'inquilino per farlo uscire: azione possessoria?", "pos_reintegrazione"),
    ("Hanno chiuso il passaggio con una sbarra e il cliente non può più accedere al suo fondo: rimedio?", "pos_reintegrazione"),
    ("Il vicino molesta il nostro possesso della stradina con continui ostacoli: azione di manutenzione?", "pos_manutenzione"),
    ("Turbativa del possesso: serve il possesso da più di un anno?", "pos_manutenzione"),
    ("Prepara il ricorso per manutenzione nel possesso della servitù di acquedotto.", "pos_manutenzione"),
    ("Entro quanto si chiede la manutenzione dopo la turbativa?", "pos_manutenzione"),
    ("Azione di manutenzione nel possesso di un'universalità di mobili: è possibile?", "pos_manutenzione"),
    ("Il vicino sta costruendo un capannone a ridosso del confine, lavori iniziati a settembre: possiamo fermarlo?", "pos_nuova_opera_danno_temuto"),
    ("Il muro di contenimento del fondo a monte è pericolante: denuncia di danno temuto?", "pos_nuova_opera_danno_temuto"),
    ("Prepara la denuncia di nuova opera.", "pos_nuova_opera_danno_temuto"),
    ("Un albero del vicino rischia di cadere sul nostro tetto: cosa chiediamo al giudice?", "pos_nuova_opera_danno_temuto"),
    ("Se l'opera è già terminata si può ancora fare la denuncia di nuova opera?", "pos_nuova_opera_danno_temuto"),
]


@pytest.mark.parametrize("frase,regola", CASI)
def test_regole_civile_cautelare(frase, regola):
    controlla(frase, regola)


def test_memorie_a_ritroso_dall_udienza():
    r = risposta("Udienza di prima comparizione fissata al 20/04/2027: quando scadono le memorie integrative?")
    assert "prima memoria" in r.testo and "terza memoria" in r.testo
