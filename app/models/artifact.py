"""
A pure Python dataclass.
Used by connectors (like GCS/S3) to represent an external file before parsing.
"""
from dataclasses import dataclass


@dataclass
class Artifact:
    external_id: str
    artifact_name: str
    last_modified: str
    metadata: dict
    