"""Tributario e riscossione, previdenza e assistenza (INPS, INAIL), lavoro e ispettorato.

Regole d'identità dal titolo aggiunte il 02/11/2026 per coprire tutte le materie (direttiva dell'avvocato del
01/11/2026). Ogni regola cita la norma che definisce l'atto, registrata in `FONTI` con URL ufficiale e data di
consultazione.

Norme vigenti al 02/11/2026: il processo tributario è ancora regolato dal D.Lgs. 546/1992, perché il Testo unico
della giustizia tributaria (D.Lgs. 175/2024) si applica dal 1° gennaio 2027 (rinvio del D.L. 200/2025, art. 4); lo
stesso vale per il D.Lgs. 472/1997 (Testo unico sanzioni, D.Lgs. 173/2024) e per gli artt. 32 e 36-bis del D.P.R.
600/1973, abrogati dal 1° gennaio 2027. Il reclamo-mediazione (art. 17-bis D.Lgs. 546/1992) è abrogato dal D.Lgs.
220/2023 ed è già coperto da `pubblico.py`; il comma 7 dell'art. 12 L. 212/2000 (osservazioni al processo verbale)
è abrogato dal D.Lgs. 219/2023, sostituito dal contraddittorio preventivo dell'art. 6-bis. Il concordato preventivo
biennale non è incluso: l'art. 9 del D.Lgs. 13/2024 è abrogato dal D.Lgs. 141/2026.

Le regole già presenti in `tributario.py`, `lavoro.py` e `pubblico.py` non si ripetono: qui solo le tipologie
mancanti, con titoli abbastanza specifici da non sottrarre i documenti delle aree generali.
"""

from __future__ import annotations

from typing import Any

from pct.fascicoli import TipoDocumento

from ._modello import RegolaTitolo, regola

_VERIFICA = "testo vigente consultato su Normattiva il 02/11/2026"
_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_D_546 = "decreto.legislativo:1992-12-31;546~art"
_L_212 = "legge:2000-07-27;212~art"
_DPR_600 = "decreto.del.presidente.della.repubblica:1973-09-29;600~art"
_DPR_602 = "decreto.del.presidente.della.repubblica:1973-09-29;602~art"
_DPR_1124 = "decreto.del.presidente.della.repubblica:1965-06-30;1124~art"
_D_124 = "decreto.legislativo:2004-04-23;124~art"
_CPC = "regio.decreto:1940-10-28;1443~art"
_CC = "regio.decreto:1942-03-16;262~art"

# Segnali del giudice tributario: senza uno di questi un appello, una revocazione o un'ottemperanza restano
# delle aree civile e amministrativa.
_GIUDICE_TRIBUTARIO = (
    r"\bcorte\s+di\s+giustizia\s+tributaria\b|\bcommissione\s+tributaria\b|\b546/1992\b"
)
_RISCOSSIONE = r"\bagente\s+della\s+riscossione\b|\bagenzia\s+delle\s+entrate[\s-]*riscossione\b|\b602/1973\b"
_ISPETTORATO = r"\bispettorat\w+\b|\bispettiv\w+\b|\b124/2004\b"


def _fonte(label: str, urn: str) -> dict[str, Any]:
    return {"label": label, "official_url": _NORMATTIVA + urn, "verification_status": _VERIFICA,
            "source_type": "normativa"}


