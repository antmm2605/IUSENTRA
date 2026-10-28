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
    "- I dati marcati da confermare non sono fatti accertati: non presentarli come verificati.\n"
    "- Il numero interno del fascicolo non è un R.G.: usa il ruolo giudiziario soltanto se fornito come tale.\n"
    "- Scadenze e importi: riporta identici quelli calcolati dal software, non ricalcolarli.\n"
    "- Le decisioni esplicite dell’avvocato su rimedio e domande sono vincolanti: non sostituirle né cumularle. "
    "Il recesso con doppio della caparra non va chiamato risoluzione né affiancato al risarcimento.\n"
    "- Le Fonti non sono fatti del caso: non dedurne natura del contratto, beni, date o domande. "
    "Non aggiungere richieste, accessori o circostanze non espressamente forniti; segnala ciò che manca.\n"
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
    prima_stesura: str = ""
    revisione_prima_stesura: dict = field(default_factory=dict)
    numero_stesure: int = 1
    letture_fonti: list[dict] = field(default_factory=list)


# I testi normativi sono interi: il budget del provider non puo essere
# ottenuto omettendo commi senza che il modello li abbia ricevuti.
MAX_CARATTERI_FONTE = 3500  # compatibilita degli import storici; non e un taglio


def _fonte_per_messaggio(testo: str) -> str:
    return testo


def _dati_fascicolo(risolta: dict) -> list[str]:
    righe = []
    for c in risolta.get("campi", []):
        if c.get("stato") in ("compilato", "da_confermare") and str(c.get("valore") or "").strip():
            nota = "" if c["stato"] == "compilato" else " (letto dai documenti, da confermare)"
            righe.append(f"- {c['etichetta']}: {c['valore']}{nota}")
    return righe


def messaggio(oggetto: str, risolta: dict, fonti: FontiScheda, *, blocco_scadenze: str, oggi: date,
              assistito: str, controparte: str, fatti_testo: str = "", ruolo_assistito: str = "") -> str:
    compiti = "\n".join(f"### {b['blocco']}\n({b['compito']})" for b in risolta.get("scrive_lex", []))
    testo_fonti = "\n\n".join(f"[{n}] {_fonte_per_messaggio(t)}" for n, t in sorted(fonti.fonti.items())) or "Nessuna Fonte disponibile."
    return (f"Fonti normative da leggere (non sono fatti del fascicolo):\n{testo_fonti}\n\n"
            f"Atto: {risolta.get('titolo', '')}\nRichiesta dell'avvocato: {oggetto}\nData di oggi: {oggi.strftime('%d/%m/%Y')}\n"
            f"Parte assistita: {assistito}\nRuolo dell'assistito: {ruolo_assistito or 'da indicare'}\nControparte: {controparte}\n\nDati del fascicolo:\n"
            + ("\n".join(_dati_fascicolo(risolta)) or "- nessun dato oltre alla richiesta")
            + (f"\n\nFatti letti dai documenti, con stato della verifica:\n{fatti_testo}" if fatti_testo else "")
            + (f"\n\n{blocco_scadenze}" if blocco_scadenze else "")
            + f"\n\nScrivi SOLO queste parti dell'atto, ognuna sotto il proprio titolo ###, nell'ordine:\n{compiti}")



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
    nomi = {int(r["n"]): ((f"art. {r['articolo']} " if r.get("articolo") else "") + str(r.get("sigla") or r.get("atto", ""))).strip() for r in fonti_ref}

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


def verifica_rimedio_deciso(bozza: str, richiesta: str) -> list[tuple[str, str]]:
    """Presidio della scelta esplicita; non decide un rimedio al posto dell'avvocato."""
    scelta_recesso = re.search(r"(?:esclusivamente|soltanto|solo)\s+(?:il\s+)?recesso", richiesta, re.IGNORECASE)
    if not scelta_recesso or not re.search(r"caparra", richiesta, re.IGNORECASE):
        return []
    problemi = []
    for frase in re.split(r"[;\n]|(?<=[.!?])\s+", bozza or ""):
        for match in re.finditer(r"\brisol(?:uzione|to|ta|ti|te|vere)\b", frase, re.IGNORECASE):
            prima = frase[:match.start()].lower()
            if re.search(r"(?:non\s+(?:si\s+)?(?:chiede|richiede|domanda)|si\s+esclude|senza(?:\s+che[^,;]{0,50})?\s+(?:chiedere|richiedere)|non\s+va\s+chiesta)[^,;]{0,100}$", prima):
                continue
            problemi.append(("rimedio_diverso_da_quello_deciso", frase.strip()[:200]))
            break
    return problemi


