"""Esecuzione forzata: il profilo viene dal codice oggetto PST o dal precetto, senza alternative fuori tema.

Collaudo 08/11/2026: per l'espropriazione presso terzi (codice oggetto 510002) il presidio proponeva «Responsabilità
medica avanzata»; per un precetto su sentenza del TAR «Istanza di sanatoria edilizia» e «Permesso di costruire».
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.practice_engine import get_profile
from pct.practice_engine.profili_rito import RITO_ESECUZIONE
from pct.practice_engine.resolver import alternative_del_fascicolo, resolve_practice_profile


def test_profilo_dell_esecuzione_con_norme_e_registro():
    profilo = get_profile(RITO_ESECUZIONE)
    assert profilo is not None and profilo.registry == "SIECIC" and profilo.channel == "PCT_CIVILE"
    assert "474" in profilo.source and "543" in profilo.source


def test_codice_oggetto_510002_fissa_l_esecuzione():
    fascicolo = SimpleNamespace(id="F1", tipo="CIVILE", tribunale="TRIBUNALE DI PALMI", oggetto="510002 - Espropriazione mobiliare presso terzi",
                                codice_oggetto_pst="510002", documenti=[])
    esito = resolve_practice_profile(fascicolo=fascicolo, payload={})
    assert esito.profile.code == RITO_ESECUZIONE and esito.automatic
    assert "510002" in esito.reason


def test_precetto_su_sentenza_amministrativa_senza_alternative_fuori_tema():
    fascicolo = SimpleNamespace(id="F2", tipo="AMMINISTRATIVO", tribunale="", oggetto="", titolo="Precetto Tar Roma",
                                documenti=[SimpleNamespace(nome="Atto di Precetto Spese legali Avv. Rossi", tipo="ALTRO")])
    esito = resolve_practice_profile(fascicolo=fascicolo, payload={})
    assert esito.profile.code == RITO_ESECUZIONE and esito.needs_manual_confirmation
    assert esito.alternatives == []
    assert "esecuzione forzata" in esito.reason and "art. 115 c.p.a." in esito.reason
    assert [riga["code"] for riga in alternative_del_fascicolo(fascicolo)] == [RITO_ESECUZIONE]


def test_senza_atti_esecutivi_restano_le_alternative_della_materia():
    fascicolo = SimpleNamespace(id="F3", tipo="AMMINISTRATIVO", tribunale="", oggetto="", documenti=[])
    nomi = [riga["name"] for riga in alternative_del_fascicolo(fascicolo)]
    assert nomi and "Esecuzione forzata (precetto e pignoramento)" not in nomi
