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
import math
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .formatting import format_date_it

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
        "imposte_contributi",     # F24 e altre imposte (registrate, non calcolate)
        "contributi_previdenziali",  # Cassa Forense: deducibili (art. 10 TUIR; art. 1 c. 64 L. 190/2014)
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

    def __init__(self, db_path: str = "./contabilita/prima_nota.json", *, studio_db=None, tenant_key: str = "", actor_key: str = ""):
        self.db_path = Path(db_path)
        self._repository = None
        if studio_db is not None:
            from pct.prima_nota_repository import PrimaNotaRepository
            self._repository = PrimaNotaRepository(studio_db, tenant_key, actor_key=actor_key)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._movimenti: dict[str, MovimentoPrimaNota] = {}
        self._source_bytes: bytes | None = None
        self._carica()

    def _carica(self) -> None:
        if self._repository is not None:
            self._movimenti = {key: MovimentoPrimaNota.from_dict(value) for key, value in self._repository.load().items()}
            return
        from pct.prima_nota_transition import assert_json_source_active
        assert_json_source_active(self.db_path)
        try:
            content = self.db_path.read_bytes()
            raw = json.loads(content.decode("utf-8"))
            if not isinstance(raw, dict) or any(not isinstance(value, dict) for value in raw.values()):
                raise ValueError("Struttura del registro non valida.")
            movements = {key: MovimentoPrimaNota.from_dict(value) for key, value in raw.items()}
        except FileNotFoundError:
            self._movimenti = {}
            self._source_bytes = None
            return
        except (OSError, ValueError, TypeError) as exc:
            raise ValueError("Prima nota non leggibile: il registro esistente è stato preservato. "
                             "La registrazione è sospesa fino al recupero dell’archivio.") from exc
        self._movimenti = movements
        self._source_bytes = content

    def _salva(self, *, command=None):
        if self._repository is not None:
            confirmed = dict(self._repository.original)
            try:
                result = self._repository.save({key: value.to_dict() for key, value in self._movimenti.items()}, command=command)
                if self._repository.last_command_replayed:
                    self._carica()
                return result
            except Exception:
                try:
                    self._carica()
                except Exception:
                    # Conserva solo l'ultimo snapshot confermato; il primo errore
                    # resta quello del comando, senza inventare un esito negativo.
                    self._movimenti = {key: MovimentoPrimaNota.from_dict(json.loads(value)) for key, value in confirmed.items()}
                raise
        if command is not None:
            raise ValueError('Conferma persistente del comando non disponibile sul registro storico.')
        from pct.prima_nota_transition import prima_nota_source_lock, assert_json_source_active

        temporary = None
        confirmed_source = self._source_bytes
        try:
            with prima_nota_source_lock(self.db_path):
                assert_json_source_active(self.db_path)
                try:
                    current = self.db_path.read_bytes()
                except FileNotFoundError:
                    current = None
                if current != self._source_bytes:
                    from pct.prima_nota_repository import PrimaNotaConflict
                    raise PrimaNotaConflict("Prima nota aggiornata da un altro processo: ricarica il registro prima di riprovare.")
                content = json.dumps(
                    {k: v.to_dict() for k, v in self._movimenti.items()},
                    ensure_ascii=False, indent=1,
                ).encode("utf-8")
                with tempfile.NamedTemporaryFile(dir=self.db_path.parent, prefix=".prima-nota-", delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.db_path)
                temporary = None
                self._source_bytes = content
        except Exception:
            # Non mantenere come salvato il movimento di un comando rifiutato.
            # Il fallimento della rilettura non deve nascondere l'errore primario.
            try:
                self._carica()
            except Exception:
                # Un fence impedisce anche la rilettura JSON: conserva soltanto
                # lo snapshot già confermato, non il comando locale rifiutato.
                previous = json.loads(confirmed_source.decode('utf-8')) if confirmed_source is not None else {}
                self._movimenti = {key: MovimentoPrimaNota.from_dict(value) for key, value in previous.items()}
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def confirm_audit(self, movement_id=None):
        if self._repository is None:
            raise ValueError('Consegna audit SQL non disponibile sul registro storico.')
        return self._repository.deliver_audit(record_key=movement_id)

    @property
    def write_protocol(self) -> dict[str, Any]:
        """Capacità effettiva del repository, senza aprire o migrare archivi."""
        import hashlib
        scope = hashlib.sha256(json.dumps([self._repository.tenant, self._repository.actor_key]).encode()).hexdigest() if self._repository is not None else None
        return {"persistentCommands": self._repository is not None,
                "revision": self._repository.revision if self._repository is not None else None,
                "scope": scope}

    # ------------------------------------------------------------------ scritture
    def registra(self, *, command_key: str = "", expected_revision: int | None = None, **campi: Any) -> MovimentoPrimaNota:
        command = None
        if expected_revision is not None:
            if type(expected_revision) is not int or expected_revision < 0:
                raise ValueError('Revisione del registro non valida.')
            if self._repository is None or not command_key:
                raise ValueError('Revisione protetta disponibile soltanto con un comando SQL persistente.')
        if self._repository is not None:
            self._repository.last_command_replayed = False
        if command_key:
            if self._repository is None:
                raise ValueError('Conferma persistente del comando non disponibile sul registro storico.')
            if set(campi) - MovimentoPrimaNota.__dataclass_fields__.keys() or set(campi) & {'id', 'creato_il', 'riconciliato_il', 'riga_estratto_id', 'storno_di'}:
                raise ValueError('Campi del comando di registrazione non consentiti.')
            import hashlib
            from pct.prima_nota_repository import _encode
            intent = campi if expected_revision is None else {'fields': campi, 'expected_revision': expected_revision}
            command = {'key': command_key, 'operation': 'registrazione',
                       'request_sha256': hashlib.sha256(_encode(intent).encode('utf-8')).hexdigest()}
            replay = self._repository.command_replay(command)
            if replay is not None:
                self._carica()
                self._repository.last_command_replayed = True
                return MovimentoPrimaNota.from_dict(replay['movement'])
        if expected_revision is not None and expected_revision != self._repository.revision:
            from pct.prima_nota_repository import PrimaNotaConflict
            raise PrimaNotaConflict('Il registro è cambiato. Ricarica i dati prima di registrare il movimento; la bozza è preservata.')
        movimento = self._prepara_movimento(**campi)
        if movimento.id in self._movimenti:
            raise ValueError("Identificativo del movimento già presente nel registro.")
        self._movimenti[movimento.id] = movimento
        if command is not None:
            command['result'] = {'movement': movimento.to_dict()}
        result = self._salva(command=command)
        if command is not None:
            return MovimentoPrimaNota.from_dict(result['movement'])
        return movimento

    def registra_da_riga(self, *, riga_estratto_id: str, **campi: Any) -> MovimentoPrimaNota:
        """Movimento bancario e riscontro salvati insieme, con replay concordante."""
        riga_id = _norm(riga_estratto_id)
        if not riga_id:
            raise ValueError('Riga estratto mancante.')
        movimento = self._prepara_movimento(**campi)
        for existing in self._movimenti.values():
            if existing.riga_estratto_id != riga_id:
                continue
            if any(getattr(existing, field) != getattr(movimento, field)
                   for field in ('data', 'tipo', 'importo', 'categoria', 'causale', 'metodo')):
                raise ValueError('La riga bancaria è già presente con dati diversi: verifica necessaria.')
            return existing
        movimento.riga_estratto_id = riga_id
        movimento.riconciliato_il = datetime.now().isoformat(timespec='seconds')
        self._movimenti[movimento.id] = movimento
        self._salva()
        return movimento

    def _prepara_movimento(self, **campi: Any) -> MovimentoPrimaNota:
        """Valida senza scrivere: riuso per comando singolo e lotto atomico."""
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
        if not math.isfinite(movimento.importo) or movimento.importo <= 0:
            raise ValueError("L'importo deve essere positivo: per correggere usa lo storno.")
        if movimento.categoria not in CATEGORIE[movimento.tipo]:
            raise ValueError(
                f"Categoria '{movimento.categoria}' non prevista per {movimento.tipo}: "
                f"ammesse {', '.join(CATEGORIE[movimento.tipo])}."
            )
        if movimento.metodo not in METODI:
            movimento.metodo = "altro"
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
        pending: dict[str, MovimentoPrimaNota] = {}
        creati: list[MovimentoPrimaNota] = []
        try:
            parcelle = list(gestione_fatturazione.tutte())
        except Exception as exc:
            raise ValueError("Parcelle non leggibili: riconciliazione sospesa senza confermare l'allineamento.") from exc
        for parcella in parcelle:
            stato = str(getattr(getattr(parcella, "stato", ""), "value", getattr(parcella, "stato", "")) or "")
            if stato.upper() not in {"PAGATA", "INCASSATA"}:
                continue
            parcella_id = str(getattr(parcella, "id", "") or "")
            if not parcella_id:
                raise ValueError("Parcella pagata senza identificativo: importazione sospesa.")
            if parcella_id in gia_registrate:
                continue
            data_pagamento = _iso_date(getattr(parcella, "data_pagamento", ""))
            if not data_pagamento:
                raise ValueError("Parcella pagata senza data valida di pagamento: importazione sospesa.")
            try:
                importo = round(float(getattr(parcella, "totale", 0.0) or 0.0), 2)
            except (TypeError, ValueError) as exc:
                raise ValueError("Importo della parcella pagata non valido: importazione sospesa.") from exc
            if not math.isfinite(importo) or importo <= 0:
                raise ValueError("Importo della parcella pagata non valido: importazione sospesa.")
            movimento = self._prepara_movimento(
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
            if parcella_id in pending:
                previous = pending[parcella_id].to_dict()
                candidate = movimento.to_dict()
                for key in ("id", "creato_il"):
                    previous.pop(key)
                    candidate.pop(key)
                if candidate != previous:
                    raise ValueError("La stessa parcella ha dati discordanti: importazione sospesa.")
                continue
            pending[parcella_id] = movimento
            creati.append(movimento)
        if creati:
            for movimento in creati:
                if movimento.id in self._movimenti:
                    raise ValueError("Identificativo del movimento già presente nel registro.")
            self._movimenti.update({movimento.id: movimento for movimento in creati})
            self._salva()
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
        if importo_riga is not None:
            try:
                amount = float(importo_riga)
            except (TypeError, ValueError) as exc:
                raise ValueError("Importo della riga bancaria non valido: abbinamento rifiutato.") from exc
            if not math.isfinite(amount) or abs(abs(amount) - movimento.importo) > 0.005:
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
                    format_date_it(m.data),
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
