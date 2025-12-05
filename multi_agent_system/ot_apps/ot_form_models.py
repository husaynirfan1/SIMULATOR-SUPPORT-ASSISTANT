"""
Pydantic models for Overtime Form data validation
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime, time as time_type
import re


class OTEntry(BaseModel):
    """Single overtime entry"""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    start_time: str = Field(..., description="Start time in HH:MM format (24-hour)")
    end_time: str = Field(..., description="End time in HH:MM format (24-hour)")
    work_schedule: str = Field(..., description="Must be one of: Normal, Rest Day, Public Holiday")
    reason: str = Field(..., description="Reason for overtime")
    
    @validator('date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format')
    
    @validator('start_time', 'end_time')
    def validate_time(cls, v):
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', v):
            raise ValueError('Time must be in HH:MM format (24-hour)')
        return v
    
    @validator('work_schedule')
    def validate_work_schedule(cls, v):
        valid_schedules = ['Normal', 'Rest Day', 'Public Holiday']
        if v not in valid_schedules:
            raise ValueError(f'Work schedule must be one of: {", ".join(valid_schedules)}')
        return v


class EmployeeInfo(BaseModel):
    """Employee information for OT form"""
    name: str = Field(..., description="Full employee name")
    designation: str = Field(..., description="Job designation/title")
    department: str = Field(..., description="Department name")
    grade: str = Field(..., description="Employee grade (e.g., E4, M1)")
    month: int = Field(..., ge=1, le=12, description="Month number (1-12)")
    year: int = Field(..., ge=2020, le=2100, description="Year")
    signature_path: Optional[str] = Field(None, description="Path to signature image file (PNG/JPEG)")


class OTFormRequest(BaseModel):
    """Complete OT form request"""
    employee_info: EmployeeInfo
    ot_entries: List[OTEntry] = Field(..., min_items=1, description="List of overtime entries")
    
    class Config:
        json_schema_extra = {
            "example": {
                "employee_info": {
                    "name": "Muhammad Husayn Irfan bin Mohammad Noor",
                    "designation": "Simulator Support Engineer",
                    "department": "Technical",
                    "grade": "E4",
                    "month": 11,
                    "year": 2025
                },
                "ot_entries": [
                    {
                        "date": "2025-11-06",
                        "start_time": "21:00",
                        "end_time": "09:00",
                        "work_schedule": "Rest Day",
                        "reason": "Replace Luqman"
                    }
                ]
            }
        }
