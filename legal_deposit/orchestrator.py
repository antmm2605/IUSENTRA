from __future__ import annotations

import uuid
from typing import Any

from .busta.manifest import build_manifest
from .busta.package_builder import ChannelPackageBuilder
from .models import DepositDocument, DepositPreparation, DepositState, DepositTransition, PreflightStatus
from .policies import channel_profile_for
from .validators import DocumentPreflightValidator


class DepositOrchestrator:
    """Vertical slice: prepara deposito, controlla documenti e produce riepilogo."""

    def __init__(
        self,
        *,
        validator: DocumentPreflightValidator | None = None,
        package_builder: ChannelPackageBuilder | None = None,
    ) -> None:
        self.validator = validator or DocumentPreflightValidator()
        self.package_builder = package_builder or ChannelPackageBuilder()

    def prepare(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        channel: str,
        documents: list[DepositDocument],
        office_name: str = "",
        user_id: str = "",
        metadata: dict[str, Any] | None = None,
        output_root: str | None = None,
    ) -> DepositPreparation:
        profile = channel_profile_for(channel)
        job_id = f"DEP-{uuid.uuid4().hex[:12].upper()}"
        transitions = [
            DepositTransition(
                status_before=DepositState.DRAFT.value,
                status_after=DepositState.DOCUMENTS_LOADED.value,
                user_id=user_id,
                reason="Documenti selezionati per la preparazione deposito.",
            ),
            DepositTransition(
                status_before=DepositState.DOCUMENTS_LOADED.value,
                status_after=DepositState.PRECHECK_RUNNING.value,
                user_id=user_id,
                reason="Avvio controlli preventivi.",
            ),
        ]
        preflight = self.validator.validate(documents=documents, profile=profile, office_name=office_name)
        has_errors = any(item.status == PreflightStatus.ERROR for item in preflight)
        state = DepositState.PRECHECK_FAILED if has_errors else DepositState.PACKAGE_READY
        transitions.append(
            DepositTransition(
                status_before=DepositState.PRECHECK_RUNNING.value,
                status_after=state.value,
                user_id=user_id,
                reason="Controlli preventivi completati.",
                errors=[item.code for item in preflight if item.status == PreflightStatus.ERROR],
            )
        )
        if not has_errors:
            transitions.append(
                DepositTransition(
                    status_before=DepositState.PACKAGE_READY.value,
                    status_after=DepositState.AWAITING_USER_CONFIRMATION.value,
                    user_id=user_id,
                    reason="Riepilogo pronto per validazione consapevole dell'avvocato.",
                )
            )
            state = DepositState.AWAITING_USER_CONFIRMATION
        manifest = build_manifest(
            job_id=job_id,
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            profile=profile,
            documents=documents,
            preflight=preflight,
            metadata=metadata,
        )
        summary = {
            "job_id": job_id,
            "channel": profile.name,
            "package_kind": profile.package_kind,
            "office_name": office_name,
            "documents_count": len(documents),
            "warnings_count": len([item for item in preflight if item.status == PreflightStatus.WARNING]),
            "errors_count": len([item for item in preflight if item.status == PreflightStatus.ERROR]),
            "requires_human_confirmation": True,
            "can_sign_and_send": not has_errors,
        }
        if output_root and not has_errors:
            package_result = self.package_builder.build(
                output_root=output_root,
                job_id=job_id,
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                channel=profile,
                documents=documents,
                preflight=preflight,
                metadata=metadata,
            )
            summary["package"] = {
                "output_dir": package_result.output_dir,
                "manifest_path": package_result.manifest_path,
                "xml_path": package_result.xml_path,
                "zip_path": package_result.zip_path,
                "requires_manual_final_upload": package_result.requires_manual_final_upload,
                "allows_direct_pec": package_result.allows_direct_pec,
            }
        return DepositPreparation(
            job_id=job_id,
            status=state,
            channel=profile.id,
            documents=documents,
            preflight=preflight,
            manifest=manifest,
            summary=summary,
            transitions=transitions,
        )
