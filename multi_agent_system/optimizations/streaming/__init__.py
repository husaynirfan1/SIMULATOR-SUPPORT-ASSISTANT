"""
Streaming Synthesis Module

Real-time response generation with streaming tokens.

Features:
- Early synthesis (starts before all agents complete)
- Incremental synthesis (updates as agents respond)
- Partial synthesis (streams with available data)
"""

from .streaming_synthesis import (
    StreamingSynthesizer,
    stream_with_early_synthesis
)

__all__ = ['StreamingSynthesizer', 'stream_with_early_synthesis']
