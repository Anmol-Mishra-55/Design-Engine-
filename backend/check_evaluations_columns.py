from app.database_mongodb import engine

with engine.connect() as conn:
    result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'evaluations'"))
    print("Evaluations columns:", [row[0] for row in result])
