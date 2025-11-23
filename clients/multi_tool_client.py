#!/usr/bin/env python3
"""
Simplified AI Text Tools GUI Client.
Clean, direct UI implementation without complex abstractions.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
import logging
import time
from typing import Optional
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings
from ai_tools.utils.prompts import build_proofread_prompt
from envyaml import EnvYAML

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimplifiedTextToolsGUI:
    """Clean, simplified GUI for AI text tools."""

    TAB_CONFIG = {
        "Proofread": {
            "input_label": "Text to Proofread:",
            "sample_text": "i had s agreat tuime when i met yuo\n- lest meet again \n- yi choose trh palce\n0 you chsoe teh tm",
            "default_prompt": "You are a professional proofreader. Your task is to improve the following text.",
            "prompt_section_label": "Text",
            "button_text": "Proofread",
            "config_frame": "_create_context_frame",
            "max_tokens": 1000,
            "temperature": 0.3,
        },
        "Explain": {
            "input_label": "Technical Text to Explain:",
            "sample_text": "SSH keys are cryptographic key pairs used for secure authentication to remote systems. The public key is placed on the server, while the private key remains on the client machine.",
            "default_prompt": "Explain the following content in an easy to understand paragraph for a general audience:",
            "prompt_section_label": "Content",
            "button_text": "Explain",
            "config_frame": None,
            "max_tokens": 400,
            "temperature": 0.2,
        },
        "Commands": {
            "input_label": "Task Description:",
            "sample_text": "copy my SSH public key to clipboard",
            "default_prompt": "List 1 to 3 alternative command-line commands to accomplish the given task (no explanation, no comments).",
            "prompt_section_label": "Task",
            "button_text": "Get Commands",
            "config_frame": "_create_os_frame",
            "max_tokens": 256,
            "temperature": 0.2,
        },
        "Q&A": {
            "input_label": "Question:",
            "sample_text": "What is the capital of France?",
            "default_prompt": "Answer the following question as accurately and concisely as possible:",
            "prompt_section_label": "Question",
            "button_text": "Ask",
            "config_frame": None,
            "max_tokens": 1000,
            "temperature": 0.7,
        }
    }

    def __init__(self, root):
        self.root = root
        self.root.title("AI Text Tools")
        self.root.geometry("900x800")
        self.root.minsize(800, 700)
        self.root.resizable(True, True)

        self._oci_client: Optional[OCIOpenAIHelper] = None
        self.selected_model: Optional[str] = None
        self.available_models = self._load_available_models()
        self.last_result: Optional[str] = None

        # Map tab names to widgets
        self.input_widgets = {}
        self.prompt_widgets = {}
        self.response_widgets = {}
        self.sub_notebooks = {}
        self.sub_notebook_selections = {}

        self.args = self._parse_args()
        self.config = EnvYAML("config.yaml")
        self.app_mappings = self.config.get('app_mappings', {})
        self._setup_ui()

    def _parse_args(self):
        """Parse command line arguments."""
        import argparse
        parser = argparse.ArgumentParser(description='AI Text Tools GUI')
        parser.add_argument('--app', help='Application context to select the appropriate tab based on config.yaml mappings')
        parser.add_argument('--text', help='Text content to pre-populate in the selected tab\'s input field')
        return parser.parse_args()

    def _get_mapping_for_app(self, app):
        """Get tab and config for a given app from mappings."""
        for tab, configs in self.app_mappings.items():
            for config in configs:
                if app in config.get('apps', []):
                    return {'tab': tab, 'config': config}
        return None

    def _load_available_models(self) -> list:
        """Load available LLM models from config."""
        settings = get_settings()
        models = settings.models if settings.models else [settings.oci.default_model]
        return models

    def _setup_ui(self):
        """Set up the main UI."""
        self._create_model_selector()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        for tab_name, config in self.TAB_CONFIG.items():
            self._create_tab(tab_name, config)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_main_tab_changed)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Handle CLI args for tab selection and text population
        mapping = self._get_mapping_for_app(self.args.app) if self.args.app else None
        if mapping:
            tab_name = mapping['tab']
        else:
            tab_name = 'Q&A'
        tab_index = list(self.TAB_CONFIG.keys()).index(tab_name)
        self.notebook.select(tab_index)

        # Set tab-specific configs
        config = mapping['config'] if mapping else {}
        if tab_name == 'Proofread' and 'context' in config:
            self.context_var.set(config['context'])
        elif tab_name == 'Commands' and 'os' in config:
            self.os_var.set(config['os'])

        # Populate text if provided
        if self.args.text:
            active_tab = self.notebook.tab(self.notebook.select(), "text")
            widget = self.input_widgets[active_tab]
            widget.delete("1.0", tk.END)
            widget.insert("1.0", self.args.text)

    def _create_tab(self, tab_name: str, config: dict):
        """Create a tab with input, prompt, and response areas."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=tab_name)

        # Input area
        ttk.Label(frame, text=config["input_label"]).pack(anchor=tk.W, pady=(10, 0))
        input_text = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD)
        input_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        input_text.insert("1.0", config["sample_text"])
        self.input_widgets[tab_name] = input_text

        # Prompt/Response notebook
        sub_notebook = ttk.Notebook(frame)

        response_text = scrolledtext.ScrolledText(sub_notebook, height=12, wrap=tk.WORD, state='disabled')
        sub_notebook.add(response_text, text="Response")
        self.response_widgets[tab_name] = response_text

        prompt_text = scrolledtext.ScrolledText(sub_notebook, height=8, wrap=tk.WORD)
        prompt_text.insert("1.0", config["default_prompt"])
        sub_notebook.add(prompt_text, text="Prompt")
        self.prompt_widgets[tab_name] = prompt_text

        sub_notebook.select(0)  # Default to Response tab

        # Optional config frame (e.g., context, OS)
        if config.get("config_frame"):
            getattr(self, config["config_frame"])(frame)

        sub_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        self.sub_notebooks[tab_name] = sub_notebook
        self.sub_notebook_selections[tab_name] = 0

        sub_notebook.bind(
            "<<NotebookTabChanged>>",
            lambda e: self.sub_notebook_selections.update({tab_name: sub_notebook.index("current")})
        )

        # Action frame
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            action_frame, 
            text=config["button_text"], 
            command=lambda: self._run_action_for_tab(tab_name)
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(action_frame, text="Done", command=lambda: self._done_action(tab_name)).pack(
            side=tk.LEFT, padx=10
        )

    def _create_os_frame(self, frame):
        """Create OS selection frame for Commands tab."""
        os_frame = ttk.Frame(frame)
        os_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(os_frame, text="Operating System:").pack(side=tk.LEFT, padx=(0, 5))
        self.os_var = tk.StringVar(value="macos")
        for os_name in ["macos", "linux"]:
            ttk.Radiobutton(os_frame, text=os_name.capitalize(), variable=self.os_var, value=os_name).pack(
                side=tk.LEFT, padx=10
            )

    def _create_context_frame(self, frame):
        """Create context selection frame for Proofread tab."""
        # Main context frame
        context_frame = ttk.LabelFrame(frame, text="Context & Options", padding="5")
        context_frame.pack(fill=tk.X, pady=(0, 10))

        # Context radio buttons
        context_defaults = {
            "general": "You are a professional proofreader. Your task is to improve the following text.",
            "slack": "Proofread this as a Slack message: keep it concise, friendly, professional, and use relevant emojis if appropriate.",
            "email": "Proofread this as a business email: ensure a professional tone, proper structure, greeting, and closing."
        }

        self.context_var = tk.StringVar(value="general")

        self.allow_rewrite_var = tk.BooleanVar(value=True)

        def on_context_change(*args):
            chosen = self.context_var.get()
            self.prompt_widgets["Proofread"].delete("1.0", tk.END)
            self.prompt_widgets["Proofread"].insert("1.0", context_defaults[chosen])

        self.context_var.trace_add("write", on_context_change)

        # Context section
        context_label = ttk.Label(context_frame, text="Type:", font=("TkDefaultFont", 9, "bold"))
        context_label.pack(anchor=tk.W, pady=(0, 5))

        radio_frame = ttk.Frame(context_frame)
        radio_frame.pack(anchor=tk.W, padx=(20, 0))
        for context in context_defaults.keys():
            ttk.Radiobutton(
                radio_frame, text=context.capitalize(), variable=self.context_var, value=context
            ).pack(side=tk.LEFT, padx=10)

        ttk.Checkbutton(
            radio_frame, text="Allow rewriting", variable=self.allow_rewrite_var
        ).pack(side=tk.LEFT, padx=10)


    def _create_model_selector(self):
        """Create the model selector dropdown."""
        model_frame = ttk.Frame(self.root)
        model_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(model_frame, text="LLM Model:").pack(side=tk.LEFT, padx=(0, 5))

        self.model_var = tk.StringVar()
        settings = get_settings()
        self.model_var.set(settings.oci.default_model)

        self.model_combo = ttk.Combobox(
            model_frame, textvariable=self.model_var,
            values=self.available_models, state="readonly", width=40
        )
        self.model_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

    def _on_model_change(self, event=None):
        """Handle model selection change."""
        selected_model = self.model_var.get()
        if selected_model != self.selected_model:
            self.selected_model = selected_model
            self._oci_client = None
            self.status_var.set(f"Model: {selected_model}")

    def _refresh_models(self):
        """Refresh the list of available models."""
        old_model = self.model_var.get()
        self.available_models = self._load_available_models()
        self.model_combo['values'] = self.available_models

        if old_model in self.available_models:
            self.model_var.set(old_model)
        elif self.available_models:
            self.model_var.set(self.available_models[0])
            self._on_model_change()

        self.status_var.set(f"Models refreshed: {len(self.available_models)} available")

    def _invoke_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Invoke the AI API and return the response."""
        client = self._get_oci_client()
        messages = [{"role": "user", "content": prompt}]
        response = client.invoke(messages, max_tokens=max_tokens, temperature=temperature)
        return str(response.content).strip()

    def _run_action_for_tab(self, tab_name: str):
        """Generic handler for all tab action buttons."""
        config = self.TAB_CONFIG[tab_name]
        template = self.prompt_widgets[tab_name].get("1.0", tk.END).strip()
        input_text = self.input_widgets[tab_name].get("1.0", tk.END).strip()

        if not input_text:
            messagebox.showwarning("Input Required", f"Please enter {config['input_label'].lower()}")
            return

        section_label = config.get("prompt_section_label", "Content")
        if tab_name == "Commands":
            os_selected = self.os_var.get() if hasattr(self, 'os_var') else 'macos'
            prompt = f"{template} for {os_selected} operating system.\n\n{section_label}:\n{input_text}"
        elif tab_name == "Proofread":
            context_key = self.context_var.get()
            prompt = build_proofread_prompt(
                text=input_text,
                context_key=context_key,
                instructions="",
                can_rewrite=self.allow_rewrite_var.get()
            )
        else:
            prompt = f"{template}\n\n{section_label}:\n{input_text}"
        self._run_action(tab_name, prompt, config)

    def _run_action(self, tab_name: str, prompt: str, config: dict):
        """Run an AI action in a background thread."""
        self.status_var.set("Processing request...")

        def worker():
            start_time = time.time()
            try:
                result = self._invoke_api(
                    prompt, config["max_tokens"], config["temperature"]
                )
                # Post-process if needed (e.g., Commands tab)
                if tab_name == "Commands":
                    result = self._clean_command_output(result)
                processing_time = time.time() - start_time
                self.root.after(0, lambda: self._display_result(tab_name, result))
                self.root.after(0, lambda: self.status_var.set(f"Response ready ({processing_time:.2f}s)"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _clean_command_output(self, result: str) -> str:
        """Clean up command list output."""
        lines = []
        for line in result.splitlines():
            line = line.strip()
            if line.startswith('- '):
                line = line[2:]
            elif line and line[0] in '123456789' and len(line) > 1 and line[1] in '.)':
                line = line[2:].strip()
            if line:
                lines.append(line)
        return '\n'.join(lines) if lines else result

    def _display_result(self, tab_name: str, result: str):
        """Display result in the response area."""
        widget = self.response_widgets[tab_name]
        widget.config(state='normal')
        widget.delete("1.0", tk.END)
        widget.insert("1.0", result)
        widget.config(state='disabled')
        self.last_result = result
        # Switch to Response tab
        self.sub_notebooks[tab_name].select(0)
        self.sub_notebook_selections[tab_name] = 0

    def _on_main_tab_changed(self, event):
        """Restore sub-notebook selection on main tab change."""
        notebook = event.widget
        tab_text = notebook.tab(notebook.select(), "text")
        sub_notebook = self.sub_notebooks.get(tab_text)
        if sub_notebook:
            index = self.sub_notebook_selections.get(tab_text, 0)
            sub_notebook.select(index)

    def _done_action(self, tab_name: str):
        """Handle Done button: print response and exit."""
        result = self.response_widgets[tab_name].get("1.0", tk.END).strip()
        if not result:
            messagebox.showwarning("No Response", "No response available. Please run an action first.")
            return
        print(result)
        self.root.quit()
        sys.exit(0)

    def _get_oci_client(self) -> OCIOpenAIHelper:
        """Get or create OCI client."""
        if self._oci_client is None:
            config = EnvYAML("config.yaml")
            self._oci_client = OCIOpenAIHelper.get_client(
                model_name=self.model_var.get(),
                config=config,
            )
        return self._oci_client


def main():
    """Main entry point."""
    root = tk.Tk()
    app = SimplifiedTextToolsGUI(root)

    # Bring window to front
    root.lift()
    root.focus_force()
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))

    root.mainloop()


if __name__ == "__main__":
    main()
