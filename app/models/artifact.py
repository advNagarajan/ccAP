from dataclasses import dataclass


@dataclass
class Artifact:
    external_id: str
    artifact_name: str
    last_modified: str
    metadata: dict
    