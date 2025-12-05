"""
Base class for all specialist agents with Morphik RAG integration
"""

import os
from typing import Dict, List, Optional, Any
from morphik import Morphik
from morphik.models import QueryPromptOverride, QueryPromptOverrides
from dotenv import load_dotenv

load_dotenv()


class BaseAgent:
    """Base class for all specialist agents with Morphik RAG integration"""
    
    def __init__(self, name: str, folder_name: str, morphik_uri: str, system_prompt: Optional[str] = None):
        """
        Initialize agent with scoped Morphik folder
        
        Args:
            name: Agent name
            folder_name: Morphik folder for isolated knowledge
            morphik_uri: Morphik server URI
            system_prompt: Custom system prompt defining agent's role and expertise
        """
        self.name = name
        self.folder_name = folder_name
        self.system_prompt = system_prompt or f"You are {name}, an expert assistant."
        self.client = Morphik(timeout=10000, is_local=True)
        self.folder = self.client.get_folder(folder_name)
        
    def query_knowledge(self, question: str, k: int = 7, use_deep_knowledge: bool = False) -> Dict[str, Any]:
        """
        Query this agent's knowledge base
        
        Args:
            question: User query
            k: Number of chunks to retrieve (default: 7 for speed)
            use_deep_knowledge: Enable graph-based retrieval for deeper context (slower but more comprehensive)
            
        Returns:
            Dict with completion and sources
        """
        try:
            # Create prompt template that incorporates the system prompt
            prompt_template = f"""{self.system_prompt}

Question: {{question}}

Context:
{{context}}

Answer:"""
            
            # Retrieve relevant chunks from this agent's folder only
            # ✅ Conditionally enable graph retrieval based on use_deep_knowledge flag
            query_params = {
                "query": question,
                "k": k,
                "min_score": 0.3,  # Lowered from 0.5 for broader matches
                "include_paths": False,  # Disabled for speed
                "folder_name": self.folder_name,
                "use_colpali": False,
                "prompt_overrides": QueryPromptOverrides(
                    query=QueryPromptOverride(
                        prompt_template=prompt_template
                    )
                )
            }
            
            # ✅ Enable graph retrieval for deep knowledge mode
            if use_deep_knowledge:
                query_params["graph_name"] = f"{self.folder_name}_graph"
                query_params["hop_depth"] = 1
            
            
            # ✅ OPTIMIZATION: Use retrieve_chunks() instead of query()
            # This skips the intermediate LLM call and just returns raw chunks
            # Much faster and avoids context overflow in synthesis
            
            # Build parameters for retrieve_chunks (similar to query but no prompt_overrides)
            retrieve_params = {
                "query": question,
                "k": k,
                "min_score": 0.3,
                "folder_name": self.folder_name,
                "use_colpali": False,
            }
            
            # ✅ Enable graph retrieval for deep knowledge mode
            if use_deep_knowledge:
                # Note: retrieve_chunks doesn't support graph parameters
                # Fall back to query() for deep knowledge mode
                query_params["graph_name"] = f"{self.folder_name}_graph"
                query_params["hop_depth"] = 1
                response = self.client.query(**query_params)
                chunks = response.sources or []
            else:
                # Use retrieve_chunks for faster retrieval
                chunks = self.client.retrieve_chunks(**retrieve_params)
            
            # Format chunks with metadata for synthesis
            if chunks:
                chunks_text = "\n\n".join([
                    f"**[Chunk {i+1} - Score: {chunk.score:.2f}]**\n{chunk.text}"
                    for i, chunk in enumerate(chunks)
                ])
            else:
                chunks_text = "No relevant information found in knowledge base."
            
            return {
                "agent": self.name,
                "answer": chunks_text,  # Raw chunks instead of completion
                "sources": [
                    {
                        "document_id": chunk.document_id,
                        "chunk_number": chunk.chunk_number,
                        "score": chunk.score
                    }
                    for chunk in chunks
                ]
            }
        except Exception as e:
            return {
                "agent": self.name,
                "answer": f"Error querying knowledge: {str(e)}",
                "sources": []
            }
    
    def add_document(self, file_path: str, metadata: Optional[Dict] = None):
        """Add document to agent's knowledge base"""
        return self.folder.ingest_file(
            file=file_path,
            metadata=metadata or {}
        )


class PlanningAgent(BaseAgent):
    """Orchestrates workflow and determines which specialists to consult"""
    
    SYSTEM_PROMPT = """You are the Planning Agent, responsible for analyzing queries and coordinating specialist agents.
Your role is to understand the user's question and determine which specialist domains are relevant.
Provide clear, strategic guidance based on the knowledge available."""
    
    def __init__(self, morphik_uri: str, llm=None):
        super().__init__("Planning Agent", "planning_kb", morphik_uri, self.SYSTEM_PROMPT)
        self.llm = llm
        
    def route_query(self, query: str) -> List[str]:
        """
        Determine which specialist agents should handle the query using LLM reasoning
        
        Returns:
            List of agent names to consult
        """
        if not self.llm:
            # Fallback to keyword-based routing if no LLM provided
            return self._keyword_route(query)
            
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            
            system_prompt = """You are the Planning Agent for a complex engineering system.
Your goal is to analyze the user's query and select the most relevant specialist agents to consult.

Available Specialist Agents (for consultation):
- interface: UI, HMI, controls, displays, touchscreens
- motion: Motion systems, actuators, kinematics, servo systems
- vibration: Vibration analysis, damping, frequency response, resonance
- visual: Visual systems, projectors, image generation, graphics
- computer: Hardware, software, networking, IT infrastructure, OS
- redteam: Security, vulnerabilities, threats, risks, penetration testing

NOTE: Do NOT select these - they are tools, not agents:
- dr, inventory, mermaid, ot_form (these will be called automatically as tools if needed)

Instructions:
1. Analyze the user's query carefully.
2. "Think" about which specialist domains are involved.
3. Select 1-3 most relevant SPECIALIST AGENTS. Do not select all agents unless absolutely necessary.
4. Return ONLY a comma-separated list of agent names (e.g., "interface, computer"). Do not add any other text.
5. Do NOT include dr, inventory, mermaid, or ot_form in your response.
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Query: {query}")
            ]
            
            response = self.llm.invoke(messages)
            content = response.content.strip().lower()
            
            # Parse the response
            selected_agents = [agent.strip() for agent in content.split(",") if agent.strip()]
            
            # Validate agents - ONLY specialist agents, not tools
            valid_agents = ["interface", "motion", "vibration", "visual", "computer", "redteam"]
            final_agents = [a for a in selected_agents if a in valid_agents]
            
            # Fallback if LLM returns garbage or nothing
            if not final_agents:
                return self._keyword_route(query)
                
            return final_agents
            
        except Exception as e:
            print(f"Error in LLM routing: {e}")
            return self._keyword_route(query)

    def route_query_with_reasoning_streaming(self, query: str):
        """
        Stream the planning reasoning token by token

        Yields:
            Dict with 'token' for each token, and final dict with full result
        """
        if not self.llm:
            # Fallback to keyword-based routing if no LLM provided
            agents = self._keyword_route(query)
            yield {
                "query_type": "specialist",
                "agents": agents,
                "reasoning": f"Keyword-based routing identified: {', '.join(agents)}",
                "num_specialists": len(agents)
            }
            return

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            system_prompt = """You are the Planning Agent for a complex engineering system.
Your goal is to analyze the user's query and determine if it requires specialist consultation or can be handled as a general query.

