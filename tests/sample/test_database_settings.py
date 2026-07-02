from app.core.settings import Settings

def test_database_url_without_cloud_sql():
    test_settings = Settings(
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_NAME="testdb",
        DB_USER="postgres",
        DB_PASSWORD="password",
        CLOUD_SQL_CONNECTION_NAME=None,
        GCP_PROJECT_ID="test-project"
    )
    
    expected_url = "postgresql://postgres:password@localhost:5432/testdb"
    assert test_settings.database_url == expected_url
    assert "localhost" in test_settings.database_url
    assert "5432" in test_settings.database_url

def test_database_url_with_cloud_sql():
    test_settings = Settings(
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_NAME="testdb",
        DB_USER="postgres",
        DB_PASSWORD="password",
        CLOUD_SQL_CONNECTION_NAME="my-project:us-central1:my-db",
        GCP_PROJECT_ID="test-project"
    )
    
    expected_url = "postgresql://postgres:password@/testdb?host=/cloudsql/my-project:us-central1:my-db"
    assert test_settings.database_url == expected_url
    assert "localhost" not in test_settings.database_url
    assert "5432" not in test_settings.database_url
    assert "/cloudsql/my-project:us-central1:my-db" in test_settings.database_url
