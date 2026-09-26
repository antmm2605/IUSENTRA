"""Il presidio delle parti: dalle epigrafi lette all'anagrafica del fascicolo.

L'archivio delle letture contiene le parti lette negli atti (categoria «parte»).
Questo presidio **scrive**: le parti certe — lato riconosciuto dal difensore
dello studio o dal nome del cliente, codice fiscale valido o difensore della
controparte letto nell'epigrafe — entrano da sole fra le parti del fascicolo
(anagrafica soggetti), senza doppioni: se il soggetto esiste già (stesso
codice fiscale, stesso nome) si collega quello. Il cliente del fascicolo non
si duplica. Le altre letture (testimoni, CTU, parti senza lato) restano
proposte che l'avvocato aggiunge con un clic.

Quando il fascicolo non ha ancora controparte o difensore della controparte,
si scrivono anche lì, con la stessa prova.

Base normativa: art. 163 c.p.c. (citazione), art. 125 c.p.c. (atti di parte),
art. 40 c.p.a. (ricorso), art. 132 c.p.c. (sentenza) per l'epigrafe; D.M.
23/12/1976 per il codice fiscale; art. 1 R.D. 1611/1933 per l'Avvocatura dello
Stato.
"""

from __future__ import annotations

import logging
from typing import Any

from pct.archivio_letture.parti_fascicolo import (
    RUOLO_SOGGETTO,
    ParteDelFascicolo,
    cognome_e_nome,
    confronta_con_fascicolo,
    parti_lette,
    stesso_nome,
    tipo_soggetto,
)

logger = logging.getLogger(__name__)

NOTA_PARTE = "Parte letta dagli atti del fascicolo (epigrafe)."


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _soggetto_esistente(gestione: Any, voce: ParteDelFascicolo) -> Any:
    """Lo stesso soggetto già in anagrafica: prima il codice fiscale, poi il nome se non c'è conflitto di codice."""
    tutti = list(gestione.tutti())
    if voce.codice_fiscale:
        for soggetto in tutti:
            codici = {str(getattr(soggetto, "codice_fiscale", "") or "").upper(), str(getattr(soggetto, "partita_iva", "") or "").upper()}
            if voce.codice_fiscale.upper() in codici:
                return soggetto
    for soggetto in tutti:
        codice = str(getattr(soggetto, "codice_fiscale", "") or "").upper()
        if voce.codice_fiscale and codice and codice != voce.codice_fiscale.upper():
            continue
        if stesso_nome(voce.nome, getattr(soggetto, "nome_completo", "")):
            return soggetto
    return None


def _nuovo_soggetto(gestione: Any, voce: ParteDelFascicolo) -> Any:
    from pct.soggetti import TipoSoggetto

    tipo = TipoSoggetto(tipo_soggetto(voce.nome, voce.codice_fiscale, voce.ruolo))
    dati: dict[str, Any] = {"note": NOTA_PARTE, "tag": ["letta dagli atti"]}
    if tipo in (TipoSoggetto.PERSONA_FISICA, TipoSoggetto.PROFESSIONISTA):
        cognome, nome = cognome_e_nome(voce.nome, voce.codice_fiscale)
        dati.update(cognome=cognome, nome=nome, codice_fiscale=voce.codice_fiscale if len(voce.codice_fiscale) == 16 else "")
        if voce.ruolo == "difensore_controparte":
            dati["qualifica"] = "Avvocato"
        elif voce.ruolo == "ctu":
            dati["qualifica"] = "Consulente tecnico d'ufficio"
    else:
        dati.update(ragione_sociale=voce.nome, partita_iva=voce.codice_fiscale if len(voce.codice_fiscale) == 11 else "",
                    codice_fiscale=voce.codice_fiscale)
    return gestione.crea(tipo, **dati)


def collega_parte(fascicolo: Any, voce: ParteDelFascicolo, *, gestione: Any = None) -> str:
    """Collega la parte al fascicolo (creandola in anagrafica se manca); restituisce l'id del soggetto."""
    from pct.soggetti import RuoloSoggetto

    if gestione is None:
        from web.helpers import get_soggetti

        gestione = get_soggetti()
    soggetto = _soggetto_esistente(gestione, voce) or _nuovo_soggetto(gestione, voce)
    nota = NOTA_PARTE + (f" Difensore: {voce.difensore}." if voce.difensore else "") + (f" Posizione: {voce.posizione}." if voce.posizione else "")
    gestione.aggiungi_parte(_testo(getattr(fascicolo, "id", "")), soggetto.id, RuoloSoggetto(RUOLO_SOGGETTO.get(voce.ruolo, "ALTRO")), note=nota)
    return str(soggetto.id)