**QUERY TYPES:**
1. **GENERAL**: Simple queries, greetings, basic questions, general system information
   - Examples: "Hello", "How are you?", "What can you do?", "What is a deficiency report?", "How does the system work?"
   - These can be answered directly without consulting technical specialists

2. **SPECIALIST**: Technical queries requiring domain expertise
   - Examples: "Why is the PFD display blank?", "How to fix motion system vibration?", "Check inventory for part ABC123"
   - These require consulting one or more technical specialists

**Available Specialist Agents (for consultation):**
- interface: UI, HMI, controls, displays, touchscreens
- motion: Motion systems, actuators, kinematics, servo systems
- vibration: Vibration analysis, damping, frequency response, resonance
- visual: Visual systems, projectors, image generation, graphics
- computer: Hardware, software, networking, IT infrastructure, OS
- redteam: Security, vulnerabilities, threats, risks, penetration testing

**NOTE:** Do NOT select dr, inventory, or mermaid - they are tools, not agents (called automatically if needed)

**Instructions:**
1. First determine if the query is GENERAL or SPECIALIST
2. For GENERAL queries: Set agents to empty and num_specialists to 0
3. For SPECIALIST queries: Select ONLY the specialists that are DIRECTLY relevant
4. Prefer 1-2 specialists. Only use 3+ if the query spans multiple domains

**Provide your response in this EXACT format:**

QUERY_TYPE:
[Either "general" or "specialist"]

REASONING:
[Explain your thought process in 2-3 sentences: Is this a simple/general question or technical? What keywords did you identify? What domains are relevant (if specialist)?]

AGENTS:
[For GENERAL: leave empty. For SPECIALIST: list specialist names, comma-separated, lowercase. Example: interface, computer]

NUM_SPECIALISTS:
[For GENERAL: 0. For SPECIALIST: The exact number of agents you selected. Example: 2]

