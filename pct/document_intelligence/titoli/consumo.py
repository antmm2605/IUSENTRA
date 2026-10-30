"""Tutela del consumatore, protezione dei dati e contenuti digitali.

Fonti: D.Lgs. 206/2005 (Codice del consumo), Reg. UE 2016/679 (GDPR),
c.p. art. 595 (diffamazione). Il reclamo al Garante e l'informativa restano in `studio`.
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_CONSUMATORE = r"\bconsumator\w+\b|\bprofessionist\w+\b|\bvenditor\w+\b|\bgaranzi\w+\b|\b206/2005\b|\bcodice\s+del\s+consumo\b"
_DATI = r"\bdati\s+personali\b|\binteressat\w+\b|\btitolare\s+del\s+trattamento\b|\bgdpr\b|\b679\b|\btrattament\w+\b"


def _lettera(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
             role: str = "corrispondenza_stragiudiziale", section: str = "comunicazioni",
             tipo: TipoDocumento = TipoDocumento.COMUNICAZIONE, deposit_role: str = "allegato"):
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, evidence=evidence)


REGOLE = (
    _lettera(
        "reclamo_consumatore",
        r"reclamo\s+(?:per\s+(?:il\s+)?trasporto\s+(?:aereo|ferroviario|marittimo)|al\s+(?:vettore|venditore|professionista)|per\s+(?:ritardo|cancellazione)\s+(?:del\s+)?volo).*|"
        r"richiesta\s+(?:di\s+)?(?:rimborso|risarcimento|compensazione)\s+(?:per\s+)?(?:(?:il\s+)?pacchetto\s+turistico|acquisto\s+difettoso|volo|ritardo|cancellazione|bene\s+difettoso).*|"
        r"denuncia\s+(?:del\s+)?difetto\s+di\s+conformit[aà](?:\s+.*)?",
        _CONSUMATORE + r"|\bvettor\w+\b|\bvol[oi]\b|\bpasseggero\b|\brimbors\w+\b|\bdifett\w+\b|\b261/2004\b",
        "Reclamo del consumatore",
        "titolo del reclamo e diritti del consumatore verso il professionista (artt. 128-135 D.Lgs. 206/2005)",
        fonte="normattiva_codice_consumo_206_2005",
    ),
    _lettera(
        "conciliazione_paritetica",
        r"(?:invito|domanda|istanza)\s+(?:a|di)\s+conciliazione\s+paritetica(?:\s+.*)?",
        _CONSUMATORE + r"|\bparitetic\w+\b|\bconcilia\w+\b",
        "Domanda di conciliazione paritetica",
        "titolo della domanda e procedura ADR di consumo (art. 141 D.Lgs. 206/2005)",
        fonte="normattiva_codice_consumo_206_2005",
    ),
    _lettera(
        "clausole_vessatorie",
        r"(?:atto|azione|ricorso|diffida)\s+(?:su|in\s+materia\s+di|per\s+(?:l.?\s*accertamento\s+di\s+)?)\s*clausole\s+vessatorie(?:\s+.*)?",
        _CONSUMATORE + r"|\bvessatori\w+\b|\b3[3-7]\b|\bsquilibrio\b",
        "Atto in materia di clausole vessatorie",
        "titolo dell'atto e squilibrio contrattuale a danno del consumatore (artt. 33-37 D.Lgs. 206/2005)",
        fonte="normattiva_codice_consumo_206_2005", role="atto_principale", section="atti",
        tipo=TipoDocumento.CITAZIONE, deposit_role="atto_principale",
    ),
    _lettera(
        "richiesta_diritti_gdpr",
        r"richiesta\s+(?:di\s+)?(?:esercizio\s+dei\s+diritti(?:\s+(?:dell.?\s*interessato|gdpr|privacy))?|accesso\s+ai\s+dati\s+personali|cancellazione\s+dei\s+dati|deindicizzazione).*|"
        r"istanza\s+(?:ex\s+)?art\.?\s*(?:15|17|21)\s+(?:gdpr|reg\.?.*)|richiesta\s+di\s+rimozione\s+(?:di\s+)?contenuti(?:\s+.*)?",
        _DATI + r"|\bdeindicizz\w+\b|\boblio\b|\brimozion\w+\b",
        "Richiesta di esercizio dei diritti dell'interessato",
        "titolo della richiesta e diritti di accesso, cancellazione e opposizione (artt. 15-22 Reg. UE 2016/679)",
        fonte="eurlex_gdpr",
    ),
    _lettera(
        "riscontro_istanza_privacy",
        r"riscontro\s+(?:a(?:ll.?\s*)?\s*)?(?:istanza|richiesta)\s+(?:privacy|di\s+esercizio\s+dei\s+diritti|ex\s+art\.?\s*1[5-9]).*",
        _DATI,
        "Riscontro all'istanza dell'interessato",
        "titolo del riscontro e termine di un mese per la risposta (art. 12 Reg. UE 2016/679)",
        fonte="eurlex_gdpr",
    ),
    _lettera(
        "violazione_dati",
        r"(?:contestazione|notifica|comunicazione)\s+(?:di\s+|della\s+)?(?:data\s+breach|violazione\s+dei\s+dati(?:\s+personali)?)(?:\s+.*)?",
        _DATI + r"|\bbreach\b|\bviolazion\w+\b|\b3[34]\b",
        "Comunicazione di violazione dei dati personali",
        "titolo della comunicazione e violazione dei dati (artt. 33 e 34 Reg. UE 2016/679)",
        fonte="eurlex_gdpr",
    ),
    _lettera(
        "contestazione_contenuti_diffamatori",
        r"(?:contestazione|diffida)\s+(?:di|per)\s+(?:recensioni|contenuti|pubblicazioni)\s+diffamatori[ei](?:\s+.*)?",
        r"\bdiffamator\w+\b|\breputazion\w+\b|\b595\b|\brecension\w+\b|\brimozion\w+\b",
        "Contestazione di contenuti diffamatori",
        "titolo della contestazione e lesione della reputazione (art. 595 c.p.; art. 2043 c.c.)",
        fonte="normattiva_codice_penale",
    ),
)

__all__ = ["REGOLE"]
