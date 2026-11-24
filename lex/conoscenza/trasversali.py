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
    "competenza_pagamento delibera_condominio lite_condominio attivita_pericolose".split())
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
_ILLECITO = frozenset("cose_in_custodia diffamazione_civile responsabilita_medica attivita_pericolose".split())
_CIRCOLAZIONE = frozenset("sinistro_stradale negoziazione_sinistri".split())
_MEDIAZIONE = frozenset(
    "delibera_condominio lite_condominio negatoria confessoria usucapione regolamento_confini divisione petizione_eredita "
    "riduzione procedibilita_locazione canone_nero deposito_cauzionale aggiornamento_canone responsabilita_medica "
    "diffamazione_civile usura anatocismo estratti_conto".split())
# Cause decise con il rito del lavoro (artt. 409 ss. e 442 c.p.c.; art. 63 d.lgs. 165/2001 per il pubblico impiego).
_RITO_LAVORO = frozenset(
    "licenziamento differenze_retributive tfr mobbing ricorso_414 ricorso_dipendente_pubblico carta_docente abuso_termine_pa "
    "ricorso_442".split())
_PUBBLICO_IMPIEGO = frozenset("ricorso_dipendente_pubblico carta_docente abuso_termine_pa".split())
_PRESCRIZIONI = _PRESCRIZIONE_ORDINARIA | _CANONI | _PERIODICI_LAVORO | _ILLECITO | _CIRCOLAZIONE | {"tfr"}


