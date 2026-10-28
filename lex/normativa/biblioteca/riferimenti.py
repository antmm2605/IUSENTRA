"""Dalla chiave di un atto, come la usano le schede dei modelli d'atto, alla fonte ufficiale da cui acquisirlo.

Chiavi riconosciute (stesse convenzioni della biblioteca ``codici_leggi.sqlite``):
  legge_N_AAAA, dlgs_N_AAAA, dpr_N_AAAA, dl_N_AAAA, rd_N_AAAA, lcost_N_AAAA -> URN NIR per Normattiva (anno senza data:
  il risolutore ``uri-res/N2Ls`` di Normattiva accetta anno e numero);
  reg_ue_AAAA_N -> CELEX 3AAAARNNNN per l'Ufficio delle pubblicazioni dell'UE.
Ogni altra chiave (codici con nome proprio, forme N/AAAA senza tipo) non si deduce: resta da indicare a mano, mai
indovinata.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TIPI_NIR = {
    "legge": "legge",
    "dlgs": "decreto.legislativo",
    "dpr": "decreto.del.presidente.della.repubblica",
    "dl": "decreto.legge",
    "rd": "regio.decreto",
    "lcost": "legge.costituzionale",
}


# Denominazioni letterali riscontrate negli XML primari; non dedotte dai numeri.
PARTIZIONI_CODICI = {
    "codice_civile": "CODICE CIVILE",
    "preleggi": "Disposizioni sulla legge in generale",
    "12/1941": "Ordinamento giudiziario",
    "318/1942": "Disposizioni per l'attuazione del Codice Civile e disposizioni transitorie",
    "1368/1941": "DISPOSIZIONI DI ATTUAZIONE DEL CODICE DI PROCEDURA CIVILE",
    "175/2024": "Allegato",
    "cpa_norme_attuazione": "Allegato 2 Norme di attuazione",
    "cpa_norme_transitorie": "Allegato 3 Norme transitorie",
    "cpa_norme_coordinamento": "Allegato 4 Norme di coordinamento e abrogazioni ",
    "codice_procedura_civile": "CODICE DI PROCEDURA CIVILE",
    "codice_penale": "Codice Penale",
    "codice_processo_amministrativo": "Allegato 1 Codice del processo amministrativo",
}


@dataclass(frozen=True)
class FonteAtto:
    chiave: str
    tipo: str  # "normattiva" | "ue" | "non_deducibile"
    urn: str = ""
    celex: str = ""
    motivo: str = ""


def fonte_per_chiave(chiave: str) -> FonteAtto:
    c = str(chiave or "").strip().lower()
    # Codici nominati: identita esplicite gia usate dal lettore ufficiale.
    from lex.testi_ufficiali import CODICI

    short = {"codice_civile":"cc","codice_procedura_civile":"cpc","codice_penale":"cp",
             "codice_procedura_penale":"cpp","costituzione":"cost","preleggi":"cc"}.get(c)
    if short:
        official = next(x for x in CODICI if x.chiave == short)
        urn = official.urn.replace("urn:nir:presidente.repubblica:decreto:","urn:nir:stato:decreto.del.presidente.della.repubblica:")
        return FonteAtto(c,"normattiva",urn=urn)

    m = re.fullmatch(r"(legge|dlgs|dpr|dl|rd|lcost)_(\d+)_(\d{4})", c)
    if m:
        tipo, numero, anno = m.groups()
        return FonteAtto(c, "normattiva", urn=f"urn:nir:stato:{TIPI_NIR[tipo]}:{anno};{int(numero)}")
    m = re.fullmatch(r"reg_ue_(\d{4})_(\d+)", c)
    if m:
        anno, numero = m.groups()
        return FonteAtto(c, "ue", celex=f"3{anno}R{int(numero):04d}")
    return FonteAtto(c, "non_deducibile", motivo="chiave senza tipo e numero riconoscibili: indicare la fonte ufficiale")
