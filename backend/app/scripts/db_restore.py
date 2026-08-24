import argparse
import logging
import sqlite3
import os
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def restore_sqlite_db(backup_db_path: str, live_db_path: str):
    logger.info(f"Initiating restore from {backup_db_path} to {live_db_path}")
    
    if not os.path.exists(backup_db_path):
        logger.error(f"Backup database {backup_db_path} does not exist.")
        exit(1)

    # For safety, we can either use the backup API in reverse or copy the file.
    # Given that a restore implies disaster recovery or rollback, the app should be quiesced.
    # We will safely copy the file.
    try:
        if os.path.exists(live_db_path):
            shutil.copy2(live_db_path, f"{live_db_path}.corrupted.bak")
            logger.info(f"Saved current state as {live_db_path}.corrupted.bak just in case.")
            
        shutil.copy2(backup_db_path, live_db_path)
        logger.info("Restore completed successfully.")
        
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely Restore SQLite DB")
    parser.add_argument("--backup", required=True, help="Path to backup SQLite file (e.g. v2_prod_backup.db)")
    parser.add_argument("--target", required=True, help="Path to destination live file (e.g. v2_prod.db)")
    args = parser.parse_args()
    
    restore_sqlite_db(args.backup, args.target)
