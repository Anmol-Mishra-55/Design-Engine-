from typing import Any, List, Tuple

from sqlalchemy.sql import text


def build_preferences_from_db(db: Any, min_delta: float = 0.5):
    """
    Produce (prompt, before_spec, after_spec, preferred) tuples
    using iterations + evaluations. preferred == "B" if rating improved.
    """
    pairs = []
    rows = db.execute(
        text(
            """
      SELECT i.spec_id, i.spec_json, e.rating AS new_score, e.created_at AS ets
      FROM iterations i
      JOIN evaluations e ON e.spec_id = i.spec_id
      ORDER BY e.created_at DESC
    """
        )
    ).fetchall()

    for spec_id, spec_json, new_score, ets in rows:
        prev = db.execute(
            text(
                """
           SELECT rating FROM evaluations
           WHERE spec_id=:sid AND created_at < :ets
           ORDER BY created_at DESC LIMIT 1
        """
            ),
            {"sid": spec_id, "ets": ets},
        ).fetchone()
        if not prev:
            continue
        prev_score = float(prev[0])
        delta = float(new_score) - prev_score
        if abs(delta) < min_delta:
            continue
        preferred = "B" if delta > 0 else "A"
        # Use current spec_json as both before and after for now
        pairs.append(("Improve design", spec_json, spec_json, preferred))
    return pairs
