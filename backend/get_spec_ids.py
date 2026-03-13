from app.database_mongodb import engine

with engine.connect() as conn:
    result = conn.execute(text("SELECT id FROM specs LIMIT 3"))
    print("Available spec_ids:")
    for row in result:
        print(f"  {row[0]}")
