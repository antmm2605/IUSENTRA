"""Adapter template atti per il retrieval applicativo Lex."""

from __future__ import annotations


class TemplateAttiSource:
    source_name = "template_atti"

    def search(self, queries, request, context):
        return []
