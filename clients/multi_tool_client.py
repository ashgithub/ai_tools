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
from typing import Any, Optional
from ai_tools.agent_runtime import AgentRuntimeError, AgentRequest, DeepAgentRuntime
from ai_tools.utils.config import get_settings
from ai_tools.utils.model_cache import (
    ModelCatalogBootstrapError,
    get_cached_or_refreshed_models,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimplifiedTextToolsGUI:
    """Clean, simplified GUI for AI text tools."""

    def __init__(self, root):
        self.root = root
        self.args = self._parse_args()
        self.root.title("AI Text Tools")
        self._configure_window_geometry()
        self.root.minsize(800, 700)
        self.root.resizable(True, True)

        self.settings = get_settings()
        self.selected_model: Optional[str] = None
        self.available_models, self.initial_default_model = self._load_available_models()
        self.agent_runtime = DeepAgentRuntime(self.settings)
        self.last_result: Optional[str] = None
        self.last_agent_response_by_tab: dict[str, Any] = {}
        self.current_text = ""
        self.previous_tab = None
        self.selected_command = tk.StringVar()
        self.selected_proofread = tk.StringVar()

        # Map tab names to widgets
        self.input_widgets = {}
        self.prompt_widgets = {}
        self.resolved_prompt_widgets = {}
        self.template_overrides = {}
        self.active_template_keys = {}
        self.response_widgets = {}
        self.sub_notebooks = {}
        self.sub_notebook_selections = {}

        # Read from stdin if --text not provided and stdin is not a tty
        if self.args.text is None:
            if not sys.stdin.isatty():
                self.args.text = sys.stdin.read().strip()
        self.current_text = self.args.text or ""
        self.app_mappings = self.settings.app_mappings
        self.tabs_config = self.settings.tabs
        self.os_options = self.settings.commands.os_options
        self.context_defaults = {"general": "General", "slack": "Slack", "email": "Email"}
        self._setup_ui()

    def _parse_args(self):
        """Parse command line arguments."""
        import argparse
        parser = argparse.ArgumentParser(description='AI Text Tools GUI')
        parser.add_argument('--app', help='Application context to select the appropriate tab based on config.yaml mappings')
        parser.add_argument('--tab', help='Explicit tab override (Proofread, Explain, Commands, Q&A)')
        parser.add_argument('--text', help='Text content to pre-populate in the selected tab\'s input field')
        parser.add_argument('--window-x', type=int, help='X position of the application window')
        parser.add_argument('--window-y', type=int, help='Y position of the application window')
        parser.add_argument('--window-width', type=int, default=900, help='Window width')
        parser.add_argument('--window-height', type=int, default=800, help='Window height')
        return parser.parse_args()

    def _configure_window_geometry(self):
        """Configure initial window geometry and clamp to visible virtual bounds."""
        width = max(800, self.args.window_width)
        height = max(700, self.args.window_height)

        self.root.update_idletasks()
        vroot_x = self.root.winfo_vrootx()
        vroot_y = self.root.winfo_vrooty()
        vroot_width = self.root.winfo_vrootwidth()
        vroot_height = self.root.winfo_vrootheight()
        max_x = vroot_x + max(0, vroot_width - width)
        max_y = vroot_y + max(0, vroot_height - height)

        if self.args.window_x is None or self.args.window_y is None:
            centered_x = vroot_x + max(0, (vroot_width - width) // 2)
            centered_y = vroot_y + max(0, (vroot_height - height) // 2)
            clamped_x = min(max(centered_x, vroot_x), max_x)
            clamped_y = min(max(centered_y, vroot_y), max_y)
        else:
            clamped_x = min(max(self.args.window_x, vroot_x), max_x)
            clamped_y = min(max(self.args.window_y, vroot_y), max_y)
        self.root.geometry(f"{width}x{height}+{clamped_x}+{clamped_y}")

    def _get_mapping_for_app(self, app):
        """Get tab and config for a given app from mappings."""
        for tab, configs in self.app_mappings.items():
            for config in configs:
                if app in config.get('apps', []):
                    return {'tab': tab, 'config': config}
        return None

    def _load_available_models(self) -> tuple[list[str], str]:
        """Load available LLM models, falling back to configured default if cache is missing."""
        try:
            catalog = get_cached_or_refreshed_models(self.settings)
        except ModelCatalogBootstrapError as exc:
            fallback_default = (self.settings.oci.default_model or "").strip() or "openai.gpt-5"
            logger.warning(
                "Model catalog bootstrap unavailable; using fallback default model=%s error=%s",
                fallback_default,
                exc,
            )
            return [fallback_default], fallback_default
        except Exception as exc:
            raise ModelCatalogBootstrapError(
                f"Unexpected model catalog error while loading cache/OCI models: {exc}"
            ) from exc

        models = [entry["id"] for entry in catalog.get("models", []) if entry.get("id")]
        default_model = catalog.get("default_model")
        if not models:
            raise ModelCatalogBootstrapError(
                "Model catalog is empty after cache/OCI loading."
            )
        if not default_model or default_model not in models:
            default_model = models[0]

        logger.info(
            "Model catalog loaded source=%s cache_age_hours=%s default_model=%s",
            catalog.get("source", "unknown"),
            f"{catalog.get('cache_age_hours'):.2f}" if isinstance(catalog.get("cache_age_hours"), (int, float)) else "n/a",
            default_model,
        )
        return models, default_model

    def _setup_ui(self):
        """Set up the main UI."""
        self._create_model_selector()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        for tab_name, config in self.tabs_config.items():
            self._create_tab(tab_name, config)

        self.notebook.bind("<<NotebookTabChanged>>", self._on_main_tab_changed)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # if no text is passed cler out the app name
        if not self.args.text or len(self.args.text.strip()) == 0:
            self.args.app = None 
            
        # Handle CLI args for tab selection and text population
        mapping = self._get_mapping_for_app(self.args.app.lower()) if self.args.app else None
        if self.args.tab:
            tab_name = self.args.tab.strip()
            if tab_name not in self.tabs_config:
                valid_tabs = ", ".join(self.tabs_config.keys())
                messagebox.showerror("Invalid --tab", f"Unknown tab '{tab_name}'. Valid tabs: {valid_tabs}")
                self.root.destroy()
                raise SystemExit(2)
        elif mapping:
            tab_name = mapping['tab']
        else:
            tab_name = 'Q&A'
        tab_index = list(self.tabs_config.keys()).index(tab_name)
        self.notebook.select(tab_index)
        self.previous_tab = tab_name

        # Set tab-specific configs
        config = mapping['config'] if mapping else {}
        if tab_name == 'Proofread' and 'context' in config:
            self.context_var.set(config['context'])
        elif tab_name == 'Commands' and 'os' in config:
            self.os_var.set(config['os'])

        for loaded_tab_name in self.tabs_config.keys():
            self._activate_template_for_state(loaded_tab_name, persist_current=False)

        # Populate all tabs with current_text if provided
        for tab_name, widget in self.input_widgets.items():
            widget.delete("1.0", tk.END)
            if self.current_text:
                widget.insert("1.0", self.current_text)

        # Auto-submit if text was provided
        if self.current_text:
            active_tab = self.notebook.tab(self.notebook.select(), "text")
            self._run_action_for_tab(active_tab)

    def _create_tab(self, tab_name: str, config: dict):
        """Create a tab with input, prompt, and response areas."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=tab_name)

        # Input area
        ttk.Label(frame, text=config["input_label"]).pack(anchor=tk.W, pady=(10, 0))
        input_text = scrolledtext.ScrolledText(frame, height=8, wrap=tk.WORD)
        input_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.input_widgets[tab_name] = input_text

        # Response/Template/Resolved Prompt notebook
        sub_notebook = ttk.Notebook(frame)

        if tab_name in {"Commands", "Proofread"}:
            response_frame = ttk.Frame(sub_notebook)
            sub_notebook.add(response_frame, text="Response")
            self.response_widgets[tab_name] = response_frame
        else:
            response_text = scrolledtext.ScrolledText(sub_notebook, height=12, wrap=tk.WORD, state='normal')
            sub_notebook.add(response_text, text="Response")
            self.response_widgets[tab_name] = response_text

        prompt_text = scrolledtext.ScrolledText(sub_notebook, height=8, wrap=tk.WORD)
        prompt_text.insert("1.0", self._get_default_skill_instruction(tab_name))
        sub_notebook.add(prompt_text, text="Template")
        self.prompt_widgets[tab_name] = prompt_text

        resolved_prompt_text = scrolledtext.ScrolledText(
            sub_notebook, height=8, wrap=tk.WORD, state='disabled'
        )
        sub_notebook.add(resolved_prompt_text, text="Resolved Prompt")
        self.resolved_prompt_widgets[tab_name] = resolved_prompt_text

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

        ttk.Button(
            action_frame,
            text="Reset Template",
            command=lambda: self._reset_template(tab_name),
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(action_frame, text="Done", command=lambda: self._done_action(tab_name)).pack(
            side=tk.LEFT, padx=10
        )

    def _create_os_frame(self, frame):
        """Create OS selection frame for Commands tab."""
        os_frame = ttk.Frame(frame)
        os_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(os_frame, text="Operating System:").pack(side=tk.LEFT, padx=(0, 5))
        self.os_var = tk.StringVar(value=self.os_options[0])
        for os_name in self.os_options:
            ttk.Radiobutton(
                os_frame,
                text=os_name.capitalize(),
                variable=self.os_var,
                value=os_name,
                command=self._on_commands_os_change,
            ).pack(
                side=tk.LEFT, padx=10
            )

    def _create_context_frame(self, frame):
        """Create context selection frame for Proofread tab."""
        # Main context frame
        context_frame = ttk.LabelFrame(frame, text="Context & Options", padding="5")
        context_frame.pack(fill=tk.X, pady=(0, 10))

        # Context radio buttons
        context_defaults = self.context_defaults

        self.context_var = tk.StringVar(value="general")

        def on_context_change(*args):
            self._on_proofread_options_change()

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

    def _create_model_selector(self):
        """Create the model selector dropdown."""
        model_frame = ttk.Frame(self.root)
        model_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(model_frame, text="LLM Model:").pack(side=tk.LEFT, padx=(0, 5))

        self.model_var = tk.StringVar()
        self.model_var.set(self.initial_default_model)

        self.model_combo = ttk.Combobox(
            model_frame, textvariable=self.model_var,
            values=self.available_models, state="readonly", width=40
        )
        self.model_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        ttk.Button(
            model_frame,
            text="Refresh Models",
            command=self._run_refresh_models,
        ).pack(side=tk.LEFT, padx=(0, 10))

    def _on_model_change(self, event=None):
        """Handle model selection change."""
        selected_model = self.model_var.get()
        if selected_model != self.selected_model:
            self.selected_model = selected_model
            self.status_var.set(f"Model: {selected_model}")



    def _render_resolved_prompt(self, tab_name: str, prompt: str):
        """Render the resolved prompt in a read-only widget."""
        widget = self.resolved_prompt_widgets[tab_name]
        widget.config(state='normal')
        widget.delete("1.0", tk.END)
        widget.insert("1.0", prompt)
        widget.config(state='disabled')

    def _get_template_key(self, tab_name: str):
        """Return the active session key for template overrides."""
        if tab_name == "Proofread":
            context_value = self.context_var.get() if hasattr(self, "context_var") else "general"
            return (tab_name, context_value)
        if tab_name == "Commands":
            os_value = self.os_var.get() if hasattr(self, "os_var") else (self.os_options[0] if self.os_options else "macos")
            return (tab_name, os_value)
        return (tab_name,)

    def _request_options_for_tab(self, tab_name: str) -> dict:
        options = {}
        if tab_name == "Proofread":
            options["proofread_context"] = self.context_var.get() if hasattr(self, "context_var") else "general"
        elif tab_name == "Commands":
            options["selected_os"] = self.os_var.get() if hasattr(self, "os_var") else (
                self.os_options[0] if self.os_options else "macos"
            )
        return options

    def _build_agent_request(self, tab_name: str, input_text: str, *, instruction_override: str | None = None) -> AgentRequest:
        options = self._request_options_for_tab(tab_name)
        if instruction_override is not None:
            options["instruction_override"] = instruction_override
        return AgentRequest(
            input_text=input_text,
            ui_tab=tab_name,
            app_context=self.args.app,
            options=options,
            selected_model=self.model_var.get(),
        )

    def _get_default_skill_instruction(self, tab_name: str) -> str:
        """Load default skill instruction for current tab/options."""
        request = self._build_agent_request(tab_name, "")
        _, instruction = self.agent_runtime.preview_instruction(request)
        return instruction

    def _set_template_text(self, tab_name: str, value: str):
        widget = self.prompt_widgets[tab_name]
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)

    def _activate_template_for_state(self, tab_name: str, persist_current: bool = True):
        """Switch template text based on current options and session overrides."""
        if tab_name not in self.prompt_widgets:
            return
        old_key = self.active_template_keys.get(tab_name)
        if persist_current and old_key is not None:
            current_text = self.prompt_widgets[tab_name].get("1.0", tk.END).rstrip("\n")
            self.template_overrides[old_key] = current_text

        new_key = self._get_template_key(tab_name)
        self.active_template_keys[tab_name] = new_key
        if new_key in self.template_overrides:
            template_text = self.template_overrides[new_key]
        else:
            template_text = self._get_default_skill_instruction(tab_name)
        self._set_template_text(tab_name, template_text)

    def _on_proofread_options_change(self):
        self._activate_template_for_state("Proofread", persist_current=True)

    def _on_commands_os_change(self):
        self._activate_template_for_state("Commands", persist_current=True)

    def _reset_template(self, tab_name: str):
        """Reset current option-keyed session override back to skill default."""
        key = self._get_template_key(tab_name)
        self.template_overrides.pop(key, None)
        self.active_template_keys[tab_name] = key
        self._set_template_text(tab_name, self._get_default_skill_instruction(tab_name))
        self.status_var.set("Template reset to skill default for current options.")

    def _run_action_for_tab(self, tab_name: str):
        """Generic handler for all tab action buttons."""
        config = self.tabs_config[tab_name]
        input_text = self.input_widgets[tab_name].get("1.0", tk.END).strip()

        if not input_text:
            messagebox.showwarning("Input Required", f"Please enter {config['input_label'].lower()}")
            return

        active_template = self.prompt_widgets[tab_name].get("1.0", tk.END).rstrip("\n")
        current_key = self._get_template_key(tab_name)
        self.active_template_keys[tab_name] = current_key
        self.template_overrides[current_key] = active_template

        request = self._build_agent_request(
            tab_name,
            input_text,
            instruction_override=active_template,
        )
        resolved_payload = self.agent_runtime.preview_resolved_payload(
            request,
            instruction_override=active_template,
        )
        self._render_resolved_prompt(tab_name, resolved_payload)
        logger.info(
            "Resolved payload prepared tab=%s model=%s payload_chars=%d",
            tab_name,
            self.model_var.get(),
            len(resolved_payload),
        )

        self._run_action(tab_name, request)

    def _run_action(self, tab_name: str, request: AgentRequest):
        """Run an AI action in a background thread."""
        self.status_var.set("Processing request...")

        def worker():
            start_time = time.time()
            try:
                response = self.agent_runtime.invoke(request)
                processing_time = time.time() - start_time
                self.root.after(0, lambda: self._display_result(tab_name, response))
                self.root.after(0, lambda: self.status_var.set(f"Response ready ({processing_time:.2f}s)"))
            except AgentRuntimeError as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"{e.code}: {e.message}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {e.code}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _run_refresh_models(self):
        """Refresh model cache via refresh skill and reload dropdown."""
        self.status_var.set("Refreshing models...")

        def worker():
            try:
                refresh_request = AgentRequest(
                    input_text="",
                    ui_tab="Q&A",
                    app_context=self.args.app,
                    options={"action": "refresh_models"},
                    selected_model=self.model_var.get(),
                )
                self.agent_runtime.invoke(refresh_request)

                catalog = get_cached_or_refreshed_models(self.settings)
                models = [entry["id"] for entry in catalog.get("models", []) if entry.get("id")]
                default_model = catalog.get("default_model")
                if not models:
                    raise RuntimeError("Model catalog is empty after refresh.")
                if not default_model or default_model not in models:
                    default_model = models[0]

                self.available_models = models
                self.initial_default_model = default_model

                def apply_ui():
                    self.model_combo["values"] = self.available_models
                    self.model_var.set(self.initial_default_model)
                    self.selected_model = self.initial_default_model
                    self.status_var.set(f"Models refreshed ({len(self.available_models)} available)")

                self.root.after(0, apply_ui)
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("Refresh Failed", str(exc)))
                self.root.after(0, lambda: self.status_var.set(f"Refresh failed: {exc}"))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _display_result(self, tab_name: str, response):
        """Display result in the response area."""
        result = response.output_text
        structured = response.structured_output or {}
        self.last_agent_response_by_tab[tab_name] = response

        if tab_name == "Commands":
            # Render command cards with one-line explanations and selection radio.
            frame = self.response_widgets[tab_name]
            for widget in frame.winfo_children():
                widget.destroy()

            self.selected_command = tk.StringVar()
            alternatives = structured.get("alternatives", [])
            if not isinstance(alternatives, list):
                alternatives = []

            if alternatives:
                for idx, item in enumerate(alternatives, start=1):
                    command = str(item.get("command", "")).strip() if isinstance(item, dict) else ""
                    explanation = str(item.get("explanation", "")).strip() if isinstance(item, dict) else ""
                    if not command:
                        continue
                    card = ttk.LabelFrame(frame, text=f"Option {idx}", padding=6)
                    card.pack(fill=tk.X, expand=True, padx=4, pady=4)
                    ttk.Radiobutton(
                        card,
                        text=command,
                        variable=self.selected_command,
                        value=command,
                    ).pack(anchor=tk.W)
                    if explanation:
                        ttk.Label(card, text=explanation, wraplength=700, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))
                if not self.selected_command.get() and alternatives:
                    first = alternatives[0]
                    if isinstance(first, dict) and first.get("command"):
                        self.selected_command.set(str(first["command"]))
            else:
                ttk.Label(frame, text=result, wraplength=700, justify=tk.LEFT).pack(anchor=tk.W, padx=4, pady=4)
            self.last_result = response.primary_output or result
        elif tab_name == "Proofread":
            frame = self.response_widgets[tab_name]
            for widget in frame.winfo_children():
                widget.destroy()

            if isinstance(structured, dict) and structured.get("original") is not None:
                original = str(structured.get("original", "")).strip()
                rewritten = str(structured.get("rewritten", "")).strip()
                self.selected_proofread = tk.StringVar(value=rewritten or original)

                chooser = ttk.Frame(frame)
                chooser.pack(fill=tk.X, padx=4, pady=(4, 2))
                ttk.Label(chooser, text="Use version:").pack(side=tk.LEFT, padx=(0, 8))
                ttk.Radiobutton(
                    chooser,
                    text="Rewritten",
                    variable=self.selected_proofread,
                    value=rewritten,
                ).pack(side=tk.LEFT, padx=(0, 8))
                ttk.Radiobutton(
                    chooser,
                    text="Original",
                    variable=self.selected_proofread,
                    value=original,
                ).pack(side=tk.LEFT)

                notebook = ttk.Notebook(frame)
                notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

                rewritten_tab = ttk.Frame(notebook)
                notebook.add(rewritten_tab, text="Rewritten")
                rewritten_text = scrolledtext.ScrolledText(rewritten_tab, height=16, wrap=tk.WORD)
                rewritten_text.pack(fill=tk.BOTH, expand=True)
                rewritten_text.insert("1.0", rewritten)
                rewritten_text.config(state="disabled")

                original_tab = ttk.Frame(notebook)
                notebook.add(original_tab, text="Original")
                original_text = scrolledtext.ScrolledText(original_tab, height=16, wrap=tk.WORD)
                original_text.pack(fill=tk.BOTH, expand=True)
                original_text.insert("1.0", original)
                original_text.config(state="disabled")

                notebook.select(0)

                def on_proofread_tab_change(event):
                    selected = event.widget.tab(event.widget.select(), "text")
                    if selected == "Rewritten":
                        self.selected_proofread.set(rewritten)
                    else:
                        self.selected_proofread.set(original)

                notebook.bind("<<NotebookTabChanged>>", on_proofread_tab_change)
                self.last_result = self.selected_proofread.get().strip() or (response.primary_output or result)
            else:
                ttk.Label(frame, text=response.primary_output or result, wraplength=700, justify=tk.LEFT).pack(
                    anchor=tk.W, padx=4, pady=4
                )
                self.last_result = response.primary_output or result
        else:
            widget = self.response_widgets[tab_name]
            widget.config(state='normal')
            widget.delete("1.0", tk.END)
            widget.insert("1.0", response.primary_output or result)
            self.last_result = response.primary_output or result
        # Switch to Response tab
        self.sub_notebooks[tab_name].select(0)
        self.sub_notebook_selections[tab_name] = 0

    def _on_main_tab_changed(self, event):
        """Sync text across tabs and restore sub-notebook selection."""
        notebook = event.widget
        new_tab = notebook.tab(notebook.select(), "text")

        # Update current_text from previous tab if it exists
        if self.previous_tab and self.previous_tab != new_tab:
            prev_widget = self.input_widgets.get(self.previous_tab)
            if prev_widget:
                self.current_text = prev_widget.get("1.0", tk.END).strip()

        # Set the new tab's text to current_text
        new_widget = self.input_widgets.get(new_tab)
        if new_widget:
            new_widget.delete("1.0", tk.END)
            new_widget.insert("1.0", self.current_text)

        # Restore sub-notebook selection
        sub_notebook = self.sub_notebooks.get(new_tab)
        if sub_notebook:
            index = self.sub_notebook_selections.get(new_tab, 0)
            sub_notebook.select(index)

        # Update previous_tab
        self.previous_tab = new_tab

    def _done_action(self, tab_name: str):
        """Handle Done button: print response and exit."""
        response = self.last_agent_response_by_tab.get(tab_name)
        if tab_name == "Commands":
            result = self.selected_command.get().strip()
            if not result:
                result = (response.primary_output if response else "").strip() or "no command selected"
        elif tab_name == "Proofread":
            result = self.selected_proofread.get().strip()
            if not result:
                result = (response.primary_output if response else "").strip() or "no result"
        else:
            if response and response.primary_output:
                result = response.primary_output.strip()
            else:
                result = self.response_widgets[tab_name].get("1.0", tk.END).strip()
            if not result:
                result = "no result"
        print(result)
        self.root.quit()
        sys.exit(0)

def main():
    """Main entry point."""
    root = tk.Tk()
    try:
        app = SimplifiedTextToolsGUI(root)
    except ModelCatalogBootstrapError as exc:
        print(
            f"[MODEL_CATALOG_BOOTSTRAP_ERROR] script={__file__} error={exc}",
            file=sys.stderr,
        )
        root.destroy()
        raise SystemExit(22)

    # Bring window to front
    root.lift()
    root.focus_force()
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))

    root.mainloop()


if __name__ == "__main__":
    main()
