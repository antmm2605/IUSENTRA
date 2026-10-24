"""Lex scrive le parti narrative dell'atto (blocchi «scrive_lex» della scheda), con il percorso controllato.

Il software prepara tutto: dati del fascicolo gia' risolti dalla scheda (gestionale e fatti letti), scadenze
calcolate, Fonti della scheda con provenienza (testo vigente). Lex scrive solo i blocchi richiesti, cita solo
le Fonti con [n] e segnala con [DATO MANCANTE: ...] cio' che non risulta. Poi revisione indipendente
(norme fuori Fonti, richiami sbagliati, date e importi senza provenienza, conclusioni contro l'assistito,
termini scaduti non segnalati) e stato della consegna. Nessuno stato significa «atto corretto».
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .fonti_scheda import FontiScheda
from .revisione_indipendente import rivedi
from .stato_consegna import stato

SISTEMA = (
    "Sei Lex, assistente giuridico di uno studio legale italiano. Scrivi in italiano forense, preciso, senza saluti.\n"
    "- Per le norme usa SOLO le Fonti numerate [1], [2]...: cita ogni affermazione giuridica con [n].\n"
    "- Usa SOLO i dati del fascicolo forniti; ogni dato che manca va scritto come [DATO MANCANTE: descrizione].\n"
    "- Scadenze e importi: riporta identici quelli calcolati dal software, non ricalcolarli.\n"
    "- Non scrivere ragionamenti interni, note per te o riferimenti alla scheda."
)
# Blocco della scheda -> campi del modello del compilatore, in ordine di preferenza (parole chiave nel nome del blocco).
CANDIDATI_CAMPO = (
    (("fatt", "svolgimento", "premesse", "rapporto di lavoro"),
     ("facts", "relevant_facts", "reported_facts", "position_on_facts", "defence_on_facts", "supervening_facts")),
    (("eccezion", "difes", "opposizion"), ("merit_exceptions", "procedural_exceptions", "legal_arguments")),
    (("diritto", "motivi", "fumus", "periculum", "impugnazione", "osservazioni"), ("legal_arguments",)),
    (("istruttori", "prove", "mezzi di prova", "capitoli", "lista"), ("evidence_means",)),
    (("conclusion", "domand", "richiesta", "istanz"), ("requests_or_conclusions", "final_conclusions")),
    (("conteggi", "prospetto"), ("legal_arguments", "facts")),
    (("allegati", "indice"), ("attachments_list",)),
)


@dataclass
class EsitoStesura:
    blocchi: dict[str, str] = field(default_factory=dict)
    campi: dict[str, str] = field(default_factory=dict)  # blocco -> campo del modello in cui inserirlo
    revisione: dict = field(default_factory=dict)
    stato_consegna: dict = field(default_factory=dict)
    testo: str = ""
    modello_ai: str = ""


# Budget del contesto (modello locale con 32k token): ogni Fonte oltre questa misura viene accorciata dichiarandolo,
# cosi' Lex sa che il testo integrale esiste e non deve supplire con la memoria.
MAX_CARATTERI_FONTE = 3500


def _fonte_per_messaggio(testo: str) -> str:
    if len(testo) <= MAX_CARATTERI_FONTE:
        return testo
    taglio = testo.rfind("\n", 0, MAX_CARATTERI_FONTE)
    taglio = taglio if taglio > MAX_CARATTERI_FONTE // 2 else MAX_CARATTERI_FONTE
    return testo[:taglio].rstrip() + "\n[... testo accorciato: per le parti omesse scrivi [DATO MANCANTE: verifica del testo integrale]]"


def _dati_fascicolo(risolta: dict) -> list[str]:
    righe = []
    for c in risolta.get("campi", []):
        if c.get("stato") in ("compilato", "da_confermare") and str(c.get("valore") or "").strip():
            nota = "" if c["stato"] == "compilato" else " (letto dai documenti, da confermare)"
            righe.append(f"- {c['etichetta']}: {c['valore']}{nota}")
    return righe


def messaggio(oggetto: str, risolta: dict, fonti: FontiScheda, *, blocco_scadenze: str, oggi: date,
              assistito: str, controparte: str) -> str:
    compiti = "\n".join(f"### {b['blocco']}\n({b['compito']})" for b in risolta.get("scrive_lex", []))
    testo_fonti = "\n\n".join(f"[{n}] {_fonte_per_messaggio(t)}" for n, t in sorted(fonti.fonti.items())) or "Nessuna Fonte disponibile."
    return (f"Atto: {risolta.get('titolo', '')}\nRichiesta dell'avvocato: {oggetto}\nData di oggi: {oggi.strftime('%d/%m/%Y')}\n"
            f"Parte assistita: {assistito}\nControparte: {controparte}\n\nDati del fascicolo:\n"
            + ("\n".join(_dati_fascicolo(risolta)) or "- nessun dato oltre alla richiesta")
            + (f"\n\n{blocco_scadenze}" if blocco_scadenze else "")
            + f"\n\nFonti:\n{testo_fonti}\n\nScrivi SOLO queste parti dell'atto, ognuna sotto il proprio titolo ###, nell'ordine:\n{compiti}")


def dividi_blocchi(testo: str, nomi: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    pezzi = re.split(r"(?m)^\s*#{2,4}\s*(.+?)\s*$", testo or "")
    for i in range(1, len(pezzi) - 1, 2):
        titolo = pezzi[i].strip().strip("*: ").lower()
        nome = next((n for n in nomi if n.lower() in titolo or titolo in n.lower()), None)
        if nome and pezzi[i + 1].strip():
            out[nome] = pezzi[i + 1].strip()
    return out


def campi_per_blocchi(nomi: list[str], campi_modello: list[str]) -> dict[str, str]:
    out = {}
    for nome in nomi:
        basso = nome.lower()
        for chiavi, candidati in CANDIDATI_CAMPO:
            campo = next((c for c in candidati if c in campi_modello), None) if any(k in basso for k in chiavi) else None
            if campo:
                out[nome] = campo
                break
        else:
            # corpo unico dell'atto (Istanza, Ricorso, Diffida, Lettera...): va nel campo dei fatti se c'e'
            corpo = next((c for c in CANDIDATI_CAMPO[0][1] if c in campi_modello), None)
            if corpo:
                out[nome] = corpo
    return out


def risolvi_citazioni(testo: str, fonti_ref: list[dict]) -> str:
    """Nell'atto i richiami [n] diventano la norma citata, es. «(art. 163 c.p.c.)»; [n, m] diventano una sola parentesi."""
    nomi = {int(r["n"]): f"art. {r['articolo']} {r.get('sigla') or r.get('atto', '')}".strip() for r in fonti_ref}

    def sostituisci(m: re.Match) -> str:
        numeri = [int(x) for x in re.findall(r"\d+", m.group(0))]
        if not all(n in nomi for n in numeri):
            return m.group(0)
        return "(" + "; ".join(nomi[n] for n in numeri) + ")"

    return re.sub(r"\[\d+(?:\s*[,;]\s*\d+)*\]", sostituisci, testo or "")


