"""Gli atti del fascicolo: natura (dal catalogo), autore, data, ruolo, appartenenza alla causa, studio.

Regole (ognuna con la sua ragione):
- la natura viene dal catalogo documenti (`pct/document_intelligence`), mai ridecisa qui;
- l'autore si deduce dalla natura e dal testo: i provvedimenti sono del giudice, gli atti di parte sono
  dello studio quando il testo nomina un avvocato dello studio come difensore o firmatario
  (art. 83 c.p.c.: la procura e la sottoscrizione del difensore), altrimenti della controparte;
- un atto appartiene alla causa se porta il nostro numero di ruolo o nessun ruolo diverso; i precedenti
  giurisprudenziali allegati, gli atti stragiudiziali e i documenti di prova sono atti di contorno:
  non fanno decorrere termini né portano esiti della causa (G-8);
- la data dell'atto è quella letta nell'atto (fatto `data_atto` collaudato o la data in calce al
  provvedimento), mai la data di caricamento del file.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from pct.atto_della_causa import provvedimento_della_causa, ruoli_in_intestazione
from pct.decreto_fissazione_lavoro import ETICHETTA as ETICHETTA_DECRETO_415, e_decreto_fissazione_lavoro

from pct.archivio_letture.copie_atti import messaggio_strutturato

from .modello import Atto
from .testo import date_nel_testo, giorno, pulito, rg_normale, ruoli_nel_testo, semplice

NATURE_CONTORNO = {
    "precedente_giurisprudenziale": "precedente giurisprudenziale di altro procedimento",
    "contratto": "documento di prova (contratto)",
    "documento_identita": "documento d'identità",
    "documento_economico": "documento economico di prova",
    "dichiarazione_sostitutiva": "dichiarazione sostitutiva",
    "adempimento_studio": "adempimento interno dello studio",
    "corrispondenza": "corrispondenza",
    "contributo_unificato": "pagamento del contributo unificato",
    "economia_fascicolo": "documento economico dello studio",
}
NATURE_GIUDICE = {"provvedimento", "ordinanza_ufficio", "sentenza", "decreto"}
NATURE_DI_PARTE = {"atto_principale", "atto_difensivo", "procura", "relata", "istanza", "attestazione",
                   "nota_iscrizione_ruolo", "atto_esecutivo"}
_SENTENZA = re.compile(r"\bsentenza\b", re.I)
_VERIFICATI = {"verificata", "corretta"}


def _fatti_di(fatti: Iterable[dict[str, Any]], oggetto_id: str) -> list[dict[str, Any]]:
    return [f for f in fatti if f.get("oggetto_id") == oggetto_id and f.get("verifica") in _VERIFICATI]


def _avvocati_nel_testo(testo: str, avvocati: Iterable[str]) -> bool:
    piatto = semplice(testo)
    for nome in avvocati:
        parole = [p for p in semplice(nome).replace("avv.", "").split() if len(p) > 2]
        if len(parole) >= 2 and all(p in piatto for p in parole):
            return True
    return False


def _natura_contorno(documento: dict[str, Any], letti: list[dict[str, Any]]) -> str:
    natura = pulito(documento.get("natura"))
    etichetta = semplice(documento.get("etichetta"))
    for fatto in letti:
        if fatto.get("campo") == "natura_documentale" and fatto.get("valore") in NATURE_CONTORNO:
            return NATURE_CONTORNO[fatto["valore"]]
    if natura in NATURE_CONTORNO:
        return NATURE_CONTORNO[natura]
    if "stragiudizial" in etichetta or "diffida" in semplice(documento.get("nome")):
        return "atto stragiudiziale (diffida o richiesta di pagamento)"
    if "precedente" in etichetta:
        return NATURE_CONTORNO["precedente_giurisprudenziale"]
    return ""


def _data_in_calce(testo: str) -> str:
    """La data del provvedimento: «Vicenza, 09/10/2026 Il Giudice», «Palmi 3.7.2026», «All'udienza del 2.11.2026»."""
    coda = testo[-600:]
    date = date_nel_testo(coda)
    for inizio, _fine, valore in reversed(date):
        prima = semplice(coda[max(0, inizio - 40):inizio])
        if not re.search(r"(udienza|entro|termine|del|il|al|dal|dalla)\s*$", prima):
            return valore.isoformat()
    m = re.search(r"all['’]?\s*udienza del\s+", testo[:800], re.I)
    if m:
        dopo = date_nel_testo(testo[m.end():m.end() + 14])
        if dopo:
            return dopo[0][2].isoformat()
    return ""


