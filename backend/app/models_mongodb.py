"""
MongoDB Document Models
Pydantic schemas for MongoDB collections
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """User document"""

    id: str = Field(alias="_id")
    username: str
    email: str
    password_hash: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    class Config:
        populate_by_name = True


class RefreshToken(BaseModel):
    """Refresh token document"""

    id: str = Field(alias="_id")
    token: str
    user_id: str
    expires_at: datetime
    is_revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class Spec(BaseModel):
    """Design specification document"""

    id: str = Field(alias="_id")
    user_id: str
    title: str
    description: Optional[str] = None
    city: str
    spec_data: dict
    geometry_url: Optional[str] = None
    preview_url: Optional[str] = None
    status: str = "draft"  # draft, generated, completed
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class Iteration(BaseModel):
    """Design iteration document"""

    id: str = Field(alias="_id")
    spec_id: str
    user_id: str
    iteration_number: int
    changes: dict
    geometry_url: Optional[str] = None
    preview_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class Evaluation(BaseModel):
    """Design evaluation document"""

    id: str = Field(alias="_id")
    spec_id: str
    user_id: str
    score: float
    feedback: str
    metrics: dict
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class RLFeedback(BaseModel):
    """RL feedback document"""

    id: str = Field(alias="_id")
    spec_id: str
    user_id: str
    feedback_type: str  # positive, negative, neutral
    feedback_data: dict
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class AuditLog(BaseModel):
    """Audit log document"""

    id: str = Field(alias="_id")
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    changes: dict
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class ComplianceCheck(BaseModel):
    """Compliance check document"""

    id: str = Field(alias="_id")
    spec_id: str
    city: str
    rules_applied: List[str]
    violations: List[dict]
    status: str  # passed, failed, warning
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


class WorkflowRun(BaseModel):
    """Workflow run document"""

    id: str = Field(alias="_id")
    user_id: str
    workflow_name: str
    status: str  # pending, running, completed, failed
    input_data: dict
    output_data: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


__all__ = [
    "User",
    "RefreshToken",
    "Spec",
    "Iteration",
    "Evaluation",
    "RLFeedback",
    "AuditLog",
    "ComplianceCheck",
    "WorkflowRun",
]
