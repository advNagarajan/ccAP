import logging
from sqlalchemy import text
from app.db.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_schema")

def run_migrations():
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            logger.info("Starting schema migrations...")
            
            # 1. Create control_plane schema
            logger.info("Ensuring control_plane schema exists...")
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS control_plane;"))
            
            # 2. Check if control_plane.users exists
            check_cp_users = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'control_plane' AND table_name = 'users')"
            )).scalar()
            
            if not check_cp_users:
                # Check if metadata.users exists
                check_meta_users = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'metadata' AND table_name = 'users')"
                )).scalar()
                
                if check_meta_users:
                    logger.info("Moving metadata.users to control_plane schema...")
                    conn.execute(text("ALTER TABLE metadata.users SET SCHEMA control_plane;"))
                else:
                    logger.info("Creating control_plane.users table...")
                    conn.execute(text("""
                        CREATE TABLE control_plane.users (
                            user_id UUID PRIMARY KEY,
                            email VARCHAR(100) UNIQUE NOT NULL,
                            hashed_password TEXT NOT NULL,
                            role VARCHAR(50) NOT NULL DEFAULT 'USER',
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                    """))
            
            # 3. Check if role column exists in control_plane.users
            check_role_col = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = 'control_plane' 
                      AND table_name = 'users' 
                      AND column_name = 'role'
                )
            """)).scalar()
            
            if not check_role_col:
                logger.info("Adding role column to control_plane.users...")
                conn.execute(text("ALTER TABLE control_plane.users ADD COLUMN role VARCHAR(50) NOT NULL DEFAULT 'USER';"))
                
            # 4. Check if control_plane.audit_logs exists
            check_audit_logs = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'control_plane' AND table_name = 'audit_logs')"
            )).scalar()
            
            if not check_audit_logs:
                logger.info("Creating control_plane.audit_logs table...")
                conn.execute(text("""
                    CREATE TABLE control_plane.audit_logs (
                        log_id UUID PRIMARY KEY,
                        user_email VARCHAR(255) NOT NULL,
                        action VARCHAR(100) NOT NULL,
                        details JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                
            # 5. Set default developer user role to OWNER
            logger.info("Ensuring dev-engineer@sutherland.com is OWNER...")
            conn.execute(text("""
                UPDATE control_plane.users 
                SET role = 'OWNER' 
                WHERE email = 'dev-engineer@sutherland.com';
            """))
            
            transaction.commit()
            logger.info("Migrations completed successfully!")
            
        except Exception as e:
            transaction.rollback()
            logger.error(f"Migration failed: {e}")
            raise e

if __name__ == "__main__":
    run_migrations()
