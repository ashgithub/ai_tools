#!/usr/bin/env uv run                                                                                                                                                                                                                                     
"""                                                                                                                                                                                                                                                       
Benchmark multiple OCI Generative AI models.                                                                                                                                                                                                              
                                                                                                                                                                                                                                                          
The script iterates through the list of models documented in                                                                                                                                                                                              
`settings.testing.models_file`, sends a single prompt to each model,                                                                                                                                                                                      
measures latency, and writes a Markdown report to                                                                                                                                                                                                         
`settings.testing.results_dir`.                                                                                                                                                                                                                           
                                                                                                                                                                                                                                                          
This refactored version uses the centralised settings loader and modern                                                                                                                                                                                   
import paths introduced in the recent refactor.                                                                                                                                                                                                           
"""                                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                          
import sys                                                                                                                                                                                                                                                
import time                                                                                                                                                                                                                                               
import os                                                                                                                                                                                                                                                 
from pathlib import Path                                                                                                                                                                                                                                  
from typing import List, Tuple                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                          
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from envyaml import EnvYAML
from ai_tools.utils.config import get_settings                                                                                                                                                                                                            
                                                                                                                                                                                                                                                          
settings = get_settings()                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                          
def get_model_list_path() -> Path:
    """
    Resolve the absolute path to the models file, relative to:
      1. The config file location (if specified via env or discovered upward)
      2. The current working directory (as a fallback)
    Tries all reasonable locations and returns the first one found.
    Raises FileNotFoundError if not found.
    """
    model_file = settings.testing.models_file
    model_list_path = Path(model_file)

    # Case 1: models_file is an absolute path
    if model_list_path.is_absolute():
        if model_list_path.exists():
            return model_list_path  # Found as absolute path
        else:
            raise FileNotFoundError(f"Model file not found: {model_list_path}")

    search_paths = []

    # Case 2: models_file is a relative path, first try relative to config file
    config_file = os.environ.get("AI_TOOLS_CONFIG")
    if config_file:
        # Environment variable specified config file location
        config_dir = Path(config_file).parent.resolve()
        candidate = (config_dir / model_file).resolve()
        search_paths.append(candidate)  # Candidate: relative to config dir
    else:
        # Attempt to discover config.yaml by searching up from current script
        path = Path(__file__).resolve()
        found = False
        for parent in (path.parent, *path.parents):
            candidate_config = parent / "config.yaml"
            if candidate_config.exists():
                config_dir = candidate_config.parent
                candidate = (config_dir / model_file).resolve()
                search_paths.append(candidate)  # Candidate: relative to found config.yaml
                found = True
                break
        if not found:
            # No config.yaml found, fall through to CWD fallback below
            pass

    # Case 3: As additional fallback, try current working directory
    search_paths.append((Path.cwd() / model_file).resolve())  # Candidate: CWD

    # Try each candidate in order: config dir → cwd
    for candidate in search_paths:
        if candidate.exists():
            return candidate

    # If none found, raise error with all searched paths
    raise FileNotFoundError(f"Model file '{model_file}' not found in any of: {[str(p) for p in search_paths]}")
                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                          
def parse_models(file_path: Path) -> List[str]:                                                                                                                                                                                                           
    """Return a list of model identifiers parsed from the docs file."""                                                                                                                                                                                   
    models: List[str] = []                                                                                                                                                                                                                                
    for line in file_path.read_text(encoding="utf-8").splitlines():                                                                                                                                                                                       
        if line.strip().startswith("- "):  # bullet list in docs                                                                                                                                                                                          
            model = line.split(" – ")[0].removeprefix("- ").strip()                                                                                                                                                                                       
            models.append(model)                                                                                                                                                                                                                          
    return models                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                          
def query_model(client, model: str) -> Tuple[float, str]:
    """Send the test prompt to *model* and return (elapsed_seconds, answer)."""
    start = time.perf_counter()
    messages = [{"role": "user", "content": settings.testing.test_prompt}]
    response = client.invoke(messages)
    elapsed = time.perf_counter() - start
    answer = response.content
    return elapsed, answer
                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                          