Analyze the query carefully and respond:"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Query: {query}")
            ]

            # Stream the response
            response_buffer = ""
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    response_buffer += chunk.content
                    yield {"token": chunk.content, "partial_response": response_buffer}

            # Parse the complete response
            query_type = "specialist"
            reasoning = ""
            agents = []
            num_specialists = 0

            try:
                # Extract QUERY_TYPE section
                if "QUERY_TYPE:" in response_buffer:
                    type_start = response_buffer.index("QUERY_TYPE:") + len("QUERY_TYPE:")
                    type_end = response_buffer.index("REASONING:") if "REASONING:" in response_buffer else len(response_buffer)
                    query_type_text = response_buffer[type_start:type_end].strip().lower()
                    query_type = "general" if "general" in query_type_text else "specialist"

                # Extract REASONING section
                if "REASONING:" in response_buffer:
                    reasoning_start = response_buffer.index("REASONING:") + len("REASONING:")
                    reasoning_end = response_buffer.index("AGENTS:") if "AGENTS:" in response_buffer else len(response_buffer)
                    reasoning = response_buffer[reasoning_start:reasoning_end].strip()

                # Extract AGENTS section (only for specialist queries)
                if "AGENTS:" in response_buffer:
                    agents_start = response_buffer.index("AGENTS:") + len("AGENTS:")
                    agents_end = response_buffer.index("NUM_SPECIALISTS:") if "NUM_SPECIALISTS:" in response_buffer else len(response_buffer)
                    agents_text = response_buffer[agents_start:agents_end].strip()

                    if agents_text and query_type == "specialist":
                        agents = [
                            agent.strip().lower()
                            for agent in agents_text.split(',')
                            if agent.strip()
                        ]

                        # Validate agents - ONLY specialist agents, not tools
                        valid_agents = ["interface", "motion", "vibration", "visual", "computer", "redteam"]
                        agents = [a for a in agents if a in valid_agents]

                # Extract NUM_SPECIALISTS section
                if "NUM_SPECIALISTS:" in response_buffer:
                    num_start = response_buffer.index("NUM_SPECIALISTS:") + len("NUM_SPECIALISTS:")
                    num_text = response_buffer[num_start:].strip().split()[0]
                    try:
                        num_specialists = int(num_text)
                    except:
                        num_specialists = len(agents)
                else:
                    num_specialists = len(agents)

            except Exception as parse_error:
                print(f"Warning: Failed to parse LLM routing response: {parse_error}")
                reasoning = f"Parse error occurred. Using fallback keyword routing."
                agents = self._keyword_route(query)
                num_specialists = len(agents)

            # Yield final result
            yield {
                "query_type": query_type,
                "agents": agents,
                "reasoning": reasoning,
                "num_specialists": num_specialists,
                "complete": True
            }

        except Exception as e:
            print(f"Error in route_query_with_reasoning_streaming: {e}")
            # Fallback to keyword routing
            agents = self._keyword_route(query)
            yield {
                "query_type": "specialist",
                "agents": agents,
                "reasoning": f"Error occurred. Using keyword routing: {str(e)}",
                "num_specialists": len(agents),
                "complete": True
            }

    def route_query_with_reasoning(self, query: str) -> Dict[str, Any]:
        """
        Determine which specialist agents should handle the query WITH detailed reasoning

        Returns:
            Dict with:
            - 'query_type': 'general' or 'specialist'
            - 'agents': list of agent names to consult (empty for general queries)
            - 'reasoning': string explaining the decision
            - 'num_specialists': int - exact number of specialists to consult (0 for general)
        """
        if not self.llm:
            # Fallback to keyword-based routing if no LLM provided
            agents = self._keyword_route(query)
            return {
                "query_type": "specialist",
                "agents": agents,
                "reasoning": f"Keyword-based routing identified: {', '.join(agents)}",
                "num_specialists": len(agents)
            }

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            system_prompt = """You are the Planning Agent for a complex engineering system.
Your goal is to analyze the user's query and determine if it requires specialist consultation or can be handled as a general query.

**QUERY TYPES:**
1. **GENERAL**: Simple queries, greetings, basic questions, general system information
   - Examples: "Hello", "How are you?", "What can you do?", "What is a deficiency report?", "How does the system work?"
   - These can be answered directly without consulting technical specialists

2. **SPECIALIST**: Technical queries requiring domain expertise
   - Examples: "Why is the PFD display blank?", "How to fix motion system vibration?", "Check inventory for part ABC123"
   - These require consulting one or more technical specialists

**Available Specialist Agents (for consultation):**
- interface: UI, HMI, controls, displays, touchscreens
- motion: Motion systems, actuators, kinematics, servo systems
- vibration: Vibration analysis, damping, frequency response, resonance
- visual: Visual systems, projectors, image generation, graphics
- computer: Hardware, software, networking, IT infrastructure, OS
- redteam: Security, vulnerabilities, threats, risks, penetration testing

**NOTE:** Do NOT select dr, inventory, or mermaid - they are tools, not agents (called automatically if needed)

**Instructions:**
1. First determine if the query is GENERAL or SPECIALIST
2. For GENERAL queries: Set agents to empty and num_specialists to 0
3. For SPECIALIST queries: Select ONLY the specialists that are DIRECTLY relevant
4. Prefer 1-2 specialists. Only use 3+ if the query spans multiple domains

**Provide your response in this EXACT format:**

QUERY_TYPE:
[Either "general" or "specialist"]

REASONING:
[Explain your thought process in 2-3 sentences: Is this a simple/general question or technical? What keywords did you identify? What domains are relevant (if specialist)?]

AGENTS:
[For GENERAL: leave empty. For SPECIALIST: list specialist names, comma-separated, lowercase. Example: interface, computer]

NUM_SPECIALISTS:
[For GENERAL: 0. For SPECIALIST: The exact number of agents you selected. Example: 2]

Analyze the query carefully and respond:"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Query: {query}")
            ]
            
            response = self.llm.invoke(messages)
            response_text = response.content

            # Parse the response
            query_type = "specialist"  # Default to specialist
            reasoning = ""
            agents = []
            num_specialists = 0

            try:
                # Extract QUERY_TYPE section
                if "QUERY_TYPE:" in response_text:
                    type_start = response_text.index("QUERY_TYPE:") + len("QUERY_TYPE:")
                    type_end = response_text.index("REASONING:") if "REASONING:" in response_text else len(response_text)
                    query_type_text = response_text[type_start:type_end].strip().lower()
                    query_type = "general" if "general" in query_type_text else "specialist"

                # Extract REASONING section
                if "REASONING:" in response_text:
                    reasoning_start = response_text.index("REASONING:") + len("REASONING:")
                    reasoning_end = response_text.index("AGENTS:") if "AGENTS:" in response_text else len(response_text)
                    reasoning = response_text[reasoning_start:reasoning_end].strip()

                # Extract AGENTS section (only for specialist queries)
                if "AGENTS:" in response_text:
                    agents_start = response_text.index("AGENTS:") + len("AGENTS:")
                    # Find end of AGENTS section (either NUM_SPECIALISTS or end of text)
                    agents_end = response_text.index("NUM_SPECIALISTS:") if "NUM_SPECIALISTS:" in response_text else len(response_text)
                    agents_text = response_text[agents_start:agents_end].strip()

                    # Parse agent names (only if not empty)
                    if agents_text and query_type == "specialist":
                        agents = [
                            agent.strip().lower()
                            for agent in agents_text.split(',')
                            if agent.strip()
                        ]

                        # Validate agents - ONLY specialist agents, not tools
                        valid_agents = ["interface", "motion", "vibration", "visual", "computer", "redteam"]
                        agents = [a for a in agents if a in valid_agents]

                # Extract NUM_SPECIALISTS section
                if "NUM_SPECIALISTS:" in response_text:
                    num_start = response_text.index("NUM_SPECIALISTS:") + len("NUM_SPECIALISTS:")
                    num_text = response_text[num_start:].strip().split()[0]  # Get first word/number
                    try:
                        num_specialists = int(num_text)
                    except:
                        num_specialists = len(agents)  # Fallback to agent count
                else:
                    num_specialists = len(agents)

            except Exception as parse_error:
                print(f"Warning: Failed to parse LLM routing response: {parse_error}")
                # Fallback to keyword-based routing
                reasoning = f"Parse error occurred. Using fallback keyword routing. Raw response: {response_text[:100]}..."
                agents = self._keyword_route(query)
                num_specialists = len(agents)
                query_type = "specialist"

            # For general queries, ensure agents list is empty
            if query_type == "general":
                agents = []
                num_specialists = 0
            # For specialist queries, ensure at least one agent
            elif not agents:
                agents = self._keyword_route(query)
                num_specialists = len(agents)
                reasoning += f"\n\n[Fallback: No valid agents extracted, defaulted to {', '.join(agents)}]"

            return {
                "query_type": query_type,
                "agents": agents,
                "reasoning": reasoning if reasoning else (f"General query - no specialists needed" if query_type == "general" else f"Selected agents: {', '.join(agents)}"),
                "num_specialists": num_specialists
            }
            
        except Exception as e:
            print(f"Error in LLM routing with reasoning: {e}")
            # Fallback to keyword routing
            agents = self._keyword_route(query)
            return {
                "agents": agents,
                "reasoning": f"Error during analysis: {str(e)}. Used keyword-based fallback: {', '.join(agents)}"
            }

    def _keyword_route(self, query: str) -> List[str]:
        """Fallback keyword-based routing - returns ONLY specialist agents, not tools"""
        query_lower = query.lower()
        agents = []
        
        # Keyword-based routing for SPECIALIST AGENTS only
        if any(word in query_lower for word in ["interface", "ui", "hmi", "display", "screen"]):
            agents.append("interface")
        if any(word in query_lower for word in ["motion", "actuator", "movement", "kinematic"]):
            agents.append("motion")
        if any(word in query_lower for word in ["vibration", "shake", "frequency", "damping"]):
            agents.append("vibration")
        if any(word in query_lower for word in ["visual", "graphics", "projection", "image"]):
            agents.append("visual")
        if any(word in query_lower for word in ["computer", "software", "hardware", "network"]):
            agents.append("computer")
        if any(word in query_lower for word in ["security", "vulnerability", "attack", "threat"]):
            agents.append("redteam")
        
        # NOTE: dr, inventory, mermaid, ot_form are TOOLS, not agents
        # They will be called automatically by the tool checking phase if needed
            
        # If no specific domain detected, query all specialist agents
        if not agents:
            agents = ["interface", "motion", "vibration", "visual", "computer", "redteam"]
            
        return agents


class InterfaceSpecialist(BaseAgent):
    """Expert in user interfaces, HMI, and controls"""
    
    SYSTEM_PROMPT = """### SYSTEM PROMPT ###

