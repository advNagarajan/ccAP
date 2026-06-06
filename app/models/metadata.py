from dataclasses import dataclass, field


@dataclass
class ColumnMetadata:
    name: str
    observed_types: list[str]
    null_count: int
    non_null_count: int
    distinct_count: int
    sample_values: list
    min_value: str | None = None
    max_value: str | None = None
    average_length: float | None = None


@dataclass
class DatasetStatistics:
    row_count: int
    column_count: int


@dataclass
class StructureMetadata:
    nested_fields: list[str] = field(default_factory=list)
    array_fields: list[str] = field(default_factory=list)
    max_depth: int = 0


@dataclass
class DatasetMetadata:
    statistics: DatasetStatistics
    columns: list[ColumnMetadata]
    structure: StructureMetadata
    connector_metadata: dict