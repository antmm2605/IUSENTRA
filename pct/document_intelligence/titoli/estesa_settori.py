"""Privacy e digitale, comunicazioni, circolazione e trasporti, sanzioni amministrative, professione forense, ordinamento giudiziario e spese di giustizia.

Regole d'identità dal titolo aggiunte il 02/11/2026 per coprire tutte le materie (direttiva dell'avvocato del
01/11/2026). Ogni regola cita la norma che definisce l'atto, registrata in `FONTI` con URL ufficiale e data di
consultazione.

Non duplicano le regole già presenti nelle altre aree: reclamo al Garante, richiesta di esercizio dei diritti,
comunicazione di violazione dei dati, informativa e consenso (studio/consumo); verbale di accertamento CdS,
ordinanza-ingiunzione e opposizione a sanzione amministrativa (amministrativo); reclamo al vettore per ritardo o
cancellazione del volo (consumo); preventivo e conferimento dell'incarico (studio); equa riparazione (civile).
Dove il documento è lo stesso ma il titolo è diverso, la regola riusa la stessa etichetta.
"""

from __future__ import annotations

from typing import Any

from pct.fascicoli import TipoDocumento

from ._modello import RegolaTitolo, regola

_NORMATTIVA = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
_VERIFICA = "testo vigente consultato su Normattiva il 02/11/2026"
_VERIFICA_AGCOM = ("art. 1, comma 11, L. 249/1997 consultato su Normattiva il 02/11/2026; regolamento AGCOM "
                   "(Allegato A alla delibera 203/18/CONS e successive modifiche) verificato su fonti AGCOM/CORECOM il 02/11/2026")

_CODICE_PRIVACY = "decreto.legislativo:2003-06-30;196~art"
_CDS = "decreto.legislativo:1992-04-30;285~art"
_L689 = "legge:1981-11-24;689~art"
_L247 = "legge:2012-12-31;247~art"
_DPR115 = "decreto.del.presidente.della.repubblica:2002-05-30;115~art"


def _fonte(label: str, urn: str) -> dict[str, Any]:
    return {"label": label, "official_url": _NORMATTIVA + urn, "verification_status": _VERIFICA, "source_type": "normativa"}


def _fonte_url(label: str, url: str, verifica: str) -> dict[str, Any]:
    return {"label": label, "official_url": url, "verification_status": verifica, "source_type": "normativa"}


FONTI: dict[str, dict[str, Any]] = {
    # Privacy e digitale
    "estesa_settori_gdpr_titolare_responsabile": _fonte(
        "D.Lgs. 196/2003, art. 1, e Reg. UE 2016/679 da esso richiamato, artt. 26, 28 e 30: contitolari, responsabile del trattamento e registro delle attività",
        _CODICE_PRIVACY + "1"),
    "estesa_settori_gdpr_dpia_dpo": _fonte(
        "D.Lgs. 196/2003, art. 1, e Reg. UE 2016/679 da esso richiamato, artt. 35 e 37-39: valutazione d'impatto e responsabile della protezione dei dati",
        _CODICE_PRIVACY + "1"),
    "estesa_settori_codice_privacy_designati": _fonte(
        "D.Lgs. 196/2003, art. 2-quaterdecies: attribuzione di funzioni e compiti a soggetti designati", _CODICE_PRIVACY + "2quaterdecies"),
    "estesa_settori_codice_privacy_garante": _fonte(
        "D.Lgs. 196/2003, artt. 144, 154 e 157 e Reg. UE 2016/679 art. 58: segnalazioni, provvedimenti e richieste del Garante", _CODICE_PRIVACY + "144"),
    "estesa_settori_codice_privacy_ricorso": _fonte(
        "D.Lgs. 196/2003, art. 152, e D.Lgs. 150/2011, art. 10: ricorso all'autorità giudiziaria ordinaria in materia di dati personali", _CODICE_PRIVACY + "152"),
    # Comunicazioni elettroniche
    "estesa_settori_agcom_controversie": _fonte_url(
        "L. 249/1997, art. 1, comma 11, e regolamento AGCOM delibera 203/18/CONS: conciliazione (UG), provvedimenti temporanei (GU5) e definizione (GU14) delle controversie",
        _NORMATTIVA + "legge:1997-07-31;249~art1", _VERIFICA_AGCOM),
    # Circolazione stradale e trasporti
    "estesa_settori_cds_ricorsi": _fonte(
        "D.Lgs. 285/1992, artt. 203, 204 e 204-bis, e D.Lgs. 150/2011, art. 7: ricorso al prefetto, provvedimenti del prefetto, ricorso al giudice di pace", _CDS + "203"),
    "estesa_settori_cds_patente": _fonte(
        "D.Lgs. 285/1992, artt. 126-bis, 128, 218, 219 e 223: patente a punti, revisione, sospensione, revoca e ritiro della patente", _CDS + "218"),
    "estesa_settori_cds_veicolo": _fonte(
        "D.Lgs. 285/1992, artt. 213 e 214: sequestro e fermo amministrativo del veicolo", _CDS + "214"),
    "estesa_settori_cds_dati_conducente": _fonte(
        "D.Lgs. 285/1992, art. 126-bis, comma 2: comunicazione dei dati del conducente e decurtazione dei punti", _CDS + "126bis"),
    "estesa_settori_trasporto_aereo": _fonte(
        "D.Lgs. 69/2006, artt. 1 e 2 (ENAC organismo responsabile del Reg. CE 261/2004) e L. 12/2004 (Convenzione di Montreal, art. 31: reclamo per bagaglio)",
        "decreto.legislativo:2006-01-27;69~art2"),
    # Sanzioni amministrative
    "estesa_settori_l689_procedimento": _fonte(
        "L. 689/1981, artt. 14, 18 e 26: contestazione, scritti difensivi, ordinanza di archiviazione e pagamento rateale", _L689 + "18"),
    # Professione forense
    "estesa_settori_l247_disciplina": _fonte(
        "L. 247/2012, artt. 50, 58, 59 e 61: esposto, procedimento davanti al consiglio distrettuale di disciplina, decisione e ricorso al CNF", _L247 + "59"),
    "estesa_settori_l247_albo": _fonte(
        "L. 247/2012, artt. 17, 36, 41 e 45: iscrizione e cancellazione dall'albo, registro dei praticanti, certificato di compiuto tirocinio", _L247 + "17"),
    "estesa_settori_l247_congruita": _fonte(
        "L. 247/2012, art. 29, comma 1, lett. l): pareri del consiglio dell'ordine sulla liquidazione dei compensi", _L247 + "29"),
    # Spese di giustizia
    "estesa_settori_dpr115_patrocinio": _fonte(
        "D.P.R. 115/2002, artt. 74-79, 96, 112, 126 e 136: istanza, ammissione, rigetto e revoca del patrocinio a spese dello Stato", _DPR115 + "78"),
    "estesa_settori_dpr115_liquidazione": _fonte(
        "D.P.R. 115/2002, artt. 71, 82, 83 e 168: domanda di liquidazione e decreto di pagamento di difensori e ausiliari", _DPR115 + "82"),
    "estesa_settori_dpr115_opposizione": _fonte(
        "D.P.R. 115/2002, art. 170, e D.Lgs. 150/2011, art. 15: opposizione al decreto di pagamento", _DPR115 + "170"),
    "estesa_settori_dpr115_recupero": _fonte(
        "D.P.R. 115/2002, artt. 212 e 248: invito al pagamento delle spese di giustizia e del contributo unificato", _DPR115 + "248"),
}

