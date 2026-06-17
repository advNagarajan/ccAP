import logging
from sqlalchemy import text
from app.db.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("update_db_schema")

def run_migration():
    logger.info("Connecting to PostgreSQL database to apply schema migration...")
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE metadata.jobs 
                ADD COLUMN IF NOT EXISTS parent_job_id UUID 
                REFERENCES metadata.jobs(job_id) NULL;
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS metadata.notification_recipients (
                    recipient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now()
                );
            """))
            conn.commit()
            logger.info("Successfully added parent_job_id column and created metadata.notification_recipients table.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()
