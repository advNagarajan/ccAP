from uuid import UUID

import yaml

from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException
)

from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.target_catalog import TargetCatalog

from app.schemas.configuration import (
    ConfigurationCreateResponse,
    ConfigurationResponse,
    ConfigurationUpdate
)

router = APIRouter(
    tags=["Configurations"]
)

VALID_CONFIG_TYPES = {
    "SOURCE",
    "TARGET"
}

VALID_CONFIG_SUBTYPES = {
    "CSV",
    "JSON",
    "PARQUET",
    "BIGQUERY",
    "FIRESTORE",
    "GCS"
}

VALID_STATUSES = {
    "ACTIVE",
    "INACTIVE",
    "DELETED"
}


def validate_predefined_targets(config_content: dict, db: Session):
    predefined_target_ids = config_content.get("predefined_target_ids")
    if predefined_target_ids is not None:
        if not isinstance(predefined_target_ids, list):
            raise HTTPException(
                status_code=400,
                detail="predefined_target_ids must be a list"
            )
        missing_ids = []
        for tid in predefined_target_ids:
            try:
                target_uuid = UUID(str(tid))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid UUID format: {tid}"
                )
            target_exists = db.get(TargetCatalog, target_uuid)
            if not target_exists:
                missing_ids.append(str(tid))
        if missing_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Predefined target ID(s) {', '.join(missing_ids)} do not exist in Target Catalog."
            )


@router.post("/configurations", response_model=ConfigurationCreateResponse, status_code=201)
async def create_configuration(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not (
        file.filename.endswith(".yaml")
        or file.filename.endswith(".yml")
    ):
        raise HTTPException(
            status_code=400,
            detail="Only YAML files are supported"
        )

    content = await file.read()

    yaml_text = content.decode("utf-8")

    try:
        config = yaml.safe_load(yaml_text)

    except yaml.YAMLError:
        raise HTTPException(
            status_code=400,
            detail="Invalid YAML syntax"
        )

    if not isinstance(config, dict):
        raise HTTPException(
            status_code=400,
            detail="YAML must contain a valid object"
        )

    config_type = config.get("config_type")

    config_subtype = config.get("config_subtype")

    if config_type not in VALID_CONFIG_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid config_type"
        )

    if config_subtype not in VALID_CONFIG_SUBTYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid config_subtype"
        )

    config_content = dict(config)
    config_name = config_content.get("name", file.filename)

    existing = db.execute(
        select(ProcessingConfiguration).where(
            ProcessingConfiguration.name
            == config_name
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Configuration with name '{config_name}' already exists"
        )

    config_content.pop("config_type", None)
    config_content.pop("config_subtype", None)
    config_content.pop("name", None)
    config_description = config_content.pop("description", None)

    validate_predefined_targets(config_content, db)

    configuration = ProcessingConfiguration(
        name=config_name,
        description=config_description,
        config_type=config_type,
        config_subtype=config_subtype,
        config_content=config_content,
        status="ACTIVE",
        version=1
    )

    db.add(configuration)

    db.commit()

    db.refresh(configuration)

    return {
        "config_id":
            configuration.config_id,

        "filename":
            configuration.name,

        "status":
            configuration.status,

        "created_at":
            configuration.created_at
    }


@router.get("/configurations", response_model=list[ConfigurationResponse])
def get_configurations(db: Session = Depends(get_db)):
    configurations = db.execute(
        select(ProcessingConfiguration).where(
            ProcessingConfiguration.status
            != "DELETED"
        )
    ).scalars().all()

    return configurations


@router.get("/configurations/{config_id}",response_model=ConfigurationResponse)
def get_configuration(config_id: UUID, db: Session = Depends(get_db)):
    configuration = db.get(
        ProcessingConfiguration,
        config_id
    )

    if not configuration:
        raise HTTPException(
            status_code=404,
            detail="Configuration not found"
        )

    return configuration

@router.patch("/configurations/{config_id}", response_model=ConfigurationResponse)
def update_configuration(config_id: UUID, payload: ConfigurationUpdate, db: Session = Depends(get_db)):
    configuration = db.get(
        ProcessingConfiguration,
        config_id
    )

    if not configuration:
        raise HTTPException(
            status_code=404,
            detail="Configuration not found"
        )

    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates and updates["name"] is not None:
        new_name = updates["name"]
        existing_with_name = db.execute(
            select(ProcessingConfiguration)
            .where(ProcessingConfiguration.name == new_name)
            .where(ProcessingConfiguration.config_id != config_id)
        ).scalar_one_or_none()
        if existing_with_name:
            raise HTTPException(
                status_code=409,
                detail=f"Configuration with name '{new_name}' already exists"
            )

    if "config_content" in updates and updates["config_content"] is not None:
        validate_predefined_targets(updates["config_content"], db)

    if (
        "status" in updates
        and updates["status"]
        not in VALID_STATUSES
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid status"
        )

    for field, value in updates.items():
        setattr(
            configuration,
            field,
            value
        )

    configuration.version += 1

    configuration.updated_at = datetime.now(UTC).replace(tzinfo=None)

    db.commit()

    db.refresh(configuration)

    return configuration

@router.delete("/configurations/{config_id}", response_model=ConfigurationResponse)
def delete_configuration(config_id: UUID, db: Session = Depends(get_db)):
    configuration = db.get(
        ProcessingConfiguration,
        config_id
    )

    if not configuration:
        raise HTTPException(
            status_code=404,
            detail="Configuration not found"
        )

    configuration.status = "DELETED"

    configuration.version += 1

    configuration.updated_at = datetime.now(UTC).replace(tzinfo=None)

    db.commit()

    db.refresh(configuration)

    return configuration