@dataclass(frozen=True)
class Voce:
    id: str
    sezione: str                 # «prove_oneri» | «eccezioni»
    testo: str
    rif: tuple[Rif, ...]
    istituti: frozenset[str]
    lacuna: str = ""             # limite dichiarato nella scheda quando la voce si applica


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
          R("cpc:665", "su istanza del locatore, se non sussistono gravi motivi in contrario"),
          R("cpc:665", "pronuncia ordinanza non impugnabile di rilascio, con riserva delle eccezioni del convenuto")),
         frozenset({"sfratto_morosita", "sfratto_finita_locazione", "opposizione_convalida"})),
    Voce("presunzioni", "prove_oneri",
         "Le presunzioni semplici sono lasciate alla prudenza del giudice, che ammette solo presunzioni gravi, precise e "
         "concordanti; non sono ammesse dove la legge esclude la prova per testimoni.",
         (R("cc:2729", "il quale non deve ammettere che presunzioni gravi, precise e concordanti"),
          R("cc:2729", "Le presunzioni non si possono ammettere nei casi in cui la legge esclude la prova per testimoni")),
         _AZIONI_CIVILI),
    Voce("non_contestazione", "prove_oneri",
         "Il giudice pone a fondamento della decisione le prove proposte dalle parti e i fatti non specificamente "
         "contestati dalla parte costituita.",
         (R("cpc:115", "il giudice deve porre a fondamento della decisione le prove proposte dalle parti"),
          R("cpc:115", "i fatti non specificatamente contestati dalla parte costituita")), _AZIONI_CIVILI),
    Voce("contegno_parti", "prove_oneri",
         "Il giudice valuta le prove secondo prudente apprezzamento e può desumere argomenti di prova dal contegno delle "
         "parti nel processo.",
         (R("cpc:116", "Il giudice deve valutare le prove secondo il suo prudente apprezzamento"),
          R("cpc:116", "dal contegno delle parti stesse nel processo")), _AZIONI_CIVILI),
    Voce("attivita_pericolosa", "prove_oneri",
         "Chi cagiona danno nello svolgimento di un'attività pericolosa risarcisce se non prova di avere adottato tutte le "
         "misure idonee a evitare il danno.",
         (R("cc:2050", "se non prova di avere adottato tutte le misure idonee a evitare il danno"),),
         frozenset({"attivita_pericolose"})),
    Voce("memoria_416_prove", "prove_oneri",
         "Rito del lavoro: nella memoria difensiva il convenuto prende posizione in modo preciso sui fatti affermati "
         "dall'attore e indica specificamente, a pena di decadenza, i mezzi di prova e i documenti, da depositare insieme.",
         (R("cpc:416", "deve prendere posizione, in maniera precisa e non limitata ad una generica contestazione"),
          R("cpc:416", "indicare specificamente, a pena di decadenza, i mezzi di prova dei quali intende avvalersi"),
          R("cpc:416", "ed in particolare i documenti che deve contestualmente depositare")),
         _RITO_LAVORO),
    Voce("poteri_istruttori_lavoro", "prove_oneri",
         "Rito del lavoro: il giudice può disporre d'ufficio, in qualsiasi momento, ogni mezzo di prova anche fuori dei "
         "limiti del codice civile, salvo il giuramento decisorio.",
         (R("cpc:421", "disporre d'ufficio in qualsiasi momento l'ammissione di ogni mezzo di prova, anche fuori dei limiti stabiliti dal codice civile"),
          R("cpc:421", "ad eccezione del giuramento decisorio")),
         _RITO_LAVORO),
    Voce("nova_appello_lavoro_prove", "prove_oneri",
         "Appello nel rito del lavoro: non sono ammessi nuovi mezzi di prova, salvo il giuramento estimatorio e salvo che "
         "il collegio, anche d'ufficio, li ritenga indispensabili per decidere.",
         (R("cpc:437", "Non sono ammessi nuovi mezzi di prova, tranne il giuramento estimatorio"),
          R("cpc:437", "li ritenga indispensabili ai fini della decisione della causa")), frozenset({"appello_lavoro"})),
    Voce("nova_appello_civile_prove", "prove_oneri",
         "Appello civile: non sono ammessi nuovi mezzi di prova né nuovi documenti, salvo che la parte dimostri di non "
         "averli potuti proporre o produrre in primo grado per causa a lei non imputabile.",
         (R("cpc:345", "Non sono ammessi i nuovi mezzi di prova e non possono essere prodotti nuovi documenti"),
          R("cpc:345", "dimostri di non aver potuto proporli o produrli nel giudizio di primo grado per causa ad essa non imputabile")),
         frozenset({"appello_civile"})),
    # ------------------------------------------------------------------ eccezioni
    Voce("memoria_416_eccezioni", "eccezioni",
         "Rito del lavoro: il convenuto si costituisce almeno dieci giorni prima dell'udienza e propone nella memoria "
         "difensiva, a pena di decadenza, le domande riconvenzionali e le eccezioni processuali e di merito non rilevabili "
         "d'ufficio.",
         (R("cpc:416", "Il convenuto deve costituirsi almeno dieci giorni prima della udienza"),
          R("cpc:416", "devono essere proposte, a pena di decadenza, le eventuali domande in via riconvenzionale e le eccezioni processuali e di merito che non siano rilevabili d'ufficio")),
         _RITO_LAVORO),
    Voce("modifica_domande_lavoro", "eccezioni",
         "Rito del lavoro: domande, eccezioni e conclusioni già formulate si possono modificare solo se ricorrono gravi "
         "motivi e con l'autorizzazione del giudice.",
         (R("cpc:420", "se ricorrono gravi motivi, modificare le domande, eccezioni e conclusioni gia' formulate, previa autorizzazione del giudice"),),
         _RITO_LAVORO),
    Voce("nova_appello_lavoro", "eccezioni",
         "Appello nel rito del lavoro: non sono ammesse nuove domande ed eccezioni.",
         (R("cpc:437", "Non sono ammesse nuove domande ed eccezioni"),), frozenset({"appello_lavoro"})),
    Voce("nova_appello_civile", "eccezioni",
         "Appello civile: le domande nuove sono inammissibili, rilevabili d'ufficio; non si propongono nuove eccezioni "
         "che non siano rilevabili anche d'ufficio.",
         (R("cpc:345", "Nel giudizio d'appello non possono proporsi domande nuove"),
          R("cpc:345", "debbono essere dichiarate inammissibili d'ufficio"),
          R("cpc:345", "Non possono proporsi nuove eccezioni, che non siano rilevabili anche d'ufficio")), frozenset({"appello_civile"})),
    Voce("giurisdizione_pa", "eccezioni",
         "Difetto di giurisdizione del giudice ordinario: verso la pubblica amministrazione è rilevato, anche d'ufficio, in "
         "qualunque stato e grado del processo; verso il giudice amministrativo o i giudici speciali è rilevato anche "
         "d'ufficio nel giudizio di primo grado e, nei giudizi di impugnazione, solo se oggetto di specifico motivo. Testo "
         "in vigore per i procedimenti instaurati dopo il 28/02/2023.",
         (R("cpc:37", "nei confronti della pubblica amministrazione e' rilevato, anche d'ufficio, in qualunque stato e grado del processo"),
          R("cpc:37", "nei confronti del giudice amministrativo o dei giudici speciali e' rilevato anche d'ufficio nel giudizio di primo grado"),
          R("cpc:37", "Nei giudizi di impugnazione puo' essere rilevato solo se oggetto di specifico motivo"),
          R("cpc:37", "hanno effetto a decorrere dal 28 febbraio 2023 e si applicano ai procedimenti instaurati successivamente a tale data")),
         _PUBBLICO_IMPIEGO,
         "Art. 37 c.p.c.: il testo citato è quello del d.lgs. 149/2022 (procedimenti instaurati dopo il 28/02/2023); per i "
         "procedimenti pendenti a quella data vale il testo anteriore, non presente nel registro delle norme, e "
         "nell'archivio delle pronunce lette non c'è giurisprudenza sul giudicato implicito sulla giurisdizione: da "
         "verificare per le cause anteriori."),
    Voce("prescrizione_non_rilevabile", "eccezioni",
         "La prescrizione va eccepita dalla parte: il giudice non può rilevarla d'ufficio, come ogni eccezione riservata "
         "alle parti.",
         (R("cc:2938", "Il giudice non puo' rilevare d'ufficio la prescrizione non opposta"),
          R("cpc:112", "non puo' pronunciare d'ufficio su eccezioni, che possono essere proposte soltanto dalle parti")),
         _PRESCRIZIONI),
    Voce("diritti_indisponibili", "eccezioni",
         "Ogni diritto si prescrive se non esercitato nel tempo di legge; non si prescrivono i diritti indisponibili e gli "
         "altri indicati dalla legge.",
         (R("cc:2934", "Ogni diritto si estingue per prescrizione, quando il titolare non lo esercita per il tempo determinato dalla legge"),
          R("cc:2934", "Non sono soggetti alla prescrizione i diritti indisponibili")), _PRESCRIZIONI),
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
         (R("cc:2948", "Si prescrivono in cinque anni"),
          R("cc:2948", "le pigioni delle case, i fitti dei beni rustici e ogni altro corrispettivo di locazioni")), _CANONI),
    Voce("prescrizione_periodici", "eccezioni",
         "Prescrizione quinquennale degli interessi e, in generale, di tutto ciò che si paga periodicamente ad anno o in "
         "termini più brevi.",
         (R("cc:2948", "Si prescrivono in cinque anni"),
          R("cc:2948", "tutto cio' che deve pagarsi periodicamente ad anno o in termini piu' brevi")), _PERIODICI_LAVORO),
    Voce("prescrizione_tfr", "eccezioni",
         "Prescrizione quinquennale delle indennità spettanti per la cessazione del rapporto di lavoro.",
         (R("cc:2948", "Si prescrivono in cinque anni"),
          R("cc:2948", "le indennita' spettanti per la cessazione del rapporto di lavoro")), frozenset({"tfr"})),
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
         (R("cc:2964", "non si applicano le norme relative all'interruzione della prescrizione"),
          R("cc:2964", "Del pari non si applicano le norme che si riferiscono alla sospensione, salvo che sia disposto altrimenti")),
         frozenset({"licenziamento", "conciliazione_lavoro"})),
    Voce("rinunce_lavoratore", "eccezioni",
         "Rinunce e transazioni del lavoratore su diritti inderogabili: invalide, ma l'impugnazione va proposta, a pena di "
         "decadenza, entro sei mesi dalla cessazione del rapporto o dalla rinuncia o transazione successiva.",
         (R("cc:2113", "non sono valide"),
          R("cc:2113", "L'impugnazione deve essere proposta, a pena di decadenza, entro sei mesi dalla data di cessazione del rapporto"),
          R("cc:2113", "o dalla data della rinunzia o della transazione, se queste sono intervenute dopo la cessazione medesima")),
         frozenset({"conciliazione_lavoro", "differenze_retributive", "tfr"})),
    Voce("inadempimento_eccezione", "eccezioni",
         "Eccezione di inadempimento: nei contratti a prestazioni corrispettive ciascuno può rifiutarsi di adempiere se "
         "l'altro non adempie, ma non se il rifiuto è contrario alla buona fede.",
         (R("cc:1460", "ciascuno dei contraenti puo' rifiutarsi di adempiere la sua obbligazione, se l'altro non adempie"),
          R("cc:1460", "il rifiuto e' contrario alla buona fede")),
         frozenset({"risoluzione", "risarcimento_contrattuale", "caparra", "vizi_appalto", "sfratto_morosita", "opposizione_convalida"})),
    Voce("scarsa_importanza", "eccezioni",
         "Il contratto non si risolve se l'inadempimento ha scarsa importanza, avuto riguardo all'interesse dell'altra parte.",
         (R("cc:1455", "Il contratto non si puo' risolvere se l'inadempimento di una delle parti ha scarsa importanza, avuto riguardo all'interesse dell'altra"),),
         frozenset({"risoluzione", "diffida_1454", "sfratto_morosita", "opposizione_convalida"})),
)


