from dataclasses import dataclass


@dataclass
class Dataset:
    records: list[dict]
    source_type: str
    format_type: str