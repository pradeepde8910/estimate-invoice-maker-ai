import argparse
import logging
import sqlite3
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def backup_sqlite_db(source_db_path: str, target_backup_path: str):
    logger.info(f"Initiating safe backup of {source_db_path} to {target_backup_path}")
    
    if not os.path.exists(source_db_path):
        logger.error(f"Source database {source_db_path} does not exist.")
        exit(1)

    try:
        source_conn = sqlite3.connect(source_db_path)
        target_conn = sqlite3.connect(target_backup_path)
        
        with target_conn:
            # The backup() method uses the SQLite backup API which handles concurrency
            # and locking correctly without stopping the source database.
            source_conn.backup(target_conn)
            
        logger.info("Backup completed successfully.")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        exit(1)
    finally:
        source_conn.close()
        target_conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safely Backup SQLite DB")
    parser.add_argument("--source", required=True, help="Path to source SQLite file (e.g. v2_prod.db)")
    parser.add_argument("--target", required=True, help="Path to destination backup file (e.g. v2_prod_backup.db)")
    args = parser.parse_args()
    
    backup_sqlite_db(args.source, args.target)
