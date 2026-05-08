# Backup Manager - Backup memory files

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List
from datetime import datetime
import shutil
import glob
from shared import (
    timestamp, ensure_dir, setup_logging
)

logger = setup_logging(__name__, "./logs/backup.log")

class BackupManager:
    """
    Manage memory backups
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        memory_config = config.get('memory', {})
        self.backup_path = memory_config.get('backup_path', './data/backups')
        self.backup_interval = memory_config.get('backup_interval', 86400)
        self.retention_days = 7

        ensure_dir(self.backup_path)
        logger.info(f"BackupManager initialized: {self.backup_path}")

    def create_backup(self, source_path: str, backup_name: str = None) -> Dict[str, Any]:
        """Create a backup of memory"""
        if not os.path.exists(source_path):
            return {"status": "error", "message": "Source path does not exist"}

        if backup_name is None:
            ts = timestamp().replace(':', '-').replace('T', '_')
            backup_name = f"backup_{ts}"

        backup_file = os.path.join(self.backup_path, f"{backup_name}.tar.gz")

        try:
            shutil.make_archive(
                os.path.join(self.backup_path, backup_name),
                'gztar',
                source_path
            )

            logger.info(f"Backup created: {backup_file}")

            return {
                "status": "success",
                "backup_file": backup_file,
                "timestamp": timestamp()
            }
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {"status": "error", "message": str(e)}

    def restore_backup(self, backup_file: str, dest_path: str) -> Dict[str, Any]:
        """Restore from backup"""
        if not os.path.exists(backup_file):
            return {"status": "error", "message": "Backup file not found"}

        try:
            shutil.unpack_archive(backup_file, dest_path)
            logger.info(f"Restored from: {backup_file}")

            return {
                "status": "success",
                "restored_to": dest_path,
                "timestamp": timestamp()
            }
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"status": "error", "message": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all backups"""
        backups = []
        pattern = os.path.join(self.backup_path, "backup_*.tar.gz")

        for filepath in glob.glob(pattern):
            stat = os.stat(filepath)
            backups.append({
                "file": filepath,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        return sorted(backups, key=lambda x: x['created_at'], reverse=True)

    def cleanup_old(self) -> Dict[str, Any]:
        """Remove old backups"""
        cutoff = datetime.now().timestamp() - (self.retention_days * 86400)
        removed = 0

        for filepath in glob.glob(os.path.join(self.backup_path, "backup_*.tar.gz")):
            stat = os.stat(filepath)
            if stat.st_mtime < cutoff:
                try:
                    os.remove(filepath)
                    removed += 1
                except Exception as e:
                    logger.error(f"Failed to remove {filepath}: {e}")

        logger.info(f"Cleaned up {removed} old backups")

        return {"removed": removed, "retention_days": self.retention_days}

    def get_latest_backup(self) -> Dict[str, Any]:
        """Get the most recent backup"""
        backups = self.list_backups()
        if backups:
            return {"status": "found", "backup": backups[0]}
        return {"status": "not_found"}
