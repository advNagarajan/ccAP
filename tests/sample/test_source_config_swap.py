import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from datetime import datetime
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration

# Setup mock database
mock_db = MagicMock()

mock_sources = {}
mock_configs = {}

def mock_get(model_class, ident):
    if isinstance(ident, str):
        ident = uuid.UUID(ident)
    if model_class == Source:
        return mock_sources.get(ident)
    if model_class == ProcessingConfiguration:
        return mock_configs.get(ident)
    return None

mock_db.get = mock_get

# Override dependencies
def override_get_db():
    try:
        yield mock_db
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_source_swap_config_success():
    # Arrange
    source_id = uuid.uuid4()
    old_config_id = uuid.uuid4()
    new_config_id = uuid.uuid4()
    
    source = Source(
        source_id=source_id,
        config_id=old_config_id,
        name="test_source",
        source_type="GCS",
        connection_details={"bucket": "my-bucket"},
        status="ACTIVE",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    new_config = ProcessingConfiguration(
        config_id=new_config_id,
        name="new_config",
        config_type="SOURCE",
        config_subtype="GCS",
        status="ACTIVE"
    )
    
    mock_sources[source_id] = source
    mock_configs[new_config_id] = new_config
    
    # Act
    response = client.patch(
        f"/sources/{source_id}",
        json={"config_id": str(new_config_id)}
    )
    
    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["config_id"] == str(new_config_id)
    assert source.config_id == new_config_id

def test_source_swap_config_not_found():
    # Arrange
    source_id = uuid.uuid4()
    old_config_id = uuid.uuid4()
    invalid_config_id = uuid.uuid4()
    
    source = Source(
        source_id=source_id,
        config_id=old_config_id,
        name="test_source",
        source_type="GCS",
        connection_details={"bucket": "my-bucket"},
        status="ACTIVE",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    mock_sources[source_id] = source
    if invalid_config_id in mock_configs:
        del mock_configs[invalid_config_id]
        
    # Act
    response = client.patch(
        f"/sources/{source_id}",
        json={"config_id": str(invalid_config_id)}
    )
    
    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Configuration not found"
