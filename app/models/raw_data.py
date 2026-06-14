"""
A pure Python dataclass.
Used to pass raw byte strings from Connectors to Parsers.
"""
from dataclasses import dataclass


@dataclass
class RawData:
    content: str
    format_type: str
    source_type: str
    source_name: str
    connector_metadata: dict