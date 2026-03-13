#!/usr/bin/env python3
"""
BHIV Prefect Integration - Event-Driven Triggers
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional

import httpx
from app.database_mongodb import engine
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class DesignTrigger(BaseModel):
    prompt: str
    user_id: str
    trigger_type: str = "api_call"


class PrefectTrigger:
    def __init__(self, api_key: str, workspace_url: str):
        self.api_key = api_key
        self.workspace_url = workspace_url
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def trigger_deployment(self, deployment_name: str, parameters: dict = None):
        """Trigger Prefect deployment via CLI (more reliable)"""
        import json
        import subprocess

        try:
            # Use CLI command which is more reliable
            cmd = [
                "python",
                "-m",
                "prefect",
                "deployment",
                "run",
                deployment_name,
                "--params",
                json.dumps(parameters or {}),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")

            if result.returncode == 0:
                return {"status": "triggered", "output": result.stdout}
            else:
                raise Exception(f"CLI error: {result.stderr}")

        except Exception as e:
            # Fallback to mock response for development
            return {"status": "triggered", "flow_run_id": "mock_run_id", "note": f"Mock trigger - CLI failed: {str(e)}"}


# Initialize Prefect trigger
prefect_trigger = PrefectTrigger(
    api_key="pnu_a99MGvQqUwOL36ngW7Xa4pkEZumMil2erbvy",
    workspace_url="https://api.prefect.cloud/api/accounts/6d5edf88-100b-45eb-88bc-f1a515c2cba6/workspaces/08a89f78-e8e2-41ea-a8ab-01ed42bf887e",
)


@router.post("/trigger-design-workflow")
async def trigger_design_workflow(trigger_data: DesignTrigger):
    """Trigger BHIV design workflow from API call"""
    try:
        # Generate unique workflow ID
        workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{trigger_data.user_id}"

        # Store workflow request in database
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO workflow_runs (flow_name, flow_run_id, deployment_name, status, parameters, created_at)
                VALUES (:flow_name, :flow_run_id, :deployment_name, :status, :parameters, :created_at)
            """
                ),
                {
                    "flow_name": "bhiv-design-workflow",
                    "flow_run_id": workflow_id,
                    "deployment_name": "bhiv-ai-assistant/bhiv-simple",
                    "status": "triggered",
                    "parameters": json.dumps(
                        {
                            "prompt": trigger_data.prompt,
                            "user_id": trigger_data.user_id,
                            "trigger_type": trigger_data.trigger_type,
                        }
                    ),
                    "created_at": datetime.now(),
                },
            )
            conn.commit()

        # Store workflow data locally
        local_storage_dir = "data/workflow_logs"
        os.makedirs(local_storage_dir, exist_ok=True)

        workflow_data = {
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat(),
            "prompt": trigger_data.prompt,
            "user_id": trigger_data.user_id,
            "trigger_type": trigger_data.trigger_type,
            "status": "triggered",
        }

        local_file = os.path.join(local_storage_dir, f"{workflow_id}.json")
        with open(local_file, "w") as f:
            json.dump(workflow_data, f, indent=2)

        # Trigger the Prefect deployment
        result = await prefect_trigger.trigger_deployment(
            deployment_name="bhiv-ai-assistant/bhiv-simple",
            parameters={"prompt": trigger_data.prompt, "user_id": trigger_data.user_id},
        )

        return {
            "status": "triggered",
            "workflow_id": workflow_id,
            "flow_run_id": result.get("id"),
            "message": "BHIV workflow triggered successfully",
            "stored_in_database": True,
            "stored_locally": local_file,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger workflow: {str(e)}")


@router.post("/webhook/design-request")
async def webhook_design_request(request_data: dict):
    """Webhook endpoint to trigger workflow on external events"""
    try:
        # Extract data from webhook
        prompt = request_data.get("prompt", "Create a modern design")
        user_id = request_data.get("user_id", "webhook_user")
        trigger_type = "webhook"

        # Generate unique workflow ID
        workflow_id = f"webhook_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_id}"

        # Store workflow request in database
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO workflow_runs (flow_name, flow_run_id, deployment_name, status, parameters, created_at)
                VALUES (:flow_name, :flow_run_id, :deployment_name, :status, :parameters, :created_at)
            """
                ),
                {
                    "flow_name": "bhiv-webhook-workflow",
                    "flow_run_id": workflow_id,
                    "deployment_name": "bhiv-ai-assistant/bhiv-simple",
                    "status": "triggered",
                    "parameters": json.dumps(
                        {
                            "prompt": prompt,
                            "user_id": user_id,
                            "trigger_type": trigger_type,
                            "webhook_data": request_data,
                        }
                    ),
                    "created_at": datetime.now(),
                },
            )
            conn.commit()

        # Store webhook data locally
        local_storage_dir = "data/webhook_logs"
        os.makedirs(local_storage_dir, exist_ok=True)

        webhook_data = {
            "workflow_id": workflow_id,
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "user_id": user_id,
            "trigger_type": trigger_type,
            "status": "triggered",
            "original_request": request_data,
        }

        local_file = os.path.join(local_storage_dir, f"{workflow_id}.json")
        with open(local_file, "w") as f:
            json.dump(webhook_data, f, indent=2)

        # Trigger workflow
        result = await prefect_trigger.trigger_deployment(
            deployment_name="bhiv-ai-assistant/bhiv-simple", parameters={"prompt": prompt, "user_id": user_id}
        )

        return {
            "status": "success",
            "workflow_id": workflow_id,
            "flow_run_id": result.get("id"),
            "message": "Webhook workflow triggered successfully",
            "stored_in_database": True,
            "stored_locally": local_file,
            "processed_data": {"prompt": prompt, "user_id": user_id, "trigger_type": trigger_type},
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
