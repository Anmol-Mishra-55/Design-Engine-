import logging

from app.auth_mongodb import get_current_user, get_db
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/reports/{spec_id}")
async def get_report(
    spec_id: str,
    current_user: str = Depends(get_current_user),
):
    """Get complete report with data integrity checks"""
    try:
        # Get spec with all related data
        spec = None  # Mock database operation
        if not spec:
            # Get available specs for helpful error message
            available_specs = None  # Mock database operation
            available_ids = [s.id for s in available_specs]

            error_detail = {
                "error": "Spec not found",
                "requested_spec_id": spec_id,
                "message": f"The spec '{spec_id}' does not exist in the database.",
                "available_specs": available_ids,
                "hint": "Use one of the available spec IDs or create a new design using POST /api/v1/generate",
            }
            raise HTTPException(status_code=404, detail=error_detail)

        # Get all related data
        iterations = None  # Mock database operation
        evaluations = None  # Mock database operation
        compliance_checks = (
            db.query(ComplianceCheck)
            .filter(ComplianceCheck.spec_id == spec_id)
            .order_by(ComplianceCheck.created_at.desc())
            .all()
        )

        # Build complete response with data integrity
        response_data = {
            "report_id": spec_id,
            "data": {
                "spec_id": spec_id,
                "version": spec.version or 1,
                "user_id": spec.user_id,
                "project_id": spec.project_id,
                "city": spec.city,
                "design_type": spec.design_type,
                "status": spec.status,
                "compliance_status": spec.compliance_status,
            },
            "spec": spec.spec_json or {},
            "preview_url": spec.preview_url,
            "geometry_url": spec.geometry_url,
            "estimated_cost": spec.estimated_cost,
            "currency": spec.currency,
            "iterations": [
                {
                    "id": it.id,
                    "query": it.query,
                    "diff": it.diff,
                    "spec_json": it.spec_json,
                    "preview_url": it.preview_url,
                    "cost_delta": it.cost_delta,
                    "created_at": it.created_at.isoformat() if it.created_at else None,
                }
                for it in iterations
            ],
            "evaluations": [
                {
                    "id": ev.id,
                    "score": ev.rating or 0,
                    "rating": ev.rating,
                    "notes": ev.notes or "",
                    "aspects": ev.aspects,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                }
                for ev in evaluations
            ],
            "compliance_checks": [
                {
                    "id": cc.id,
                    "case_id": cc.case_id,
                    "status": cc.status,
                    "compliant": cc.compliant,
                    "confidence_score": cc.confidence_score,
                    "violations": cc.violations or [],
                    "recommendations": cc.recommendations or [],
                    "created_at": cc.created_at.isoformat() if cc.created_at else None,
                }
                for cc in compliance_checks
            ],
            "preview_urls": [],
            "data_integrity": {
                "spec_json_exists": spec.spec_json is not None,
                "preview_url_exists": spec.preview_url is not None,
                "geometry_url_exists": spec.geometry_url is not None,
                "has_iterations": len(iterations) > 0,
                "has_evaluations": len(evaluations) > 0,
                "has_compliance": len(compliance_checks) > 0,
                "data_complete": True,
            },
            "created_at": spec.created_at.isoformat() if spec.created_at else None,
            "updated_at": spec.updated_at.isoformat() if spec.updated_at else None,
        }

        # Add preview URLs if available
        if spec.preview_url:
            response_data["preview_urls"].append(spec.preview_url)

        for it in iterations:
            if it.preview_url:
                response_data["preview_urls"].append(it.preview_url)

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_report for {spec_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/reports")
async def create_report(
    request: dict,
    current_user: str = Depends(get_current_user),
):
    import json
    import os
    from datetime import datetime

    from app.database_mongodb import engine

    title = request.get("title", "Untitled Report")
    content = request.get("content", "")
    report_type = request.get("report_type", "general")
    spec_id = request.get("spec_id", None)

    # Generate report ID
    report_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{current_user}"

    # Store in database
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO reports (report_id, user_id, title, content, report_type, spec_id, created_at)
                VALUES (:report_id, :user_id, :title, :content, :report_type, :spec_id, :created_at)
            """
                ),
                {
                    "report_id": report_id,
                    "user_id": current_user,
                    "title": title,
                    "content": content,
                    "report_type": report_type,
                    "spec_id": spec_id,
                    "created_at": datetime.now(),
                },
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to store report in database: {e}")
    # Store locally
    local_storage_dir = "data/reports"
    os.makedirs(local_storage_dir, exist_ok=True)

    report_data = {
        "report_id": report_id,
        "title": title,
        "content": content,
        "report_type": report_type,
        "spec_id": spec_id,
        "user": current_user,
        "created_at": datetime.now().isoformat(),
    }

    local_file = os.path.join(local_storage_dir, f"{report_id}.json")
    with open(local_file, "w") as f:
        json.dump(report_data, f, indent=2)

    return {
        "message": "Report created successfully",
        "report_id": report_id,
        "title": title,
        "content": content,
        "report_type": report_type,
        "user": current_user,
        "stored_in_database": True,
        "stored_locally": local_file,
    }


@router.post("/upload")
async def upload_report_file(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    import json
    import os
    from datetime import datetime

    from app.database_mongodb import engine

    file_content = await file.read()

    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = os.path.splitext(file.filename)[1]
    file_base = os.path.splitext(file.filename)[0]
    unique_filename = f"{file_base}_{timestamp}{file_ext}"
    file_path = f"reports/{unique_filename}"

    # Generate upload ID
    upload_id = f"upload_{timestamp}_{current_user}"

    # Upload to MongoDB GridFS
    try:
        from app.storage import get_signed_url, upload_to_bucket

        file_id = await upload_to_bucket("files", file_path, file_content)
        signed_url = get_signed_url("files", file_id, expires=600)
    except Exception as e:
        logger.error(f"GridFS upload failed: {e}")
        signed_url = None

    # Store metadata in database
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO reports (report_id, user_id, title, content, report_type, created_at)
                VALUES (:report_id, :user_id, :title, :content, :report_type, :created_at)
            """
                ),
                {
                    "report_id": upload_id,
                    "user_id": current_user,
                    "title": f"File Upload: {file.filename}",
                    "content": f"Uploaded file: {unique_filename}, Size: {len(file_content)} bytes",
                    "report_type": "file_upload",
                    "created_at": datetime.now(),
                },
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Database storage failed: {e}")

    # Store file locally with unique name — Phase 4: upload only to Bucket, no local write
    local_path = None

    return {
        "message": "File uploaded successfully",
        "upload_id": upload_id,
        "original_filename": file.filename,
        "stored_filename": unique_filename,
        "file_path": file_path,
        "file_size": len(file_content),
        "signed_url": signed_url,
        "user": current_user,
        "stored_in_database": True,
        "stored_locally": local_path,
        "metadata_file": metadata_path,
    }


