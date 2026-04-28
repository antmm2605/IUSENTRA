from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from legal_deposit.busta.manifest import build_manifest
from legal_deposit.models import DepositDocument, PreflightResult
from legal_deposit.policies import ChannelProfile, channel_profile_for


@dataclass(slots=True)
class PackageBuildResult:
    channel: str
    package_kind: str
    output_dir: str
    manifest_path: str
    zip_path: str
    xml_path: str = ""
    requires_manual_final_upload: bool = False
    allows_direct_pec: bool = False


class ChannelPackageBuilder:
    """Build a safe local package using the selected channel profile."""

    def build(
        self,
        *,
        output_root: str | Path,
        job_id: str,
        tenant_id: str,
        fascicolo_id: str,
        channel: str | ChannelProfile,
        documents: list[DepositDocument],
        preflight: list[PreflightResult],
        metadata: dict[str, Any] | None = None,
    ) -> PackageBuildResult:
        profile = channel if isinstance(channel, ChannelProfile) else channel_profile_for(str(channel))
        safe_job_id = "".join(ch for ch in str(job_id) if ch.isalnum() or ch in {"-", "_"})[:80] or "deposito"
        output_dir = Path(output_root).resolve() / safe_job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = build_manifest(
            job_id=job_id,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            profile=profile,
            documents=documents,
            preflight=preflight,
            metadata=metadata,
        )
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        xml_path = ""
        if profile.requires_xml or profile.xml_filename:
            xml_name = profile.xml_filename or "metadati_deposito.xml"
            xml_file = output_dir / xml_name
            xml_file.write_text(_metadata_xml(profile, manifest), encoding="utf-8")
            xml_path = str(xml_file)

        zip_path = output_dir / f"{safe_job_id}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(manifest_path, "manifest.json")
            if xml_path:
                archive.write(xml_path, Path(xml_path).name)
            for index, doc in enumerate(documents, start=1):
                doc_path = Path(doc.path).resolve()
                if not doc_path.is_file():
                    continue
                archive_name = f"documenti/{index:02d}_{Path(doc.filename or doc_path.name).name}"
                archive.write(doc_path, archive_name)

        return PackageBuildResult(
            channel=profile.id,
            package_kind=profile.package_kind,
            output_dir=str(output_dir),
            manifest_path=str(manifest_path),
            xml_path=xml_path,
            zip_path=str(zip_path),
            requires_manual_final_upload=profile.requires_manual_final_upload,
            allows_direct_pec=profile.allows_direct_pec,
        )


def _metadata_xml(profile: ChannelProfile, manifest: dict[str, Any]) -> str:
    """Small neutral XML metadata file; channel-specific XSD validation stays separate."""

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<iusentra-deposito canale="{profile.id}" tipoPacchetto="{profile.package_kind}">\n'
        f"  <jobId>{_escape(str(manifest.get('job_id') or ''))}</jobId>\n"
        f"  <fascicoloId>{_escape(str(manifest.get('fascicolo_id') or ''))}</fascicoloId>\n"
        f"  <documenti>{len(manifest.get('documents') or [])}</documenti>\n"
        "</iusentra-deposito>\n"
    )


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

