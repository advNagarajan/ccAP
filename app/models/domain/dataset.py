"""
A pure Python dataclass.
Used by parsers (like CSV/JSON) to hold records in memory before metadata extraction.
"""
from dataclasses import dataclass


@dataclass
class Dataset:
    records: list[dict]
    source_type: str
    format_type: str