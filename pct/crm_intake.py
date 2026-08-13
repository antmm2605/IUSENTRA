"""CRM di studio: intake dei potenziali clienti (lead) con verifica conflitti.

Base deontologica: art. 23 (incarico) e art. 24 (conflitto di interessi,
dovere di astensione) del Codice Deontologico Forense; art. 28 (titolarita'
dello studio nei rapporti col cliente). La pipeline registra la richiesta di
assistenza, verifica i conflitti PRIMA dell'assunzione dell'incarico e
conduce fino a preventivo (L. 247/2012 art. 13: preventivo scritto) e
onboarding — riusando i moduli esistenti (``pct/preventivi.py``,
``pct/workflow_onboarding.py``); l'adeguata verifica antiriciclaggio resta in
``pct/antiriciclaggio.py`` e si aggancia alla conversione in cliente.

Verifica conflitti fail-closed:
- match su codice fiscale/partita IVA → esito certo;
- match solo sul nome → "da valutare" (omonimie possibili): la decisione
  resta all'avvocato, il software non assolve ne' condanna;
- il lead non diventa cliente finche' la verifica non e' stata eseguita.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

FONTE_DEONTOLOGICA = "Codice Deontologico Forense artt. 23-24; L. 247/2012 art. 13"

# Pipeline di intake (stati ordinati).
STATI_LEAD = ("NUOVO", "CONTATTATO", "APPUNTAMENTO", "PREVENTIVO", "VINTO", "PERSO")

FONTI_LEAD = (
    "passaparola",
    "sito_studio",
    "referral_professionista",
    "directory_ordine",
    "social",
    "altro",
)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm_fiscale(value: Any) -> str:
    return _norm(value).upper().replace(" ", "")


def _norm_nome(value: Any) -> str:
    return _norm(value).casefold()


@dataclass
class Lead:
    """Richiesta di assistenza di un potenziale cliente."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12].upper())
    denominazione: str = ""  # nome e cognome o ragione sociale
    codice_fiscale: str = ""
    partita_iva: str = ""
    email: str = ""
    telefono: str = ""
    fonte: str = "altro"
    materia: str = ""  # es. "lavoro", "famiglia", "recupero crediti"
    esigenza: str = ""  # descrizione libera della richiesta
    stato: str = "NUOVO"
    conflitto_verificato: bool = False
    conflitto_esito: dict[str, Any] = field(default_factory=dict)
    cliente_id: str = ""  # valorizzato alla conversione
    preventivo_id: str = ""
    motivo_perso: str = ""
    note: str = ""
    referente: str = ""  # avvocato assegnato
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, dati: dict[str, Any]) -> "Lead":
        return cls(**{k: v for k, v in dict(dati or {}).items() if k in cls.__dataclass_fields__})


