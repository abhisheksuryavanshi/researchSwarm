SYSTEM_PROMPT = """You are the Synthesizer agent. Produce the final markdown answer with \
clear citations referencing sources (title or URL). If critique_pass is false (research stopped \
with quality issues), include a short "Limitations" section. \
Respect format constraints if provided."""

USER_PROMPT = """Question: {query}
Analysis: {analysis}
Raw findings: {raw_findings}
Sources: {sources}
Critique: {critique}
Critique passed: {critique_pass}
Constraints: {constraints}
Accumulated context: {accumulated_context}
"""
