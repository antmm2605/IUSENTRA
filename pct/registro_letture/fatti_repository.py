"""L'archivio di alimentazione dentro il registro: i fatti letti dai due motori.

Un fatto è un dato estratto da un oggetto del fascicolo (documento, PEC,
allegato PEC) con impronta nota: una data con il suo campo (udienza, termine,
notifica, deposito, accettazione, consegna, comunicazione), un numero di
ruolo, una prova di notifica, un importo, un evento. Ogni fatto porta la
prova del collaudo automatico e il verdetto: `verificata`, `plausibile`,
`respinta`; l'avvocato può renderlo `corretta` o `ignorata` e quella decisione
sopravvive alle riletture dello stesso contenuto.

Il mixin non legge file e non estrae nulla: registra ciò che i motori hanno
letto e lo restituisce ai presìdi. Tabella `letture_fatti` (schema gemello
SQLite/PostgreSQL nei file del registro).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

MOTORI = ("documenti", "pec")
CATEGORIE = ("data", "ruolo", "prova_notifica", "importo", "evento")
VERIFICHE = ("verificata", "plausibile", "respinta", "corretta", "ignorata")
VERIFICHE_UTILI = ("verificata", "plausibile", "corretta")
COLONNE_FATTI: tuple[str, ...] = (
    "id", "tenant_id", "fascicolo_id", "tipo", "oggetto_id", "sha256", "motore", "versione_motore", "categoria", "campo",
    "valore_letto", "valore", "etichetta", "contesto", "posizione", "origine", "confidenza", "verifica", "prove_json",
    "chiave", "letto_il", "aggiornato_il", "risolta_da", "risolta_il",
)
_FILTRI_FATTI = {
    "tenant_id = ? AND fascicolo_id = ?": '"tenant_id" = ? AND "fascicolo_id" = ?',
    "tenant_id = ? AND tipo = ? AND oggetto_id = ? AND sha256 = ? AND motore = ?": '"tenant_id" = ? AND "tipo" = ? AND "oggetto_id" = ? AND "sha256" = ? AND "motore" = ?',
    "tenant_id = ? AND tipo = ? AND oggetto_id = ?": '"tenant_id" = ? AND "tipo" = ? AND "oggetto_id" = ?',
    "tenant_id = ? AND id = ?": '"tenant_id" = ? AND "id" = ?',
}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def chiave_fatto(campo: str, valore: str, contesto: str) -> str:
    """La chiave con cui lo stesso fatto si riconosce fra due letture dello stesso contenuto."""
    base = "|".join((_testo(campo).casefold(), _testo(valore).casefold(), _testo(contesto).casefold()[:120]))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


@dataclass(slots=True)
class Fatto:
    """Un fatto letto: che cosa, dove, come, con quale prova."""

    categoria: str
    campo: str
    valore: str
    valore_letto: str = ""
    etichetta: str = ""
    contesto: str = ""
    posizione: int = 0
    origine: str = ""
    confidenza: float = 0.0
    verifica: str = "plausibile"
    prove: list[dict[str, Any]] = field(default_factory=list)
    motore: str = ""
    tipo: str = ""
    oggetto_id: str = ""
    sha256: str = ""
    id: str = ""
    fascicolo_id: str = ""
    letto_il: str = ""

    @property
    def chiave(self) -> str:
        return chiave_fatto(self.campo, self.valore, self.contesto)

    def to_dict(self) -> dict[str, Any]:
        dati = asdict(self)
        dati["chiave"] = self.chiave
        return dati


class FattiMixin:
    """Le operazioni sull'archivio dei fatti; si innesta nel registro delle letture."""

    # Forniti dal registro: connection(), _inserisci, _aggiorna, _elimina, _tabella, _adesso, _nuovo_id
    def _filtro_fatti(self, filtro: str) -> str:
        sql = _FILTRI_FATTI.get(filtro)
        if sql is None:
            raise ValueError("Filtro non valido.")
        return sql

    def _seleziona_fatti(self, filtro: str, parametri: Iterable[Any]) -> list[dict[str, Any]]:
        sql = f'SELECT * FROM "letture_fatti" WHERE {self._filtro_fatti(filtro)} ORDER BY "posizione", "letto_il"'
        with self.connection() as conn:  # type: ignore[attr-defined]
            righe = conn.execute(sql, tuple(parametri)).fetchall()
        esito = []
        for riga in righe:
            try:
                esito.append(dict(riga))
            except Exception:
                continue
        return esito

    @staticmethod
    def _fatto(riga: dict[str, Any]) -> Fatto:
        try:
            prove = json.loads(str(riga.get("prove_json") or "[]"))
        except (TypeError, ValueError):
            prove = []
        return Fatto(
            categoria=str(riga.get("categoria") or ""), campo=str(riga.get("campo") or ""), valore=str(riga.get("valore") or ""),
            valore_letto=str(riga.get("valore_letto") or ""), etichetta=str(riga.get("etichetta") or ""), contesto=str(riga.get("contesto") or ""),
            posizione=int(riga.get("posizione") or 0), origine=str(riga.get("origine") or ""), confidenza=float(riga.get("confidenza") or 0),
            verifica=str(riga.get("verifica") or ""), prove=prove if isinstance(prove, list) else [], motore=str(riga.get("motore") or ""),
            tipo=str(riga.get("tipo") or ""), oggetto_id=str(riga.get("oggetto_id") or ""), sha256=str(riga.get("sha256") or ""),
            id=str(riga.get("id") or ""), fascicolo_id=str(riga.get("fascicolo_id") or ""), letto_il=str(riga.get("letto_il") or ""),
        )

    def registra_fatti(self, tenant_id: str, fascicolo_id: str, oggetto: Any, motore: str, fatti: Iterable[Fatto], *, versione: str = "") -> dict[str, int]:
        """I fatti di una lettura sostituiscono quelli della lettura precedente dello stesso contenuto.

        Le decisioni dell'avvocato (`corretta`, `ignorata`) restano: un fatto
        con la stessa chiave non viene sovrascritto e un fatto deciso che la
        nuova lettura non trova più non viene cancellato.
        """
        if motore not in MOTORI:
            raise ValueError("Motore non censito nell'archivio.")
        tenant, fascicolo = _testo(tenant_id), _testo(fascicolo_id)
        tipo, oggetto_id, sha = _testo(oggetto.tipo), _testo(oggetto.oggetto_id), _testo(oggetto.impronta)
        adesso = self._adesso()  # type: ignore[attr-defined]
        esistenti = {riga["chiave"]: riga for riga in self._seleziona_fatti("tenant_id = ? AND tipo = ? AND oggetto_id = ? AND sha256 = ? AND motore = ?", (tenant, tipo, oggetto_id, sha, motore))}
        conteggi = {"nuovi": 0, "aggiornati": 0, "conservati": 0, "rimossi": 0}
        visti: set[str] = set()
        with self.connection() as conn:  # type: ignore[attr-defined]
            for fatto in fatti:
                if fatto.categoria not in CATEGORIE or fatto.verifica not in VERIFICHE or not _testo(fatto.campo):
                    continue
                chiave = fatto.chiave
                if chiave in visti:
                    continue
                visti.add(chiave)
                valori = {
                    "fascicolo_id": fascicolo, "versione_motore": _testo(versione), "categoria": fatto.categoria, "campo": _testo(fatto.campo),
                    "valore_letto": _testo(fatto.valore_letto)[:1200 if fatto.campo == "domanda_atto" else 120], "valore": _testo(fatto.valore)[:1200 if fatto.campo == "domanda_atto" else 120], "etichetta": _testo(fatto.etichetta)[:120],
                    "contesto": _testo(fatto.contesto)[:300], "posizione": int(fatto.posizione or 0), "origine": _testo(fatto.origine)[:40],
                    "confidenza": round(float(fatto.confidenza or 0), 3), "verifica": fatto.verifica,
                    "prove_json": json.dumps(list(fatto.prove or []), ensure_ascii=False, sort_keys=True, default=str), "aggiornato_il": adesso,
                }
                riga = esistenti.get(chiave)
                if riga is None:
                    conteggi["nuovi"] += 1
                    conn.execute(
                        'INSERT INTO "letture_fatti" ("id", "tenant_id", "tipo", "oggetto_id", "sha256", "motore", "chiave", "letto_il", '
                        + ", ".join(f'"{colonna}"' for colonna in valori) + ") VALUES (" + ", ".join("?" for _ in range(8 + len(valori))) + ")",
                        (self._nuovo_id("fat"), tenant, tipo, oggetto_id, sha, motore, chiave, adesso, *valori.values()),  # type: ignore[attr-defined]
                    )
                    continue
                if str(riga.get("verifica") or "") in {"corretta", "ignorata"} or riga.get("risolta_da"):
                    conteggi["conservati"] += 1
                    continue
                conteggi["aggiornati"] += 1
                conn.execute(
                    'UPDATE "letture_fatti" SET ' + ", ".join(f'"{colonna}" = ?' for colonna in valori) + ' WHERE "tenant_id" = ? AND "id" = ?',
                    (*valori.values(), tenant, riga["id"]),
                )
            for chiave, riga in esistenti.items():
                if chiave in visti or str(riga.get("verifica") or "") in {"corretta", "ignorata"} or riga.get("risolta_da"):
                    continue
                conteggi["rimossi"] += 1
                prove = json.loads(riga.get("prove_json") or "[]")
                prova = {"codice": "riconvalida", "esito": "respinta", "dettaglio": "La lettura corrente non conferma più questo dato: mantenuto solo nello storico delle evidenze."}
                if prova not in prove:
                    prove.append(prova)
                conn.execute('UPDATE "letture_fatti" SET "verifica" = ?, "prove_json" = ?, "aggiornato_il" = ? WHERE "tenant_id" = ? AND "id" = ?', ("respinta", json.dumps(prove, ensure_ascii=False), adesso, tenant, riga["id"]))
        return conteggi

    def fatti(self, tenant_id: str, fascicolo_id: str, *, categoria: str = "", campo: str = "", verifiche: Iterable[str] | None = VERIFICHE_UTILI, motore: str = "", tipo: str = "") -> list[Fatto]:
        """I fatti del fascicolo, di regola solo quelli utili (verificati, plausibili, corretti)."""
        ammesse = set(verifiche) if verifiche is not None else None
        esito: list[Fatto] = []
        for riga in self._seleziona_fatti("tenant_id = ? AND fascicolo_id = ?", (_testo(tenant_id), _testo(fascicolo_id))):
            fatto = self._fatto(riga)
            if categoria and fatto.categoria != categoria:
                continue
            if campo and fatto.campo != campo:
                continue
            if motore and fatto.motore != motore:
                continue
            if tipo and fatto.tipo != tipo:
                continue
            if ammesse is not None and fatto.verifica not in ammesse:
                continue
            esito.append(fatto)
        return esito

    def fatti_oggetto(self, tenant_id: str, tipo: str, oggetto_id: str) -> list[Fatto]:
        return [self._fatto(riga) for riga in self._seleziona_fatti("tenant_id = ? AND tipo = ? AND oggetto_id = ?", (_testo(tenant_id), _testo(tipo), _testo(oggetto_id)))]

    def decidi_fatto(self, tenant_id: str, fatto_id: str, *, verifica: str, valore: str = "", utente_id: str = "") -> Fatto:
        """L'avvocato conferma (verificata), corregge (corretta, con il valore giusto) o ignora un fatto."""
        if verifica not in {"verificata", "corretta", "ignorata"}:
            raise ValueError("Decisione non valida.")
        tenant = _testo(tenant_id)
        righe = self._seleziona_fatti("tenant_id = ? AND id = ?", (tenant, _testo(fatto_id)))
        if not righe:
            raise ValueError("Fatto non trovato.")
        riga = righe[0]
        nuovo_valore = _testo(valore) if verifica == "corretta" else str(riga.get("valore") or "")
        if verifica == "corretta" and not nuovo_valore:
            raise ValueError("Per correggere serve il valore giusto.")
        adesso = self._adesso()  # type: ignore[attr-defined]
        prove = riga.get("prove_json") or "[]"
        try:
            elenco = json.loads(prove)
        except (TypeError, ValueError):
            elenco = []
        elenco = (elenco if isinstance(elenco, list) else []) + [{"codice": "decisione_avvocato", "esito": verifica, "dettaglio": f"deciso da {utente_id or 'utente'}"}]
        with self.connection() as conn:  # type: ignore[attr-defined]
            conn.execute(
                'UPDATE "letture_fatti" SET "verifica" = ?, "valore" = ?, "prove_json" = ?, "risolta_da" = ?, "risolta_il" = ?, "aggiornato_il" = ? WHERE "tenant_id" = ? AND "id" = ?',
                (verifica, nuovo_valore, json.dumps(elenco, ensure_ascii=False, sort_keys=True), _testo(utente_id), adesso, adesso, tenant, riga["id"]),
            )
        return self._fatto({**riga, "verifica": verifica, "valore": nuovo_valore, "prove_json": json.dumps(elenco), "risolta_da": utente_id, "risolta_il": adesso})

    def allinea_fatti_da_anomalia(self, tenant_id: str, anomalia: Any, *, utente_id: str = "") -> int:
        """Una decisione presa sul pannello delle anomalie vale anche per i fatti con lo stesso dato letto."""
        esito = str(getattr(anomalia, "stato", "") or "")
        verifica = {"confermata": "verificata", "corretta": "corretta", "ignorata": "ignorata"}.get(esito)
        if not verifica:
            return 0
        valore = str(getattr(anomalia, "valore_confermato", "") or "")
        allineati = 0
        for fatto in self.fatti_oggetto(tenant_id, getattr(anomalia, "tipo", ""), getattr(anomalia, "oggetto_id", "")):
            if fatto.campo != str(getattr(anomalia, "campo", "") or "") or fatto.valore_letto != str(getattr(anomalia, "valore_letto", "") or ""):
                continue
            if fatto.verifica in {"corretta", "ignorata"}:
                continue
            self.decidi_fatto(tenant_id, fatto.id, verifica=verifica, valore=valore if verifica == "corretta" else "", utente_id=utente_id)
            allineati += 1
        return allineati

    def riconvalida_fatti(self, tenant_id: str, fascicolo_id: str, *, esclusioni_oggetto: dict[str, str] | None = None) -> list[Fatto]:
        """Respinge i fatti che le regole correnti non estrarrebbero più.

        Un fatto registrato prima che una regola si stringesse resta
        nell'archivio e continua ad alimentare i presìdi: una data che oggi il
        lettore riconosce come riferimento normativo («l. 69/2023») va respinta,
        non lasciata a chiedere conferma. Le decisioni dell'avvocato
        (corretta, ignorata) non si toccano mai.
        """
        from legal_ocr.formulario.riferimenti_normativi import e_riferimento_normativo

        tenant = _testo(tenant_id)
        respinti: list[Fatto] = []
        adesso = self._adesso()  # type: ignore[attr-defined]
        for fatto in self.fatti(tenant, fascicolo_id, verifiche=("plausibile", "verificata")):
            if fatto.categoria != "data" or any(p.get("codice") == "decisione_avvocato" for p in fatto.prove):
                continue
            letto = _testo(fatto.valore_letto)
            riferimento = e_riferimento_normativo(letto, 0, len(letto)) if letto else ""
            from pct.archivio_letture.ancoraggio import esclusione_data_salvata
            esclusione = esclusione_data_salvata(fatto.contesto, fatto.valore) if fatto.campo in {"termine", "decorrenza", "udienza", "costituzione"} else ""
            if fatto.campo in {"termine", "udienza", "costituzione"}:
                esclusione = (esclusioni_oggetto or {}).get(fatto.oggetto_id) or esclusione
            if not riferimento and not esclusione:
                continue
            motivo = f"«{letto}» è un riferimento normativo ({riferimento}), non una data" if riferimento else f"«{letto}»: {esclusione}"
            prove = list(fatto.prove) + [{
                "codice": "riconvalida",
                "esito": "respinta",
                "dettaglio": motivo,
            }]
            with self.connection() as conn:  # type: ignore[attr-defined]
                conn.execute(
                    'UPDATE "letture_fatti" SET "verifica" = ?, "prove_json" = ?, "aggiornato_il" = ? WHERE "tenant_id" = ? AND "id" = ?',
                    ("respinta", json.dumps(prove, ensure_ascii=False, sort_keys=True), adesso, tenant, fatto.id),
                )
            fatto.verifica, fatto.prove = "respinta", prove
            respinti.append(fatto)
        return respinti

    def riassunto_fatti(self, tenant_id: str, fascicolo_id: str) -> dict[str, Any]:
        """Quanti fatti, per verdetto e per categoria; per i presìdi e per il pannello."""
        per_verifica = {chiave: 0 for chiave in VERIFICHE}
        per_categoria: dict[str, int] = {chiave: 0 for chiave in CATEGORIE}
        per_campo: dict[str, int] = {}
        ultima = ""
        for fatto in self.fatti(tenant_id, fascicolo_id, verifiche=None):
            per_verifica[fatto.verifica] = per_verifica.get(fatto.verifica, 0) + 1
            if fatto.verifica in VERIFICHE_UTILI:
                per_categoria[fatto.categoria] = per_categoria.get(fatto.categoria, 0) + 1
                per_campo[fatto.campo] = per_campo.get(fatto.campo, 0) + 1
            ultima = max(ultima, fatto.letto_il)
        return {"per_verifica": per_verifica, "per_categoria": per_categoria, "per_campo": per_campo, "totale": sum(per_verifica.values()), "ultima_lettura": ultima}


__all__ = ["CATEGORIE", "COLONNE_FATTI", "Fatto", "FattiMixin", "MOTORI", "VERIFICHE", "VERIFICHE_UTILI", "chiave_fatto"]
