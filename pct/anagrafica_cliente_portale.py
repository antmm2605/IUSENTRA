"""L'anagrafica che il portale mostra al cliente: prima quello che lo studio sa.

Il portale chiedeva al cliente dati che lo studio aveva gia' in scheda. Non e'
solo scortese: un modulo vuoto invita a riscrivere, e quello che viene
riscritto puo' divergere dal fascicolo. Qui la scheda dello studio diventa la
proposta di partenza; quello che il cliente ha scritto di suo resta la sua
parola e vince sempre.

La distinzione fra le due origini non si perde: `origine_dei_campi` dice, campo
per campo, se il valore viene dalla scheda dello studio (da confermare) o dal
cliente (gia' confermato). Serve a non spacciare per «dichiarato dal cliente»
un dato che il cliente non ha mai letto.

Base normativa: GDPR 2016/679 art. 5 § 1 lett. d) (esattezza dei dati) e
art. 16 (diritto di rettifica): mettere l'interessato in condizione di
verificare e correggere i propri dati e' un adempimento, non una comodita'.
"""

from __future__ import annotations

import re
from typing import Any

#: I campi dell'anagrafica del portale, nell'ordine in cui la scheda li mostra.
CAMPI_PORTALE: tuple[str, ...] = (
    "displayName",
    "email",
    "phone",
    "fiscalCode",
    "birthDate",
    "birthPlace",
    "address",
    "cap",
    "city",
    "province",
    "pec",
    "vatNumber",
    "profession",
    "identityExpiresAt",
)

#: Campi che la scheda cliente dello studio non conosce: restano del cliente.
#: La professione non e' un campo di `pct.clienti.Cliente`; dichiararlo qui
#: evita di cercarla ogni volta in un posto dove non c'e'.
CAMPI_SOLO_DEL_CLIENTE: tuple[str, ...] = ("profession",)


def _testo(valore: Any) -> str:
    return " ".join(str(valore if valore is not None else "").split()).strip()


def _primo_indirizzo(cliente: Any) -> Any:
    """L'indirizzo da proporre: residenza, poi domicilio, poi sede legale.

    Una persona fisica ha la residenza, una societa' la sede legale; qualche
    scheda ha solo il domicilio eletto. Si prende il primo che ha una via.
    """
    for nome in ("indirizzo_residenza", "indirizzo_domicilio", "indirizzo_sede_legale"):
        indirizzo = getattr(cliente, nome, None)
        if indirizzo is not None and _testo(getattr(indirizzo, "via", "")):
            return indirizzo
    return getattr(cliente, "indirizzo_residenza", None)


def _via_e_civico(indirizzo: Any) -> str:
    via = _testo(getattr(indirizzo, "via", ""))
    civico = _testo(getattr(indirizzo, "civico", ""))
    return _testo(f"{via} {civico}") if via else ""


def separa_via_e_civico(indirizzo: str) -> tuple[str, str]:
    """Divide «Via Roma 12/A» in via e civico, ma solo quando e' evidente.

    La scheda dello studio tiene via e civico in due campi; il portale ne ha
    uno solo. Si stacca l'ultima parola solo se ha la forma di un civico
    (cifre, eventualmente con lettera o barra: 87, 12/A, 5bis). In ogni altro
    caso l'indirizzo resta intero nella via: meglio un campo civico vuoto che
    un civico inventato.
    """
    testo = _testo(indirizzo)
    if not testo:
        return "", ""
    parti = testo.split(" ")
    if len(parti) < 2:
        return testo, ""
    ultima = parti[-1]
    if re.fullmatch(r"\d+[/\-]?[A-Za-z]{0,3}", ultima) and any(ch.isdigit() for ch in ultima):
        return " ".join(parti[:-1]), ultima
    return testo, ""


def anagrafica_dallo_studio(cliente: Any) -> dict[str, str]:
    """I campi del portale ricavati dalla scheda cliente dello studio.

    Nessuna invenzione: ogni valore viene da un campo dichiarato di
    `pct.clienti.Cliente`. Cio' che la scheda non ha resta stringa vuota.
    """
    if cliente is None:
        return {campo: "" for campo in CAMPI_PORTALE}
    recapiti = getattr(cliente, "recapiti", None)
    documento = getattr(cliente, "documento", None)
    indirizzo = _primo_indirizzo(cliente)
    return {
        "displayName": _testo(getattr(cliente, "nome_completo", "")),
        "email": _testo(getattr(recapiti, "email", "")),
        "phone": _testo(getattr(recapiti, "cellulare", "")) or _testo(getattr(recapiti, "telefono", "")),
        "fiscalCode": _testo(getattr(cliente, "identificativo_fiscale", "")),
        "birthDate": _testo(getattr(cliente, "data_nascita", ""))[:10],
        "birthPlace": _testo(getattr(cliente, "luogo_nascita", "")),
        "address": _via_e_civico(indirizzo),
        "cap": _testo(getattr(indirizzo, "cap", "")),
        "city": _testo(getattr(indirizzo, "comune", "")),
        "province": _testo(getattr(indirizzo, "provincia", "")).upper()[:2],
        "pec": _testo(getattr(recapiti, "pec", "")),
        "vatNumber": _testo(getattr(cliente, "partita_iva", "")),
        "profession": "",
        "identityExpiresAt": _testo(getattr(documento, "data_scadenza", ""))[:10],
    }


