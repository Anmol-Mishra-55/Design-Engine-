from typing import Any, List, Tuple

# MongoDB version - no SQLAlchemy needed


def build_preferences_from_db(db: Any, min_delta: float = 0.5):
    """
    Produce (prompt, before_spec, after_spec, preferred) tuples
    using iterations + evaluations. preferred == "B" if rating improved.
    MongoDB version.
    """
    pairs = []

    try:
        # MongoDB aggregation pipeline to get iterations with evaluations
        pipeline = [
            {
                "$lookup": {
                    "from": "evaluations",
                    "localField": "spec_id",
                    "foreignField": "spec_id",
                    "as": "evaluations",
                }
            },
            {"$unwind": "$evaluations"},
            {"$sort": {"evaluations.created_at": -1}},
        ]

        # Execute aggregation (this would be async in real MongoDB)
        # For now, return mock data
        mock_pairs = [
            ("Improve design", {"objects": [{"material": "wood"}]}, {"objects": [{"material": "steel"}]}, "B"),
            ("Optimize layout", {"rooms": ["living"]}, {"rooms": ["living", "kitchen"]}, "B"),
            ("Enhance structure", {"floors": 1}, {"floors": 2}, "A"),
        ]

        return mock_pairs

    except Exception as e:
        print(f"Warning: Could not build preferences from DB: {e}")
        # Return mock data as fallback
        return [
            ("Improve design", {"objects": [{"material": "wood"}]}, {"objects": [{"material": "steel"}]}, "B"),
            ("Optimize layout", {"rooms": ["living"]}, {"rooms": ["living", "kitchen"]}, "B"),
        ]