_DATI = r"\bdati\s+personali\b|\btrattament\w+\b|\b679\b|\bgdpr\b"
_PATROCINIO = r"\bpatrocinio\s+a\s+spese\s+dello\s+stato\b|\bgratuito\s+patrocinio\b|\b115/2002\b|\b7[4-9]\b|\b96\b|\b126\b"

REGOLE: tuple[RegolaTitolo, ...] = (
    # ── Privacy e digitale ──
    regola(
        "set_provvedimento_garante",
        r"provvedimento\s+(?:correttivo\s+|sanzionatorio\s+)?del\s+garante(?:\s+per\s+la\s+protezione\s+dei\s+dati(?:\s+personali)?)?(?:\s+.*)?|provvedimento\s+(?:di\s+)?(?:ammonimento|limitazione\s+del\s+trattamento)(?:\s+.*)?",
        r"\bgarante\b|\b58\b|\b154\b|\b157\b",
        "Provvedimento del Garante per la protezione dei dati personali",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_codice_privacy_garante",
        evidence="provvedimento dell'autorità di controllo (art. 58 Reg. UE 2016/679, art. 154 D.Lgs. 196/2003)",
    ),
    regola(
        "set_richiesta_informazioni_garante",
        r"richiesta\s+di\s+informazioni(?:\s+e\s+(?:di\s+)?esibizione\s+(?:di\s+)?documenti)?\s+(?:del\s+garante|ex\s+art\.?\s*157)(?:\s+.*)?",
        r"\bgarante\b|\b157\b|\besibizion\w+\b",
        "Richiesta di informazioni del Garante privacy",
        role="atto_amministrativo", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_codice_privacy_garante",
        evidence="richiesta di informazioni ed esibizione di documenti (art. 157 D.Lgs. 196/2003)",
    ),
    regola(
        "set_segnalazione_garante",
        r"segnalazione\s+(?:al\s+garante(?:\s+per\s+la\s+protezione\s+dei\s+dati(?:\s+personali)?|\s+privacy)?|ex\s+art\.?\s*144)(?:\s+.*)?",
        r"\bgarante\b|\b144\b|" + _DATI,
        "Segnalazione al Garante privacy",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO, deposit_role="atto_principale",
        fonte="estesa_settori_codice_privacy_garante",
        evidence="segnalazione al Garante (art. 144 D.Lgs. 196/2003)",
    ),
    regola(
        "set_ricorso_tribunale_privacy",
        r"ricorso\s+(?:al\s+tribunale\s+)?(?:avverso|contro|in\s+opposizione\s+al)\s+(?:il\s+)?provvedimento\s+del\s+garante(?:\s+.*)?|ricorso\s+(?:al\s+tribunale\s+)?in\s+materia\s+di\s+(?:protezione\s+dei\s+)?dati\s+personali(?:\s+.*)?|ricorso\s+(?:ex|ai\s+sensi\s+dell.?)\s*art\.?\s*152\s+(?:d\.?\s*lgs\.?\s*196/2003|codice\s+(?:della\s+)?privacy)(?:\s+.*)?",
        r"\bgarante\b|\b152\b|\b150/2011\b|" + _DATI,
        "Ricorso al tribunale in materia di protezione dei dati personali",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO, deposit_role="atto_principale",
        fonte="estesa_settori_codice_privacy_ricorso",
        evidence="ricorso all'autorità giudiziaria ordinaria (art. 152 D.Lgs. 196/2003, art. 10 D.Lgs. 150/2011)",
    ),
    regola(
        "set_nomina_responsabile_trattamento",
        r"(?:atto\s+di\s+)?(?:nomina|designazione)\s+(?:a\s+|del\s+|quale\s+)?responsabile\s+(?:esterno\s+)?del\s+trattamento(?:\s+.*)?|accordo\s+(?:sul|per\s+il)\s+trattamento\s+dei\s+dati(?:\s+personali)?(?:\s+.*)?|data\s+processing\s+agreement(?:\s+.*)?",
        r"\b28\b|\bresponsabile\s+del\s+trattamento\b|\btitolare\s+del\s+trattamento\b",
        "Nomina del responsabile del trattamento (art. 28 GDPR)",
        role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
        fonte="estesa_settori_gdpr_titolare_responsabile",
        evidence="atto giuridico che vincola il responsabile al titolare (art. 28 Reg. UE 2016/679)",
    ),
    regola(
        "set_accordo_contitolarita",
        r"accordo\s+(?:di\s+)?contitolarit[aà]'?(?:\s+.*)?|accordo\s+tra\s+contitolari(?:\s+del\s+trattamento)?(?:\s+.*)?",
        r"\b26\b|\bcontitolar\w+\b",
        "Accordo di contitolarità del trattamento (art. 26 GDPR)",
        role="contratto", section="contratti", tipo=TipoDocumento.CONTRATTO,
        fonte="estesa_settori_gdpr_titolare_responsabile",
        evidence="accordo interno fra contitolari del trattamento (art. 26 Reg. UE 2016/679)",
    ),
    regola(
        "set_registro_trattamenti",
        r"registro\s+(?:delle\s+)?(?:attivit[aà]'?\s+di\s+trattamento|(?:dei\s+)?trattamenti)(?:\s+.*)?",
        r"\b30\b|\bfinalit[aà]'?\b|\bcategori\w+\b|\btitolare\s+del\s+trattamento\b",
        "Registro delle attività di trattamento (art. 30 GDPR)",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_gdpr_titolare_responsabile",
        evidence="registro tenuto dal titolare o dal responsabile (art. 30 Reg. UE 2016/679)",
    ),
    regola(
        "set_dpia",
        r"valutazione\s+(?:d.?\s*)?impatto\s+(?:sulla\s+)?protezione\s+dei\s+dati(?:\s+.*)?|dpia(?:\s+.*)?|data\s+protection\s+impact\s+assessment(?:\s+.*)?",
        r"\b35\b|\brisch\w+\b|\bmisure\b",
        "Valutazione d'impatto sulla protezione dei dati (DPIA)",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_gdpr_dpia_dpo",
        evidence="valutazione dei rischi del trattamento (art. 35 Reg. UE 2016/679)",
    ),
    regola(
        "set_nomina_dpo",
        r"(?:atto\s+di\s+)?(?:nomina|designazione)\s+(?:del\s+)?(?:responsabile\s+della\s+protezione\s+dei\s+dati|rpd|dpo|data\s+protection\s+officer)(?:\s+.*)?",
        r"\b3[7-9]\b|\brpd\b|\bdpo\b|\bprotezione\s+dei\s+dati\b",
        "Nomina del responsabile della protezione dei dati (DPO)",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_gdpr_dpia_dpo",
        evidence="designazione del responsabile della protezione dei dati (artt. 37-39 Reg. UE 2016/679)",
    ),
    regola(
        "set_designazione_autorizzati",
        r"(?:atto\s+di\s+)?(?:designazione|autorizzazione|nomina)\s+(?:dei\s+|degli\s+|del(?:l.?)?\s*|quale\s+)?(?:soggett[oi]\s+)?(?:autorizzat[oi]|incaricat[oi]|designat[oi])\s+(?:al\s+trattamento|del\s+trattamento)(?:\s+.*)?|autorizzazione\s+al\s+trattamento\s+dei\s+dati(?:\s+personali)?(?:\s+.*)?",
        r"\b2-?quaterdecies\b|\b29\b|\bistruzion\w+\b|\btitolare\s+del\s+trattamento\b",
        "Designazione dei soggetti autorizzati al trattamento",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_codice_privacy_designati",
        evidence="attribuzione di compiti a persone autorizzate (art. 2-quaterdecies D.Lgs. 196/2003, art. 29 GDPR)",
    ),
    # ── Comunicazioni elettroniche (AGCOM/CORECOM) ──
    regola(
        "set_istanza_conciliazione_corecom",
        r"(?:istanza|domanda)\s+di\s+conciliazione\s+(?:al\s+corecom|corecom|conciliaweb|(?:mod(?:ello|\.)?\s+|formulario\s+)?ug|(?:in\s+materia\s+di|per\s+(?:le\s+)?)\s*comunicazioni\s+elettroniche)(?:\s+.*)?",
        r"\bcorecom\b|\bagcom\b|\bconciliaweb\b|\b203/18/cons\b|\boperator\w+\b|\btentativo\s+obbligatorio\s+di\s+conciliazione\b",
        "Istanza di conciliazione al CORECOM (comunicazioni elettroniche)",
        role="istanza_mediazione", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_agcom_controversie",
        evidence="tentativo obbligatorio di conciliazione (art. 1, comma 11, L. 249/1997; delibera AGCOM 203/18/CONS)",
    ),
    regola(
        "set_istanza_provvedimento_temporaneo_agcom",
        r"(?:istanza|richiesta)\s+di\s+provvedimento\s+temporaneo(?:\s+.*)?|(?:formulario|modello|istanza)\s+gu\s*5(?:\s+.*)?",
        r"\bcorecom\b|\bagcom\b|\bconciliaweb\b|\boperator\w+\b|\bsospension\w+\s+del\s+servizio\b",
        "Istanza di provvedimento temporaneo (GU5)",
        role="istanza_mediazione", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_agcom_controversie",
        evidence="provvedimenti temporanei per garantire il servizio (art. 5 regolamento delibera AGCOM 203/18/CONS)",
    ),
    regola(
        "set_istanza_definizione_controversia",
        r"(?:istanza|domanda)\s+di\s+definizione\s+(?:della\s+)?controversia(?:\s+.*)?|(?:formulario|modello|istanza)\s+gu\s*14(?:\s+.*)?",
        r"\bcorecom\b|\bagcom\b|\bconciliaweb\b|\boperator\w+\b|\b203/18/cons\b",
        "Istanza di definizione della controversia (GU14)",
        role="atto_adr", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_agcom_controversie",
        evidence="istanza di definizione dopo il tentativo di conciliazione (art. 14 regolamento delibera AGCOM 203/18/CONS)",
    ),
    regola(
        "set_decisione_definizione_controversia",
        r"(?:determina(?:zione)?|delibera(?:zione)?|decisione|provvedimento)\s+di\s+definizione\s+(?:della\s+)?controversia(?:\s+.*)?",
        r"\bcorecom\b|\bagcom\b|\boperator\w+\b|\bindennizz\w+\b",
        "Decisione di definizione della controversia (AGCOM/CORECOM)",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_agcom_controversie",
        evidence="provvedimento che definisce la controversia utente-operatore (regolamento delibera AGCOM 203/18/CONS)",
    ),
    # ── Circolazione stradale ──
    regola(
        "set_ricorso_prefetto",
        r"ricorso\s+(?:amministrativo\s+)?al\s+prefetto(?:\s+.*)?|ricorso\s+(?:ex|ai\s+sensi\s+dell.?)\s*art\.?\s*203\s+(?:c\.?\s*d\.?\s*s\.?|codice\s+della\s+strada)(?:\s+.*)?",
        r"\bprefett\w+\b|\b203\b|\bverbale\b|\bcodice\s+della\s+strada\b",
        "Ricorso al Prefetto (art. 203 C.d.S.)",
        role="atto_amministrativo", section="atti", tipo=TipoDocumento.RICORSO,
        fonte="estesa_settori_cds_ricorsi",
        evidence="ricorso al prefetto entro sessanta giorni dalla contestazione (art. 203 D.Lgs. 285/1992)",
    ),
    regola(
        "set_ricorso_gdp_verbale_cds",
        r"ricorso\s+(?:al\s+giudice\s+di\s+pace\s+)?(?:ex|ai\s+sensi\s+dell.?)\s*(?:art\.?\s*204-?bis|art\.?\s*7\s+d\.?\s*lgs\.?\s*150/2011)(?:\s+.*)?|ricorso\s+(?:al\s+giudice\s+di\s+pace\s+)?(?:avverso|contro)\s+(?:il\s+)?verbale\s+(?:di\s+(?:accertamento|contestazione)|del\s+codice\s+della\s+strada|n\.?)(?:\s+.*)?",
        r"\bgiudice\s+di\s+pace\b|\b204-?bis\b|\b150/2011\b|\bcodice\s+della\s+strada\b",
        "Opposizione a sanzione amministrativa",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO, deposit_role="atto_principale",
        fonte="estesa_settori_cds_ricorsi",
        evidence="ricorso al giudice di pace contro il verbale (art. 204-bis D.Lgs. 285/1992, art. 7 D.Lgs. 150/2011)",
    ),
    regola(
        "set_ordinanza_archiviazione_sanzione",
        r"ordinanza\s+(?:prefettizia\s+)?(?:motivata\s+)?di\s+archiviazione\s+(?:degli\s+atti|del\s+verbale|del\s+procedimento\s+sanzionatorio|del\s+ricorso\s+al\s+prefetto|ex\s+art\.?\s*(?:18|204))(?:\s+.*)?|ordinanza\s+prefettizia\s+di\s+archiviazione(?:\s+.*)?|provvedimento\s+di\s+archiviazione\s+(?:del\s+verbale|del\s+ricorso\s+al\s+prefetto)(?:\s+.*)?",
        r"\bprefett\w+\b|\b689\b|\b204\b|\bsanzione\s+amministrativa\b",
        "Ordinanza di archiviazione degli atti (sanzione amministrativa)",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ORDINANZA,
        fonte="estesa_settori_l689_procedimento",
        evidence="archiviazione dell'autorità competente (art. 18 L. 689/1981, art. 204 D.Lgs. 285/1992)",
    ),
    regola(
        "set_sospensione_patente",
        r"(?:provvedimento|ordinanza|decreto)\s+(?:prefettizi[oa]\s+)?di\s+sospensione\s+(?:provvisoria\s+)?(?:della\s+)?patente(?:\s+di\s+guida)?(?:\s+.*)?|sospensione\s+(?:provvisoria\s+)?della\s+patente\s+di\s+guida(?:\s+.*)?",
        r"\bpatente\b|\b218\b|\b223\b|\bprefett\w+\b",
        "Provvedimento di sospensione della patente di guida",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_cds_patente",
        evidence="sanzione accessoria della sospensione della patente (artt. 218 e 223 D.Lgs. 285/1992)",
    ),
    regola(
        "set_revoca_patente",
        r"(?:provvedimento|decreto|ordinanza)\s+(?:prefettizi[oa]\s+)?di\s+revoca\s+(?:della\s+)?patente(?:\s+di\s+guida)?(?:\s+.*)?|revoca\s+della\s+patente\s+di\s+guida(?:\s+.*)?",
        r"\bpatente\b|\b219\b|\bprefett\w+\b|\bmotorizzazion\w+\b",
        "Provvedimento di revoca della patente di guida",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_cds_patente",
        evidence="revoca della patente di guida (art. 219 D.Lgs. 285/1992)",
    ),
    regola(
        "set_revisione_patente",
        r"(?:provvedimento|disposizione|ordine)\s+di\s+revisione\s+(?:della\s+)?patente(?:\s+di\s+guida)?(?:\s+.*)?|revisione\s+della\s+patente\s+di\s+guida(?:\s+.*)?",
        r"\bpatente\b|\b128\b|\bvisita\s+medica\b|\besame\s+di\s+idoneit\w+\b|\bmotorizzazion\w+\b",
        "Provvedimento di revisione della patente di guida",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_cds_patente",
        evidence="revisione della patente con visita medica o esame di idoneità (art. 128 D.Lgs. 285/1992)",
    ),
    regola(
        "set_ritiro_patente",
        r"verbale\s+di\s+ritiro\s+(?:della\s+)?patente(?:\s+di\s+guida)?(?:\s+.*)?",
        r"\bpatente\b|\b21[68]\b|\b223\b|\britir\w+\b",
        "Verbale di ritiro della patente di guida",
        role="verbale_ufficio", section="provvedimenti", tipo=TipoDocumento.VERBALE, deposit_candidate=False,
        deposit_role="fuori_busta",
        fonte="estesa_settori_cds_patente",
        evidence="ritiro della patente da parte dell'agente accertatore (artt. 218 e 223 D.Lgs. 285/1992)",
    ),
    regola(
        "set_fermo_veicolo",
        r"verbale\s+di\s+fermo(?:\s+amministrativo)?(?:\s+del\s+veicolo)?(?:\s+.*)?|fermo\s+amministrativo\s+del\s+veicolo(?:\s+.*)?",
        r"\bveicol\w+\b|\b214\b|\bcustod\w+\b|\btarga\b",
        "Verbale di fermo amministrativo del veicolo",
        role="verbale_ufficio", section="provvedimenti", tipo=TipoDocumento.VERBALE, deposit_candidate=False,
        deposit_role="fuori_busta",
        fonte="estesa_settori_cds_veicolo",
        evidence="sanzione accessoria del fermo del veicolo (art. 214 D.Lgs. 285/1992)",
    ),
    regola(
        "set_sequestro_veicolo",
        r"verbale\s+di\s+sequestro\s+amministrativo(?:\s+del\s+veicolo)?(?:\s+.*)?|sequestro\s+amministrativo\s+del\s+veicolo(?:\s+.*)?",
        r"\bveicol\w+\b|\b213\b|\bconfisc\w+\b|\bcustod\w+\b",
        "Verbale di sequestro amministrativo del veicolo",
        role="verbale_ufficio", section="provvedimenti", tipo=TipoDocumento.VERBALE, deposit_candidate=False,
        deposit_role="fuori_busta",
        fonte="estesa_settori_cds_veicolo",
        evidence="sequestro cautelare in vista della confisca amministrativa (art. 213 D.Lgs. 285/1992)",
    ),
    regola(
        "set_comunicazione_dati_conducente",
        r"(?:comunicazione|dichiarazione)\s+(?:dei\s+)?dati\s+(?:del\s+)?conducente(?:\s+.*)?|(?:invito|richiesta)\s+(?:a\s+comunicare\s+i|di\s+comunicazione\s+dei)\s+dati\s+(?:del\s+)?conducente(?:\s+.*)?",
        r"\b126-?bis\b|\bconducent\w+\b|\bpatente\b",
        "Comunicazione dei dati del conducente (art. 126-bis C.d.S.)",
        role="atto_amministrativo", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_cds_dati_conducente",
        evidence="dati del conducente al momento della violazione (art. 126-bis, comma 2, D.Lgs. 285/1992)",
    ),
    regola(
        "set_decurtazione_punti",
        r"comunicazione\s+(?:di\s+|della\s+)?(?:decurtazione|variazione)\s+(?:dei\s+|del\s+)?punt(?:i|eggio)(?:\s+della\s+patente)?(?:\s+.*)?",
        r"\bpunt\w+\b|\b126-?bis\b|\bpatente\b",
        "Comunicazione di decurtazione dei punti della patente",
        role="atto_amministrativo", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_cds_dati_conducente",
        evidence="variazione del punteggio nell'anagrafe nazionale degli abilitati alla guida (art. 126-bis D.Lgs. 285/1992)",
    ),
    # ── Trasporti ──
    regola(
        "set_reclamo_enac",
        r"reclamo\s+(?:all.?\s*)?enac(?:\s+.*)?|segnalazione\s+(?:all.?\s*)?enac(?:\s+.*)?|reclamo\s+all.?\s*ente\s+nazionale\s+per\s+l.?\s*aviazione\s+civile(?:\s+.*)?",
        r"\b261/2004\b|\benac\b|\bvolo\b|\bvettore\b",
        "Reclamo all'ENAC (Reg. CE 261/2004)",
        role="corrispondenza_stragiudiziale", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_trasporto_aereo",
        evidence="reclamo all'organismo responsabile dell'applicazione del Reg. CE 261/2004 (art. 2 D.Lgs. 69/2006)",
    ),
    regola(
        "set_rapporto_irregolarita_bagaglio",
        r"rapporto\s+(?:di\s+)?irregolarit[aà]'?\s+(?:del\s+)?bagaglio(?:\s+.*)?|property\s+irregularity\s+report(?:\s+.*)?|pir(?:\s+bagaglio)?(?:\s+.*)?",
        r"\bbagagli\w*\b|\bvolo\b|\bvettore\b|\bmontreal\b",
        "Rapporto di irregolarità bagaglio (PIR)",
        role="documento_sinistro", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_trasporto_aereo",
        evidence="denuncia del danno o della perdita del bagaglio (art. 31 Convenzione di Montreal, L. 12/2004)",
    ),
    # ── Sanzioni amministrative L. 689/1981 ──
    regola(
        "set_processo_verbale_accertamento",
        r"processo\s+verbale\s+di\s+(?:accertamento|contestazione)(?:\s+.*)?",
        r"\b689\b|\bsanzione\s+amministrativa\b|\bviolazion\w+\b|\bcontestazion\w+\b",
        "Verbale di accertamento di violazione",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.VERBALE,
        fonte="estesa_settori_l689_procedimento",
        evidence="contestazione e notificazione della violazione (art. 14 L. 689/1981)",
    ),
    regola(
        "set_scritti_difensivi",
        r"scritti\s+difensivi(?:\s+.*)?|memoria\s+difensiva\s+(?:ex|ai\s+sensi\s+dell.?)\s*art\.?\s*18\s+(?:l\.?|legge)\s*(?:n\.?\s*)?689(?:/1981)?(?:\s+.*)?|(?:istanza|richiesta)\s+di\s+audizione(?:\s+personale)?(?:\s+ex\s+art\.?\s*18)?(?:\s+.*)?",
        r"\b689\b|\bart\.?\s*18\b|\bsanzion\w+\b|\bverbale\b",
        "Scritti difensivi (art. 18 L. 689/1981)",
        role="atto_difensivo", section="atti", tipo=TipoDocumento.MEMORIA,
        fonte="estesa_settori_l689_procedimento",
        evidence="scritti difensivi e richiesta di audizione entro trenta giorni (art. 18 L. 689/1981)",
    ),
    regola(
        "set_rateizzazione_sanzione",
        r"(?:istanza|richiesta)\s+di\s+(?:pagamento\s+rateale|rateizzazione|rateazione)\s+(?:della\s+|delle\s+)?sanzion[ei](?:\s+amministrativ[ae])?(?:\s+pecuniari[ae])?(?:\s+.*)?",
        r"\b26\b|\b202-?bis\b|\brat[ea]\w*\b|\bsanzion\w+\b",
        "Istanza di pagamento rateale della sanzione amministrativa",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO, deposit_role="allegato",
        fonte="estesa_settori_l689_procedimento",
        evidence="pagamento rateale della sanzione pecuniaria (art. 26 L. 689/1981, art. 202-bis D.Lgs. 285/1992)",
    ),
    # ── Professione forense ──
    regola(
        "set_esposto_disciplinare",
        r"esposto(?:\s+disciplinare)?\s+(?:al\s+consiglio\s+(?:dell.?\s*ordine|distrettuale\s+di\s+disciplina)|al\s+c\.?\s*o\.?\s*a\.?|al\s+c\.?\s*d\.?\s*d\.?|nei\s+confronti\s+dell.?\s*avv\w*\.?|contro\s+l.?\s*avv\w*\.?)(?:\s+.*)?|esposto\s+disciplinare(?:\s+.*)?",
        r"\bavv\w*\b|\bdeontolog\w+\b|\bdisciplin\w+\b|\bordine\s+degli\s+avvocati\b",
        "Esposto disciplinare nei confronti di un avvocato",
        role="atto_principale", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO, deposit_role="allegato",
        fonte="estesa_settori_l247_disciplina",
        evidence="esposto al consiglio dell'ordine trasmesso al consiglio distrettuale di disciplina (art. 50, comma 4, L. 247/2012)",
    ),
    regola(
        "set_invito_deduzioni_esposto",
        r"(?:comunicazione|avviso)\s+(?:di\s+|dell.?\s*)?(?:ricezione\s+(?:di\s+)?|presentazione\s+(?:di\s+)?)?esposto(?:\s+e\s+invito\s+a\s+(?:presentare\s+)?(?:deduzioni|dedurre))?(?:\s+.*)?|invito\s+a\s+(?:presentare\s+)?deduzioni(?:\s+.*)?|invito\s+a\s+dedurre(?:\s+.*)?",
        r"\besposto\b|\bdeduzion\w+\b|\bventi\s+giorni\b|\b50\b",
        "Comunicazione dell'esposto con invito a presentare deduzioni",
        role="atto_ufficio", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_l247_disciplina",
        evidence="notizia dell'esposto all'iscritto con invito a dedurre entro venti giorni (art. 50, comma 4, L. 247/2012)",
    ),
    regola(
        "set_capo_incolpazione",
        r"(?:comunicazione\s+(?:del\s+)?)?capo\s+d.?\s*incolpazione(?:\s+.*)?|comunicazione\s+di\s+(?:apertura|avvio)\s+del\s+procedimento\s+disciplinare(?:\s+.*)?",
        r"\bincolpat\w+\b|\baddebit\w+\b|\bconsiglio\s+distrettuale\s+di\s+disciplina\b|\b59\b",
        "Capo d'incolpazione del procedimento disciplinare forense",
        role="atto_ufficio", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_l247_disciplina",
        evidence="capo d'incolpazione approvato dal consiglio distrettuale di disciplina (art. 59, lett. a e b, L. 247/2012)",
    ),
    regola(
        "set_citazione_giudizio_disciplinare",
        r"(?:decreto\s+di\s+)?citazione\s+(?:a\s+)?giudizio\s+disciplinare(?:\s+.*)?|citazione\s+(?:a\s+)?giudizio\s+(?:dinanzi|davanti|innanzi)\s+al\s+consiglio\s+distrettuale\s+di\s+disciplina(?:\s+.*)?",
        r"\bincolpat\w+\b|\bdibattimento\b|\bconsiglio\s+distrettuale\s+di\s+disciplina\b|\b59\b",
        "Citazione a giudizio disciplinare",
        role="atto_ufficio", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO,
        fonte="estesa_settori_l247_disciplina",
        evidence="citazione dell'incolpato al dibattimento disciplinare (art. 59, lett. d, L. 247/2012)",
    ),
    regola(
        "set_memoria_disciplinare",
        r"(?:memoria\s+difensiva|deduzioni(?:\s+difensive)?|memoria)\s+(?:nel\s+procedimento\s+disciplinare|dell.?\s*incolpato|al\s+consiglio\s+distrettuale\s+di\s+disciplina|(?:in\s+riscontro\s+)?all.?\s*esposto)(?:\s+.*)?",
        r"\bincolpat\w+\b|\besposto\b|\bdisciplin\w+\b|\bdeontolog\w+\b",
        "Memoria difensiva nel procedimento disciplinare forense",
        role="atto_difensivo", section="atti", tipo=TipoDocumento.MEMORIA,
        fonte="estesa_settori_l247_disciplina",
        evidence="deduzioni e memorie dell'iscritto incolpato (artt. 50, comma 4, e 59, lett. b, L. 247/2012)",
    ),
    regola(
        "set_decisione_cdd",
        r"(?:decisione|sentenza|provvedimento)\s+(?:disciplinare\s+)?del\s+consiglio\s+distrettuale\s+di\s+disciplina(?:\s+.*)?|decisione\s+disciplinare(?:\s+.*)?",
        r"\bincolpat\w+\b|\bsanzion\w+\b|\bcensura\b|\bavvertiment\w+\b|\bsospension\w+\b|\bradiazion\w+\b|\bproscioglim\w+\b|\bdisciplin\w+\b",
        "Decisione del Consiglio distrettuale di disciplina",
        role="provvedimento", section="provvedimenti", tipo=TipoDocumento.SENTENZA,
        fonte="estesa_settori_l247_disciplina",
        evidence="decisione che definisce il procedimento disciplinare (artt. 59 e 61 L. 247/2012)",
    ),
    regola(
        "set_ricorso_cnf",
        r"ricorso\s+al\s+consiglio\s+nazionale\s+forense(?:\s+.*)?|ricorso\s+al\s+c\.?\s*n\.?\s*f\.?(?:\s+.*)?",
        r"\bconsiglio\s+nazionale\s+forense\b|\bcnf\b|\bc\.n\.f\.|\b61\b|\b36\b|\bdisciplin\w+\b|\bdeontolog\w+\b",
        "Ricorso al Consiglio nazionale forense",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO, deposit_role="atto_principale",
        fonte="estesa_settori_l247_disciplina",
        evidence="impugnazione delle decisioni disciplinari e in materia di albi (artt. 36 e 61 L. 247/2012)",
    ),
    regola(
        "set_sentenza_cnf",
        r"(?:sentenza|decisione)\s+del\s+consiglio\s+nazionale\s+forense(?:\s+.*)?|(?:sentenza|decisione)\s+(?:del\s+)?c\.?\s*n\.?\s*f\.?\s+n\.?(?:\s+.*)?",
        r"\bconsiglio\s+nazionale\s+forense\b|\bcnf\b|\bricors\w+\b|\bp\.?\s*q\.?\s*m\.?\b",
        "Sentenza del Consiglio nazionale forense",
        role="provvedimento", section="provvedimenti", tipo=TipoDocumento.SENTENZA,
        fonte="estesa_settori_l247_disciplina",
        evidence="pronuncia del CNF sui ricorsi disciplinari e in materia di albi (art. 36 L. 247/2012)",
    ),
    regola(
        "set_istanza_parere_congruita",
        r"(?:istanza|richiesta|domanda)\s+(?:di\s+)?(?:rilascio\s+(?:del\s+)?|opinamento\s+(?:della\s+)?)?(?:parere\s+(?:di\s+)?congruit[aà]'?|liquidazione\s+della\s+parcella\s+da\s+parte\s+del\s+consiglio\s+dell.?\s*ordine)(?:\s+.*)?|istanza\s+di\s+opinamento(?:\s+.*)?",
        r"\bparcell\w+\b|\bcompens\w+\b|\bcongruit\w+\b|\bconsiglio\s+dell.?\s*ordine\b",
        "Istanza di parere di congruità del compenso",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO, deposit_role="allegato", deposit_candidate=False,
        fonte="estesa_settori_l247_congruita",
        evidence="richiesta al consiglio dell'ordine del parere sulla liquidazione dei compensi (art. 29, comma 1, lett. l, L. 247/2012)",
    ),
    regola(
        "set_parere_congruita",
        r"parere\s+(?:di\s+)?congruit[aà]'?(?:\s+.*)?|parcella\s+(?:vistata|opinata)(?:\s+.*)?",
        r"\bcompens\w+\b|\bparcell\w+\b|\bconsiglio\s+dell.?\s*ordine\b|\bcongru\w+\b",
        "Parere di congruità del Consiglio dell'Ordine",
        role="documento_economico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_l247_congruita",
        evidence="parere del consiglio dell'ordine sulla liquidazione dei compensi (art. 29, comma 1, lett. l, L. 247/2012)",
    ),
    regola(
        "set_domanda_iscrizione_albo",
        r"domanda\s+(?:di\s+)?iscrizione\s+(?:all.?\s*albo\s+(?:degli\s+)?avvocati|all.?\s*albo\s+(?:del(?:l.?\s*|\s+)?)?ordine|nell.?\s*albo|all.?\s*albo)(?:\s+.*)?",
        r"\bavvocat\w+\b|\bconsiglio\s+dell.?\s*ordine\b|\b17\b|\babilitazion\w+\b",
        "Domanda di iscrizione all'albo degli avvocati",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_l247_albo",
        evidence="requisiti e domanda di iscrizione all'albo (art. 17 L. 247/2012)",
    ),
    regola(
        "set_domanda_iscrizione_praticanti",
        r"domanda\s+(?:di\s+)?iscrizione\s+(?:al\s+|nel\s+)?registro\s+(?:speciale\s+)?dei\s+praticanti(?:\s+avvocati)?(?:\s+.*)?",
        r"\bpratica\b|\btirocini\w+\b|\bpraticant\w+\b|\b41\b",
        "Domanda di iscrizione al registro dei praticanti avvocati",
        role="adempimento_studio", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_l247_albo",
        evidence="iscrizione al registro dei praticanti per il tirocinio professionale (artt. 17 e 41 L. 247/2012)",
    ),
    regola(
        "set_delibera_albo",
        r"delibera(?:zione)?\s+(?:del\s+consiglio\s+dell.?\s*ordine\s+)?di\s+(?:iscrizione|cancellazione|sospensione|reiscrizione)(?:\s+o\s+(?:iscrizione|cancellazione))?\s+(?:dall.?\s*|all.?\s*|nell.?\s*)albo(?:\s+.*)?|delibera(?:zione)?\s+di\s+cancellazione\s+dal\s+registro\s+dei\s+praticanti(?:\s+.*)?",
        r"\bavvocat\w+\b|\bavv\.|\bc\.?\s*o\.?\s*a\.?\b|\bconsiglio\s+dell.?\s*ordine\b|\b17\b|\biscritt\w+\b",
        "Delibera di iscrizione o cancellazione dall'albo",
        role="atto_amministrativo", section="provvedimenti", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_l247_albo",
        evidence="delibera di iscrizione o cancellazione dall'albo, reclamabile al CNF (artt. 17 e 36 L. 247/2012)",
    ),
    regola(
        "set_certificato_compiuta_pratica",
        r"certificato\s+di\s+compiut[ao]\s+(?:pratica|tirocinio)(?:\s+forense)?(?:\s+.*)?",
        r"\btirocini\w+\b|\bpratica\b|\bpraticant\w+\b|\b45\b",
        "Certificato di compiuto tirocinio forense",
        role="certificato", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="estesa_settori_l247_albo",
        evidence="certificato rilasciato dal consiglio dell'ordine al termine del tirocinio (art. 45 L. 247/2012)",
    ),
    # ── Spese di giustizia D.P.R. 115/2002 ──
    regola(
        "set_istanza_patrocinio_stato",
        r"(?:istanza|domanda)\s+(?:di\s+|per\s+l.?\s*)?ammissione\s+al\s+(?:patrocinio\s+a\s+spese\s+dello\s+stato|gratuito\s+patrocinio)(?:\s+.*)?|istanza\s+(?:di\s+)?(?:gratuito\s+patrocinio|patrocinio\s+a\s+spese\s+dello\s+stato)(?:\s+.*)?",
        _PATROCINIO + r"|\breddit\w+\b",
        "Istanza di ammissione al patrocinio a spese dello Stato",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO, deposit_role="allegato",
        fonte="estesa_settori_dpr115_patrocinio",
        evidence="istanza sottoscritta dall'interessato con dichiarazione dei redditi (artt. 78 e 79 D.P.R. 115/2002)",
    ),
    regola(
        "set_ammissione_patrocinio_stato",
        r"(?:decreto|delibera(?:zione)?|provvedimento)\s+di\s+ammissione\s+(?:anticipata\s+(?:e\s+provvisoria\s+)?)?al\s+(?:patrocinio\s+a\s+spese\s+dello\s+stato|gratuito\s+patrocinio)(?:\s+.*)?",
        _PATROCINIO + r"|\bammess\w+\b",
        "Provvedimento di ammissione al patrocinio a spese dello Stato",
        role="provvedimento", section="provvedimenti", tipo=TipoDocumento.DECRETO,
        fonte="estesa_settori_dpr115_patrocinio",
        evidence="ammissione del magistrato o, nel civile, del consiglio dell'ordine (artt. 96 e 126 D.P.R. 115/2002)",
    ),
    regola(
        "set_rigetto_patrocinio_stato",
        r"(?:decreto|delibera(?:zione)?|provvedimento)\s+di\s+(?:rigetto|inammissibilit[aà]'?|non\s+ammissione)\s+(?:dell.?\s*istanza\s+(?:di\s+ammissione\s+)?)?(?:al\s+|del\s+)?(?:patrocinio\s+a\s+spese\s+dello\s+stato|gratuito\s+patrocinio)(?:\s+.*)?",
        _PATROCINIO + r"|\brigett\w+\b|\binammissibil\w+\b",
        "Provvedimento di rigetto del patrocinio a spese dello Stato",
        role="provvedimento", section="provvedimenti", tipo=TipoDocumento.DECRETO,
        fonte="estesa_settori_dpr115_patrocinio",
        evidence="rigetto o inammissibilità dell'istanza di ammissione (artt. 96 e 126 D.P.R. 115/2002)",
    ),
    regola(
        "set_revoca_patrocinio_stato",
        r"(?:decreto|delibera(?:zione)?|provvedimento)\s+di\s+revoca\s+(?:dell.?\s*ammissione\s+|del\s+provvedimento\s+di\s+ammissione\s+)?(?:al\s+|del\s+)?(?:patrocinio\s+a\s+spese\s+dello\s+stato|gratuito\s+patrocinio)(?:\s+.*)?",
        _PATROCINIO + r"|\brevoc\w+\b|\b112\b|\b136\b",
        "Decreto di revoca del patrocinio a spese dello Stato",
        role="provvedimento", section="provvedimenti", tipo=TipoDocumento.DECRETO,
        fonte="estesa_settori_dpr115_patrocinio",
        evidence="revoca dell'ammissione (artt. 112 e 136 D.P.R. 115/2002)",
    ),
    regola(
        "set_istanza_liquidazione_ausiliario",
        r"(?:istanza|domanda|richiesta)\s+(?:di\s+)?liquidazione\s+(?:del\s+compenso\s+|delle\s+spettanze\s+|dell.?\s*onorario\s+)?(?:del\s+|dell.?\s*)?(?:c\.?\s*t\.?\s*u\.?|consulente\s+tecnico(?:\s+d.?\s*ufficio)?|perito|ausiliario|custode|interprete|traduttore)(?:\s+.*)?",
        r"\b115/2002\b|\b71\b|\b168\b|\bvacazion\w+\b|\bonorar\w+\b|\bcompens\w+\b",
        "Istanza di liquidazione del compenso dell'ausiliario del magistrato",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO, deposit_role="atto_principale",
        fonte="estesa_settori_dpr115_liquidazione",
        evidence="domanda di liquidazione degli ausiliari del magistrato a pena di decadenza (art. 71 D.P.R. 115/2002)",
    ),
    regola(
        "set_istanza_liquidazione_difensore",
        r"istanza\s+(?:di\s+)?liquidazione\s+(?:dei\s+|del\s+|degli\s+|delle\s+)?(?:compens[oi]|onorar[io]|spettanze)(?:\s+(?:e\s+(?:delle\s+)?spese\s+)?(?:del\s+difensore|professional[ei]))?(?:\s+.*)?",
        r"\bpatrocinio\s+a\s+spese\s+dello\s+stato\b|\bgratuito\s+patrocinio\b|\b115/2002\b|\bdifensor\w+\b",
        "Istanza di liquidazione dei compensi del difensore (patrocinio a spese dello Stato)",
        role="istanza", section="atti", tipo=TipoDocumento.ATTO_GIUDIZIARIO, deposit_role="atto_principale",
        fonte="estesa_settori_dpr115_liquidazione",
        evidence="liquidazione di onorario e spese del difensore con decreto di pagamento (artt. 82 e 83 D.P.R. 115/2002)",
    ),
    regola(
        "set_decreto_pagamento",
        r"decreto\s+di\s+pagamento(?:\s+.*)?|decreto\s+di\s+liquidazione\s+(?:dei\s+compensi|del\s+compenso|delle\s+spettanze|dell.?\s*onorario)(?:\s+.*)?",
        r"\b115/2002\b|\b8[23]\b|\b168\b|\bpatrocinio\s+a\s+spese\s+dello\s+stato\b|\bausiliar\w+\b",
        "Decreto di pagamento (D.P.R. 115/2002)",
        role="provvedimento", section="provvedimenti", tipo=TipoDocumento.DECRETO,
        fonte="estesa_settori_dpr115_liquidazione",
        evidence="decreto di pagamento motivato del magistrato (artt. 82 e 168 D.P.R. 115/2002)",
    ),
    regola(
        "set_opposizione_decreto_pagamento",
        r"(?:ricorso\s+in\s+|atto\s+di\s+)?opposizione\s+(?:al|avverso\s+il|contro\s+il)\s+decreto\s+di\s+(?:pagamento|liquidazione)(?:\s+.*)?|opposizione\s+ex\s+art\.?\s*170\s+d\.?\s*p\.?\s*r\.?\s*(?:n\.?\s*)?115(?:/2002)?(?:\s+.*)?",
        r"\b170\b|\b115/2002\b|\b150/2011\b|\bdecreto\s+di\s+(?:pagamento|liquidazione)\b",
        "Opposizione al decreto di pagamento (art. 170 D.P.R. 115/2002)",
        role="atto_principale", section="atti", tipo=TipoDocumento.RICORSO, deposit_role="atto_principale",
        fonte="estesa_settori_dpr115_opposizione",
        evidence="opposizione al decreto di pagamento con il rito dell'art. 15 D.Lgs. 150/2011 (art. 170 D.P.R. 115/2002)",
    ),
    regola(
        "set_invito_pagamento_contributo",
        r"invito\s+al\s+pagamento\s+(?:del(?:l.?\s*integrazione\s+del)?\s+)?contributo\s+unificato(?:\s+.*)?|invito\s+al\s+pagamento\s+ex\s+art\.?\s*248(?:\s+.*)?",
        r"\b248\b|\bcontributo\s+unificato\b|\b115/2002\b|\b16\b",
        "Invito al pagamento del contributo unificato",
        role="atto_ufficio", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_dpr115_recupero",
        evidence="invito della cancelleria al pagamento o all'integrazione del contributo (art. 248 D.P.R. 115/2002)",
    ),
    regola(
        "set_invito_pagamento_spese_giustizia",
        r"invito\s+al\s+pagamento\s+(?:delle\s+)?spese\s+(?:di\s+giustizia|processuali|di\s+mantenimento|del\s+procedimento)(?:\s+.*)?|invito\s+al\s+pagamento\s+ex\s+art\.?\s*212(?:\s+.*)?|recupero\s+(?:delle\s+)?spese\s+di\s+giustizia(?:\s+.*)?",
        r"\b212\b|\b115/2002\b|\bruolo\b|\bspese\s+(?:di\s+giustizia|processuali)\b",
        "Invito al pagamento delle spese di giustizia",
        role="atto_ufficio", section="comunicazioni", tipo=TipoDocumento.COMUNICAZIONE,
        fonte="estesa_settori_dpr115_recupero",
        evidence="invito al pagamento con avvertenza dell'iscrizione a ruolo (art. 212 D.P.R. 115/2002)",
    ),
)
