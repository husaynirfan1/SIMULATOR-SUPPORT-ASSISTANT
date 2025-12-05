# OT Form Multi-Turn Conversation Implementation Guide

## Overview

The OT Form tool has been upgraded to support **multi-turn conversations**, allowing users to fill overtime forms through a natural, progressive dialogue rather than requiring all data upfront.

## Key Features

✅ **Progressive Data Collection**: Collects employee info and OT entries step-by-step
✅ **Smart Field Extraction**: Uses regex to parse structured and natural language inputs
✅ **Validation**: Validates data using Pydantic models at each step
✅ **State Persistence**: Maintains conversation state across multiple queries
✅ **Error Handling**: Provides clear feedback for missing or invalid data
✅ **Flexible Input**: Accepts various input formats (structured lists, natural language)

---

## Architecture

### Components

1. **`OTConversationManager`** ([ot_conversation_manager.py](ot_conversation_manager.py))
   - Manages conversation state machine
   - Extracts and validates data incrementally
   - Generates contextual prompts

2. **`AgentState`** (Updated in [graph.py](graph.py))
   - Added `ot_conversation_state`: Persists conversation data
   - Added `ot_conversation_active`: Tracks if OT conversation is ongoing

3. **`_check_tools_node`** (Updated in [graph.py](graph.py))
   - Detects OT form requests
   - Routes to multi-turn handler
   - Only calls `fill_overtime_form` tool when data is complete

---

## Conversation Flow

### State Machine

```
INITIAL
  ↓
AWAITING_EMPLOYEE_INFO
  ↓
AWAITING_OT_ENTRIES (can repeat)
  ↓
AWAITING_CONFIRMATION
  ↓
COMPLETE → Call fill_overtime_form tool
```

### Typical User Journey

**Turn 1**: User requests OT form
```
User: "I want to fill my overtime form"
System: "I'll help you fill your OT form. Please provide employee information..."
```

**Turn 2**: User provides employee details
```
User: "Name: John Doe
       Designation: Engineer
       Department: Technical
       Grade: E4
       Month: 12
       Year: 2025"
System: "Great! Now let's add your overtime entries..."
```

**Turn 3**: User adds first OT entry
```
User: "Date: 2025-12-06
       Start: 18:00
       End: 22:00
       Schedule: Normal
       Reason: Project work"
System: "You have 1 OT entry. Add another or type 'done' to proceed."
```

**Turn 4**: User adds more entries or finishes
```
User: "done"
System: "Please review your OT form details: [shows all data]
        Type 'confirm' to proceed or 'edit' to make changes."
```

**Turn 5**: User confirms
```
User: "confirm"
System: "Great! Generating your OT form now..."
[Tool is called with collected data]
```

---

## Implementation Details

### Data Extraction

The system uses regex patterns to extract fields from user messages:

**Employee Info Fields:**
- `name`: "Name: John Doe" or "Name is John Doe"
- `designation`: "Designation: Engineer"
- `department`: "Department: Technical"
- `grade`: "Grade: E4" (extracts format like E4, M1, etc.)
- `month`: "Month: 12" (1-12)
- `year`: "Year: 2025"

**OT Entry Fields:**
- `date`: "Date: 2025-12-06" (YYYY-MM-DD format)
- `start_time`: "Start: 18:00" or "From: 18:00"
- `end_time`: "End: 22:00" or "To: 22:00"
- `work_schedule`: "Schedule: Normal" (Normal, Rest Day, or Public Holiday)
- `reason`: "Reason: Project work"

### Validation

Uses Pydantic models from [ot_apps/ot_form_models.py](ot_apps/ot_form_models.py):

- **Date Format**: Must be YYYY-MM-DD
- **Time Format**: Must be HH:MM (24-hour)
- **Work Schedule**: Must be one of: Normal, Rest Day, Public Holiday
- **Month**: Must be 1-12
- **Year**: Must be 2020-2100

---

## Frontend Integration

### WebSocket Communication

The frontend ([chatbotui/index.html](../frontend/chatbotui/index.html)) connects via WebSocket to `ws://localhost:8082/ws/query`.

**Request Format:**
```json
{
  "query": "I want to fill my OT form",
  "previous_state": {
    "ot_conversation_state": {...},
    "ot_conversation_active": true
  }
}
```

**Response Format:**
```json
{
  "final_answer": "Please provide employee information...",
  "ot_conversation_active": true,
  "ot_conversation_state": {...}
}
```

### State Persistence

The frontend/backend **MUST** persist the conversation state across turns:

1. **Backend** returns `ot_conversation_state` and `ot_conversation_active`
2. **Frontend** stores this state (in memory or session storage)
3. **Frontend** sends it back with the next query as `previous_state`

---

## Usage Examples

### Example 1: Structured Input

```
User: "Fill OT form"

System: "I'll help you fill your OT form. Please provide..."

User: "Name: Jane Smith
       Designation: Senior Engineer
       Department: Engineering
       Grade: E5
       Month: 11
       Year: 2025"

System: "Great! Now let's add your overtime entries..."

User: "Date: 2025-11-15
       Start: 21:00
       End: 09:00
       Schedule: Rest Day
       Reason: Emergency maintenance"

System: "You have 1 OT entry. Add another or type 'done'."

User: "done"

System: [Shows review]

User: "confirm"

System: "Overtime form created successfully! Download: http://..."
```