_CHIUSURA_GIUDICE = re.compile(r"\bIl\s+(?:G\.\s?E\.?|Giudice\b|Presidente\b)", re.I)


def e_messaggio(nome: str, testo: str) -> bool:
    """Un messaggio PEC esportato (busta, ricevuta, comunicazione): l'atto è l'allegato, non il messaggio."""
    return pulito(nome).casefold().endswith((".eml", ".msg")) or messaggio_strutturato(testo)


def firmato_dal_giudice(testo: str) -> bool:
    """Il testo si chiude con la sottoscrizione del giudice («Il G.E.», «Il Giudice O.T.», «Il Giudice del Lavoro»).

    Serve quando il catalogo non ha riconosciuto il provvedimento («Contenuto da verificare»): la firma del
    giudice in calce è ciò che fa di un testo un provvedimento (art. 132, ultimo comma, e art. 134 c.p.c.).
    Un atto di parte si chiude con la firma dell'avvocato e non passa.
    """
    coda = " ".join(str(testo or "")[-350:].split())
    return bool(_CHIUSURA_GIUDICE.search(coda)) and not re.search(r"\bAvv\.|\bavvocat", coda, re.I)


def _autore(natura: str, etichetta: str, testo: str, dello_studio: bool) -> str:
    if natura in NATURE_GIUDICE or "sentenza" in etichetta or "decreto" in etichetta or "ordinanza" in etichetta:
        return "giudice"
    if natura in NATURE_DI_PARTE:
        return "studio" if dello_studio else "controparte"
    if natura == "comunicazione":
        if "comunicazione di cancelleria" in semplice(testo[:3000]) or "notificazione ai sensi del d.l. 179" in semplice(testo[:3000]):
            return "cancelleria"
        return "studio" if dello_studio else "terzo"
    return "studio" if dello_studio else "ignoto"


_ENFASI_TESTO_ESTRATTO = re.compile(r"(?<![\w*])(\*{1,2})([^\s*](?:[^*\n]*[^\s*])?)\1(?![\w*])")


def priorita_fonte_sentenza(atto: Atto) -> tuple[bool, bool]:
    """Una copia con estremi di pubblicazione è la fonte da cui esporre l'esito."""
    from pct.termine_lungo_sentenza import numero_sentenza
    from .regole.sentenza import data_pubblicazione

    if not atto.sentenza or not atto.copie:
        return True, True
    return not bool(data_pubblicazione(atto.testo)), not bool(numero_sentenza(atto.testo[:1200]))


def _copie_della_sentenza(atti: list[Atto]) -> None:
    from pct.percorso_pratica.esito import dispositivo
    from pct.termine_lungo_sentenza import data_decisione, numero_sentenza

    gruppi: dict[tuple[str, str, str], list[tuple[Atto, str]]] = {}
    for atto in atti:
        if not atto.sentenza or atto.appartenenza != "causa" or not atto.rg:
            continue
        decisione = data_decisione(atto.testo)
        testo_decisione = semplice(_ENFASI_TESTO_ESTRATTO.sub(r"\2", dispositivo(atto.testo)))
        # Un dispositivo breve o senza data può appartenere a decisioni distinte dello stesso fascicolo.
        if decisione is None or len(testo_decisione.split()) < 30:
            continue
        numero = numero_sentenza(atto.testo[:1200])
        gruppi.setdefault((atto.rg, decisione.isoformat(), testo_decisione), []).append((atto, numero))
    for gruppo in gruppi.values():
        if len(gruppo) < 2 or len({numero for _, numero in gruppo if numero}) > 1:
            continue
        identificativi = {atto.id for atto, _ in gruppo}
        for atto, _ in gruppo:
            atto.copie = sorted((identificativi | set(atto.copie)) - {atto.id})


