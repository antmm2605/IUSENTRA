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


__all__ = [
    "CAMPI_PORTALE",
    "CAMPI_SOLO_DEL_CLIENTE",
    "anagrafica_dallo_studio",
    "origine_dei_campi",
    "unisci_anagrafica",
]
