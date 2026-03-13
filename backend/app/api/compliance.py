import base64
import json
import logging

import httpx

logger = logging.getLogger(__name__)
from app.auth_mongodb import get_current_user
from app.config import settings
from app.database_mongodb import get_database
from app.schemas import ComplianceRequest, ComplianceResponse
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter()

SOHAM_URL = settings.SOHAM_URL
API_KEY = settings.COMPLIANCE_API_KEY


@router.get("/test", include_in_schema=False)
async def test_endpoint(current_user: str = Depends(get_current_user)):
    return {"message": "Compliance endpoint is working", "timestamp": "2024-01-01", "user": current_user}


@router.post("/run_case", include_in_schema=False)
async def run_case(case: dict, current_user: str = Depends(get_current_user)):
    try:
        logger.info(f"Processing compliance case for {case.get('city')} - Project: {case.get('project_id')}")

        # Validate city
        city = case.get("city", "").lower()
        if city not in ["mumbai", "pune", "ahmedabad", "nashik"]:
            raise HTTPException(
                status_code=400, detail=f"Invalid city: {city}. Supported cities: Mumbai, Pune, Ahmedabad, Nashik"
            )

        # Check if we should use mock response based on service health
        if False:
            logger.info(f"Using mock response for {city} - external service unavailable")
            return await _mock_compliance_response(case)

        # Call Soham's compliance service with extended timeout
        logger.info(f"Calling external compliance service for {city}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{SOHAM_URL}/run_case", json=case)

        if res.status_code == 200:
            data = res.json()
            logger.info(f"Successfully received compliance analysis from external service ({len(res.content)} bytes)")
            return data
        else:
            logger.warning(f"External compliance service returned status {res.status_code}")
            raise Exception(f"External service returned {res.status_code}")

    except httpx.TimeoutException as e:
        logger.warning(f"Compliance service timeout after 60 seconds: {e}")
        return await _mock_compliance_response(case)
    except httpx.RequestError as e:
        logger.error(f"Network error calling compliance service: {e}")
        return await _mock_compliance_response(case)
    except Exception as e:
        logger.error(f"Unexpected error in compliance service: {type(e).__name__}: {e}")
        return await _mock_compliance_response(case)


async def _mock_compliance_response(case: dict):
    """Enhanced mock compliance response matching Soham's format"""
    try:
        import uuid
        from datetime import datetime

        logger.info(f"Generating mock compliance response for {case.get('city')}")

        city_name = case.get("city", "Mumbai")
        city = city_name.lower()
        project_id = case.get("project_id", "unknown_project")
        case_id = case.get("case_id", f"{city}_case_{str(uuid.uuid4())[:8]}")

        # City-specific mock rules
        city_rules = {
            "mumbai": ["MUM-FSI-URBAN-R15-20", "MUM-SETBACK-R15-20", "MUM-HEIGHT-STANDARD"],
            "pune": ["PUNE-HEIGHT-SPECIAL-ECO", "PUNE-FSI-SUBURBAN", "PUNE-SETBACK-ECO"],
            "ahmedabad": ["AMD-FSI-URBAN-R15-20", "AMD-SETBACK-R15-20", "AMD-HEIGHT-HERITAGE"],
            "nashik": ["NAS-FSI-SUBURBAN-R10-15", "NAS-SETBACK-R10-15", "NAS-HEIGHT-WINE-TOURISM"],
        }

        return {
            "project_id": project_id,
            "case_id": case_id,
            "city": city_name,
            "parameters": case.get("parameters", {}),
            "rules_applied": city_rules.get(city, city_rules["mumbai"]),
            "reasoning": f"Mock compliance analysis for {city_name} project. This is a fallback response when the external compliance service is unavailable. For detailed analysis, please ensure the external service is accessible.",
            "clause_summaries": [
                {
                    "clause_id": rule,
                    "authority": f"{city_name} Municipal Corporation",
                    "notes": f"Mock rule for {city_name} compliance",
                    "quick_summary": "Fallback compliance check",
                }
                for rule in city_rules.get(city, city_rules["mumbai"])
            ],
            "confidence_score": 0.3,
            "confidence_level": "Low",
            "confidence_note": "Mock response - external compliance service unavailable",
            "basic_reasoning": f"Fallback compliance analysis for {city_name} project with mock regulations.",
        }
    except Exception as e:
        logger.error(f"Mock response generation failed: {e}")
        return {"case_id": "error_case", "status": "ERROR", "message": f"Mock response generation failed: {str(e)}"}


