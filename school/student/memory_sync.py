# Memory Sync - Sync memory between school and student

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from typing import Dict, Any, List, Optional
from shared import (
    timestamp, generate_id, ensure_dir,
    read_json, write_json, setup_logging
)
import shutil

logger = setup_logging(__name__, "./logs/memory_sync.log")

class MemorySync:
    """
    Synchronize and backup student agent memory
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        memory_config = config.get('memory', {})
        self.student_memory_path = memory_config.get('student_memory_path', '/home/user/openclaw/memory')
        self.backup_path = memory_config.get('backup_path', './data/backups')

        ensure_dir(self.backup_path)
        logger.info(f"MemorySync initialized, memory_path: {self.student_memory_path}")

    def check_memory_health(self) -> Dict[str, Any]:
        """Check health of student memory"""
        if not os.path.exists(self.student_memory_path):
            return {
                "healthy": False,
                "error": "Memory path does not exist",
                "memory_path": self.student_memory_path
            }

        try:
            files = os.listdir(self.student_memory_path)
            total_size = sum(
                os.path.getsize(os.path.join(self.student_memory_path, f))
                for f in files if os.path.isfile(os.path.join(self.student_memory_path, f))
            )

            return {
                "healthy": True,
                "files": len(files),
                "total_size_bytes": total_size,
                "memory_path": self.student_memory_path
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "memory_path": self.student_memory_path
            }

    def backup_memory(self) -> Dict[str, Any]:
        """Create backup of student memory"""
        if not os.path.exists(self.student_memory_path):
            return {"status": "error", "message": "Memory path does not exist"}

        timestamp_str = timestamp().replace(':', '-').replace('T', '_')
        backup_name = f"memory_backup_{timestamp_str}"
        backup_file = os.path.join(self.backup_path, f"{backup_name}.tar.gz")

        try:
            shutil.make_archive(
                os.path.join(self.backup_path, backup_name),
                'gztar',
                self.student_memory_path
            )

            logger.info(f"Memory backed up: {backup_file}")

            return {
                "status": "success",
                "backup_file": backup_file,
                "timestamp": timestamp()
            }
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {"status": "error", "message": str(e)}

    def restore_memory(self, backup_file: str) -> Dict[str, Any]:
        """Restore memory from backup"""
        if not os.path.exists(backup_file):
            return {"status": "error", "message": "Backup file not found"}

        try:
            extract_dir = os.path.join(self.backup_path, "restore_temp")
            shutil.unpack_archive(backup_file, extract_dir)

            for item in os.listdir(extract_dir):
                src = os.path.join(extract_dir, item)
                dst = os.path.join(self.student_memory_path, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

            shutil.rmtree(extract_dir)

            logger.info(f"Memory restored from: {backup_file}")

            return {
                "status": "success",
                "backup_file": backup_file,
                "timestamp": timestamp()
            }
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"status": "error", "message": str(e)}

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        import glob

        backups = []
        pattern = os.path.join(self.backup_path, "memory_backup_*.tar.gz")

        for filepath in glob.glob(pattern):
            stat = os.stat(filepath)
            backups.append({
                "file": filepath,
                "size_bytes": stat.st_size,
                "created": timestamp.fromtimestamp(stat.st_mtime)
            })

        return sorted(backups, key=lambda x: x['created'], reverse=True)

    def save_correction(self, correction: Dict[str, Any]) -> Dict[str, Any]:
        """Save correction to student's memory"""
        corrections_file = os.path.join(self.student_memory_path, "corrections.json")

        corrections = []
        if os.path.exists(corrections_file):
            corrections = read_json(corrections_file, [])

        correction['id'] = generate_id("corr_")
        correction['saved_at'] = timestamp()
        corrections.append(correction)

        write_json(corrections_file, corrections)

        logger.info(f"Correction saved: {correction['id']}")

        return {
            "status": "saved",
            "correction_id": correction['id'],
            "total_corrections": len(corrections)
        }

    def get_corrections(self) -> List[Dict[str, Any]]:
        """Get all saved corrections"""
        corrections_file = os.path.join(self.student_memory_path, "corrections.json")
        return read_json(corrections_file, [])
