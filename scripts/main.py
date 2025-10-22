#!/usr/bin/env uv run
"""
Simple hello world program demonstrating the OCI OpenAI client.
This script sends a "Hello World" prompt to the OCI Generative AI service
and prints the response.
"""

import sys

from ai_tools.oci_client import OciOpenAI, OCIUserPrincipleAuth
from ai_tools.utils.config import get_settings

settings = get_settings()


def main() -> int:
    try:
        # Initialize the OCI OpenAI client using central settings
        client = OciOpenAI(
            service_endpoint=settings.oci.service_endpoint,
            auth=OCIUserPrincipleAuth(profile_name=settings.oci.profile_name),
            compartment_id=settings.oci.compartment_id,
        )

        # Send a simple hello-world prompt
        response = client.chat.completions.create(
            model=settings.oci.default_model,
            messages=[
                {
                    "role": "user",
                    "content": "Say 'Hello World!' in a friendly way.",
                }
            ],
            max_tokens=100,
        )

        # Print the response
        print("Response from OCI Generative AI:")
        print(response.choices[0].message.content)

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your OCI configuration is set up correctly.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
