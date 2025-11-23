#!/usr/bin/env python3
"""
Command-line tool for proofreading text using LLM models.
Supports different contexts (slack, email, general) with configurable LLM.
"""

import sys
import os
import argparse
from typing import Optional

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings
from ai_tools.utils.prompts import build_proofread_prompt
from envyaml import EnvYAML


def get_oci_client(model_name: Optional[str] = None):
    """Get or create OCI client with specified model."""
    settings = get_settings()
    config = EnvYAML("config.yaml")
    model = model_name or settings.oci.default_model
    return OCIOpenAIHelper.get_client(model_name=model, config=config)


def main():
    parser = argparse.ArgumentParser(
        description='Proofread text using LLM models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Proofread from stdin with default context (general)
  echo "This is some text to proofread." | python proofread.py

  # Proofread with specific context
  echo "Hey team, let's meet tomorrow" | python proofread.py --context slack

  # Proofread with custom model
  python proofread.py --text "This needs proofreading" --context email --model xai.grok-4

  # Allow rewriting for better clarity
  python proofread.py --text "This is bad writing" --allow-rewrite
        """
    )

    parser.add_argument(
        '--text', '-t',
        help='Text to proofread (if not provided, reads from stdin)'
    )
    parser.add_argument(
        '--context', '-c',
        choices=['slack', 'email', 'general'],
        default='general',
        help='Context for proofreading (default: general)'
    )
    parser.add_argument(
        '--model', '-m',
        help='LLM model to use (default: from config)'
    )
    parser.add_argument(
        '--allow-rewrite', '-r',
        action='store_true',
        help='Allow rewriting for better clarity (default: only corrections)'
    )

    args = parser.parse_args()

    # Get input text
    if args.text:
        text = args.text
    else:
        # Read from stdin
        text = sys.stdin.read().strip()
        if not text:
            print("Error: No text provided. Use --text or pipe text to stdin.", file=sys.stderr)
            sys.exit(1)

    try:
        # Get client and proofread
        client = get_oci_client(args.model)

        prompt = build_proofread_prompt(
            text=text,
            context_key=args.context,
            instructions="",
            can_rewrite=args.allow_rewrite,
        )

        messages = [{"role": "user", "content": prompt}]
        response = client.invoke(messages, max_tokens=1000, temperature=0.3)

        # Output result
        print(str(response.content).strip())

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
