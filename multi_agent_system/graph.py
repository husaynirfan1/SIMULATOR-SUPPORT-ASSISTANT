"""
Advanced LangGraph workflow for multi-agent orchestration with Morphik
Implements LLM-based tool calling for DR, Inventory, and Mermaid
Uses OpenRouter for flexible model selection
"""

from typing import TypedDict, List, Dict, Any, Annotated, Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
import operator
import os
import time  
from dotenv import load_dotenv
load_dotenv()

from agents import (
    PlanningAgent,
    InterfaceSpecialist,
    MotionSpecialist,
    VibrationSpecialist,
    VisualSpecialist,
    ComputerSpecialist,
    RedTeamAgent,
    DRAgent,
    InventoryAgent,
    SynthesizerAgent,
    GeneralAgent
)
from agent_tools import (
    AVAILABLE_TOOLS,
    initialize_tool_agents,
    search_deficiency_records,
    search_inventory,
    create_diagram,
    fill_overtime_form
)
from ot_conversation_manager import OTConversationManager
from optimizations.cache.response_cache import get_cache


class AgentState(TypedDict):
    """State passed between agents in the graph"""
    query: str
    messages: Annotated[List, operator.add]
    agents_to_consult: List[str]
    num_specialists_to_consult: int  # ✅ NEW: Exact number of specialists to consult
    agent_responses: Annotated[List[Dict[str, Any]], operator.add]
    tool_responses: Annotated[List[Dict[str, Any]], operator.add]
    final_answer: str
    current_step: str
    require_redteam: bool
    dr_replan_triggered: bool
    dr_replan_done: bool
    tools_called: List[str]  # ✅ Track which tools have been called
    ot_conversation_state: Optional[Dict[str, Any]]  # ✅ NEW: OT form conversation state
    ot_conversation_active: bool  # ✅ NEW: Is OT conversation active?
    is_general_query: bool  # ✅ NEW: Flag for general queries
    use_deep_knowledge: bool  # ✅ NEW: Enable graph-based retrieval for deeper context
    skip_tool_check: bool  # ✅ NEW: Flag from Planning Agent to skip tool checking