FONTI: dict[str, dict[str, Any]] = {
    # Processo tributario (D.Lgs. 546/1992, vigente fino al 31/12/2026; poi D.Lgs. 175/2024)
    "estesa_tributi_lavoro_d_lgs_546_1992_art_32": _fonte("D.Lgs. 546/1992, art. 32: memorie illustrative e repliche nel processo tributario (dal 2027 D.Lgs. 175/2024)", _D_546 + "32"),
    "estesa_tributi_lavoro_d_lgs_546_1992_art_53": _fonte("D.Lgs. 546/1992, artt. 52-53: appello alla Corte di giustizia tributaria di secondo grado (dal 2027 D.Lgs. 175/2024, artt. 106 ss.)", _D_546 + "53"),
    "estesa_tributi_lavoro_d_lgs_546_1992_art_62": _fonte("D.Lgs. 546/1992, art. 62: ricorso per cassazione contro le sentenze tributarie (dal 2027 D.Lgs. 175/2024, artt. 116 ss.)", _D_546 + "62"),
    "estesa_tributi_lavoro_d_lgs_546_1992_art_63": _fonte("D.Lgs. 546/1992, art. 63: giudizio di rinvio e atto di riassunzione", _D_546 + "63"),
    "estesa_tributi_lavoro_d_lgs_546_1992_art_64": _fonte("D.Lgs. 546/1992, art. 64: revocazione delle sentenze tributarie (dal 2027 D.Lgs. 175/2024, artt. 120 ss.)", _D_546 + "64"),
    "estesa_tributi_lavoro_d_lgs_546_1992_art_70": _fonte("D.Lgs. 546/1992, art. 70: giudizio di ottemperanza tributario (dal 2027 D.Lgs. 175/2024, artt. 127-128)", _D_546 + "70"),
    # Statuto del contribuente
    "estesa_tributi_lavoro_l_212_2000_art_11": _fonte("L. 212/2000, art. 11: interpello del contribuente e risposta dell'Amministrazione", _L_212 + "11"),
    "estesa_tributi_lavoro_l_212_2000_art_10_quater": _fonte("L. 212/2000, artt. 10-quater e 10-quinquies: autotutela obbligatoria e facoltativa", _L_212 + "10quater"),
    "estesa_tributi_lavoro_l_212_2000_art_6_bis": _fonte("L. 212/2000, art. 6-bis: contraddittorio preventivo, schema di atto e osservazioni", _L_212 + "6bis"),
    "estesa_tributi_lavoro_l_212_2000_art_12": _fonte("L. 212/2000, art. 12: accessi, ispezioni, verifiche e processo verbale", _L_212 + "12"),
    # Accertamento, sanzioni, versamenti
    "estesa_tributi_lavoro_dpr_600_1973_art_36_bis": _fonte("D.P.R. 600/1973, art. 36-bis: liquidazione automatizzata e comunicazione dell'esito al contribuente (abrogato dal 1/1/2027, D.Lgs. 141/2026)", _DPR_600 + "36bis"),
    "estesa_tributi_lavoro_dpr_600_1973_art_32": _fonte("D.P.R. 600/1973, art. 32: inviti, questionari e richieste di documenti (abrogato dal 1/1/2027, D.Lgs. 141/2026)", _DPR_600 + "32"),
    "estesa_tributi_lavoro_d_lgs_472_1997_art_16": _fonte("D.Lgs. 472/1997, artt. 16 e 17: atto di contestazione e irrogazione delle sanzioni tributarie (dal 2027 D.Lgs. 173/2024)", "decreto.legislativo:1997-12-18;472~art16"),
    "estesa_tributi_lavoro_d_lgs_241_1997_art_17": _fonte("D.Lgs. 241/1997, art. 17: versamento unitario con modello F24", "decreto.legislativo:1997-07-09;241~art17"),
    "estesa_tributi_lavoro_l_160_2019_art_1": _fonte("L. 160/2019, art. 1, comma 792: avviso di accertamento esecutivo dei tributi locali", "legge:2019-12-27;160~art1"),
    "estesa_tributi_lavoro_rd_639_1910_art_2": _fonte("R.D. 639/1910, art. 2: ingiunzione fiscale degli enti pubblici", "regio.decreto:1910-04-14;639~art2"),
    # Riscossione (D.P.R. 602/1973, dal 2027 Testo unico versamenti e riscossione D.Lgs. 33/2025)
    "estesa_tributi_lavoro_dpr_602_1973_art_38": _fonte("D.P.R. 602/1973, art. 38: istanza di rimborso dei versamenti diretti", _DPR_602 + "38"),
    "estesa_tributi_lavoro_dpr_602_1973_art_19": _fonte("D.P.R. 602/1973, art. 19: dilazione del pagamento delle somme iscritte a ruolo", _DPR_602 + "19"),
    "estesa_tributi_lavoro_dpr_602_1973_art_72_bis": _fonte("D.P.R. 602/1973, art. 72-bis: pignoramento dei crediti verso terzi da parte dell'agente della riscossione", _DPR_602 + "72bis"),
    "estesa_tributi_lavoro_dpr_602_1973_art_77": _fonte("D.P.R. 602/1973, art. 77, comma 2-bis: comunicazione preventiva di iscrizione ipotecaria", _DPR_602 + "77"),
    "estesa_tributi_lavoro_dpr_602_1973_art_12": _fonte("D.P.R. 602/1973, art. 12: formazione del ruolo ed estratto di ruolo (comma 4-bis)", _DPR_602 + "12"),
    "estesa_tributi_lavoro_l_197_2022_art_1": _fonte("L. 197/2022, art. 1, commi 231-252: definizione agevolata dei carichi affidati all'agente della riscossione", "legge:2022-12-29;197~art1"),
    "estesa_tributi_lavoro_l_228_2012_art_1": _fonte("L. 228/2012, art. 1, commi 537-543: sospensione legale della riscossione", "legge:2012-12-24;228~art1"),
    # Previdenza e assistenza
    "estesa_tributi_lavoro_dl_78_2010_art_30": _fonte("D.L. 78/2010, art. 30: avviso di addebito INPS con valore di titolo esecutivo", "decreto.legge:2010-05-31;78~art30"),
    "estesa_tributi_lavoro_d_lgs_22_2015_art_6": _fonte("D.Lgs. 22/2015, art. 6: domanda di indennità NASpI", "decreto.legislativo:2015-03-04;22~art6"),
    "estesa_tributi_lavoro_dl_78_2009_art_20": _fonte("D.L. 78/2009, art. 20: domanda e accertamento sanitario dell'invalidità civile, cecità, sordità, handicap e disabilità", "decreto.legge:2009-07-01;78~art20"),
    "estesa_tributi_lavoro_cpc_art_445_bis": _fonte("c.p.c., art. 445-bis: accertamento tecnico preventivo obbligatorio e dichiarazione di dissenso", _CPC + "445bis"),
    "estesa_tributi_lavoro_cpc_art_442": _fonte("c.p.c., art. 442: controversie in materia di previdenza e assistenza obbligatorie", _CPC + "442"),
    "estesa_tributi_lavoro_dpr_1124_1965_art_53": _fonte("D.P.R. 1124/1965, art. 53: denuncia di infortunio e di malattia professionale all'INAIL", _DPR_1124 + "53"),
    "estesa_tributi_lavoro_dpr_1124_1965_art_66": _fonte("D.P.R. 1124/1965, art. 66: prestazioni INAIL, fra cui la rendita per inabilità permanente", _DPR_1124 + "66"),
    # Ispettorato del lavoro
    "estesa_tributi_lavoro_d_lgs_124_2004_art_13": _fonte("D.Lgs. 124/2004, art. 13: accesso ispettivo, verbale di primo accesso e verbale unico di accertamento e notificazione", _D_124 + "13"),
    "estesa_tributi_lavoro_d_lgs_124_2004_art_12": _fonte("D.Lgs. 124/2004, art. 12: diffida accertativa per crediti patrimoniali", _D_124 + "12"),
    "estesa_tributi_lavoro_d_lgs_124_2004_art_11": _fonte("D.Lgs. 124/2004, art. 11: conciliazione monocratica", _D_124 + "11"),
    "estesa_tributi_lavoro_d_lgs_124_2004_art_16": _fonte("D.Lgs. 124/2004, artt. 16 e 17: ricorsi al direttore dell'Ispettorato e al Comitato per i rapporti di lavoro", _D_124 + "16"),
    "estesa_tributi_lavoro_d_lgs_758_1994_art_20": _fonte("D.Lgs. 758/1994, art. 20: prescrizione dell'organo di vigilanza per le contravvenzioni in materia di lavoro", "decreto.legislativo:1994-12-19;758~art20"),
    "estesa_tributi_lavoro_d_lgs_81_2008_art_14": _fonte("D.Lgs. 81/2008, art. 14: provvedimento di sospensione dell'attività imprenditoriale", "decreto.legislativo:2008-04-09;81~art14"),
    # Rapporto di lavoro
    "estesa_tributi_lavoro_l_300_1970_art_7": _fonte("L. 300/1970, art. 7: sanzioni disciplinari, contestazione e giustificazioni del lavoratore", "legge:1970-05-20;300~art7"),
    "estesa_tributi_lavoro_l_300_1970_art_28": _fonte("L. 300/1970, art. 28: repressione della condotta antisindacale", "legge:1970-05-20;300~art28"),
    "estesa_tributi_lavoro_d_lgs_151_2015_art_26": _fonte("D.Lgs. 151/2015, art. 26: dimissioni e risoluzione consensuale telematiche e loro revoca", "decreto.legislativo:2015-09-14;151~art26"),
    "estesa_tributi_lavoro_cpc_art_410": _fonte("c.p.c., art. 410: tentativo di conciliazione nelle controversie di lavoro", _CPC + "410"),
    "estesa_tributi_lavoro_l_223_1991_art_4": _fonte("L. 223/1991, artt. 4 e 24: procedura di licenziamento collettivo", "legge:1991-07-23;223~art4"),
    "estesa_tributi_lavoro_d_lgs_148_2015_art_15": _fonte("D.Lgs. 148/2015, art. 15: domanda di concessione della cassa integrazione guadagni ordinaria", "decreto.legislativo:2015-09-14;148~art15"),
    "estesa_tributi_lavoro_cc_art_2120": _fonte("c.c., art. 2120: trattamento di fine rapporto, calcolo e anticipazione", _CC + "2120"),
    "estesa_tributi_lavoro_cc_art_2103": _fonte("c.c., art. 2103: mansioni e trasferimento del lavoratore", _CC + "2103"),
    "estesa_tributi_lavoro_l_297_1982_art_2": _fonte("L. 297/1982, art. 2: Fondo di garanzia INPS per il trattamento di fine rapporto", "legge:1982-05-29;297~art2"),
    "estesa_tributi_lavoro_dl_510_1996_art_9_bis": _fonte("D.L. 510/1996, art. 9-bis: comunicazioni obbligatorie di instaurazione, trasformazione e cessazione del rapporto", "decreto.legge:1996-10-01;510~art9bis"),
}

