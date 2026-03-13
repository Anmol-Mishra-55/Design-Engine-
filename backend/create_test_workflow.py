#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uuid
from datetime import datetime

from app.database_mongodb import get_database


def create_test_workflow_run():
    db = next(get_db())

    # Create a test workflow run entry
    test_flow_run_id = "test-flow-run-" + str(uuid.uuid4())[:8]

    insert_query = text(
        """
        INSERT INTO workflow_runs
        (id, flow_name, flow_run_id, deployment_name, status, parameters, result, created_at)
        VALUES
        (:id, :flow_name, :flow_run_id, :deployment_name, :status, :parameters, :result, :created_at)
    """
    )

    db.execute(
        insert_query,
        {
            "id": str(uuid.uuid4()),
            "flow_name": "test-workflow",
            "flow_run_id": test_flow_run_id,
            "deployment_name": "test-deployment",
            "status": "completed",
            "parameters": '{"test": "data"}',
            "result": '{"status": "success", "message": "Test workflow completed"}',
            "created_at": datetime.utcnow(),
        },
    )

    db.commit()
    print(f"Created test workflow run with ID: {test_flow_run_id}")
    return test_flow_run_id


if __name__ == "__main__":
    flow_id = create_test_workflow_run()