def unisci_anagrafica(
    *,
    dallo_studio: dict[str, Any] | None,
    dal_cliente: dict[str, Any] | None,
) -> dict[str, str]:
    """La scheda da mostrare: il cliente vince, lo studio riempie il resto."""
    studio = dallo_studio or {}
    cliente = dal_cliente or {}
    unita: dict[str, str] = {}
    for campo in CAMPI_PORTALE:
        scritto = _testo(cliente.get(campo))
        unita[campo] = scritto or _testo(studio.get(campo))
    return unita


def origine_dei_campi(
    *,
    dallo_studio: dict[str, Any] | None,
    dal_cliente: dict[str, Any] | None,
) -> dict[str, str]:
    """Da dove viene ogni valore: «cliente», «studio» o vuoto se manca.

    Il portale usa questa mappa per dire all'interessato che cosa deve solo
    confermare e che cosa deve ancora scrivere, senza far passare per
    dichiarato dal cliente un dato che il cliente non ha mai visto.
    """
    studio = dallo_studio or {}
    cliente = dal_cliente or {}
    origini: dict[str, str] = {}
    for campo in CAMPI_PORTALE:
        if _testo(cliente.get(campo)):
            origini[campo] = "cliente"
        elif _testo(studio.get(campo)):
            origini[campo] = "studio"
        else:
            origini[campo] = ""
    return origini


#: Come ogni campo del portale si riporta sulla scheda cliente dello studio.
#: La chiave e' il campo del portale, il valore dice su quale struttura di
#: `pct.clienti.Cliente` vive quel dato e con quale nome. Le strutture sono
#: quelle dichiarate nella dataclass: campo piatto, `recapiti`, l'indirizzo di
#: residenza, `documento`. Un campo che lo studio non conosce non compare qui.
DESTINAZIONE_SULLA_SCHEDA: dict[str, tuple[str, str]] = {
    "email": ("recapiti", "email"),
    "phone": ("recapiti", "cellulare"),
    "pec": ("recapiti", "pec"),
    "fiscalCode": ("cliente", "codice_fiscale"),
    "vatNumber": ("cliente", "partita_iva"),
    "birthDate": ("cliente", "data_nascita"),
    "birthPlace": ("cliente", "luogo_nascita"),
    "address": ("indirizzo", "via"),
    "cap": ("indirizzo", "cap"),
    "city": ("indirizzo", "comune"),
    "province": ("indirizzo", "provincia"),
    "identityExpiresAt": ("documento", "data_scadenza"),
}


def aggiornamenti_per_la_scheda(
    cliente: Any,
    anagrafica: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, str]], dict[str, tuple[str, str]]]:
    """Che cosa scrivere sulla scheda dello studio e che cosa invece diverge.

    Restituisce due cose distinte:

    - gli aggiornamenti, raggruppati per struttura (`cliente`, `recapiti`,
      `indirizzo`, `documento`), cioe' i campi che sulla scheda sono **vuoti**
      e che il cliente ha compilato: li si scrive;
    - le divergenze: campi che la scheda ha gia' valorizzati **in modo diverso**
      da quanto dichiara il cliente. Non si sovrascrivono di nascosto — il dato
      del fascicolo e' l'atto dello studio — ma non si perdono: chi chiama le
      segnala allo studio, che decide (GDPR art. 16, diritto di rettifica).

    `nome` e `cognome` non si toccano: il portale ha un solo campo
    «Nome e cognome» e dividerlo sarebbe un'invenzione.
    """
    campi = anagrafica or {}
    aggiornamenti: dict[str, dict[str, str]] = {}
    divergenze: dict[str, tuple[str, str]] = {}
    if cliente is None:
        return aggiornamenti, divergenze
    attuale = anagrafica_dallo_studio(cliente)
    for campo, (struttura, attributo) in DESTINAZIONE_SULLA_SCHEDA.items():
        scritto = _testo(campi.get(campo))
        if not scritto:
            continue
        gia_in_scheda = _testo(attuale.get(campo))
        if not gia_in_scheda:
            if campo == "address":
                via, civico = separa_via_e_civico(scritto)
                aggiornamenti.setdefault(struttura, {})["via"] = via
                if civico:
                    aggiornamenti[struttura]["civico"] = civico
                continue
            aggiornamenti.setdefault(struttura, {})[attributo] = scritto
        elif gia_in_scheda.casefold() != scritto.casefold():
            divergenze[campo] = (gia_in_scheda, scritto)
    return aggiornamenti, divergenze


__all__ = [
    "CAMPI_PORTALE",
    "CAMPI_SOLO_DEL_CLIENTE",
    "DESTINAZIONE_SULLA_SCHEDA",
    "aggiornamenti_per_la_scheda",
    "separa_via_e_civico",
    "anagrafica_dallo_studio",
    "origine_dei_campi",
    "unisci_anagrafica",
]