def voci_per(istituto: str) -> list[tuple[Voce, Punto]]:
    return [(v, Punto(v.testo, list(v.rif))) for v in VOCI if istituto in v.istituti]


# ------------------------------------------------------------------ questioni dalle pronunce già lette
# Formule della motivazione: il passaggio esprime il ragionamento della Corte, non i fatti o le difese delle parti.
MOTIVAZIONE = re.compile(
    r"\bquesta corte\b|\bprincipio di diritto\b|\bva (?:qui )?ribadit|\bgiurisprudenza di (?:questa corte|legittimit)|"
    r"\bsecondo (?:il consolidato|l\W?orientamento|la giurisprudenza)|\borientamento (?:consolidato|di questa)|"
    r"\bcontrasto\b|\bla corte ritiene\b|\bquesta corte ha (?:gia )?(?:affermato|chiarito|precisato)|"
    r"\bnon e fondata\b|\bla questione (?:e|non e) fondata", re.I)


# Narrazione del fatto o delle difese: il passaggio riferisce che cosa sostiene una parte, non che cosa decide la Corte.
NARRAZIONE = re.compile(r"\bha dedotto\b|\bdeduce\b|\blamenta\b|\bespone\b|\briferisce\b|\bpremette\b|\bha proposto\b|"
                        r"\bsostiene\b|\bassume che\b|\bcon il (?:primo|secondo|terzo|quarto|quinto|sesto) motivo\b|"
                        r"\bdenuncia\b|\bcensura\b|\bad avviso\b|\brimettente\b|\ba quo\b|\brammenta\b|\baggiunge\b|\bricostruisce\b|"
                        r"\bricorda\b|\bosserva il\b|\bqualora questa corte\b|\bdifesa (?:dello stato|erariale)\b|\bavvocatura\b", re.I)