def leggi_atti(documenti: Iterable[dict[str, Any]], fatti: list[dict[str, Any]], *, rg_causa: str, avvocati: list[str]) -> list[Atto]:
    atti: list[Atto] = []
    copie: dict[str, list[str]] = {}
    for fatto in fatti:
        if fatto.get("campo") == "impronta_testo_atto":
            copie.setdefault(str(fatto.get("valore")), []).append(str(fatto.get("oggetto_id")))
    for documento in documenti:
        oid = pulito(documento.get("id"))
        testo = str(documento.get("testo") or "")
        letti = _fatti_di(fatti, oid)
        natura = pulito(documento.get("natura"))
        etichetta_mostrata = pulito(documento.get("etichetta"))
        messaggio = e_messaggio(documento.get("nome"), testo)
        if natura not in NATURE_GIUDICE and not messaggio and e_decreto_fissazione_lavoro(testo):
            # il catalogo non l'ha riconosciuto, il contenuto sì (art. 415 c.p.c.): regola di pct/decreto_fissazione_lavoro
            natura, etichetta_mostrata = "provvedimento", ETICHETTA_DECRETO_415
        elif natura not in NATURE_GIUDICE | {"atto_principale", "atto_difensivo"} and not messaggio and firmato_dal_giudice(testo):
            natura, etichetta_mostrata = "provvedimento", "Provvedimento del giudice (riconosciuto dalla sottoscrizione)"
        etichetta = semplice(etichetta_mostrata)
        dello_studio = _avvocati_nel_testo(testo, avvocati)
        autore = _autore(natura, etichetta, testo, dello_studio)
        ruoli = sorted({rg_normale(f.get("valore")) for f in letti if f.get("campo") == "numero_ruolo"} - {""})
        if not ruoli and autore == "giudice":
            ruoli = sorted({r for _p, r in ruoli_nel_testo(testo[:400])})
        data = next((pulito(f.get("valore"))[:10] for f in letti if f.get("campo") == "data_atto"), "")
        if not data and autore == "giudice":
            data = _data_in_calce(testo)
        contorno = _natura_contorno(documento, letti)
        appartenenza, motivo = ("contorno", contorno) if contorno else ("causa", "")
        if not contorno and autore == "giudice" and rg_causa:
            # Regola unica di pct/atto_della_causa (G-8): ruolo in intestazione e data rispetto all'iscrizione a ruolo.
            numero, anno = rg_causa.split("/")
            della_causa, perche = provvedimento_della_causa(ruoli=ruoli_in_intestazione(testo), date_atto=[data] if data else [],
                                                            numero_rg=numero, anno_rg=anno)
            if della_causa is False:
                appartenenza, motivo = "contorno", perche
        impronte = [str(f.get("valore")) for f in letti if f.get("campo") == "impronta_testo_atto"]
        atti.append(Atto(
            id=oid, nome=pulito(documento.get("nome")), natura=natura, etichetta=etichetta_mostrata,
            autore=autore, data=data if giorno(data) else "", rg=rg_causa if rg_causa in ruoli else (ruoli[0] if ruoli else ""),
            appartenenza=appartenenza, motivo_appartenenza=motivo, dello_studio=dello_studio, testo=testo,
            copie=sorted({c for i in impronte for c in copie.get(i, []) if c != oid}),
            sentenza=autore == "giudice" and bool(_SENTENZA.search(etichetta)),
        ))
    _copie_della_sentenza(atti)
    return atti


__all__ = ["NATURE_CONTORNO", "e_messaggio", "firmato_dal_giudice", "leggi_atti"]