def _completa_intestazione(fascicolo: Any, voci: list[ParteDelFascicolo]) -> dict[str, str]:
    """Controparte e suo difensore nell'intestazione del fascicolo, solo se vuote."""
    campi: dict[str, str] = {}
    if not _testo(getattr(fascicolo, "controparte", "")):
        controparti = [v.nome for v in voci if v.ruolo == "controparte" and v.certa]
        if controparti:
            campi["controparte"] = ", ".join(controparti[:3])
    if not _testo(getattr(fascicolo, "avvocato_controparte", "")):
        difensori = [v.nome for v in voci if v.ruolo == "difensore_controparte" and v.certa]
        if difensori:
            campi["avvocato_controparte"] = difensori[0]
    if campi:
        try:
            from web.helpers import get_fascicoli

            get_fascicoli().aggiorna(_testo(getattr(fascicolo, "id", "")), **campi)
        except Exception:
            logger.exception("Intestazione del fascicolo %s non completata dalle parti lette", getattr(fascicolo, "id", ""))
            return {}
    return campi


def consegna_parti(fascicolo: Any, fatti: list[Any], *, gestione: Any = None) -> list[dict[str, str]]:
    """Consegnatario del presidio «parti»: un esito per ogni fatto consegnato."""
    if gestione is None:
        from web.helpers import get_soggetti

        gestione = get_soggetti()
    fid = _testo(getattr(fascicolo, "id", ""))
    voci = confronta_con_fascicolo(parti_lette(fatti), nome_cliente=_testo(getattr(fascicolo, "nome_cliente", "")),
                                   parti_esistenti=gestione.parti_fascicolo(fid))
    esiti: list[dict[str, str]] = []
    per_fatto: dict[str, ParteDelFascicolo] = {fatto_id: voce for voce in voci for fatto_id in voce.fatti}
    for fatto in fatti:
        voce = per_fatto.get(str(getattr(fatto, "id", "") or ""))
        if voce is None:
            esiti.append({"fatto_id": fatto.id, "stato": "non_pertinente", "motivo": "Lettura non riconducibile a una parte."})
        elif voce.e_il_cliente:
            esiti.append({"fatto_id": fatto.id, "stato": "non_pertinente", "motivo": "È il cliente del fascicolo."})
        elif voce.gia_presente:
            esiti.append({"fatto_id": fatto.id, "stato": "consegnato", "riferimento": voce.id_soggetto, "motivo": "Parte già presente nel fascicolo."})
        elif not voce.certa:
            esiti.append({"fatto_id": fatto.id, "stato": "non_pertinente", "motivo": "Lato o identità da confermare: resta fra le proposte."})
        else:
            try:
                voce.id_soggetto = collega_parte(fascicolo, voce, gestione=gestione)
                voce.gia_presente = True
                esiti.append({"fatto_id": fatto.id, "stato": "consegnato", "riferimento": voce.id_soggetto})
            except Exception as exc:
                esiti.append({"fatto_id": fatto.id, "stato": "rifiutato", "motivo": f"{type(exc).__name__}: {exc}"[:200]})
    _completa_intestazione(fascicolo, voci)
    return esiti


def parti_proposte(fascicolo: Any, *, gestione: Any = None) -> list[dict[str, Any]]:
    """Le parti lette dagli atti, con lo stato rispetto al fascicolo (per il riquadro «Parti lette dagli atti»)."""
    from web.services.archivio_letture_runtime import fatti_fascicolo

    if gestione is None:
        from web.helpers import get_soggetti

        gestione = get_soggetti()
    fatti = fatti_fascicolo(fascicolo, categoria="parte")
    voci = confronta_con_fascicolo(parti_lette(fatti), nome_cliente=_testo(getattr(fascicolo, "nome_cliente", "")),
                                   parti_esistenti=gestione.parti_fascicolo(_testo(getattr(fascicolo, "id", ""))))
    return [voce.to_dict() for voce in voci]


def aggiungi_parte_proposta(fascicolo: Any, nome: str, ruolo: str, *, gestione: Any = None) -> dict[str, Any]:
    """L'avvocato conferma una proposta: la parte entra nel fascicolo con il ruolo scelto."""
    from web.services.archivio_letture_runtime import fatti_fascicolo

    if gestione is None:
        from web.helpers import get_soggetti

        gestione = get_soggetti()
    if ruolo not in RUOLO_SOGGETTO:
        raise ValueError("Ruolo non riconosciuto.")
    voci = parti_lette(fatti_fascicolo(fascicolo, categoria="parte"))
    voce = next((v for v in voci if stesso_nome(v.nome, nome)), None)
    if voce is None:
        raise LookupError("La parte non è fra quelle lette dagli atti del fascicolo.")
    voce.ruolo = ruolo
    return {"idSoggetto": collega_parte(fascicolo, voce, gestione=gestione), "nome": voce.nome, "ruolo": ruolo}


__all__ = ["NOTA_PARTE", "aggiungi_parte_proposta", "collega_parte", "consegna_parti", "parti_proposte"]
