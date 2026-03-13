from app.database_mongodb import engine

with engine.connect() as conn:
    # Create reports table
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            report_id VARCHAR(255) UNIQUE NOT NULL,
            user_id VARCHAR(255) NOT NULL,
            title TEXT,
            content TEXT,
            report_type VARCHAR(100),
            spec_id VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """
        )
    )
    conn.commit()
    print("Reports table created successfully")
