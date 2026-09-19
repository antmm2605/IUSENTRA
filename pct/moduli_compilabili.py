"""Quello che lo studio sa gia' e le righe che il modulo tiene pronte.

Due cose che un modulo PDF mandato al cliente non sa fare da solo.

La prima: chiedere al cliente dati che il fascicolo ha gia'. Un'autocertificazione
comincia sempre con nome, luogo e data di nascita, residenza — la scheda cliente
li contiene, e farli riscrivere non e' solo scortese: cio' che viene riscritto
puo' divergere dal fascicolo. Qui quei campi si propongono gia' compilati, con
l'origine dichiarata, e il cliente conferma o corregge (GDPR 2016/679 art. 5
§ 1 lett. d ed art. 16).

La seconda: le righe in piu'. I moduli per il nucleo familiare tengono nel file
le righe non ancora usate, nascoste, e le mostrano con un pulsante che e'
JavaScript interno al PDF — nel portale, dove si vede l'immagine della pagina,
quel pulsante non fa nulla. Qui le righe nascoste diventano righe attivabili,
una alla volta.

Il riconoscimento dei campi e' dichiarato, mai indovinato dal contenuto: un
campo si propone solo se il suo nome e' fra quelli elencati in
CORRISPONDENZE, e una riga e' un gruppo di caselle che stanno sulla stessa
linea della pagina. Quello che non e' dichiarato resta vuoto.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from pct.anagrafica_cliente_portale import CAMPI_PORTALE

#: Nomi ricorrenti dei campi nei moduli giudiziari, per ogni dato della scheda
#: del portale. Si confronta il nome del campo del PDF normalizzato (minuscolo,
#: senza spazi e punteggiatura) con questi: chi prepara un modulo usa quasi
#: sempre uno di questi nomi. Un nome fuori elenco non si interpreta.
CORRISPONDENZE: dict[str, tuple[str, ...]] = {
    "displayName": ("nome_cognome", "cognome_nome", "nome_e_cognome", "cognome_e_nome", "dichiarante", "richiedente", "nominativo"),
    "fiscalCode": ("codice_fiscale", "cf", "c_f", "codicefiscale"),
    "birthDate": ("data_nascita", "data_di_nascita", "nato_il", "nata_il"),
    "birthPlace": ("luogo_nascita", "luogo_di_nascita", "comune_nascita", "comune_di_nascita", "nato_a", "nata_a"),
    "address": ("residenza", "indirizzo", "residente_a", "indirizzo_residenza"),
    "phone": ("telefono", "recapito_telefonico", "cellulare", "tel"),
    "pec": ("pec", "posta_elettronica_certificata"),
    "vatNumber": ("partita_iva", "p_iva", "piva"),
}

#: Prefissi che indicano la prima riga di una tabella di componenti: in quei
#: moduli la riga 1 e' il richiedente stesso, e si propone con i suoi dati.
PREFISSI_PRIMA_RIGA: tuple[str, ...] = ("nucleo_1_", "componente_1_", "riga_1_")


def _normalizza(nome: Any) -> str:
    testo = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(nome or ""))
    while "__" in testo:
        testo = testo.replace("__", "_")
    return testo.strip("_")


def _campo_della_scheda(nome_campo: str) -> str:
    """Il dato della scheda che corrisponde a questo campo del modulo, se dichiarato."""
    normalizzato = _normalizza(nome_campo)
    prima_riga = False
    for prefisso in PREFISSI_PRIMA_RIGA:
        if normalizzato.startswith(prefisso):
            normalizzato, prima_riga = normalizzato[len(prefisso):], True
            break
    if prima_riga and normalizzato in ("nome", "cognome", "componente"):
        # Nella tabella dei componenti la colonna si chiama «Cognome e nome»:
        # il campo «nome» della prima riga e' il richiedente per intero.
        return "displayName"
    for campo_portale, nomi in CORRISPONDENZE.items():
        if normalizzato in nomi:
            return campo_portale
    return ""


def proposte_dalla_scheda(
    campi: Iterable[Mapping[str, Any]],
    anagrafica: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Che cosa lo studio puo' gia' scrivere nel modulo, campo per campo.

    Si propone solo un valore che la scheda contiene davvero: un dato che
    manca resta vuoto, non si costruisce da altri (GDPR art. 5 § 1 lett. d).
    """
    scheda = {chiave: str(valore or "").strip() for chiave, valore in (anagrafica or {}).items()}
    proposte: dict[str, str] = {}
    for campo in campi:
        if campo.get("sola_lettura") or not campo.get("visibile", True):
            continue
        nome = str(campo.get("nome") or "")
        chiave = _campo_della_scheda(nome)
        if not chiave or chiave not in CAMPI_PORTALE:
            continue
        valore = scheda.get(chiave, "")
        if valore:
            proposte[nome] = valore
    return proposte


PREFISSO_IMPAGINAZIONE = "impaginazione_"


