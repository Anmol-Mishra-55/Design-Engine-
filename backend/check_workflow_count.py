from app.database_mongodb import engine

with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM workflow_runs"))
    print("Total workflow runs:", result.fetchone()[0])

    result = conn.execute(text("SELECT flow_run_id, status, created_at FROM workflow_runs ORDER BY created_at DESC"))
    print("\nRecent workflows:")
    for row in result:
        print(f"  {row[0]} - {row[1]} - {row[2]}")
