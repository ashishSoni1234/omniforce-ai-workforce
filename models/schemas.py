from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class AgentType(str, Enum):
    SALES = "sales"
    OPS = "ops"
    KYC = "kyc"


class TaskRequest(BaseModel):
    agent: AgentType
    instruction: str
    context: Optional[dict] = {}


class LeadRecord(BaseModel):
    company_name: str
    industry: str
    revenue_range: str
    location: str
    contact_email: Optional[str] = None
    status: str = "new"


class DocumentData(BaseModel):
    doc_type: str  # invoice, timesheet, contract
    content: str
    metadata: Optional[dict] = {}


class KYCData(BaseModel):
    client_name: str
    email: str
    documents: List[str]
    risk_level: Optional[str] = None


class AgentState(BaseModel):
    task: str
    agent_type: str
    result: Optional[str] = None
    status: str = "pending"
    error: Optional[str] = None
    metadata: Optional[dict] = {}
