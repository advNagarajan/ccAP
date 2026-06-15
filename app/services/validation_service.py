import logging

# Centralized Type Compatibility Matrix
COMPATIBILITY_MATRIX = {
    "INTEGER": {"compatible": ["int"], "warning": ["float", "bool", "str"]},
    "INT": {"compatible": ["int"], "warning": ["float", "bool", "str"]},
    "BIGINT": {"compatible": ["int"], "warning": ["float", "bool", "str"]},
    "SMALLINT": {"compatible": ["int"], "warning": ["float", "bool", "str"]},
    "NUMERIC": {"compatible": ["int", "float"], "warning": ["str"]},
    "DECIMAL": {"compatible": ["int", "float"], "warning": ["str"]},
    "FLOAT": {"compatible": ["int", "float"], "warning": ["str"]},
    "DOUBLE": {"compatible": ["int", "float"], "warning": ["str"]},
    "REAL": {"compatible": ["int", "float"], "warning": ["str"]},
    "BOOLEAN": {"compatible": ["bool"], "warning": ["int", "str"]},
    "BOOL": {"compatible": ["bool"], "warning": ["int", "str"]},
    "VARCHAR": {"compatible": ["str", "int", "float", "bool", "date", "datetime"], "warning": []},
    "STRING": {"compatible": ["str", "int", "float", "bool", "date", "datetime"], "warning": []},
    "TEXT": {"compatible": ["str", "int", "float", "bool", "date", "datetime"], "warning": []},
    "CHAR": {"compatible": ["str", "int", "float", "bool", "date", "datetime"], "warning": []},
    "CHARACTER VARYING": {"compatible": ["str", "int", "float", "bool", "date", "datetime"], "warning": []},
    "UUID": {"compatible": ["str"], "warning": []},
    "JSON": {"compatible": ["dict", "list", "str"], "warning": []},
    "JSONB": {"compatible": ["dict", "list", "str"], "warning": []},
    "DATE": {"compatible": ["date", "datetime"], "warning": ["str"]},
    "TIMESTAMP": {"compatible": ["datetime", "date"], "warning": ["str"]},
    "TIMESTAMP WITH TIME ZONE": {"compatible": ["datetime", "date"], "warning": ["str"]},
    "DATETIME": {"compatible": ["datetime", "date"], "warning": ["str"]}
}


def compute_schema_validation(
    metadata_json: dict,
    schema_definition: dict,
    column_mapping: dict,
    unmapped_source_columns: list,
    missing_target_columns: list,
    warning_threshold: float = 1.0
) -> dict:
    """
    Pure synchronous function that validates a source schema against a target schema definition.
    Returns calculated metrics, validation status, and a structured report.
    """
    # Extract source schema columns
    source_cols = metadata_json.get("columns", [])
    source_col_names = {col["name"] for col in source_cols}
    source_col_types = {col["name"]: col.get("observed_types", []) for col in source_cols}

    # Extract target schema fields
    target_fields = []
    if isinstance(schema_definition, dict):
        if "fields" in schema_definition and isinstance(schema_definition["fields"], list):
            target_fields = schema_definition["fields"]
        else:
            for col_name, col_type in schema_definition.items():
                if isinstance(col_type, str):
                    target_fields.append({"name": col_name, "type": col_type})
                elif isinstance(col_type, dict):
                    target_fields.append({
                        "name": col_name,
                        "type": col_type.get("type", "VARCHAR")
                    })
    elif isinstance(schema_definition, list):
        target_fields = schema_definition

    target_field_names = {field["name"] for field in target_fields}
    target_field_types = {field["name"]: field.get("type", "VARCHAR") for field in target_fields}

    invalid_mappings = []
    datatype_issues = []

    for src_col, tgt_col in column_mapping.items():
        if tgt_col is None:
            continue

        src_exists = src_col in source_col_names
        tgt_exists = tgt_col in target_field_names

        if not src_exists:
            invalid_mappings.append({
                "source_column": src_col,
                "target_column": tgt_col,
                "severity": "ERROR",
                "reason": "Mapping references a source column that does not exist in the source dataset schema."
            })
        if not tgt_exists:
            invalid_mappings.append({
                "source_column": src_col,
                "target_column": tgt_col,
                "severity": "ERROR",
                "reason": "Mapping references a target column that does not exist in the target table schema."
            })

        if src_exists and tgt_exists:
            # Type compatibility validation
            src_types = source_col_types.get(src_col, [])
            tgt_type_raw = target_field_types.get(tgt_col, "VARCHAR")
            tgt_type = tgt_type_raw.upper().split("(")[0].strip()

            for src_type in src_types:
                if tgt_type in COMPATIBILITY_MATRIX:
                    rules = COMPATIBILITY_MATRIX[tgt_type]
                    if src_type in rules["compatible"]:
                        continue
                    elif src_type in rules["warning"]:
                        datatype_issues.append({
                            "source_column": src_col,
                            "target_column": tgt_col,
                            "source_type": src_type,
                            "target_type": tgt_type_raw,
                            "severity": "WARNING",
                            "reason": f"Type conversion warning: observed source type '{src_type}' mapped to target type '{tgt_type_raw}'."
                        })
                    else:
                        datatype_issues.append({
                            "source_column": src_col,
                            "target_column": tgt_col,
                            "source_type": src_type,
                            "target_type": tgt_type_raw,
                            "severity": "WARNING",
                            "reason": f"Type incompatibility: observed source type '{src_type}' mapped to target type '{tgt_type_raw}'."
                        })
                else:
                    datatype_issues.append({
                        "source_column": src_col,
                        "target_column": tgt_col,
                        "source_type": src_type,
                        "target_type": tgt_type_raw,
                        "severity": "WARNING",
                        "reason": f"Unknown target datatype '{tgt_type_raw}'. Compatibility check deferred."
                    })

    # Metrics calculation
    source_column_count = len(source_col_names)
    target_column_count = len(target_field_names)

    mapped_source_columns = {s for s, t in column_mapping.items() if t is not None and s in source_col_names and t in target_field_names}
    mapped_target_columns = {t for s, t in column_mapping.items() if t is not None and s in source_col_names and t in target_field_names}
    mapped_column_count = len(mapped_source_columns)

    coverage_percentage = (mapped_column_count / source_column_count * 100.0) if source_column_count > 0 else 0.0
    target_match_percentage = (len(mapped_target_columns) / target_column_count * 100.0) if target_column_count > 0 else 0.0

    # Determine status
    if len(invalid_mappings) > 0:
        status = "FAILED"
    elif len(datatype_issues) > 0:
        status = "WARNING"
    elif (coverage_percentage / 100.0) < warning_threshold or (target_match_percentage / 100.0) < warning_threshold:
        status = "WARNING"
    else:
        status = "PASSED"

    report_json = {
        "report_version": "1.0",
        "invalid_mappings": invalid_mappings,
        "datatype_issues": datatype_issues,
        "missing_target_columns": missing_target_columns,
        "additional_source_columns": unmapped_source_columns,
        "coverage_percentage": float(round(coverage_percentage, 2)),
        "target_match_percentage": float(round(target_match_percentage, 2))
    }

    return {
        "validation_status": status,
        "coverage_percentage": float(round(coverage_percentage, 2)),
        "target_match_percentage": float(round(target_match_percentage, 2)),
        "mapped_column_count": mapped_column_count,
        "source_column_count": source_column_count,
        "target_column_count": target_column_count,
        "report_json": report_json
    }