class MultiAgentSystem:
    """Advanced LangGraph-based multi-agent orchestration system with tool calling"""
    from dotenv import load_dotenv
    load_dotenv()

    def __init__(
        self,
        morphik_uri: str,
        openrouter_api_key: str = None,  # Made optional parameter
        model: str = None,
        openrouter_base_url: str = "https://api.deepseek.com/v1", # now using deepseek
        enable_cache: bool = True,  # ✅ NEW: Enable response caching
        cache_ttl: int = 3600,  # ✅ NEW: Cache TTL in seconds (1 hour default)
        cache_size: int = 100,  # ✅ NEW: Maximum cache entries
        checkpointer = None  # ✅ NEW: LangGraph checkpointer for conversation memory
    ):
        """
        Initialize the multi-agent system

        Args:
            morphik_uri: Morphik server URI
            openrouter_api_key: OpenRouter API key (or set OPENROUTER_API_KEY env var)
            model: Model to use (e.g., "anthropic/claude-3.5-sonnet", "openai/gpt-4")
            openrouter_base_url: OpenRouter API base URL
            enable_cache: Enable response caching for frequently asked questions
            cache_ttl: Cache time-to-live in seconds
            cache_size: Maximum number of cached responses
            checkpointer: LangGraph checkpointer for conversation memory (e.g., InMemorySaver)
        """
        self.morphik_uri = morphik_uri
        self.event_callback = None  # ✅ NEW: Callback for streaming events
        self.event_loop = None  # ✅ NEW: Store reference to event loop

        # ✅ NEW: Store checkpointer for conversation memory
        self.checkpointer = checkpointer

        # ✅ NEW: Initialize cache if enabled
        self.cache_enabled = enable_cache
        self.cache = get_cache(max_size=cache_size, ttl_seconds=cache_ttl) if enable_cache else None
        
        # ✅ FIX: Get API key FIRST, before using it
        api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY environment "
                "variable or pass openrouter_api_key parameter."
            )
        
        # ✅ FIX: Get model from parameter or environment
        if model is None:
            model = os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast:free")
        
        # Now we can safely use api_key
        # 1. Base LLM for pure text/synthesis (No tools bound)
        self.base_llm = ChatOpenAI(
            model=model,
            temperature=0,
            max_tokens=4096,
            openai_api_key=api_key,
            openai_api_base=openrouter_base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/your-repo",
                "X-Title": "CAE Multi-Agent System",
            }
        )

        # Initialize all agents
        # Pass base_llm to PlanningAgent for ReAct/Think mode
        self.planning_agent = PlanningAgent(morphik_uri, llm=self.base_llm)
        self.general_agent = GeneralAgent(llm=self.base_llm)  # ✅ NEW: General agent for simple queries
        self.interface_agent = InterfaceSpecialist(morphik_uri)
        self.motion_agent = MotionSpecialist(morphik_uri)
        self.vibration_agent = VibrationSpecialist(morphik_uri)
        self.visual_agent = VisualSpecialist(morphik_uri)
        self.computer_agent = ComputerSpecialist(morphik_uri)
        self.redteam_agent = RedTeamAgent(morphik_uri)
        self.dr_agent = DRAgent(morphik_uri)
        self.inventory_agent = InventoryAgent(morphik_uri)
        # Synthesizer is now handled via direct LLM call for better control
        
        # Initialize tool agents
        initialize_tool_agents(self.dr_agent, self.inventory_agent)

        # Map agent names to instances
        self.agent_map = {
            "interface": self.interface_agent,
            "motion": self.motion_agent,
            "vibration": self.vibration_agent,
            "visual": self.visual_agent,
            "computer": self.computer_agent,
            "redteam": self.redteam_agent,
        }

        # ✅ Initialize OT conversation manager (shared across all queries in a session)
        self.ot_conversation_manager = OTConversationManager()

        # 2. Tool LLM (Tools bound)
        self.tool_llm = self.base_llm.bind_tools(AVAILABLE_TOOLS)

        # Build the graph
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the advanced LangGraph workflow with tool calling"""
        workflow = StateGraph(AgentState)

        # Define nodes
        workflow.add_node("plan", self._planning_node)
        workflow.add_node("handle_general", self._handle_general_query_node)  # ✅ NEW: Handle general queries
        workflow.add_node("handle_dr_only", self._handle_dr_only_node)  # ✅ NEW: Handle DR-only queries
        workflow.add_node("consult_specialists", self._consult_specialists_node)
        workflow.add_node("check_tools", self._check_tools_node)
        workflow.add_node("execute_tools", self._execute_tools_node)
        workflow.add_node("redteam_review", self._redteam_node)
        workflow.add_node("synthesize", self._synthesize_node)

        # Define edges
        workflow.set_entry_point("plan")

        # ✅ NEW: After planning, check query type
        workflow.add_conditional_edges(
            "plan",
            self._route_after_planning,
            {
                "general": "handle_general",  # Simple general queries
                "dr_only": "handle_dr_only",  # DR-only queries (skip specialists)
                "specialist": "consult_specialists"  # Normal specialist flow
            }
        )

        # ✅ NEW: General queries go straight to END (skip synthesis)
        workflow.add_edge("handle_general", END)

        # ✅ NEW: DR-only queries go straight to synthesis
        workflow.add_edge("handle_dr_only", "synthesize")
        
        workflow.add_edge("consult_specialists", "check_tools")
        
        # Conditional: check if tools are needed
        workflow.add_conditional_edges(
            "check_tools",
            self._should_use_tools,
            {
                "use_tools": "execute_tools",
                "skip_tools": "redteam_review"
            }
        )
        
        workflow.add_conditional_edges(
            "execute_tools",
            self._check_dr_loop,
            {
                "replan": "plan",
                "continue": "redteam_review"
            }
        )
        
        # Conditional: check if redteam review is needed
        workflow.add_conditional_edges(
            "redteam_review",
            self._should_consult_redteam,
            {
                "redteam": "synthesize",  # RedTeam adds to responses
                "skip": "synthesize"
            }
        )
        
        workflow.add_edge("synthesize", END)

        # ✅ NEW: Compile with checkpointer for conversation memory
        return workflow.compile(checkpointer=self.checkpointer) if self.checkpointer else workflow.compile()

    def _check_dr_loop(self, state: AgentState) -> Literal["replan", "continue"]:
        """Check if we should loop back to planning with DR context"""
        if state.get("dr_replan_triggered"):
            # ✅ NEW: Emit re-plan event if callback is set
            if self.event_callback:
                try:
                    self._emit_sync("replan_loop_start", {
                        "message": "DR context found - re-planning workflow",
                        "reason": "Deficiency records provide additional context"
                    })
                except Exception as e:
                    print(f"⚠️ Failed to emit replan event: {e}")
            return "replan"
        return "continue"

    def _emit_sync(self, event_type: str, data: Dict[str, Any]):
        """Emit event from synchronous context"""
        if self.event_callback and self.event_loop:
            import asyncio
            try:
                # Schedule the coroutine in the stored event loop
                asyncio.run_coroutine_threadsafe(
                    self.event_callback(event_type, data),
                    self.event_loop
                )
            except Exception as e:
                print(f"⚠️ Failed to emit {event_type}: {e}")
        elif self.event_callback and not self.event_loop:
                print(f"⚠️ No event loop available for {event_type}")
    
    def _route_after_planning(self, state: AgentState) -> Literal["general", "dr_only", "specialist"]:
        """Route query after planning based on type"""
        # ✅ Check if this is a DR-only query
        if state.get("is_dr_only_query", False):
            print("🔍 Routing to DR-only handler (skip specialists)")
            return "dr_only"

        # Check if planning agent marked this as general
        if state.get("is_general_query", False):
            return "general"

        # Check if no specialists were selected
        if not state.get("agents_to_consult") or len(state.get("agents_to_consult", [])) == 0:
            # But not if it's an OT form request (those go through tools)
            query_lower = state["query"].lower()
            ot_keywords = ["overtime", "ot form", "fill form", "create form"]
            if not any(kw in query_lower for kw in ot_keywords):
                return "general"

        return "specialist"
    
    def _handle_general_query_node(self, state: AgentState) -> AgentState:
        """Handle general queries directly without specialist consultation"""
        print(f"💬 Handling general query directly")

        # Use general agent to answer
        answer = self.general_agent.answer_query(state["query"])

        # Format as agent response for consistency
        general_response = {
            "agent": "General Agent",
            "answer": answer,
            "sources": []
        }

        return {
            **state,
            "agent_responses": [general_response],
            "final_answer": answer,  # Set directly since we're skipping synthesis
            "current_step": "general_query_handled"
        }

    def _handle_dr_only_node(self, state: AgentState) -> AgentState:
        """Handle DR-only queries by directly executing DR search tool"""
        print(f"🔍 Executing DR-only search")

        # ✅ Emit tool check events for UI
        self._emit_sync("tool_check_start", {})
        self._emit_sync("tool_check_complete", {
            "tools_needed": ["search_deficiency_records"]
        })

        # ✅ Emit tool start event
        self._emit_sync("tool_start", {
            "tool": "search_deficiency_records",
            "query": state["query"]
        })

        # Execute DR search
        from multi_agent_system.agent_tools import search_deficiency_records

        # Extract search query - use the full query
        search_query = state["query"]

        try:
            # Execute DR search tool
            dr_result = search_deficiency_records.invoke({"query": search_query})

            # ✅ Emit tool complete event
            results_count = len(dr_result.get("results", []))
            preview = f"Found {results_count} deficiency records"

            self._emit_sync("tool_complete", {
                "tool": "search_deficiency_records",
                "preview": preview,
                "result_count": results_count
            })

            # ✅ Emit tools execution complete event for UI
            self._emit_sync("tools_execution_complete", {
                "message": "DR search complete"
            })

            # Format as tool response for synthesis
            tool_response = {
                "tool": "search_deficiency_records",
                "result": dr_result,
                "answer": dr_result.get("answer", ""),
                "results_count": results_count
            }

            print(f"✅ DR search complete: {results_count} records found")

            return {
                **state,
                "tool_responses": [tool_response],
                "agent_responses": [],  # No specialist responses
                "current_step": "dr_search_complete",
                "tools_called": ["search_deficiency_records"]
            }

        except Exception as e:
            print(f"❌ DR search failed: {e}")

            # Return error state
            error_response = {
                "tool": "search_deficiency_records",
                "error": str(e),
                "answer": f"Error searching deficiency records: {str(e)}"
            }

            return {
                **state,
                "tool_responses": [error_response],
                "agent_responses": [],
                "current_step": "dr_search_failed",
                "tools_called": ["search_deficiency_records"]
            }
    
    def _planning_node(self, state: AgentState) -> AgentState:
        """Planning agent determines which specialists to consult"""
        query_lower = state["query"].lower()

        # ✅ Check if this is an OT form request or active OT conversation
        ot_form_keywords = ["overtime", "ot form", "fill form", "create form", "ot sheet", "overtime form"]
        ot_form_requested = any(keyword in query_lower for keyword in ot_form_keywords)
        ot_conversation_active = state.get("ot_conversation_active", False)

        # ✅ NEW: Detect if this is a re-plan (DR context added)
        is_replan = state.get("dr_replan_triggered", False) or "[Additional Context from DR Records]" in state["query"]

        print(f"🔍 Planning: query='{state['query'][:50]}...', ot_requested={ot_form_requested}, ot_active={ot_conversation_active}, is_replan={is_replan}")

        # ✅ If OT form conversation, skip specialist consultation and go straight to tools
        if ot_form_requested or ot_conversation_active:
            print(f"📝 OT form detected in planning - routing to tool check (requested={ot_form_requested}, active={ot_conversation_active})")
            return {
                **state,
                "agents_to_consult": [],  # No specialists needed for OT form
                "num_specialists_to_consult": 0,  # ✅ NEW
                "require_redteam": False,
                "current_step": "ot_form_routing",
                "messages": [HumanMessage(content=state["query"])],
                "tools_called": state.get("tools_called", []),
                "ot_conversation_state": state.get("ot_conversation_state"),  # ✅ PRESERVE state
                "ot_conversation_active": state.get("ot_conversation_active", False)  # ✅ PRESERVE active flag
            }

        # ✅ Use route_query_with_reasoning to get query classification and specialists
        if hasattr(self.planning_agent, 'route_query_with_reasoning'):
            planning_result = self.planning_agent.route_query_with_reasoning(state["query"])
            query_type = planning_result.get("query_type", "specialist")  # ✅ Get LLM's classification
            agents_to_consult = planning_result.get("agents", [])
            num_specialists = planning_result.get("num_specialists", len(agents_to_consult))
            reasoning = planning_result.get("reasoning", "")

            # ✅ NEW: Extract tool decision from Planning Agent (DeepSeek reasoning model)
            tools_needed_flag = planning_result.get("tools_needed", True)  # Default to True if not provided
            print(f"   Tools Needed (from Planning): {tools_needed_flag}")

            # ✅ DEBUG: Log planning result
            print(f"📋 Planning Result:")
            print(f"   Query Type: {query_type}")
            print(f"   Agents: {agents_to_consult}")
            print(f"   Num Specialists: {num_specialists}")
            print(f"   Reasoning: {reasoning[:100]}...")

            # ✅ Check if LLM determined this is a GENERAL query (highest priority - no specialists/tools)
            if query_type == "general":
                print(f"💬 Planning Agent classified as GENERAL query - skipping specialists and tools")
                return {
                    **state,
                    "agents_to_consult": [],
                    "num_specialists_to_consult": 0,
                    "require_redteam": False,
                    "is_general_query": True,  # ✅ Mark as general - will route directly to general handler
                    "current_step": "general_routing",
                    "messages": [HumanMessage(content=state["query"])],
                    "tools_called": state.get("tools_called", [])
                }

            # ✅ Check if LLM determined this is a DR-only query
            if query_type == "dr_only":
                print(f"🔍 Planning Agent classified as DR-only query - skipping specialists")
                return {
                    **state,
                    "agents_to_consult": [],
                    "num_specialists_to_consult": 0,
                    "require_redteam": False,
                    "is_dr_only_query": True,  # ✅ Mark as DR-only
                    "current_step": "dr_only_routing",
                    "messages": [HumanMessage(content=state["query"])],
                    "tools_called": state.get("tools_called", [])
                }
        else:
            agents_to_consult = self.planning_agent.route_query(state["query"])
            num_specialists = len(agents_to_consult)

        # ✅ Remove tools from agent list (mermaid and ot_form are tools, not agents)
        agents_to_consult = [a for a in agents_to_consult if a not in ["mermaid", "ot_form"]]

        # ✅ Update num_specialists if agents were filtered
        if num_specialists > len(agents_to_consult):
            num_specialists = len(agents_to_consult)

        # Determine if RedTeam review is needed
        require_redteam = any(word in query_lower for word in [
            "security", "vulnerability", "attack", "threat", "risk", "breach",
            "penetration", "exploit", "malware", "hack"
        ])

        # ✅ Initialize tools_called on first run
        tools_called = state.get("tools_called", [])

        print(f"🎯 Planning complete: {num_specialists} specialists selected from {len(agents_to_consult)} candidates")

        # ✅ NEW: Emit planning event if callback is set and this is a re-plan
        if self.event_callback and is_replan:
            try:
                # Get planning reasoning if available
                planning_reasoning = "Re-analyzing query with DR context..."
                if hasattr(self.planning_agent, 'route_query_with_reasoning'):
                    try:
                        planning_result = self.planning_agent.route_query_with_reasoning(state["query"])
                        planning_reasoning = planning_result.get("reasoning", planning_reasoning)
                    except:
                        pass

                self._emit_sync("replan_thoughts", {
                    "reasoning": planning_reasoning,
                    "agents": agents_to_consult,
                    "num_specialists": num_specialists,
                    "is_replan": True
                })
            except Exception as e:
                print(f"⚠️ Failed to emit replan thoughts: {e}")

        # ✅ NEW: Check if this is a general query (no specialists needed)
        is_general = len(agents_to_consult) == 0 and not ot_form_requested and not ot_conversation_active

        # ✅ NEW: Determine if tool check should be skipped based on Planning Agent's EXPLICIT decision
        # Trust the Planning Agent's reasoning (DeepSeek model) instead of keywords
        skip_tools = not tools_needed_flag if 'tools_needed_flag' in locals() else False

        print(f"🎯 Planning complete: skip_tool_check={skip_tools}, tools_needed_flag={tools_needed_flag if 'tools_needed_flag' in locals() else 'NOT SET'}")
        
        return {
            **state,
            "agents_to_consult": agents_to_consult,
            "num_specialists_to_consult": num_specialists,  # ✅ NEW: Store exact number
            "require_redteam": require_redteam,
            "current_step": "consulting_specialists",
            "messages": [HumanMessage(content=state["query"])],
            "tools_called": tools_called,
            "is_general_query": is_general,  # ✅ NEW: Mark general queries
            "skip_tool_check": skip_tools  # ✅ NEW: Follow Planning Agent's EXPLICIT tool decision
        }
        
    def _consult_specialists_node(self, state: AgentState) -> AgentState:
        """Consult primary specialist agents in parallel - LIMITED to num_specialists_to_consult"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        responses = []

        # ✅ If no actual agents to consult (only tools requested), skip
        if not state["agents_to_consult"] or len(state["agents_to_consult"]) == 0:
            print("⚠️ No specialist agents to consult - only tools will be used")
            return {
                **state,
                "agent_responses": responses,
                "current_step": "skipped_specialists"
            }

        # Only consult primary specialists
        # ✅ Filter out ALL tools and special agents
        primary_agents = [a for a in state["agents_to_consult"]
                        if a not in ["redteam", "dr", "inventory", "mermaid", "ot_form"]]

        if not primary_agents:
            print("⚠️ No primary specialists to consult")
            return {
                **state,
                "agent_responses": responses,
                "current_step": "no_specialists_needed"
            }

        # ✅ NEW: Limit to exact number of specialists requested by planning agent
        num_to_consult = state.get("num_specialists_to_consult", len(primary_agents))
        agents_to_query = primary_agents[:num_to_consult]  # Only take the first N

        print(f"👥 Consulting {len(agents_to_query)} specialist(s) out of {len(primary_agents)} available: {agents_to_query}")

        # ✅ NEW: Check if this is a re-consultation
        is_replan = "[Additional Context from DR Records]" in state["query"]

        # Consult primary agents IN PARALLEL
        def query_agent(agent_name):
            if agent_name in self.agent_map:
                # ✅ NEW: Emit agent start event during re-plan
                if self.event_callback and is_replan:
                    try:
                        self._emit_sync("replan_agent_start", {
                            "agent": agent_name,
                            "message": f"Re-querying {agent_name.title()} Specialist with DR context..."
                        })
                    except Exception as e:
                        print(f"⚠️ Failed to emit agent start: {e}")

                agent = self.agent_map[agent_name]
                # ✅ Pass use_deep_knowledge flag to agent
                use_deep = state.get("use_deep_knowledge", False)
                result = agent.query_knowledge(state["query"], use_deep_knowledge=use_deep)

                # ✅ NEW: Emit agent complete event during re-plan
                if self.event_callback and is_replan and result:
                    try:
                        preview = result["answer"][:200] + "..." if len(result["answer"]) > 200 else result["answer"]
                        self._emit_sync("replan_agent_complete", {
                            "agent": agent_name,
                            "preview": f"[Updated with DR context] {preview}",
                            "full_response": result["answer"]
                        })
                    except Exception as e:
                        print(f"⚠️ Failed to emit agent complete: {e}")

                return result
            else:
                print(f"⚠️ Agent '{agent_name}' not found in agent_map")
                return None

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(query_agent, name): name for name in agents_to_query}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    responses.append(result)

        return {
            **state,
            "agent_responses": responses,
            "current_step": "checking_tools"
        }


    
    def _check_tools_node(self, state: AgentState) -> AgentState:
        """Use LLM to determine if tools (DR, Inventory, Mermaid, OT Form) are needed"""

        # ✅ Emit tool check start event
        self._emit_sync("tool_check_start", {})

        # ✅✅ CRITICAL FIX: Check Planning Agent's EXPLICIT decision FIRST (before any other logic)
        if state.get("skip_tool_check", False):
            print("⚡ FAST PATH: Planning Agent said NO TOOLS NEEDED - skipping tool check entirely")
            dummy_response = AIMessage(content="Planning Agent determined no tools are needed.")
            self._emit_sync("tool_check_complete", {"tools_needed": []})
            return {
                **state,
                "messages": [dummy_response],
                "current_step": "tools_checked"
            }

        # ✅✅ SECOND CHECK: If planning agent said general query, skip immediately
        if state.get("is_general_query", False):
            print("⚡ FAST PATH: General query requires no tools")
            dummy_response = AIMessage(content="No tools needed for general query.")
            self._emit_sync("tool_check_complete", {"tools_needed": []})
            return {
                **state,
                "messages": [dummy_response],
                "current_step": "tools_checked"
            }

        # ✅✅ THIRD CHECK: If we're in a replan loop, skip tool checking
        if state.get("dr_replan_triggered"):
            print("⚡ FAST PATH: Replan loop - skipping additional tool calls")
            dummy_response = AIMessage(content="Proceeding without additional tool calls.")
            self._emit_sync("tool_check_complete", {"tools_needed": []})
            return {
                **state,
                "messages": [dummy_response],
                "current_step": "tools_checked",
                "dr_replan_triggered": False
            }

        # NOW check which tools have already been called
        tools_called = state.get("tools_called", [])
        print(f"🔍 Tools already called: {tools_called}")

        # Check if we're in an active OT conversation
        ot_conversation_active = state.get("ot_conversation_active", False)
        query_lower = state["query"].lower()

        # ✅ OT Form Multi-Turn Handling
        ot_form_keywords = ["overtime", "ot form", "fill form", "create form", "ot sheet", "overtime form"]
        ot_form_requested = any(keyword in query_lower for keyword in ot_form_keywords)

        # Start or continue OT conversation
        if ot_form_requested or ot_conversation_active:
            print(f"📝 OT form conversation: requested={ot_form_requested}, active={ot_conversation_active}")
            
            # Load conversation state if exists
            if state.get("ot_conversation_state"):
                print(f"   Loading state: {state['ot_conversation_state'].get('state', 'unknown')}")
                self.ot_conversation_manager.load_state_dict(state["ot_conversation_state"])
            else:
                print(f"   ⚠️ No state to load - starting fresh")

            # Process user input
            result = self.ot_conversation_manager.process_user_input(state["query"])
            response = AIMessage(content=result["message"])

            # Check if ready to call the tool
            if result.get("ready_for_tool", False):
                tool_call = {
                    "name": "fill_overtime_form",
                    "args": {"ot_data_json": result["tool_data"]},
                    "id": f"call_{int(time.time())}"
                }
                response.tool_calls = [tool_call]

                self._emit_sync("tool_check_complete", {"tools_needed": ["fill_overtime_form"]})
                return {
                    **state,
                    "messages": [response],
                    "current_step": "tools_checked",
                    "ot_conversation_active": False,
                    "ot_conversation_state": None,
                    "tools_called": tools_called
                }
            else:
                # Continue conversation - save state
                self._emit_sync("tool_check_complete", {"tools_needed": []})
                return {
                    **state,
                    "messages": [response],
                    "current_step": "tools_checked",
                    "ot_conversation_active": True,
                    "ot_conversation_state": self.ot_conversation_manager.get_state_dict(),
                    "tools_called": tools_called
                }

        # Check remaining tools
        all_tools = ["search_deficiency_records", "search_inventory", "create_diagram", "fill_overtime_form"]
        remaining_tools = [t for t in all_tools if t not in tools_called]

        if not remaining_tools:
            print("⚠️ All tools already called - skipping tool check")
            dummy_response = AIMessage(content="All available tools have been consulted.")
            self._emit_sync("tool_check_complete", {"tools_needed": []})
            return {
                **state,
                "messages": [dummy_response],
                "current_step": "tools_checked"
            }

        # ✅ FALLBACK: Strong DR keyword check (before expensive LLM call)
        dr_keywords = ["dr", "deficiency", "defect", "deficiency record", "find dr", "search dr", "show dr"]
        looks_like_dr_query = any(keyword in query_lower for keyword in dr_keywords)
        
        if looks_like_dr_query and "search_deficiency_records" in remaining_tools:
            print("🔍 FALLBACK: Query contains DR keywords - forcing DR tool call")
            tool_call = {
                "name": "search_deficiency_records",
                "args": {"query": state["query"]},
                "id": f"call_dr_fallback_{int(time.time())}"
            }
            response = AIMessage(content="Searching deficiency records based on query keywords.")
            response.tool_calls = [tool_call]

            self._emit_sync("tool_check_complete", {"tools_needed": ["search_deficiency_records"]})
            return {
                **state,
                "messages": [response],
                "current_step": "tools_checked"
            }

        # ✅ Fast heuristic check for ANY tool keywords
        needs_llm_check = False
        inventory_keywords = ["inventory", "part", "component", "stock", "part number"]
        diagram_keywords = ["diagram", "visualize", "flow", "draw", "chart", "flowchart", "show"]

        if any(kw in query_lower for kw in dr_keywords):
            needs_llm_check = True
        elif any(kw in query_lower for kw in inventory_keywords):
            needs_llm_check = True
        elif any(kw in query_lower for kw in diagram_keywords):
            needs_llm_check = True

        # ✅✅ OPTIMIZATION: If no tool keywords AND Planning Agent didn't flag tools, skip LLM entirely
        if not needs_llm_check:
            print(f"⚡ FAST PATH: No tool keywords detected and Planning Agent didn't flag tools - skipping LLM call")
            dummy_response = AIMessage(content="No tools needed based on query analysis.")
            self._emit_sync("tool_check_complete", {"tools_needed": []})
            return {
                **state,
                "messages": [dummy_response],
                "current_step": "tools_checked"
            }

        # Only now do we call the LLM (if we really need to)
        print(f"🔧 LLM deciding on tools (remaining: {remaining_tools})")
        
        tool_check_prompt = f"""User Query: {state["query"]}

    Available Tools:
    - search_deficiency_records: Search for deficiency records (DR), known bugs, issues, defects, and problems.
    - search_inventory: Look up parts, components, and stock availability.
    - create_diagram: Generate Mermaid diagrams for visualization.
    - fill_overtime_form: Create and fill overtime forms.

    Based on the user's query, which tool (if any) should be called? Call ONLY ONE tool if needed."""

        messages = state["messages"] + [HumanMessage(content=tool_check_prompt)]

        # Create filtered tool list
        filtered_tools = [tool for tool in AVAILABLE_TOOLS if tool.name in remaining_tools]

        if not filtered_tools:
            dummy_response = AIMessage(content="No additional tools available.")
            self._emit_sync("tool_check_complete", {"tools_needed": []})
            return {
                **state,
                "messages": [dummy_response],
                "current_step": "tools_checked"
            }

        # Use temperature=0 for faster decisions
        fast_llm = self.base_llm.with_config({"temperature": 0.0})
        temp_llm = fast_llm.bind_tools(filtered_tools)

        try:
            response = temp_llm.invoke(messages)
        except Exception as e:
            print(f"⚠️ Tool check LLM call failed: {e}")
            dummy_response = AIMessage(content="Tool check skipped due to error.")
            self._emit_sync("tool_check_complete", {"tools_needed": []})
            return {
                **state,
                "messages": [dummy_response],
                "current_step": "tools_checked"
            }

        # Extract tools_needed for event
        tools_needed = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc.get('name', 'unknown')
                tools_needed.append(tool_name)
                print(f"   Tool selected: {tool_name}")

        self._emit_sync("tool_check_complete", {"tools_needed": tools_needed})
        return {
            **state,
            "messages": [response],
            "current_step": "tools_checked"
        }

    def _should_use_tools(self, state: AgentState) -> Literal["use_tools", "skip_tools"]:
        """Check if LLM decided to use any tools"""
        if state["messages"]:
            last_message = state["messages"][-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "use_tools"
        return "skip_tools"
    
    def _execute_tools_node(self, state: AgentState) -> AgentState:
        """Execute tools requested by LLM"""
        import time
        tool_responses = []
        dr_results_found = False
        dr_context = ""
        
        last_message = state["messages"][-1]
        
        # ✅ Get existing tools_called list
        tools_called = state.get("tools_called", []).copy()
        
        print(f"📋 Tools called before execution: {tools_called}")
        
        # ✅ Hard limit: Only execute if we have tool calls
        if not (hasattr(last_message, 'tool_calls') and last_message.tool_calls):
            print("⚠️ No tool calls to execute")
            return {
                **state,
                "tool_responses": tool_responses,
                "current_step": "tools_executed",
                "tools_called": tools_called
            }
        
        # ✅ Process ONLY the first tool call
        tool_call = last_message.tool_calls[0]
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        print(f"🔧 Attempting to execute tool: {tool_name}")
        
        # ✅ Check if already called
        if tool_name in tools_called:
            print(f"⚠️ Tool {tool_name} already called - SKIPPING")
            return {
                **state,
                "tool_responses": tool_responses,
                "current_step": "tools_executed",
                "tools_called": tools_called
            }
        
        # ✅ Execute the tool ONCE
        result = None
        if tool_name == "search_deficiency_records":
            print(f"✅ Executing DR search...")
            result = search_deficiency_records.invoke(tool_args)
            tool_responses.append(result)
            tools_called.append(tool_name)
            
            if result.get("results"):
                dr_results_found = True
                dr_context = result["answer"]
                for i, res in enumerate(result["results"][:3]):
                    dr_context += f"\n- {res.get('Issue Description', 'N/A')} (Status: {res.get('Status', 'N/A')})"
            
        elif tool_name == "search_inventory":
            print(f"✅ Executing inventory search...")
            result = search_inventory.invoke(tool_args)
            tool_responses.append(result)
            tools_called.append(tool_name)
            
        elif tool_name == "create_diagram":
            print(f"✅ Executing diagram creation...")
            context = "\n".join([
                f"{r['agent']}: {r['answer'][:200]}"
                for r in state["agent_responses"]
            ])
            tool_args["context"] = context
            result = create_diagram.invoke(tool_args)
            tool_responses.append(result)
            tools_called.append(tool_name)
        
        # ✅ ADD: Handle fill_overtime_form tool
        elif tool_name == "fill_overtime_form":
            print(f"✅ Executing OT form fill...")
            result = fill_overtime_form.invoke(tool_args)
            tool_responses.append(result)
            tools_called.append(tool_name)
        
        else:
            print(f"⚠️ Unknown tool: {tool_name}")
            result = {
                "agent": "Unknown Tool",
                "error": f"Tool '{tool_name}' not recognized",
                "answer": f"Error: Tool '{tool_name}' is not available"
            }
            tool_responses.append(result)
        
        # Add tool message to conversation
        if result:
            state["messages"].append(
                ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                )
            )
        
        print(f"📋 Tools called after execution: {tools_called}")
        
        # ✅ DR replan logic (only if not already replanned)
        trigger_replan = False
        new_query = state["query"]

        print(f"🔍 DR replan check: dr_found={dr_results_found}, already_triggered={state.get('dr_replan_triggered')}, already_done={state.get('dr_replan_done')}")

        if (dr_results_found
            and not state.get("dr_replan_triggered")
            and not state.get("dr_replan_done")):

            other_agents = [a for a in state["agents_to_consult"] if a != "dr"]
            print(f"   Other agents to re-consult: {other_agents}")

            if other_agents:
                trigger_replan = True
                new_query = f"{state['query']}\n\n[Additional Context from DR Records]:\n{dr_context}"
                print(f"✅ Triggering DR replan - will loop back to planning")
            else:
                print(f"   No other agents - skipping DR replan")

        print(f"🔄 Returning from execute_tools: dr_replan_triggered={trigger_replan}")

        return {
            **state,
            "tool_responses": tool_responses,
            "current_step": "tools_executed",
            "dr_replan_triggered": trigger_replan,
            "dr_replan_done": True,
            "query": new_query,
            "tools_called": tools_called
        }


    
    def _should_consult_redteam(self, state: AgentState) -> Literal["redteam", "skip"]:
        """Decide whether to consult RedTeam agent"""
        print(f"🛡️ RedTeam check: require_redteam={state['require_redteam']}")
        if state["require_redteam"]:
            # Add RedTeam response to agent_responses
            response = self.redteam_agent.query_knowledge(state["query"])
            state["agent_responses"].append(response)
            print(f"   ✅ RedTeam consulted")
            return "redteam"
        print(f"   ⏭️ Skipping RedTeam")
        return "skip"
    
    def _redteam_node(self, state: AgentState) -> AgentState:
        """RedTeam agent security review (already added in conditional check)"""
        return {
            **state,
            "current_step": "redteam_reviewed"
        }
    
    def _synthesize_node(self, state: AgentState) -> AgentState:
        """
        Synthesizer combines insights from all specialists and tools.
        CRITICAL: Filters out irrelevant inputs based on original query.

        Note: For streaming synthesis, use _synthesize_streaming() instead.
        """
        print(f"📝 Synthesize node started")

        # ✅ Special handling for active OT conversations - skip synthesis
        if state.get("ot_conversation_active", False):
            # OT conversation is active - return the message directly without synthesis
            last_message = state["messages"][-1] if state["messages"] else AIMessage(content="Processing...")
            final_answer = last_message.content if hasattr(last_message, 'content') else str(last_message)

            return {
                **state,
                "final_answer": final_answer,
                "current_step": "complete"
            }

        # 1. Gather all raw data
        all_responses = state["agent_responses"] + state.get("tool_responses", [])

        # 2. Format inputs for the LLM
        specialist_context = self._format_specialist_context(all_responses)

        # 3. Construct synthesis prompt
        system_prompt = self._get_synthesis_system_prompt()
        user_content = self._get_synthesis_user_content(state["query"], specialist_context)

        # 4. Invoke Base LLM (no tools) to prevent hallucinations
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        response = self.base_llm.invoke(messages)
        final_answer = response.content

        return {
            **state,
            "final_answer": final_answer,
            "current_step": "complete"
        }

    def _format_specialist_context(self, all_responses: List[Dict[str, Any]]) -> str:
        """Format specialist responses into context string with intelligent truncation"""
        specialist_context = ""
        MAX_RESPONSE_LENGTH = 3000  # Max chars per response
        MAX_TOTAL_LENGTH = 50000    # Max total context length

        for i, resp in enumerate(all_responses):
            if isinstance(resp, dict):
                # ✅ Handle both agent responses and tool responses
                if "agent" in resp:
                    # Specialist agent response
                    agent_name = resp['agent']
                    answer = resp.get('answer', '')

                    # ✅ Truncate individual response if too long
                    if len(answer) > MAX_RESPONSE_LENGTH:
                        answer = answer[:MAX_RESPONSE_LENGTH] + f"\n\n[... truncated {len(answer) - MAX_RESPONSE_LENGTH} chars for brevity ...]"

                    specialist_context += f"\n--- Source: {agent_name} ---\n{answer}\n"

                    # If this is a DR tool response with results, include the details (with limits)
                    if resp.get('results') and agent_name == 'DR Agent':
                        specialist_context += "\nDeficiency Record Details:\n"
                        # ✅ Limit to first 5 DR records to avoid overflow
                        for idx, dr in enumerate(resp['results'][:5], 1):
                            specialist_context += f"\n{idx}. DR#{dr.get('DeficiencyNumber', 'N/A')}"
                            specialist_context += f"\n   Issue: {dr.get('Issue Description', 'N/A')}"
                            specialist_context += f"\n   System: {dr.get('System', 'N/A')}"
                            specialist_context += f"\n   Status: {dr.get('Status', 'N/A')}"
                            specialist_context += f"\n   Resource: {dr.get('Resource', 'N/A')}"
                            if dr.get('ActionTaken'):
                                action_preview = str(dr['ActionTaken'])[:200] + "..." if len(str(dr.get('ActionTaken', ''))) > 200 else str(dr.get('ActionTaken', ''))
                                specialist_context += f"\n   Action Taken: {action_preview}"
                            specialist_context += "\n"

                        # Show count if more records exist
                        if len(resp['results']) > 5:
                            specialist_context += f"\n... and {len(resp['results']) - 5} more records\n"

                elif "tool" in resp:
                    # ✅ Tool response (DR search, inventory, etc.)
                    tool_name = resp['tool']
                    result = resp.get('result', {})

                    # Get answer from result
                    answer = result.get('answer', resp.get('answer', ''))

                    # ✅ Truncate if too long
                    if len(answer) > MAX_RESPONSE_LENGTH:
                        answer = answer[:MAX_RESPONSE_LENGTH] + f"\n\n[... truncated {len(answer) - MAX_RESPONSE_LENGTH} chars for brevity ...]"

                    specialist_context += f"\n--- Tool: {tool_name} ---\n{answer}\n"

                    # ✅ Include DR details if this is a DR search tool
                    if tool_name == "search_deficiency_records" and result.get('results'):
                        specialist_context += "\nDeficiency Record Details:\n"
                        # ✅ Limit to first 5 DR records
                        for idx, dr in enumerate(result['results'][:5], 1):
                            specialist_context += f"\n{idx}. DR#{dr.get('DeficiencyNumber', 'N/A')}"
                            specialist_context += f"\n   Issue: {dr.get('Issue Description', 'N/A')}"
                            specialist_context += f"\n   System: {dr.get('System', 'N/A')}"
                            specialist_context += f"\n   Status: {dr.get('Status', 'N/A')}"
                            specialist_context += f"\n   Resource: {dr.get('Resource', 'N/A')}"
                            if dr.get('ActionTaken'):
                                action_preview = str(dr['ActionTaken'])[:200] + "..." if len(str(dr.get('ActionTaken', ''))) > 200 else str(dr.get('ActionTaken', ''))
                                specialist_context += f"\n   Action Taken: {action_preview}"
                            specialist_context += "\n"

                        # Show count if more records exist
                        if len(result['results']) > 5:
                            specialist_context += f"\n... and {len(result['results']) - 5} more records\n"

                else:
                    # Unknown response format
                    resp_str = str(resp)
                    if len(resp_str) > MAX_RESPONSE_LENGTH:
                        resp_str = resp_str[:MAX_RESPONSE_LENGTH] + "\n[... truncated ...]"
                    specialist_context += f"\n--- Source: Unknown ---\n{resp_str}\n"
            else:
                # Truncate other responses too
                resp_str = str(resp)
                if len(resp_str) > MAX_RESPONSE_LENGTH:
                    resp_str = resp_str[:MAX_RESPONSE_LENGTH] + "\n[... truncated ...]"
                specialist_context += f"\n--- Source: Tool/Other ---\n{resp_str}\n"
            
            # ✅ Check total length and stop if exceeding limit
            if len(specialist_context) > MAX_TOTAL_LENGTH:
                specialist_context = specialist_context[:MAX_TOTAL_LENGTH]
                specialist_context += f"\n\n[... {len(all_responses) - i - 1} more responses truncated to fit context limit ...]"
                break

        return specialist_context

    def _get_synthesis_system_prompt(self) -> str:
        """Get system prompt for synthesis"""
        return """You are a Technical Synthesis Agent.
Your goal is to answer the user's query by synthesizing provided specialist reports.

CRITICAL INSTRUCTIONS:
1. REVIEW the User Query carefully.
2. ANALYZE all Specialist/Tool Responses.
3. FILTER: If a specialist returned information that is generic, "no issues found", or irrelevant to the specific User Query, DISCARD IT.
   - Example: If user asks about "UI", and Motion Specialist says "No motion faults", do not include "No motion faults" in the final answer unless relevant context requires it.
4. REWRITE: Combine the remaining relevant points into a single, cohesive, professional response. Do not just list bullet points by agent name unless necessary for clarity.
5. If the user query was a question, answer it directly.
"""

    def _get_synthesis_user_content(self, query: str, specialist_context: str) -> str:
        """Get user content for synthesis"""
        return f"""
User Query: {query}

Specialist/Tool Responses:
{specialist_context}

Please provide the final synthesized response:
"""

    def synthesize_streaming(self, query: str, all_responses: List[Dict[str, Any]]):
        """
        Stream synthesis tokens as they're generated

        Args:
            query: User query
            all_responses: List of agent and tool responses

        Yields:
            Tokens as they're generated by the LLM
        """
        # Format context
        specialist_context = self._format_specialist_context(all_responses)

        # Build messages
        system_prompt = self._get_synthesis_system_prompt()
        user_content = self._get_synthesis_user_content(query, specialist_context)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        # Stream response
        for chunk in self.base_llm.stream(messages):
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content
    
    def query(self, question: str, previous_state: Optional[Dict[str, Any]] = None, use_deep_knowledge: bool = False, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a query through the multi-agent system

        Args:
            question: User query
            previous_state: Optional previous state (for continuing OT conversations)
            use_deep_knowledge: Enable graph-based retrieval for deeper context (slower but more comprehensive)
            config: Optional LangGraph config with thread_id for conversation memory
        """
        # ✅ NEW: Check cache first (skip for OT conversations)
        if self.cache_enabled and not previous_state:
            cached_response = self.cache.get(question)
            if cached_response:
                print(f"✅ Cache HIT for query: '{question[:50]}...'")
                # Add cache metadata to response
                cached_response["from_cache"] = True
                cached_response["cache_stats"] = self.cache.get_stats()
                return cached_response
            else:
                print(f"❌ Cache MISS for query: '{question[:50]}...'")

        # ✅ DEBUG: Log what we receive
        print(f"🔍 query() received previous_state: {previous_state}")
        if previous_state:
            print(f"   Keys: {previous_state.keys()}")
            print(f"   ot_conversation_active: {previous_state.get('ot_conversation_active')}")

        print(f"🧠 Deep Knowledge Mode: {'ENABLED' if use_deep_knowledge else 'DISABLED'}")
        print(f"🧵 Memory Config: {config}")

        initial_state = AgentState(
            query=question,
            messages=[],
            agents_to_consult=[],
            num_specialists_to_consult=0,  # ✅ NEW: Initialize to 0
            agent_responses=[],
            tool_responses=[],
            final_answer="",
            current_step="planning",
            require_redteam=False,
            dr_replan_triggered=False,
            dr_replan_done=False,
            tools_called=[],  # ✅ Initialize empty tools tracker
            ot_conversation_state=previous_state.get("ot_conversation_state") if previous_state else None,  # ✅ NEW
            ot_conversation_active=previous_state.get("ot_conversation_active", False) if previous_state else False,  # ✅ NEW
            is_general_query=False,  # ✅ NEW: Initialize general query flag
            use_deep_knowledge=use_deep_knowledge  # ✅ NEW: Pass deep knowledge flag
        )

        # Run the graph with memory config
        # ✅ NEW: Pass config to enable conversation memory via thread_id
        result = self.graph.invoke(initial_state, config=config) if config else self.graph.invoke(initial_state)

        # Extract agent and tool names
        agents_consulted = [r["agent"] for r in result["agent_responses"]]
        tools_used = result.get("tools_called", [])  # ✅ Use the tracker instead

        response = {
            "query": question,
            "agents_consulted": agents_consulted,
            "tools_used": tools_used,
            "agent_responses": result["agent_responses"],
            "tool_responses": result.get("tool_responses", []),
            "final_answer": result["final_answer"],
            "redteam_reviewed": result["require_redteam"],
            "ot_conversation_state": result.get("ot_conversation_state"),  # ✅ NEW: For multi-turn
            "ot_conversation_active": result.get("ot_conversation_active", False),  # ✅ NEW: For multi-turn
            "from_cache": False
        }

        # ✅ NEW: Cache the response (skip OT conversations and error states)
        if self.cache_enabled and not previous_state and not result.get("ot_conversation_active"):
            # Only cache successful responses
            if result["final_answer"] and not result["final_answer"].startswith("Error"):
                self.cache.set(question, response)
                print(f"💾 Cached response for query: '{question[:50]}...'")

        return response