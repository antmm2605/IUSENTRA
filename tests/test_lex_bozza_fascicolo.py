"""La bozza di Lex nel fascicolo: PDF tra le bozze del passo, segnaposti contati, nessun duplicato, mai firmata."""
from __future__ import annotations

from types import SimpleNamespace

from pct.bozze_passi.archivio import ArchivioBozze

TESTO = ("TRIBUNALE DI BARI\nATTO DI CITAZIONE\n(artt. 163 ss. c.p.c.)\n\nPer: Luca Ferrandina, codice fiscale "
         "[da completare], residente in [luogo da completare]\nIN FATTO\n1. Il preliminare del 10/01/2026.")


class _Repo:
    def __init__(self):
        self.documenti = []

    def aggiungi_documento(self, fascicolo_id, nome, tipo, contenuto, **altro):
        doc = SimpleNamespace(id=f"D{len(self.documenti) + 1}", nome=nome, contenuto=contenuto, **altro)
        self.documenti.append(doc)
        return doc


def test_bozza_salvata_come_pdf_una_volta_sola(tmp_path, monkeypatch):
    import web.services.document_crypto as cifra
    from web.services.lex_bozza_fascicolo import salva_bozza

    monkeypatch.setattr(cifra, "encrypt_doc", lambda b: b)
    repo, archivio = _Repo(), ArchivioBozze(tmp_path / "bozze_passi.sqlite")
    esito = salva_bozza("F1", titolo="Atto di citazione", testo=TESTO, modello="CIV_ORD_015", repository=repo,
                        archivio=archivio, puo_scrivere=lambda: True)
    assert esito["salvata"] and esito["da_completare"] == ["codice fiscale", "luogo"]
    doc = repo.documenti[0]
    assert doc.contenuto.startswith(b"%PDF") and "bozza-lex" in doc.tags and "Non è stata inviata" in doc.note
    voce = archivio.del_fascicolo("F1")[0]
    assert voce.formato == "pdf" and voce.documento_id == doc.id
    di_nuovo = salva_bozza("F1", titolo="Atto di citazione", testo=TESTO, modello="CIV_ORD_015", repository=repo,
                           archivio=archivio, puo_scrivere=lambda: True)
    assert di_nuovo["gia_presente"] and len(repo.documenti) == 1


def test_senza_permesso_di_scrittura_niente_documento(tmp_path):
    from web.services.lex_bozza_fascicolo import salva_bozza

    repo = _Repo()
    esito = salva_bozza("F1", titolo="Atto", testo=TESTO, modello="X", repository=repo,
                        archivio=ArchivioBozze(tmp_path / "b.sqlite"), puo_scrivere=lambda: False)
    assert not esito["salvata"] and not repo.documenti
