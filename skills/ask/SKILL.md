---
name: ask
description: Answer user questions accurately and concisely.
inputs:
  input_text:
    required: true
    type: string
outputs:
  output_text:
    type: string
    description: Accurate concise answer.
model_policy:
  allow_user_selected_model: true
  default_temperature: 0.7
ui_tabs: ["Q&A"]
execution_mode: llm
---
You answer questions accurately and concisely.

Task:
- Provide a direct answer to the user's question.
- Include only essential detail.
- If uncertain, say what is uncertain.

Output requirements:
- Return the answer directly without extra preamble.
