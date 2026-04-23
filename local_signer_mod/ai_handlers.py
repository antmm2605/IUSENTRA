from __future__ import annotations

from typing import Any, Callable

from .ai_cache import TimedResultCache


class LocalAiHandlerFacade:
    _cache = TimedResultCache(ttl_seconds=20, max_items=128)

    def __init__(
        self,
        *,
        get_bridge: Callable[[], Any],
        request_payload_factory: Callable[[dict[str, Any] | None], dict[str, Any]],
        read_json: Callable[[], dict[str, Any]],
        send_json: Callable[[dict[str, Any], int | None], None] | Callable[..., None],
        stream_sse: Callable[[Any], None] | None,
        logger: Any,
        parse_attachment_payloads: Any = None,
        build_attachment_prompt_block: Any = None,
    ) -> None:
        self.get_bridge = get_bridge
        self.request_payload_factory = request_payload_factory
        self.read_json = read_json
        self.send_json = send_json
        self.stream_sse = stream_sse
        self.logger = logger
        self.parse_attachment_payloads = parse_attachment_payloads
        self.build_attachment_prompt_block = build_attachment_prompt_block

    def _send(self, payload: dict[str, Any], status: int = 200) -> None:
        try:
            self.send_json(payload, status)
        except TypeError:
            self.send_json(payload)

    def _stream(self, events: Any) -> None:
        if self.stream_sse is None:
            self._send(
                {"ok": False, "errore": "Streaming AI locale non disponibile su questo server."},
                501,
            )
            return
        self.stream_sse(events)

    def status(self) -> None:
        try:
            bridge = self.get_bridge()
            payload_seed = self.request_payload_factory(None)
            payload = self._cache.get_or_set(
                "ai_status",
                payload_seed,
                lambda: bridge.health_snapshot(payload_seed),
            )
            self._send(payload)
        except Exception as exc:
            self.logger.error("Errore AI status locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)

    def bootstrap(self) -> None:
        try:
            data = self.read_json()
            bridge = self.get_bridge()
            payload = bridge.bootstrap_runtime(
                self.request_payload_factory(data),
                force=str(data.get("force", "")).strip().lower() in {"1", "true", "yes", "on"},
            )
            self._send(payload)
        except Exception as exc:
            self.logger.error("Errore AI bootstrap locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)

    def attachments_parse(self) -> None:
        if self.parse_attachment_payloads is None or self.build_attachment_prompt_block is None:
            self._send(
                {"ok": False, "errore": "Parser documentale locale non disponibile sul companion."},
                501,
            )
            return
        try:
            data = self.read_json()
            attachments, errors = self.parse_attachment_payloads(
                data.get("files") or data.get("attachments") or []
            )
            prompt_block = self.build_attachment_prompt_block(attachments)
            self._send(
                {
                    "ok": True,
                    "attachments": attachments,
                    "errors": errors,
                    "prompt_block": prompt_block,
                }
            )
        except Exception as exc:
            self.logger.error("Errore parse allegati AI locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)

    def chat(self) -> None:
        data = self.request_payload_factory(None)
        prompt = str(data.get("prompt") or "").strip()
        if not prompt:
            self._send({"ok": False, "errore": "Prompt mancante."}, 400)
            return
        try:
            bridge = self.get_bridge()
            payload = bridge.chat(prompt, data)
            self._send(payload)
        except Exception as exc:
            self.logger.error("Errore AI chat locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)

    def chat_stream(self) -> None:
        data = self.request_payload_factory(None)
        prompt = str(data.get("prompt") or "").strip()
        if not prompt:
            self._send({"ok": False, "errore": "Prompt mancante."}, 400)
            return
        try:
            bridge = self.get_bridge()
            self._stream(bridge.chat_stream(prompt, data))
        except Exception as exc:
            self.logger.error("Errore AI chat streaming locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)

    def rag_query(self) -> None:
        data = self.read_json()
        question = str(data.get("question") or "").strip()
        prompt = str(data.get("prompt") or "").strip()
        if not question and not prompt:
            self._send({"ok": False, "errore": "Domanda mancante."}, 400)
            return
        try:
            bridge = self.get_bridge()
            payload = bridge.rag_query({**self.request_payload_factory(data), **data})
            self._send(payload)
        except Exception as exc:
            self.logger.error("Errore AI rag query locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)

    def rag_query_stream(self) -> None:
        data = self.read_json()
        question = str(data.get("question") or "").strip()
        prompt = str(data.get("prompt") or "").strip()
        if not question and not prompt:
            self._send({"ok": False, "errore": "Domanda mancante."}, 400)
            return
        try:
            bridge = self.get_bridge()
            self._stream(bridge.rag_query_stream({**self.request_payload_factory(data), **data}))
        except Exception as exc:
            self.logger.error("Errore AI rag query streaming locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)

    def embed(self) -> None:
        raw_body = self.read_json()
        data = self.request_payload_factory(raw_body)
        raw_inputs = raw_body.get("inputs")
        if not isinstance(raw_inputs, list) or not raw_inputs:
            prompt = str(data.get("prompt") or "").strip()
            raw_inputs = [prompt] if prompt else []
        inputs = [str(value or "").strip() for value in raw_inputs if str(value or "").strip()]
        if not inputs:
            self._send({"ok": False, "errore": "Testo da indicizzare mancante."}, 400)
            return
        try:
            bridge = self.get_bridge()
            payload = bridge.embed(inputs, data)
            self._send(payload)
        except Exception as exc:
            self.logger.error("Errore AI embed locale: %s", exc)
            self._send({"ok": False, "errore": str(exc)}, 500)