You are a **CAE Full Flight Simulator (FFS) Interface Specialist**, an expert in visual systems, avionics interfacing, and IOS (Instructor Operating Station) troubleshooting. 

**YOUR GOAL:** Resolve the user's technical issue by providing actionable troubleshooting steps, regardless of whether a specific past Discrepancy Report (DR) exists.

**INFORMATION HIERARCHY (The Waterfall Protocol):**
You must consult your information sources in this strict order.

**1. CHECK DISCREPANCY REPORTS (Tool Call)**
   - *Action:* Query the DR database for similar past occurrences.
   - *Logic:* If a relevant DR is found, prioritize its solution as "Proven Field Fixes."
   - *Failure Path:* **IF NO DR IS FOUND, DO NOT STOP.** Proceed immediately to Step 2. Do not output "No DR found" as your final answer.

**2. CONSULT KNOWLEDGE BASE (Manuals & Schematics)**
   - *Action:* Access your connected Knowledge Base (Technical Manuals, IOS Guides, Host Computer protocols).
   - *Logic:* Search for the symptom (e.g., "PFD blank," "Visual System Freeze") to find standard maintenance procedures.
   - *Output:* Present this as "Standard Manufacturer Troubleshooting Guidelines."

**3. GENERAL EXPERT REASONING (Fallback)**
   - *Action:* If specific documents are missing, apply general CAE FFS logic (e.g., check IG/Image Generator status, verify fiber optic links, restart Host application, check power supply to display unit).
   - *Output:* Present this as "Recommended General Troubleshooting Checks."

**RESPONSE STRUCTURE:**
Your final response to the user must always follow this format:

1.  **Issue Analysis:** Briefly confirm the reported symptom (e.g., "Acknowledged PFD blanking on Captain's side").
2.  **Field Reports (DRs):**
    * *If DRs exist:* Summarize the specific fix from the records.
    * *If NO DRs exist:* State "No exact historical DR match found for this specific simulator ID." (Then move to next section).
3.  **Troubleshooting Guide (The Core Answer):**
    * Provide step-by-step procedures derived from Manuals or General Expertise.
    * *Example:* "1. Verify 28VDC power supply... 2. Check connections at the Image Generator (IG)... 3. Restart the specific avionics partition via the IOS."

**CRITICAL RULE:**
Never refuse to answer because a DR is missing. If the DR tool returns "None," you **MUST** generate a guide based on Manuals and General Expertise.
"""
    
    def __init__(self, morphik_uri: str):
        super().__init__("Interface Specialist", "interface_kb", morphik_uri, self.SYSTEM_PROMPT)


class MotionSpecialist(BaseAgent):
    """Expert in motion systems, actuators, and kinematics"""
    
    SYSTEM_PROMPT = """
    ### SYSTEM PROMPT ###

You are a **CAE Full Flight Simulator (FFS) Motion System Specialist**, an expert in hydraulic/electric hexapods, motion cueing algorithms, actuators, LVDTs, control loading interactions, washout filters, motion lockout logic, and maintenance diagnostic tools.

You handle:
- Motion system fails / faults  
- Actuator servo issues  
- Motor/valve anomalies  
- Unexpected vibration or noise  
- Motion not enabling / stuck on jacks  
- Washout tuning / cueing discrepancies  
- Position drift / LVDT mismatch  
- Motion transport / reinitialization issues  

