"""Errori pericolosi per categoria (riscontro di tappa del 24/11/2026): impugnazioni scambiate anche con un rimedio
escluso nella frase, riesame, protezione internazionale e permesso di soggiorno, diniego del Comune, delibera condominiale
e societaria, lato (opposizione tardiva, terzo, conversione, modifica delle condizioni, datore, condominio, responsabile del
sinistro, venditore, locatore), prefetto e giudice di pace, sospensione tributaria, domande vaghe.

Frasi nuove scritte per questo controllo, non prese da banchi di misura.
"""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.norme import ISTANTANEA

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")

CASI = [
    ('civ_appello',
     "La sentenza del Tribunale di Pavia che ha respinto la nostra domanda di risarcimento ci è stata notificata il 05/11/2026. Non vogliamo andare in Cassazione, vogliamo l'appello: entro quando?"),
    ('civ_cassazione',
     "La Corte d'appello di Firenze ha confermato la condanna civile del mio cliente con sentenza notificata il 02/11/2026. Escludo un nuovo appello: si può ricorrere in Cassazione ed entro quando?"),
    ('impugnazione_penale',
     "Il mio assistito è stato condannato dal Tribunale di Lecce per furto, sentenza letta in udienza il 10/11/2026 con motivazione contestuale. Entro quando l'appello penale?"),
    ('appello_lavoro',
     'Il giudice del lavoro di Modena ha rigettato il ricorso della mia cliente con sentenza notificata il 30/10/2026. Come e entro quando si appella?'),
    ('impugnazione_licenziamento',
     "Sono stata licenziata con lettera ricevuta il 12/11/2026. Non parlo di appello, non c'è ancora nessuna causa: come contesto il licenziamento?"),
    ('pen_riesame',
     'Mio figlio è stato arrestato ieri e il gip ha disposto la custodia cautelare in carcere con ordinanza notificata il 22/11/2026. Possiamo chiedere il riesame?'),
    ('pen_riesame',
     'Ordinanza di custodia cautelare eseguita il 20/11/2026 nei confronti del mio assistito: entro quanti giorni la richiesta di riesame al tribunale della libertà?'),
    ('imm_protezione_internazionale',
     'La Commissione territoriale ha respinto il 03/06/2026 la domanda di protezione internazionale del mio assistito, notificata il 05/06/2026. Che ricorso facciamo e entro quando?'),
    ('imm_protezione_internazionale',
     'Diniego della protezione internazionale notificato il 10/11/2026 a un richiedente asilo del Mali: dove si impugna?'),
    ('permesso_soggiorno',
     'La questura di Brescia ha rifiutato al mio cliente il permesso di soggiorno per coesione familiare con la moglie italiana. Dove si impugna?'),
    ('ricorso_tar',
     "Il Comune di Parma ha negato al mio cliente l'autorizzazione per l'apertura di un'edicola con provvedimento notificato il 05/11/2026. Come lo impugniamo?"),
    ('impugnazione_delibera',
     "L'assemblea del condominio di via Roma a Cuneo ha approvato il 10/11/2026 una spesa che il mio cliente, condomino dissenziente, ritiene illegittima. Entro quando impugniamo?"),
    ('soc_impugnazione_delibere',
     "L'assemblea dei soci della Alfa s.r.l. ha approvato il 10/11/2026 il bilancio con il voto contrario del mio cliente, socio di minoranza. Entro quando si impugna la delibera?"),
    ('mon_opposizione_tardiva',
     "Ho scoperto solo oggi, con il pignoramento, che c'era un decreto ingiuntivo notificato al mio vecchio indirizzo mesi fa. Posso ancora oppormi?"),
    ('es_opposizione_terzo',
     'Hanno pignorato a casa di mio fratello i mobili che sono miei e ho le fatture. Come li salvo?'),
    ('es_conversione_pignoramento',
     "Mi hanno pignorato la casa per un debito di 20.000 euro: posso pagare a rate per evitare l'asta?"),
    ('modifica_condizioni',
     "Ho perso il lavoro e non riesco più a pagare l'assegno di mantenimento fissato nella separazione: posso farlo ridurre?"),
    ('cds_prefetto',
     'Ho ricevuto una multa per divieto di sosta notificata il 12/11/2026 e voglio fare ricorso al prefetto, non al giudice di pace. Entro quando?'),
    ('opposizione_verbale_cds',
     'Ho ricevuto una multa per eccesso di velocità notificata il 12/11/2026: voglio andare dal giudice di pace, non dal prefetto. Entro quando?'),
    ('sospensione_tributaria',
     "Ho impugnato l'avviso di accertamento davanti alla Corte di giustizia tributaria; intanto l'Agenzia mi chiede di pagare. Posso chiedere di sospendere l'atto?"),
    ('VAGA',
     'Ho un problema con un contratto, cosa posso fare?'),
    ('VAGA',
     'Mi serve un consiglio legale urgente.'),
    ('VAGA',
     'Cosa rischio?'),
    ('difesa_datore_lavoro',
     'Rappresento una srl di trasporti: un autista licenziato a settembre ci ha fatto causa davanti al giudice del lavoro, prima udienza il 12/02/2027. Cosa dobbiamo depositare e quando?'),
    ('difesa_datore_lavoro',
     'La società che assisto ha ricevuto la notifica di un ricorso ex art. 414 da parte di una ex impiegata che chiede differenze retributive. Come ci costituiamo?'),
    ('difesa_datore_lavoro',
     "Ditta individuale, titolare mia cliente: la commessa licenziata il mese scorso ha mandato tramite sindacato l'impugnazione del licenziamento. Che succede adesso?"),
    ('difesa_datore_lavoro',
     "Sono il datore di lavoro: un dipendente mi chiede gli straordinari non pagati degli ultimi due anni con lettera dell'avvocato. Come rispondo?"),
    ('difesa_condominio',
     'Amministro un condominio a Padova e ho ricevuto la citazione di una condomina che contesta la ripartizione delle spese. Cosa faccio?'),
    ('difesa_condominio',
     'Il condominio che rappresento è stato chiamato in mediazione da un condomino per le infiltrazioni dal lastrico. Devo partecipare?'),
    ('sinistro_responsabile',
     'Mio padre ha investito un ciclista il 15/11/2026, il ciclista ora tramite avvocato chiede 12.000 euro di danni a mio padre. Cosa deve fare?'),
    ('sinistro_responsabile',
     'Assisto il conducente che ha causato il tamponamento del 02/11/2026: gli è arrivata una richiesta di risarcimento. Come ci muoviamo?'),
    ('sinistro_responsabile',
     "Ho fatto un incidente per colpa mia, ho urtato un'auto parcheggiata e il proprietario vuole i soldi da me. Pago io o l'assicurazione?"),
    ('garanzia_venditore',
     'Vendo biciclette elettriche nel mio negozio di Rimini: un acquirente dice che la batteria è difettosa dopo un anno e pretende la sostituzione. Sono obbligato?'),
    ('garanzia_venditore',
     "Assisto un concessionario d'auto: il cliente a cui ha venduto un'usata a marzo chiede la risoluzione per un difetto del cambio. Che diritti ha il concessionario verso il fornitore?"),
    ('garanzia_venditore',
     'Il nostro e-commerce ha venduto un divano consegnato il 10/05/2026; la cliente reclama un difetto e vuole indietro i soldi. Cosa dobbiamo fare?'),
    ('locatore_canone_nero',
     "Ho affittato per anni un appartamento a Torino con una parte di canone in nero; l'ex inquilino, andato via a febbraio, ora vuole indietro quei soldi. Rischio?"),
    ('locatore_canone_nero',
     "Assisto la proprietaria di un monolocale: la ex conduttrice le ha mandato una diffida per riavere le somme pagate oltre il canone registrato, ha lasciato l'immobile il 30/04/2026."),
    ('opposizione_convalida',
     "Il padrone di casa mi ha notificato un'intimazione di licenza per finita locazione, ma il contratto non è scaduto. Cosa posso fare all'udienza?"),
    ('sanatoria_morosita',
     'Sono inquilino e il proprietario mi ha intimato lo sfratto per morosità di tre mesi; ora ho i soldi per pagare. Posso evitare lo sfratto?'),
]


@pytest.mark.parametrize("attesa,domanda", CASI, ids=[f"{a}-{i}" for i, (a, _) in enumerate(CASI)])
def test_categoria_pericolosa(attesa, domanda):
    r = rispondi(domanda + "\n\nOggi è il 24/11/2026.", oggi=date(2026, 11, 24))
    if attesa == "VAGA":
        # Una domanda vaga non riceve una regola: Lex chiede i fatti o propone gli strumenti.
        assert r is None or r.regola in {"fuori_materia", "chiarimento_strumento", "chiarimento_materia"}, r.regola
        return
    assert r is not None and r.regola == attesa, (r.regola if r else None)
    assert not r.citazioni_non_verificate, r.citazioni_non_verificate
