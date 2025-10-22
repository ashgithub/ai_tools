import sys
import os
import time

from src.ai_tools.oci_client import OciOpenAI, OCIUserPrincipleAuth


class ModelIterator:
    def __init__(self, service_endpoint, compartment_id, profile_name="API-USER"):
        self.client = OciOpenAI(
            service_endpoint=service_endpoint,
            auth=OCIUserPrincipleAuth(profile_name=profile_name),
            compartment_id=compartment_id,
        )
        self.models = self._parse_models()

    def _parse_models(self):
        with open("llm_models.md", "r") as f:
            lines = f.readlines()
        models = []
        for line in lines:
            if line.strip().startswith("- "):
                model = line.split(" – ")[0].strip("- ").strip()
                models.append(model)
        return models

    def iterate_and_query(self):
        results = []
        errors = []
        for model in self.models:
            print(f"Testing model {model}...")
            try:
                start_time = time.time()
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": "what can you do better than any other llm in one sentence",
                        }
                    ],
                    # max_tokens=100,
                    # max_completion_tokens=100
                )
                end_time = time.time()
                elapsed_time = end_time - start_time
                answer = response.choices[0].message.content
                results.append((elapsed_time, model, answer))
            except Exception as e:
                errors.append((model, str(e)))
        return results, errors


def main():
    # OCI Configuration - Replace with your actual values
    SERVICE_ENDPOINT = "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com"
    COMPARTMENT_ID = "ocid1.compartment.oc1..aaaaaaaac3cxhzoka75zaaysugzmvhm3ni3keqvikawjxvwpz26mud622owa"
    PROFILE_NAME = "API-USER"  # Optional: defaults to DEFAULT_PROFILE if not specified

    try:
        iterator = ModelIterator(
            service_endpoint=SERVICE_ENDPOINT,
            compartment_id=COMPARTMENT_ID,
            profile_name=PROFILE_NAME,
        )
        results, errors = iterator.iterate_and_query()

        # sort results by time ascending (fastest first)
        results.sort(key=lambda x: x[0])

        # sort errors by model alphabetically
        errors.sort(key=lambda x: x[0])

        # create results directory
        os.makedirs("results", exist_ok=True)

        # print to stdout
        print("| Model | Time | Answer |")
        print("|-------|------|--------|")
        for elapsed, model, answer in results:
            print(f"| {model} | {elapsed:.2f} | {answer} |")

        if errors:
            print("\n| Model | Status | Details |")
            print("|-------|--------|---------|")
            for model, error in errors:
                print(f"| {model} | Error | {error} |")

        # Summary
        print(
            f"\nSummary: Tested {len(results) + len(errors)} models. Successful: {len(results)}, Errors: {len(errors)}"
        )
        print(
            "Models tested:",
            ", ".join(sorted([m for _, m, _ in results] + [m for m, _ in errors])),
        )

        # write to file
        with open("results/results.md", "w") as f:
            f.write("| Model | Time | Answer |\n")
            f.write("|-------|------|--------|\n")
            for elapsed, model, answer in results:
                f.write(f"| {model} | {elapsed:.2f} | {answer} |\n")

            if errors:
                f.write("\n| Model | Status | Details |\n")
                f.write("|-------|--------|---------|\n")
                for model, error in errors:
                    f.write(f"| {model} | Error | {error} |\n")

            # Summary
            f.write(
                f"\n**Summary:** Tested {len(results) + len(errors)} models. Successful: {len(results)}, Errors: {len(errors)}\n"
            )
            f.write(
                "**Models tested:** "
                + ", ".join(sorted([m for _, m, _ in results] + [m for m, _ in errors]))
                + "\n"
            )

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure your OCI configuration is set up correctly.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
