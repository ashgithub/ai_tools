---
name: Refresh LLMs
description: Refresh the local OCI model cache used by the UI model selector.
inputs:
  input_text:
    required: false
    type: string
  action:
    required: true
    type: string
outputs:
  output_text:
    type: string
    description: Refresh status message.
model_policy:
  allow_user_selected_model: false
ui_tabs: ["Refresh"]
execution_mode: builtin.refresh_models
---
Refresh the local model cache by running the OCI refresh workflow.

Task:
- Execute the cache refresh workflow.
- Return success output on completion.
- Return a fail-fast error when refresh fails.
