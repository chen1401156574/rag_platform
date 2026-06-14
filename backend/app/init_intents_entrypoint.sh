#!/bin/sh
# Entry point for one‑time intent initialization
# If intent data already exists, exit without re‑initializing.

# Use Python to check record count
python - <<'PY'
import sys
from utils.database import SessionLocal
from models.intent import IntentNode

db = SessionLocal()
count = db.query(IntentNode).filter(IntentNode.deleted == 0).count()
if count > 0:
    print(f'Intent data already exists ({count} rows), skipping initialization.')
    sys.exit(0)
else:
    print('No intent data found, running initialization...')
    sys.exit(1)
PY
# If the Python check exited with code 1, run the init script
if [ $? -eq 1 ]; then
    python /app/db_init_intents.py
fi
