"""Resolver profilo pratica basato sulle fonti operative reali."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pct.legal_platform_catalog import infer_legal_operational_procedure
from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry, normalize_codice_oggetto_pst

from .dati_certi import DatiCerti, deduci_dati_certi, materia_del_profilo
from .models import PracticeProfile, ResolverResult
from .profiles import DEPOSITABLE_CHANNELS, get_profile, list_profiles
from .profili_rito import RITO_LAVORO


def _value(source: Any, *names: str) -> str:
    for name in names:
        if isinstance(source, dict):
            raw = source.get(name)
        else:
            raw = getattr(source, name, None)
        text = str(raw or "").strip()
        if text:
            return text
    return ""


def _alternative(profile: PracticeProfile, score: float, reason: str) -> dict[str, Any]:
    return {
        "code": profile.code,
        "name": profile.name,
        "channel": profile.channel,
        "registry": profile.registry,
        "confidence": round(score, 2),
        "reason": reason,
    }


def _first_codice_oggetto_pst(*sources: Any) -> tuple[str, dict[str, str] | None]:
    names = (
        "codice_oggetto_pst",
        "codiceOggettoPst",
        "oggetto",
        "title",
        "titolo",
        "tipo_procedimento",
    )
    for source in sources:
        for name in names:
            raw = _value(source, name)
            code = normalize_codice_oggetto_pst(raw)
            if code:
                return code, codice_oggetto_pst_entry(code)
    return "", None


def _codice_oggetto_dichiarato(code: str, *sources: Any) -> bool:
    """Il codice è il codice oggetto del fascicolo (campo dedicato o oggetto che inizia col codice), non un numero nel titolo."""
    for source in sources:
        if normalize_codice_oggetto_pst(_value(source, "codice_oggetto_pst", "codiceOggettoPst")) == code:
            return True
        if _value(source, "oggetto").upper().startswith(code):
            return True
    return False


def _source_type(*sources: Any) -> str:
    for source in sources:
        value = _value(source, "tipo", "type", "fascicolo_type", "tipo_fascicolo")
        if value:
            return value.upper()
    return ""


def _profile_from_codice_oggetto_pst(code: str, entry: dict[str, str] | None, *sources: Any) -> PracticeProfile | None:
    """Il profilo che il codice oggetto PST ufficiale fissa (catalogo XSD SICID versionato).

    Il codice dell'area «Lavoro e previdenza» iscrive la causa nel ruolo lavoro
    (artt. 409 e 413 c.p.c.): «retribuzione» e i licenziamenti individuali hanno
    il profilo specifico, gli altri il rito del lavoro. Il cautelare (art. 700
    c.p.c.) non ha un profilo nel catalogo: nessuna deduzione.
    """
    if not code or not entry:
        return None
    area = f"{entry.get('area_label', '')} {entry.get('area', '')}".lower()
    registri = str(entry.get("registri") or "").upper()
    descrizione = str(entry.get("descrizione") or "").lower()
    fascicolo_type = _source_type(*sources)

    if ("lavoro" in area or "previdenza" in area or fascicolo_type == "LAVORO") and "SICID" in registri:
        if "700" in descrizione:
            return None
        if "retribuz" in descrizione:
            return get_profile("PROC_LAV_RETRIB_001")
        if "licenziamento" in descrizione and "collettivo" not in descrizione:
            return get_profile("PROC_LIC_IMP_001")
        return get_profile(RITO_LAVORO)

    return None


def _pertinente(profile: PracticeProfile, dati: DatiCerti) -> bool:
    """Il profilo appartiene alla materia (e, se giudiziale, al canale telematico) del fascicolo."""
    materie = {dati.materia} if dati.materia else dati.materie_possibili
    if not materie:
        return False
    if materia_del_profilo(profile) not in materie:
        return False
    return not dati.giudiziale or profile.channel in DEPOSITABLE_CHANNELS


def _alternative_pertinenti(dati: DatiCerti, *, exclude: str = "", score: float = 0.3) -> list[dict[str, Any]]:
    rows = [profile for profile in list_profiles() if profile.code != exclude and _pertinente(profile, dati)]
    # Prima i profili di rito (validi per ogni oggetto della lite), poi le pratiche specifiche.
    rows.sort(key=lambda item: (0 if item.code.startswith("PROC_RITO_") else 1, item.name))
    etichetta = "stessa materia e stesso ufficio del fascicolo"
    return [_alternative(profile, score, etichetta) for profile in rows[:5]]


def _etichette(payload: dict[str, Any]) -> list[str]:
    return [str(item or "") for item in payload.get("etichette_documenti") or []]


@dataclass
class PracticeResolver:
    manual_threshold: float = 0.75

    def resolve(
        self,
        *,
        preventivo: Any | None = None,
        conferimento: Any | None = None,
        fascicolo: Any | None = None,
        template: Any | None = None,
        manual_code: str = "",
        payload: dict[str, Any] | None = None,
    ) -> ResolverResult:
        payload = payload or {}
        sources = [payload, preventivo, conferimento, fascicolo]

        # 1. codice procedura operativo esplicito
        for source in sources:
            code = _value(source, "procedura_operativa_codice", "procedure_code")
            profile = get_profile(code)
            if profile:
                return ResolverResult(profile, 0.98, "procedura_operativa_codice esplicito")

        # 2. id_pratica da preventivo/conferimento/fascicolo
        for source in sources:
            code = _value(source, "id_pratica", "practice_id")
            profile = get_profile(code)
            if profile:
                return ResolverResult(profile, 0.94, "id_pratica collegato al workflow commerciale")

        # 3. workflow operativo
        for source in sources:
            code = _value(source, "workflow_operativo_codice", "workflow_code")
            profile = get_profile(code)
            if profile:
                return ResolverResult(profile, 0.88, "workflow_operativo_codice")

        dati = deduci_dati_certi(fascicolo, _etichette(payload))

        # 6. codice oggetto PST ufficiale gia' acquisito in apertura fascicolo: dato certo del
        # catalogo ministeriale versionato; si imposta da solo se gli altri dati non lo contraddicono.
        pst_code, pst_entry = _first_codice_oggetto_pst(*sources)
        pst_profile = _profile_from_codice_oggetto_pst(pst_code, pst_entry, *sources)
        if pst_profile:
            dichiarato = _codice_oggetto_dichiarato(pst_code, *sources)
            concorde = not dati.discordanti and (
                not dati.materie_possibili or materia_del_profilo(pst_profile) in dati.materie_possibili
            )
            descrizione = str((pst_entry or {}).get("descrizione") or "").strip()
            fonte = f"codice oggetto PST ufficiale {pst_code}" + (f" «{descrizione}»" if descrizione else "")
            if dichiarato and concorde:
                return ResolverResult(
                    pst_profile, 0.91, f"Profilo impostato dal {fonte} (catalogo PST XSD SICID).",
                    [_alternative(pst_profile, 0.91, "codice oggetto PST")], False, automatic=True,
                )
            motivo = (
                f"Il {fonte} contrasta con gli altri dati del fascicolo ({'; '.join(dati.fonti)}): conferma il profilo."
                if dichiarato
                else f"Il {fonte} compare nel titolo ma non è il codice oggetto registrato nel fascicolo: conferma il profilo."
            )
            return ResolverResult(pst_profile, 0.6, motivo, _alternative_pertinenti(dati, exclude=pst_profile.code), True)

        # 6-bis. rito fissato dai dati certi concordi (tipo, ufficio, sezione, registro, atto introduttivo)
        rito_profile = get_profile(dati.rito) if dati.rito else None
        if rito_profile and dati.automatico:
            return ResolverResult(rito_profile, 0.9, dati.spiegazione(), [], False, automatic=True)

        # 4. canale + registro
        for source in sources:
            channel = _value(source, "canale_operativo", "channel")
            registry = _value(source, "registro_operativo", "registry")
            if channel and registry:
                matches = [
                    profile
                    for profile in list_profiles()
                    if profile.channel.upper() == channel.upper() and profile.registry.upper() == registry.upper()
                ]
                if dati.indizi:
                    matches = [item for item in matches if _pertinente(item, dati)]
                if matches:
                    profile = matches[0]
                    alternatives = [_alternative(item, 0.74, "canale_operativo + registro_operativo") for item in matches[:5]]
                    return ResolverResult(profile, 0.74, "canale_operativo + registro_operativo", alternatives, True)

        # 5. template atto principale selezionato
        template_label = _value(template, "link_compilatore_code", "id", "titolo", "title") or _value(payload, "template_atto")
        if template_label:
            matches = [
                profile
                for profile in list_profiles()
                if template_label.upper() in {label.upper() for label in profile.template_labels}
                or template_label.lower() in profile.name.lower()
            ]
            if matches:
                return ResolverResult(matches[0], 0.72, "template atto principale selezionato", [_alternative(m, 0.72, "template") for m in matches[:5]], True)

        # 7. tipo procedimento e oggetto tramite inferenza catalogo esistente
        tipo = ""
        oggetto = ""
        area = ""
        for source in sources:
            tipo = tipo or _value(source, "tipo_procedimento")
            oggetto = oggetto or _value(source, "oggetto", "title", "titolo")
            area = area or _value(source, "area_pratica", "area")
        inferred = infer_legal_operational_procedure(
            procedure_code="",
            practice_id="",
            area_pratica=area,
            tipo_procedimento=tipo,
            oggetto=oggetto,
        )
        if inferred:
            profile = get_profile(getattr(inferred, "code", "")) or get_profile(getattr(inferred, "practice_id", ""))
            # Una parola dell'oggetto non basta se il profilo è di un'altra materia o fuori dall'ufficio del fascicolo.
            if profile and (not dati.indizi or _pertinente(profile, dati)):
                confidence = 0.66 if oggetto else 0.62
                return ResolverResult(
                    profile,
                    confidence,
                    "tipo_procedimento/oggetto risolti dal catalogo operativo",
                    [_alternative(profile, confidence, "inferenza catalogo")],
                    True,
                )

        # 8. scelta manuale utente, esplicita e auditabile
        if manual_code:
            profile = get_profile(manual_code)
            if profile:
                return ResolverResult(profile, 0.81, "scelta manuale utente auditabile", [], False)

        # 9. proposta del rito della materia, se i dati lo indicano, con le sole alternative pertinenti
        if rito_profile and not dati.discordanti:
            return ResolverResult(
                rito_profile, 0.6, dati.spiegazione(), _alternative_pertinenti(dati, exclude=rito_profile.code), True,
            )
        return ResolverResult(None, 0.0, dati.spiegazione(), _alternative_pertinenti(dati), True)


def alternative_del_fascicolo(fascicolo: Any, etichette: list[str] | None = None, *, exclude: str = "") -> list[dict[str, Any]]:
    """I profili fra cui l'avvocato può cambiare quello applicato: solo materia e ufficio del fascicolo."""
    dati = deduci_dati_certi(fascicolo, list(etichette or []))
    righe = _alternative_pertinenti(dati, exclude=exclude)
    rito = get_profile(dati.rito) if dati.rito and not dati.discordanti else None
    if rito and rito.code != exclude and all(riga["code"] != rito.code for riga in righe):
        righe.insert(0, _alternative(rito, 0.6, "rito indicato dai dati del fascicolo"))
    return righe


def resolve_practice_profile(**kwargs: Any) -> ResolverResult:
    return PracticeResolver().resolve(**kwargs)
