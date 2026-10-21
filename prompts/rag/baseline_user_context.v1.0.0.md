---
id: rag.baseline_user_context
family: rag/baseline_user_context
version: 1.0.0
variables: [context_text, question]
compatible_with: [rag.prompts]
description: Baseline RAG user message with retrieved context
status: approved
sha256: 52e66b81e7204b582fcf302428ffe014d19fd74d97e5d32dff7b2d65663ef940
---
Answer the question using the numbered context. Cite with [n] markers.

CONTEXT:
{context_text}

QUESTION:
{question}