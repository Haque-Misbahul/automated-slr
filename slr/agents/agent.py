# slr/agents/agent.py
from __future__ import annotations
from typing import Dict, Any
from slr.agents.define_picoc import define_picoc

# professor: tools = [define picoc]
TOOLS = [define_picoc]

def run_define_picoc(topic: str) -> Dict[str, Any]:
    """Single-tool agent: just call define_picoc(topic)."""
    return define_picoc(topic)

if __name__ == "__main__":
    # quick manual test (run: python -m slr.agents.agent)
    demo = run_define_picoc("LLM-based code review automation in software engineering")
    from pprint import pprint
    pprint(demo)
