from app.database_mongodb import engine

with engine.connect() as conn:
    result = conn.execute(
        text("SELECT report_id, user_id, title, report_type, created_at FROM reports ORDER BY created_at DESC")
    )
    print("Reports in database:")
    for row in result:
        print(f"  Report ID: {row[0]}")
        print(f"  User: {row[1]}")
        print(f"  Title: {row[2]}")
        print(f"  Type: {row[3]}")
        print(f"  Created: {row[4]}")
        print("  ---")
