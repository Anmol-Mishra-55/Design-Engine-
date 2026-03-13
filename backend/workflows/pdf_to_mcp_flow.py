"""
PDF to MCP Flow - COMPLETE & FIXED
Automatically extract compliance rules from uploaded PDFs
"""
import json
import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Dict, List

import httpx
import PyPDF2
from prefect import flow, get_run_logger, task
from prefect.tasks import task_input_hash


@task(
    name="download_pdf",
    retries=3,
    retry_delay_seconds=5,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1),
)
def download_pdf_from_storage(pdf_url: str, local_path: str) -> str:
    """Download PDF from MongoDB GridFS or external URL"""
    logger = get_run_logger()
    logger.info(f"Downloading PDF from {pdf_url}")

    response = httpx.get(pdf_url, timeout=30.0)
    response.raise_for_status()

    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(response.content)

    logger.info(f"PDF downloaded: {len(response.content)} bytes")
    return local_path


@task(name="extract_text_from_pdf", retries=2)
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from PDF"""
    logger = get_run_logger()
    logger.info(f"Extracting text from {pdf_path}")

    text_content = []

    with open(pdf_path, "rb") as f:
        pdf_reader = PyPDF2.PdfReader(f)
        num_pages = len(pdf_reader.pages)

        logger.info(f"PDF has {num_pages} pages")

        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            text_content.append(text)

    full_text = "\n\n".join(text_content)
    logger.info(f"Extracted {len(full_text)} characters")

    return full_text


@task(name="parse_compliance_rules", retries=1)
def parse_compliance_rules(text_content: str, city: str) -> Dict:
    """Parse compliance rules from text using regex patterns"""
    logger = get_run_logger()
    logger.info(f"Parsing compliance rules for {city}")

    rules = {"city": city, "rules": [], "sections": []}

    # FSI Rules - FIXED
    fsi_pattern = r"FSI[:\s]+(\d+\.?\d*)"
    fsi_matches = re.findall(fsi_pattern, text_content, re.IGNORECASE)
    for fsi_value in fsi_matches:  # FIXED: Loop through matches
        rules["rules"].append(
            {"type": "fsi", "value": float(fsi_value), "description": f"Floor Space Index (FSI) regulation"}
        )
        logger.info(f"Found FSI rule: {fsi_value}")

    # Setback Rules
    setback_pattern = r"setback[:\s]+(\d+\.?\d*)\s*(m|meter|metre|feet|ft)"
    setback_matches = re.findall(setback_pattern, text_content, re.IGNORECASE)
    for match in setback_matches:
        value, unit = match
        rules["rules"].append(
            {"type": "setback", "value": float(value), "unit": unit, "description": f"Minimum setback requirement"}
        )
        logger.info(f"Found setback rule: {value} {unit}")

    # Height Restrictions
    height_pattern = r"maximum height[:\s]+(\d+\.?\d*)\s*(m|meter|metre|feet|ft)"
    height_matches = re.findall(height_pattern, text_content, re.IGNORECASE)
    for match in height_matches:
        value, unit = match
        rules["rules"].append(
            {"type": "height", "value": float(value), "unit": unit, "description": f"Maximum building height"}
        )
        logger.info(f"Found height rule: {value} {unit}")

    # Parking Requirements
    parking_pattern = r"parking[:\s]+(\d+)\s*(?:space|slot|car).*per.*(\d+)\s*(?:sq.*ft|sqft|m2)"
    parking_matches = re.findall(parking_pattern, text_content, re.IGNORECASE)
    for match in parking_matches:
        spaces, area = match
        rules["rules"].append(
            {"type": "parking", "spaces_per_area": f"{spaces} per {area}", "description": f"Parking space requirements"}
        )
        logger.info(f"Found parking rule: {spaces} per {area}")

    # Extract section headings
    section_pattern = r"^([A-Z][A-Z\s]+)$"
    sections = re.findall(section_pattern, text_content, re.MULTILINE)
    rules["sections"] = sections[:20]  # First 20 sections

    logger.info(f"Parsed {len(rules['rules'])} rules, {len(sections)} sections")

    return rules


@task(name="send_to_mcp", retries=3, retry_delay_seconds=10)
async def send_rules_to_mcp(rules: Dict, sohum_url: str) -> bool:
    """Send parsed rules to Sohum's MCP system"""
    logger = get_run_logger()
    logger.info(f"Sending {len(rules['rules'])} rules to MCP")

    try:  # FIXED: Added error handling
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{sohum_url}/rules/ingest", json=rules, headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"MCP ingestion successful: {result}")

            return True
    except Exception as e:
        logger.error(f"MCP ingestion failed: {e}")
        return False


@task(name="cleanup_temp_files")
def cleanup_temp_files(file_path: str):
    """Remove temporary files"""
    logger = get_run_logger()

    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Cleaned up {file_path}")


@flow(
    name="pdf-to-mcp-ingestion",
    description="Extract compliance rules from PDFs and send to MCP",
    retries=1,
    retry_delay_seconds=60,
)
async def pdf_to_mcp_flow(pdf_url: str, city: str, sohum_mcp_url: str) -> Dict:
    """Complete PDF to MCP ingestion flow"""
    logger = get_run_logger()
    logger.info(f"Starting PDF to MCP flow for {city}")

    # Download PDF - FIXED: Windows compatible path
    local_path = f"temp/{city}_compliance.pdf"
    pdf_path = download_pdf_from_storage(pdf_url, local_path)

    # Extract text
    text_content = extract_text_from_pdf(pdf_path)

    # Parse rules
    rules = parse_compliance_rules(text_content, city)

    # Send to MCP
    success = await send_rules_to_mcp(rules, sohum_mcp_url)

    # Cleanup
    cleanup_temp_files(pdf_path)

    result = {
        "city": city,
        "rules_count": len(rules["rules"]),
        "sections_count": len(rules["sections"]),
        "success": success,
    }

    logger.info(f"PDF to MCP flow completed: {result}")
    return result


# Test function
async def test_pdf_workflow():
    """Test the PDF workflow"""
    result = await pdf_to_mcp_flow(
        pdf_url="https://example.com/test.pdf", city="Mumbai", sohum_mcp_url="http://localhost:8001"
    )
    print(f"Test result: {result}")
    return result


if __name__ == "__main__":
    try:
        from prefect.deployments import Deployment

        deployment = Deployment.build_from_flow(
            flow=pdf_to_mcp_flow,
            name="pdf-to-mcp-production",
            version="1.0.0",
            work_queue_name="default",
            tags=["compliance", "pdf", "mcp"],
            description="Automated PDF compliance rule extraction",
            parameters={"city": "Mumbai", "sohum_mcp_url": os.getenv("SOHUM_MCP_URL", "http://localhost:8001")},
        )

        deployment.apply()
        print("PDF to MCP flow deployed")

    except Exception as e:
        print(f"PDF to MCP flow ready: {e}")
