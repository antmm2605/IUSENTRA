"""Documenti comuni a ogni fascicolo: identità, certificati, visure, estratti."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

CODICE_FISCALE = r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b"

REGOLE = (
    regola(
        "dichiarazione_sostitutiva",
        r"dichiarazione\s+sostitutiva(?:\s+.*)?|autocertificazione(?:\s+.*)?",
        r"\b445\b|\bdichiara\b|\bconsapevole\b|\bsanzioni\s+penali\b",
        "Dichiarazione sostitutiva (D.P.R. 445/2000)",
        role="dichiarazione_sostitutiva", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_445_2000_documentazione_amministrativa",
        evidence="titolo della dichiarazione e responsabilità del dichiarante (artt. 46 e 47 D.P.R. 445/2000)",
    ),
    regola(
        "documento_identita",
        r"carta\s+d.?\s*identit[aà](?:\s+.*)?|passaporto(?:\s+.*)?|patente\s+di\s+guida(?:\s+.*)?|permesso\s+di\s+soggiorno(?:\s+.*)?|carta\s+di\s+soggiorno(?:\s+.*)?",
        r"\bnat[oa]\s+(?:il|a)\b|\bscadenza\b|\bcittadinanza\b|\bcognome\b|\bdata\s+di\s+nascita\b",
        "Documento d'identità",
        role="documento_identita", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_445_2000_documentazione_amministrativa",
        evidence="titolo del documento e dati anagrafici del titolare (art. 35 D.P.R. 445/2000)",
    ),
    regola(
        "tessera_sanitaria",
        r"tessera\s+sanitaria(?:\s+.*)?|codice\s+fiscale",
        CODICE_FISCALE,
        "Tessera sanitaria / codice fiscale",
        role="documento_identita", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_605_1973_codice_fiscale",
        evidence="titolo della tessera e codice fiscale nel formato ufficiale (art. 2 D.P.R. 605/1973)",
    ),
    regola(
        "certificato_anagrafico",
        r"certificat[oi]\s+(?:di\s+|contestuale\s+)?(?:residenza|stato\s+di\s+famiglia|nascita|matrimonio|morte|cittadinanza|stato\s+libero|esistenza\s+in\s+vita)(?:\s+.*)?|certificato\s+anagrafico(?:\s+.*)?|estratto\s+(?:dell.?\s*atto\s+|per\s+riassunto\s+)?di\s+(?:nascita|matrimonio|morte)(?:\s+.*)?",
        r"\bcomune\s+di\b|\banagraf\w*\b|\bufficiale\b|\bsi\s+certifica\b|\bstato\s+civile\b",
        "Certificato anagrafico",
        role="certificato_anagrafico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_dpr_445_2000_documentazione_amministrativa",
        evidence="titolo del certificato e ufficio anagrafico emittente (art. 40 D.P.R. 445/2000)",
    ),
    regola(
        "visura_camerale",
        r"visura\s+(?:ordinaria|storica|camerale)(?:\s+.*)?|registro\s+(?:delle\s+)?imprese(?:\s+.*)?",
        r"\bcamera\s+di\s+commercio\b|\bn\.?\s*iscrizione\b|\bsede\s+legale\b|\brea\b",
        "Visura camerale",
        role="visura_camerale", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_civile",
        evidence="titolo della visura e registro delle imprese (art. 2188 c.c.)",
    ),
    regola(
        "visura_ipotecaria",
        r"visura\s+ipotecaria(?:\s+.*)?|ispezione\s+ipotecaria(?:\s+.*)?|certificato\s+ipotecario(?:\s+.*)?",
        r"\bconservatoria\b|\bformalit\w+\b|\bipotec\w+\b|\btrascrizion\w+\b",
        "Visura ipotecaria",
        role="visura", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_civile",
        evidence="titolo della visura e formalità ipotecarie (art. 2673 c.c.)",
    ),
    regola(
        "estratto_conto",
        r"estratto\s+conto(?:\s+.*)?",
        r"\bsaldo\b|\bconto\s+corrente\b|\bintestatari\w*\b|\bmovimenti\b",
        "Estratto conto",
        role="estratto_conto", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_civile",
        evidence="titolo dell'estratto e movimenti del conto (art. 1832 c.c.)",
    ),
    regola(
        "bolletta_utenza",
        r"bolletta(?:\s+.*)?|fattura\s+(?:gas|luce|energia|acqua|telefonica)(?:\s+.*)?",
        r"\bkwh\b|\bconsum\w+\b|\bfornitur\w+\b|\butenz\w+\b|\bpod\b|\bpdr\b",
        "Bolletta di utenza",
        role="documento_economico", section="allegati", tipo=TipoDocumento.ALLEGATO,
        fonte="normattiva_codice_consumo_206_2005",
        evidence="titolo della bolletta e dati della fornitura",
    ),
)

__all__ = ["CODICE_FISCALE", "REGOLE"]
