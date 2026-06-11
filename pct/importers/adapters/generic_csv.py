"""Adapter CSV generico: prima sorgente del Migration Center.

Mappa le colonne del CSV sui campi del record tramite ``mapping`` (colonna→campo);
senza mapping usa le intestazioni così come sono. Non scrive nulla: produce solo
record di staging.
"""

from __future__ import annotations

import csv
import io

from ..base import ImportError_, RecordKind, StagedRecord


class GenericCsvAdapter:
    name = "generic_csv"

    def parse(self, raw: bytes, *, kind: RecordKind, mapping: dict[str, str] | None = None) -> list[StagedRecord]:
        if raw is None:
            raise ImportError_("Sorgente CSV mancante.")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("latin-1")
            except Exception as exc:  # pragma: no cover - improbabile
                raise ImportError_("CSV con codifica non riconosciuta.") from exc

        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","

        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            raise ImportError_("CSV senza intestazioni di colonna.")

        column_map = {str(k): str(v) for k, v in (mapping or {}).items()}
        records: list[StagedRecord] = []
        for index, row in enumerate(reader, start=2):  # riga 1 = intestazioni
            data: dict[str, str] = {}
            for column, value in row.items():
                if column is None:
                    continue
                field_name = column_map.get(column, column).strip()
                if not field_name:
                    continue
                data[field_name] = str(value if value is not None else "").strip()
            if not any(data.values()):
                continue  # riga vuota
            records.append(StagedRecord(kind=kind, source_ref=f"row:{index}", data=data))
        return records


__all__ = ["GenericCsvAdapter"]
