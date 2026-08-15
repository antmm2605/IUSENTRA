"""Prima nota di studio: registro cronologico di incassi e pagamenti.

Base normativa: per i professionisti vale il principio di cassa (art. 54
TUIR); la contabilita' semplificata richiede il registro cronologico di
incassi e pagamenti (art. 19 D.P.R. 600/1973) e i registri IVA (artt. 23-25
D.P.R. 633/1972); nel regime forfettario (L. 190/2014) l'obbligo dei registri
viene meno ma resta la conservazione dei documenti. Le anticipazioni in nome
e per conto del cliente sono escluse da IVA ex art. 15 D.P.R. 633/1972.

Perimetro dichiarato (fail-closed): questo modulo REGISTRA e RICONCILIA i
movimenti e li ESPORTA per il commercialista; non calcola imposte, ritenute
o contributi — la qualificazione fiscale resta al professionista incaricato.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

FONTE_NORMATIVA = (
    "Art. 54 TUIR (principio di cassa); art. 19 D.P.R. 600/1973; "
    "artt. 15, 23-25 D.P.R. 633/1972; L. 190/2014 (forfettario)"
)

TIPI_MOVIMENTO = ("INCASSO", "PAGAMENTO")

# Categorie del piano dei conti minimo di uno studio legale. Le anticipazioni
# ex art. 15 sono una categoria dedicata: vanno tenute distinte dagli onorari.
CATEGORIE = {
    "INCASSO": (
        "onorari",
        "anticipazioni_rimborsate",  # rimborso spese ex art. 15 D.P.R. 633/72
        "altri_incassi",
    ),
    "PAGAMENTO": (
        "anticipazioni_clienti",  # CU, marche, diritti pagati per conto del cliente
        "spese_studio",           # canoni, utenze, cancelleria
        "compensi_terzi",         # domiciliatari, CTP, collaboratori
        "imposte_contributi",     # F24, Cassa Forense (registrati, non calcolati)
        "altri_pagamenti",
    ),
}

METODI = ("banca", "cassa", "pos", "altro")


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _iso_date(value: Any) -> str:
    raw = _norm(value)[:10]
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return ""


@dataclass
class MovimentoPrimaNota:
    """Un movimento del registro cronologico (principio di cassa)."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12].upper())
    data: str = field(default_factory=lambda: date.today().isoformat())
    tipo: str = "INCASSO"
    importo: float = 0.0
    categoria: str = "onorari"
    controparte: str = ""  # cliente, fornitore, erario...
    causale: str = ""
    metodo: str = "banca"
    # Collegamenti al gestionale (riconciliazione).
    parcella_id: str = ""
    fascicolo_id: str = ""
    cliente_id: str = ""
    documento_riferimento: str = ""  # numero fattura/ricevuta
    note: str = ""
    creato_da: str = ""
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    # Riconciliazione bancaria: valorizzati alla conferma dell'abbinamento
    # con una riga dell'estratto conto (mai automatica).
    riconciliato_il: str = ""
    riga_estratto_id: str = ""
    # Storno strutturato: id del movimento stornato (il marcatore testuale
    # nelle note resta per retrocompatibilita' di lettura).
    storno_di: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, dati: dict[str, Any]) -> "MovimentoPrimaNota":
        return cls(**{k: v for k, v in dict(dati or {}).items() if k in cls.__dataclass_fields__})


