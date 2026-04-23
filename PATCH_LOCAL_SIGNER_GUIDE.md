# Patch guida per `local_signer.py`

## 1) Aggiungi questi import vicino agli altri import custom

```python
from local_signer_mod.security import (
    build_allowed_origins,
    is_allowed_origin,
    is_loopback_origin,
    normalize_origin,
)
from local_signer_mod.ai_handlers import LocalAiHandlerFacade
from local_signer_mod.server_bootstrap import print_startup_banner
```

## 2) Sostituisci le funzioni origin helper locali con bridge verso il modulo

Se vuoi il refactor minimo, tieni i nomi attuali e delega:

```python
def _normalizza_origin(origin: str) -> str:
    return normalize_origin(origin)

def _origin_loopback(origin: str) -> bool:
    return is_loopback_origin(origin)

def _origini_hacs_consentite() -> set[str]:
    return build_allowed_origins(LOCAL_SIGNER_ALLOWED_ORIGINS)

def _origin_cors_consentita(origin: str) -> bool:
    return is_allowed_origin(origin, LOCAL_SIGNER_ALLOWED_ORIGINS)
```

## 3) Dentro `_Handler`, aggiungi una facade lazy

```python
def _ai_facade(self):
    return LocalAiHandlerFacade(
        get_bridge=_get_local_ai_bridge,
        request_payload_factory=self._local_ai_request_payload,
        read_json=self._read_json,
        send_json=self._send_json,
        logger=log,
        parse_attachment_payloads=parse_attachment_payloads,
        build_attachment_prompt_block=build_attachment_prompt_block,
    )
```

## 4) Sostituisci i metodi AI con delega

### `_ai_status`
```python
def _ai_status(self):
    self._ai_facade().status()
```

### `_ai_bootstrap`
```python
def _ai_bootstrap(self):
    self._ai_facade().bootstrap()
```

### `_ai_attachments_parse`
```python
def _ai_attachments_parse(self):
    self._ai_facade().attachments_parse()
```

### `_ai_chat`
```python
def _ai_chat(self):
    self._ai_facade().chat()
```

### `_ai_chat_stream`
```python
def _ai_chat_stream(self):
    self._ai_facade().chat_stream()
```

### `_ai_rag_query`
```python
def _ai_rag_query(self):
    self._ai_facade().rag_query()
```

### `_ai_rag_query_stream`
```python
def _ai_rag_query_stream(self):
    self._ai_facade().rag_query_stream()
```

### `_ai_embed`
```python
def _ai_embed(self):
    self._ai_facade().embed()
```

## 5) Nel `main()` usa il banner helper

Sostituisci il blocco di print iniziale con:

```python
print_startup_banner(
    version=VERSION,
    port=args.port,
    platform_name=sys.platform,
    lib_path=_trova_libreria(),
    curl_available=_curl_disponibile(),
    token_info_fetcher=lambda lib: _info_token(lib),
)
```

## 6) Aggiungi controllo governance opzionale

In CI o locale:
```bash
python tools/check_local_signer_boundaries.py
```
