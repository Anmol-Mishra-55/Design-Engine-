#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import engine

# Drop existing indexes if they exist
with engine.connect() as conn:
    try:
        conn.execute(text("DROP INDEX IF EXISTS ix_rl_feedback_user_created CASCADE"))
        conn.execute(text("DROP INDEX IF EXISTS ix_rl_feedback_city CASCADE"))
        conn.execute(text("DROP INDEX IF EXISTS ix_rl_live_feedback_user_created CASCADE"))
        conn.execute(text("DROP INDEX IF EXISTS ix_rl_live_feedback_city CASCADE"))
        conn.commit()
        print("Dropped existing indexes")
    except Exception as e:
        print(f"Index drop warning: {e}")

# Create table
RLLiveFeedback.__table__.create(engine, checkfirst=True)
print("RLLiveFeedback table created successfully")
