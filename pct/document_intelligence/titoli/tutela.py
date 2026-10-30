"""Istanze in materia di persone, minori e tutela (c.c., libro I; c.p.c., artt. 473-bis ss. e 737 ss.)."""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_PERSONE = r"\bminor\w+\b|\bgenitor\w+\b|\bfigli\w*\b|\btutor\w+\b|\bbeneficiari\w+\b|\bamministrator\w+\s+di\s+sostegno\b|\bincapac\w+\b"


def _istanza(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
             role: str = "istanza", tipo: TipoDocumento = TipoDocumento.MEMORIA):
    return regola(id, titolo, conferma, label, role=role, section="atti", tipo=tipo, fonte=fonte,
                  deposit_role="atto_principale", evidence=evidence)


REGOLE = (
    _istanza(
        "istanza_giudice_tutelare",
        r"(?:istanz[ae]|ricorso)\s+al\s+giudice\s+tutelare(?:\s+.*)?|"
        r"(?:istanza|ricorso)\s+(?:di|per)\s+(?:l.?\s*)?autorizzazione\s+(?:all.?\s*|alla\s+|ad\s+)(?!.*\b(?:liquidator|curator|commissari)\w*)(?:accettazione|rinuncia|riscossione|vendita|atto|atti|divisione|compimento).+",
        _PERSONE + r"|\bgiudice\s+tutelare\b|\bautorizza\w+\b|\b3(?:20|7[45])\b",
        "Istanza al giudice tutelare",
        "titolo dell'istanza e autorizzazione agli atti di straordinaria amministrazione (artt. 320, 374, 375 e 411 c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _istanza(
        "istanza_amministrazione_sostegno",
        r"istanza\s+di\s+(?:modifica|revoca|integrazione)\s+(?:del(?:l.?\s*)?\s*)?amministrazione\s+di\s+sostegno(?:\s+.*)?|"
        r"(?:istanza\s+di\s+)?rendiconto\s+(?:dell.?\s*)?amministrazione\s+di\s+sostegno(?:\s+.*)?|rendiconto\s+(?:annuale\s+)?dell.?\s*amministratore\s+di\s+sostegno(?:\s+.*)?",
        r"\bamministra\w+\s+di\s+sostegno\b|\bbeneficiari\w+\b|\brendicont\w+\b|\b40[57]\b|\b413\b",
        "Istanza nell'amministrazione di sostegno",
        "titolo dell'atto e gestione dell'amministrazione di sostegno (artt. 405, 411 e 413 c.c.)",
        fonte="normattiva_cc_amministrazione_sostegno",
    ),
    _istanza(
        "istanza_curatore_speciale_minore",
        r"istanza\s+(?:di|per\s+la)\s+nomina\s+del\s+curatore\s+speciale(?:\s+del\s+minore)?(?:\s+.*)?",
        _PERSONE + r"|\bcurator\w+\s+special\w+\b",
        "Istanza di nomina del curatore speciale del minore",
        "titolo dell'istanza e conflitto di interessi del minore (art. 473-bis.8 c.p.c.)",
        fonte="normattiva_cpc_famiglia_473_bis",
    ),
    _istanza(
        "istanza_ascolto_minore",
        r"istanza\s+(?:di|per\s+l.?\s*)\s*ascolto\s+del\s+minore(?:\s+.*)?",
        _PERSONE + r"|\bascolt\w+\b",
        "Istanza di ascolto del minore",
        "titolo dell'istanza e diritto del minore di essere ascoltato (artt. 473-bis.4 e 473-bis.5 c.p.c.)",
        fonte="normattiva_cpc_famiglia_473_bis",
    ),
    _istanza(
        "istanza_provvedimenti_urgenti_famiglia",
        r"istanza\s+di\s+provvedimenti\s+(?:urgenti|indifferibili|temporanei)(?:\s+(?:familiari|in\s+materia\s+di\s+famiglia))?(?:\s+.*)?",
        _PERSONE + r"|\bconiug\w+\b|\burgen\w+\b|\bassegno\b",
        "Istanza di provvedimenti urgenti in materia di famiglia",
        "titolo dell'istanza e provvedimenti indifferibili (art. 473-bis.15 c.p.c.)",
        fonte="normattiva_cpc_famiglia_473_bis",
    ),
    _istanza(
        "istanza_responsabilita_genitoriale",
        r"istanza\s+(?:per|di)\s+(?:l.?\s*)?(?:autorizzazione\s+al\s+trasferimento\s+(?:di\s+|della\s+)?residenza|rilascio\s+(?:del\s+)?passaporto|risoluzione\s+del\s+contrasto).*",
        _PERSONE + r"|\bresidenz\w+\b|\bpassaport\w+\b|\b316\b|\b337-?ter\b",
        "Istanza in materia di responsabilità genitoriale",
        "titolo dell'istanza e contrasto fra i genitori su questioni di particolare importanza (artt. 316 e 337-ter c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _istanza(
        "istanza_inventario",
        r"istanza\s+(?:per\s+la\s+formazione\s+(?:del(?:l.?\s*)?\s*)?|di\s+)inventario(?:\s+.*)?|ricorso\s+per\s+(?:la\s+)?redazione\s+(?:dell.?\s*)?inventario(?:\s+.*)?",
        r"\binventari\w+\b|\bered\w+\b|\bbeni\b|\b769\b|\b484\b",
        "Istanza per la formazione dell'inventario",
        "titolo dell'istanza e inventario dei beni ereditari (art. 769 c.p.c.; art. 484 c.c.)",
        fonte="normattiva_cc_successioni",
    ),
    _istanza(
        "curatore_eredita_giacente",
        r"ricorso\s+per\s+(?:la\s+)?nomina\s+del\s+curatore\s+(?:dell.?\s*)?eredit[aà]\s+giacente(?:\s+.*)?",
        r"\beredit\w+\s+giacent\w+\b|\bcurator\w+\b|\b528\b",
        "Ricorso per nomina del curatore dell'eredità giacente",
        "titolo del ricorso ed eredità non accettata (art. 528 c.c.)",
        fonte="normattiva_cc_successioni", role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
    _istanza(
        "ricorso_decadenza_responsabilita",
        r"ricorso\s+per\s+(?:la\s+)?(?:decadenza|limitazione)\s+(?:dalla|della)\s+responsabilit[aà]\s+genitoriale(?:\s+.*)?",
        _PERSONE + r"|\bdecadenz\w+\b|\b33[03]\b",
        "Ricorso in materia di responsabilità genitoriale",
        "titolo del ricorso e condotta pregiudizievole del genitore (artt. 330 e 333 c.c.)",
        fonte="normattiva_codice_civile", role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
    _istanza(
        "ordine_protezione",
        r"ricorso\s+per\s+(?:l.?\s*)?ordine\s+di\s+protezione(?:\s+.*)?",
        r"\babus\w+\b|\bviolenz\w+\b|\bprotezion\w+\b|\b342-?bis\b|\bfamiliar\w+\b",
        "Ricorso per ordine di protezione",
        "titolo del ricorso e abusi familiari (art. 342-bis c.c.; art. 473-bis.69 c.p.c.)",
        fonte="normattiva_cpc_famiglia_473_bis", role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
    _istanza(
        "volontaria_giurisdizione",
        r"ricorso\s+(?:in\s+(?:camera\s+di\s+consiglio|volontaria\s+giurisdizione)|ex\s+art\.?\s*737)(?:\s+.*)?|volontaria\s+giurisdizione(?:\s+.*)?",
        r"\bcamera\s+di\s+consiglio\b|\b737\b|\bdecreto\b|\bricorrent\w+\b",
        "Ricorso di volontaria giurisdizione",
        "titolo del ricorso e procedimento in camera di consiglio (artt. 737 ss. c.p.c.)",
        fonte="normattiva_cpc", role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
    _istanza(
        "reclamo_famiglia",
        r"reclamo(?:\s*/\s*appello)?\s+in\s+materia\s+di\s+famiglia(?:\s+.*)?|reclamo\s+ex\s+art\.?\s*473-?bis\.?\s*24(?:\s+.*)?",
        _PERSONE + r"|\breclam\w+\b|\bcorte\s+d.?\s*appello\b",
        "Reclamo in materia di famiglia",
        "titolo del reclamo e provvedimenti temporanei o definitivi (artt. 473-bis.24 e 473-bis.30 c.p.c.)",
        fonte="normattiva_cpc_famiglia_473_bis", role="atto_principale", tipo=TipoDocumento.RICORSO,
    ),
)

__all__ = ["REGOLE"]
