"""Contratto HTTP degli incassi; usato dal generatore OpenAPI nativo."""
from __future__ import annotations


def apply_receipt_contract(operation, method):
    text = {'type': 'string'}
    cents = {'type': 'integer', 'minimum': 0, 'maximum': 9007199254740991}
    digest = {'type': 'string', 'pattern': '^[a-f0-9]{64}$'}
    command = {'type': 'string', 'format': 'uuid'}
    common = {'operation': text, 'command_key': command, 'expected_revision': digest,
              'scope': digest, 'paid_on': {'type': 'string', 'format': 'date'}}
    methods = {'type': 'string', 'enum': ['banca', 'cassa', 'pos', 'altro']}
    variants = []
    for kind, fields in (
        ('receipt', {'amount_cents': {**cents, 'minimum': 1}, 'method': methods,
                     'note': {'type': 'string', 'maxLength': 2000}}),
        ('reversal', {'movement_id': text,
                      'reason': {'type': 'string', 'minLength': 1, 'maxLength': 2000}}),
    ):
        properties = {**common, **fields, 'operation': {'type': 'string', 'enum': [kind]}}
        variants.append({'type': 'object', 'additionalProperties': False,
                         'required': list(properties), 'properties': properties})
    receipt = {'type': 'object', 'required': ['movement_id', 'amount_cents', 'direction', 'paid_on'],
               'properties': {'movement_id': text, 'amount_cents': {**cents, 'minimum': 1},
                              'direction': {'type': 'integer', 'enum': [1, -1]},
                              'paid_on': {'type': 'string', 'format': 'date'}, 'method': methods,
                              'note': text, 'reverses_movement_id': text, 'reversed': {'type': 'boolean'}}}
    summary = {'type': 'object', 'required': ['invoice_id', 'status', 'paid_cents', 'residual_cents',
                                           'due_cents', 'revision', 'command_scope', 'can_write', 'receipts'],
               'properties': {'invoice_id': text,
                              'status': {'type': 'string', 'enum': ['OPEN', 'PARTIAL', 'PAID', 'DRAFT', 'CANCELLED', 'REVIEW']},
                              **{key: {**cents, 'nullable': True} for key in
                                 ('paid_cents', 'residual_cents', 'due_cents')},
                              'revision': digest, 'command_scope': digest,
                              'can_write': {'type': 'boolean'}, 'reason': text,
                              'receipts': {'type': 'array', 'items': receipt}}}
    response = {'type': 'object', 'required': ['ok', 'summary'],
                'properties': {'ok': {'type': 'boolean'}, 'summary': summary}}
    if method == 'POST':
        operation['requestBody'] = {'required': True, 'content': {
            'application/json': {'schema': {'oneOf': variants}}}}
        response['required'] += ['movement_id', 'already_present', 'confirmed_command']
        response['properties'].update({
            'movement_id': text, 'already_present': {'type': 'boolean'},
            'confirmed_command': {'type': 'object', 'additionalProperties': False,
                                  'required': ['scope', 'command_key', 'invoice_id', 'expected_revision'],
                                  'properties': {'scope': digest, 'command_key': command,
                                                 'invoice_id': text, 'expected_revision': digest}},
        })
    operation['security'] = [{'cookieSession': []}]
    operation['responses']['200'] = {'description': 'Saldo verificato; POST conferma lo stesso comando persistito.',
                                     'content': {'application/json': {'schema': response}}}
    operation['responses']['503'] = {
        'description': 'Esito non confermato: conservare il comando e verificarlo senza crearne uno nuovo.'}
