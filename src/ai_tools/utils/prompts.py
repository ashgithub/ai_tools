\"\"\"Prompt-building utilities for proofreading tools.

The server code and any future clients should call
```
from ai_tools.utils.prompts import build_proofread_prompt
```
to obtain the properly formatted prompt string.

Design:
• Relies on the shared settings instance provided by
  :pyfunc:`ai_tools.utils.config.get_settings`.
• Handles optional *instructions* and *can_rewrite* flag.
\"\"\"

from __future__ import annotations

from ai_tools.utils.config import get_settings


def build_proofread_prompt(
    *,
    text: str,
    context_key: str,
    instructions: str = \"\",
    can_rewrite: bool = False,
) -> str:
    \"\"\"Return a formatted proofreading prompt.

    Parameters
    ----------
    text:
        The user-supplied text to be proof-read.
    context_key:
        One of ``\"slack\" | \"email\" | \"general\"`` mapping to prompt contexts in the
        YAML config.
    instructions:
        Additional reviewer guidance provided by caller.  Optional.
    can_rewrite:
        If *True*, allow the LLM to rewrite for clarity; otherwise limit to error fixing.

    Returns
    -------
    str
        Fully formatted prompt ready for LLM chat completion.
    \"\"\"
    settings = get_settings()
    prompts_cfg = settings.prompts

    # Resolve context phrase
    context = prompts_cfg.contexts[context_key]
    if instructions:
        context += f\" Additional notes: {instructions}\"

    prompt = prompts_cfg.base_proofread.format(
        context=context,
        text=text,
        instructions=instructions,
    )

    prompt += prompts_cfg.rewrite_allowed if can_rewrite else prompts_cfg.rewrite_forbidden
    prompt += prompts_cfg.output_instruction
    return prompt
