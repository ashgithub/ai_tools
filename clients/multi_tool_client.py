#!/usr/bin/env python3
"""
Simplified AI Text Tools GUI Client.
Clean, direct UI implementation without complex abstractions.
Version: Clean Implementation
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import sys
import os
import logging
import time
from typing import List
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings
from ai_tools.utils.prompts import build_proofread_prompt
from envyaml import EnvYAML

# Set up logging - change to INFO level for cleaner output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimplifiedTextToolsGUI:
    """Clean, simplified GUI for AI text tools."""

    def __init__(self, root):
        self.root = root
        self.root.title("AI Text Tools")
        self.root.geometry("900x800")
        self.root.minsize(800, 700)
        self.root.resizable(True, True)

        self._oci_client = None
        self.selected_model = None
        self.available_models = self._load_available_models()
        self.last_result = None

        # Parse command line arguments
        self.args = self._parse_args()

        # Set up UI
        self._setup_ui()

    def _parse_args(self):
        """Parse command line arguments from macOS Shortcuts."""
        import argparse
        parser = argparse.ArgumentParser(description='AI Text Tools GUI')
        parser.add_argument('--app', help='Active application name')
        parser.add_argument('--clipboard', help='Clipboard content')
        return parser.parse_args()

    def _load_available_models(self) -> List[str]:
        """Load available LLM models from config."""
        settings = get_settings()
        models = settings.models if settings.models else []

        if not models:
            # Fallback to default model
            models = [settings.oci.default_model]

        return models

    def _setup_ui(self):
        """Set up the main UI."""
        # Model selector at top
        self._create_model_selector()

        # State tracking for sub-tab selection persistence
        self._sub_notebook_map = {}
        self._sub_notebook_selection = {}

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # Tab configuration
        tab_config = {
            "Proofread": {
                "input_label": "Text to Proofread:",
                "sample_text": "i had s agreat tuime when i met yuo\n- lest meet again \n- yi choose trh palce\n0 you chsoe teh tm",
                "default_prompt": "You are a professional proofreader. Your task is to improve the following text.",
                "action_handler": self._do_proofread_action,
                "button_text": "Proofread",
                "config_frame_func": self._create_context_frame,
            },
            "Explain": {
                "input_label": "Technical Text to Explain:",
                "sample_text": "SSH keys are cryptographic key pairs used for secure authentication to remote systems. The public key is placed on the server, while the private key remains on the client machine.",
                "default_prompt": "Explain the following content in an easy to understand paragraph for a general audience:",
                "action_handler": self._do_explain_action,
                "button_text": "Explain",
                "config_frame_func": None,
            },
            "Commands": {
                "input_label": "Task Description:",
                "sample_text": "copy my SSH public key to clipboard",
                "default_prompt": "List 1 to 3 alternative command-line commands to accomplish the given task (no explanation, no comments).",
                "action_handler": self._do_commands_action,
                "button_text": "Get Commands",
                "config_frame_func": self._create_os_frame,
            },
            "Q&A": {
                "input_label": "Question:",
                "sample_text": "What is the capital of France?",
                "default_prompt": "Answer the following question as accurately and concisely as possible:",
                "action_handler": self._do_question_action,
                "button_text": "Ask",
                "config_frame_func": None,
            }
        }

        # Create tabs using configuration
        for tab_name, config in tab_config.items():
            extra_widgets = None
            if tab_name == "Proofread":
                self.allow_rewrite_var = tk.BooleanVar(value=True)
                checkbutton = ttk.Checkbutton(text="Allow rewriting", variable=self.allow_rewrite_var)
                extra_widgets = [checkbutton]
            self._create_tab(
                tab_name=tab_name,
                input_label=config["input_label"],
                sample_text=config["sample_text"],
                default_prompt=config["default_prompt"],
                action_handler=config["action_handler"],
                button_text=config["button_text"],
                config_frame_func=config["config_frame_func"],
                extra_widgets=extra_widgets
            )

        # Hook up main tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self._on_main_tab_changed)

        # Status bar at bottom
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _create_tab(self, tab_name: str, input_label: str, sample_text: str, default_prompt: str,
                    action_handler, button_text: str, config_frame_func=None, extra_widgets=None):
        """Create a generic tab with common UI components."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=tab_name)

        # Input text area
        ttk.Label(frame, text=input_label).pack(anchor=tk.W, pady=(10, 0))
        input_text = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD)
        input_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        input_text.insert("1.0", sample_text)

        # Set attribute for input text based on tab_name
        input_attr = f"{tab_name.lower().replace(' ', '_')}_input"
        setattr(self, input_attr, input_text)

        # Create Prompt/Response Notebook (not packed yet)
        notebook = ttk.Notebook(frame)

        # Prompt tab (editable)
        prompt_text = scrolledtext.ScrolledText(notebook, height=8, wrap=tk.WORD)
        prompt_text.insert("1.0", default_prompt)
        notebook.add(prompt_text, text="Prompt")

        # Response tab (read-only)
        response_text = scrolledtext.ScrolledText(notebook, height=12, wrap=tk.WORD, state='disabled')
        notebook.add(response_text, text="Response")
        # Default to Response tab (index 1)
        notebook.select(1)

        # Set attributes for prompt and response text
        prompt_attr = f"{tab_name.lower().replace(' ', '_')}_prompt_text"
        response_attr = f"{tab_name.lower().replace(' ', '_')}_response_text"
        setattr(self, prompt_attr, prompt_text)
        setattr(self, response_attr, response_text)

        # Optional config frame (e.g., context, OS) - after prompt_text is set, before packing notebook
        if config_frame_func:
            config_frame_func(frame)

        # Pack notebook
        notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        # Action frame
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        # Action button
        ttk.Button(action_frame, text=button_text, command=action_handler).pack(side=tk.LEFT, padx=(0, 10))

        # Optional extra widgets (e.g., checkboxes)
        if extra_widgets:
            for widget in extra_widgets:
                widget.pack(side=tk.LEFT, padx=10)

        # Track in sub-notebook map
        self._sub_notebook_map[tab_name] = notebook
        self._sub_notebook_selection[tab_name] = 1
        notebook.bind("<<NotebookTabChanged>>", lambda e: self._record_subtab(tab_name, notebook.index("current")))

    def _create_os_frame(self, frame):
        """Create OS selection frame for Commands tab."""
        os_frame = ttk.Frame(frame)
        os_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(os_frame, text="Operating System:").pack(side=tk.LEFT, padx=(0, 5))
        self.os_var = tk.StringVar(value="macos")
        ttk.Radiobutton(os_frame, text="macOS", variable=self.os_var, value="macos").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(os_frame, text="Linux", variable=self.os_var, value="linux").pack(side=tk.LEFT, padx=10)

    def _create_context_frame(self, frame):
        """Create context selection frame for Proofread tab."""
        context_frame = ttk.LabelFrame(frame, text="Context", padding="5")
        context_frame.pack(fill=tk.X, pady=(0, 10))

        self.context_var = tk.StringVar(value="general")
        def on_context_change(*args):
            context_defaults = {
                "general": "You are a professional proofreader. Your task is to improve the following text.",
                "slack": "Proofread this as a Slack message: keep it concise, friendly, professional, and use relevant emojis if appropriate.",
                "email": "Proofread this as a business email: ensure a professional tone, proper structure, greeting, and closing."
            }
            chosen = self.context_var.get()
            self.proofread_prompt_text.delete("1.0", tk.END)
            self.proofread_prompt_text.insert("1.0", context_defaults.get(chosen, context_defaults["general"]))
        self.context_var.trace_add("write", on_context_change)
        ttk.Radiobutton(context_frame, text="General", variable=self.context_var, value="general").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(context_frame, text="Slack", variable=self.context_var, value="slack").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(context_frame, text="Email", variable=self.context_var, value="email").pack(side=tk.LEFT, padx=10)

    def _create_model_selector(self):
        """Create the model selector dropdown at the top."""
        model_frame = ttk.Frame(self.root)
        model_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(model_frame, text="LLM Model:").pack(side=tk.LEFT, padx=(0, 5))

        self.model_var = tk.StringVar()
        settings = get_settings()
        self.model_var.set(settings.oci.default_model)

        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var,
                                       values=self.available_models, state="readonly", width=40)
        self.model_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        ttk.Button(model_frame, text="🔄", width=3, command=self._refresh_models).pack(side=tk.LEFT)

    def _create_proofread_tab(self):
        """Create the proofread tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Proofread")

        # Input text area
        ttk.Label(frame, text="Text to Proofread:").pack(anchor=tk.W, pady=(10, 0))
        self.proofread_input = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD)
        self.proofread_input.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # Add sample text
        sample_text = "i had s agreat tuime when i met yuo\n- lest meet again \n- yi choose trh palce\n0 you chsoe teh tm"
        self.proofread_input.insert("1.0", sample_text)

        # Context selection
        context_frame = ttk.LabelFrame(frame, text="Context", padding="5")
        context_frame.pack(fill=tk.X, pady=(0, 10))

        self.context_var = tk.StringVar(value="general")
        def on_context_change(*args):
            context_defaults = {
                "general": "You are a professional proofreader. Your task is to improve the following text.",
                "slack": "Proofread this as a Slack message: keep it concise, friendly, professional, and use relevant emojis if appropriate.",
                "email": "Proofread this as a business email: ensure a professional tone, proper structure, greeting, and closing."
            }
            chosen = self.context_var.get()
            # Optionally warn if modified --- skipped for simplicity
            self.proofread_prompt_text.delete("1.0", tk.END)
            self.proofread_prompt_text.insert("1.0", context_defaults.get(chosen, context_defaults["general"]))
        self.context_var.trace_add("write", on_context_change)
        ttk.Radiobutton(context_frame, text="General", variable=self.context_var, value="general").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(context_frame, text="Slack", variable=self.context_var, value="slack").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(context_frame, text="Email", variable=self.context_var, value="email").pack(side=tk.LEFT, padx=10)

        # Prompt/Response Notebook below input and context
        pr_notebook = ttk.Notebook(frame)
        pr_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        # Prompt tab (editable)
        self.proofread_prompt_text = scrolledtext.ScrolledText(pr_notebook, height=8, wrap=tk.WORD)
        default_prompt = "You are a professional proofreader. Your task is to improve the following text."
        self.proofread_prompt_text.insert("1.0", default_prompt)
        pr_notebook.add(self.proofread_prompt_text, text="Prompt")

        # Response tab (read-only)
        self.proofread_response_text = scrolledtext.ScrolledText(pr_notebook, height=12, wrap=tk.WORD, state='disabled')
        pr_notebook.add(self.proofread_response_text, text="Response")
        # Default to Response tab (index 1)
        pr_notebook.select(1)

        # Action buttons with allow_rewrite checkbox
        action_frame = ttk.Frame(frame)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(action_frame, text="Proofread", command=self._do_proofread_action).pack(side=tk.LEFT, padx=(0, 10))
        self.allow_rewrite_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(action_frame, text="Allow rewriting", variable=self.allow_rewrite_var).pack(side=tk.LEFT)

        # Track in sub-notebook map
        self._sub_notebook_map["Proofread"] = pr_notebook
        self._sub_notebook_selection["Proofread"] = 1
        pr_notebook.bind("<<NotebookTabChanged>>", lambda e: self._record_subtab("Proofread", pr_notebook.index("current")))

    def _create_explain_tab(self):
        """Create the explain tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Explain")

        # Input text area
        ttk.Label(frame, text="Technical Text to Explain:").pack(anchor=tk.W, pady=(10, 0))
        self.explain_input = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD)
        self.explain_input.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # Add sample text
        sample_text = "SSH keys are cryptographic key pairs used for secure authentication to remote systems. The public key is placed on the server, while the private key remains on the client machine."
        self.explain_input.insert("1.0", sample_text)

        # Prompt/Response Notebook
        expl_notebook = ttk.Notebook(frame)
        expl_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        # Prompt tab (editable)
        self.explain_prompt_text = scrolledtext.ScrolledText(expl_notebook, height=8, wrap=tk.WORD)
        default_prompt = "Explain the following content in an easy to understand paragraph for a general audience:"
        self.explain_prompt_text.insert("1.0", default_prompt)
        expl_notebook.add(self.explain_prompt_text, text="Prompt")

        # Response tab (read-only)
        self.explain_response_text = scrolledtext.ScrolledText(expl_notebook, height=12, wrap=tk.WORD, state='disabled')
        expl_notebook.add(self.explain_response_text, text="Response")
        # Default to Response tab (index 1)
        expl_notebook.select(1)

        # Action button
        ttk.Button(frame, text="Explain", command=self._do_explain_action).pack(anchor=tk.W, pady=(0, 10))

        # Track in sub-notebook map
        self._sub_notebook_map["Explain"] = expl_notebook
        self._sub_notebook_selection["Explain"] = 1
        expl_notebook.bind("<<NotebookTabChanged>>", lambda e: self._record_subtab("Explain", expl_notebook.index("current")))

    def _create_commands_tab(self):
        """Create the commands tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Commands")

        # Input text area
        ttk.Label(frame, text="Task Description:").pack(anchor=tk.W, pady=(10, 0))
        self.commands_input = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD)
        self.commands_input.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # Add sample text
        sample_text = "copy my SSH public key to clipboard"
        self.commands_input.insert("1.0", sample_text)

        # OS selection
        os_frame = ttk.Frame(frame)
        os_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(os_frame, text="Operating System:").pack(side=tk.LEFT, padx=(0, 5))
        self.os_var = tk.StringVar(value="macos")
        ttk.Radiobutton(os_frame, text="macOS", variable=self.os_var, value="macos").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(os_frame, text="Linux", variable=self.os_var, value="linux").pack(side=tk.LEFT, padx=10)

        # Prompt/Response Notebook
        cmd_notebook = ttk.Notebook(frame)
        cmd_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        # Prompt tab (editable)
        self.commands_prompt_text = scrolledtext.ScrolledText(cmd_notebook, height=8, wrap=tk.WORD)
        default_prompt = "List 1 to 3 alternative command-line commands to accomplish the given task (no explanation, no comments)."
        self.commands_prompt_text.insert("1.0", default_prompt)
        cmd_notebook.add(self.commands_prompt_text, text="Prompt")

        # Response tab (read-only)
        self.commands_response_text = scrolledtext.ScrolledText(cmd_notebook, height=12, wrap=tk.WORD, state='disabled')
        cmd_notebook.add(self.commands_response_text, text="Response")
        # Default to Response tab (index 1)
        cmd_notebook.select(1)

        # Action button
        ttk.Button(frame, text="Get Commands", command=self._do_commands_action).pack(anchor=tk.W, pady=(0, 10))

        # Track in sub-notebook map
        self._sub_notebook_map["Commands"] = cmd_notebook
        self._sub_notebook_selection["Commands"] = 1
        cmd_notebook.bind("<<NotebookTabChanged>>", lambda e: self._record_subtab("Commands", cmd_notebook.index("current")))

    def _create_question_tab(self):
        """Create the question (Q&A) tab."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Q&A")

        # Input text area
        ttk.Label(frame, text="Question:").pack(anchor=tk.W, pady=(10, 0))
        self.question_input = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD)
        self.question_input.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        # Add sample text
        sample_text = "What is the capital of France?"
        self.question_input.insert("1.0", sample_text)

        # Prompt/Response Notebook
        qa_notebook = ttk.Notebook(frame)
        qa_notebook.pack(fill=tk.BOTH, expand=True, pady=(5, 10))

        # Prompt tab (editable)
        self.question_prompt_text = scrolledtext.ScrolledText(qa_notebook, height=8, wrap=tk.WORD)
        default_prompt = "Answer the following question as accurately and concisely as possible:"
        self.question_prompt_text.insert("1.0", default_prompt)
        qa_notebook.add(self.question_prompt_text, text="Prompt")

        # Response tab (read-only)
        self.question_response_text = scrolledtext.ScrolledText(qa_notebook, height=12, wrap=tk.WORD, state='disabled')
        qa_notebook.add(self.question_response_text, text="Response")
        # Default to Response tab (index 1)
        qa_notebook.select(1)

        # Action button
        ttk.Button(frame, text="Ask", command=self._do_question_action).pack(anchor=tk.W, pady=(0, 10))

        # Track in sub-notebook map
        self._sub_notebook_map["Q&A"] = qa_notebook
        self._sub_notebook_selection["Q&A"] = 1
        qa_notebook.bind("<<NotebookTabChanged>>", lambda e: self._record_subtab("Q&A", qa_notebook.index("current")))

    def _prefill_clipboard(self):
        """Prefill clipboard content into the current tab's input field."""
        clipboard_text = getattr(self.args, 'clipboard', '') or ''
        if clipboard_text:
            # Get current tab and prefill the appropriate input field
            current_tab = self.notebook.tab(self.notebook.select(), "text")
            if current_tab == "Proofread" and hasattr(self, 'proofread_input'):
                self.proofread_input.delete("1.0", tk.END)
                self.proofread_input.insert("1.0", clipboard_text)
            elif current_tab == "Explain" and hasattr(self, 'explain_input'):
                self.explain_input.delete("1.0", tk.END)
                self.explain_input.insert("1.0", clipboard_text)
            elif current_tab == "Commands" and hasattr(self, 'commands_input'):
                self.commands_input.delete("1.0", tk.END)
                self.commands_input.insert("1.0", clipboard_text)
            elif current_tab == "Q&A" and hasattr(self, 'question_input'):
                self.question_input.delete("1.0", tk.END)
                self.question_input.insert("1.0", clipboard_text)

    def _on_model_change(self, event=None):
        """Handle model selection change."""
        selected_model = self.model_var.get()
        if selected_model != self.selected_model:
            self.selected_model = selected_model
            self._oci_client = None  # Reset client to use new model
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

    def _copy_result(self):
        """Copy the current result to clipboard for the active tab."""
        current_tab = self.notebook.tab(self.notebook.select(), "text")
        widget = None
        if current_tab == "Proofread":
            widget = self.proofread_response_text
        elif current_tab == "Explain":
            widget = self.explain_response_text
        elif current_tab == "Commands":
            widget = self.commands_response_text
        elif current_tab == "Q&A":
            widget = self.question_response_text

        if widget is not None:
            result = widget.get("1.0", tk.END).strip()
            if result:
                self.root.clipboard_clear()
                self.root.clipboard_append(result)
                self.status_var.set("Result copied to clipboard")

    def _display_result(self, result: str, current_tab):
        """Display result in the current tab's result text area."""
        widget = None
        sub_notebook = None
        if current_tab == "Proofread":
            widget = self.proofread_response_text
            sub_notebook = self._sub_notebook_map.get("Proofread")
        elif current_tab == "Explain":
            widget = self.explain_response_text
            sub_notebook = self._sub_notebook_map.get("Explain")
        elif current_tab == "Commands":
            widget = self.commands_response_text
            sub_notebook = self._sub_notebook_map.get("Commands")
        elif current_tab == "Q&A":
            widget = self.question_response_text
            sub_notebook = self._sub_notebook_map.get("Q&A")

        if widget is not None:
            widget.config(state='normal')
            widget.delete("1.0", tk.END)
            widget.insert("1.0", result)
            widget.config(state='disabled')
        self.last_result = result
        self.status_var.set("Ready")
        # Always select Response sub-tab upon display
        if sub_notebook:
            sub_notebook.select(1)
            self._sub_notebook_selection[current_tab] = 1

    def _do_proofread_action(self):
        """Handle proofread button click."""
        template = self.proofread_prompt_text.get("1.0", tk.END).strip()
        user_text = self.proofread_input.get("1.0", tk.END).strip()
        if not user_text:
            messagebox.showwarning("Input Required", "Please enter text to proofread.")
            return

        # Build actual prompt from template and input text
        prompt = f"{template}\n\nText:\n{user_text}"

        self.status_var.set("Processing request...")

        def worker():
            start_time = time.time()
            try:
                client = self._get_oci_client()
                model_name = self.model_var.get()
                messages = [{"role": "user", "content": prompt}]
                response = client.invoke(messages, max_tokens=1000, temperature=0.3)
                result = str(response.content).strip()
                processing_time = time.time() - start_time
                self.root.after(0, lambda: self._display_result(result, "Proofread"))
                self.root.after(0, lambda: self.status_var.set(f"Response ready ({processing_time:.2f}s)"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Proofreading failed: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _do_explain_action(self):
        """Handle explain button click."""
        template = self.explain_prompt_text.get("1.0", tk.END).strip()
        input_text = self.explain_input.get("1.0", tk.END).strip()
        if not input_text:
            messagebox.showwarning("Input Required", "Please enter text to explain.")
            return

        # Build actual prompt
        prompt = f"{template}\n\nContent:\n{input_text}"

        self.status_var.set("Processing request...")

        def worker():
            start_time = time.time()
            try:
                client = self._get_oci_client()
                model_name = self.model_var.get()
                messages = [{"role": "user", "content": prompt}]
                response = client.invoke(messages, max_tokens=400, temperature=0.2)
                result = str(response.content).strip()
                processing_time = time.time() - start_time
                self.root.after(0, lambda: self._display_result(result, "Explain"))
                self.root.after(0, lambda: self.status_var.set(f"Response ready ({processing_time:.2f}s)"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Explanation failed: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _do_commands_action(self):
        """Handle commands button click."""
        template = self.commands_prompt_text.get("1.0", tk.END).strip()
        input_desc = self.commands_input.get("1.0", tk.END).strip()
        if not input_desc:
            messagebox.showwarning("Input Required", "Please enter a task description.")
            return

        # Build actual prompt
        prompt = f"{template}\n\nTask:\n{input_desc}\n"

        self.status_var.set("Processing request...")

        def worker():
            start_time = time.time()
            try:
                client = self._get_oci_client()
                model_name = self.model_var.get()
                messages = [{"role": "user", "content": prompt}]
                response = client.invoke(messages, max_tokens=256, temperature=0.2)
                result = str(response.content).strip()
                # Post-process list output (for command-only bulleted lists)
                lines = []
                for line in result.splitlines():
                    line = line.strip()
                    if line.startswith('- '):
                        line = line[2:]
                    elif line and line[0] in '123' and len(line) > 1 and line[1] in '.)':
                        line = line[2:].strip()
                    if line:
                        lines.append(line)
                final_result = '\n'.join(lines) if lines else result
                processing_time = time.time() - start_time
                self.root.after(0, lambda: self._display_result(final_result, "Commands"))
                self.root.after(0, lambda: self.status_var.set(f"Response ready ({processing_time:.2f}s)"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Command generation failed: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _do_question_action(self):
        """Handle question button click."""
        template = self.question_prompt_text.get("1.0", tk.END).strip()
        question_text = self.question_input.get("1.0", tk.END).strip()
        if not question_text:
            messagebox.showwarning("Input Required", "Please enter a question.")
            return

        # Build actual prompt from template and input
        prompt = f"{template}\n\nQuestion:\n{question_text}"

        self.status_var.set("Processing request...")

        def worker():
            start_time = time.time()
            try:
                client = self._get_oci_client()
                model_name = self.model_var.get()
                messages = [{"role": "user", "content": prompt}]
                response = client.invoke(messages, max_tokens=1000, temperature=0.7)
                result = str(response.content).strip()
                processing_time = time.time() - start_time
                self.root.after(0, lambda: self._display_result(result, "Q&A"))
                self.root.after(0, lambda: self.status_var.set(f"Response ready ({processing_time:.2f}s)"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Question answering failed: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _on_main_tab_changed(self, event):
        """Sync sub-notebook selection on main tab change."""
        notebook = event.widget
        tab_text = notebook.tab(notebook.select(), "text")
        sub_notebook = self._sub_notebook_map.get(tab_text)
        if sub_notebook:
            index = self._sub_notebook_selection.get(tab_text, 1)
            sub_notebook.select(index)

    def _record_subtab(self, tab_text, idx):
        """Record last selected sub-tab for tab."""
        self._sub_notebook_selection[tab_text] = idx

    def _get_oci_client(self):
        """Get or create OCI client."""
        if self._oci_client is None:
            settings = get_settings()
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
