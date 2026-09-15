"""Le consegne ai presìdi: l'archivio tiene il conto di che cosa ha già dato.

La catena è a due gambe. La prima: i due motori leggono e scrivono i fatti
nell'archivio, l'archivio conferma, i motori si fermano. La seconda, qui: per
ogni fatto l'archivio sa **a quali presìdi serve** e glielo consegna una volta
sola. Il presidio lo scrive nel proprio registro — una scadenza nello
scadenziario, un appuntamento in agenda, un importo nei pagamenti, una prova
nel presidio notifiche — e **conferma**, indicando il riferimento della riga
che ha creato. Da quel momento l'archivio non ripropone più quel fatto a quel
presidio: niente doppioni, e tutto si ferma.

Se il presidio valuta il fatto e non lo usa, lo dichiara `non_pertinente`: non
torna più. Se non riesce a scriverlo, lo dichiara `rifiutato` con il motivo:
resta visibile e si riprova. In nessun caso un fatto esce dalla catena in
silenzio.

Base normativa della tracciabilità: art. 3 D.M. 44/2011 e art. 20 CAD.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

STATI_CONSEGNA = ("da_consegnare", "consegnato", "non_pertinente", "rifiutato")
COLONNE_CONSEGNE = (
    "id", "tenant_id", "fascicolo_id", "fatto_id", "presidio", "stato",
    "riferimento", "motivo", "versione_presidio", "consegnato_il", "aggiornato_il",
)


@dataclass(slots=True)
class Consegna:
    """Che cosa l'archivio ha dato a un presidio, e che cosa il presidio ne ha fatto."""

    id: str
    fatto_id: str
    presidio: str
    stato: str
    riferimento: str = ""
    motivo: str = ""
    versione_presidio: str = ""
    consegnato_il: str = ""
    aggiornato_il: str = ""

    @property
    def chiusa(self) -> bool:
        """Se il presidio ha già deciso: non va riproposta."""
        return self.stato in {"consegnato", "non_pertinente"}

    def to_dict(self) -> dict[str, Any]:
        dati = asdict(self)
        dati["chiusa"] = self.chiusa
        return dati


