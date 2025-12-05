# Multi-Agent System with Morphik Folder Scoping

A sophisticated multi-agent system using LangGraph where each agent has specialized knowledge stored in isolated Morphik folders.

## Architecture

### Agents
1. **Planning Agent** - Orchestrates workflow, determines which specialists to consult
2. **Interface Specialist** - Expertise in user interfaces, HMI, controls
3. **Motion Specialist** - Knowledge of motion systems, actuators, kinematics
4. **Vibration Specialist** - Vibration analysis, damping, frequency response
5. **Visual Specialist** - Visual systems, displays, graphics, projections
6. **Computer Specialist** - Computing hardware, software, networking
7. **Red Team Agent** - Security, vulnerabilities, attack vectors
8. **DR Agent** - Deficiency tracking, issue management
9. **Inventory Agent** - Parts, components, stock management
10. **Synthesizer Agent** - Combines insights from multiple agents

### Folder Isolation
Each agent has its own Morphik folder for isolated knowledge:
- `planning_kb/` - Planning knowledge
- `interface_kb/` - Interface knowledge
- `motion_kb/` - Motion systems knowledge
- `vibration_kb/` - Vibration knowledge
- `visual_kb/` - Visual systems knowledge
- `computer_kb/` - Computing knowledge
- `redteam_kb/` - Security knowledge
- `dr_kb/` - Deficiency tracking
- `inventory_kb/` - Inventory management
- `synthesis_kb/` - Synthesis knowledge

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file:
```env
MORPHIK_URI=http://localhost:8000
```

### 3. Initialize Folders
Run the setup script to create Morphik folders:
```bash
python setup_folders.py
```

### 4. Add Documents (Optional)
Edit `add_documents.py` to specify document paths for each agent, then run:
```bash
python add_documents.py
```

## Usage

### Demo Mode
Run with example queries:
```bash
python main.py
```

### Interactive Mode
Run in interactive mode:
```bash
python main.py --interactive
```

### API Server Mode
Run as a FastAPI server:
```bash
./start_server.sh
# or
python server.py
```

The API will be available at:
- **Base URL**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health

#### API Endpoints

**POST /query** - Query the multi-agent system
```bash
curl -X POST "http://localhost:8001/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the vibration control procedures?"}'
```

**GET /agents** - List all available agents
```bash
curl "http://localhost:8001/agents"
```

**POST /query/{agent_name}** - Query a specific agent
```bash
curl -X POST "http://localhost:8001/query/interface" \
  -H "Content-Type: application/json" \
  -d '{"query": "How to design a touch interface?"}'
```

### Programmatic Usage
```python
from graph import MultiAgentSystem

# Initialize system
system = MultiAgentSystem("http://localhost:8000")

# Query the system
result = system.query("What are the vibration control procedures?")

print(result['final_answer'])
```

## How It Works

1. **Planning**: User query is analyzed by the Planning Agent to determine which specialists to consult
2. **Consultation**: Selected specialist agents query their isolated knowledge bases using Morphik RAG
3. **Synthesis**: Synthesizer Agent combines insights from all consulted specialists into a coherent answer

## Features

- ✅ **Folder-based Knowledge Isolation**: Each agent only accesses its designated Morphik folder
- ✅ **LangGraph Orchestration**: Structured workflow with clear phases
- ✅ **RAG-Enabled Agents**: Each specialist uses Morphik's retrieval-augmented generation
- ✅ **Scalable Architecture**: Easy to add new specialist agents
- ✅ **Intelligent Routing**: Planning agent determines optimal specialist consultation

## File Structure

```
multi_agent_system/
├── agents.py           # Agent class definitions
├── graph.py            # LangGraph workflow
├── main.py             # Main entry point
├── setup_folders.py    # Folder initialization
├── add_documents.py    # Document upload helper
├── requirements.txt    # Dependencies
└── README.md           # This file
```