def main() -> int:
    try:
        config = EnvYAML("config.yaml")
        client = OCIOpenAIHelper.get_client(
            model_name=settings.oci.default_model,
            config=config,
        )
                                                                                                                                                                                                                                                          
        model_list_path = get_model_list_path()                                                                                                                                                                                                           
        models = parse_models(model_list_path)                                                                                                                                                                                                            
                                                                                                                                                                                                                                                          
        results: List[Tuple[float, str, str]] = []                                                                                                                                                                                                        
        errors: List[Tuple[str, str]] = []                                                                                                                                                                                                                
                                                                                                                                                                                                                                                          
        for model in models:                                                                                                                                                                                                                              
            print(f"⏳ Testing model {model} …")                                                                                                                                                                                                          
            try:                                                                                                                                                                                                                                          
                elapsed, answer = query_model(client, model)                                                                                                                                                                                              
                results.append((elapsed, model, answer))                                                                                                                                                                                                  
            except Exception as exc:  # noqa: BLE001                                                                                                                                                                                                      
                errors.append((model, str(exc)))                                                                                                                                                                                                          
                                                                                                                                                                                                                                                          
        # sort for readability                                                                                                                                                                                                                            
        results.sort(key=lambda t: t[0])  # fastest first                                                                                                                                                                                                 
        errors.sort(key=lambda t: t[0])                                                                                                                                                                                                                   
                                                                                                                                                                                                                                                          
        # ensure results directory                                                                                                                                                                                                                        
        results_dir = Path(settings.testing.results_dir)                                                                                                                                                                                                  
        results_dir.mkdir(parents=True, exist_ok=True)                                                                                                                                                                                                    
        md_path = results_dir / "results.md"                                                                                                                                                                                                              
                                                                                                                                                                                                                                                          
        # ── console summary ────────────────────────────────────────────────────                                                                                                                                                                         
        print("\n| Model | Time (s) | Answer |")                                                                                                                                                                                                          
        print("|-------|----------|--------|")                                                                                                                                                                                                            
        for elapsed, model, answer in results:                                                                                                                                                                                                            
            print(f"| {model} | {elapsed:.2f} | {answer} |")                                                                                                                                                                                              
        if errors:                                                                                                                                                                                                                                        
            print("\n| Model | Status | Details |")                                                                                                                                                                                                       
            print("|-------|--------|---------|")                                                                                                                                                                                                         
            for model, detail in errors:                                                                                                                                                                                                                  
                print(f"| {model} | Error | {detail} |")                                                                                                                                                                                                  
                                                                                                                                                                                                                                                          
        # ── write markdown ─────────────────────────────────────────────────────                                                                                                                                                                         
        with md_path.open("w", encoding="utf-8") as fd:                                                                                                                                                                                                   
            fd.write("| Model | Time (s) | Answer |\n|-------|----------|--------|\n")                                                                                                                                                                    
            for elapsed, model, answer in results:                                                                                                                                                                                                        
                fd.write(f"| {model} | {elapsed:.2f} | {answer} |\n")                                                                                                                                                                                     
                                                                                                                                                                                                                                                          
            if errors:                                                                                                                                                                                                                                    
                fd.write("\n| Model | Status | Details |\n|-------|--------|---------|\n")                                                                                                                                                                
                for model, detail in errors:                                                                                                                                                                                                              
                    fd.write(f"| {model} | Error | {detail} |\n")                                                                                                                                                                                         
                                                                                                                                                                                                                                                          
            total = len(results) + len(errors)                                                                                                                                                                                                            
            fd.write(                                                                                                                                                                                                                                     
                f"\n**Summary:** Tested {total} models. "                                                                                                                                                                                                 
                f"Successful: {len(results)}, Errors: {len(errors)}\n"                                                                                                                                                                                    
            )                                                                                                                                                                                                                                             
            all_models = sorted([m for _, m, _ in results] + [m for m, _ in errors])                                                                                                                                                                      
            fd.write("**Models tested:** " + ", ".join(all_models) + "\n")                                                                                                                                                                                
                                                                                                                                                                                                                                                          
        print(f"\nMarkdown report written to {md_path}")                                                                                                                                                                                                  
    except Exception as exc:  # noqa: BLE001                                                                                                                                                                                                              
        print(f"Fatal error: {exc}")                                                                                                                                                                                                                      
        return 1                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                          
    return 0                                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                          
if __name__ == "__main__":                                                                                                                                                                                                                                
    sys.exit(main())
