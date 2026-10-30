"""Il dataset per addestrare il modello di catalogazione sul PC dell'avvocato (autorizzazione del 30/10/2026).

Formato: la domanda è quella della seconda lettura di Lex nel catalogo (`catalog_lex.domanda`), così il modello
addestrato può prenderne il posto senza cambiare la pipeline; la risposta è il JSON del catalogo (etichetta,
citazione copiata dal testo, motivo). Il prefisso fisso (istruzioni ed elenco delle voci) è scritto una volta.

Righe per gruppo:
- `addestramento`: proposte quasi certe delle regole (documenti reali pseudonimizzati) ed esempi inventati;
- `verifica`: proposte quasi certe tenute da parte in modo stabile (mai viste in addestramento);
- `verifica_avvocato`: decisioni dell'avvocato documento per documento, il confronto che misura chi sbaglia meno;
- `da_rivedere`: proposte incerte delle regole, senza risposta; servono a trovare i disaccordi da rivedere;
- `banco_inventati`: documenti inventati con un altro seme, mai in addestramento: banco di prova di tutte le voci.

Nessun identificativo del server lascia il server: ogni riga ha un codice opaco; la corrispondenza codice →
documento resta in un file a parte, nella cartella dello studio sul server.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable
from typing import Any

from pct.document_intelligence.catalog_lex import voce_dell_elenco

from .censimento import CONFIDENZA_ARGENTO
from .classificatore import in_verifica
from .esperimento import Campione
from .pseudonimi import pseudonimizza
from .sintetici import DocumentoInventato

FORMATO = "iusentra-catalogo-addestramento.v1"


def _codice(*parti: str) -> str:
    return hashlib.sha256("|".join(parti).encode("utf-8")).hexdigest()[:20]


_PAROLA = re.compile(r"[^\W\d_]{2,}")
_NUMERO_PAGINA = re.compile(r"(?i)^\W*pag(?:ina|\.)?\s*\d")


def _taglia(frase: str, massimo: int = 240) -> str:
    """Taglio a parola intera: una parola mozzata non si ritrova nel testo e invalida la citazione."""
    return frase if len(frase) <= massimo else frase[:massimo].rsplit(" ", 1)[0]


def citazione(testo: str) -> str:
    """La prima frase d'intestazione dall'alto (almeno quattro parole) che si ritrova davvero nel testo.

    Si salta ciò che precede l'intestazione e non la dimostra (numeri di pagina, righe di soli segni o cifre);
    il taglio è a parola intera. La verifica tollera gli a capo fra righe intere: `catalog_lex.citazione_nel_testo`.
    """
    from pct.document_intelligence.catalog_lex import citazione_nel_testo

    righe = [riga.strip() for riga in str(testo or "").splitlines()[:30] if riga.strip()]
    prima = ""
    for inizio, riga in enumerate(righe):
        if not _PAROLA.search(riga) or _NUMERO_PAGINA.match(riga):
            continue
        scelte: list[str] = []
        for seguente in righe[inizio:]:
            scelte.append(seguente)
            if len(_PAROLA.findall(" ".join(scelte))) >= 4:
                break
        frase = _taglia(" ".join(scelte))
        prima = prima or frase
        if citazione_nel_testo(frase, testo):
            return frase
    return prima


def _citazione_valida(testo: str) -> bool:
    from pct.document_intelligence.catalog_lex import citazione_nel_testo

    return citazione_nel_testo(citazione(testo), testo)


def risposta(testo: str, voce: str) -> str:
    return json.dumps({"etichetta": voce, "citazione": citazione(testo),
                       "motivo": f"L'intestazione e il titolo del documento lo qualificano come {voce}."},
                      ensure_ascii=False)


def righe_dataset(campioni: Iterable[Campione], inventati: Iterable[DocumentoInventato], voci: set[str],
                  banco: Iterable[DocumentoInventato] = (), disaccordi: dict[str, str] | None = None
                  ) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], dict[str, Any]]:
    """`disaccordi`: documento → voce scelta con sicurezza dal classificatore piccolo contro le regole."""
    """Righe del dataset, corrispondenze codice → documento (solo server) e conteggi del manifesto."""
    righe: list[dict[str, Any]] = []
    corrispondenze: dict[str, dict[str, str]] = {}
    scartati: Counter[str] = Counter()
    for c in campioni:
        if not c.testo.strip():
            scartati["senza_testo"] += 1
            continue
        testo = pseudonimizza(c.testo, set(c.nomi))
        codice = _codice(c.fascicolo_id, c.document_id)
        voce_regole = voce_dell_elenco(c.voce, voci)
        riga: dict[str, Any] = {"id": codice, "testo": testo, "voce_regole": voce_regole,
                                "voce_spark": voce_dell_elenco(c.voce_spark, voci)}
        proposta = c.stato == "proposed" and c.origine != "manual_override"
        if c.voce_avvocato:
            if c.voce_avvocato not in voci:
                scartati["decisione_fuori_elenco"] += 1
                continue
            riga.update(gruppo="verifica_avvocato", fonte="avvocato", voce=c.voce_avvocato,
                        risposta=risposta(testo, c.voce_avvocato))
        elif proposta and c.confidenza >= CONFIDENZA_ARGENTO and voce_regole:
            gruppo = "verifica" if in_verifica(c.document_id) else "addestramento"
            riga.update(gruppo=gruppo, fonte="regole_quasi_certe", voce=voce_regole, risposta=risposta(testo, voce_regole))
        elif c.stato in {"proposed", "review_required"} and c.origine != "manual_override":
            riga.update(gruppo="da_rivedere", fonte="regole_incerte", voce="", confidenza_regole=c.confidenza,
                        voce_lineare=(disaccordi or {}).get(c.document_id, ""))
        else:
            scartati["fuori_elenco_o_gia_deciso"] += 1
            continue
        if "risposta" in riga and not _citazione_valida(testo):
            scartati["citazione_non_verificabile"] += 1
            continue
        righe.append(riga)
        corrispondenze[codice] = {"fascicolo_id": c.fascicolo_id, "document_id": c.document_id}
    for n, d in enumerate(inventati):
        if d.voce not in voci:
            scartati["inventato_fuori_elenco"] += 1
            continue
        if not _citazione_valida(d.testo):
            scartati["citazione_non_verificabile"] += 1
            continue
        righe.append({"id": _codice("inventato", str(n), d.origine), "testo": d.testo, "gruppo": "addestramento",
                      "fonte": "inventato", "voce": d.voce, "voce_regole": d.voce, "voce_spark": "",
                      "risposta": risposta(d.testo, d.voce)})
    # Banco di prova inventato: generato con un altro seme, mai in addestramento; un testo già visto si scarta.
    visti = {hashlib.sha256(r["testo"].encode("utf-8")).hexdigest() for r in righe if r["gruppo"] == "addestramento"}
    for n, d in enumerate(banco):
        impronta = hashlib.sha256(d.testo.encode("utf-8")).hexdigest()
        if d.voce not in voci or impronta in visti or not _citazione_valida(d.testo):
            scartati["banco_scartato"] += 1
            continue
        visti.add(impronta)
        righe.append({"id": _codice("banco", str(n), d.origine), "testo": d.testo, "gruppo": "banco_inventati",
                      "fonte": "inventato", "voce": d.voce, "voce_regole": d.voce, "voce_spark": "",
                      "risposta": risposta(d.testo, d.voce)})
    disaccordi_esportati = sum(1 for r in righe if r.get("voce_lineare"))
    per_gruppo = Counter(r["gruppo"] for r in righe)
    per_fonte = Counter(f"{r['gruppo']}/{r['fonte']}" for r in righe)
    per_voce = Counter(r["voce"] for r in righe if r["gruppo"] == "addestramento")
    manifesto = {"formato": FORMATO, "righe": len(righe), "per_gruppo": dict(per_gruppo), "per_fonte": dict(per_fonte),
                 "voci_in_addestramento": len(per_voce), "voci_con_almeno_30": sum(1 for n in per_voce.values() if n >= 30),
                 "disaccordi_da_rivedere": disaccordi_esportati, "scartati": dict(scartati)}
    return righe, corrispondenze, manifesto


__all__ = ["FORMATO", "citazione", "righe_dataset", "risposta"]
