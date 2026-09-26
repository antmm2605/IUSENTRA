"""Il presidio notifiche che legge i documenti: che cosa va notificato, a chi, entro quando.

Il presidio PEC riconosce le notifiche ricevute e inviate. Qui si fa il passo
che mancava: dal **documento** presente nel fascicolo (voce del catalogo),
dalle **parti** lette negli atti e dalle **date** dell'archivio delle letture
nasce l'obbligo di notificare, con i destinatari e il termine. Nessuna lettura
nuova: tutto viene da catalogo e archivio.

Ogni regola dichiara la norma. Una regola si applica solo se l'atto è dello
studio (la parte assistita agisce nell'epigrafe) — un decreto ingiuntivo
ottenuto dalla controparte non si notifica: si valuta l'opposizione. Quando i
dati non bastano (lato non letto, data mancante) l'obbligo resta «da
verificare» con il motivo, mai un termine inventato.

Destinatari:

- controparte privata: all'indirizzo PEC dei pubblici elenchi (art. 3-bis L.
  53/1994; art. 16-ter D.L. 179/2012) o nelle forme degli artt. 137 ss. c.p.c.;
  dopo la costituzione, presso il difensore (artt. 170, 285, 330 c.p.c.);
- amministrazione dello Stato: presso l'Avvocatura dello Stato del distretto
  dell'ufficio giudiziario (art. 11 R.D. 1611/1933; art. 144 c.p.c.);
  nel pubblico impiego contrattualizzato, art. 415, settimo comma, c.p.c.;
- altre amministrazioni: presso la sede, in persona del legale rappresentante
  (art. 144, secondo comma, c.p.c.; art. 145 c.p.c.).

I termini «liberi» (art. 163-bis, 660 c.p.c.) escludono il giorno iniziale e
quello finale: l'ultima data utile è l'udienza meno i giorni meno uno.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable

STATO_DA_NOTIFICARE = "da_notificare"
STATO_NOTIFICATO = "notificato"
STATO_DA_VERIFICARE = "da_verificare"
STATO_FACOLTATIVO = "facoltativo"

# Amministrazioni dello Stato (difese dall'Avvocatura dello Stato, R.D. 1611/1933).
_STATALE = re.compile(r"\b(?:ministero|ministro|presidenza\s+del\s+consiglio|prefettura|questura|ufficio\s+scolastico|agenzia\s+del\s+demanio|avvocatura)\b", re.IGNORECASE)
_PA = re.compile(r"\b(?:comune|regione|provincia|citt[aà]\s+metropolitana|inps|inail|azienda\s+sanitaria|asl|asp|universit[aà]|agenzia|istituto|autorit[aà])\b", re.IGNORECASE)


@dataclass(frozen=True)
class Termine:
    """Come si calcola il termine: da quale data, quanti giorni, in che verso."""

    base: str  # pronuncia | udienza | provvedimento_impugnato | pubblicazione
    giorni: int = 0
    mesi: int = 0
    prima: bool = False  # True: il termine scade «giorni prima» della base (udienza)
    liberi: bool = False
    natura: str = "perentorio"  # perentorio | a_difesa | ordinatorio
    formula: str = ""


@dataclass(frozen=True)
class RegolaNotifica:
    id: str
    etichette: tuple[str, ...]
    atti: str
    destinatari: str  # controparti | amministrazione_e_controinteressati | amministrazione_e_parti | controparti_presso_difensore
    fonti: tuple[str, ...]
    termini: tuple[Termine, ...] = ()
    solo_se_nostro: bool = True
    facoltativa: bool = False
    dopo: str = ""
    avvertenze: str = ""


REGOLE: tuple[RegolaNotifica, ...] = (
    RegolaNotifica(
        "lavoro_415", ("Ricorso in materia di lavoro (art. 414 c.p.c.)",),
        "ricorso e decreto di fissazione dell'udienza", "controparti",
        ("art. 415, commi 4, 5 e 7, c.p.c.", "art. 417-bis c.p.c."),
        termini=(
            Termine("udienza", giorni=30, prima=True, liberi=True, natura="a_difesa",
                    formula="almeno 30 giorni prima dell'udienza di discussione (art. 415, quinto comma, c.p.c.; calcolato per prudenza come termine libero)"),
        ),
        avvertenze="Entro 10 giorni dalla pronuncia del decreto (art. 415, quarto comma: termine ordinatorio). "
                   "Pubblico impiego: notifica presso l'amministrazione (art. 144, secondo comma) o, per le amministrazioni statali, "
                   "presso l'Avvocatura dello Stato competente (art. 415, settimo comma); l'amministrazione può stare in giudizio con propri funzionari (art. 417-bis).",
    ),
    RegolaNotifica(
        "decreto_ingiuntivo_644", ("Decreto ingiuntivo",),
        "ricorso e decreto ingiuntivo", "controparti",
        ("art. 643 c.p.c.", "art. 644 c.p.c."),
        termini=(Termine("pronuncia", giorni=60, natura="perentorio",
                         formula="entro 60 giorni dalla pronuncia, a pena di inefficacia del decreto (art. 644 c.p.c.; 90 giorni se la notifica è all'estero)"),),
        avvertenze="Il decreto va notificato con il ricorso (art. 643). Senza notifica nel termine il decreto perde efficacia.",
    ),
    RegolaNotifica(
        "citazione_163bis", ("Atto di citazione",),
        "atto di citazione", "controparti",
        ("art. 163-bis c.p.c.",),
        termini=(Termine("udienza", giorni=120, prima=True, liberi=True, natura="a_difesa",
                         formula="almeno 120 giorni liberi prima dell'udienza indicata (150 se la notifica è all'estero, art. 163-bis c.p.c.)"),),
    ),
    RegolaNotifica(
        "opposizione_di_645", ("Opposizione a decreto ingiuntivo",),
        "atto di citazione in opposizione", "controparti_presso_difensore",
        ("art. 641 c.p.c.", "art. 645 c.p.c."),
        avvertenze="L'opposizione si propone entro 40 giorni dalla notificazione del decreto (art. 641), con citazione notificata al ricorrente presso il difensore del procedimento monitorio (art. 645).",
    ),
    RegolaNotifica(
        "sfratto_660", ("Intimazione di sfratto",),
        "intimazione di sfratto con citazione per la convalida", "controparti",
        ("art. 660 c.p.c.",),
        termini=(Termine("udienza", giorni=20, prima=True, liberi=True, natura="a_difesa",
                         formula="almeno 20 giorni liberi prima dell'udienza (art. 660, quarto comma, c.p.c.)"),),
    ),
    RegolaNotifica(
        "precetto_480", ("Atto di precetto",),
        "titolo esecutivo (se non già notificato) e atto di precetto", "controparti",
        ("art. 479 c.p.c.", "art. 480 c.p.c.", "art. 481 c.p.c.", "art. 482 c.p.c."),
        dopo="Pignoramento non prima di 10 giorni dalla notifica del precetto (art. 482) ed entro 90 giorni, poi il precetto perde efficacia (art. 481).",
    ),
    RegolaNotifica(
        "ricorso_tar_41", ("Ricorso al TAR",),
        "ricorso", "amministrazione_e_controinteressati",
        ("art. 41 c.p.a.", "art. 45 c.p.a.", "art. 11 R.D. 1611/1933"),
        termini=(Termine("provvedimento_impugnato", giorni=60, natura="perentorio",
                         formula="entro 60 giorni dalla notificazione, comunicazione o piena conoscenza del provvedimento impugnato (art. 41, secondo comma, c.p.a.)"),),
        dopo="Deposito del ricorso notificato entro 30 giorni dall'ultima notificazione (art. 45 c.p.a.).",
        avvertenze="Il ricorso va notificato all'amministrazione che ha emesso l'atto e ad almeno uno dei controinteressati (art. 41, secondo comma, c.p.a.).",
    ),
    RegolaNotifica(
        "ottemperanza_114", ("Ricorso per l'ottemperanza (art. 114 c.p.a.)",),
        "ricorso per l'ottemperanza", "amministrazione_e_parti",
        ("art. 114 c.p.a.", "art. 45 c.p.a.", "art. 11 R.D. 1611/1933"),
        dopo="Deposito del ricorso notificato entro 30 giorni dall'ultima notificazione (art. 45 c.p.a.).",
        avvertenze="Il ricorso si notifica alla pubblica amministrazione e a tutte le altre parti del giudizio definito dalla sentenza (art. 114, primo comma, c.p.a.).",
    ),
    RegolaNotifica(
        "appello_civile_325", ("Atto di appello",),
        "atto di appello", "controparti_presso_difensore",
        ("art. 325 c.p.c.", "art. 327 c.p.c.", "art. 330 c.p.c."),
        termini=(Termine("pubblicazione", mesi=6, natura="perentorio",
                         formula="entro 30 giorni dalla notificazione della sentenza (art. 325) e comunque entro 6 mesi dalla pubblicazione (art. 327)"),),
        avvertenze="Si notifica al procuratore costituito della controparte (art. 330 c.p.c.).",
    ),
    RegolaNotifica(
        "appello_cds_92", ("Appello al Consiglio di Stato",),
        "appello", "controparti_presso_difensore",
        ("art. 92 c.p.a.", "art. 94 c.p.a."),
        termini=(Termine("pubblicazione", mesi=6, natura="perentorio",
                         formula="entro 60 giorni dalla notificazione della sentenza e comunque entro 6 mesi dalla pubblicazione (art. 92 c.p.a.)"),),
        dopo="Deposito entro 30 giorni dall'ultima notificazione (art. 94 c.p.a.).",
    ),
    RegolaNotifica(
        "sentenza_notifica_breve", ("Sentenza",),
        "sentenza (per far decorrere il termine breve di impugnazione)", "controparti_presso_difensore",
        ("art. 285 c.p.c.", "art. 325 c.p.c.", "art. 326 c.p.c."),
        solo_se_nostro=False, facoltativa=True,
        avvertenze="Scelta difensiva: notificare la sentenza al difensore costituito fa decorrere il termine breve di impugnazione anche per chi notifica.",
    ),
)
REGOLE_PER_ETICHETTA: dict[str, tuple[RegolaNotifica, ...]] = {}
for _regola in REGOLE:
    for _etichetta in _regola.etichette:
        REGOLE_PER_ETICHETTA[_etichetta.casefold()] = (*REGOLE_PER_ETICHETTA.get(_etichetta.casefold(), ()), _regola)


@dataclass(frozen=True)
class DocumentoCatalogato:
    id: str
    nome: str
    etichetta: str
    data: str = ""  # data del provvedimento o dell'atto (ISO), dall'archivio
    nostro: bool | None = None  # la parte assistita agisce nell'atto?
    udienze: tuple[str, ...] = ()  # udienze lette nel documento (ISO)


@dataclass(frozen=True)
class Parte:
    nome: str
    ruolo: str  # controparte | difensore_controparte | assistito | controinteressato
    difensore: str = ""
    posizione: str = ""


@dataclass
class ObbligoNotifica:
    regola: RegolaNotifica
    documento: DocumentoCatalogato
    stato: str
    motivo: str = ""
    scadenza: str = ""
    natura: str = ""
    formula: str = ""
    destinatari: list[dict[str, str]] = field(default_factory=list)

    @property
    def chiave(self) -> str:
        return f"{self.regola.id}:{self.documento.id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chiave": self.chiave, "regola": self.regola.id, "documentoId": self.documento.id, "documento": self.documento.nome,
            "etichetta": self.documento.etichetta, "atti": self.regola.atti, "stato": self.stato, "motivo": self.motivo,
            "scadenza": self.scadenza, "natura": self.natura, "formula": self.formula, "destinatari": list(self.destinatari),
            "fonti": list(self.regola.fonti), "dopo": self.regola.dopo, "avvertenze": self.regola.avvertenze,
            "facoltativa": self.regola.facoltativa,
        }


def _giorno(valore: str) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def _aggiungi_mesi(giorno: date, mesi: int) -> date:
    mese = giorno.month - 1 + mesi
    anno, mese = giorno.year + mese // 12, mese % 12 + 1
    for ultimo in (31, 30, 29, 28):
        try:
            return date(anno, mese, min(giorno.day, ultimo))
        except ValueError:
            continue
    return giorno


def scadenza(termine: Termine, base: date) -> date:
    """L'ultima data utile per notificare."""
    if termine.mesi:
        return _aggiungi_mesi(base, termine.mesi)
    giorni = termine.giorni + (1 if termine.liberi else 0)
    return base - timedelta(days=giorni) if termine.prima else base + timedelta(days=giorni)


