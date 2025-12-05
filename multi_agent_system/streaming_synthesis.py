"""
Streaming synthesis implementation for real-time response generation
"""

import asyncio
from typing import Dict, Any, List, AsyncGenerator
from langchain_core.messages import SystemMessage, HumanMessage


class StreamingSynthesizer:
    """
    Handles streaming synthesis of agent responses without waiting for full completion
    """

    def __init__(self, system):
        """
        Initialize streaming synthesizer

        Args:
            system: MultiAgentSystem instance
        """
        self.system = system

    async def partial_synthesis_stream(
        self,
        query: str,
        agent_responses: List[Dict[str, Any]],
        tool_responses: List[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream partial synthesis as agent responses arrive

        This allows starting synthesis before all agents complete,
        providing faster time-to-first-token.

        Args:
            query: User query
            agent_responses: List of agent responses (may be incomplete)
            tool_responses: List of tool responses (optional)

        Yields:
            Synthesis tokens as they're generated
        """
        # Combine available responses
        all_responses = agent_responses.copy()
        if tool_responses:
            all_responses.extend(tool_responses)

        # Early return if no responses
        if not all_responses:
            yield "Processing your query..."
            return

        # Format context from available responses
        specialist_context = self.system._format_specialist_context(all_responses)

        # Build synthesis messages
        system_prompt = self._get_partial_synthesis_prompt()
        user_content = f"""
User Query: {query}

Available Specialist Responses (synthesis in progress):
{specialist_context}

Provide a response based on the information available so far. More details may follow.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        # Stream the synthesis
        try:
            for chunk in self.system.base_llm.stream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
                    # Small delay to prevent overwhelming
                    await asyncio.sleep(0.001)
        except Exception as e:
            yield f"\n\n[Synthesis error: {str(e)}]"

    def _get_partial_synthesis_prompt(self) -> str:
        """Get system prompt for partial synthesis"""
        return """You are a Technical Synthesis Agent providing real-time analysis.

INSTRUCTIONS:
1. Synthesize the information from available specialist reports
2. If information is incomplete, provide what you know and indicate more details may follow
3. Be concise and focus on answering the user's question with available data
4. Filter out irrelevant or "no issues found" responses
5. If only partial information is available, acknowledge this briefly

IMPORTANT: You're providing a streaming response. Start with what you know.
"""

    async def incremental_synthesis_stream(
        self,
        query: str,
        response_queue: asyncio.Queue
    ) -> AsyncGenerator[str, None]:
        """
        Stream synthesis incrementally as agent responses arrive via queue

        Args:
            query: User query
            response_queue: Async queue receiving agent responses in real-time

        Yields:
            Synthesis tokens as they're generated
        """
        collected_responses = []
        synthesis_started = False

        while True:
            try:
                # Wait for next response with timeout
                response = await asyncio.wait_for(response_queue.get(), timeout=0.5)

                # Check for completion signal
                if response is None:
                    break

                collected_responses.append(response)

                # Start synthesis after first response or when we have 2+ responses
                if not synthesis_started and len(collected_responses) >= 1:
                    synthesis_started = True

                    # Stream synthesis with current responses
                    async for token in self.partial_synthesis_stream(query, collected_responses):
                        yield token

            except asyncio.TimeoutError:
                # No new responses, continue waiting
                continue
            except Exception as e:
                yield f"\n\n[Error: {str(e)}]"
                break


async def stream_with_early_synthesis(
    system,
    query: str,
    emit_event_callback=None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Execute query with streaming synthesis that starts before all agents complete

    This provides faster perceived response time by starting synthesis
    as soon as the first few agents return results.

    Args:
        system: MultiAgentSystem instance
        query: User query
        emit_event_callback: Optional callback for event emission

    Yields:
        Event dictionaries with streaming updates
    """
    import time

    # Planning phase
    if emit_event_callback:
        await emit_event_callback("planning_start", {
            "message": "Analyzing query..."
        })

    planning_result = await asyncio.to_thread(
        system.planning_agent.route_query_with_reasoning,
        query
    )

    agents_to_consult = planning_result.get("agents", [])

    if emit_event_callback:
        await emit_event_callback("planning_complete", {
            "agents_to_consult": agents_to_consult,
            "reasoning": planning_result.get("reasoning", "")
        })

    # Consultation phase - collect responses
    agent_responses = []
    response_queue = asyncio.Queue()

    async def collect_agent_response(agent_name):
        """Query agent and add to queue"""
        if agent_name in system.agent_map:
            result = await asyncio.to_thread(
                system.agent_map[agent_name].query_knowledge,
                query
            )
            agent_responses.append(result)
            await response_queue.put(result)

            if emit_event_callback:
                await emit_event_callback("agent_complete", {
                    "agent": agent_name,
                    "preview": result["answer"][:200]
                })

    # Start all agent queries in parallel
    primary_agents = [a for a in agents_to_consult if a not in ["redteam", "dr", "inventory", "mermaid", "ot_form"]]

    if primary_agents:
        if emit_event_callback:
            await emit_event_callback("consultation_start", {
                "message": f"Consulting {len(primary_agents)} specialists...",
                "agents": primary_agents
            })

        # Launch all agent queries
        tasks = [collect_agent_response(agent) for agent in primary_agents]
        asyncio.gather(*tasks, return_exceptions=True)  # Fire and forget

        # Start streaming synthesis as responses arrive
        if emit_event_callback:
            await emit_event_callback("synthesis_start", {
                "message": "Streaming synthesis as results arrive...",
                "mode": "early_synthesis"
            })

        synthesizer = StreamingSynthesizer(system)
        token_count = 0

        # Wait for at least one response before starting synthesis
        first_response = await response_queue.get()
        agent_responses.append(first_response)

        # Stream synthesis with incremental updates
        async for token in synthesizer.partial_synthesis_stream(query, agent_responses):
            token_count += 1

            if emit_event_callback and token_count % 10 == 0:
                await emit_event_callback("synthesis_progress", {
                    "token": token,
                    "token_count": token_count
                })

            yield {
                "event_type": "synthesis_token",
                "timestamp": time.time(),
                "data": {
                    "token": token,
                    "token_count": token_count
                }
            }

        # Signal completion
        await response_queue.put(None)

        if emit_event_callback:
            await emit_event_callback("synthesis_complete", {
                "message": "Response generated",
                "total_tokens": token_count
            })

    else:
        # No specialists needed - handle as general query
        if emit_event_callback:
            await emit_event_callback("synthesis_start", {
                "message": "Generating response...",
                "mode": "general"
            })

        answer = system.general_agent.answer_query(query)

        yield {
            "event_type": "complete",
            "timestamp": time.time(),
            "data": {
                "final_answer": answer,
                "agents_consulted": [],
                "tools_used": [],
                "mode": "general"
            }
        }