class ConsegneMixin:
    """Le consegne dei fatti ai presìdi, dentro il registro delle letture."""

    def _consegne_riga(self, riga: dict[str, Any]) -> Consegna:
        return Consegna(
            id=str(riga.get("id") or ""), fatto_id=str(riga.get("fatto_id") or ""),
            presidio=str(riga.get("presidio") or ""), stato=str(riga.get("stato") or ""),
            riferimento=str(riga.get("riferimento") or ""), motivo=str(riga.get("motivo") or ""),
            versione_presidio=str(riga.get("versione_presidio") or ""),
            consegnato_il=str(riga.get("consegnato_il") or ""), aggiornato_il=str(riga.get("aggiornato_il") or ""),
        )

    def consegne(self, tenant_id: str, fascicolo_id: str, *, presidio: str = "") -> list[Consegna]:
        """Le consegne registrate per il fascicolo, eventualmente di un solo presidio."""
        from .repository import _testo

        righe = self._seleziona_consegne(_testo(tenant_id), _testo(fascicolo_id))
        consegne = [self._consegne_riga(riga) for riga in righe]
        presidio = _testo(presidio)
        return [voce for voce in consegne if not presidio or voce.presidio == presidio]

    def da_consegnare(self, tenant_id: str, fascicolo_id: str, presidio: str, fatti: Iterable[Any]) -> list[Any]:
        """I fatti che questo presidio non ha ancora preso in carico.

        Un fatto già consegnato o dichiarato non pertinente non torna. Un fatto
        rifiutato torna, perché il presidio deve poterci riprovare.
        """
        chiuse = {voce.fatto_id for voce in self.consegne(tenant_id, fascicolo_id, presidio=presidio) if voce.chiusa}
        return [fatto for fatto in fatti if str(getattr(fatto, "id", "") or "") and str(fatto.id) not in chiuse]

    def segna_consegna(
        self, tenant_id: str, fascicolo_id: str, fatto_id: str, presidio: str, *,
        stato: str = "consegnato", riferimento: str = "", motivo: str = "", versione_presidio: str = "",
    ) -> Consegna:
        """Il presidio dichiara che cosa ha fatto del fatto: è la conferma che chiude il giro."""
        from .repository import RegistroLettureError, _adesso, _nuovo_id, _testo

        if stato not in STATI_CONSEGNA:
            raise RegistroLettureError("Stato di consegna non valido.")
        tenant, fascicolo = _testo(tenant_id), _testo(fascicolo_id)
        fatto, nome = _testo(fatto_id), _testo(presidio)
        if not fatto or not nome:
            raise RegistroLettureError("Consegna senza fatto o senza presidio.")
        adesso = _adesso()
        valori = {
            "stato": stato, "riferimento": _testo(riferimento)[:300], "motivo": _testo(motivo)[:300],
            "versione_presidio": _testo(versione_presidio)[:120],
            "consegnato_il": adesso if stato == "consegnato" else "", "aggiornato_il": adesso,
        }
        with self.connection() as conn:  # type: ignore[attr-defined]
            esistente = conn.execute(
                f'SELECT "id" FROM "letture_consegne" WHERE "tenant_id" = ? AND "fatto_id" = ? AND "presidio" = ?',
                (tenant, fatto, nome),
            ).fetchone()
            if esistente:
                identificativo = dict(esistente).get("id") if not isinstance(esistente, (list, tuple)) else esistente[0]
                conn.execute(
                    'UPDATE "letture_consegne" SET "stato" = ?, "riferimento" = ?, "motivo" = ?, '
                    '"versione_presidio" = ?, "consegnato_il" = ?, "aggiornato_il" = ? WHERE "id" = ?',
                    (valori["stato"], valori["riferimento"], valori["motivo"], valori["versione_presidio"],
                     valori["consegnato_il"], valori["aggiornato_il"], identificativo),
                )
            else:
                identificativo = _nuovo_id("cns")
                conn.execute(
                    'INSERT INTO "letture_consegne" ("id","tenant_id","fascicolo_id","fatto_id","presidio","stato",'
                    '"riferimento","motivo","versione_presidio","consegnato_il","aggiornato_il") '
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (identificativo, tenant, fascicolo, fatto, nome, valori["stato"], valori["riferimento"],
                     valori["motivo"], valori["versione_presidio"], valori["consegnato_il"], valori["aggiornato_il"]),
                )
        return Consegna(id=str(identificativo), fatto_id=fatto, presidio=nome, **valori)  # type: ignore[arg-type]

    def _seleziona_consegne(self, tenant: str, fascicolo: str) -> list[dict[str, Any]]:
        from .repository import _riga

        with self.connection() as conn:  # type: ignore[attr-defined]
            righe = conn.execute(
                'SELECT * FROM "letture_consegne" WHERE "tenant_id" = ? AND "fascicolo_id" = ? ORDER BY "aggiornato_il" DESC',
                (tenant, fascicolo),
            ).fetchall()
        return [_riga(riga) for riga in righe]

    def riassunto_consegne(self, tenant_id: str, fascicolo_id: str) -> dict[str, dict[str, int]]:
        """Per ogni presidio quante consegne sono chiuse, rifiutate o in attesa."""
        esito: dict[str, dict[str, int]] = {}
        for voce in self.consegne(tenant_id, fascicolo_id):
            riga = esito.setdefault(voce.presidio, {"consegnato": 0, "non_pertinente": 0, "rifiutato": 0, "da_consegnare": 0})
            riga[voce.stato] = riga.get(voce.stato, 0) + 1
        return esito


__all__ = ["COLONNE_CONSEGNE", "Consegna", "ConsegneMixin", "STATI_CONSEGNA"]
