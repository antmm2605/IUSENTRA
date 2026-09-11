"""Controparti aggiuntive inserite dal form Nuovo/Modifica fascicolo.

Il form invia `controparti_aggiuntive_json`: un elenco di parti oltre alla controparte principale,
scelte fra i Soggetti dello studio, dai registri pubblici consultati in locale (ReGIndE,
Registro PP.AA., INI-PEC) oppure inserite a mano. Ogni voce diventa (o riusa) una scheda in
Soggetti e Parti ed e collegata al fascicolo con il ruolo indicato.

Regole:
- il dato del registro e un suggerimento: l'avvocato lo vede nel form e lo conferma salvando;
- nessun duplicato: si riusa la scheda con lo stesso codice fiscale/partita IVA e si completa solo la
  PEC mancante, senza sovrascrivere dati gia presenti;
- una voce che coincide con il cliente dello studio non viene collegata come controparte;
- la validazione avviene prima di creare il fascicolo, cosi un dato errato non lascia fascicoli a meta.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

from pct.clienti import Recapiti
from pct.soggetti import RuoloSoggetto, TipoSoggetto, soggetto_coincide_con_cliente

MAX_CONTROPARTI_AGGIUNTIVE = 20
FONTI_CONTROPARTE = {
    "soggetti": "Soggetti dello studio",
    "reginde": "ReGIndE",
    "registro_ppaa": "Registro PP.AA.",
    "inipec": "INI-PEC",
    "manuale": "Inserimento manuale",
}
RUOLI_AMMESSI = {
    "CONTROPARTE": RuoloSoggetto.CONTROPARTE,
    "DIFENSORE_CONTROPARTE": RuoloSoggetto.DIFENSORE_CONTROPARTE,
}
_TIPI_PERSONA = {TipoSoggetto.PERSONA_FISICA, TipoSoggetto.PROFESSIONISTA}
_CODICE_FISCALE_RE = re.compile(r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]")
_NUMERICO_11_RE = re.compile(r"[0-9]{11}")
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass(frozen=True)
class ControparteAggiuntiva:
    nome: str
    identificativo: str
    tipo: TipoSoggetto
    ruolo: RuoloSoggetto
    fonte: str
    id_soggetto: str = ""
    pec: str = ""
    email: str = ""
    telefono: str = ""
    persona_nome: str = ""
    persona_cognome: str = ""

    @property
    def fonte_label(self) -> str:
        return FONTI_CONTROPARTE.get(self.fonte, FONTI_CONTROPARTE["manuale"])


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def normalizza_identificativo(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def identificativo_valido(value: str) -> bool:
    return bool(_CODICE_FISCALE_RE.fullmatch(value) or _NUMERICO_11_RE.fullmatch(value))


def _tipo(value: Any) -> TipoSoggetto:
    try:
        return TipoSoggetto(_text(value) or TipoSoggetto.PERSONA_GIURIDICA.value)
    except ValueError:
        return TipoSoggetto.PERSONA_GIURIDICA


def leggi_controparti_aggiuntive(raw: Any, *, gestore_soggetti: Any) -> list[ControparteAggiuntiva]:
    """Legge e valida l'elenco inviato dal form; solleva ValueError con un messaggio per l'avvocato."""
    testo = str(raw or "").strip()
    if not testo:
        return []
    try:
        payload = json.loads(testo)
    except ValueError as exc:
        raise ValueError("L'elenco delle altre controparti non è leggibile: ricarica la pagina e riprova.") from exc
    if not isinstance(payload, list):
        raise ValueError("L'elenco delle altre controparti non è leggibile: ricarica la pagina e riprova.")
    righe = [item for item in payload if isinstance(item, dict)]
    if len(righe) > MAX_CONTROPARTI_AGGIUNTIVE:
        raise ValueError(f"Puoi aggiungere al massimo {MAX_CONTROPARTI_AGGIUNTIVE} controparti per volta.")
    controparti: list[ControparteAggiuntiva] = []
    visti: set[str] = set()
    for posizione, item in enumerate(righe, start=1):
        riga = _leggi_riga(item, posizione, gestore_soggetti=gestore_soggetti)
        if riga is None:
            continue
        chiave = f"{riga.ruolo.value}|{riga.id_soggetto or riga.identificativo}"
        if chiave in visti:
            continue
        visti.add(chiave)
        controparti.append(riga)
    return controparti


def _leggi_riga(item: dict[str, Any], posizione: int, *, gestore_soggetti: Any) -> ControparteAggiuntiva | None:
    fonte = _text(item.get("fonte")).lower() or "manuale"
    fonte = fonte if fonte in FONTI_CONTROPARTE else "manuale"
    ruolo = RUOLI_AMMESSI.get(_text(item.get("ruolo")).upper() or "CONTROPARTE")
    if ruolo is None:
        raise ValueError(f"Controparte {posizione}: ruolo non valido.")
    id_soggetto = _text(item.get("id_soggetto"))
    if id_soggetto:
        soggetto = gestore_soggetti.get(id_soggetto)
        if not soggetto:
            raise ValueError(f"Controparte {posizione}: il soggetto selezionato non è più disponibile in anagrafica.")
        return ControparteAggiuntiva(
            nome=soggetto.nome_completo,
            identificativo=normalizza_identificativo(soggetto.identificativo),
            tipo=soggetto.tipo,
            ruolo=ruolo,
            fonte="soggetti",
            id_soggetto=soggetto.id,
        )
    nome = _text(item.get("nome"))
    identificativo = normalizza_identificativo(item.get("identificativo"))
    if not nome and not identificativo:
        return None
    etichetta = nome or f"n. {posizione}"
    if not nome:
        raise ValueError(f"Controparte {posizione}: manca il nome o la ragione sociale.")
    if not identificativo:
        raise ValueError(f"Controparte {etichetta}: manca il codice fiscale o la partita IVA.")
    if not identificativo_valido(identificativo):
        raise ValueError(f"Controparte {etichetta}: codice fiscale o partita IVA non valido.")
    pec = _text(item.get("pec")).lower()
    email = _text(item.get("email")).lower()
    for label, valore in (("PEC", pec), ("email", email)):
        if valore and not _EMAIL_RE.fullmatch(valore):
            raise ValueError(f"Controparte {etichetta}: {label} non valida.")
    return ControparteAggiuntiva(
        nome=nome,
        identificativo=identificativo,
        tipo=_tipo(item.get("tipo")),
        ruolo=ruolo,
        fonte=fonte,
        pec=pec,
        email=email,
        telefono=_text(item.get("telefono")),
        persona_nome=_text(item.get("persona_nome")),
        persona_cognome=_text(item.get("persona_cognome")),
    )


def _soggetto_per_identificativo(gestore_soggetti: Any, identificativo: str) -> Any:
    for soggetto in gestore_soggetti.cerca(q=identificativo):
        if normalizza_identificativo(soggetto.identificativo) == identificativo:
            return soggetto
        if identificativo in {
            normalizza_identificativo(getattr(soggetto, "codice_fiscale", "")),
            normalizza_identificativo(getattr(soggetto, "partita_iva", "")),
        }:
            return soggetto
    return None


def _nome_persona(nome_completo: str, *, nome: str = "", cognome: str = "") -> tuple[str, str]:
    if nome or cognome:
        return nome, cognome
    parti = nome_completo.split()
    if len(parti) <= 1:
        return nome_completo, ""
    return parti[0], " ".join(parti[1:])


def _crea_soggetto(gestore_soggetti: Any, controparte: ControparteAggiuntiva, *, momento: str) -> Any:
    common: dict[str, Any] = {
        "recapiti": Recapiti(pec=controparte.pec, email=controparte.email, telefono=controparte.telefono),
        "note": f"Creato durante {momento} del fascicolo. Fonte: {controparte.fonte_label}.",
        "tag": ["controparte", controparte.fonte],
    }
    if controparte.ruolo == RuoloSoggetto.DIFENSORE_CONTROPARTE:
        common["qualifica"] = "Avvocato"
        if controparte.fonte == "reginde":
            common["ordine"] = "ReGIndE"
    if controparte.tipo in _TIPI_PERSONA:
        nome, cognome = _nome_persona(
            controparte.nome, nome=controparte.persona_nome, cognome=controparte.persona_cognome
        )
        return gestore_soggetti.crea(
            tipo=controparte.tipo,
            nome=nome,
            cognome=cognome,
            codice_fiscale=controparte.identificativo,
            **common,
        )
    partita_iva = controparte.identificativo if _NUMERICO_11_RE.fullmatch(controparte.identificativo) else ""
    return gestore_soggetti.crea(
        tipo=controparte.tipo,
        ragione_sociale=controparte.nome,
        codice_fiscale="" if partita_iva and controparte.tipo != TipoSoggetto.PUBBLICA_AMMINISTRAZIONE else controparte.identificativo,
        partita_iva=partita_iva if controparte.tipo != TipoSoggetto.PUBBLICA_AMMINISTRAZIONE else "",
        **common,
    )


def _completa_pec_mancante(gestore_soggetti: Any, soggetto: Any, pec: str) -> Any:
    recapiti = getattr(soggetto, "recapiti", None)
    if not pec or recapiti is None or str(getattr(recapiti, "pec", "") or "").strip():
        return soggetto
    return gestore_soggetti.aggiorna(soggetto.id, recapiti=replace(recapiti, pec=pec))


def _probe(controparte: ControparteAggiuntiva) -> SimpleNamespace:
    """Record minimo per il confronto con i clienti prima di creare una nuova scheda."""
    persona = controparte.tipo in _TIPI_PERSONA
    nome, cognome = (
        _nome_persona(controparte.nome, nome=controparte.persona_nome, cognome=controparte.persona_cognome)
        if persona
        else ("", "")
    )
    return SimpleNamespace(
        id_cliente="",
        nome=nome,
        cognome=cognome,
        ragione_sociale="" if persona else controparte.nome,
        codice_fiscale=controparte.identificativo,
        partita_iva=controparte.identificativo,
    )


@dataclass(frozen=True)
class EsitoControparti:
    collegate: tuple[str, ...]
    escluse_cliente: tuple[str, ...]

    def messaggio(self) -> str:
        parti: list[str] = []
        if self.collegate:
            parti.append(f"Collegate altre {len(self.collegate)} parti: {', '.join(self.collegate)}.")
        if self.escluse_cliente:
            parti.append(f"Non collegate perché coincidono con il cliente: {', '.join(self.escluse_cliente)}.")
        return " ".join(parti)


def collega_controparti_aggiuntive(
    gestore_soggetti: Any,
    clienti: list[Any],
    id_fascicolo: str,
    controparti: list[ControparteAggiuntiva],
    *,
    momento: str = "l'apertura",
) -> EsitoControparti:
    """Crea o riusa le schede soggetto e le collega al fascicolo con il ruolo scelto."""
    collegate: list[str] = []
    escluse: list[str] = []
    for controparte in controparti:
        soggetto = (
            gestore_soggetti.get(controparte.id_soggetto)
            if controparte.id_soggetto
            else _soggetto_per_identificativo(gestore_soggetti, controparte.identificativo)
        )
        if soggetto is not None and soggetto_coincide_con_cliente(soggetto, clienti):
            escluse.append(controparte.nome)
            continue
        if soggetto is None:
            if soggetto_coincide_con_cliente(_probe(controparte), clienti):
                escluse.append(controparte.nome)
                continue
            soggetto = _crea_soggetto(gestore_soggetti, controparte, momento=momento)
        else:
            soggetto = _completa_pec_mancante(gestore_soggetti, soggetto, controparte.pec)
        gestore_soggetti.aggiungi_parte(
            id_fascicolo,
            soggetto.id,
            controparte.ruolo,
            note=f"Aggiunta durante {momento} del fascicolo ({controparte.fonte_label}).",
        )
        collegate.append(soggetto.nome_completo)
    return EsitoControparti(collegate=tuple(collegate), escluse_cliente=tuple(escluse))


__all__ = [
    "FONTI_CONTROPARTE",
    "MAX_CONTROPARTI_AGGIUNTIVE",
    "ControparteAggiuntiva",
    "EsitoControparti",
    "collega_controparti_aggiuntive",
    "identificativo_valido",
    "leggi_controparti_aggiuntive",
    "normalizza_identificativo",
]
