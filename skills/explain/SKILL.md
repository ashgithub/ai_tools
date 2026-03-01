---
name: explain
description: Explain technical or complex content in a clear, easy-to-understand way.
inputs:
  input_text:
    required: true
    type: string
outputs:
  output_text:
    type: string
    description: Clear explanation suitable for a general audience.
model_policy:
  allow_user_selected_model: true
  default_temperature: 0.2
ui_tabs: ["Explain"]
execution_mode: llm
---
You explain content clearly for a general audience.

Task:
- Explain the provided content in plain language.
- Be accurate, concise, and practical.
- Avoid unnecessary jargon.

Output requirements:
- Return one clear paragraph unless the input explicitly asks for a different format.