def _riga_dal_nome(nome: str) -> tuple[str, int, str]:
    """Scompone «nucleo_5_data_nascita» in (gruppo, numero di riga, campo)."""
    parti = _normalizza(nome).split("_")
    for indice, parte in enumerate(parti):
        if parte.isdigit() and 0 < indice < len(parti) - 1:
            return "_".join(parti[:indice]), int(parte), "_".join(parti[indice + 1:])
    return "", 0, ""


def _altezza(campo: Mapping[str, Any]) -> float:
    return float((list(campo.get("rettangolo") or [0, 0, 0, 0]))[3])


def impaginazioni_dichiarate(campi: Iterable[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    """Le impaginazioni che il modulo si porta dietro, per numero di righe.

    Un modulo a righe variabili non puo' ridisegnare la griglia della tabella:
    la tiene pronta, una per ogni numero di righe, come caselle grandi quanto
    la tabella chiamate ``impaginazione_4`` … ``impaginazione_10``, e mostra
    quella che serve. Qui si leggono: se il modulo non le dichiara, le righe
    non si aggiungono e si dice perche' — meglio non aggiungerne che
    scriverne una fuori dalla griglia.
    """
    trovate: dict[int, dict[str, Any]] = {}
    for campo in campi:
        nome = _normalizza(campo.get("nome"))
        if not nome.startswith(PREFISSO_IMPAGINAZIONE):
            continue
        coda = nome[len(PREFISSO_IMPAGINAZIONE):]
        if coda.isdigit():
            trovate.setdefault(int(coda), dict(campo))
    return trovate


def caselle_per_impaginazione(campi: Iterable[Mapping[str, Any]], righe: int) -> dict[str, int]:
    """Quale casella di ogni campo vale nell'impaginazione con questo numero di righe.

    Ogni campo della tabella esiste in tante copie quante sono le
    impaginazioni che lo contengono, e piu' righe stanno nel foglio piu' ogni
    cella e' bassa: ordinando le copie per altezza decrescente, la prima vale
    per l'impaginazione piu' corta che contiene quella riga, e si prosegue
    fino a dieci. Il criterio e' la geometria del documento, non una scelta
    nostra.
    """
    elenco = [dict(c) for c in campi]
    minime = min((n for n in impaginazioni_dichiarate(elenco)), default=0)
    per_campo: dict[str, list[dict[str, Any]]] = {}
    for campo in elenco:
        gruppo, numero, _coda = _riga_dal_nome(str(campo.get("nome") or ""))
        if gruppo and numero:
            per_campo.setdefault(str(campo.get("nome")), []).append(campo)
    scelte: dict[str, int] = {}
    for nome, varianti in per_campo.items():
        _gruppo, numero, _coda = _riga_dal_nome(nome)
        prima = max(numero, minime or numero)
        indice = righe - prima
        if indice < 0 or indice >= len(varianti):
            continue
        ordinate = sorted(varianti, key=lambda c: (-_altezza(c), _cima(c)))
        scelte[nome] = int(ordinate[indice].get("xref") or 0)
    return scelte


def _cima(campo: Mapping[str, Any]) -> float:
    return float((list(campo.get("rettangolo") or [0, 0, 0, 0]))[1])


def righe_gia_mostrate(campi: Iterable[Mapping[str, Any]]) -> int:
    """Quante righe della tabella il modulo mostra adesso."""
    numeri = [
        _riga_dal_nome(str(c.get("nome") or ""))[1]
        for c in campi
        if c.get("visibile", True) and _riga_dal_nome(str(c.get("nome") or ""))[0]
    ]
    return max(numeri) if numeri else 0


def righe_da_attivare(campi: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Le righe in piu' che il modulo puo' mostrare, in ordine di tabella.

    Solo fin dove il modulo ha un'impaginazione pronta: oltre, la riga non
    esiste e non si inventa (il modulo stesso avverte che il foglio A4 non
    ne regge altre).
    """
    elenco = [dict(c) for c in campi]
    impaginazioni = impaginazioni_dichiarate(elenco)
    mostrate = righe_gia_mostrate(elenco)
    if not impaginazioni or not mostrate:
        return []
    massimo = max(impaginazioni)
    per_riga: dict[int, dict[str, dict[str, Any]]] = {}
    for campo in elenco:
        gruppo, numero, _coda = _riga_dal_nome(str(campo.get("nome") or ""))
        if not gruppo or campo.get("sola_lettura") or numero <= mostrate or numero > massimo:
            continue
        per_riga.setdefault(numero, {}).setdefault(str(campo.get("nome")), dict(campo))
    risultato: list[dict[str, Any]] = []
    for numero in sorted(per_riga):
        campi_riga = sorted(per_riga[numero].values(), key=lambda c: _cima(c))
        risultato.append({
            "numero": numero,
            "pagina": int(campi_riga[0].get("pagina") or 1) if campi_riga else 1,
            "campi": [{k: v for k, v in c.items() if k != "xref"} for c in campi_riga],
        })
    return risultato


__all__ = [
    "CORRISPONDENZE",
    "PREFISSO_IMPAGINAZIONE",
    "caselle_per_impaginazione",
    "impaginazioni_dichiarate",
    "righe_gia_mostrate",
    "PREFISSI_PRIMA_RIGA",
    "proposte_dalla_scheda",
    "righe_da_attivare",
]
