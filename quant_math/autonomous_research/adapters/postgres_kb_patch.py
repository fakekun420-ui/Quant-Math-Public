import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def archive_dead_hypotheses(jsonl_path: str, records: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Garbage Collection: moves permanently failed/dead hypotheses to an archive to keep JSONL fast."""
    archive_path = jsonl_path.replace('.jsonl', '_archive.jsonl')
    active_records = {}
    archived_count = 0
    
    with open(archive_path, 'a', encoding='utf-8') as fh:
        for hid, rec in records.items():
            # If status is failed and hasn't been updated in a while, or score is too low
            status = rec.get("status")
            if status in ["failed", "rejected", "deprecated"] and rec.get("expectancy", 1) <= 0:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                archived_count += 1
            else:
                active_records[hid] = rec
                
    if archived_count > 0:
        logger.info(f"[jsonl-kb] Archived {archived_count} dead hypotheses to {archive_path}")
    return active_records
