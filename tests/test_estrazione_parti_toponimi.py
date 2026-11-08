"""Una strada nell'indirizzo della parte non è il nome della parte (caso reale 08/11/2026, RG 833/2025)."""
from pct.archivio_letture.estrazione_parti import estrai_parti

STUDIO = ["Giuseppe Montagnese"]


def _assistiti(testo):
    return [p.nome for p in estrai_parti(testo, avvocati_studio=STUDIO) if p.ruolo == "assistito"]


def test_via_pietro_nenni_non_e_la_ricorrente():
    testo = ("Per: la Prof.ssa Furiglio Nancy, c.f. FRGNNC80A41G288X, residente in Taurianova, via Pietro Nenni, "
             "rappresentata e difesa dall’Avv. Giuseppe Montagnese con procura allegata\ncontro\nMINISTERO DELL'ISTRUZIONE E DEL MERITO")
    assert _assistiti(testo) == ["Furiglio Nancy"]


def test_altri_toponimi():
    for strada in ("piazza Giuseppe Garibaldi", "corso Vittorio Emanuele", "c.da Santa Maria", "viale Aldo Moro"):
        testo = (f"Per: la Sig.ra Rossi Maria residente in Palmi {strada}, rappresentata e difesa dall’Avv. Giuseppe Montagnese"
                 "\ncontro\nMINISTERO DELL'ISTRUZIONE E DEL MERITO")
        assert _assistiti(testo) == ["Rossi Maria"], strada


def test_nome_della_parte_resta_riconosciuto():
    testo = "Per: Bianchi Luca, rappresentato e difeso dall’Avv. Giuseppe Montagnese\ncontro\nCOMUNE DI PALMI"
    assert _assistiti(testo) == ["Bianchi Luca"]
