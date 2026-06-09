from dataclasses import asdict
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset

from app.models.metadata import (
    ColumnMetadata,
    DatasetMetadata,
    DatasetStatistics,
    StructureMetadata,
    NumericStatistics
)

from app.models.metadata_profile import MetadataProfile


def _walk_structure(
    value,
    path,
    nested_fields,
    array_fields,
    flattened_paths,
    depth
):

    max_depth = depth

    if isinstance(value, dict):

        if path:
            nested_fields.add(path)

        for key, child in value.items():

            child_path = f"{path}.{key}" if path else key

            flattened_paths.add(child_path)

            child_depth = _walk_structure(
                child,
                child_path,
                nested_fields,
                array_fields,
                flattened_paths,
                depth + 1
            )

            max_depth = max(
                max_depth,
                child_depth
            )

    elif isinstance(value, list):

        if path:
            array_fields.add(path)

        for item in value:

            child_depth = _walk_structure(
                item,
                path,
                nested_fields,
                array_fields,
                flattened_paths,
                depth + 1
            )

            max_depth = max(
                max_depth,
                child_depth
            )

    return max_depth


def extract_structure_metadata(
    records
) -> StructureMetadata:

    nested_fields = set()
    array_fields = set()
    flattened_paths = set()

    max_depth = 0

    for record in records:

        record_depth = _walk_structure(
            record,
            "",
            nested_fields,
            array_fields,
            flattened_paths,
            0
        )

        max_depth = max(
            max_depth,
            record_depth
        )

    return StructureMetadata(
        nested_fields=sorted(nested_fields),
        array_fields=sorted(array_fields),
        flattened_paths=sorted(flattened_paths),
        max_depth=max_depth
    )


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
            connector_metadata=connector_metadata,
            sample_records=[]
        )

    columns = []

    column_names = set()

    for record in records:
        column_names.update(record.keys())

    for column_name in sorted(column_names):

        values = [record.get(column_name) for record in records]

        non_null_values = [
            value
            for value in values
            if value is not None
        ]

        null_count = len(values) - len(non_null_values)

        observed_types = sorted({
            type(value).__name__
            for value in non_null_values
        })

        distinct_count = len({
            str(value)
            for value in non_null_values
        })

        sample_values = list({
            str(value)
            for value in non_null_values
        })[:10]

        min_value = None
        max_value = None

        try:

            if non_null_values:

                min_value = str(min(non_null_values))
                max_value = str(max(non_null_values))

        except Exception:
            pass

        average_length = None

        if non_null_values:

            lengths = [
                len(str(value))
                for value in non_null_values
            ]

            average_length = (
                sum(lengths)
                / len(lengths)
            )

        numeric_values = [
            value
            for value in non_null_values
            if isinstance(value, (int, float))
        ]

        numeric_statistics = None

        if numeric_values:

            numeric_statistics = NumericStatistics(
                mean=float(mean(numeric_values)),
                median=float(median(numeric_values))
            )

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
                sample_values=sample_values,
                min_value=min_value,
                max_value=max_value,
                average_length=average_length,
                numeric_statistics=numeric_statistics
            )
        )

    structure = extract_structure_metadata(
        records
    )

    return DatasetMetadata(
        statistics=DatasetStatistics(
            row_count=row_count,
            column_count=len(column_names)
        ),
        columns=columns,
        structure=structure,
        connector_metadata=connector_metadata,
        sample_records=records[:10]
    )


def metadata_to_dict(
    metadata: DatasetMetadata
) -> dict:

    return asdict(metadata)


def save_metadata(
    job_id,
    artifact_id,
    metadata,
    db: Session
):

    profile = MetadataProfile(
        job_id=job_id,
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
            MetadataProfile.metadata_profile_id == metadata_profile_id
        )
    ).scalar_one_or_none()


def get_metadata_by_artifact(
    artifact_id,
    db: Session
):

    return db.execute(
        select(MetadataProfile).where(
            MetadataProfile.artifact_id == artifact_id
        )
    ).scalar_one_or_none()