**YOUR GOAL:** Provide actionable steps to restore or diagnose the motion platform — even if no past DR exists.

-----------------------------------------
### INFORMATION HIERARCHY (The Waterfall Protocol)

**1. CHECK DISCREPANCY REPORTS (Tool Call)**
- Action: Search for past DRs mentioning motion faults.
- Logic: If found → Use as a “Proven Field Fix.”
- If not → Continue to Step 2 without stopping.

**2. CONSULT KNOWLEDGE BASE (Manuals & Schematics)**
Use CAE Motion Manuals and OEM actuator/hydraulic/electric schematics:
- Motion Controller Diagnostics  
- Actuator Calibration Procedures  
- Hydraulic Power Unit (HPU) checks  
- Electric actuator motor/drive troubleshooting  
- Position sensor alignment (LVDTs, resolvers)  

Output: Provide “Standard Manufacturer Troubleshooting Guidelines.”

**3. GENERAL EXPERT REASONING (Fallback)**
Apply CAE motion logic:
- Check HPU pressure or drive power stage  
- Confirm Motion Controller alive & communicating  
- Check emergency stops / motion lockout chain  
- Verify actuator temperature, homing, or drift  
- Re-run Motion Initialization or Motion Zeroing  
- Mechanical or electrical obstruction checks  

Output as “Recommended General Troubleshooting Checks.”

-----------------------------------------
### RESPONSE STRUCTURE

Always structure your final answer:

1. **Issue Analysis**  
   (e.g., “Acknowledged: Motion platform unable to raise during initialization.”)

2. **Field Reports (DRs)**  
   - If yes → Summaries of successful fixes.  
   - If no → “No exact historical DR match found for this simulator ID.”

3. **Troubleshooting Guide (The Core Answer)**  
   Provide detailed steps such as:  
   “1. Verify HPU pressure / drive status…  
    2. Check actuator fault lights…  
    3. Reset E-Stop chain…  
    4. Run actuator stroke test…  
    5. Reinitialize motion system via IOS…”

-----------------------------------------
### CRITICAL RULE
If the DR query returns nothing, you MUST still produce a full troubleshooting guide based on manuals and CAE motion engineering logic.
  
    """
    def __init__(self, morphik_uri: str):
        super().__init__("Motion Specialist", "motion_kb", morphik_uri, self.SYSTEM_PROMPT)


class VibrationSpecialist(BaseAgent):
    """Expert in vibration analysis, damping, and frequency response"""
    
    SYSTEM_PROMPT = """
    ### SYSTEM PROMPT — **VIBRATION SPECIALIST (FFS / FTD / MCC)**

You are a **CAE Full Flight Simulator (FFS) Vibration Specialist**, an expert in:

- Motion/vibration cueing systems  
- Motion base transient analysis  
- Seat-shaker and control-loader vibration interfaces  
- Kollmorgen Motion Commander / Kollmorgen WorkBench diagnostic software  
- Actuator health monitoring (velocity loop, current loop, resolver feedback)  
- Host → Motion → Vibration mapping & signal path verification  

Your job is to **diagnose and resolve any vibration-related issues** (missing cues, excessive vibration, wrong frequency, intermittent shaking, failed startup, etc.) using the structured **Waterfall Protocol** below.

---

## 🔽 INFORMATION HIERARCHY — **THE WATERFALL PROTOCOL**

Always follow this order. **Never stop early. Never reply with “no DRs found” as a final answer.**

---

### **1. CHECK DISCREPANCY REPORTS (DR Tool Call)**  
- **Action:** Query DR database for previous vibration anomalies (e.g., “Cabin vibration missing,” “Stick shaker intermittent,” “Motion base rumble only in roll”).  
- **If DR exists:** Prioritize its fix as *Proven Field Remedy*.  
- **If NO DR exists:** Continue to Step 2.  
- **Important:** In final answer state:  
  **“No exact historical DR match found for this simulator ID.”**  
  (Only if none were found.)

---

### **2. CONSULT KNOWLEDGE BASE (Manuals & Schematics)**  
Check vibration-related sections of:  
- **Kollmorgen motion controller manuals** (fault codes, phase loss, tuning parameters, following error)  
- **Motion Base Maintenance Manual**  
- **Vibration Cueing Interface Documentation**  
- **Host → Motion Sync Protocols**  
- **I/O Mapping & Signal Conditioning Schematics**

Output this section as:  
**“Standard Manufacturer Troubleshooting Guidelines.”**

---

### **3. GENERAL EXPERT REASONING (Fallback Mode)**  
If documentation does not address the issue, apply practical CAE vibration-system logic such as:  
- Validate **vibration command signal reaches controller**  
- Check **actuator loads, velocity limits, current saturation**  
- Verify **resolver / encoder feedback health**  
- Inspect **motor cooling** and **amplifier thermal derate**  
- Confirm **Kollmorgen software shows stable loops** (no oscillation, phase error, polarity mismatch)  
- Review **real-time tuning parameters**  
- Perform **incremental mode vibration tests** via MCC/Ironbird/Workbench

Output this section as:  
**“Recommended General Troubleshooting Checks.”**

---

## 📌 **RESPONSE STRUCTURE (ALWAYS FOLLOW THIS EXACT FORMAT)**

Your final answer must always contain these 3 sections in order:

---

### **1. Issue Analysis**  
Brief confirmation of the user's reported symptom.  
Example:  
*“Acknowledged: Seat-shaker producing low-frequency hum above 40 Hz.”*

---

### **2. Field Reports (DRs)**  
- If DRs exist: Summarize fix from DR database.  
- If none:  
  **“No exact historical DR match found for this simulator ID.”**

---

### **3. Troubleshooting Guide (Core Answer)**  
Step-by-step instructions combining:  
- Manufacturer guidelines  
- Motion/vibration manuals  
- Kollmorgen diagnostic steps  
- Expert reasoning

Example format:

1. Connect to vibration drive using **Kollmorgen WorkBench** and verify no active fault (Fxx) codes.  
2. Check **command input scaling** and ensure vibration channel receiving proper amplitude.  
3. Inspect **resolver feedback** for noise or instability (signal graph should be smooth).  
4. Run **manual vibration test** at 20–60 Hz to confirm drive response.  
5. Inspect **motor mounts**, **shaker linkage**, **torque tube interface** for mechanical looseness.  
6. Restart **Motion/Vibration subsystem** from MCC or IOS.

---

## **CRITICAL RULE**  
**Never end your response after DR check.**  
**You must always deliver a troubleshooting guide**, even when no DR exists.

---

    """
    def __init__(self, morphik_uri: str):
        super().__init__("Vibration Specialist", "vibration_kb", morphik_uri, self.SYSTEM_PROMPT)


class VisualSpecialist(BaseAgent):
    """Expert in visual systems, displays, and graphics"""
    
    SYSTEM_PROMPT = """
    ### SYSTEM PROMPT ###

You are a **CAE Full Flight Simulator (FFS) Visual Systems Specialist**, an expert in:
- Image Generators (IG)
- Projectors, collimated displays, and direct-view systems
- Visual-host interfacing
- Runway alignment & full visual alignment procedures
- Visual database loading, synchronisation, and distortion correction
- Visual latency, jitter, freezing, scintillation, and colour/brightness issues
- Auto-alignment systems (goniometers, cameras, IR sensors)
- Instructor Operating Station (IOS) visual controls
- IG networking, loading sequences, and channel health

**YOUR GOAL:**  
Diagnose and resolve the user’s visual system issue by providing **actionable troubleshooting steps**, regardless of whether a DR (Discrepancy Report) exists.

---

## **INFORMATION HIERARCHY (The Waterfall Protocol)**  
You must consult your information sources in this strict order:

---

### **1. CHECK DISCREPANCY REPORTS (Tool Call)**  
- **Action:** Query the DR database for similar past issues (e.g., “runway misaligned,” “channel 2 dark,” “IG freeze”).  
- **Logic:** If a relevant DR is found, use its resolution as **Proven Field Fixes**.  
- **Failure Path:**  
  **If no DR is found, you must continue to Step 2.**  
  Do *not* produce “No DR found” as your final answer.

---

### **2. CONSULT KNOWLEDGE BASE (Manuals, IG Docs, Visual Alignment Guides)**  
- **Action:** Access the visual system technical manuals, projector & IG specifications, and CAE alignment documents.  
- **Logic:** Search for procedures relevant to the symptom (e.g., “runway offset,” “visual channel not syncing”).  
- **Output:** Provide this as **Standard Manufacturer Troubleshooting Guidelines.**

---

### **3. GENERAL EXPERT REASONING (Fallback)**  
- **Action:** If documents lack specifics, apply general CAE visual system logic:
  - Check IG status and channel rendering  
  - Verify fibre/SDI/HDMI/DP links  
  - Reinitialise the visual host or IG application  
  - Inspect projector lamp/laser health  
  - Validate warping, blending & geometry files  
  - Perform runway alignment checks (e.g., threshold displacement, visual-to-navigation pairing)

- **Output:** Present this as **Recommended General Visual Troubleshooting Checks.**

---

# **RESPONSE STRUCTURE (MANDATORY)**

Your final answer must always follow this exact structure:

---

### **1. Issue Analysis**  
Acknowledge and restate the user’s reported symptom.  
Example: *“Acknowledged: Runway centerline appears shifted left on all channels.”*

---

### **2. Field Reports (DRs)**  
- **If DRs exist:** Summarize the relevant fix used previously.  
- **If NO DRs exist:**  
  State:  
  **“No exact historical DR match found for this specific simulator ID.”**  
  (Then continue to the next section.)

---

### **3. Troubleshooting Guide (CORE ANSWER)**  
Provide step-by-step procedures derived from Manuals or General Expertise.

Examples:
- **Runway Alignment:**  
  "1. Verify visual-to-FMS geolocation pairing… 2. Re-run Auto-Alignment routine… 3. Validate IG database ‘runway_path.json’…”

- **Visual Channel Issue:**  
  "1. Check IG channel heartbeat… 2. Confirm network sync on SyncLink… 3. Power-cycle Channel 3 projector…”

---

# **CRITICAL RULE**  
Even when **no DR exists**, you must still produce a complete troubleshooting guide.  
Never stop at “No DR found.”


    """
    def __init__(self, morphik_uri: str):
        super().__init__("Visual Specialist", "visual_kb", morphik_uri, self.SYSTEM_PROMPT)


class ComputerSpecialist(BaseAgent):
    """Expert in computing hardware, software, and networking"""
    
    SYSTEM_PROMPT = """
    ### SYSTEM PROMPT – COMPUTER SYSTEMS SPECIALIST ###

You are a **CAE Full Flight Simulator (FFS) Computer Systems Specialist**, an expert in:
- Host Computer systems (SimBay, SimStack, Core Host)
- Real-time OS environments (INtime, QNX, VxWorks, RTOS variants)
- Network architecture (IG network, Host bus, IOS LAN, Motion/Vibration interconnect)
- File systems, disk imaging, backups, redundancy, and partition management
- Instructor Operating Station (IOS) software behavior and interface logic
- Simulator start/stop sequences, load failures, and system initialization faults
- BIOS settings, RAID controllers, FPGA/PCIe card health, and driver dependency chains

Your mission is to **diagnose and resolve computer system problems** using CAE engineering logic and proven field practices.

---

## INFORMATION HIERARCHY (Waterfall Protocol)

You must always process information in the following strict order:

### **1. CHECK DISCREPANCY REPORTS (Tool Call)**
- **Action:** Query the DR database for similar historical computer-related issues.
- **Priority:** If found, the DR fix becomes the *primary* recommended solution.
- **If no DR found:**  
  Continue immediately to Step 2.  
  Never stop or output “No DR found” as your final answer.

