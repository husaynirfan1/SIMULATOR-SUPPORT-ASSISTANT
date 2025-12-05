"""
Multi-turn conversation manager for OT Form filling
Handles progressive data collection and validation
"""

from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import ValidationError
import json
import re
from datetime import datetime


class OTConversationState(Enum):
    """States for OT form conversation flow"""
    INITIAL = "initial"
    AWAITING_EMPLOYEE_INFO = "awaiting_employee_info"
    AWAITING_OT_ENTRIES = "awaiting_ot_entries"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETE = "complete"


class OTConversationManager:
    """
    Manages multi-turn conversations for OT form collection
    Tracks state, collects data incrementally, validates input
    """

    def __init__(self):
        self.state = OTConversationState.INITIAL
        self.collected_data = {
            "employee_info": {},
            "ot_entries": []
        }
        self.current_entry = {}
        self.missing_fields = []

    def reset(self):
        """Reset conversation state"""
        self.state = OTConversationState.INITIAL
        self.collected_data = {"employee_info": {}, "ot_entries": []}
        self.current_entry = {}
        self.missing_fields = []

    def is_complete(self) -> bool:
        """Check if all required data has been collected"""
        return self.state == OTConversationState.COMPLETE

    def get_next_prompt(self) -> str:
        """Generate the next prompt based on current state"""
        if self.state == OTConversationState.INITIAL:
            return self._get_initial_prompt()
        elif self.state == OTConversationState.AWAITING_EMPLOYEE_INFO:
            return self._get_employee_info_prompt()
        elif self.state == OTConversationState.AWAITING_OT_ENTRIES:
            return self._get_ot_entries_prompt()
        elif self.state == OTConversationState.AWAITING_CONFIRMATION:
            return self._get_confirmation_prompt()
        return "Something went wrong. Please start over."

    def _get_initial_prompt(self) -> str:
        """Initial prompt asking for employee information"""
        return """I'll help you fill your Overtime (OT) form. Let's start by collecting your employee information.

Please provide the following details:

**Employee Information:**
1. Full Name
2. Designation (Job Title)
3. Department
4. Grade (e.g., E4, M1, etc.)
5. Month (1-12)
6. Year (e.g., 2025)
7. Signature (optional: file path to your signature image PNG/JPEG)

You can provide all at once or one by one. For example:
```
Name: John Doe
Designation: Engineer
Department: Technical
Grade: E4
Month: 12
Year: 2025
Signature: /path/to/signature.png
```

**Note:** If you don't have a digital signature, you can skip it for now."""

    def _get_employee_info_prompt(self) -> str:
        """Prompt for missing employee information fields"""
        if not self.missing_fields:
            return "I have all your employee information. Let's move on to OT entries."

        fields_text = "\n".join([f"- {field}" for field in self.missing_fields])
        current_data = "\n".join([f"- {k}: {v}" for k, v in self.collected_data["employee_info"].items()])

        return f"""I still need the following employee information:

{fields_text}

**Current data collected:**
{current_data if current_data else "(none yet)"}

Please provide the missing information."""

    def _get_ot_entries_prompt(self) -> str:
        """Prompt for OT entry information"""
        entries_count = len(self.collected_data["ot_entries"])

        if entries_count == 0:
            return """Great! Now let's add your overtime entries.

For each OT entry, I need:
1. **Date** (YYYY-MM-DD format, e.g., 2025-12-06)
2. **Start Time** (24-hour format HH:MM, e.g., 21:00)
3. **End Time** (24-hour format HH:MM, e.g., 09:00)
4. **Work Schedule** (choose one: Normal, Rest Day, or Public Holiday)
5. **Reason** (brief description of the OT work)

Example:
```
Date: 2025-12-06
Start: 21:00
End: 09:00
Schedule: Rest Day
Reason: System maintenance
```

Please provide your first OT entry."""
        else:
            return f"""You have {entries_count} OT entry(ies) recorded.

Would you like to:
1. Add another OT entry
2. Proceed to review and confirm

To add another entry, provide the details. To proceed, type "done" or "finish"."""

    def _get_confirmation_prompt(self) -> str:
        """Generate confirmation prompt with all collected data"""
        emp = self.collected_data["employee_info"]
        entries = self.collected_data["ot_entries"]

        # Format employee info
        emp_text = f"""**Employee Information:**
- Name: {emp.get('name', 'N/A')}
- Designation: {emp.get('designation', 'N/A')}
- Department: {emp.get('department', 'N/A')}
- Grade: {emp.get('grade', 'N/A')}
- Month: {emp.get('month', 'N/A')}
- Year: {emp.get('year', 'N/A')}"""

        # Format OT entries
        entries_text = "\n".join([
            f"""
**Entry {i+1}:**
- Date: {entry.get('date', 'N/A')}
- Time: {entry.get('start_time', 'N/A')} to {entry.get('end_time', 'N/A')}
- Schedule: {entry.get('work_schedule', 'N/A')}
- Reason: {entry.get('reason', 'N/A')}"""
            for i, entry in enumerate(entries)
        ])

        return f"""Please review your OT form details:

{emp_text}

**Overtime Entries ({len(entries)} total):**
{entries_text}

Is this information correct?
- Type "confirm" or "yes" to generate the form
- Type "edit" to make changes
- Specify what to change (e.g., "change name to Jane Doe")"""

    def process_user_input(self, user_message: str) -> Dict[str, Any]:
        """
        Process user input based on current conversation state

        Returns:
            Dict with:
                - status: 'continue' or 'complete'
                - message: Response message to user
                - ready_for_tool: Boolean indicating if ready to call fill_overtime_form
                - tool_data: JSON data for the tool (if ready)
        """
        user_message = user_message.strip()

        if self.state == OTConversationState.INITIAL:
            self.state = OTConversationState.AWAITING_EMPLOYEE_INFO
            return {
                "status": "continue",
                "message": self._get_initial_prompt(),
                "ready_for_tool": False
            }

        elif self.state == OTConversationState.AWAITING_EMPLOYEE_INFO:
            return self._process_employee_info(user_message)

        elif self.state == OTConversationState.AWAITING_OT_ENTRIES:
            return self._process_ot_entries(user_message)

        elif self.state == OTConversationState.AWAITING_CONFIRMATION:
            return self._process_confirmation(user_message)

        return {
            "status": "error",
            "message": "Invalid conversation state. Please start over.",
            "ready_for_tool": False
        }

    def _process_employee_info(self, user_message: str) -> Dict[str, Any]:
        """Extract and validate employee information from user message"""
        # Extract fields using regex patterns
        extracted = self._extract_employee_fields(user_message)

        # Merge with existing data
        self.collected_data["employee_info"].update(extracted)

        # Check what's still missing
        required_fields = ["name", "designation", "department", "grade", "month", "year"]
        self.missing_fields = [
            field for field in required_fields
            if field not in self.collected_data["employee_info"] or not self.collected_data["employee_info"][field]
        ]

        if self.missing_fields:
            # Still missing fields
            return {
                "status": "continue",
                "message": self._get_employee_info_prompt(),
                "ready_for_tool": False
            }
        else:
            # All employee info collected, move to OT entries
            # Validate the data
            validation_result = self._validate_employee_info()
            if not validation_result["valid"]:
                return {
                    "status": "continue",
                    "message": f"There's an issue with the data:\n\n{validation_result['error']}\n\nPlease provide the correct information.",
                    "ready_for_tool": False
                }

            self.state = OTConversationState.AWAITING_OT_ENTRIES
            return {
                "status": "continue",
                "message": self._get_ot_entries_prompt(),
                "ready_for_tool": False
            }

    def _process_ot_entries(self, user_message: str) -> Dict[str, Any]:
        """Extract and validate OT entry from user message"""
        user_lower = user_message.lower().strip()

        # Check if user wants to finish
        if any(word in user_lower for word in ["done", "finish", "complete", "no more", "that's all", "proceed", "review"]):
            if len(self.collected_data["ot_entries"]) == 0:
                return {
                    "status": "continue",
                    "message": "You haven't added any OT entries yet. Please add at least one entry.",
                    "ready_for_tool": False
                }

            self.state = OTConversationState.AWAITING_CONFIRMATION
            return {
                "status": "continue",
                "message": self._get_confirmation_prompt(),
                "ready_for_tool": False
            }

        # Extract OT entry fields
        entry = self._extract_ot_entry_fields(user_message)

        if not entry:
            return {
                "status": "continue",
                "message": "I couldn't extract the OT entry details. Please provide the information in this format:\n\n" + self._get_ot_entries_prompt(),
                "ready_for_tool": False
            }

        # Validate entry
        validation_result = self._validate_ot_entry(entry)
        if not validation_result["valid"]:
            return {
                "status": "continue",
                "message": f"There's an issue with the OT entry:\n\n{validation_result['error']}\n\nPlease provide the correct information.",
                "ready_for_tool": False
            }

        # Add to entries list
        self.collected_data["ot_entries"].append(entry)

        # Ask if they want to add more
        return {
            "status": "continue",
            "message": self._get_ot_entries_prompt(),
            "ready_for_tool": False
        }

    def _process_confirmation(self, user_message: str) -> Dict[str, Any]:
        """Process user's confirmation response"""
        user_lower = user_message.lower().strip()

        if any(word in user_lower for word in ["confirm", "yes", "correct", "looks good", "approve"]):
            # User confirmed - prepare tool data
            self.state = OTConversationState.COMPLETE

            tool_data = json.dumps(self.collected_data)

            return {
                "status": "complete",
                "message": "Great! Generating your OT form now...",
                "ready_for_tool": True,
                "tool_data": tool_data
            }

        elif "edit" in user_lower or "change" in user_lower or "fix" in user_lower:
            # User wants to make changes
            # Try to extract what they want to change
            # For simplicity, let them restart from the field they want to change
            return {
                "status": "continue",
                "message": "What would you like to change? Please specify:\n- 'employee info' to update employee details\n- 'entries' to modify OT entries\n\nOr provide the specific change (e.g., 'change name to Jane Doe')",
                "ready_for_tool": False
            }

        else:
            return {
                "status": "continue",
                "message": "Please respond with 'confirm' to proceed, or 'edit' to make changes.",
                "ready_for_tool": False
            }

    def _extract_employee_fields(self, text: str) -> Dict[str, Any]:
        """Extract employee information fields from text using regex"""
        extracted = {}

        # Name patterns
        name_match = re.search(r'(?:name|employee)(?:\s*[:\-]\s*|\s+is\s+)([A-Za-z\s]+?)(?:\n|,|$)', text, re.IGNORECASE)
        if name_match:
            extracted["name"] = name_match.group(1).strip()

        # Designation patterns
        desig_match = re.search(r'(?:designation|title|position|role)(?:\s*[:\-]\s*|\s+is\s+)([A-Za-z\s]+?)(?:\n|,|$)', text, re.IGNORECASE)
        if desig_match:
            extracted["designation"] = desig_match.group(1).strip()

        # Department patterns
        dept_match = re.search(r'(?:department|dept)(?:\s*[:\-]\s*|\s+is\s+)([A-Za-z\s]+?)(?:\n|,|$)', text, re.IGNORECASE)
        if dept_match:
            extracted["department"] = dept_match.group(1).strip()

        # Grade patterns
        grade_match = re.search(r'(?:grade)(?:\s*[:\-]\s*|\s+is\s+)([A-Z]\d+)', text, re.IGNORECASE)
        if grade_match:
            extracted["grade"] = grade_match.group(1).upper()

        # Month patterns
        month_match = re.search(r'(?:month)(?:\s*[:\-]\s*|\s+is\s+)(\d{1,2})', text, re.IGNORECASE)
        if month_match:
            extracted["month"] = int(month_match.group(1))

        # Year patterns
        year_match = re.search(r'(?:year)(?:\s*[:\-]\s*|\s+is\s+)(\d{4})', text, re.IGNORECASE)
        if year_match:
            extracted["year"] = int(year_match.group(1))

        # Signature path patterns (optional)
        sig_match = re.search(r'(?:signature|sign)(?:\s*[:\-]\s*|\s+is\s+)([^\n,]+?)(?:\n|,|$)', text, re.IGNORECASE)
        if sig_match:
            sig_path = sig_match.group(1).strip()
            # Only store if it looks like a file path
            if sig_path and (sig_path.endswith(('.png', '.jpg', '.jpeg')) or '/' in sig_path):
                extracted["signature_path"] = sig_path

        return extracted

    def _extract_ot_entry_fields(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract OT entry fields from text"""
        entry = {}

        # Date patterns (YYYY-MM-DD)
        date_match = re.search(r'(?:date)(?:\s*[:\-]\s*|\s+is\s+)?(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
        if date_match:
            entry["date"] = date_match.group(1)

        # Start time patterns (HH:MM)
        start_match = re.search(r'(?:start|from)(?:\s*(?:time)?[:\-]\s*|\s+is\s+)?(\d{1,2}:\d{2})', text, re.IGNORECASE)
        if start_match:
            entry["start_time"] = start_match.group(1)

        # End time patterns (HH:MM)
        end_match = re.search(r'(?:end|to|until)(?:\s*(?:time)?[:\-]\s*|\s+is\s+)?(\d{1,2}:\d{2})', text, re.IGNORECASE)
        if end_match:
            entry["end_time"] = end_match.group(1)

        # Work schedule patterns
        schedule_match = re.search(r'(?:schedule|type)(?:\s*[:\-]\s*|\s+is\s+)?(Normal|Rest Day|Public Holiday)', text, re.IGNORECASE)
        if schedule_match:
            # Normalize case
            schedule = schedule_match.group(1)
            if "rest" in schedule.lower():
                entry["work_schedule"] = "Rest Day"
            elif "public" in schedule.lower() or "holiday" in schedule.lower():
                entry["work_schedule"] = "Public Holiday"
            else:
                entry["work_schedule"] = "Normal"

        # Reason patterns
        reason_match = re.search(r'(?:reason|description|purpose)(?:\s*[:\-]\s*|\s+is\s+)([^\n]+)', text, re.IGNORECASE)
        if reason_match:
            entry["reason"] = reason_match.group(1).strip()

        # Return None if we didn't extract enough fields
        if len(entry) < 3:  # At minimum need date, time, and reason
            return None

        return entry

    def _validate_employee_info(self) -> Dict[str, Any]:
        """Validate employee information using Pydantic model"""
        try:
            from ot_apps.ot_form_models import EmployeeInfo

            emp_info = EmployeeInfo(**self.collected_data["employee_info"])
            return {"valid": True}
        except ValidationError as e:
            errors = []
            for err in e.errors():
                field = err["loc"][0]
                msg = err["msg"]
                errors.append(f"- {field}: {msg}")
            return {
                "valid": False,
                "error": "\n".join(errors)
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

    def _validate_ot_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a single OT entry using Pydantic model"""
        try:
            from ot_apps.ot_form_models import OTEntry

            ot_entry = OTEntry(**entry)
            return {"valid": True}
        except ValidationError as e:
            errors = []
            for err in e.errors():
                field = err["loc"][0]
                msg = err["msg"]
                errors.append(f"- {field}: {msg}")
            return {
                "valid": False,
                "error": "\n".join(errors)
            }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

    def get_state_dict(self) -> Dict[str, Any]:
        """Export conversation state for persistence"""
        return {
            "state": self.state.value,
            "collected_data": self.collected_data,
            "current_entry": self.current_entry,
            "missing_fields": self.missing_fields
        }

    def load_state_dict(self, state_dict: Dict[str, Any]):
        """Load conversation state from dictionary"""
        self.state = OTConversationState(state_dict.get("state", "initial"))
        self.collected_data = state_dict.get("collected_data", {"employee_info": {}, "ot_entries": []})
        self.current_entry = state_dict.get("current_entry", {})
        self.missing_fields = state_dict.get("missing_fields", [])
