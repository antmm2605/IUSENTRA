"""Prove e oneri, eccezioni e questioni interpretative delle schede di istituto: solo da fonti certe.

- Prove e oneri, eccezioni: norme generali e speciali (onere della prova, presunzioni, prescrizione, decadenza,
  incompetenza, improcedibilità) con l'ancora letterale controllata sul testo vigente dal controllore di Lex. Ogni voce
  dice a quali istituti si applica, scelti per materia e rito: una norma non entra in una scheda per somiglianza.
- Questioni interpretative: passaggi delle pronunce già lette che contengono la motivazione della Corte (non la
  narrazione dei fatti o delle difese), con estremi; nessuna classificazione e nessuna prevalenza automatica.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from lex.harness.modello import Punto, Rif

# Istituti decisi con il rito ordinario o semplificato, dove il convenuto si difende con la comparsa di risposta.
_RITO_ORDINARIO = frozenset(
    "citazione comparsa opposizione_di risoluzione caparra rescissione annullamento nullita esecuzione_2932 "
    "risarcimento_contrattuale vizi_appalto responsabilita_medica cose_in_custodia sinistro_stradale diffamazione_civile "
    "negatoria confessoria usucapione regolamento_confini petizione_eredita riduzione divisione usura anatocismo "
    "competenza_pagamento delibera_condominio lite_condominio".split())
# Azioni di cognizione su diritti (non procedure esecutive, cautelari, stragiudiziali o penali).
_AZIONI_CIVILI = _RITO_ORDINARIO | frozenset(
    "rito_semplificato licenziamento differenze_retributive tfr mobbing ricorso_414 di_retribuzioni ricorso_dipendente_pubblico "
    "carta_docente abuso_termine_pa ricorso_442 sfratto_morosita sfratto_finita_locazione opposizione_convalida "
    "deposito_cauzionale canone_nero aggiornamento_canone garanzia_conformita clausole_vessatorie "
    "impugnazione_delibere_societarie responsabilita_amministratori recesso_socio estratti_conto".split())
_CREDITI_CONTRATTUALI = frozenset(
    "risoluzione risarcimento_contrattuale caparra vizi_appalto responsabilita_medica differenze_retributive "
    "ricorso_dipendente_pubblico di_retribuzioni mobbing sfratto_morosita opposizione_convalida decreto_ingiuntivo "
    "opposizione_di".split())
_PRESCRIZIONE_ORDINARIA = frozenset(
    "risoluzione risarcimento_contrattuale caparra esecuzione_2932 usura anatocismo decreto_ingiuntivo".split())
_CANONI = frozenset("sfratto_morosita canone_nero aggiornamento_canone opposizione_convalida".split())
_PERIODICI_LAVORO = frozenset("differenze_retributive ricorso_dipendente_pubblico di_retribuzioni ricorso_414".split())
_ILLECITO = frozenset("cose_in_custodia diffamazione_civile responsabilita_medica".split())
_CIRCOLAZIONE = frozenset("sinistro_stradale negoziazione_sinistri".split())
_MEDIAZIONE = frozenset(
    "delibera_condominio lite_condominio negatoria confessoria usucapione regolamento_confini divisione petizione_eredita "
    "riduzione procedibilita_locazione canone_nero deposito_cauzionale aggiornamento_canone responsabilita_medica "
    "diffamazione_civile usura anatocismo estratti_conto".split())
_PRESCRIZIONI = _PRESCRIZIONE_ORDINARIA | _CANONI | _PERIODICI_LAVORO | _ILLECITO | _CIRCOLAZIONE | {"tfr"}


@dataclass(frozen=True)
class Voce:
    id: str
    sezione: str                 # «prove_oneri» | «eccezioni»
    testo: str
    rif: tuple[Rif, ...]
    istituti: frozenset[str]


def R(chiave: str, ancora: str) -> Rif:
    return Rif(chiave, ancora)


VOCI: tuple[Voce, ...] = (
    # ------------------------------------------------------------------ prove e oneri
    Voce("onere_generale", "prove_oneri",
         "Chi agisce prova i fatti costitutivi del diritto; chi eccepisce che il diritto è inefficace, modificato o estinto "
         "prova i fatti su cui l'eccezione si fonda.",
         (R("cc:2697", "deve provare i fatti che ne costituiscono il fondamento"),
          R("cc:2697", "deve provare i fatti su cui l'eccezione si fonda")), _AZIONI_CIVILI),
    Voce("inadempimento", "prove_oneri",
         "Il debitore che non adempie esattamente risponde del danno se non prova che l'inadempimento o il ritardo deriva "
         "da impossibilità della prestazione per causa a lui non imputabile.",
         (R("cc:1218", "se non prova che l'inadempimento o il ritardo e' stato determinato da impossibilita' della prestazione"),),
         _CREDITI_CONTRATTUALI),
    Voce("licenziamento", "prove_oneri",
         "L'onere di provare la giusta causa o il giustificato motivo del licenziamento spetta al datore di lavoro.",
         (R("l604:5", "L'onere della prova della sussistenza della giusta causa o del giustificato motivo di licenziamento spetta al datore di lavoro"),),
         frozenset({"licenziamento"})),
    Voce("custodia", "prove_oneri",
         "Il custode risponde del danno cagionato dalla cosa, salvo che provi il caso fortuito.",
         (R("cc:2051", "salvo che provi il caso fortuito"),), frozenset({"cose_in_custodia"})),
    Voce("circolazione", "prove_oneri",
         "Il conducente risarcisce il danno se non prova di aver fatto tutto il possibile per evitarlo; nello scontro fra "
         "veicoli si presume, fino a prova contraria, il concorso uguale dei conducenti.",
         (R("cc:2054", "se non prova di aver fatto tutto il possibile per evitare il danno"),
          R("cc:2054", "si presume, fino a prova contraria, che ciascuno dei conducenti abbia concorso ugualmente")), _CIRCOLAZIONE),
    Voce("restituzione_locata", "prove_oneri",
         "Senza descrizione dello stato dell'immobile si presume che il conduttore l'abbia ricevuto in buono stato di "
         "manutenzione; non risponde del deterioramento dovuto a vetustà.",
         (R("cc:1590", "si presume che il conduttore abbia ricevuto la cosa in buono stato di manutenzione"),
          R("cc:1590", "non risponde del perimento o del deterioramento dovuti a vetusta'")),
         frozenset({"deposito_cauzionale", "rilascio"})),
    Voce("sfratto_prova_scritta", "prove_oneri",
         "Se l'intimato si oppone con eccezioni non fondate su prova scritta, il giudice, su istanza del locatore e se non "
         "vi sono gravi motivi contrari, pronuncia ordinanza di rilascio con riserva delle eccezioni.",
         (R("cpc:665", "oppone eccezioni non fondate su prova scritta"),
          R("cpc:665", "pronuncia ordinanza non impugnabile di rilascio, con riserva delle eccezioni del convenuto")),
         frozenset({"sfratto_morosita", "sfratto_finita_locazione", "opposizione_convalida"})),
    # ------------------------------------------------------------------ eccezioni
    Voce("incompetenza", "eccezioni",
         "L'incompetenza per materia, valore e territorio si eccepisce, a pena di decadenza, nella comparsa di risposta "
         "tempestivamente depositata; l'eccezione di incompetenza per territorio deve indicare il giudice competente.",
         (R("cpc:38", "sono eccepite, a pena di decadenza, nella comparsa di risposta tempestivamente depositata"),
          R("cpc:38", "si ha per non proposta se non contiene l'indicazione del giudice che la parte ritiene competente")),
         _RITO_ORDINARIO),
    Voce("eccezioni_non_rilevabili", "eccezioni",
         "Il convenuto propone nella comparsa di risposta, a pena di decadenza, le domande riconvenzionali e le eccezioni "
         "processuali e di merito non rilevabili d'ufficio.",
         (R("cpc:167", "A pena di decadenza deve proporre le eventuali domande riconvenzionali e le eccezioni processuali e di merito che non siano rilevabili d'ufficio"),),
         _RITO_ORDINARIO),
    Voce("improcedibilita_mediazione", "eccezioni",
         "Mancata mediazione obbligatoria: l'improcedibilità è eccepita dal convenuto, a pena di decadenza, o rilevata "
         "d'ufficio dal giudice non oltre la prima udienza.",
         (R("dlgs28:5", "L'improcedibilita' e' eccepita dal convenuto, a pena di decadenza, o rilevata d'ufficio dal giudice non oltre la prima udienza"),),
         _MEDIAZIONE),
    Voce("improcedibilita_negoziazione", "eccezioni",
         "Mancata negoziazione assistita obbligatoria: l'improcedibilità deve essere eccepita dal convenuto, a pena di "
         "decadenza, o rilevata d'ufficio dal giudice, non oltre la prima udienza.",
         (R("dl132:3", "L'improcedibilita' deve essere eccepita dal convenuto, a pena di decadenza, o rilevata d'ufficio dal giudice, non oltre la prima udienza"),),
         _CIRCOLAZIONE | {"competenza_pagamento"}),
    Voce("prescrizione_ordinaria", "eccezioni",
         "Prescrizione: salvo diversa disposizione di legge, il diritto si estingue in dieci anni.",
         (R("cc:2946", "Salvi i casi in cui la legge dispone diversamente, i diritti si estinguono per prescrizione con il decorso di dieci anni"),),
         _PRESCRIZIONE_ORDINARIA),
    Voce("prescrizione_canoni", "eccezioni",
         "Prescrizione quinquennale dei canoni e di ogni altro corrispettivo di locazione.",
         (R("cc:2948", "le pigioni delle case, i fitti dei beni rustici e ogni altro corrispettivo di locazioni"),), _CANONI),
    Voce("prescrizione_periodici", "eccezioni",
         "Prescrizione quinquennale di ciò che si paga periodicamente ad anno o in termini più brevi (come le retribuzioni).",
         (R("cc:2948", "tutto cio' che deve pagarsi periodicamente ad anno o in termini piu' brevi"),), _PERIODICI_LAVORO),
    Voce("prescrizione_tfr", "eccezioni",
         "Prescrizione quinquennale delle indennità spettanti per la cessazione del rapporto di lavoro.",
         (R("cc:2948", "le indennita' spettanti per la cessazione del rapporto di lavoro"),), frozenset({"tfr"})),
    Voce("prescrizione_illecito", "eccezioni",
         "Il diritto al risarcimento del danno da fatto illecito si prescrive in cinque anni dal giorno del fatto.",
         (R("cc:2947", "si prescrive in cinque anni dal giorno in cui il fatto si e' verificato"),), _ILLECITO),
    Voce("prescrizione_circolazione", "eccezioni",
         "Per il danno da circolazione dei veicoli il diritto al risarcimento si prescrive in due anni.",
         (R("cc:2947", "Per il risarcimento del danno prodotto dalla circolazione dei veicoli di ogni specie il diritto si prescrive in due anni"),),
         _CIRCOLAZIONE),
    Voce("prescrizione_decorrenza", "eccezioni",
         "La prescrizione decorre dal giorno in cui il diritto può essere fatto valere.",
         (R("cc:2935", "La prescrizione comincia a decorrere dal giorno in cui il diritto puo' essere fatto valere"),), _PRESCRIZIONI),
    Voce("prescrizione_interruzione", "eccezioni",
         "La prescrizione è interrotta dalla notificazione dell'atto che inizia il giudizio e da ogni atto che valga a "
         "costituire in mora il debitore.",
         (R("cc:2943", "La prescrizione e' interrotta dalla notificazione dell'atto con il quale si inizia un giudizio"),
          R("cc:2943", "da ogni altro atto che valga a costituire in mora il debitore")), _PRESCRIZIONI),
    Voce("decadenza", "eccezioni",
         "Ai termini a pena di decadenza non si applicano le norme sull'interruzione della prescrizione né, salvo diversa "
         "disposizione, quelle sulla sospensione.",
         (R("cc:2964", "non si applicano le norme relative all'interruzione della prescrizione"),),
         frozenset({"licenziamento", "conciliazione_lavoro"})),
    Voce("rinunce_lavoratore", "eccezioni",
         "Rinunce e transazioni del lavoratore su diritti inderogabili: invalide, ma l'impugnazione va proposta, a pena di "
         "decadenza, entro sei mesi dalla cessazione del rapporto o dalla rinuncia o transazione successiva.",
         (R("cc:2113", "non sono valide"),
          R("cc:2113", "L'impugnazione deve essere proposta, a pena di decadenza, entro sei mesi dalla data di cessazione del rapporto")),
         frozenset({"conciliazione_lavoro", "differenze_retributive", "tfr"})),
    Voce("inadempimento_eccezione", "eccezioni",
         "Eccezione di inadempimento: nei contratti a prestazioni corrispettive ciascuno può rifiutarsi di adempiere se "
         "l'altro non adempie, ma non se il rifiuto è contrario alla buona fede.",
         (R("cc:1460", "ciascuno dei contraenti puo' rifiutarsi di adempiere la sua obbligazione, se l'altro non adempie"),
          R("cc:1460", "il rifiuto e' contrario alla buona fede")),
         frozenset({"risoluzione", "risarcimento_contrattuale", "caparra", "vizi_appalto", "sfratto_morosita", "opposizione_convalida"})),
    Voce("scarsa_importanza", "eccezioni",
         "Il contratto non si risolve se l'inadempimento ha scarsa importanza, avuto riguardo all'interesse dell'altra parte.",
         (R("cc:1455", "Il contratto non si puo' risolvere se l'inadempimento di una delle parti ha scarsa importanza"),),
         frozenset({"risoluzione", "diffida_1454", "sfratto_morosita", "opposizione_convalida"})),
)


def voci_per(istituto: str) -> list[tuple[Voce, Punto]]:
    return [(v, Punto(v.testo, list(v.rif))) for v in VOCI if istituto in v.istituti]


# ------------------------------------------------------------------ questioni dalle pronunce già lette
# Formule della motivazione: il passaggio esprime il ragionamento della Corte, non i fatti o le difese delle parti.
MOTIVAZIONE = re.compile(
    r"\bquesta corte\b|\bprincipio di diritto\b|\bva (?:qui )?ribadit|\bgiurisprudenza di (?:questa corte|legittimit)|"
    r"\bsecondo (?:il consolidato|l'orientamento|la giurisprudenza)|\borientamento (?:consolidato|di questa)|"
    r"\bcontrasto\b|\bla corte ritiene\b|\bquesta corte ha (?:gia )?(?:affermato|chiarito|precisato)|"
    r"\bnon e fondata\b|\bla questione (?:e|non e) fondata", re.I)


# Narrazione del fatto o delle difese: il passaggio riferisce che cosa sostiene una parte, non che cosa decide la Corte.
NARRAZIONE = re.compile(r"\bha dedotto\b|\bdeduce\b|\blamenta\b|\bespone\b|\briferisce\b|\bpremette\b|\bha proposto\b|"
                        r"\bsostiene\b|\bassume che\b|\bcon il (?:primo|secondo|terzo|quarto|quinto|sesto) motivo\b|"
                        r"\bdenuncia\b|\bcensura\b|\bad avviso\b|\brimettente\b|\ba quo\b|\brammenta\b|\baggiunge\b|\bricostruisce\b|"
                        r"\bricorda\b|\bosserva il\b|\bqualora questa corte\b|\bdifesa (?:dello stato|erariale)\b|\bavvocatura\b", re.I)


def e_motivazione(passaggio: str) -> bool:
    """Il passaggio contiene una formula della motivazione e nessuna formula di narrazione delle difese."""
    from lex.harness.norme import normalizza

    t = normalizza(passaggio)
    return bool(MOTIVAZIONE.search(t)) and not NARRAZIONE.search(t)
