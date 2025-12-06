"""
FastAPI Server for Multi-Agent System with Detailed Streaming
Provides real-time updates for each workflow step for flowing thinking UI
"""

import os
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import asyncio
import json
from datetime import datetime
import uuid
from jose import JWTError, jwt  # ✅ NEW: JWT validation for authentication

from graph import MultiAgentSystem
from optimizations.streaming.streaming_synthesis import stream_with_early_synthesis
from langgraph.checkpoint.memory import InMemorySaver  # ✅ NEW: Memory for conversation context

load_dotenv()

# ✅ NEW: JWT Configuration (must match auth_server.py)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_SUPER_SECRET")
ALGORITHM = "HS256"

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Agent System API",
    description="LangGraph-based multi-agent orchestration with Morphik - Real-time streaming",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add static file serving for OT forms
from fastapi.staticfiles import StaticFiles
ot_files_path = os.path.join(os.path.dirname(__file__), "ot_apps")
if os.path.exists(ot_files_path):
    app.mount("/files/ot_apps", StaticFiles(directory=ot_files_path), name="ot_files")

# Global system instance
system: Optional[MultiAgentSystem] = None

# ✅ NEW: Global memory checkpointer for conversation context
memory_checkpointer: Optional[InMemorySaver] = None

# ✅ NEW: JWT validation function
def verify_jwt_token(token: str) -> Optional[str]:
    """
    Verify JWT token and extract username

    Args:
        token: JWT token string

    Returns:
        Username if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError as e:
        print(f"❌ JWT validation failed: {e}")
        return None

# Request/Response Models
class QueryRequest(BaseModel):
    query: str = Field(..., description="User query to process", min_length=1)
    include_trace: bool = Field(default=False, description="Include detailed execution trace")
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are the common interface issues in the system?",
                "include_trace": True
            }
        }

class AgentResponse(BaseModel):
    agent: str
    answer: str
    
class QueryResponse(BaseModel):
    query_id: str
    query: str
    final_answer: str
    agents_consulted: List[str]
    tools_used: List[str]
    redteam_reviewed: bool
    execution_time: float
    timestamp: str
    agent_responses: Optional[List[AgentResponse]] = None
    tool_responses: Optional[List[Any]] = None

class HealthResponse(BaseModel):
    status: str
    morphik_uri: str
    model: str
    timestamp: str

class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: str

# Streaming Event Models for Frontend
class StreamEvent(BaseModel):
    event_type: str  # 'planning', 'routing', 'agent_start', 'agent_complete', 'tool_call', 'tool_result', 'redteam', 'synthesis', 'complete', 'error'
    timestamp: float
    data: Dict[str, Any]

# Custom Multi-Agent System Wrapper with Hooks
class StreamingMultiAgentSystem:
    """Wrapper around MultiAgentSystem that emits events during execution"""
    
    def __init__(self, system: MultiAgentSystem):
        self.system = system
        self.event_queue = asyncio.Queue()

        # ✅ NEW: Set callback on the system to receive events from graph
        self.system.event_callback = self.emit_event

        # ✅ NEW: Store event loop reference for thread-safe emission
        try:
            self.system.event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # Will be set later when query_with_streaming is called
            self.system.event_loop = None

    async def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to the queue"""
        event = {
            "event_type": event_type,
            "timestamp": time.time(),
            "data": data
        }
        await self.event_queue.put(event)
    
    # Key fixes in StreamingMultiAgentSystem.query_with_streaming()

    async def query_with_streaming(self, question: str, previous_state: Optional[Dict[str, Any]] = None, use_deep_knowledge: bool = False, config: Optional[Dict[str, Any]] = None):
        """
        Execute query with streaming events

        Args:
            question: User query
            previous_state: Optional previous state for multi-turn conversations (e.g., OT form)
            use_deep_knowledge: Enable graph-based retrieval for deeper context (slower but more comprehensive)
            config: Optional LangGraph config with thread_id for conversation memory
        """

        # ✅ NEW: Ensure event loop is set for graph callbacks
        if not self.system.event_loop:
            self.system.event_loop = asyncio.get_running_loop()

        # ✅ DEBUG: Log what streaming receives
        print(f"🎬 query_with_streaming received previous_state: {previous_state}")
        print(f"🧠 Deep Knowledge Mode: {'ENABLED' if use_deep_knowledge else 'DISABLED'}")
        print(f"🧵 Config: {config}")

        # ✅ CHECK: If OT conversation is active, skip streaming's planning/consultation
        # and go straight to system.query() which handles OT multi-turn properly
        ot_conversation_active = False
        if previous_state:
            ot_conversation_active = previous_state.get("ot_conversation_active", False)

        query_lower = question.lower()
        ot_form_keywords = ["overtime", "ot form", "fill form", "create form", "ot sheet"]
        ot_form_requested = any(keyword in query_lower for keyword in ot_form_keywords)

        if ot_conversation_active or ot_form_requested:
            # OT conversation - skip streaming's planning/consultation, go straight to system.query
            print(f"🎬 OT conversation active - bypassing streaming planning")
            await self.emit_event("planning_start", {
                "message": "Processing OT form conversation..."
            })
            await self.emit_event("planning_complete", {
                "agents_to_consult": [],
                "require_redteam": False,
                "reasoning": "OT form multi-turn conversation in progress",
                "message": "Continuing OT form conversation"
            })
            await self.emit_event("consultation_start", {
                "message": "No specialist consultation needed",
                "agents": [],
                "is_reloop": False
            })
            await self.emit_event("consultation_complete", {
                "message": "Skipped - OT form conversation",
                "agents": []
            })
            # Jump directly to tool checking phase below
        else:
            # Normal workflow - do planning and consultation
            # 1. PLANNING PHASE - STREAMING
            await self.emit_event("planning_start", {
                "message": "Analyzing query and determining workflow..."
            })

            planning_result = None
            planning_buffer = ""
            try:
                # Try streaming planning first
                if hasattr(self.system.planning_agent, 'route_query_with_reasoning_streaming'):
                    def stream_planning():
                        for chunk in self.system.planning_agent.route_query_with_reasoning_streaming(question):
                            yield chunk

                    for chunk in await asyncio.to_thread(lambda: list(stream_planning())):
                        if "token" in chunk:
                            # Stream individual planning tokens
                            planning_buffer += chunk["token"]
                            await self.emit_event("planning_progress", {
                                "token": chunk["token"],
                                "partial_response": chunk.get("partial_response", planning_buffer)
                            })
                        elif "complete" in chunk:
                            # Final planning result
                            planning_result = chunk

                    agents_to_consult = planning_result.get("agents", [])
                    planning_thoughts = planning_result.get("reasoning", "")
                elif hasattr(self.system.planning_agent, 'route_query_with_reasoning'):
                    # Non-streaming version
                    planning_result = await asyncio.to_thread(
                        self.system.planning_agent.route_query_with_reasoning,
                        question
                    )
                    agents_to_consult = planning_result.get("agents", [])
                    planning_thoughts = planning_result.get("reasoning", "")
                else:
                    # Fallback to basic routing
                    agents_to_consult = await asyncio.to_thread(
                        self.system.planning_agent.route_query,
                        question
                    )
                    planning_thoughts = f"Query analysis: Identified need for {', '.join(agents_to_consult)} specialist(s)"
            except Exception as e:
                print(f"⚠️ Planning error: {e}")
                agents_to_consult = self.system.planning_agent.route_query(question)
                planning_thoughts = f"Standard routing applied based on query keywords"

            agents_to_consult = [a for a in agents_to_consult if a != "mermaid"]

            require_redteam = any(word in query_lower for word in [
                "security", "vulnerability", "attack", "threat", "risk", "breach",
                "penetration", "exploit", "malware", "hack"
            ])

            await self.emit_event("planning_complete", {
                "agents_to_consult": agents_to_consult,
                "require_redteam": require_redteam,
                "reasoning": planning_thoughts,
                "message": f"Routing to {len(agents_to_consult)} specialist(s)",
                "full_response": planning_buffer if planning_buffer else planning_thoughts
            })

            # 2. SPECIALIST CONSULTATION PHASE
            has_dr_context = "[Additional Context from DR Records]" in question

            if not agents_to_consult:
                # Skip consultation phase entirely
                await self.emit_event("consultation_start", {
                    "message": "No specialist consultation needed",
                    "agents": [],
                    "is_reloop": False
                })

                await self.emit_event("consultation_complete", {
                    "message": "Skipped - proceeding directly to tool execution",
                    "agents": []
                })
            else:
                # ✅ NEW: Emit re-plan notification if DR context detected
                if has_dr_context:
                    await self.emit_event("replan_detected", {
                        "message": "DR context found - re-planning and re-consulting specialists",
                        "reason": "Additional deficiency records context available"
                    })

                    # ✅ Re-run planning to get updated thoughts
                    try:
                        if hasattr(self.system.planning_agent, 'route_query_with_reasoning'):
                            replan_result = await asyncio.to_thread(
                                self.system.planning_agent.route_query_with_reasoning,
                                question
                            )
                            replan_reasoning = replan_result.get("reasoning", "Re-analyzing with DR context...")

                            await self.emit_event("replan_thoughts", {
                                "reasoning": replan_reasoning,
                                "agents": replan_result.get("agents", agents_to_consult),
                                "num_specialists": replan_result.get("num_specialists", len(agents_to_consult))
                            })
                    except Exception as e:
                        print(f"⚠️ Failed to get re-plan reasoning: {e}")

                # Normal consultation flow
                consultation_message = "Consulting specialist agents..."
                if has_dr_context:
                    consultation_message = "Re-consulting specialists with DR context..."

                await self.emit_event("consultation_start", {
                    "message": consultation_message,
                    "agents": agents_to_consult,
                    "is_reloop": has_dr_context
                })

                agent_responses = []
                for agent_name in agents_to_consult:
                    if agent_name in ["redteam", "dr", "inventory", "mermaid", "ot_form"]:
                        continue

                    query_message = f"Querying {agent_name.title()} Specialist..."
                    if has_dr_context:
                        query_message = f"Re-querying {agent_name.title()} Specialist with DR context..."

                    await self.emit_event("agent_start", {
                        "agent": agent_name,
                        "message": query_message,
                        "is_reloop": has_dr_context
                    })

                    # Query the specialist with deep knowledge flag
                    result = await asyncio.to_thread(
                        self.system.agent_map[agent_name].query_knowledge,
                        question,
                        7,  # k parameter
                        use_deep_knowledge  # ✅ Pass deep knowledge flag
                    )

                    agent_responses.append(result)

                    # Stream the specialist's response in chunks (simulated streaming)
                    full_answer = result["answer"]
                    words = full_answer.split()
                    chunk_size = 10  # words per chunk

                    for i in range(0, len(words), chunk_size):
                        chunk = " ".join(words[i:i+chunk_size])
                        partial_answer = " ".join(words[:i+chunk_size])

                        await self.emit_event("agent_progress", {
                            "agent": agent_name,
                            "chunk": chunk,
                            "partial_response": partial_answer,
                            "progress": min(100, int((i+chunk_size) / len(words) * 100))
                        })

                        # Small delay to simulate streaming
                        await asyncio.sleep(0.05)

                    complete_message = result["answer"][:200] + "..." if len(result["answer"]) > 200 else result["answer"]
                    if has_dr_context:
                        complete_message = f"[Updated with DR context] {complete_message}"

                    await self.emit_event("agent_complete", {
                        "agent": agent_name,
                        "preview": complete_message,
                        "full_response": result["answer"],
                        "is_reloop": has_dr_context
                    })

                await self.emit_event("consultation_complete", {
                    "message": f"Consulted {len(agent_responses)} specialist(s)",
                    "agents": agents_to_consult
                })
        
        # 3. TOOL CHECKING PHASE
        await self.emit_event("tool_check_start", {
            "message": "Checking if additional tools are needed..."
        })

        # ✅ FIX: Execute full query but track what we've already shown
        # ✅ NEW: Pass previous_state for multi-turn conversations, use_deep_knowledge flag, and config for memory
        result = await asyncio.to_thread(self.system.query, question, previous_state, use_deep_knowledge, config)
        
        # ✅ FIX: Properly emit tool events
        tools_used = result.get("tools_used", [])
        
        if tools_used and len(tools_used) > 0:
            await self.emit_event("tool_check_complete", {
                "tools_needed": tools_used,
                "message": f"Executing {len(tools_used)} tool(s)"
            })
            
            # ✅ Emit each tool execution (with deduplication)
            tool_responses = result.get("tool_responses", [])
            emitted_tools = set()  # Track which tools we've already emitted
            
            for i, tool_resp in enumerate(tool_responses):
                tool_name = tool_resp.get("agent", f"Tool {i+1}")
                
                # ✅ Skip if we've already emitted this tool
                if tool_name in emitted_tools:
                    print(f"⚠️ Skipping duplicate tool event for: {tool_name}")
                    continue
                
                emitted_tools.add(tool_name)

                await self.emit_event("tool_start", {
                    "tool": tool_name,
                    "message": f"Executing {tool_name}..."
                })

                # Small delay for UI effect
                await asyncio.sleep(0.2)

                tool_result = str(tool_resp.get("answer", ""))

                # ✅ Special handling for different tool types
                preview = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
                result_count = None

                # DR Tool: Show count information
                if tool_name == "DR Agent" and "results" in tool_resp:
                    results_list = tool_resp.get("results", [])
                    if isinstance(results_list, list):
                        result_count = len(results_list)
                        preview = f"Found {result_count} deficiency records. {preview}"
                
                # Mermaid Tool: Show friendly message instead of raw code
                elif tool_name == "Mermaid Tool":
                    preview = "✓ Diagram generated successfully (see final response)"

                await self.emit_event("tool_complete", {
                    "tool": tool_name,
                    "preview": preview,
                    "full_result": tool_result,
                    "result_count": result_count  # ✅ NEW: Include count for frontend
                })
            
            # ✅ FIX: Emit tools execution complete
            await self.emit_event("tools_execution_complete", {
                "message": f"Completed {len(emitted_tools)} tool(s)",
                "tools": list(emitted_tools)
            })
        else:
            # ✅ FIX: Even if no tools, emit complete
            await self.emit_event("tool_check_complete", {
                "tools_needed": [],
                "message": "No additional tools required"
            })
            await self.emit_event("tools_execution_complete", {
                "message": "No tools required",
                "tools": []
            })
        
        # 4. REDTEAM PHASE
        if result.get("redteam_reviewed"):
            await self.emit_event("redteam_start", {
                "message": "Conducting security review..."
            })
            
            await asyncio.sleep(0.3)
            
            rt_response = next((r for r in result["agent_responses"] if r["agent"] == "Red Team Agent"), None)
            if rt_response:
                await self.emit_event("redteam_complete", {
                    "preview": rt_response["answer"][:200] + "...",
                    "full_response": rt_response["answer"]
                })
        
        # 5. SYNTHESIS PHASE - Stream tokens as they're generated
        synthesis_start_time = time.time()
        first_token_time = None

        await self.emit_event("synthesis_start", {
            "message": "Synthesizing final response...",
            "start_time": synthesis_start_time
        })

        # Get all responses for synthesis
        all_responses = result["agent_responses"] + result.get("tool_responses", [])

        # Stream synthesis tokens in real-time
        synthesis_buffer = ""
        token_count = 0

        try:
            # Stream synthesis
            for token in self.system.synthesize_streaming(question, all_responses):
                synthesis_buffer += token
                token_count += 1

                # Capture time to first token
                if token_count == 1:
                    first_token_time = time.time()

                # Emit synthesis progress every 5 tokens or when we hit punctuation
                if token_count % 5 == 0 or token in ['.', '!', '?', '\n']:
                    await self.emit_event("synthesis_progress", {
                        "token": token,
                        "partial_response": synthesis_buffer[-200:] if len(synthesis_buffer) > 200 else synthesis_buffer,
                        "token_count": token_count
                    })

                # Small delay to prevent overwhelming the client
                if token_count % 10 == 0:
                    await asyncio.sleep(0.01)

        except Exception as e:
            print(f"⚠️ Streaming synthesis failed, falling back to full response: {e}")
            # Fallback to non-streaming
            synthesis_buffer = result["final_answer"]

        synthesis_end_time = time.time()
        synthesis_duration = synthesis_end_time - synthesis_start_time
        time_to_first_token = (first_token_time - synthesis_start_time) if first_token_time else 0
        tokens_per_second = token_count / synthesis_duration if synthesis_duration > 0 else 0

        await self.emit_event("synthesis_complete", {
            "message": "Response ready",
            "total_tokens": token_count,
            "synthesis_duration": round(synthesis_duration, 2),
            "time_to_first_token": round(time_to_first_token, 3),
            "tokens_per_second": round(tokens_per_second, 1)
        })
        
        # 6. FINAL RESULT
        # Use streamed synthesis if available, otherwise use result's final_answer
        final_answer = synthesis_buffer if synthesis_buffer else result["final_answer"]

        await self.emit_event("complete", {
            "final_answer": final_answer,
            "agents_consulted": result["agents_consulted"],
            "tools_used": result.get("tools_used", []),
            "redteam_reviewed": result.get("redteam_reviewed", False),
            "ot_conversation_state": result.get("ot_conversation_state"),  # ✅ NEW: For multi-turn
            "ot_conversation_active": result.get("ot_conversation_active", False),  # ✅ NEW: For multi-turn
            "metadata": {
                "num_agents": len(result["agents_consulted"]),
                "num_tools": len(result.get("tools_used", [])),
                "synthesis_tokens": token_count if synthesis_buffer else 0,
                "streaming_synthesis": bool(synthesis_buffer),
                "synthesis_duration": round(synthesis_duration, 2),
                "time_to_first_token": round(time_to_first_token, 3),
                "tokens_per_second": round(tokens_per_second, 1)
            }
        })

        # Update result with streamed synthesis
        if synthesis_buffer:
            result["final_answer"] = synthesis_buffer

        return result

# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize the multi-agent system on startup"""
    global system, memory_checkpointer

    morphik_uri = os.getenv("MORPHIK_URI", "http://localhost:8000")
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY environment variable is required")

    try:
        # Initialize InMemorySaver for conversation context
        memory_checkpointer = InMemorySaver()
        print(f"✓ InMemorySaver initialized for conversation context")

        # Initialize MultiAgentSystem with checkpointer for memory
        system = MultiAgentSystem(
            morphik_uri=morphik_uri,
            openrouter_api_key=openrouter_api_key,
            checkpointer=memory_checkpointer  # ✅ NEW: Pass checkpointer for conversation memory
        )
        print(f"✓ Multi-Agent System initialized successfully")
        print(f"  - Morphik URI: {morphik_uri}")
        print(f"  - Model: {os.getenv('OPENROUTER_MODEL', 'x-ai/grok-4.1-fast:free')}")
        print(f"  - Memory: InMemorySaver (conversation context enabled)")
    except Exception as e:
        print(f"✗ Failed to initialize system: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global system
    system = None
    print("✓ Multi-Agent System shutdown complete")

# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Multi-Agent System API with Streaming",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws/query"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    return HealthResponse(
        status="healthy",
        morphik_uri=system.morphik_uri,
        model=os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast:free"),
        timestamp=datetime.utcnow().isoformat()
    )

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a query through the multi-agent system (non-streaming)
    
    Args:
        request: Query request with query text and options
        
    Returns:
        QueryResponse with final answer and execution details
    """
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        start_time = time.time()
        
        # Execute query
        result = await asyncio.to_thread(system.query, request.query)
        
        execution_time = time.time() - start_time
        
        # Build response
        response = QueryResponse(
            query_id=str(uuid.uuid4()),
            query=request.query,
            final_answer=result["final_answer"],
            agents_consulted=result["agents_consulted"],
            tools_used=result.get("tools_used", []),
            redteam_reviewed=result.get("redteam_reviewed", False),
            execution_time=round(execution_time, 2),
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Include trace if requested
        if request.include_trace:
            response.agent_responses = [
                AgentResponse(agent=r["agent"], answer=r["answer"])
                for r in result.get("agent_responses", [])
            ]
            response.tool_responses = result.get("tool_responses", [])
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )

@app.post("/query/stream")
async def process_query_stream(request: QueryRequest):
    """
    Stream query processing updates via Server-Sent Events
    Enhanced with detailed workflow steps
    """
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    async def event_generator():
        try:
            streaming_system = StreamingMultiAgentSystem(system)
            
            # Start query execution in background
            query_task = asyncio.create_task(
                streaming_system.query_with_streaming(request.query)
            )
            
            # Stream events as they arrive
            while not query_task.done():
                try:
                    event = await asyncio.wait_for(
                        streaming_system.event_queue.get(),
                        timeout=0.1
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    continue
            
            # Drain remaining events
            while not streaming_system.event_queue.empty():
                event = await streaming_system.event_queue.get()
                yield f"data: {json.dumps(event)}\n\n"
            
            # Ensure task completed successfully
            await query_task
            
        except Exception as e:
            error_event = {
                "event_type": "error",
                "timestamp": time.time(),
                "data": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@app.post("/query/stream-fast")
async def process_query_stream_fast(request: QueryRequest):
    """
    Stream query with EARLY SYNTHESIS - starts generating response
    before all agents complete for faster perceived performance

    This endpoint provides faster time-to-first-token by starting
    synthesis as soon as initial agent responses arrive.
    """
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    async def event_generator():
        try:
            # Stream with early synthesis
            async for event in stream_with_early_synthesis(system, request.query):
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            error_event = {
                "event_type": "error",
                "timestamp": time.time(),
                "data": {"error": str(e)}
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.websocket("/ws/query")
async def websocket_query(websocket: WebSocket):
    """
    WebSocket endpoint for real-time bidirectional communication
    Provides detailed workflow updates
    """
    await websocket.accept()
    
    if system is None:
        await websocket.send_json({
            "event_type": "error",
            "data": {"error": "System not initialized"}
        })
        await websocket.close()
        return
    
    try:
        while True:
            # Receive query from client
            data = await websocket.receive_json()
            query = data.get("query", "")
            previous_state = data.get("previous_state")  # ✅ Get previous state for multi-turn
            use_deep_knowledge = data.get("use_deep_knowledge", False)  # ✅ Get deep knowledge flag
            jwt_token = data.get("token")  # ✅ NEW: Get JWT token for authentication

            # ✅ NEW: Validate JWT token and extract username
            if not jwt_token:
                await websocket.send_json({
                    "event_type": "error",
                    "data": {"error": "Authentication required. Please log in."}
                })
                await websocket.close()
                return

            username = verify_jwt_token(jwt_token)
            if not username:
                await websocket.send_json({
                    "event_type": "error",
                    "data": {"error": "Invalid or expired token. Please log in again."}
                })
                await websocket.close()
                return

            # ✅ NEW: Get thread_id from frontend (or fallback to generate one)
            # Frontend sends persistent thread_id for conversation continuity
            thread_id = data.get("thread_id")
            if not thread_id:
                # Fallback: generate thread_id if not provided
                timestamp = int(time.time())
                thread_id = f"thread_{username}_{timestamp}"
                print(f"⚠️ No thread_id from frontend, generated: {thread_id}")

            print(f"🔐 Authenticated user: {username}")
            print(f"🧵 Using thread_id: {thread_id}")

            # ✅ DEBUG: Log what WebSocket receives
            print(f"🌐 WebSocket received data keys: {data.keys()}")
            print(f"   query: {query[:50]}...")
            print(f"   username: {username}")
            print(f"   thread_id: {thread_id}")
            print(f"   previous_state: {previous_state}")
            print(f"   use_deep_knowledge: {use_deep_knowledge}")

            if not query:
                await websocket.send_json({
                    "event_type": "error",
                    "data": {"error": "Query is required"}
                })
                continue

            # ✅ NEW: Create LangGraph config with thread_id for memory isolation
            config = {"configurable": {"thread_id": thread_id}}
            print(f"🧵 Using thread_id for conversation context: {thread_id}")

            # Create streaming system
            streaming_system = StreamingMultiAgentSystem(system)

            # Start query execution with previous state, deep knowledge flag, and memory config
            query_task = asyncio.create_task(
                streaming_system.query_with_streaming(query, previous_state, use_deep_knowledge, config)
            )
            
            # Stream events to client
            while not query_task.done():
                try:
                    event = await asyncio.wait_for(
                        streaming_system.event_queue.get(),
                        timeout=0.1
                    )
                    await websocket.send_json(event)
                except asyncio.TimeoutError:
                    continue
            
            # Drain remaining events
            while not streaming_system.event_queue.empty():
                event = await streaming_system.event_queue.get()
                await websocket.send_json(event)
            
            # Ensure task completed
            await query_task
            
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        await websocket.send_json({
            "event_type": "error",
            "data": {"error": str(e)}
        })
        await websocket.close()

@app.get("/agents", response_model=Dict[str, List[str]])
async def list_agents():
    """List all available agents in the system"""
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    return {
        "specialists": list(system.agent_map.keys()),
        "tools": ["search_deficiency_records", "search_inventory", "create_diagram"],
        "special": ["planning", "redteam", "synthesizer"]
    }

@app.get("/models", response_model=Dict[str, str])
async def list_models():
    """Get current model configuration"""
    return {
        "current_model": os.getenv("OPENROUTER_MODEL", "x-ai/grok-4.1-fast:free"),
        "provider": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1"
    }

@app.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_stats():
    """Get cache statistics"""
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    if not system.cache_enabled:
        return {
            "enabled": False,
            "message": "Caching is disabled"
        }

    return {
        "enabled": True,
        **system.cache.get_stats()
    }

@app.get("/cache/queries", response_model=Dict[str, Any])
async def list_cached_queries():
    """List all cached queries"""
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    if not system.cache_enabled:
        raise HTTPException(status_code=400, detail="Caching is disabled")

    return {
        "cached_queries": system.cache.get_cached_queries()
    }

@app.delete("/cache/clear")
async def clear_cache():
    """Clear all cached responses"""
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    if not system.cache_enabled:
        raise HTTPException(status_code=400, detail="Caching is disabled")

    system.cache.clear()

    return {
        "status": "success",
        "message": "Cache cleared successfully"
    }

@app.delete("/cache/invalidate")
async def invalidate_cache_entry(query: str):
    """Invalidate a specific cached query"""
    if system is None:
        raise HTTPException(status_code=503, detail="System not initialized")

    if not system.cache_enabled:
        raise HTTPException(status_code=400, detail="Caching is disabled")

    success = system.cache.invalidate(query)

    if success:
        return {
            "status": "success",
            "message": f"Cache entry for query '{query}' invalidated"
        }
    else:
        return {
            "status": "not_found",
            "message": f"No cache entry found for query '{query}'"
        }

# Error Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return ErrorResponse(
        error=exc.detail,
        detail=str(exc.status_code),
        timestamp=datetime.utcnow().isoformat()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    return ErrorResponse(
        error="Internal server error",
        detail=str(exc),
        timestamp=datetime.utcnow().isoformat()
    )

# Run with: uvicorn server:app --reload --host 0.0.0.0 --port 8082
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8082))
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║        🚀 Multi-Agent System FastAPI Server v2.0            ║
║           Real-time Streaming & WebSocket Support           ║
║                                                              ║
║  HTTP:      http://0.0.0.0:{port}                            ║
║  WebSocket: ws://0.0.0.0:{port}/ws/query                     ║
║  Docs:      http://0.0.0.0:{port}/docs                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )