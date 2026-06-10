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


def generate_embedding_optimized_text(
    raw_metadata: dict
) -> str:
    """
    Compiles a deterministic, embedding-optimized natural language description
    (passport) for a metadata profile to match target passports for cosine similarity.
    """
    passport_parts = []

    # 1. Identity Context
    object_name = raw_metadata.get("connector_metadata", {}).get("object_name", "Unknown Dataset")
    if "/" in object_name:
        object_name = object_name.split("/")[-1]
    if "." in object_name:
        object_name = object_name.split(".")[0]
    asset_name = object_name.replace("_", " ").replace("-", " ").title()
    passport_parts.append(f"Source Dataset Asset: {asset_name}")

    # 2. Schema Structure
    columns = raw_metadata.get("columns", [])
    if columns:
        passport_parts.append("Structure Schema Fields:")
        
        # Grouping columns: check if they have "parent", otherwise default to "General Schema Columns"
        grouped_fields = {}
        for col in columns:
            parent = col.get("parent") or "General Schema Columns"
            parent_title = parent.replace("_", " ").title()
            grouped_fields.setdefault(parent_title, []).append(col)
            
        for parent_title, col_list in sorted(grouped_fields.items()):
            passport_parts.append(f"  Under {parent_title}:")
            for col in col_list:
                col_name = col.get("name", "").replace("_", " ").title()
                observed_types = col.get("observed_types", [])
                col_type = "/".join(observed_types).upper() if observed_types else "UNKNOWN"
                
                tags = []
                if col.get("is_unique"):
                    tags.append("(unique identifier)")
                if col.get("presence_percentage") == 100.0:
                    tags.append("(present in 100% of records)")
                    
                tag_suffix = " " + " ".join(tags) if tags else ""
                passport_parts.append(f"    - Column Name: {col_name}, Data Type: {col_type}{tag_suffix}")

    return "\n".join(passport_parts)


def generate_llm_optimized_json(
    raw_metadata: dict
) -> dict:
    """
    Generates a simplified, token-efficient representation of metadata
    for LLM prompt usage, stripping operational noise.
    """
    stats = raw_metadata.get("statistics", {})
    optimized_stats = {
        "row_count": stats.get("row_count"),
        "column_count": stats.get("column_count")
    }
    
    optimized_columns = []
    for col in raw_metadata.get("columns", []):
        opt_col = {
            "name": col.get("name"),
            "observed_types": col.get("observed_types"),
            "is_unique": col.get("is_unique"),
            "presence_percentage": col.get("presence_percentage"),
            "sample_values": col.get("sample_values", [])
        }
        for key in ["min_value", "max_value", "average_length", "numeric_statistics"]:
            if col.get(key) is not None:
                opt_col[key] = col.get(key)
        optimized_columns.append(opt_col)
        
    struct = raw_metadata.get("structure", {})
    optimized_struct = {
        "nested_fields": struct.get("nested_fields", []),
        "array_fields": struct.get("array_fields", []),
        "flattened_paths": struct.get("flattened_paths", []),
        "max_depth": struct.get("max_depth", 0)
    }
    
    return {
        "statistics": optimized_stats,
        "columns": optimized_columns,
        "structure": optimized_struct
    }


def save_metadata(
    job_id,
    artifact_id,
    metadata,
    db: Session
):

    embedding_text = generate_embedding_optimized_text(metadata)

    profile = MetadataProfile(
        job_id=job_id,
        artifact_id=artifact_id,
        metadata_json=metadata,
        embedding_optimized_text=embedding_text
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