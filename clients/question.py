#!/usr/bin/env python3
"""
Command-line tool for asking direct questions to LLM models.
Provides direct passthrough access to LLM responses.
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


def ask_question(question: str, client) -> str:
    """Ask a direct question to the LLM."""
    messages = [{"role": "user", "content": question}]
    response = client.invoke(messages, max_tokens=1000, temperature=0.7)
    return str(response.content).strip()


def main():
    parser = argparse.ArgumentParser(
        description='Ask direct questions to LLM models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ask a question from stdin
  echo "What is the capital of France?" | python question.py

  # Ask with custom model
  python question.py --text "Explain quantum computing in simple terms" --model xai.grok-4

  # Ask about code or technical topics
  python question.py --text "How do I reverse a string in Python?"
        """
    )

    parser.add_argument(
        '--text', '-t',
        help='Question or prompt (if not provided, reads from stdin)'
    )
    parser.add_argument(
        '--model', '-m',
        help='LLM model to use (default: from config)'
    )

    args = parser.parse_args()

    # Get input text
    if args.text:
        question = args.text
    else:
        # Read from stdin
        question = sys.stdin.read().strip()
        if not question:
            print("Error: No question provided. Use --text or pipe text to stdin.", file=sys.stderr)
            sys.exit(1)

    try:
        # Get client and ask question
        client = get_oci_client(args.model)
        answer = ask_question(question, client)

        # Output result
        print(answer)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
