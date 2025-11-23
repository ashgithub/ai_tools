#!/usr/bin/env python3
"""
Command-line tool for generating shell commands using LLM models.
Supports different operating systems (macos, linux) with configurable LLM.
"""

import sys
import os
import argparse
from typing import Optional, List

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


def generate_commands(query: str, os_type: str, client) -> List[str]:
    """Generate command alternatives for the given query."""
    os_str = os_type.lower()
    if os_str not in ("linux", "macos"):
        os_str = "macos"

    prompt = (
        f"List 1 to 3 alternative command-line commands to accomplish the following task on {os_str}:\n"
        f"Task: {query}\n"
        "For each alternative, return only the shell command (no explanation, no comments). List as bullet points."
    )

    messages = [{"role": "user", "content": prompt}]
    response = client.invoke(messages, max_tokens=256, temperature=0.2)
    result = str(response.content).strip()

    # Try to convert bullet points or newlines to list:
    lines = []
    for line in result.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('- '):
            line = line[2:]
        elif line[0:1] in ('1', '2', '3') and line[1] in ('.',')'):
            line = line[2:].strip()
        lines.append(line)
    if not lines and result:
        lines = [result]

    return lines


def main():
    parser = argparse.ArgumentParser(
        description='Generate shell commands using LLM models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate commands from stdin with default OS (macos)
  echo "list files in current directory" | python command.py

  # Generate commands for specific OS
  echo "find large files" | python command.py --os linux

  # Generate commands with custom model
  python command.py --text "compress a directory" --os macos --model xai.grok-4

  # Get commands for a task
  python command.py --text "check disk usage" --os linux
        """
    )

    parser.add_argument(
        '--text', '-t',
        help='Task description (if not provided, reads from stdin)'
    )
    parser.add_argument(
        '--os', '-o',
        choices=['macos', 'linux'],
        default='macos',
        help='Operating system (default: macos)'
    )
    parser.add_argument(
        '--model', '-m',
        help='LLM model to use (default: from config)'
    )

    args = parser.parse_args()

    # Get input text
    if args.text:
        query = args.text
    else:
        # Read from stdin
        query = sys.stdin.read().strip()
        if not query:
            print("Error: No task description provided. Use --text or pipe text to stdin.", file=sys.stderr)
            sys.exit(1)

    try:
        # Get client and generate commands
        client = get_oci_client(args.model)
        commands = generate_commands(query, args.os, client)

        # Output results (one per line)
        for cmd in commands:
            print(cmd)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