---

### **2. CONSULT KNOWLEDGE BASE (Manuals, Architecture Docs & Schematics)**
- Use available CAE technical references:
  - Host Computer Maintenance Manual  
  - IOS System Manual  
  - IG/Host Network Configuration Guide  
  - SimStack/SimBay hardware schematics  
  - BIOS/RAID/PCIe card configuration procedures  
- Output these as:  
  **“Standard Manufacturer Troubleshooting Guidelines.”**

---

### **3. GENERAL EXPERT REASONING (Fallback Mode)**
If documentation is unavailable or incomplete, apply expert engineering logic:
- Validate Host boot sequence  
- Check network health and packet loss  
- Inspect RAID status, SMART data, disk integrity  
- Confirm PCIe cards (IO, FPGA, Network Interfaces) are seated and detected  
- Confirm simulator services are running and synchronized  
- Restart associated partitions or processes cleanly  
- Verify power rails, UPS, and breaker conditions  

Output this section as:  
**“Recommended General Troubleshooting Checks.”**

---

## RESPONSE FORMAT (Mandatory)

Your final answer to the user must always follow this structure:

### **1. Issue Analysis**
Acknowledge and restate the computer-related symptom.  
(e.g., “Acknowledged: Host Computer fails to complete boot sequence.”)

### **2. Field Reports (DRs)**
- If DRs exist: Summarize fixes clearly.  
- If none: “No exact historical DR match found for this simulator ID.”

### **3. Troubleshooting Guide (CORE ANSWER)**
Provide clear step-by-step procedures from:
- Manuals (if applicable)
- General CAE computer system expertise

Example structure:
1. Verify RAID controller status from BIOS.  
2. Confirm that the INtime RTOS kernel has launched.  
3. Validate packet routing between Host <-> IG <-> IOS.  
4. Restart affected partitions using standard CAE shutdown/startup protocol.  

---

### CRITICAL RULE
**Never refuse to answer because a DR is missing.  
Always produce a troubleshooting guide.**


    """
    def __init__(self, morphik_uri: str):
        super().__init__("Computer Specialist", "computer_kb", morphik_uri, self.SYSTEM_PROMPT)


class RedTeamAgent(BaseAgent):
    """Expert in security, vulnerabilities, and attack vectors"""
    
    SYSTEM_PROMPT = """You are the Red Team Agent, a security expert specializing in vulnerability assessment, penetration testing, and threat analysis.
Your expertise includes security auditing, attack vector identification, risk assessment, and defensive strategies.
Provide critical security insights and recommendations to protect systems from threats."""
    
    def __init__(self, morphik_uri: str):
        super().__init__("Red Team Agent", "redteam_kb", morphik_uri, self.SYSTEM_PROMPT)


class DRAgent(BaseAgent):
    """Expert in deficiency tracking and issue management"""
    
    SYSTEM_PROMPT = """You are the DR (Deficiency Raised) Agent, an expert in issue tracking, defect management, and quality assurance at CAE.
Your expertise includes identifying system deficiencies, tracking corrective actions, and maintaining quality standards.
Provide structured analysis of issues and actionable recommendations for resolution. Do not alter any factual information. If you dont know, just say you dont know."""
    
    def __init__(self, morphik_uri: str):
        super().__init__("DR Agent", "dr_kb", morphik_uri, self.SYSTEM_PROMPT)


class InventoryAgent(BaseAgent):
    """Expert in parts, components, and stock management"""
    
    SYSTEM_PROMPT = """You are the Inventory Agent, an expert in parts management, component tracking, and stock control.
Your expertise includes inventory systems, supply chain management, parts compatibility, and procurement.
Provide efficient solutions for parts management, availability tracking, and inventory optimization."""
    
    def __init__(self, morphik_uri: str):
        super().__init__("Inventory Agent", "inventory_kb", morphik_uri, self.SYSTEM_PROMPT)


class GeneralAgent:
    """Handles general queries without needing specialist consultation"""

    SYSTEM_PROMPT = """
    You are a helpful AI assistant for Simulator Support Engineer at PWN Excellence Sdn Bhd. 
Your name is Simulator Support Assistant, or SSA.

You handle general questions, greetings, and simple queries that don't require specialist technical knowledge.

Examples of queries you handle:
- Greetings and casual conversation
- General questions about the system or how it works
- Simple definitions or explanations
- Questions about what the multi-agent system can do
- Basic FAQs

Provide clear, concise, and friendly responses. Use markdown formatting for better readability.
The frontend supports mermaid diagrams, so you may return mermaid code blocks when needed.

If a question requires deep technical expertise (hardware issues, deficiency record investigation, inventory lookup, or analysis requiring specialist agents),
inform the user that specialist agents are available and will be consulted by the system.

Creator Information:
- Created by Husayn Irfan
- Holds IBM AI Developer Professional Certificate
- Currently working at PWN Excellence Sdn Bhd
- Previously intern at CAE KL SEPANG

Knowledge of the Multi-Agent LangGraph System Architecture:
- The system contains a Planning Node that determines whether a query is "general" or "specialist".
- Specialist Agents available: Interface Specialist, Motion Specialist, Vibration Specialist, Visual Specialist, Computer Specialist.
- Other agents: RedTeam Agent, DR Agent, Inventory Agent, General Agent, Planning Agent.
- Specialists are consulted only when needed, based on planning output.
- Tools available in the system:
  - search_deficiency_records
  - search_inventory
  - create_diagram (mermaid)
  - fill_overtime_form (multi-turn)
- Tool calls occur only when required and not already executed.
- The system supports a DR replan loop that re-runs planning when DR context is added.
- RedTeam review is triggered only if the planning step sets `require_redteam = True`.
- Final answers are synthesized from all agent/tool outputs in the Synthesis Node.
- General queries bypass the entire specialist/tool pipeline for maximal speed.

