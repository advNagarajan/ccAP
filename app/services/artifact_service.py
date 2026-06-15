from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.domain.artifact import Artifact
from app.models.db.artifact_record import ArtifactRecord


def get_unprocessed_artifacts(
    source_id,
    artifacts: list[Artifact],
    db: Session
) -> list[Artifact]:

    unprocessed = []

    for artifact in artifacts:

        record = db.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.source_id == source_id,
                ArtifactRecord.external_artifact_id == artifact.external_id
            )
        ).scalar_one_or_none()

        if record is None:
            continue

        if record.status in ("DISCOVERED", "FAILED"):
            unprocessed.append(artifact)

    return unprocessed


def mark_discovered(
    source_id,
    artifact: Artifact,
    db: Session
):

    existing = db.execute(
        select(ArtifactRecord).where(
            ArtifactRecord.source_id == source_id,
            ArtifactRecord.external_artifact_id == artifact.external_id
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    record = ArtifactRecord(
        source_id=source_id,
        external_artifact_id=artifact.external_id,
        artifact_name=artifact.artifact_name,
        artifact_metadata=artifact.metadata,
        status="DISCOVERED"
    )

    db.add(record)

    db.commit()

    db.refresh(record)

    return record

def discover_new_artifacts(
    source_id,
    artifacts: list[Artifact],
    db: Session
) -> list[Artifact]:

    new_artifacts = []

    for artifact in artifacts:

        existing = db.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.source_id == source_id,
                ArtifactRecord.external_artifact_id == artifact.external_id
            )
        ).scalar_one_or_none()

        if existing is None:

            mark_discovered(source_id, artifact, db)

            new_artifacts.append(artifact)

    return new_artifacts


def mark_processed(
    source_id,
    artifact: Artifact,
    db: Session
):

    record = db.execute(
        select(ArtifactRecord).where(
            ArtifactRecord.source_id == source_id,
            ArtifactRecord.external_artifact_id == artifact.external_id
        )
    ).scalar_one_or_none()

    if record is None:
        return

    record.status = "PROCESSED"
    record.processed_at = datetime.now(UTC)

    db.commit()


def mark_failed(
    source_id,
    artifact: Artifact,
    reason,
    db: Session
):

    record = db.execute(
        select(ArtifactRecord).where(
            ArtifactRecord.source_id == source_id,
            ArtifactRecord.external_artifact_id == artifact.external_id
        )
    ).scalar_one_or_none()

    if record is None:
        return

    record.status = "FAILED"
    record.failure_reason = str(reason)

    db.commit()