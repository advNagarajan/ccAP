from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File,
    HTTPException
)

from sqlalchemy import select
from sqlalchemy.orm import Session

import yaml

from app.db.session import get_db

from app.models.processing_configuration import (
    ProcessingConfiguration
)

from app.schemas.configuration import (
    ConfigurationCreateResponse
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


@router.post(
    "/configurations",
    response_model=ConfigurationCreateResponse,
    status_code=201
)
async def create_configuration(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

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

    config_type = config.get(
        "config_type"
    )

    config_subtype = config.get(
        "config_subtype"
    )

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

    existing = db.execute(
        select(
            ProcessingConfiguration
        ).where(
            ProcessingConfiguration.name
            == file.filename
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Configuration already exists"
        )

    config_content = dict(config)

    config_content.pop(
        "config_type",
        None
    )

    config_content.pop(
        "config_subtype",
        None
    )

    configuration = (
        ProcessingConfiguration(
            name=file.filename,
            description=None,
            config_type=config_type,
            config_subtype=config_subtype,
            config_content=config_content,
            status="ACTIVE",
            version=1
        )
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