from __future__ import annotations

from lex.dependencies import LexDependencies


class _FakeRequests:
    class exceptions:
        class ConnectionError(Exception):
            pass

    @staticmethod
    def get(*args, **kwargs):
        class _Resp:
            @staticmethod
            def json():
                return {"models": [{"name": "mistral"}]}

        return _Resp()


def _stub_dict(*args, **kwargs):
    return {}


def _stub_str(*args, **kwargs):
    return "ok"


def _stub_bytes(*args, **kwargs):
    return b"docx-bytes"


def _stub_tuple(*args, **kwargs):
    return ([], [])


def test_lex_dependencies_can_be_instantiated():
    deps = LexDependencies(
        requests_module=_FakeRequests(),
        build_studio_context=_stub_dict,
        warm_studio_context=_stub_dict,
        build_today_summary=_stub_dict,
        build_language_guidance=_stub_dict,
        build_prompt=_stub_str,
        resolve_followup_query=_stub_dict,
        resolve_social_and_operational_intent=_stub_dict,
        latest_user_message=_stub_str,
        build_social_only_reply=_stub_str,
        resolved_runtime=_stub_dict,
        warm_runtime=_stub_dict,
        build_unverified_pdf_reply=_stub_str,
        build_docx_bytes=_stub_bytes,
        build_export_filename=_stub_str,
        infer_export_title=_stub_str,
        build_attachment_prompt_block=_stub_str,
        parse_attachment_payloads=_stub_tuple,
    )

    assert deps is not None
    assert callable(deps.build_studio_context)
    assert callable(deps.build_prompt)
    assert callable(deps.parse_attachment_payloads)