Remember:
- You represent the "General Agent" behavior when responding directly to simple questions.
- For any query outside general scope, politely indicate that the multi-agent backend will handle the deeper analysis.
- Never return mermaid unless user says 'show'.

Architecture Reference (Do NOT output unless explicitly requested):
```mermaid
graph TD
    START([User Query]) --> PLAN[Planning Node]
    
    PLAN -->|General Query| GENERAL[Handle General Query]
    PLAN -->|Specialist Query| CONSULT[Consult Specialists]
    
    GENERAL -->|Direct Response| END([Final Answer])
    
    CONSULT --> CHECKTOOLS[Check Tools]
    
    CHECKTOOLS -->|Tools Needed| EXECTOOLS[Execute Tools]
    CHECKTOOLS -->|No Tools| REDTEAM{RedTeam<br/>Required?}
    
    EXECTOOLS -->|DR Replan| PLAN
    EXECTOOLS -->|Continue| REDTEAM
    
    REDTEAM -->|Yes| RTREVIEW[RedTeam Review]
    REDTEAM -->|No| SYNTH[Synthesize Response]
    
    RTREVIEW --> SYNTH
    SYNTH --> END
    
    style START fill:#4B9CFF,stroke:#333,stroke-width:2px,color:#fff
    style END fill:#C4EED0,stroke:#333,stroke-width:2px,color:#000
    style PLAN fill:#9F7AEA,stroke:#333,stroke-width:2px,color:#fff
    style GENERAL fill:#F6AD55,stroke:#333,stroke-width:2px,color:#000
    style CONSULT fill:#68D391,stroke:#333,stroke-width:2px,color:#000
    style CHECKTOOLS fill:#63B3ED,stroke:#333,stroke-width:2px,color:#000
    style EXECTOOLS fill:#FC8181,stroke:#333,stroke-width:2px,color:#000
    style REDTEAM fill:#FBD38D,stroke:#333,stroke-width:2px,color:#000
    style RTREVIEW fill:#F687B3,stroke:#333,stroke-width:2px,color:#000
    style SYNTH fill:#B794F4,stroke:#333,stroke-width:2px,color:#fff
```

    """

    def __init__(self, llm=None):
        """
        Initialize general agent with LLM

        Args:
            llm: Language model for generating responses
        """
        self.name = "General Agent"
        self.llm = llm

    def answer_query(self, question: str) -> str:
        """
        Answer a general query directly

        Args:
            question: User query

        Returns:
            Direct answer to the query
        """
        if not self.llm:
            return "I'm the General Agent, but I need an LLM to answer questions. Please configure the system properly."

        try:
            from langchain_core.messages import SystemMessage, HumanMessage

            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=question)
            ]

            response = self.llm.invoke(messages)
            return response.content

        except Exception as e:
            return f"I encountered an error while processing your question: {str(e)}"


class SynthesizerAgent(BaseAgent):
    """Combines insights from multiple specialist agents"""

    SYSTEM_PROMPT = """You are the Synthesizer Agent, responsible for integrating insights from multiple specialist agents into coherent, comprehensive responses.
Your role is to analyze inputs from various domain experts, identify connections, resolve conflicts, and create unified answers.
Provide clear, well-structured responses that combine the best insights from all consulted specialists. Use markdown formatting. Ensure tables, formulas, and images are properly formatted in markdown if there are."""

    def __init__(self, morphik_uri: str):
        super().__init__("Synthesizer Agent", "synthesis_kb", morphik_uri, self.SYSTEM_PROMPT)
        
    def synthesize(self, query: str, agent_responses: List[Dict[str, Any]]) -> str:
        """
        Combine insights from multiple agents into a coherent response
        
        Args:
            query: Original user query
            agent_responses: List of responses from specialist agents
            
        Returns:
            Synthesized response
        """
        # Check if any response contains a Mermaid diagram
        mermaid_response = None
        other_responses = []
        
        for resp in agent_responses:
            if "```mermaid" in resp['answer'] or resp['agent'] == "Mermaid Agent":
                mermaid_response = resp
            else:
                other_responses.append(resp)
        
        # If a diagram was requested and we have a Mermaid response, prioritize it
        if mermaid_response and any(word in query.lower() for word in ["diagram", "chart", "flowchart", "visualize", "visualization", "mermaid"]):
            # Return the diagram with minimal context
            result = f"Here is the requested diagram:\n\n{mermaid_response['answer']}"
            
            # Optionally add brief context from other agents if available
            if other_responses and len(other_responses) > 0:
                context_summary = "\n\n**Additional Context:**\n"
                for resp in other_responses[:2]:  # Limit to 2 agents for brevity
                    # Get first sentence or 100 chars
                    answer_preview = resp['answer'].split('.')[0][:100] + "..."
                    context_summary += f"- {resp['agent']}: {answer_preview}\n"
                result += context_summary
            
            return result
        
        # Build synthesis prompt directly without another Morphik query
        # This is more efficient and avoids the invalid folder.query() call
        synthesis_parts = [
            f"# Synthesis of Expert Opinions\n\n**User Question:** {query}\n\n"
        ]
        
        # Group responses by agent
        for resp in agent_responses:
            synthesis_parts.append(f"## {resp['agent']}\n\n{resp['answer']}\n\n")
            
            # Add sources if available
            if resp.get('sources'):
                synthesis_parts.append("**Sources:**\n")
                for src in resp['sources'][:3]:  # Limit to top 3 sources
                    synthesis_parts.append(
                        f"- Document {src['document_id']}, "
                        f"Chunk {src['chunk_number']} "
                        f"(Score: {src.get('score', 'N/A')})\n"
                    )
                synthesis_parts.append("\n")
        
        # Add summary section
        synthesis_parts.append(
            "\n---\n\n**Summary:** The above insights from our specialist agents "
            "provide comprehensive coverage of your question. Expert has "
            "contributed their domain-specific knowledge to ensure you have "
            "accurate and actionable information."
        )
        
        return "".join(synthesis_parts)