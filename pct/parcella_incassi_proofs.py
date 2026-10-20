"""Riscontro condiviso degli importi e della fonte nativa di ogni movimento."""
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from pct.prima_nota import METODI
from pct.prima_nota_repository import _encode


def _cents(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount != amount.quantize(Decimal('0.01')):
            raise ValueError('Importo privo di una rappresentazione esatta in centesimi.')
        return int(amount * 100)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('Importo non valido.') from exc


def _cash_sha(payload):
    # La riconciliazione aggiunge riscontri senza riscrivere il fatto di cassa.
    identity = {key: value for key, value in payload.items()
                if key not in {'riconciliato_il', 'riga_estratto_id'}}
    return hashlib.sha256(_encode(identity).encode('utf-8')).hexdigest()


def install_proof_guards(conn, *, postgres):
    if postgres:
        schema = str(conn.execute('SELECT current_schema()').fetchone()[0]).replace('"', '""')
        function = f'"{schema}".iusentra_receipt_proofs_immutable'
        conn.execute(f"CREATE OR REPLACE FUNCTION {function}() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'Prove incassi immutabili: usare uno storno'; END; $$")
        conn.execute('DROP TRIGGER IF EXISTS iusentra_receipt_proofs_immutable ON parcella_incassi_proofs')
        conn.execute('CREATE TRIGGER iusentra_receipt_proofs_immutable BEFORE UPDATE OR DELETE '
            f'ON parcella_incassi_proofs FOR EACH ROW EXECUTE FUNCTION {function}()')
    else:
        for operation in ('UPDATE', 'DELETE'):
            conn.execute(f'CREATE TRIGGER IF NOT EXISTS iusentra_receipt_proofs_no_{operation.lower()} '
                f'BEFORE {operation} ON parcella_incassi_proofs BEGIN '
                "SELECT RAISE(ABORT,'Prove incassi immutabili: usare uno storno'); END")


def verified_receipt(invoice_id, movement_id, cents, direction, digest, payload, reverses_id, paid_on):
    if payload is None:
        raise ValueError('Movimento di Prima nota collegato non presente.')
    source = json.loads(payload)
    reverse = reverses_id or ''
    if (not isinstance(source, dict) or source.get('id') != movement_id
            or source.get('parcella_id') != invoice_id or _cash_sha(source) != digest
            or _cents(source.get('importo')) != int(cents) or int(cents) <= 0
            or int(direction) not in {-1, 1}
            or source.get('tipo') != ('INCASSO' if int(direction) == 1 else 'PAGAMENTO')
            or source.get('storno_di', '') != reverse or source.get('data') != paid_on
            or not isinstance(paid_on, str) or date.fromisoformat(paid_on).isoformat() != paid_on
            or source.get('metodo') not in METODI or not isinstance(source.get('note'), str)):
        raise ValueError('Prova di incasso discordante dalla fonte di Prima nota.')
    return {'movement_id': movement_id, 'amount_cents': int(cents), 'direction': int(direction),
            'paid_on': paid_on, 'method': source['metodo'], 'note': source['note'],
            'reverses_movement_id': reverse, 'client_id': source.get('cliente_id', ''),
            'case_id': source.get('fascicolo_id', '')}