_F = "estesa_tributi_lavoro_"


def _atto(id: str, titolo: str, conferma: str, label: str, fonte: str, evidence: str, *,
          role: str = "atto_principale", tipo: TipoDocumento = TipoDocumento.RICORSO) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role=role, section="atti", tipo=tipo, fonte=_F + fonte,
                  deposit_role="atto_principale", evidence=evidence)


def _provvedimento(id: str, titolo: str, conferma: str, label: str, fonte: str, evidence: str, *,
                   role: str = "atto_amministrativo", tipo: TipoDocumento = TipoDocumento.ALLEGATO) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role=role, section="provvedimenti", tipo=tipo, fonte=_F + fonte,
                  evidence=evidence)


def _comunicazione(id: str, titolo: str, conferma: str, label: str, fonte: str, evidence: str, *,
                   role: str = "corrispondenza") -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role=role, section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
                  fonte=_F + fonte, evidence=evidence)


def _allegato(id: str, titolo: str, conferma: str, label: str, fonte: str, evidence: str, *,
              role: str = "documento_economico", section: str = "allegati",
              tipo: TipoDocumento = TipoDocumento.ALLEGATO) -> RegolaTitolo:
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=_F + fonte,
                  evidence=evidence)


_PROCESSO_TRIBUTARIO = (
    _atto(
        "trl_appello_tributi",
        r"(?:atto\s+di\s+|ricorso\s+in\s+)?appello(?:\s+.*)?",
        r"\bcorte\s+di\s+giustizia\s+tributaria\s+di\s+secondo\s+grado\b|\bcommissione\s+tributaria\s+regionale\b|\bappello\s+tributario\b",
        "Appello tributario",
        "d_lgs_546_1992_art_53",
        "titolo dell'appello e giudice di secondo grado delle imposte (artt. 52-53 D.Lgs. 546/1992)",
    ),
    _atto(
        "trl_cassazione_tributi",
        r"ricorso\s+per\s+cassazione(?:\s+.*)?",
        _GIUDICE_TRIBUTARIO + r"|\bmateria\s+tributaria\b",
        "Ricorso per cassazione in materia tributaria",
        "d_lgs_546_1992_art_62",
        "titolo del ricorso e sentenza del giudice delle imposte impugnata (art. 62 D.Lgs. 546/1992)",
    ),
    _atto(
        "trl_revocazione_tributi",
        r"(?:ricorso\s+per\s+|istanza\s+di\s+|atto\s+di\s+)?revocazione(?:\s+.*)?",
        _GIUDICE_TRIBUTARIO + r"|\bmateria\s+tributaria\b",
        "Ricorso per revocazione in materia tributaria",
        "d_lgs_546_1992_art_64",
        "titolo del ricorso e sentenza del giudice delle imposte da revocare (art. 64 D.Lgs. 546/1992)",
    ),
    _atto(
        "trl_ottemperanza_tributi",
        r"(?:ricorso|istanza)\s+per\s+(?:l[’'\s]*|il\s+giudizio\s+di\s+)?ottemperanza(?:\s+.*)?|giudizio\s+di\s+ottemperanza(?:\s+.*)?",
        _GIUDICE_TRIBUTARIO + r"|\bmateria\s+tributaria\b",
        "Ricorso per l'ottemperanza in materia tributaria",
        "d_lgs_546_1992_art_70",
        "titolo del ricorso e sentenza del giudice delle imposte da eseguire (art. 70 D.Lgs. 546/1992)",
    ),
    _atto(
        "trl_memoria_illustrativa_tributi",
        r"memori[ae]\s+(?:illustrativ[ae]|di\s+replica)(?:\s+.*)?",
        _GIUDICE_TRIBUTARIO,
        "Memoria illustrativa nel processo tributario",
        "d_lgs_546_1992_art_32",
        "titolo della memoria e giudice delle imposte (art. 32 D.Lgs. 546/1992)",
        role="atto_difensivo", tipo=TipoDocumento.MEMORIA,
    ),
    _atto(
        "trl_riassunzione_tributi",
        r"(?:atto\s+di\s+|ricorso\s+(?:in|per)\s+)?riassunzione(?:\s+.*)?",
        _GIUDICE_TRIBUTARIO,
        "Atto di riassunzione nel processo tributario",
        "d_lgs_546_1992_art_63",
        "titolo dell'atto e giudizio di rinvio davanti al giudice delle imposte (art. 63 D.Lgs. 546/1992)",
    ),
)

