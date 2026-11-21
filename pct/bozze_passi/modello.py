"""La forma di una bozza preparata per un passo del fascicolo.

Una bozza è un testo (Markdown giuridico, lo stesso dell'editor) compilato con i soli dati certi della
Lettura e del modello della causa. Dove un dato non è certo il testo contiene un segnaposto evidente
«[da completare: …]»: il passo lo elenca, l'avvocato lo completa. La bozza non si invia, non si deposita e
non si notifica da sola: resta un documento del fascicolo da rivedere e firmare.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

FONTE_BOZZA_PASSO = "BOZZA_PASSO"
# Le bozze preparate dal software non sono fatti della causa: la Lettura, il ragionamento e i motori di
# lettura non le leggono (un precetto in bozza non è un precetto notificato).
FONTI_BOZZE_DEL_SOFTWARE = frozenset({FONTE_BOZZA_PASSO, "BOZZA_NOTE_127_TER"})
AVVISO_BOZZA = "Bozza da rivedere e firmare"

_RE_SEGNAPOSTO = re.compile(r"\[da completare: ([^\]]+)\]")


def manca(cosa: str) -> str:
    """Il segnaposto di un dato che le fonti non danno con certezza."""
    return f"[da completare: {' '.join(str(cosa).split())}]"


def da_completare(testo: str) -> tuple[str, ...]:
    """I segnaposti del testo, nell'ordine, senza ripetizioni."""
    return tuple(dict.fromkeys(m.group(1).strip() for m in _RE_SEGNAPOSTO.finditer(testo or "")))


def e_bozza_del_software(documento: Any) -> bool:
    """Il documento è una bozza preparata dal software (non un atto della causa)."""
    fonte = documento.get("fonte_documento") if isinstance(documento, dict) else getattr(documento, "fonte_documento", "")
    return str(fonte or "").strip().upper() in FONTI_BOZZE_DEL_SOFTWARE


# Marcatori interni delle bozze (registro dei passi «bozza-passo:<chiave>», Lex, editor, note 127-ter): servono al
# software per ritrovare il documento, all'avvocato non dicono nulla. Nella scheda compare un'etichetta chiara.
_RE_TAG_TECNICO_BOZZA = re.compile(r"^(?:bozza(?:-[a-z0-9_]+)*|editor-(?:nuovo|richiesta)|preparazione-[a-z0-9_-]+)(?::.*)?$",
                                   re.IGNORECASE)
ETICHETTA_BOZZA_SOFTWARE = "Bozza preparata da IUSENTRA"
ETICHETTA_BOZZA = "Bozza"


def tag_tecnico_bozza(tag: Any) -> bool:
    return bool(_RE_TAG_TECNICO_BOZZA.match(str(tag or "").strip()))


def etichette_visibili(documento: Any, tags: Any = None) -> list[str]:
    """I tag del documento senza i marcatori interni delle bozze; al loro posto «Bozza preparata da IUSENTRA»
    (bozze del software) o «Bozza» (bozze dell'editor). Gli altri tag restano come sono, nell'ordine."""
    grezzi = list(tags if tags is not None else (getattr(documento, "tags", None) or []))
    visibili = [str(t).strip() for t in grezzi if str(t or "").strip() and not tag_tecnico_bozza(t)]
    if e_bozza_del_software(documento):
        visibili.insert(0, ETICHETTA_BOZZA_SOFTWARE)
    elif len(visibili) < len([t for t in grezzi if str(t or "").strip()]):
        visibili.insert(0, ETICHETTA_BOZZA)
    return list(dict.fromkeys(visibili))


@dataclass(frozen=True)
class AggancioPasso:
    """Come si riconosce il passo della Lettura a cui la bozza appartiene."""

    parole: tuple[str, ...]  # espressioni regolari che l'azione del passo deve contenere (tutte)
    entro: tuple[str, ...] = ()  # date gg/mm/aaaa ammesse; vuoto = qualsiasi

    def riconosce(self, passo: dict[str, Any]) -> bool:
        azione = str(passo.get("azione") or "")
        if not all(re.search(parola, azione, re.IGNORECASE) for parola in self.parole):
            return False
        return not self.entro or str(passo.get("entro") or "") in self.entro


@dataclass(frozen=True)
class Bozza:
    chiave: str  # stabile: tipo e riferimento (termine o provvedimento)
    tipo: str
    titolo: str
    modello: str  # identificativo del template del catalogo (Template atti)
    modello_titolo: str
    fonti: tuple[str, ...]  # registro pct/procedura_fasi/fonti.py
    testo: str
    agganci: tuple[AggancioPasso, ...] = ()
    dati: dict[str, Any] = field(default_factory=dict)  # i dati certi usati, con la loro fonte

    @property
    def segnaposti(self) -> tuple[str, ...]:
        return da_completare(self.testo)

    @property
    def impronta(self) -> str:
        grezzo = json.dumps([self.titolo, self.modello, self.testo], ensure_ascii=False)
        return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()

    def passi(self, prossimi_passi: list[dict[str, Any]]) -> list[dict[str, str]]:
        """I passi della Lettura a cui la bozza si aggancia (azione ed entro, come li mostra la pagina)."""
        return [{"azione": str(p.get("azione") or ""), "entro": str(p.get("entro") or "")}
                for p in prossimi_passi or [] if any(a.riconosce(p) for a in self.agganci)]

    def descrizione(self) -> dict[str, Any]:
        from pct.procedura_fasi.fonti import norme

        return {"chiave": self.chiave, "tipo": self.tipo, "titolo": self.titolo, "modello": self.modello,
                "modelloTitolo": self.modello_titolo, "norma": norme(self.fonti), "daCompletare": list(self.segnaposti),
                "impronta": self.impronta}


__all__ = [
    "AVVISO_BOZZA",
    "ETICHETTA_BOZZA",
    "ETICHETTA_BOZZA_SOFTWARE",
    "etichette_visibili",
    "tag_tecnico_bozza",
    "FONTE_BOZZA_PASSO",
    "FONTI_BOZZE_DEL_SOFTWARE",
    "AggancioPasso",
    "Bozza",
    "da_completare",
    "e_bozza_del_software",
    "manca",
]
