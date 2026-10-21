"""Schede di locazione, condominio e diritti reali (LOC).

Base normativa: artt. 657-669 e 447-bis c.p.c.; L. 392/1978; artt. 1117-1139 c.c. e disp. att. c.c. sul
condominio; artt. 844-951 e 1027-1079 c.c. sui diritti reali; artt. 1490-1495, 1667-1669 c.c. per i vizi;
art. 5 D.Lgs. 28/2010 (mediazione obbligatoria per locazione, condominio e diritti reali).
"""
from scripts.schede_compilazione.comuni import (CC, CPC, FERIALE, IN_AVANTI, SENZA_FERIALE, T, assistito, avvocato, calcolo, controparte,
                                                data_luogo, difensore, documento, fatti_documentati, letto, procura)
from scripts.schede_compilazione.costruisci import scheda

ESTENSIONI = {"MON_005": ["LOC_007"], "MON_006": ["LOC_011"]}
MEDIAZIONE = ("28/2010", "5", "mediazione obbligatoria in materia di locazione, condominio e diritti reali")


def _parti(attore, convenuto):
    return [difensore(), procura(), data_luogo(), assistito(attore), controparte(convenuto)]


def _mediazione():
    return avvocato("mediazione", "Mediazione obbligatoria", "È stata esperita la mediazione? Indica organismo, data e verbale",
                    norma=[MEDIAZIONE], se_manca="segnalare che la domanda è improcedibile senza mediazione")


def _contratto():
    return documento("contratto", "Contratto di locazione registrato", "contratto di locazione", ["locazione", "contratto"],
                     se_manca="astensione: serve il contratto")