def avvocatura_distrettuale(ufficio: str) -> str:
    """L'Avvocatura dello Stato del distretto dell'ufficio (art. 11 R.D. 1611/1933)."""
    nome = str(ufficio or "").strip()
    if not nome:
        return "Avvocatura distrettuale dello Stato competente per territorio"
    try:
        from pct.uffici_giudiziari import _build_bundle_completo

        voce = next((u for u in _build_bundle_completo() if str(u.get("nome") or "").casefold() == nome.casefold()), None)
    except Exception:
        voce = None
    if voce and voce.get("tipo") != "TAR":
        distretto = str(voce.get("distretto_gl") or voce.get("distretto") or "").strip()
        if distretto:
            return f"Avvocatura distrettuale dello Stato di {distretto}"
    return f"Avvocatura distrettuale dello Stato competente per la sede di {nome}"


def _destinatario(parte: Parte, *, presso_difensore: bool, ufficio: str, difensori: dict[str, str], lavoro: bool) -> dict[str, str]:
    difensore = parte.difensore or difensori.get(parte.nome, "")
    if _STATALE.search(parte.nome):
        avvocatura = difensore if "avvocatura" in difensore.casefold() else avvocatura_distrettuale(ufficio)
        presso = f"presso {avvocatura}"
        fonte = "art. 11 R.D. 1611/1933; art. 144 c.p.c." + ("; art. 415, settimo comma, c.p.c." if lavoro else "")
    elif _PA.search(parte.nome):
        presso = "presso la sede, in persona del legale rappresentante" + (f" (difensore letto: {difensore})" if difensore else "")
        fonte = "art. 144, secondo comma, e art. 145 c.p.c."
    elif presso_difensore and difensore:
        presso = f"presso il difensore costituito {difensore}"
        fonte = "artt. 170, 285 e 330 c.p.c."
    else:
        presso = "all'indirizzo PEC dei pubblici elenchi o nelle forme degli artt. 137 ss. c.p.c."
        fonte = "art. 3-bis L. 53/1994; art. 16-ter D.L. 179/2012"
    return {"nome": parte.nome, "ruolo": parte.ruolo, "presso": presso, "fonte": fonte}


