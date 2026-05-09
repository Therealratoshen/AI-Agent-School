# Shared utilities

import os
import json
import logging
from pathlib import Path
from datetime import datetime

def setup_logging(name: str, log_file: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)

def write_json(path: str, data: dict) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def timestamp() -> str:
    return datetime.utcnow().isoformat()

def generate_id(prefix: str = "") -> str:
    import uuid
    return f"{prefix}{uuid.uuid4().hex[:8]}"

def safe_read(path: str, default: str = "") -> str:
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception:
        return default

def safe_json_read(path: str, default: dict = None) -> dict:
    if default is None:
        default = {}
    try:
        return read_json(path)
    except Exception:
        return default