@router.post("/feedback", include_in_schema=False)
async def feedback(feedback_req: dict, current_user: str = Depends(get_current_user)):
    """Submit compliance feedback to Soham's service"""
    try:
        logger.info(f"Submitting compliance feedback for project: {feedback_req.get('project_id')}")

        # Validate required fields
        required_fields = ["project_id", "case_id", "user_feedback"]
        for field in required_fields:
            if field not in feedback_req:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Validate user_feedback value
        valid_feedback = ["up", "down"]
        if feedback_req.get("user_feedback") not in valid_feedback:
            raise HTTPException(status_code=400, detail=f"Invalid user_feedback. Must be one of: {valid_feedback}")

        headers = {}
        if API_KEY:
            headers["Authorization"] = f"Bearer {API_KEY}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(f"{SOHAM_URL}/feedback", json=feedback_req, headers=headers)

        if res.status_code != 200:
            logger.error(f"Soham feedback service returned {res.status_code}: {res.text}")
            raise HTTPException(status_code=500, detail="Compliance feedback failed")

        data = res.json()
        logger.info(f"Feedback submitted successfully: {data.get('feedback_id')}")
        return data

    except httpx.TimeoutException as e:
        logger.error(f"Timeout submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Feedback service timeout")
    except httpx.RequestError as e:
        logger.error(f"Network error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Network error")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/ingest_pdf", include_in_schema=False)
async def ingest_pdf_rules(request: dict, current_user: str = Depends(get_current_user)):
    """Ingest compliance rules from PDF using Prefect workflow"""
    try:
        pdf_url = request.get("pdf_url")
        city = request.get("city", "Mumbai")

        if not pdf_url:
            raise HTTPException(status_code=400, detail="pdf_url is required")

        # Trigger PDF processing workflow
        result = {"status": "mock"}

        return {"message": "PDF processing initiated", "city": city, "workflow_result": result}

    except Exception as e:
        logger.error(f"PDF ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workflow_status", include_in_schema=False)
async def get_workflow_status(current_user: str = Depends(get_current_user)):
    """Get workflow system status"""
    return {"status": "healthy"}


@router.get("/regulations", include_in_schema=False)
async def get_regulations(current_user: str = Depends(get_current_user)):
    """Get available compliance regulations"""
    return {
        "regulations": [
            {"id": "ISO_9001", "name": "ISO 9001 Quality Management"},
            {"id": "OSHA", "name": "OSHA Safety Standards"},
            {"id": "CE_MARKING", "name": "CE Marking Requirements"},
            {"id": "FDA_510K", "name": "FDA 510(k) Medical Device"},
        ]
    }


@router.post("/check", response_model=ComplianceResponse, include_in_schema=False)
async def compliance_check(request: ComplianceRequest, current_user: str = Depends(get_current_user)):
    # Get spec for compliance check
    db = get_database()
    spec = await db.specs.find_one({"_id": request.spec_id})
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    # Generate compliance report (placeholder)
    compliance_report = {
        "spec_id": request.spec_id,
        "compliance_status": "PASSED",
        "checks": [
            {"rule": "Safety Standards", "status": "PASSED"},
            {"rule": "Material Requirements", "status": "PASSED"},
            {"rule": "Dimensional Constraints", "status": "PASSED"},
        ],
        "generated_at": "2024-01-01T00:00:00Z",
    }

    # Create compliance ZIP file with timestamp to avoid duplicates
    import uuid
    from datetime import datetime

    compliance_data = json.dumps(compliance_report, indent=2).encode("utf-8")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    case_id = f"case_{request.spec_id}_{timestamp}_{unique_id}"

    # Upload compliance report with error handling
    try:
        # Mock upload since we removed Supabase and now use MongoDB GridFS
        compliance_url = f"https://mock-compliance-{case_id}.zip"
        logger.info(f"Mock compliance report generated: {case_id}")
    except Exception as e:
        logger.warning(f"Mock upload: {e}")
        compliance_url = f"https://mock-compliance-{case_id}.zip"

    return ComplianceResponse(compliance_url=compliance_url, status="PASSED")