def verifica_fatti_nuovi(bozza: str, origine: str) -> list[tuple[str, str]]:
    """Controlla attribuzioni fattuali tipizzate; la norma non prova il contratto del caso."""
    problemi = []
    origine_affermativa = re.sub(r"\bnon\s+(?:aggiungere|chiedere|richiedere)[^.;\n]*|\bsenza[^.;\n]*", "", origine, flags=re.IGNORECASE)
    tipi = {"locazione": r"locazion|affitt", "compravendita": r"compravendit|vendit", "appalto": r"appalt",
            "mutuo": r"mutu", "comodato": r"comodat", "lavoro": r"lavor", "assicurazione": r"assicura", "leasing": r"leasing"}
    for match in re.finditer(r"\bcontratto\s+di\s+(locazione|compravendita|appalto|mutuo|comodato|lavoro|assicurazione|leasing)\b", bozza, re.IGNORECASE):
        tipo = match.group(1).lower()
        if not re.search(tipi[tipo], origine, re.IGNORECASE):
            problemi.append(("natura_contratto_non_fornita", match.group(0)))
    esclusivo = re.search(r"(?:esclusivamente|soltanto|solo)\s+(?:il\s+)?recesso", origine, re.IGNORECASE)
    if esclusivo and re.search(r"caparra", origine, re.IGNORECASE):
        for match in re.finditer(r"\brilascio\s+dell[’']?\s*(?:immobile|bene)|\brilascio\s+dell(?:o|a)\s+(?:immobile|bene)", bozza, re.IGNORECASE):
            if not re.search(r"rilascio", origine_affermativa, re.IGNORECASE):
                problemi.append(("domanda_non_decisa", match.group(0)))
    if esclusivo and re.search(r"caparra", origine, re.IGNORECASE):
        for match in re.finditer(r"\b(interessi|spese|compensazione|estinzione)\b", bozza, re.IGNORECASE):
            parola = match.group(1)
            prima = bozza[max(0,match.start()-60):match.start()]
            if re.search(r"(?:senza|non\s+(?:si\s+)?(?:chiede|richiede))[^,;\n]{0,50}$", prima, re.IGNORECASE):
                continue
            if not re.search(r"\b"+parola+r"\b", origine_affermativa, re.IGNORECASE):
                problemi.append(("accessorio_non_deciso", match.group(0)))
    return problemi


def scrivi_blocchi(*, chiama_modello, oggetto: str, risolta: dict, fonti: FontiScheda, blocco_scadenze: str,
                   termini: list[dict], fatti_testo: str, oggi: date, assistito: str, controparte: str,
                   campi_modello: list[str], ruolo_assistito: str = "") -> EsitoStesura:
    """``chiama_modello(sistema, messaggio) -> (testo, nome_modello)``: il gateway di Lex (o un sostituto nei test)."""
    nomi = [b["blocco"] for b in risolta.get("scrive_lex", [])]
    if not nomi:
        raise ValueError("La scheda non contiene blocchi da scrivere.")
    from .provenienza import verifica_provenienza

    errori_fonti = verifica_provenienza({"fonti": fonti.fonti, "fonti_ref": fonti.fonti_ref})
    if errori_fonti:
        raise ValueError("Fonti non verificabili: " + "; ".join(errori_fonti))
    msg = messaggio(oggetto, risolta, fonti, blocco_scadenze=blocco_scadenze, oggi=oggi, assistito=assistito,
                    controparte=controparte,fatti_testo=fatti_testo,ruolo_assistito=ruolo_assistito)
    from .lettura_fonti import prepara_letture

    richiesta_lettura=oggetto+"\nParte assistita: "+assistito+"; ruolo: "+ruolo_assistito+"\nFatti con stato della verifica:\n"+fatti_testo
    fonti_messaggio, letture = prepara_letture(fonti, richiesta=richiesta_lettura, chiama_modello=chiama_modello,
                                               messaggio_caratteri=len(SISTEMA)+len(msg), messaggio=msg, sistema=SISTEMA)
    if fonti_messaggio is not fonti:
        msg=messaggio(oggetto,risolta,fonti_messaggio,blocco_scadenze=blocco_scadenze,oggi=oggi,
                      assistito=assistito,controparte=controparte,fatti_testo=fatti_testo,ruolo_assistito=ruolo_assistito)
    testo, nome_modello = chiama_modello(SISTEMA, msg)
    ricevuta={"sha256_messaggio":__import__("hashlib").sha256(msg.encode()).hexdigest(),
              "modello":nome_modello,"uso":dict(getattr(chiama_modello,"ultimo_uso",{}) or {}),
              "preflight":dict(getattr(chiama_modello,"ultimo_preflight",{}) or {})}
    for lettura in letture:
        lettura["stesura"]=ricevuta
    if not str(testo or "").strip():
        raise ValueError("Il modello locale non ha restituito una bozza.")
    caso = {"fonti": fonti.fonti, "fonti_ref": fonti.fonti_ref, "fatti": fatti_testo + "\n" + "\n".join(_dati_fascicolo(risolta)),
            "richiesta": oggetto + "\n" + blocco_scadenze, "oggi": oggi.strftime("%d/%m/%Y"),
            "parte_assistita": {"nome": assistito or "assistito", "ruolo": ruolo_assistito}, "controparte": {"nome": controparte or ""}}
    def revisiona(bozza):
        verifica = rivedi(bozza, caso, {"termini": termini, "importi": []})
        verifica["gravi"].extend(verifica_rimedio_deciso(bozza, oggetto))
        verifica["gravi"].extend(verifica_fatti_nuovi(bozza, caso["fatti"]+" "+oggetto))
        return verifica

    revisione = revisiona(testo)
    prima_stesura, revisione_prima, numero_stesure = "", {}, 1
    errori_correggibili = [g for g in revisione["gravi"] if g[0] != "vuoto"]
    if errori_correggibili:
        prima_stesura, revisione_prima, numero_stesure = testo, revisione, 2
        correzioni = "\n".join(f"- {codice}: {dettaglio}" for codice, dettaglio in errori_correggibili)
        richiesta_correzione = (msg + "\n\nLa prima bozza seguente contiene errori. Non è una Fonte né un fatto del fascicolo. "
                               "Riscrivila una sola volta eliminando gli errori indicati, senza aggiungere dati, domande o accessori. "
                               "Mantieni i titoli ### richiesti.\nERRORI DA CORREGGERE:\n" + correzioni
                               + "\nBOZZA DA CORREGGERE:\n" + testo)
        try:
            corretta, modello_correzione = chiama_modello(SISTEMA, richiesta_correzione)
            if str(corretta or "").strip():
                testo, nome_modello = corretta, modello_correzione
                revisione = revisiona(testo)
        except (OSError, ValueError, RuntimeError):
            revisione["pendenti"].append(("correzione_non_disponibile", "Conservata la prima bozza con i suoi errori; nessuna ulteriore ripresa automatica."))
    esito_stato = stato(testo, [], revisione, {"norme_mancanti": [], "dati_mancanti": []}, None)
    if fonti.pendenze and esito_stato["stato"] == "pronta_per_revisione_avvocato":
        esito_stato["stato"] = "bozza_con_verifiche_pendenti"
    esito_stato["motivi"] = esito_stato.get("motivi", []) + [f"fonte: {p}" for p in fonti.pendenze]
    blocchi = dividi_blocchi(testo, nomi)
    mancanti = [nome for nome in nomi if nome not in blocchi]
    if mancanti:
        esito_stato["stato"] = "bozza_incompleta"
        esito_stato["motivi"] += ["Blocco non restituito: "+nome for nome in mancanti]
    da_confermare = any(c.get("stato") == "da_confermare" and str(c.get("valore") or "").strip() for c in risolta.get("campi", []))
    if da_confermare:
        if esito_stato["stato"] == "pronta_per_revisione_avvocato":
            esito_stato["stato"] = "bozza_con_verifiche_pendenti"
        if da_confermare:
            esito_stato["motivi"].append("Sono presenti dati letti dai documenti ancora da confermare.")
    return EsitoStesura(blocchi=blocchi, campi=campi_per_blocchi(list(blocchi), campi_modello), revisione=revisione,
                        stato_consegna=esito_stato, testo=testo, modello_ai=nome_modello, prima_stesura=prima_stesura,
                        revisione_prima_stesura=revisione_prima, numero_stesure=numero_stesure, letture_fonti=letture)