def _destinatari(regola: RegolaNotifica, parti: list[Parte], ufficio: str) -> list[dict[str, str]]:
    difensori = {p.posizione.replace("difensore di ", "", 1): p.nome for p in parti if p.ruolo == "difensore_controparte"}
    presso_difensore = regola.destinatari == "controparti_presso_difensore"
    ruoli = {"controparte", "controinteressato"}
    lavoro = regola.id == "lavoro_415"
    return [_destinatario(p, presso_difensore=presso_difensore, ufficio=ufficio, difensori=difensori, lavoro=lavoro)
            for p in parti if p.ruolo in ruoli]


def _base(termine: Termine, documento: DocumentoCatalogato, contesto: dict[str, Any]) -> date | None:
    if termine.base == "udienza":
        udienze = [g for g in (_giorno(u) for u in documento.udienze) if g]
        if not udienze:
            udienze = [g for g in (_giorno(u) for u in contesto.get("udienze_future", ())) if g]
        return min(udienze) if udienze else None
    if termine.base in {"pronuncia", "pubblicazione"}:
        if termine.base == "pubblicazione":
            sentenze = [g for g in (_giorno(d) for d in contesto.get("date_sentenze", ())) if g]
            return max(sentenze) if sentenze else None
        return _giorno(documento.data)
    if termine.base == "provvedimento_impugnato":
        return _giorno(contesto.get("data_provvedimento_impugnato", ""))
    return None


