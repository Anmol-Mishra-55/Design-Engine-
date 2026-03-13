#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import engine

# Drop indexes and table
with engine.connect() as conn:
    conn.execute(text("DROP INDEX IF EXISTS ix_rl_live_feedback_user_created CASCADE"))
    conn.execute(text("DROP INDEX IF EXISTS ix_rl_live_feedback_city CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS rl_live_feedback CASCADE"))
    conn.commit()
    print("Dropped table and indexes")

# Recreate table

RLLiveFeedback.__table__.create(engine)
print("RLLiveFeedback table created successfully")