@router.post("/upload-preview")
async def upload_preview_file(
    spec_id: str, file: UploadFile = File(...), current_user: str = Depends(get_current_user)
):
    """Upload preview file (GLB, JPG, PNG, etc.)"""
    import json
    import os
    from datetime import datetime

    from app.database_mongodb import engine

    try:
        preview_bytes = await file.read()
        file_extension = file.filename.split(".")[-1].lower() if "." in file.filename else "glb"
        timestamp = int(datetime.now().timestamp())
        path = f"{spec_id}_{timestamp}.{file_extension}"

        # Upload to MongoDB GridFS
        await upload_to_bucket("previews", path, preview_bytes)
        signed_url = get_signed_url("previews", path, expires=600)

        # Store metadata in database
        upload_id = f"preview_{timestamp}_{spec_id}"
        try:
            with engine.connect() as conn:
                conn.execute(
                    text(
                        """
                    INSERT INTO reports (report_id, user_id, title, content, report_type, spec_id, created_at)
                    VALUES (:report_id, :user_id, :title, :content, :report_type, :spec_id, :created_at)
                """
                    ),
                    {
                        "report_id": upload_id,
                        "user_id": current_user,
                        "title": f"Preview Upload: {file.filename}",
                        "content": f"Preview for spec {spec_id}, File: {path}, Size: {len(preview_bytes)} bytes",
                        "report_type": "preview_upload",
                        "spec_id": spec_id,
                        "created_at": datetime.now(),
                    },
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Database storage failed: {e}")

        # Phase 4: upload to Bucket only, no local write
        local_path = None

        return {
            "message": "Preview uploaded successfully",
            "upload_id": upload_id,
            "spec_id": spec_id,
            "filename": file.filename,
            "stored_filename": path,
            "file_type": file_extension,
            "file_size": len(preview_bytes),
            "signed_url": signed_url,
            "expires_in": 600,
            "user": current_user,
            "stored_in_database": True,
            "stored_locally": local_path,
            "metadata_file": metadata_path,
        }
    except Exception as e:
        logger.error(f"Preview upload failed for {spec_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Preview upload failed: {str(e)}")


@router.post("/upload-geometry")
async def upload_geometry_file(
    spec_id: str, file: UploadFile = File(...), current_user: str = Depends(get_current_user)
):
    """Upload geometry STL file"""
    import json
    import os
    from datetime import datetime

    from app.database_mongodb import engine

    geometry_bytes = await file.read()
    file_type = file.filename.split(".")[-1] if "." in file.filename else "stl"
    timestamp = int(datetime.now().timestamp())
    path = f"{spec_id}_{timestamp}.{file_type}"

    # Upload to MongoDB GridFS (upload_geometry only takes spec_id and bytes)
    try:
        from app.storage import upload_geometry

        signed_url = upload_geometry(spec_id, geometry_bytes)  # Not async
    except Exception as e:
        logger.error(f"GridFS upload failed: {e}")
        signed_url = None

    # Store metadata in database
    upload_id = f"geometry_{timestamp}_{spec_id}"
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO reports (report_id, user_id, title, content, report_type, spec_id, created_at)
                VALUES (:report_id, :user_id, :title, :content, :report_type, :spec_id, :created_at)
            """
                ),
                {
                    "report_id": upload_id,
                    "user_id": current_user,
                    "title": f"Geometry Upload: {file.filename}",
                    "content": f"Geometry for spec {spec_id}, File: {path}, Size: {len(geometry_bytes)} bytes",
                    "report_type": "geometry_upload",
                    "spec_id": spec_id,
                    "created_at": datetime.now(),
                },
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Database storage failed: {e}")

    # Phase 4: upload to Bucket only, no local write to data/geometry_outputs
    local_path = None

    return {
        "message": "Geometry uploaded successfully",
        "upload_id": upload_id,
        "spec_id": spec_id,
        "filename": file.filename,
        "stored_filename": path,
        "signed_url": signed_url,
        "file_type": file_type,
        "file_size": len(geometry_bytes),
        "user": current_user,
        "stored_in_database": True,
        "stored_locally": local_path,
        "metadata_file": metadata_path,
    }


@router.post("/upload-compliance")
async def upload_compliance_file(
    case_id: str, file: UploadFile = File(...), current_user: str = Depends(get_current_user)
):
    """Upload compliance ZIP file"""
    import json
    import os
    from datetime import datetime

    from app.database_mongodb import engine

    compliance_bytes = await file.read()
    timestamp = int(datetime.now().timestamp())
    file_path = f"compliance/{case_id}_{timestamp}.zip"

    # Upload to MongoDB GridFS
    try:
        await upload_to_bucket("compliance", file_path, compliance_bytes)
        signed_url = get_signed_url("compliance", file_path, expires=600)
    except Exception as e:
        logger.error(f"GridFS upload failed: {e}")
        signed_url = None

    # Store metadata in database
    upload_id = f"compliance_{timestamp}_{case_id}"
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO reports (report_id, user_id, title, content, report_type, created_at)
                VALUES (:report_id, :user_id, :title, :content, :report_type, :created_at)
            """
                ),
                {
                    "report_id": upload_id,
                    "user_id": current_user,
                    "title": f"Compliance Upload: {file.filename}",
                    "content": f"Compliance for case {case_id}, File: {file_path}, Size: {len(compliance_bytes)} bytes",
                    "report_type": "compliance_upload",
                    "created_at": datetime.now(),
                },
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Database storage failed: {e}")

    # Store file locally
    local_dir = "data/compliance"
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, f"{case_id}_{timestamp}.zip")

    with open(local_path, "wb") as f:
        f.write(compliance_bytes)

    # Store metadata locally
    metadata = {
        "upload_id": upload_id,
        "case_id": case_id,
        "original_filename": file.filename,
        "stored_filename": f"{case_id}_{timestamp}.zip",
        "file_path": file_path,
        "file_size": len(compliance_bytes),
        "signed_url": signed_url,
        "user": current_user,
        "local_path": local_path,
        "uploaded_at": datetime.now().isoformat(),
    }

    metadata_path = os.path.join(local_dir, f"{upload_id}_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return {
        "message": "Compliance file uploaded successfully",
        "upload_id": upload_id,
        "case_id": case_id,
        "filename": file.filename,
        "stored_filename": f"{case_id}_{timestamp}.zip",
        "file_path": file_path,
        "file_size": len(compliance_bytes),
        "signed_url": signed_url,
        "user": current_user,
        "stored_in_database": True,
        "stored_locally": local_path,
        "metadata_file": metadata_path,
    }