### Example 2: Natural Language Input

```
User: "I need to submit my overtime form for December 2025"

System: "I'll help you. Please provide your employee information..."

User: "My name is Ahmad bin Ali, I'm a Maintenance Engineer in the Technical department, grade M2"

System: [Extracts: name, designation, department, grade]
        "I still need: Month and Year"

User: "Month 12, year 2025"

System: "Great! Now let's add your overtime entries..."
```

### Example 3: Partial Information Handling

```
User: "Create OT form"

System: "Please provide employee information..."

User: "Name: Bob Lee
       Grade: E3"

System: "I still need the following:
        - Designation
        - Department
        - Month
        - Year"

User: "I'm a Technician in Maintenance, month 12, year 2025"

System: [Extracts all remaining fields]
        "Great! Now let's add your overtime entries..."
```

---

## Testing

### Unit Tests

Run the test script:
```bash
cd multi_agent_system
conda activate sse-ai
python test_ot_multiturn.py
```

Test scenarios covered:
- ✅ Complete flow from request to tool call
- ✅ Partial information handling
- ✅ Validation error handling
- ✅ Multiple OT entries
- ✅ State persistence

### Manual Testing via API

1. Start the backend server
2. Use WebSocket client or frontend UI
3. Test conversation flow manually

---

## Configuration

### Keywords for Detection

OT form requests are detected by these keywords in [graph.py](graph.py#L296):
```python
ot_form_keywords = ["overtime", "ot form", "fill form", "create form", "ot sheet", "overtime form"]
```

To add more keywords, edit this list.

### Conversation Prompts

All prompts are in [ot_conversation_manager.py](ot_conversation_manager.py):
- `_get_initial_prompt()`: First message when OT form is requested
- `_get_employee_info_prompt()`: Asks for missing employee fields
- `_get_ot_entries_prompt()`: Asks for OT entry details
- `_get_confirmation_prompt()`: Shows review and asks for confirmation

---

## Troubleshooting

### Issue: Conversation State Not Persisting

**Symptom**: System asks for employee info again on every turn

**Solution**: Ensure the frontend/WebSocket handler passes `previous_state` with each query:
```python
result = system.query(
    question=user_message,
    previous_state={
        "ot_conversation_state": previous_result.get("ot_conversation_state"),
        "ot_conversation_active": previous_result.get("ot_conversation_active")
    }
)
```

### Issue: Data Not Being Extracted

**Symptom**: System says it can't find fields even when user provides them

**Solution**:
1. Check input format matches regex patterns in `_extract_employee_fields()` and `_extract_ot_entry_fields()`
2. Test regex patterns individually
3. Add debug logging to see what's being extracted

### Issue: Validation Errors

**Symptom**: System rejects valid data

**Solution**:
1. Check Pydantic models in [ot_apps/ot_form_models.py](ot_apps/ot_form_models.py)
2. Ensure date format is YYYY-MM-DD
3. Ensure time format is HH:MM (24-hour)
4. Ensure work_schedule is exactly "Normal", "Rest Day", or "Public Holiday"

---

## API Reference

### OTConversationManager

#### Methods

**`process_user_input(user_message: str) -> Dict[str, Any]`**
- Processes user input and advances conversation state
- Returns:
  - `status`: 'continue' or 'complete'
  - `message`: Response message to user
  - `ready_for_tool`: Boolean indicating if ready to call tool
  - `tool_data`: JSON data for tool (if ready)

**`get_state_dict() -> Dict[str, Any]`**
- Exports conversation state for persistence
- Returns state dictionary

**`load_state_dict(state_dict: Dict[str, Any])`**
- Loads conversation state from dictionary
- Used to restore conversation after page reload

**`reset()`**
- Resets conversation to initial state
- Clears all collected data

### MultiAgentSystem

#### Updated Signature

**`query(question: str, previous_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]`**
- `question`: User query
- `previous_state`: Optional dict with `ot_conversation_state` and `ot_conversation_active`
- Returns result dict with conversation state fields

---

## Future Enhancements

Potential improvements:

1. **Natural Language Understanding**: Use LLM to extract fields instead of regex
2. **Multi-Language Support**: Support Malay, Chinese, etc.
3. **Voice Input**: Accept voice commands and convert to text
4. **Smart Suggestions**: Suggest recent OT reasons, common time slots
5. **Batch Entry**: "I worked OT from Dec 1-5, same hours" → creates 5 entries
6. **Edit Specific Fields**: "Change my name to John" without restarting
7. **Export Formats**: Support PDF, CSV in addition to Excel
8. **Template Selection**: Different OT form templates for different departments

---

## Summary

The OT Form tool now provides a **user-friendly, conversational interface** for filling overtime forms. Key benefits:

✅ **No need to gather all data upfront** - users can provide info step-by-step
✅ **Flexible input formats** - structured lists or natural language
✅ **Clear guidance** - system tells users exactly what's needed
✅ **Validation at each step** - catches errors early
✅ **Resumable conversations** - state persists across page reloads (if implemented)

The implementation seamlessly integrates with the existing multi-agent system architecture and frontend UI.
