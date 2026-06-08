from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset

from app.models.metadata import (
    ColumnMetadata,
    DatasetMetadata,
    DatasetStatistics,
    StructureMetadata
)

from app.models.metadata_profile import MetadataProfile


def extract_metadata(
    dataset: Dataset,
    connector_metadata: dict[str, object]
) -> DatasetMetadata:

    records = dataset.records

    row_count = len(records)

    if not records:

        return DatasetMetadata(
            statistics=DatasetStatistics(
                row_count=0,
                column_count=0
            ),
            columns=[],
            structure=StructureMetadata(),
            connector_metadata=connector_metadata
        )

    columns = []

    column_names = set()

    for record in records:
        column_names.update(record.keys())

    for column_name in sorted(column_names):

        values = [
            record.get(column_name)
            for record in records
        ]

        non_null_values = [
            value
            for value in values
            if value is not None
        ]

        null_count = (
            len(values)
            - len(non_null_values)
        )

        observed_types = sorted(
            {
                type(value).__name__
                for value in non_null_values
            }
        )

        distinct_count = len(
            {
                str(value)
                for value in non_null_values
            }
        )

        sample_values = list(
            {
                str(value)
                for value in non_null_values
            }
        )[:10]

        columns.append(
            ColumnMetadata(
                name=column_name,
                observed_types=observed_types,
                null_count=null_count,
                non_null_count=len(non_null_values),
                distinct_count=distinct_count,
                is_unique=(
                    distinct_count ==
                    len(non_null_values)
                ),
                presence_percentage=(
                    len(non_null_values)
                    / row_count
                ) * 100,
                sample_values=sample_values
            )
        )

    return DatasetMetadata(
        statistics=DatasetStatistics(
            row_count=row_count,
            column_count=len(column_names)
        ),
        columns=columns,
        structure=StructureMetadata(),
        connector_metadata=connector_metadata
    )


def metadata_to_dict(
    metadata: DatasetMetadata
) -> dict:

    return asdict(metadata)


def save_metadata(
    artifact_id,
    metadata,
    db: Session
):

    profile = MetadataProfile(
        artifact_id=artifact_id,
        metadata_json=metadata
    )

    db.add(profile)

    db.commit()

    db.refresh(profile)

    return profile


def get_metadata(
    metadata_profile_id,
    db: Session
):

    return db.execute(
        select(MetadataProfile).where(
            MetadataProfile.metadata_profile_id ==
            metadata_profile_id
        )
    ).scalar_one_or_none()


def get_metadata_by_artifact(
    artifact_id,
    db: Session
):

    return db.execute(
        select(MetadataProfile).where(
            MetadataProfile.artifact_id ==
            artifact_id
        )
    ).scalar_one_or_none()