class GestionePrimaNota:
    """Registro cronologico tenant-aware (JSON), append-oriented.

    I movimenti non si cancellano: si stornano con un movimento di segno
    opposto collegato (``storna``), cosi' il registro resta ricostruibile —
    coerente con l'impianto probatorio del gestionale.
    """

    def __init__(self, db_path: str = "./contabilita/prima_nota.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._movimenti: dict[str, MovimentoPrimaNota] = {}
        self._carica()

    def _carica(self) -> None:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            self._movimenti = {k: MovimentoPrimaNota.from_dict(v) for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError):
            self._movimenti = {}

    def _salva(self) -> None:
        self.db_path.write_text(
            json.dumps({k: v.to_dict() for k, v in self._movimenti.items()}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------ scritture
    def registra(self, **campi: Any) -> MovimentoPrimaNota:
        movimento = MovimentoPrimaNota(
            **{k: v for k, v in campi.items() if k in MovimentoPrimaNota.__dataclass_fields__}
        )
        if movimento.tipo not in TIPI_MOVIMENTO:
            raise ValueError(f"Tipo movimento non valido: {movimento.tipo}.")
        if not _iso_date(movimento.data):
            raise ValueError("Data movimento non valida: atteso formato ISO (YYYY-MM-DD).")
        movimento.data = _iso_date(movimento.data)
        try:
            movimento.importo = round(float(movimento.importo), 2)
        except (TypeError, ValueError) as exc:
            raise ValueError("Importo non numerico.") from exc
        if movimento.importo <= 0:
            raise ValueError("L'importo deve essere positivo: per correggere usa lo storno.")
        if movimento.categoria not in CATEGORIE[movimento.tipo]:
            raise ValueError(
                f"Categoria '{movimento.categoria}' non prevista per {movimento.tipo}: "
                f"ammesse {', '.join(CATEGORIE[movimento.tipo])}."
            )
        if movimento.metodo not in METODI:
            movimento.metodo = "altro"
        self._movimenti[movimento.id] = movimento
        self._salva()
        return movimento

    def storna(self, movimento_id: str, *, motivo: str, attore: str = "") -> MovimentoPrimaNota:
        """Storno con movimento contrario collegato: il registro non si riscrive."""

        originale = self._movimenti.get(movimento_id)
        if originale is None:
            raise KeyError(f"Movimento {movimento_id} non trovato.")
        if not _norm(motivo):
            raise ValueError("Lo storno richiede il motivo.")
        marcatore = f"storno di {movimento_id}".casefold()
        gia_stornato = any(
            m.storno_di == movimento_id or marcatore in str(m.note or "").casefold()
            for m in self._movimenti.values()
        )
        if gia_stornato:
            raise ValueError("Movimento gia' stornato.")
        contrario = "PAGAMENTO" if originale.tipo == "INCASSO" else "INCASSO"
        categoria_contraria = (
            "altri_pagamenti" if contrario == "PAGAMENTO" else "altri_incassi"
        )
        nota_storno = f"Storno di {movimento_id}: {_norm(motivo)}"
        if originale.riconciliato_il:
            nota_storno += (
                f" [il movimento era riconciliato con la riga estratto {originale.riga_estratto_id}: "
                "verifica la riconciliazione bancaria]"
            )
        storno = MovimentoPrimaNota(
            data=date.today().isoformat(),
            tipo=contrario,
            importo=originale.importo,
            categoria=categoria_contraria,
            controparte=originale.controparte,
            causale=f"Storno: {_norm(motivo)}",
            metodo=originale.metodo,
            parcella_id=originale.parcella_id,
            fascicolo_id=originale.fascicolo_id,
            cliente_id=originale.cliente_id,
            note=nota_storno,
            creato_da=attore,
            storno_di=movimento_id,
        )
        self._movimenti[storno.id] = storno
        self._salva()
        return storno

    # ------------------------------------------------------------------ letture
    def registro(self, *, dal: str = "", al: str = "", tipo: str = "") -> list[MovimentoPrimaNota]:
        rows = list(self._movimenti.values())
        if dal:
            rows = [m for m in rows if m.data >= _iso_date(dal)]
        if al:
            rows = [m for m in rows if m.data <= _iso_date(al)]
        if tipo:
            rows = [m for m in rows if m.tipo == tipo]
        rows.sort(key=lambda m: (m.data, m.creato_il))
        return rows

    def saldi(self, *, dal: str = "", al: str = "") -> dict[str, Any]:
        rows = self.registro(dal=dal, al=al)
        incassi = round(sum(m.importo for m in rows if m.tipo == "INCASSO"), 2)
        pagamenti = round(sum(m.importo for m in rows if m.tipo == "PAGAMENTO"), 2)
        per_categoria: dict[str, float] = {}
        for m in rows:
            per_categoria[m.categoria] = round(per_categoria.get(m.categoria, 0.0) + m.importo, 2)
        return {
            "incassi": incassi,
            "pagamenti": pagamenti,
            "saldo": round(incassi - pagamenti, 2),
            "per_categoria": per_categoria,
            "movimenti": len(rows),
        }

    # ------------------------------------------------------------ riconciliazione
    def incassi_da_parcelle(self, gestione_fatturazione: Any, *, attore: str = "") -> list[MovimentoPrimaNota]:
        """Importa come incassi le parcelle pagate non ancora registrate.

        Idempotente per ``parcella_id``: una parcella pagata genera al massimo
        un incasso in prima nota. L'importo e' il totale della parcella; la
        data e' la data di pagamento registrata in fatturazione.
        """

        gia_registrate = {m.parcella_id for m in self._movimenti.values() if m.parcella_id}
        creati: list[MovimentoPrimaNota] = []
        try:
            parcelle = list(gestione_fatturazione.tutte())
        except Exception:
            return []
        for parcella in parcelle:
            stato = str(getattr(getattr(parcella, "stato", ""), "value", getattr(parcella, "stato", "")) or "")
            if stato.upper() not in {"PAGATA", "INCASSATA"}:
                continue
            parcella_id = str(getattr(parcella, "id", "") or "")
            if not parcella_id or parcella_id in gia_registrate:
                continue
            data_pagamento = _iso_date(getattr(parcella, "data_pagamento", "")) or date.today().isoformat()
            try:
                importo = round(float(getattr(parcella, "totale", 0.0) or 0.0), 2)
            except (TypeError, ValueError):
                continue
            if importo <= 0:
                continue
            movimento = self.registra(
                data=data_pagamento,
                tipo="INCASSO",
                importo=importo,
                categoria="onorari",
                controparte=_norm(getattr(parcella, "intestatario", "") or getattr(parcella, "nome_cliente", "")),
                causale=f"Incasso parcella {_norm(getattr(parcella, 'numero', '') or parcella_id)}",
                metodo="banca",
                parcella_id=parcella_id,
                fascicolo_id=_norm(getattr(parcella, "id_fascicolo", "")),
                cliente_id=_norm(getattr(parcella, "id_cliente", "")),
                documento_riferimento=_norm(getattr(parcella, "numero", "")),
                creato_da=attore or "riconciliazione-parcelle",
            )
            creati.append(movimento)
        return creati

    # ------------------------------------------------------------ riconciliazione bancaria
    def _e_storno_o_stornato(self, movimento: MovimentoPrimaNota) -> bool:
        if movimento.storno_di or str(movimento.note or "").casefold().startswith("storno di"):
            return True
        marcatore = f"storno di {movimento.id}".casefold()
        return any(
            m.storno_di == movimento.id or marcatore in str(m.note or "").casefold()
            for m in self._movimenti.values()
        )

    def marca_riconciliato(
        self,
        movimento_id: str,
        *,
        riga_estratto_id: str,
        importo_riga: float | None = None,
        verso_riga: str = "",
    ) -> MovimentoPrimaNota:
        """Conferma dell'abbinamento con una riga dell'estratto conto.

        Validazioni server-side (il client non e' fidato): il movimento non
        deve essere gia' riconciliato, ne' uno storno o stornato; se il
        chiamante fornisce importo e verso della riga bancaria, devono
        coincidere col movimento; la stessa riga non puo' riconciliare due
        movimenti diversi.
        """

        movimento = self._movimenti.get(movimento_id)
        if movimento is None:
            raise KeyError(f"Movimento {movimento_id} non trovato.")
        if movimento.riconciliato_il:
            raise ValueError("Movimento gia' riconciliato con l'estratto conto.")
        if self._e_storno_o_stornato(movimento):
            raise ValueError("Gli storni e i movimenti stornati non si riconciliano con la banca.")
        riga_id = _norm(riga_estratto_id)
        if not riga_id:
            raise ValueError("Riga estratto mancante per la riconciliazione.")
        if any(m.riga_estratto_id == riga_id for m in self._movimenti.values()):
            raise ValueError("Questa riga dell'estratto e' gia' riconciliata con un altro movimento.")
        if importo_riga is not None and abs(abs(float(importo_riga)) - movimento.importo) > 0.005:
            raise ValueError(
                "L'importo della riga bancaria non coincide col movimento selezionato: abbinamento rifiutato."
            )
        if verso_riga and verso_riga != movimento.tipo:
            raise ValueError(
                "Il verso della riga bancaria (incasso/pagamento) non coincide col movimento: abbinamento rifiutato."
            )
        movimento.riconciliato_il = datetime.now().isoformat(timespec="seconds")
        movimento.riga_estratto_id = riga_id
        self._salva()
        return movimento

    def non_riconciliati(self, *, dal: str = "", al: str = "") -> list[MovimentoPrimaNota]:
        """Movimenti bancari senza riscontro: esclusi contanti, storni e stornati."""

        return [
            m for m in self.registro(dal=dal, al=al)
            if not m.riconciliato_il and m.metodo != "cassa" and not self._e_storno_o_stornato(m)
        ]

    # ------------------------------------------------------------------ export
    def esporta_csv(self, *, dal: str = "", al: str = "") -> str:
        """Registro cronologico in CSV per il commercialista (delimitatore ;)."""

        def _sicura(value: str) -> str:
            # Anti formula-injection: una cella che inizia con =, +, -, @ verrebbe
            # eseguita come formula da Excel/Calc — prefisso apostrofo.
            testo = str(value or "")
            return f"'{testo}" if testo[:1] in {"=", "+", "-", "@"} else testo

        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", lineterminator="\n")
        writer.writerow(
            ["Data", "Tipo", "Importo", "Categoria", "Controparte", "Causale", "Metodo", "Documento", "Fascicolo", "Note"]
        )
        for m in self.registro(dal=dal, al=al):
            writer.writerow(
                [
                    m.data,
                    m.tipo,
                    f"{m.importo:.2f}".replace(".", ","),
                    m.categoria,
                    _sicura(m.controparte),
                    _sicura(m.causale),
                    m.metodo,
                    _sicura(m.documento_riferimento),
                    m.fascicolo_id,
                    _sicura(m.note),
                ]
            )
        return output.getvalue()