_PROCEDIMENTO_TRIBUTARIO = (
    _atto(
        "trl_istanza_interpello",
        r"istanza\s+di\s+interpello(?!\s+formale)(?:\s+.*)?|interpello\s+(?:ordinario|probatorio|antiabuso|disapplicativo)(?:\s+.*)?",
        r"\b212/2000\b|\bagenzia\s+delle\s+entrate\b|\bstatuto\s+(?:dei\s+diritti\s+)?del\s+contribuente\b|\binterpellant\w*\b",
        "Istanza di interpello",
        "l_212_2000_art_11",
        "titolo dell'istanza e quesito all'Amministrazione finanziaria (art. 11 L. 212/2000)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _provvedimento(
        "trl_risposta_interpello",
        r"risposta\s+(?:n\.?\s*\d+\s+)?(?:all.?\s*istanza\s+di\s+|a(?:ll.?)?\s*)interpello(?:\s+.*)?",
        r"\binterpellant\w*\b|\bagenzia\s+delle\s+entrate\b|\b212/2000\b",
        "Risposta a interpello",
        "l_212_2000_art_11",
        "titolo della risposta e parere dell'Amministrazione sul quesito (art. 11 L. 212/2000)",
    ),
    _atto(
        "trl_istanza_autotutela",
        r"(?:istanza|richiesta)\s+di\s+(?:annullamento\s+in\s+)?autotutela(?:\s+.*)?",
        r"\b10[\s-]*(?:quater|quinquies)\b|\b212/2000\b|\bagenzia\s+delle\s+entrate\b|\bcartell\w+\b|\btribut\w+\b|\bimposta\b|\bsgravio\b",
        "Istanza di autotutela tributaria",
        "l_212_2000_art_10_quater",
        "titolo dell'istanza e annullamento dell'atto impositivo (artt. 10-quater e 10-quinquies L. 212/2000)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _atto(
        "trl_istanza_rimborso",
        r"(?:istanza|domanda)\s+di\s+rimborso(?:\s+.*)?",
        r"\b602/1973\b|\bimpost[ae]\b|\btribut\w+\b|\bagenzia\s+delle\s+entrate\b|\bversamento\s+(?:non\s+dovuto|indebito)\b",
        "Istanza di rimborso tributario",
        "dpr_602_1973_art_38",
        "titolo dell'istanza e versamento non dovuto (art. 38 D.P.R. 602/1973)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _comunicazione(
        "trl_comunicazione_irregolarita",
        r"comunicazione\s+(?:di\s+irregolarit[aà]|dell.?\s*esito\s+(?:del(?:la)?\s+)?(?:liquidazione|controllo)(?:\s+automatizzat[oa])?)(?:\s+.*)?|avviso\s+bonario(?:\s+.*)?",
        r"\b36[\s-]*(?:bis|ter)\b|\b54[\s-]*bis\b|\bdichiarazion\w+\b|\bagenzia\s+delle\s+entrate\b",
        "Comunicazione di irregolarità (avviso bonario)",
        "dpr_600_1973_art_36_bis",
        "titolo della comunicazione ed esito del controllo della dichiarazione (art. 36-bis D.P.R. 600/1973)",
        role="atto_amministrativo",
    ),
    _comunicazione(
        "trl_iscrizione_ipotecaria",
        r"comunicazione\s+preventiva\s+di\s+iscrizione\s+(?:di\s+)?ipoteca(?:ria)?(?:\s+.*)?|(?:avviso|comunicazione)\s+di\s+(?:avvenuta\s+)?iscrizione\s+(?:di\s+)?ipoteca(?:ria)?(?:\s+.*)?",
        _RISCOSSIONE + r"|\b77\b|\briscossione\b",
        "Comunicazione preventiva di iscrizione ipotecaria",
        "dpr_602_1973_art_77",
        "titolo della comunicazione e ipoteca dell'agente della riscossione (art. 77, comma 2-bis, D.P.R. 602/1973)",
        role="atto_amministrativo",
    ),
    _provvedimento(
        "trl_pignoramento_riscossione",
        r"(?:atto\s+di\s+)?pignoramento\s+(?:dei\s+crediti\s+)?presso\s+(?:il\s+)?terz[oi](?:\s+.*)?",
        r"\b72[\s-]*(?:bis|ter)\b|\bagente\s+della\s+riscossione\b|\bagenzia\s+delle\s+entrate[\s-]*riscossione\b",
        "Pignoramento presso terzi dell'agente della riscossione",
        "dpr_602_1973_art_72_bis",
        "titolo dell'atto e ordine al terzo di pagare all'agente della riscossione (art. 72-bis D.P.R. 602/1973)",
        tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _atto(
        "trl_istanza_rateizzazione",
        r"(?:istanza|domanda|richiesta)\s+di\s+(?:rateizzazione|rateazione|dilazione\s+(?:del|di)\s+pagamento)(?:\s+.*)?",
        _RISCOSSIONE + r"|\briscossione\b|\bcartell\w+\b|\brate\s+mensili\b",
        "Istanza di rateizzazione",
        "dpr_602_1973_art_19",
        "titolo dell'istanza e dilazione delle somme iscritte a ruolo (art. 19 D.P.R. 602/1973)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _provvedimento(
        "trl_provvedimento_rateizzazione",
        r"provvedimento\s+(?:sulla|di)\s+rateizzazione(?:\s+.*)?|(?:provvedimento\s+di\s+)?(?:accoglimento|rigetto)\s+(?:dell.?\s*istanza\s+di\s+|della\s+)?(?:rateizzazione|dilazione)(?:\s+.*)?|piano\s+di\s+rateizzazione(?:\s+.*)?",
        _RISCOSSIONE + r"|\briscossione\b|\bcartell\w+\b",
        "Provvedimento sulla rateizzazione",
        "dpr_602_1973_art_19",
        "titolo del provvedimento e piano di dilazione concesso o negato (art. 19 D.P.R. 602/1973)",
    ),
    _atto(
        "trl_definizione_agevolata",
        r"(?:dichiarazione|domanda|istanza)\s+di\s+adesione\s+alla\s+definizione\s+agevolata(?:\s+.*)?|(?:domanda|istanza)\s+di\s+rottamazione(?:\s+.*)?",
        r"\bcarich\w+\b|\bagente\s+della\s+riscossione\b|\b197/2022\b|\brottamazione\b",
        "Dichiarazione di adesione alla definizione agevolata",
        "l_197_2022_art_1",
        "titolo della dichiarazione e carichi affidati all'agente della riscossione (art. 1, comma 235, L. 197/2022)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _comunicazione(
        "trl_comunicazione_somme_definizione",
        r"comunicazione\s+(?:delle\s+somme\s+dovute|di\s+accoglimento)\s+(?:per\s+la\s+|della\s+)?definizione\s+agevolata(?:\s+.*)?",
        r"\brat[ae]\b|\bscadenz\w+\b|\bagente\s+della\s+riscossione\b|\bbollettin\w+\b",
        "Comunicazione delle somme dovute per la definizione agevolata",
        "l_197_2022_art_1",
        "titolo della comunicazione e somme da versare per la definizione (art. 1, comma 241, L. 197/2022)",
        role="atto_amministrativo",
    ),
    _provvedimento(
        "trl_accertamento_esecutivo_locale",
        r"avviso\s+di\s+accertamento\s+(?:esecutivo|(?:d.?\s*ufficio\s+|in\s+rettifica\s+)?(?:imu|tari|tasi|tosap|cosap|canone\s+unico|tributi\s+locali))(?:\s+.*)?",
        r"\b792\b|\b160/2019\b|\bcomune\b|\btributi\s+locali\b|\bimu\b|\btari\b",
        "Avviso di accertamento esecutivo dei tributi locali",
        "l_160_2019_art_1",
        "titolo dell'avviso ed efficacia esecutiva per i tributi dell'ente locale (art. 1, comma 792, L. 160/2019)",
    ),
    _provvedimento(
        "trl_ingiunzione_fiscale",
        r"ingiunzione\s+(?:fiscale|di\s+pagamento\s+(?:fiscale|(?:ex|ai\s+sensi\s+del)\s+r\.?\s*d\.?\s*(?:n\.?\s*)?639.*))(?:\s+.*)?",
        r"\b639\b|\bcomune\b|\bente\s+(?:locale|creditore|impositore)\b|\bconcessionari\w+\b",
        "Ingiunzione fiscale",
        "rd_639_1910_art_2",
        "titolo dell'ingiunzione e ordine di pagamento dell'ente (art. 2 R.D. 639/1910)",
    ),
    _provvedimento(
        "trl_processo_verbale_constatazione",
        r"processo\s+verbale\s+(?:di\s+constatazione|di\s+verifica|di\s+chiusura\s+(?:delle\s+)?operazioni)(?:\s+.*)?",
        r"\bguardia\s+di\s+finanza\b|\bverificator\w+\b|\bagenzia\s+delle\s+entrate\b|\bcontribuent\w+\b|\bverifica\s+fiscale\b",
        "Processo verbale di constatazione",
        "l_212_2000_art_12",
        "titolo del verbale e operazioni di verifica fiscale (art. 12 L. 212/2000)",
        role="verbale_ufficio", tipo=TipoDocumento.VERBALE,
    ),
    _comunicazione(
        "trl_schema_atto",
        r"(?:comunicazione\s+dello\s+)?schema\s+d.?\s*(?:i\s+)?atto(?:\s+.*)?",
        r"\b6[\s-]*bis\b|\bcontraddittorio\b|\b212/2000\b",
        "Schema d'atto per il contraddittorio preventivo",
        "l_212_2000_art_6_bis",
        "titolo dello schema e termine per le osservazioni del contribuente (art. 6-bis L. 212/2000)",
        role="atto_amministrativo",
    ),
    _atto(
        "trl_osservazioni_schema_atto",
        r"osservazioni\s+(?:allo|sullo)\s+schema\s+d.?\s*(?:i\s+)?atto(?:\s+.*)?|memoria\s+(?:per\s+il|nel)\s+contraddittorio\s+preventivo(?:\s+.*)?",
        r"\b6[\s-]*bis\b|\bcontraddittorio\b|\b212/2000\b",
        "Osservazioni allo schema d'atto",
        "l_212_2000_art_6_bis",
        "titolo delle osservazioni e contraddittorio preventivo (art. 6-bis L. 212/2000)",
        role="atto_difensivo", tipo=TipoDocumento.MEMORIA,
    ),
    _comunicazione(
        "trl_questionario_fiscale",
        r"questionario(?:\s+.*)?|invito\s+(?:a\s+comparire|ad?\s+esibire|a\s+trasmettere)(?:\s+.*)?",
        r"\b600/1973\b|\b633/1972\b|\bagenzia\s+delle\s+entrate\b|\bguardia\s+di\s+finanza\b",
        "Questionario o invito dell'Amministrazione finanziaria",
        "dpr_600_1973_art_32",
        "titolo dell'invito e richiesta di dati e documenti al contribuente (art. 32 D.P.R. 600/1973)",
        role="atto_amministrativo",
    ),
    _provvedimento(
        "trl_contestazione_sanzioni_tributarie",
        r"(?:atto|provvedimento)\s+di\s+(?:contestazione|irrogazione)\s+(?:delle\s+|di\s+)?sanzioni(?:\s+.*)?",
        r"\b472/1997\b|\btribut\w+\b|\bagenzia\s+delle\s+entrate\b|\bimposta\b|\bdogan\w+\b",
        "Atto di contestazione delle sanzioni tributarie",
        "d_lgs_472_1997_art_16",
        "titolo dell'atto e sanzioni amministrative tributarie (artt. 16 e 17 D.Lgs. 472/1997)",
    ),
    _atto(
        "trl_sospensione_legale_riscossione",
        r"(?:dichiarazione|istanza|domanda)\s+di\s+sospensione\s+legale\s+della\s+riscossione(?:\s+.*)?",
        r"\b537\b|\b228/2012\b|\bagente\s+della\s+riscossione\b|\bprescrizion\w+\b|\bsgravio\b",
        "Dichiarazione di sospensione legale della riscossione",
        "l_228_2012_art_1",
        "titolo della dichiarazione e causa di non esigibilità del carico (art. 1, comma 538, L. 228/2012)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _allegato(
        "trl_estratto_ruolo",
        r"estratto\s+(?:di|del)\s+ruolo(?:\s+.*)?",
        _RISCOSSIONE + r"|\bcartell\w+\b|\bente\s+creditore\b|\briscossione\b",
        "Estratto di ruolo",
        "dpr_602_1973_art_12",
        "titolo dell'estratto e carichi iscritti a ruolo (art. 12, comma 4-bis, D.P.R. 602/1973)",
    ),
    _allegato(
        "trl_modello_f24",
        r"(?:modello\s+(?:di\s+pagamento\s+unificato\s+)?)?f\s*24(?:\s+.*)?|delega\s+(?:di\s+pagamento\s+)?f\s*24(?:\s+.*)?",
        r"\bcodice\s+tributo\b|\bsezione\s+erario\b|\bsaldo\s+finale\b|\bdelega\s+irrevocabile\b|\bimporti\s+a\s+debito\b",
        "Modello F24",
        "d_lgs_241_1997_art_17",
        "titolo del modello e versamento unitario con codici tributo (art. 17 D.Lgs. 241/1997)",
        section="pagamenti",
    ),
)

_PREVIDENZA = (
    _provvedimento(
        "trl_avviso_addebito_inps",
        r"avviso\s+di\s+addebito(?:\s+.*)?",
        r"\binps\b|\b78/2010\b|\bcontribut\w+\b",
        "Avviso di addebito INPS",
        "dl_78_2010_art_30",
        "titolo dell'avviso e contributi dovuti all'INPS con valore di titolo esecutivo (art. 30 D.L. 78/2010)",
    ),
    _atto(
        "trl_domanda_naspi",
        r"domanda\s+(?:di\s+)?(?:indennit[aà]\s+(?:di\s+disoccupazione\s+)?)?(?:naspi|dis-?\s*coll)(?:\s+.*)?",
        r"\binps\b|\bdisoccupazion\w+\b|\b22/2015\b",
        "Domanda di indennità NASpI",
        "d_lgs_22_2015_art_6",
        "titolo della domanda e disoccupazione involontaria (art. 6 D.Lgs. 22/2015)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _atto(
        "trl_domanda_invalidita_civile",
        r"domanda\s+(?:di\s+)?(?:riconoscimento|accertamento)\s+(?:dell.?\s*|dello\s+stato\s+di\s+)?(?:invalidit[aà]\s+civile|handicap|disabilit[aà]|cecit[aà]\s+civile|sordit[aà])(?:\s+.*)?|certificato\s+medico\s+introduttivo(?:\s+.*)?",
        r"\binps\b|\bcertificato\s+medico\b|\bcommissione\s+medica\b|\b104/1992\b|\b118/1971\b",
        "Domanda di accertamento dell'invalidità civile",
        "dl_78_2009_art_20",
        "titolo della domanda e certificato medico trasmesso all'INPS (art. 20 D.L. 78/2009)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _provvedimento(
        "trl_verbale_invalidita_civile",
        r"verbale\s+(?:di\s+(?:visita|accertamento)\s+)?(?:della\s+)?commissione\s+medica(?:\s+.*)?|verbale\s+di\s+accertamento\s+(?:dell.?\s*)?(?:invalidit[aà]|handicap|disabilit[aà])(?:\s+.*)?",
        r"\bpercentual\w+\b|\binvalidit\w+\b|\bhandicap\b|\binps\b|\bcommissione\s+medica\b",
        "Verbale di accertamento dell'invalidità civile",
        "dl_78_2009_art_20",
        "titolo del verbale e giudizio della commissione medica (art. 20 D.L. 78/2009)",
        role="verbale_ufficio", tipo=TipoDocumento.VERBALE,
    ),
    _atto(
        "trl_ricorso_atp_previdenziale",
        r"ricorso\s+per\s+accertamento\s+tecnico\s+preventivo(?:\s+obbligatorio)?(?:\s+.*)?|ricorso\s+(?:ex|ai\s+sensi\s+dell.?)\s*art\.?\s*445[\s-]*bis(?:\s+.*)?",
        r"\b445[\s-]*bis\b|\binvalidit\w+\b|\bprestazion\w+\b|\binps\b",
        "Ricorso per accertamento tecnico preventivo obbligatorio (art. 445-bis c.p.c.)",
        "cpc_art_445_bis",
        "titolo del ricorso e verifica delle condizioni sanitarie per la prestazione (art. 445-bis c.p.c.)",
    ),
    _atto(
        "trl_dissenso_atp",
        r"dichiarazione\s+di\s+dissenso(?:\s+.*)?|atto\s+di\s+(?:contestazione|dissenso)\s+(?:alle\s+)?conclusioni\s+del\s+(?:c\.?\s*t\.?\s*u\.?|consulente)(?:\s+.*)?",
        r"\b445[\s-]*bis\b|\baccertamento\s+tecnico\s+preventivo\b|\bconclusioni\s+del\s+(?:c\.?t\.?u|consulente)\b",
        "Dichiarazione di dissenso (art. 445-bis c.p.c.)",
        "cpc_art_445_bis",
        "titolo della dichiarazione e contestazione delle conclusioni del consulente (art. 445-bis, comma 4, c.p.c.)",
        role="atto_difensivo", tipo=TipoDocumento.MEMORIA,
    ),
    _atto(
        "trl_ricorso_previdenziale_442",
        r"ricorso(?:\s+.*)?",
        r"\bart\.?\s*442\s+c\.?\s*p\.?\s*c\b|\bcontroversi\w+\s+in\s+materia\s+di\s+previdenza\b",
        "Ricorso in materia di previdenza e assistenza (art. 442 c.p.c.)",
        "cpc_art_442",
        "titolo del ricorso e controversia previdenziale o assistenziale (art. 442 c.p.c.)",
    ),
    _comunicazione(
        "trl_denuncia_infortunio",
        r"denuncia(?:\s*/\s*comunicazione)?\s+(?:di\s+|d.?\s*)infortunio(?:\s+.*)?|comunicazione\s+(?:di\s+|d.?\s*)infortunio(?:\s+.*)?",
        r"\binail\b|\b1124/1965\b|\bdatore\s+di\s+lavoro\b|\bprognosi\b",
        "Denuncia di infortunio sul lavoro",
        "dpr_1124_1965_art_53",
        "titolo della denuncia e infortunio comunicato all'INAIL (art. 53 D.P.R. 1124/1965)",
    ),
    _comunicazione(
        "trl_denuncia_malattia_professionale",
        r"denuncia\s+(?:di\s+)?malattia\s+professionale(?:\s+.*)?|(?:primo\s+)?certificato\s+(?:medico\s+)?di\s+malattia\s+professionale(?:\s+.*)?",
        r"\binail\b|\b1124/1965\b|\btecnopat\w+\b|\besposizion\w+\b",
        "Denuncia di malattia professionale",
        "dpr_1124_1965_art_53",
        "titolo della denuncia e malattia professionale comunicata all'INAIL (art. 53 D.P.R. 1124/1965)",
    ),
    _provvedimento(
        "trl_rendita_inail",
        r"(?:provvedimento|comunicazione)\s+di\s+(?:costituzione|liquidazione|revisione)\s+(?:della\s+)?rendita(?:\s+.*)?",
        r"\binail\b|\binabilit\w+\b|\bmenomazion\w+\b|\bdanno\s+biologico\b",
        "Provvedimento di costituzione della rendita INAIL",
        "dpr_1124_1965_art_66",
        "titolo del provvedimento e rendita per inabilità permanente (art. 66 D.P.R. 1124/1965)",
    ),
)

_ISPEZIONI = (
    _provvedimento(
        "trl_verbale_unico_accertamento",
        r"verbale\s+unico\s+di\s+accertamento(?:\s+.*)?|verbale\s+di\s+accertamento\s+(?:ispettivo|e\s+notificazione|e\s+notifica)(?:\s+.*)?",
        _ISPETTORATO + r"|\binps\b|\binail\b",
        "Verbale unico di accertamento e notificazione",
        "d_lgs_124_2004_art_13",
        "titolo del verbale e illeciti accertati in sede ispettiva (art. 13 D.Lgs. 124/2004)",
        role="verbale_ufficio", tipo=TipoDocumento.VERBALE,
    ),
    _provvedimento(
        "trl_verbale_primo_accesso",
        r"verbale\s+di\s+primo\s+accesso(?:\s+ispettivo)?(?:\s+.*)?",
        _ISPETTORATO + r"|\blavorator\w+\b",
        "Verbale di primo accesso ispettivo",
        "d_lgs_124_2004_art_13",
        "titolo del verbale e lavoratori trovati al primo accesso (art. 13, comma 1, D.Lgs. 124/2004)",
        role="verbale_ufficio", tipo=TipoDocumento.VERBALE,
    ),
    _provvedimento(
        "trl_diffida_accertativa",
        r"diffida\s+accertativa(?:\s+.*)?",
        _ISPETTORATO + r"|\bcredit\w+\s+patrimonial\w+\b|\bretribu\w+\b",
        "Diffida accertativa per crediti patrimoniali",
        "d_lgs_124_2004_art_12",
        "titolo della diffida e crediti retributivi accertati dall'ispettore (art. 12 D.Lgs. 124/2004)",
    ),
    _allegato(
        "trl_conciliazione_monocratica",
        r"(?:verbale\s+di\s+|richiesta\s+di\s+|convocazione\s+per\s+(?:la\s+)?)?conciliazione\s+monocratica(?:\s+.*)?",
        _ISPETTORATO + r"|\bmonocratic\w+\b",
        "Conciliazione monocratica",
        "d_lgs_124_2004_art_11",
        "titolo dell'atto e conciliazione davanti all'Ispettorato (art. 11 D.Lgs. 124/2004)",
        role="verbale_ufficio", tipo=TipoDocumento.VERBALE,
    ),
    _atto(
        "trl_ricorso_ispettorato",
        r"ricorso\s+(?:al\s+direttore\s+(?:della\s+sede\s+territoriale\s+)?dell.?\s*ispettorato|al\s+comitato\s+(?:regionale\s+)?per\s+i\s+rapporti\s+di\s+lavoro|all.?\s*ispettorato(?:\s+(?:nazionale|territoriale))?\s+del\s+lavoro)(?:\s+.*)?",
        _ISPETTORATO + r"|\bverbale\b|\bcomitato\b",
        "Ricorso all'Ispettorato del lavoro",
        "d_lgs_124_2004_art_16",
        "titolo del ricorso e atto di accertamento ispettivo impugnato (artt. 16 e 17 D.Lgs. 124/2004)",
    ),
    _provvedimento(
        "trl_prescrizione_vigilanza",
        r"(?:verbale\s+di\s+)?prescrizion[ei](?:\s+(?:obbligatori[ae]|dell.?\s*organo\s+di\s+vigilanza|ex\s+art|ai\s+sensi).*)?",
        r"\b758/1994\b|\bcontravvenzion\w+\b|\borgano\s+di\s+vigilanza\b|\b81/2008\b",
        "Prescrizione dell'organo di vigilanza",
        "d_lgs_758_1994_art_20",
        "titolo della prescrizione e regolarizzazione della contravvenzione (art. 20 D.Lgs. 758/1994)",
    ),
    _provvedimento(
        "trl_sospensione_attivita_imprenditoriale",
        r"provvedimento\s+di\s+sospensione\s+dell.?\s*attivit[aà](?:\s+imprenditoriale)?(?:\s+.*)?",
        r"\b81/2008\b|\blavoratori?\s+irregolar\w*\b|\bispettorat\w+\b|\bsalute\s+e\s+sicurezza\b",
        "Provvedimento di sospensione dell'attività imprenditoriale",
        "d_lgs_81_2008_art_14",
        "titolo del provvedimento e lavoro irregolare o violazioni di sicurezza (art. 14 D.Lgs. 81/2008)",
    ),
)

_LAVORO = (
    _comunicazione(
        "trl_provvedimento_disciplinare",
        r"(?:lettera\s+di\s+|comunicazione\s+di\s+|provvedimento\s+di\s+)?(?:irrogazione\s+(?:della\s+|di\s+)?)?sanzione\s+disciplinare(?:\s+.*)?|provvedimento\s+disciplinare(?:\s+.*)?",
        r"\blavorator\w+\b|\bdipendent\w+\b|\bdatore\s+di\s+lavoro\b|\b300/1970\b|\bccnl\b",
        "Provvedimento disciplinare al lavoratore",
        "l_300_1970_art_7",
        "titolo del provvedimento e sanzione inflitta dopo la contestazione (art. 7 L. 300/1970)",
    ),
    _comunicazione(
        "trl_giustificazioni_disciplinari",
        r"giustificazioni(?:\s+(?:alla|alle|in\s+merito|del\s+lavoratore|ex\s+art).*)?|(?:lettera\s+di\s+|memoria\s+di\s+)?(?:difese|controdeduzioni)\s+(?:alla|alle|in\s+merito\s+alla)\s+contestazione(?:\s+.*)?",
        r"\bcontestazion\w+\b|\baddebit\w+\b|\bart\.?\s*7\b",
        "Giustificazioni alla contestazione disciplinare",
        "l_300_1970_art_7",
        "titolo dell'atto e difese del lavoratore sull'addebito (art. 7, commi 2 e 5, L. 300/1970)",
    ),
    _comunicazione(
        "trl_risoluzione_consensuale",
        r"(?:accordo\s+di\s+|modulo\s+di\s+|comunicazione\s+di\s+)?risoluzione\s+consensuale\s+del\s+rapporto\s+di\s+lavoro(?:\s+.*)?",
        r"\brapporto\s+di\s+lavoro\b|\b151/2015\b|\btelematic\w+\b|\bdatore\s+di\s+lavoro\b",
        "Risoluzione consensuale del rapporto di lavoro",
        "d_lgs_151_2015_art_26",
        "titolo dell'atto e cessazione concordata con modalità telematiche (art. 26 D.Lgs. 151/2015)",
    ),
    _comunicazione(
        "trl_revoca_dimissioni",
        r"revoca\s+(?:delle\s+)?dimissioni(?:\s+.*)?|revoca\s+della\s+risoluzione\s+consensuale(?:\s+.*)?",
        r"\bdimission\w+\b|\brisoluzione\s+consensuale\b|\b151/2015\b",
        "Revoca delle dimissioni",
        "d_lgs_151_2015_art_26",
        "titolo dell'atto e revoca entro sette giorni (art. 26, comma 2, D.Lgs. 151/2015)",
    ),
    _atto(
        "trl_tentativo_conciliazione_lavoro",
        r"(?:richiesta|istanza|domanda)\s+(?:del\s+|di\s+)?tentativo\s+(?:obbligatorio\s+|facoltativo\s+)?di\s+conciliazione(?:\s+.*)?",
        r"\b410\b|\bcommission\w+\s+di\s+conciliazione\b|\bispettorat\w+\b|\bsindacal\w+\b",
        "Richiesta di tentativo di conciliazione (art. 410 c.p.c.)",
        "cpc_art_410",
        "titolo della richiesta e commissione di conciliazione presso l'Ispettorato (art. 410 c.p.c.)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _atto(
        "trl_ricorso_condotta_antisindacale",
        r"ricorso\s+per\s+(?:la\s+)?repressione\s+(?:della\s+)?condotta\s+antisindacale(?:\s+.*)?|ricorso\s+per\s+condotta\s+antisindacale(?:\s+.*)?|ricorso\s+(?:ex|ai\s+sensi\s+dell.?)\s*art\.?\s*28\s+(?:dell[ao]\s+)?(?:l\.?|legge|statuto)(?:\s+.*)?",
        r"\bantisindacal\w+\b|\b300/1970\b|\bstatuto\s+dei\s+lavoratori\b",
        "Ricorso per repressione della condotta antisindacale (art. 28 L. 300/1970)",
        "l_300_1970_art_28",
        "titolo del ricorso e comportamento antisindacale del datore (art. 28 L. 300/1970)",
    ),
    _comunicazione(
        "trl_licenziamento_collettivo",
        r"comunicazione\s+di\s+(?:avvio|apertura)\s+(?:della\s+)?procedura\s+di\s+(?:licenziamento\s+collettivo|riduzione\s+(?:del\s+)?personale|mobilit[aà])(?:\s+.*)?|procedura\s+di\s+licenziamento\s+collettivo(?:\s+.*)?",
        r"\b223/1991\b|\besuber\w+\b|\brappresentanze\s+sindacali\b|\beccedenz\w+\b",
        "Comunicazione di avvio della procedura di licenziamento collettivo",
        "l_223_1991_art_4",
        "titolo della comunicazione ed eccedenza di personale (artt. 4 e 24 L. 223/1991)",
    ),
    _atto(
        "trl_domanda_cassa_integrazione",
        r"domanda\s+(?:di\s+)?(?:concessione\s+(?:della\s+|del(?:l.?)?\s*)?)?(?:cassa\s+integrazione(?:\s+guadagni)?(?:\s+(?:ordinaria|straordinaria))?|cig[os]?|trattamento\s+di\s+integrazione\s+salariale|assegno\s+di\s+integrazione\s+salariale)(?:\s+.*)?",
        r"\binps\b|\bintegrazione\s+salariale\b|\b148/2015\b|\bsospension\w+\b|\briduzion\w+\b",
        "Domanda di cassa integrazione guadagni",
        "d_lgs_148_2015_art_15",
        "titolo della domanda e sospensione o riduzione dell'attività (art. 15 D.Lgs. 148/2015)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _allegato(
        "trl_prospetto_tfr",
        r"(?:prospetto|conteggio|calcolo|scheda)\s+(?:di\s+|del\s+)?(?:liquidazione\s+(?:del\s+)?)?(?:t\.?\s*f\.?\s*r\.?|trattamento\s+di\s+fine\s+rapporto)(?:\s+.*)?",
        r"\b2120\b|\brivalutazion\w+\b|\bretribu\w+\b|\baccantonament\w+\b|\bquot[ae]\b",
        "Prospetto di liquidazione del TFR",
        "cc_art_2120",
        "titolo del prospetto e quote accantonate e rivalutate (art. 2120 c.c.)",
    ),
    _comunicazione(
        "trl_anticipazione_tfr",
        r"(?:richiesta|domanda|istanza)\s+di\s+anticipazione\s+(?:del\s+)?(?:t\.?\s*f\.?\s*r\.?|trattamento\s+di\s+fine\s+rapporto)(?:\s+.*)?",
        r"\b2120\b|\bspese\s+sanitarie\b|\bprima\s+casa\b|\banzianit\w+\b|\bdatore\s+di\s+lavoro\b",
        "Richiesta di anticipazione del TFR",
        "cc_art_2120",
        "titolo della richiesta e causali dell'anticipazione (art. 2120, commi 6-8, c.c.)",
    ),
    _atto(
        "trl_fondo_garanzia_tfr",
        r"domanda\s+(?:di\s+intervento\s+)?(?:al|del)\s+fondo\s+di\s+garanzia(?:\s+.*)?",
        r"\b297/1982\b|\bt\.?f\.?r\.?\b|\btrattamento\s+di\s+fine\s+rapporto\b|\binps\b",
        "Domanda al Fondo di garanzia INPS",
        "l_297_1982_art_2",
        "titolo della domanda e TFR non pagato dal datore insolvente (art. 2 L. 297/1982)",
        role="istanza", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
    ),
    _allegato(
        "trl_comunicazione_obbligatoria_unilav",
        r"comunicazione\s+obbligatoria(?:\s+.*)?|(?:modello\s+)?unilav(?:\s+.*)?",
        r"\bunilav\b|\b510/1996\b|\bcentro\s+per\s+l.?\s*impiego\b|\bdatore\s+di\s+lavoro\b",
        "Comunicazione obbligatoria di assunzione o cessazione (Unilav)",
        "dl_510_1996_art_9_bis",
        "titolo della comunicazione e instaurazione o cessazione del rapporto (art. 9-bis D.L. 510/1996)",
        role="certificato",
    ),
    _comunicazione(
        "trl_trasferimento_lavoratore",
        r"(?:lettera|comunicazione|provvedimento)\s+di\s+trasferimento(?:\s+.*)?",
        r"\b2103\b|\bunit[aà]\s+produttiv\w+\b|\bsede\s+di\s+lavoro\b",
        "Lettera di trasferimento del lavoratore",
        "cc_art_2103",
        "titolo della lettera e nuova unità produttiva (art. 2103 c.c.)",
    ),
)

REGOLE: tuple[RegolaTitolo, ...] = (
    *_PROCESSO_TRIBUTARIO,
    *_PROCEDIMENTO_TRIBUTARIO,
    *_PREVIDENZA,
    *_ISPEZIONI,
    *_LAVORO,
)

__all__ = ["FONTI", "REGOLE"]
