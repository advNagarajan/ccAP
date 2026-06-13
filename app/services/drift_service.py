import logging
from app.services.validation_service import COMPATIBILITY_MATRIX

logger = logging.getLogger("schema_drift")


def normalize_type_token(t: str) -> str:
    if not t:
        return ""
    t = t.strip().lower()
    if t in ("string", "text", "varchar", "char", "str", "character varying"):
        return "str"
    if t in ("integer", "int", "bigint", "smallint"):
        return "int"
    if t in ("float", "double", "real", "numeric", "decimal"):
        return "float"
    if t in ("boolean", "bool"):
        return "bool"
    if t in ("datetime", "timestamp", "timestamp with time zone"):
        return "datetime"
    if t in ("date",):
        return "date"
    if t in ("json", "jsonb", "dict"):
        return "dict"
    return t


def compute_schema_drift(
    metadata_json: dict,
    schema_definition: dict,
    column_mapping: dict,
    warning_threshold: float = 20.0,
    critical_threshold: float = 50.0
) -> dict:
    """
    Computes rule-based schema drift between current source schema and target schema definition.
    Does not use previous validation runs as baseline (compares current source vs target).
    """
    source_cols = metadata_json.get("columns", [])
    source_col_names = {col["name"] for col in source_cols}
    source_col_types = {col["name"]: col.get("observed_types", []) for col in source_cols}

    target_fields = schema_definition.get("fields", [])
    target_field_names = {field["name"] for field in target_fields}
    target_field_types = {field["name"]: field.get("type", "VARCHAR") for field in target_fields}

    new_columns = []
    removed_columns = []
    datatype_changes = []
    renamed_columns = []

    # Map mapping: source -> target
    # Renamed: where src_col != tgt_col (in mapped columns)
    # New: source columns not in target
    # Removed: target columns not in source

    # Let's count renamed columns
    for src_col, tgt_col in column_mapping.items():
        if tgt_col:
            # Check renaming
            if src_col != tgt_col:
                renamed_columns.append({
                    "source_column": src_col,
                    "target_column": tgt_col
                })

            # Check datatype changes for mapped columns
            if src_col in source_col_names and tgt_col in target_field_names:
                src_types = source_col_types.get(src_col, [])
                tgt_type_raw = target_field_types.get(tgt_col, "VARCHAR")
                tgt_type = tgt_type_raw.upper().split("(")[0].strip()

                if tgt_type in COMPATIBILITY_MATRIX:
                    rules = COMPATIBILITY_MATRIX[tgt_type]
                    # Check if any observed type is incompatible
                    for src_type in src_types:
                        norm_src = normalize_type_token(src_type)
                        # If not in compatible list, it is a datatype change/warning
                        if norm_src not in rules["compatible"]:
                            datatype_changes.append({
                                "source_column": src_col,
                                "target_column": tgt_col,
                                "source_type": src_type,
                                "target_type": tgt_type_raw,
                                "reason": f"Type conversion warning/incompatibility: {src_type} vs {tgt_type_raw}"
                            })
                            break
                else:
                    # Target type unknown in compat matrix
                    datatype_changes.append({
                        "source_column": src_col,
                        "target_column": tgt_col,
                        "source_type": str(src_types),
                        "target_type": tgt_type_raw,
                        "reason": f"Unknown target datatype: {tgt_type_raw}"
                    })

    # Added columns: Columns in source that are not present in target catalog schema at all
    for src_col in source_col_names:
        # Check if mapped to anything in target, or if exists in target fields
        mapped_target = column_mapping.get(src_col)
        if mapped_target:
            if mapped_target not in target_field_names:
                new_columns.append(src_col)
        else:
            if src_col not in target_field_names:
                new_columns.append(src_col)

    # Removed columns: Columns in target that are not present in source at all
    mapped_targets = {t for s, t in column_mapping.items() if t}
    for tgt_col in target_field_names:
        if tgt_col not in source_col_names and tgt_col not in mapped_targets:
            removed_columns.append(tgt_col)

    # Drift Score formula:
    # drift_score = (new + removed + datatype_changes + renamed) / total_target_columns * 100
    total_target_columns = len(target_field_names)
    n_new = len(new_columns)
    n_removed = len(removed_columns)
    n_datatype = len(datatype_changes)
    n_renamed = len(renamed_columns)

    if total_target_columns > 0:
        drift_score = float(round(((n_new + n_removed + n_datatype + n_renamed) / total_target_columns) * 100.0, 2))
    else:
        # If target catalog is completely empty
        drift_score = 100.0 if n_new > 0 else 0.0

    # Classify status using new categories:
    # NO_DRIFT: score == 0
    # WARNING_DRIFT: 0 < score <= warning_threshold
    # DRIFTED: warning_threshold < score <= critical_threshold
    # CRITICAL_DRIFT: score > critical_threshold
    if drift_score == 0:
        drift_status = "NO_DRIFT"
    elif drift_score <= warning_threshold:
        drift_status = "WARNING_DRIFT"
    elif drift_score <= critical_threshold:
        drift_status = "DRIFTED"
    else:
        drift_status = "CRITICAL_DRIFT"

    return {
        "drift_status": drift_status,
        "drift_score": drift_score,
        "drift_summary": {
            "new_columns": new_columns,
            "removed_columns": removed_columns,
            "datatype_changes": datatype_changes,
            "renamed_columns": renamed_columns
        }
    }
