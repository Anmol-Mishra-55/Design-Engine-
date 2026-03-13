from app.database_mongodb import engine

with engine.connect() as conn:
    result = conn.execute(
        text(
            "SELECT user_id, action, details, created_at FROM audit_logs WHERE action = 'create_report' ORDER BY created_at DESC LIMIT 3"
        )
    )
    print("Recent reports in database:")
    for row in result:
        print(f"  User: {row[0]}, Action: {row[1]}")
        print(f"  Details: {row[2]}")
        print(f"  Created: {row[3]}")
        print("  ---")