def _notificato(regola: RegolaNotifica, documento: DocumentoCatalogato, contesto: dict[str, Any]) -> bool:
    """Una prova di notifica successiva all'atto (relata o ricevuta di consegna) nel fascicolo."""
    riferimento = _giorno(documento.data)
    for prova in contesto.get("prove_notifica", ()):
        giorno = _giorno(prova.get("data", ""))
        if prova.get("documento_id") == documento.id:
            return True
        if riferimento and giorno and giorno >= riferimento:
            return True
        if not riferimento and prova.get("atto") and any(p in prova.get("atto", "").casefold() for p in regola.atti.casefold().split()[:2]):
            return True
    return False


def obblighi_del_fascicolo(documenti: Iterable[DocumentoCatalogato], parti: Iterable[Parte], *, ufficio: str = "",
                           contesto: dict[str, Any] | None = None, oggi: date | None = None) -> list[ObbligoNotifica]:
    """Gli obblighi di notifica che nascono dai documenti del fascicolo."""
    contesto = dict(contesto or {})
    oggi = oggi or date.today()
    parti = list(parti)
    esito: list[ObbligoNotifica] = []
    for documento in documenti:
        for regola in REGOLE_PER_ETICHETTA.get(documento.etichetta.casefold(), ()):
            obbligo = ObbligoNotifica(regola=regola, documento=documento, stato=STATO_DA_NOTIFICARE)
            obbligo.destinatari = _destinatari(regola, parti, ufficio)
            if regola.facoltativa:
                obbligo.stato, obbligo.motivo = STATO_FACOLTATIVO, "Notifica facoltativa: decisione del difensore."
            elif regola.solo_se_nostro and documento.nostro is False:
                continue
            elif regola.solo_se_nostro and documento.nostro is None:
                obbligo.stato, obbligo.motivo = STATO_DA_VERIFICARE, "Dagli atti non risulta se l'atto è dello studio: confermare prima di notificare."
            if _notificato(regola, documento, contesto):
                obbligo.stato, obbligo.motivo = STATO_NOTIFICATO, "Nel fascicolo c'è una prova di notifica successiva all'atto (relata o ricevuta di consegna): verificare che riguardi questo atto."
            for termine in regola.termini:
                obbligo.natura, obbligo.formula = termine.natura, termine.formula
                base = _base(termine, documento, contesto)
                if base is None:
                    if obbligo.stato == STATO_DA_NOTIFICARE:
                        obbligo.motivo = obbligo.motivo or "La data da cui decorre il termine non è stata letta: calcolare il termine a mano."
                    continue
                obbligo.scadenza = scadenza(termine, base).isoformat()
                break
            if not obbligo.destinatari and obbligo.stato in {STATO_DA_NOTIFICARE, STATO_DA_VERIFICARE}:
                obbligo.motivo = (obbligo.motivo + " " if obbligo.motivo else "") + "Controparte non ancora letta negli atti: completare le parti del fascicolo."
            esito.append(obbligo)
    ordine = {STATO_DA_NOTIFICARE: 0, STATO_DA_VERIFICARE: 1, STATO_FACOLTATIVO: 2, STATO_NOTIFICATO: 3}
    return sorted(esito, key=lambda o: (ordine.get(o.stato, 9), o.scadenza or "9999"))


__all__ = [
    "REGOLE", "STATO_DA_NOTIFICARE", "STATO_DA_VERIFICARE", "STATO_FACOLTATIVO", "STATO_NOTIFICATO",
    "DocumentoCatalogato", "ObbligoNotifica", "Parte", "RegolaNotifica", "Termine",
    "avvocatura_distrettuale", "obblighi_del_fascicolo", "scadenza",
]
