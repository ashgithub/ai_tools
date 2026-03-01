---
name: proofread-general
description: proof read & Improve grammar, punctuation, spelling, and readability for general apps outside email & slack
inputs:
  input_text:
    required: true
    type: string
  proofread_context:
    required: false
    type: string
outputs:
  corrected:
    type: string
    description: Minimally corrected source text.
  rewritten:
    type: string
    description: Corrected and improved text.
model_policy:
  allow_user_selected_model: true
  default_temperature: 0.3
ui_tabs: ["Proofread"]
execution_mode: llm
---
You are a professional proofreader.

Task:
- Correct grammar, punctuation, spelling, and markdown formatting errors.
- Rewrite for clarity while preserving the original intent.

Output requirements:
- Return structured output with:
  - corrected: minimally corrected source text fixing grammer & typos
  - rewritten: the improved final text that keeps the original intent but is rewritten for better impact