SCHEDE = [
    scheda("LOC_001", "Intimazione di sfratto per morosità con citazione per la convalida", ["LOC_001", "LOC_002"],
           [(CPC, "658", "sfratto per morosità e ingiunzione dei canoni"), (CPC, "660", "forma dell’intimazione e termini"),
            (CPC, "663", "convalida"), (CPC, "661", "competenza del tribunale del luogo dell’immobile"),
            ("legge_392_1978", "5", "morosità rilevante nelle locazioni abitative"), ("legge_392_1978", "55", "termine di grazia nelle locazioni abitative"), *SENZA_FERIALE],
           _parti("Locatore", "Conduttore") + [_contratto(),
            avvocato("morosita", "Canoni e oneri non pagati", "Quali canoni e oneri sono scaduti e non pagati, con importi e scadenze?",
                     norma=[(CPC, "658", "canoni scaduti"), ("legge_392_1978", "5", "venti giorni o oneri oltre due mensilità")]),
            avvocato("uso", "Uso dell’immobile", "Abitativo o commerciale? (per l’abitativo il conduttore può sanare in udienza, con termine di grazia fino a 90 giorni, 120 nei casi dell’art. 55)",
                     norma=[("legge_392_1978", "55", "termine di grazia nelle locazioni abitative")]),
            calcolo("udienza", "Udienza di convalida", "almeno 20 giorni liberi tra notifica e udienza (non si contano il giorno iniziale e quello finale; dimezzabili con decreto), senza sospensione feriale",
                    norma=[(CPC, "660", "termini"), *SENZA_FERIALE])],
           [("Atto", "contratto, morosità, intimazione di sfratto, ingiunzione dei canoni e citazione per la convalida")],
           ["contratto non presente", "morosità non indicata"]),

    scheda("LOC_003", "Intimazione di licenza o sfratto per finita locazione", ["LOC_003"],
           [(CPC, "657", "licenza e sfratto per finita locazione"), (CPC, "660", "forma e termini liberi"), (CPC, "661", "competenza"),
            ("legge_431_1998", "2", "durata delle locazioni abitative"), ("legge_431_1998", "3", "diniego di rinnovo alla prima scadenza e preavviso di sei mesi"),
            ("legge_392_1978", "29", "diniego di rinnovo alla prima scadenza per uso non abitativo, preavviso di dodici mesi"), *SENZA_FERIALE],
           _parti("Locatore", "Conduttore") + [_contratto(),
            documento("disdetta", "Disdetta inviata nei termini", "lettera di disdetta con ricevuta", ["disdetta"],
                      se_manca="verificare che la disdetta sia stata data nei termini di legge o di contratto"),
            avvocato("scadenza", "Scadenza e motivo del diniego", "Quale scadenza è (prima o successiva) e quale regime (4+4, 3+2, transitorio, commerciale 6+6)? Alla prima scadenza quale motivo di legge giustifica il diniego?",
                     norma=[("legge_431_1998", "3", "motivi di diniego"), ("legge_392_1978", "29", "motivi per uso non abitativo")])],
           [("Atto", "scadenza, disdetta o diniego motivato, intimazione e citazione per la convalida")],
           ["disdetta non data o tardiva", "scadenza non indicata", "diniego alla prima scadenza senza un motivo di legge"]),

    scheda("LOC_004", "Opposizione del conduttore all’intimazione e comparsa", ["LOC_004", "LOC_005"],
           [(CPC, "665", "opposizione e ordinanza di rilascio"), (CPC, "667", "mutamento del rito"), (CPC, "447bis", "rito locatizio"),
            (CPC, "426", "termine perentorio per integrare gli atti dopo il mutamento del rito"),
            ("28/2010", "5", "mediazione: non richiesta nella fase di convalida, condizione di procedibilità dopo il mutamento del rito, a carico del locatore")],
           _parti("Conduttore", "Locatore") + [
            documento("intimazione", "Intimazione notificata", "atto di intimazione di sfratto", ["intimazione", "sfratto"], se_manca="astensione: serve l’intimazione"),
            letto("udienza", "Udienza di convalida o fissata dopo il mutamento del rito", "udienza", "atto e verbali", [{"categoria": "data", "campo": "udienza"}]),
            avvocato("eccezioni", "Eccezioni e prova scritta", "Quali eccezioni opponi (pagamento, vizi, nullità) e con quale prova scritta?",
                     norma=[(CPC, "665", "eccezioni fondate su prova scritta")]),
            letto("termine", "Termine assegnato per integrare gli atti", "termine_integrazione", "ordinanza di mutamento del rito",
                  [{"categoria": "data"}], obbligatorio=False, norma=[(CPC, "426", "termine perentorio")])],
           [("Difese", "eccezioni con prova scritta"), ("Conclusioni", "rigetto della convalida e dell’ordinanza di rilascio")],
           ["intimazione non presente", "intimazione già convalidata: valutare solo l’opposizione tardiva o l’impugnazione"]),

    scheda("LOC_006", "Istanza di ordinanza provvisoria di rilascio", ["LOC_006"],
           [(CPC, "665", "ordinanza non impugnabile di rilascio")],
           _parti("Locatore", "Conduttore") + [
            letto("udienza", "Udienza di convalida", "udienza", "verbale", [{"categoria": "data", "campo": "udienza"}]),
            avvocato("eccezioni", "Eccezioni avversarie senza prova scritta", "Il conduttore ha opposto eccezioni non fondate su prova scritta?",
                     norma=[(CPC, "665", "presupposti")])],
           [("Istanza", "assenza di prova scritta e di gravi motivi contrari")], ["eccezioni avversarie fondate su prova scritta"]),

    scheda("LOC_008", "Diffida per pagamento dei canoni o per rilascio", ["LOC_008", "LOC_009"],
           [(CC, "1219", "costituzione in mora"), (CC, "1454", "diffida ad adempiere: termine non inferiore a quindici giorni"),
            (CC, "1587", "obbligazioni del conduttore"), (CC, "1591", "danni per ritardata restituzione")],
           [difensore(), data_luogo(), assistito("Locatore"), controparte("Conduttore"), _contratto(),
            avvocato("richiesta", "Cosa si chiede", "Pagamento di canoni (quali, quanto) o rilascio dell’immobile (perché il contratto è cessato)?"),
            avvocato("termine", "Termine assegnato", "Entro quanti giorni deve adempiere? Se vuoi la risoluzione di diritto il termine non può essere inferiore a 15 giorni",
                     norma=[(CC, "1454", "quindici giorni")])],
           [("Diffida", "richiesta, termine e conseguenze dell’inadempimento")], ["contratto non presente"]),

    scheda("LOC_010", "Impugnazione di delibera condominiale", ["LOC_010"],
           [(CC, "1137", "impugnazione entro trenta giorni"), MEDIAZIONE, ("318/1942", "71quater", "controversie condominiali"),
            ("28/2010", "8", "la domanda di mediazione impedisce la decadenza una sola volta"), (CPC, "7", "giudice di pace per le cause condominiali solo dal 31 ottobre 2027 (art. 32 D.Lgs. 116/2017, come prorogato dal D.L. 100/2026); prima, competenza per valore"), FERIALE],
           _parti("Condomino", "Condominio, in persona dell’amministratore") + [
            documento("verbale", "Verbale della delibera", "verbale di assemblea", ["verbale", "delibera"], se_manca="astensione: serve la delibera"),
            letto("data", "Data della delibera o della comunicazione agli assenti", "data_delibera", "verbale e comunicazione", [{"categoria": "data", "campo": "evento"}]),
            calcolo("termine", "Ultimo giorno per impugnare", termine=T("evento", 30), regola="30 giorni dalla delibera per i dissenzienti o astenuti, dalla comunicazione per gli assenti, con sospensione feriale" + IN_AVANTI,
                    norma=[(CC, "1137", "trenta giorni"), FERIALE]),
            avvocato("vizi", "Vizi della delibera", "Quali vizi ha la delibera (annullabilità o nullità)? Il cliente era assente, dissenziente o astenuto?"),
            _mediazione()],
           [("Fatto", "assemblea e delibera"), ("Diritto", "vizi con le norme"), ("Conclusioni", "annullamento o nullità")],
           ["termine di 30 giorni scaduto per i vizi di annullabilità", "delibera non presente",
            "azione proposta oltre i 30 giorni dal verbale negativo di mediazione"]),

    scheda("LOC_012", "Diffida o richiesta all’amministratore di condominio", ["LOC_012", "LOC_013"],
           [(CC, "1129", "obblighi dell’amministratore e accesso ai documenti"), (CC, "1130", "attribuzioni"), (CC, "1130bis", "rendiconto e documenti giustificativi")],
           [difensore(), data_luogo(), assistito("Condomino"), controparte("Amministratore di condominio"),
            avvocato("richiesta", "Cosa si chiede", "Quale adempimento chiedi o quali documenti vuoi visionare o avere in copia?",
                     norma=[(CC, "1129", "accesso"), (CC, "1130bis", "documenti giustificativi")])],
           [("Richiesta", "obbligo dell’amministratore, richiesta e termine")], ["richiesta non indicata"]),

    scheda("LOC_014", "Citazione per infiltrazioni e danni tra unità immobiliari", ["LOC_014"],
           [(CC, "2051", "danno cagionato da cose in custodia"), (CC, "1117", "parti comuni"), (CC, "1123", "ripartizione delle spese"),
            (CPC, "7", "competenza per valore; giudice di pace per le cause condominiali solo dal 31 ottobre 2027"), MEDIAZIONE],
           _parti("Danneggiato", "Responsabile (condominio o proprietario)") + [fatti_documentati("Infiltrazioni: date, provenienza, danni"),
            avvocato("origine", "Origine dell’infiltrazione", "Da dove provengono (parti comuni, unità sovrastante, impianti) e c’è una perizia?",
                     norma=[(CC, "2051", "custodia")]),
            avvocato("danni", "Danni e quantificazione", "Quali danni chiedi, con preventivi o fatture?"), _mediazione()],
           [("Fatto", "infiltrazioni con documenti"), ("Diritto", "responsabilità del custode"), ("Conclusioni", "eliminazione delle cause e risarcimento")],
           ["origine non indicata", "mediazione non esperita"]),

    scheda("LOC_015", "Azioni per vizi dell’immobile e dell’opera", ["LOC_015", "LOC_016", "LOC_017"],
           [(CC, "1490", "garanzia per vizi della cosa venduta"), (CC, "1495", "denuncia entro otto giorni e prescrizione annuale"),
            (CC, "1667", "difformità e vizi dell’opera nell’appalto"), (CC, "1669", "rovina e gravi difetti degli edifici, anche verso il venditore-costruttore"),
            ("codice_consumo", "132", "termini del consumatore"), ("codice_consumo", "133", "prescrizione nella vendita al consumatore"),
            ("28/2010", "5", "mediazione obbligatoria per il contratto d’opera e i diritti reali")],
           _parti("Acquirente o committente", "Venditore, appaltatore o costruttore") + [fatti_documentati("Consegna, scoperta e denuncia dei vizi"),
            avvocato("consumatore", "Qualità dell’acquirente", "L’acquirente è un consumatore? (si applicano i termini del Codice del consumo)", norma=[("codice_consumo", "132", "termini")]),
            avvocato("rapporto", "Rapporto e tipo di vizio", "Compravendita, appalto o gravi difetti di un edificio (art. 1669)? Quali vizi?",
                     norma=[(CC, "1490", "vendita"), (CC, "1667", "appalto"), (CC, "1669", "gravi difetti")]),
            avvocato("date", "Date di consegna, scoperta e denuncia", "Quando è avvenuta la consegna, quando hai scoperto i vizi e quando li hai denunciati?",
                     norma=[(CC, "1495", "otto giorni"), (CC, "1667", "sessanta giorni"), (CC, "1669", "un anno dalla scoperta")]),
            calcolo("termini", "Termini di denuncia e prescrizione",
                    "vendita: denuncia entro 8 giorni dalla scoperta, azione entro un anno dalla consegna; appalto: denuncia entro 60 giorni, azione entro due anni dalla consegna; art. 1669: vizi manifestati entro dieci anni dal compimento, denuncia entro un anno dalla scoperta e azione entro un anno dalla denuncia; per il consumatore valgono i termini del Codice del consumo",
                    norma=[(CC, "1495", "vendita"), (CC, "1667", "appalto"), (CC, "1669", "rovina e gravi difetti")])],
           [("Fatto", "consegna, vizi, scoperta e denuncia"), ("Diritto", "garanzia applicabile"), ("Conclusioni", "eliminazione, riduzione del prezzo o risarcimento")],
           ["termini di denuncia o di prescrizione scaduti", "date non indicate"]),

    scheda("LOC_018", "Azioni in materia di servitù, confini, distanze e immissioni", ["LOC_018", "LOC_019", "LOC_020", "LOC_021"],
           [(CC, "1079", "azione confessoria"), (CC, "949", "azione negatoria"), (CC, "950", "regolamento di confini"),
            (CC, "873", "distanze nelle costruzioni"), (CC, "844", "immissioni"), (CPC, "7", "competenza del giudice di pace per apposizione di termini e immissioni tra abitazioni"), MEDIAZIONE],
           _parti("Proprietario o titolare del diritto", "Vicino") + [fatti_documentati("Situazione dei luoghi con date e documenti"),
            avvocato("azione", "Azione da proporre", "Servitù (esistenza o inesistenza), confini incerti, violazione delle distanze o immissioni intollerabili?",
                     norma=[(CC, "1079", "servitù"), (CC, "950", "confini"), (CC, "873", "distanze"), (CC, "844", "immissioni")]),
            avvocato("titolo", "Titolo di proprietà e documenti", "Quali titoli, mappe, perizie o rilievi hai?"), _mediazione(),
            calcolo("ufficio", "Giudice competente",
                    "confini: tribunale; apposizione di termini e immissioni tra immobili adibiti a civile abitazione: giudice di pace (art. 7 nn. 1 e 3); distanze nelle costruzioni: tribunale; servitù: secondo il valore. Le modifiche all’art. 7 del D.Lgs. 116/2017 (cause condominiali) entrano in vigore il 31 ottobre 2027",
                    norma=[(CPC, "7", "competenza del giudice di pace")])],
           [("Fatto", "luoghi, titoli e violazione"), ("Diritto", "norma applicabile"), ("Conclusioni", "accertamento, riduzione in pristino o cessazione")],
           ["azione non indicata", "mediazione non esperita"]),
]
