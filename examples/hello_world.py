#!/usr/bin/env uv run
"""
Simple hello world program demonstrating the OCI OpenAI client.
This script sends a "Hello World" prompt to the OCI Generative AI service
and prints the response.
"""

import sys

from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings
from envyaml import EnvYAML

settings = get_settings()


def main() -> int:
    try:
        # Load config with EnvYAML for the helper
        config = EnvYAML("config.yaml")

        # Initialize the OCI OpenAI client using the helper
        client = OCIOpenAIHelper.get_client(
            model_name=settings.oci.default_model,
            config=config,
        )

        # Send a simple hello-world prompt
        messages = [
            {
                "role": "user",
                "content": "Say 'Hello World!' in a friendly way.",
            }
        ]
        response = client.invoke(messages, max_tokens=100)

        # Print the response
        print("Response from OCI Generative AI:")
        print(response.content)

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your OCI configuration is set up correctly.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