def e_motivazione(passaggio: str) -> bool:
    """Il passaggio contiene una formula della motivazione e nessuna formula di narrazione delle difese."""
    from lex.harness.norme import piano

    t = piano(passaggio)
    return bool(MOTIVAZIONE.search(t)) and not NARRAZIONE.search(t)


# ------------------------------------------------------------------ pertinenza del passaggio all'istituto
_GENERICHE = frozenset(
    "ricorso giudice tribunale termine termini sentenza articolo articoli domanda giudizio procedimento decreto legge "
    "codice diritto diritti quando perche essere avere fatto cliente clienti voglio dobbiamo possiamo nostro nostra "
    "questo questa quello quella contro dopo prima ancora sempre ormai fatto oppure giorni mesi anni importo euro "
    "parte parti causa cause azione azioni richiesta chiedere chiede devo posso".split())
FINESTRA = 300


def termini_istituto(nome: str, regole: tuple[str, ...]) -> frozenset[str]:
    """Radici delle parole che identificano l'istituto: il suo nome e, per ogni sua regola, nome, sinonimi e situazioni
    del file del significato di Lex (``lex.harness.significato.voci``)."""
    from lex.harness.norme import normalizza

    testi = [nome]
    try:
        from lex.harness.significato import voci

        testi += [v.testo for v in voci() if v.regola in regole]
    except Exception:  # noqa: BLE001 - senza il file del significato vale solo il nome dell'istituto
        pass
    out = set()
    for t in testi:
        for w in re.findall(r"[a-z]+", normalizza(t)):
            if len(w) >= 6 and w not in _GENERICHE:
                out.add(w[:7])
    return frozenset(out)


def pertinente(passaggio: str, citazione_norma: str, termini: frozenset[str]) -> bool:
    """Il passaggio resta fra le questioni solo se, nella stessa finestra di testo della formula di motivazione,
    compaiono anche la norma dell'istituto e almeno un termine dell'istituto."""
    from lex.harness.norme import piano

    from .citazioni import modello_citazione

    t = piano(passaggio)  # minuscole, senza accenti; l'apostrofo separa le parole («dell'art.» → «dell art.»)
    rx = modello_citazione(citazione_norma)
    if not rx:
        return False
    for m in MOTIVAZIONE.finditer(t):
        finestra = t[max(0, m.start() - FINESTRA): m.end() + FINESTRA]
        if not re.search(rx, finestra, re.I):
            continue
        parole = re.findall(r"[a-z]+", finestra)
        if any(w.startswith(r) for w in parole for r in termini):
            return True
    return False