def termini_da_scadenze(scadenze: list[dict]) -> list[dict]:
    """Scadenze calcolate dalla scheda nel formato della revisione indipendente (solo date gg/mm/aaaa)."""
    out = []
    for s in scadenze:
        m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", str(s.get("valore") or ""))
        if m:
            out.append({"descrizione": s.get("etichetta", ""), "scadenza": m.group(1),
                        "per_agire": not s["etichetta"].lower().startswith("primo giorno")})
    return out


def scrivi_blocchi(*, chiama_modello, oggetto: str, risolta: dict, fonti: FontiScheda, blocco_scadenze: str,
                   termini: list[dict], fatti_testo: str, oggi: date, assistito: str, controparte: str,
                   campi_modello: list[str], ruolo_assistito: str = "") -> EsitoStesura:
    """``chiama_modello(sistema, messaggio) -> (testo, nome_modello)``: il gateway di Lex (o un sostituto nei test)."""
    nomi = [b["blocco"] for b in risolta.get("scrive_lex", [])]
    msg = messaggio(oggetto, risolta, fonti, blocco_scadenze=blocco_scadenze, oggi=oggi, assistito=assistito,
                    controparte=controparte)
    testo, nome_modello = chiama_modello(SISTEMA, msg)
    caso = {"fonti": fonti.fonti, "fonti_ref": fonti.fonti_ref, "fatti": fatti_testo + "\n" + "\n".join(_dati_fascicolo(risolta)),
            "richiesta": oggetto + "\n" + blocco_scadenze, "oggi": oggi.strftime("%d/%m/%Y"),
            "parte_assistita": {"nome": assistito or "assistito", "ruolo": ruolo_assistito}, "controparte": {"nome": controparte or ""}}
    revisione = rivedi(testo, caso, {"termini": termini, "importi": []})
    esito_stato = stato(testo, [], revisione, {"norme_mancanti": [], "dati_mancanti": []}, None)
    if fonti.pendenze and esito_stato["stato"] == "pronta_per_revisione_avvocato":
        esito_stato["stato"] = "bozza_con_verifiche_pendenti"
    esito_stato["motivi"] = esito_stato.get("motivi", []) + [f"fonte: {p}" for p in fonti.pendenze]
    blocchi = dividi_blocchi(testo, nomi)
    return EsitoStesura(blocchi=blocchi, campi=campi_per_blocchi(list(blocchi), campi_modello), revisione=revisione,
                        stato_consegna=esito_stato, testo=testo, modello_ai=nome_modello)
