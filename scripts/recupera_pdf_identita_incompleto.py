"""Consolida una copia incompleta nell'originale già presente, con cestino e audit.

La modalità predefinita è soltanto diagnostica. Non modifica file fisici;
richiede stesso fascicolo, scansione JPEG concordante, dimensioni e data di
creazione identiche e nessun riferimento operativo alla copia incompleta.
"""
from __future__ import annotations
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("tenant", "fascicolo", "incompleto", "integrale", "report"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--applica", action="store_true")
    args = parser.parse_args()
    from web.app import create_app
    from pct.tenant import GestioneTenant
    from pct.document_crypto import decrypt_doc
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.registro_letture_runtime import documento_rimosso, aggiorna_inventario, registro_corrente, tenant_corrente
    from web.helpers import get_fascicoli
    import fitz
    app = create_app()
    manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
    with app.test_request_context("/__riparazione/pdf-identita"):
        _attach_tenant_context(manager, manager.get(args.tenant))
        gestore = get_fascicoli()
        fascicolo = gestore.get(args.fascicolo)
        docs = {d.id: d for d in fascicolo.documenti}
        rotto, sano = docs[args.incompleto], docs[args.integrale]
        if rotto.id == sano.id or any("identit" not in d.nome.casefold() for d in (rotto, sano)):
            raise ValueError("Occorrono due copie del documento d’identità dello stesso fascicolo.")
        if any(rotto.id in list(getattr(d, "documenti_ids", []) or []) for d in fascicolo.depositi_pct) or any(getattr(a, "id_documento", "") == rotto.id for a in fascicolo.attivita):
            raise ValueError("La copia incompleta ha riferimenti operativi: conservarla e riallinearli prima.")
        frammento = decrypt_doc(gestore.percorso_documento_lettura(fascicolo.id, rotto.id).read_bytes())
        completo = decrypt_doc(gestore.percorso_documento_lettura(fascicolo.id, sano.id).read_bytes())
        if b"%%EOF" in frammento[-2048:] or not completo.startswith(b"%PDF"):
            raise ValueError("Il file non è un PDF troncato oppure la copia integrale non è un PDF.")
        with fitz.open(stream=frammento, filetype="pdf") as doc:
            if doc.page_count:
                raise ValueError("Il file presenta pagine: non rientra in questa rettifica.")
        start = frammento.find(b"\xff\xd8\xff")
        if start < 0 or len(frammento) - start < 4096:
            raise ValueError("Frammento immagine insufficiente per il confronto.")
        attesa = re.search(rb"/Length\s+(\d+)", frammento[:start])
        creazione = re.search(rb"/CreationDate\(([^)]+)\)", frammento[:start])
        if not attesa or not creazione:
            raise ValueError("Dimensione e data originali della scansione non disponibili.")
        with fitz.open(stream=completo, filetype="pdf") as doc:
            if doc.page_count != 1 or doc.is_repaired or doc.metadata.get("creationDate", "").encode() != creazione[1]:
                raise ValueError("Struttura o data di creazione non concordanti.")
            immagini = [doc.extract_image(x[0])["image"] for x in doc[0].get_images()]
            if len(immagini) != 1 or len(immagini[0]) != int(attesa[1]) or not immagini[0].startswith(frammento[start:]):
                raise ValueError("La scansione completa non corrisponde al frammento.")
        registro, tenant = registro_corrente(), tenant_corrente()
        fatti = [f for f in registro.fatti(tenant, fascicolo.id, verifiche=("verificata", "corretta")) if f.oggetto_id == sano.id and f.campo == "natura_documentale" and f.valore == "documento_identita"]
        if not fatti:
            raise ValueError("La copia integrale non è ancora catalogata dall’archivio come documento d’identità.")
        report = {"source_of_truth": str(getattr(gestore._studio_db, "backend_kind", "sqlite")), "tenant": tenant, "fascicolo": fascicolo.id, "applicata": False, "copia_incompleta": rotto.to_dict(), "copia_integrale": sano.to_dict(), "sha256_incompleto": hashlib.sha256(frammento).hexdigest(), "sha256_integrale": hashlib.sha256(completo).hexdigest(), "byte_immagine_concordanti": len(frammento)-start, "byte_immagine_integrale": int(attesa[1]), "fatti_identita": [f.id for f in fatti]}
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.applica:
            nota = "Recupero della copia integrale verificato il " + datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M") + ": il frammento " + rotto.id + " è conservato nel cestino; scansione, dimensione originaria e data di creazione concordano con questo originale. Nessun file cancellato."
            gestore.aggiorna_documento_metadati(fascicolo.id, sano.id, note=(sano.note + "\n" + nota).strip())
            gestore.aggiorna_documento_metadati(fascicolo.id, rotto.id, note=(rotto.note + "\nCopia incompleta: originale integrale disponibile nel documento " + sano.id + ".").strip())
            gestore.rimuovi_documento(fascicolo.id, rotto.id, eliminato_da="IUSENTRA: recupero copia integrale verificata")
            documento_rimosso(fascicolo.id, rotto.id)
            aggiorna_inventario(gestore.get(fascicolo.id), registro=registro, con_pec=False)
            report["applicata"] = True
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if k not in {"copia_incompleta", "copia_integrale"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
