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
            conn.commit()
            logger.info("Successfully added parent_job_id column to metadata.jobs table.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()
