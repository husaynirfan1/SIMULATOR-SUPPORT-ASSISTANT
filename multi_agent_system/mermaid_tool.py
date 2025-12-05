"""
Mermaid diagram generation tool using LLM
Calls LM Studio's OpenAI-compatible API directly
"""

from openai import OpenAI
import os

# LM Studio OpenAI-compatible endpoint
LMSTUDIO_BASE_URL = os.getenv("LMSTUDIO_BASE_URL", "https://515f479b5325.ngrok-free.app/v1")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "lm-studio")

MERMAID_SYSTEM_PROMPT = """You are a Mermaid diagram specialist. Your ONLY job is to create diagrams using Mermaid syntax.

CRITICAL RULES:
1. You MUST ALWAYS respond with ONLY a valid Mermaid diagram wrapped in ```mermaid code blocks
2. NEVER provide explanations, steps, or text before or after the diagram
3. ONLY generate diagram code - flowcharts, sequence diagrams, class diagrams, state diagrams, etc.
4. Use clear labels, proper syntax, and appropriate diagram types for the context
5. Your ENTIRE response should be the mermaid code block and nothing else

Example response format (this is ALL you should output):
```mermaid
graph TD
    A[Start] --> B[Process]
    B --> C{Decision}
    C -->|Yes| D[Action]
    C -->|No| E[End]
    D --> E
```

REMEMBER: No explanations, no additional text. Just the ```mermaid code block."""


def generate_mermaid_diagram(query: str, context: str = "") -> str:
    """
    Generate a Mermaid diagram using LLM
    
    Args:
        query: The diagram request
        context: Optional context from other agents
        
    Returns:
        Mermaid diagram code as string
    """
    try:
        client = OpenAI(
            base_url=LMSTUDIO_BASE_URL,
            api_key=LMSTUDIO_API_KEY
        )
        
        # Prepare the user message
        user_message = query
        if context:
            user_message = f"Context from other agents:\n{context}\n\nUser request: {query}"
        
        # Call LLM
        response = client.chat.completions.create(
            model="qwen2.5-coder-1.5b-instruct",  # LM Studio will use whatever model is loaded
            messages=[
                {"role": "system", "content": MERMAID_SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,  # Lower temperature for more consistent formatting
            max_tokens=2000
        )
        
        diagram_code = response.choices[0].message.content.strip()
        
        # Ensure it's wrapped in mermaid code block
        if "```mermaid" not in diagram_code:
            diagram_code = f"```mermaid\n{diagram_code}\n```"
        
        return diagram_code
        
    except Exception as e:
        return f"```mermaid\ngraph TD\n    Error[Error generating diagram: {str(e)}]\n```"


def create_mermaid_response(query: str, context: str = "") -> dict:
    """
    Create a response dict compatible with agent responses
    
    Args:
        query: The diagram request
        context: Optional context from other agents
        
    Returns:
        Dict with agent, answer, and sources keys
    """
    diagram = generate_mermaid_diagram(query, context)
    
    return {
        "agent": "Mermaid Tool",
        "answer": diagram,
        "sources": []
    }
