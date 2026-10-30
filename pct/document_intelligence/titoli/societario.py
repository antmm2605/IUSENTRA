"""Diritto societario, commerciale e bancario: atti della vita sociale e contenzioso d'impresa e bancario.

Fonti: c.c., libro V (società) e artt. 2598 ss. (concorrenza sleale);
D.Lgs. 385/1993 (TUB). Le azioni giudiziali sono atti di citazione: qui si
riconoscono quando il titolo stesso dichiara l'azione.
"""

from __future__ import annotations

from pct.fascicoli import TipoDocumento

from ._modello import regola

_SOCIETA = r"\bsociet\w+\b|\bsoci[oa]?\b|\bassemble\w+\b|\bamministrator\w+\b|\bs\.?\s*r\.?\s*l\.?\b|\bs\.?\s*p\.?\s*a\.?\b"
_BANCA = r"\bbanc\w+\b|\bconto\s+corrente\b|\bistitut\w+\s+di\s+credito\b|\bintermediari\w+\b|\btub\b|\b385/1993\b"


def _atto(id: str, titolo: str, conferma: str, label: str, evidence: str, *, fonte: str,
          role: str = "atto_principale", section: str = "atti", tipo: TipoDocumento = TipoDocumento.CITAZIONE,
          deposit_role: str = "atto_principale", deposit_candidate: bool = True):
    return regola(id, titolo, conferma, label, role=role, section=section, tipo=tipo, fonte=fonte,
                  deposit_role=deposit_role, deposit_candidate=deposit_candidate, evidence=evidence)


REGOLE = (
    _atto(
        "azione_responsabilita_amministratori",
        r"(?:atto\s+di\s+citazione\s+per\s+|azione\s+(?:sociale\s+)?di\s+)responsabilit[aà]\s+(?:(?:contro|nei\s+confronti)\s+(?:de)?gli\s+|degli\s+)?(?:amministratori|organi\s+sociali|sindaci).*|"
        r"atto\s+per\s+responsabilit[aà]\s+(?:degli\s+)?organi\s+sociali(?:\s+.*)?",
        _SOCIETA + r"|\b239[2-5]\b|\b2476\b",
        "Azione di responsabilità contro gli amministratori",
        "titolo dell'atto e responsabilità degli amministratori (artt. 2392-2395 e 2476 c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "esclusione_recesso_socio",
        r"(?:azione|opposizione|impugnazione)\s+(?:di|alla|della|avverso\s+la)\s+(?:esclusione|delibera\s+di\s+esclusione)\s+(?:del\s+)?socio(?:\s+.*)?|"
        r"(?:azione|dichiarazione|atto)\s+di\s+recesso\s+(?:del\s+)?socio(?:\s+.*)?",
        _SOCIETA + r"|\brecess\w+\b|\besclusion\w+\b|\b2437\b|\b2473\b|\b2287\b",
        "Atto in materia di recesso o esclusione del socio",
        "titolo dell'atto e uscita del socio dalla società (artt. 2287, 2437, 2473 e 2473-bis c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "impugnazione_bilancio",
        r"impugnazione\s+(?:della\s+delibera\s+di\s+approvazione\s+)?del\s+bilancio(?:\s+.*)?",
        _SOCIETA + r"|\bbilanci\w+\b|\b2434-?bis\b",
        "Impugnazione del bilancio",
        "titolo dell'atto e invalidità della delibera di approvazione del bilancio (art. 2434-bis c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "impugnazione_delibera_societaria",
        r"impugnazione\s+(?:di\s+|della\s+)?delibera(?:zione)?\s+(?:assembleare\s+)?(?:di\s+)?(?:s\.?\s*r\.?\s*l\.?|s\.?\s*p\.?\s*a\.?|societ[aà]|sociale|dell.?\s*assemblea\s+dei\s+soci)(?:\s+.*)?",
        _SOCIETA + r"|\b2377\b|\b2479-?ter\b",
        "Impugnazione di delibera societaria",
        "titolo dell'atto e invalidità della delibera dei soci (artt. 2377 e 2479-ter c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "convocazione_assemblea",
        r"(?:avviso\s+di\s+)?convocazione\s+(?:di|dell.?\s*)\s*assemblea(?:\s+(?:dei\s+soci|ordinaria|straordinaria))?(?:\s+.*)?",
        r"\bordine\s+del\s+giorno\b|\bassemble\w+\b|\bsoci\b|\bcondomin\w+\b|\bconvoca\w+\b",
        "Convocazione di assemblea",
        "titolo dell'avviso e ordine del giorno (art. 2366 c.c.; art. 66 disp. att. c.c.)",
        fonte="normattiva_codice_civile", role="corrispondenza", section="comunicazioni",
        tipo=TipoDocumento.COMUNICAZIONE, deposit_role="allegato",
    ),
    _atto(
        "verbale_assemblea_soci",
        r"verbale\s+(?:di|dell.?\s*)\s*assemblea\s+(?:(?:ordinaria|straordinaria)\s+)?(?:dei\s+soci|totalitaria)(?:\s+.*)?|verbale\s+del\s+consiglio\s+di\s+amministrazione(?:\s+.*)?",
        r"\bsoci\b|\bsociet\w+\b|\bs\.r\.l\.|\bs\.p\.a\.|\bcapitale\s+sociale\b|\bconsiglio\s+di\s+amministrazione\b",
        "Verbale di assemblea societaria",
        "titolo del verbale e deliberazioni dei soci o del consiglio (artt. 2375 e 2479-bis c.c.)",
        fonte="normattiva_codice_civile", role="verbale_societario", section="allegati",
        tipo=TipoDocumento.VERBALE, deposit_role="allegato",
    ),
    _atto(
        "richiesta_libri_sociali",
        r"richiesta\s+di\s+(?:esibizione|consultazione|accesso\s+ai)\s+(?:dei\s+)?(?:libri|documenti)\s+social[ei](?:\s+.*)?",
        _SOCIETA + r"|\blibri\s+social\w+\b|\b2476\b|\b2261\b",
        "Richiesta di consultazione dei libri sociali",
        "titolo della richiesta e diritto di controllo del socio (artt. 2261 e 2476, secondo comma, c.c.)",
        fonte="normattiva_codice_civile", role="corrispondenza_stragiudiziale", section="comunicazioni",
        tipo=TipoDocumento.COMUNICAZIONE, deposit_role="allegato",
    ),
    _atto(
        "concorrenza_sleale",
        r"(?:atto\s+di\s+citazione\s+per\s+|azione\s+di\s+|ricorso\s+per\s+)concorrenza\s+sleale(?:\s+.*)?",
        r"\bconcorrenz\w+\s+slea\w+\b|\b259[89]\b|\b2600\b|\bconfusori\w+\b|\bstorno\b",
        "Azione di concorrenza sleale",
        "titolo dell'atto e atti di concorrenza sleale (artt. 2598-2600 c.c.)",
        fonte="normattiva_codice_civile",
    ),
    _atto(
        "richiesta_documentazione_bancaria",
        r"richiesta\s+(?:di\s+)?(?:copia\s+(?:della\s+)?documentazione|estratti\s+conto|documentazione)\s+(?:bancaria\s+)?(?:ex\s+|ai\s+sensi\s+dell.?\s*)art\.?\s*119.*|richiesta\s+(?:di\s+)?estratti\s+conto(?:\s+.*)?",
        _BANCA + r"|\b119\b|\bestratt\w+\s+cont\w+\b",
        "Richiesta di documentazione bancaria (art. 119 TUB)",
        "titolo della richiesta e diritto del cliente alla documentazione (art. 119, quarto comma, D.Lgs. 385/1993)",
        fonte="normattiva_tub_385_1993", role="corrispondenza_stragiudiziale", section="comunicazioni",
        tipo=TipoDocumento.COMUNICAZIONE, deposit_role="allegato",
    ),
    _atto(
        "contenzioso_bancario",
        r"(?:atto\s+di\s+citazione\s+per\s+|azione\s+di\s+)(?:anatocismo|usura\s+bancaria|ripetizione\s+(?:di\s+)?indebito\s+bancario|nullit[aà]\s+della\s+fideiussione).*|"
        r"(?:atto|azione)\s+in\s+materia\s+di\s+fideiussione(?:\s+omnibus)?(?:\s+.*)?|azione\s+di\s+ripetizione\s+di\s+indebito\s+bancario(?:\s+.*)?",
        _BANCA + r"|\banatocism\w+\b|\busur\w+\b|\bfideiussion\w+\b|\bindebit\w+\b|\b2033\b|\b1283\b",
        "Atto di contenzioso bancario",
        "titolo dell'atto e rapporto bancario contestato (artt. 117 e 120 D.Lgs. 385/1993; artt. 1283, 1938 e 2033 c.c.)",
        fonte="normattiva_tub_385_1993",
    ),
    _atto(
        "centrale_rischi",
        r"(?:opposizione|reclamo|ricorso|contestazione)\s+(?:a|alla|avverso\s+la)\s+(?:iscrizione|segnalazione)\s+in\s+centrale\s+(?:dei\s+)?rischi(?:\s+.*)?",
        _BANCA + r"|\bcentrale\s+(?:dei\s+)?rischi\b|\bsegnalazion\w+\b",
        "Contestazione della segnalazione in Centrale dei rischi",
        "titolo dell'atto e segnalazione dell'intermediario (art. 53 D.Lgs. 385/1993)",
        fonte="normattiva_tub_385_1993",
    ),
    _atto(
        "perizia_econometrica",
        r"perizia\s+(?:econometrica|contabile(?:\s+bancaria)?|di\s+ricalcolo)(?:\s+.*)?|relazione\s+(?:tecnica\s+)?(?:econometrica|di\s+ricalcolo\s+del\s+rapporto)(?:\s+.*)?",
        _BANCA + r"|\bricalcol\w+\b|\btaeg\b|\btasso\b|\binteress\w+\b",
        "Perizia econometrica",
        "titolo della perizia e ricalcolo del rapporto bancario (artt. 117 e 120 D.Lgs. 385/1993)",
        fonte="normattiva_tub_385_1993", role="perizia_di_parte", section="allegati",
        tipo=TipoDocumento.ALLEGATO, deposit_role="allegato",
    ),
)

__all__ = ["REGOLE"]
