"""
Database Initialization & Seeding Script for Smart Data Landing Platform.

This script:
1. Connects to PostgreSQL (AWS RDS).
2. Enables the `pgvector` extension.
3. Creates the required PostgreSQL schemas: `metadata` and `control_plane`.
4. Creates all 18 SQLAlchemy database tables.
5. Seeds the initial platform `OWNER` user so you can log in to the web portal.
6. Seeds baseline Target Catalogs and Processing Configurations.
"""
import os
import sys
import uuid
from sqlalchemy import text, select

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine, SessionLocal
from app.db.base import Base
from app.services.security import hash_password

# Import all models to register with Base.metadata
from app.models.db.user import User
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.job import Job
from app.models.db.job_stage_history import JobStageHistory
from app.models.db.artifact_record import ArtifactRecord
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_recommendation import SchemaRecommendation
from app.models.db.data_quality_job import DataQualityJob
from app.models.db.data_quality_report import DataQualityReport
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.models.db.schema_fallback_request import SchemaFallbackRequest
from app.models.db.notification_recipient import NotificationRecipient
from app.models.db.audit_log import AuditLog


def init_database():
    print("=" * 65)
    print("🚀 Initializing AWS RDS PostgreSQL Database")
    print("=" * 65)

    # 1. Enable pgvector and create schemas
    print("\n[1/5] Creating database schemas & vector extension...")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS metadata;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS control_plane;"))
    print("  ✓ Extension 'vector' verified.")
    print("  ✓ Schema 'metadata' created.")
    print("  ✓ Schema 'control_plane' created.")

    # 2. Create tables
    print("\n[2/5] Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("  ✓ All 18 database tables created successfully.")

    session = SessionLocal()
    try:
        # 3. Seed Default OWNER User
        print("\n[3/5] Checking Admin / Owner User...")
        admin_email = "admin@platform.com"
        admin_password = "AdminPassword123!"

        stmt = select(User).where(User.email == admin_email)
        existing_admin = session.execute(stmt).scalar_one_or_none()

        if not existing_admin:
            owner_user = User(
                user_id=uuid.uuid4(),
                email=admin_email,
                hashed_password=hash_password(admin_password),
                role="OWNER"
            )
            session.add(owner_user)
            session.commit()
            print(f"  ✓ Created OWNER user: {admin_email}")
        else:
            print(f"  ✓ OWNER user already exists: {admin_email}")

        # 4. Seed Baseline Target Catalogs
        print("\n[4/5] Checking Baseline Target Catalogs...")
        target_stmt = select(TargetCatalog).where(TargetCatalog.target_name == "customers_master")
        existing_target = session.execute(target_stmt).scalar_one_or_none()

        if not existing_target:
            sample_target = TargetCatalog(
                target_id=uuid.uuid4(),
                target_name="customers_master",
                target_type="S3",
                business_domain="Customers",
                description="Master customer profiles table containing identifiers, contact details, and account status.",
                connection_details={
                    "bucket": os.getenv("AWS_S3_LANDING_BUCKET", "dataset-platform-landing"),
                    "prefix": "targets/customers/"
                },
                schema_definition={
                    "columns": [
                        {"name": "id", "type": "int", "nullable": False, "primary_key": True},
                        {"name": "first_name", "type": "string", "nullable": False},
                        {"name": "last_name", "type": "string", "nullable": False},
                        {"name": "email", "type": "string", "nullable": False},
                        {"name": "age", "type": "int", "nullable": True},
                        {"name": "created_at", "type": "datetime", "nullable": False}
                    ]
                },
                target_status="ACTIVE",
                is_system_generated=False,
                target_passport_text="Customer profile table with id, first_name, last_name, email, age, created_at."
            )
            session.add(sample_target)
            session.commit()
            print("  ✓ Seeded baseline target: customers_master")
        else:
            print("  ✓ Baseline target catalog already exists.")

        # 5. Seed Baseline Processing Configuration
        print("\n[5/5] Checking Baseline Processing Configuration...")
        config_stmt = select(ProcessingConfiguration).where(ProcessingConfiguration.name == "Standard S3 Ingestion Profile")
        existing_config = session.execute(config_stmt).scalar_one_or_none()

        if not existing_config:
            sample_config = ProcessingConfiguration(
                config_id=uuid.uuid4(),
                name="Standard S3 Ingestion Profile",
                config_type="SOURCE",
                config_subtype="S3",
                description="Default configuration with data quality rules and profiling enabled.",
                status="ACTIVE",
                version=1,
                config_content={
                    "data_quality_enabled": True,
                    "data_quality_sampling": {
                        "sample_ratio": 1.0,
                        "random_sample": False
                    },
                    "data_quality_rules": [
                        {
                            "type": "null_check",
                            "columns": ["email", "first_name"],
                            "allowed_null_ratio": 0.05,
                            "severity": "FAILED"
                        },
                        {
                            "type": "uniqueness_check",
                            "columns": ["id"],
                            "severity": "FAILED"
                        },
                        {
                            "type": "boundary_range_check",
                            "columns": {"age": {"min": 0, "max": 120}},
                            "severity": "WARNING"
                        }
                    ]
                }
            )
            session.add(sample_config)
            session.commit()
            print("  ✓ Seeded baseline configuration: Standard S3 Ingestion Profile")
        else:
            print("  ✓ Baseline configuration already exists.")

        print("\n" + "=" * 65)
        print("🎉 Database Initialization Complete!")
        print("=" * 65)
        print("\n🔑 Web Portal Login Credentials:")
        print(f"   Email:    {admin_email}")
        print(f"   Password: {admin_password}")
        print("   Role:     OWNER")
        print("=" * 65)

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error initializing database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    init_database()
