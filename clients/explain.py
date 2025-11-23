#!/usr/bin/env python3
"""
Command-line tool for explaining technical content using LLM models.
Provides easy-to-understand explanations for technical text.
"""

import sys
import os
import argparse
from typing import Optional

# Add the src directory to the path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings
from envyaml import EnvYAML


def get_oci_client(model_name: Optional[str] = None):
    """Get or create OCI client with specified model."""
    settings = get_settings()
    config = EnvYAML("config.yaml")
    model = model_name or settings.oci.default_model
    return OCIOpenAIHelper.get_client(model_name=model, config=config)


def explain_technical_text(text: str, client) -> str:
    """Explain technical content in an easy-to-understand paragraph."""
    prompt = (
        "Explain the following technical content in an easy to understand paragraph, for a general audience with some computer experience but not an expert.\n\n"
        f"Content:\n{text}\n"
    )

    messages = [{"role": "user", "content": prompt}]
    response = client.invoke(messages, max_tokens=400, temperature=0.2)
    return str(response.content).strip()


def main():
    parser = argparse.ArgumentParser(
        description='Explain technical content using LLM models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Explain text from stdin
  echo "The grep command searches for patterns in files using regular expressions." | python explain.py

  # Explain with custom model
  python explain.py --text "TCP/IP is a protocol suite for networking." --model xai.grok-4

  # Explain technical documentation
  python explain.py --text "$(cat technical_doc.txt)"
        """
    )

    parser.add_argument(
        '--text', '-t',
        help='Technical text to explain (if not provided, reads from stdin)'
    )
    parser.add_argument(
        '--model', '-m',
        help='LLM model to use (default: from config)'
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
        # Get client and explain
        client = get_oci_client(args.model)
        explanation = explain_technical_text(text, client)

        # Output result
        print(explanation)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