def verifica_conflitto_interessi(
    *,
    denominazione: str,
    codice_fiscale: str = "",
    partita_iva: str = "",
    get_clienti: Callable[[], Any] | None = None,
    get_soggetti: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Cerca il potenziale cliente tra anagrafiche e controparti dello studio.

    Ritorna ``{"livello": "nessuno"|"da_valutare"|"potenziale_conflitto",
    "riscontri": [...], "verificato_il": iso}``. Il livello e' informativo:
    la valutazione ex art. 24 CDF resta dell'avvocato.
    """

    nome_norm = _norm_nome(denominazione)
    cf_norm = _norm_fiscale(codice_fiscale)
    piva_norm = _norm_fiscale(partita_iva)
    riscontri: list[dict[str, Any]] = []

    def _match_codici(cf: str, piva: str) -> bool:
        return bool((cf_norm and _norm_fiscale(cf) == cf_norm) or (piva_norm and _norm_fiscale(piva) == piva_norm))

    # Clienti esistenti: un cliente attuale che chiede un nuovo incarico non e'
    # un conflitto, ma va segnalato (posizioni contrapposte in altri giudizi).
    if get_clienti is not None:
        try:
            clienti = list(get_clienti().tutti(stato=None))
        except TypeError:
            clienti = list(get_clienti().tutti())
        except Exception:
            clienti = []
        for cliente in clienti:
            nome_cliente = _norm_nome(
                getattr(cliente, "denominazione", "")
                or f"{getattr(cliente, 'nome', '')} {getattr(cliente, 'cognome', '')}"
            )
            certo = _match_codici(getattr(cliente, "codice_fiscale", ""), getattr(cliente, "partita_iva", ""))
            omonimo = bool(nome_norm and nome_cliente and nome_norm == nome_cliente)
            if certo or omonimo:
                riscontri.append(
                    {
                        "tipo": "cliente_esistente",
                        "certo": certo,
                        "id": str(getattr(cliente, "id", "") or ""),
                        "etichetta": _norm(
                            getattr(cliente, "denominazione", "")
                            or f"{getattr(cliente, 'nome', '')} {getattr(cliente, 'cognome', '')}"
                        ),
                    }
                )

    # Soggetti dello studio: controparti e difensori di controparte sono il
    # cuore della verifica ex art. 24 CDF.
    if get_soggetti is not None:
        try:
            soggetti = list(get_soggetti().tutti())
        except Exception:
            soggetti = []
        for soggetto in soggetti:
            tipo = str(getattr(getattr(soggetto, "tipo", ""), "value", getattr(soggetto, "tipo", "")) or "")
            nome_soggetto = _norm_nome(
                getattr(soggetto, "ragione_sociale", "")
                or f"{getattr(soggetto, 'nome', '')} {getattr(soggetto, 'cognome', '')}"
            )
            certo = _match_codici(getattr(soggetto, "codice_fiscale", ""), getattr(soggetto, "partita_iva", ""))
            omonimo = bool(nome_norm and nome_soggetto and nome_norm == nome_soggetto)
            if not (certo or omonimo):
                continue
            e_controparte = "CONTROPARTE" in tipo.upper()
            riscontri.append(
                {
                    "tipo": "controparte" if e_controparte else "soggetto_noto",
                    "certo": certo,
                    "id": str(getattr(soggetto, "id", "") or ""),
                    "etichetta": _norm(
                        getattr(soggetto, "ragione_sociale", "")
                        or f"{getattr(soggetto, 'nome', '')} {getattr(soggetto, 'cognome', '')}"
                    ),
                    "ruolo": tipo,
                }
            )

    livello = "nessuno"
    if any(r["tipo"] == "controparte" and r["certo"] for r in riscontri):
        livello = "potenziale_conflitto"
    elif riscontri:
        livello = "da_valutare"
    return {
        "livello": livello,
        "riscontri": riscontri,
        "fonte": FONTE_DEONTOLOGICA,
        "verificato_il": datetime.now().isoformat(timespec="seconds"),
    }


class GestioneCrmIntake:
    """Repository tenant-aware dei lead (JSON)."""

    def __init__(self, db_path: str = "./crm/leads.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._leads: dict[str, Lead] = {}
        self._carica()

    def _carica(self) -> None:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            self._leads = {k: Lead.from_dict(v) for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError):
            self._leads = {}

    def _salva(self) -> None:
        self.db_path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._leads.items()}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ CRUD
    def nuovo(self, **campi: Any) -> Lead:
        lead = Lead(**{k: v for k, v in campi.items() if k in Lead.__dataclass_fields__})
        if lead.fonte not in FONTI_LEAD:
            lead.fonte = "altro"
        if not _norm(lead.denominazione):
            raise ValueError("Il lead richiede almeno nome e cognome o denominazione.")
        self._leads[lead.id] = lead
        self._salva()
        return lead

    def get(self, lead_id: str) -> Lead | None:
        return self._leads.get(lead_id)

    def tutti(self, *, stato: str = "") -> list[Lead]:
        rows = [l for l in self._leads.values() if not stato or l.stato == stato]
        rows.sort(key=lambda l: l.creato_il, reverse=True)
        return rows

    def pipeline(self) -> dict[str, list[Lead]]:
        colonne: dict[str, list[Lead]] = {stato: [] for stato in STATI_LEAD}
        for lead in self.tutti():
            colonne.setdefault(lead.stato, []).append(lead)
        return colonne

    # ------------------------------------------------------------------ stati
    def cambia_stato(self, lead_id: str, stato: str, *, motivo_perso: str = "") -> Lead:
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        if stato not in STATI_LEAD:
            raise ValueError(f"Stato non valido: {stato}.")
        if stato == "PERSO" and not _norm(motivo_perso):
            raise ValueError("Per chiudere un lead come perso serve il motivo (migliora le statistiche di intake).")
        if stato == "VINTO" and not lead.conflitto_verificato:
            raise ValueError(
                "Prima di assumere l'incarico va eseguita la verifica conflitti (art. 24 CDF)."
            )
        lead.stato = stato
        lead.motivo_perso = _norm(motivo_perso)
        lead.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return lead

    # ------------------------------------------------------------ conflitti
    def verifica_conflitti(
        self,
        lead_id: str,
        *,
        get_clienti: Callable[[], Any] | None = None,
        get_soggetti: Callable[[], Any] | None = None,
    ) -> dict[str, Any]:
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        esito = verifica_conflitto_interessi(
            denominazione=lead.denominazione,
            codice_fiscale=lead.codice_fiscale,
            partita_iva=lead.partita_iva,
            get_clienti=get_clienti,
            get_soggetti=get_soggetti,
        )
        lead.conflitto_verificato = True
        lead.conflitto_esito = esito
        lead.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return esito

    # ------------------------------------------------------------ conversione
    def converti_in_cliente(
        self,
        lead_id: str,
        *,
        crea_cliente: Callable[[dict[str, Any]], Any],
    ) -> Lead:
        """Conversione in cliente reale: solo dopo la verifica conflitti.

        ``crea_cliente`` riceve i dati anagrafici e ritorna il cliente creato
        (la persistenza resta nel dominio clienti). Il lead passa a VINTO.
        """

        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        if not lead.conflitto_verificato:
            raise ValueError(
                "Prima della conversione va eseguita la verifica conflitti (art. 24 CDF)."
            )
        if lead.cliente_id:
            return lead  # gia' convertito: idempotente
        cliente = crea_cliente(
            {
                "denominazione": lead.denominazione,
                "codice_fiscale": lead.codice_fiscale,
                "partita_iva": lead.partita_iva,
                "email": lead.email,
                "telefono": lead.telefono,
                "note": f"Da intake CRM (fonte: {lead.fonte}). {lead.esigenza}".strip(),
            }
        )
        cliente_id = cliente.get("id", "") if isinstance(cliente, dict) else getattr(cliente, "id", "")
        lead.cliente_id = str(cliente_id or "")
        lead.stato = "VINTO"
        lead.modificato_il = datetime.now().isoformat(timespec="seconds")
        self._salva()
        return lead

    # ------------------------------------------------------------ statistiche
    def statistiche(self) -> dict[str, Any]:
        rows = self.tutti()
        per_stato = {stato: sum(1 for l in rows if l.stato == stato) for stato in STATI_LEAD}
        per_fonte: dict[str, int] = {}
        for lead in rows:
            per_fonte[lead.fonte] = per_fonte.get(lead.fonte, 0) + 1
        chiusi = per_stato["VINTO"] + per_stato["PERSO"]
        return {
            "totale": len(rows),
            "per_stato": per_stato,
            "per_fonte": per_fonte,
            "tasso_conversione": round(per_stato["VINTO"] / chiusi, 2) if chiusi else 0.0,
        }
