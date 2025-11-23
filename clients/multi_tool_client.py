#!/usr/bin/env python3
"""
Dynamic JSON-Form GUI Client for multiple MCP servers.
Provides a tabbed interface with context-aware tab selection for macOS Shortcuts integration.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
import json
import sys
import os
from typing import Dict, Any, Optional, List
from ai_tools.oci_openai_helper import OCIOpenAIHelper
from ai_tools.utils.config import get_settings
from ai_tools.utils.prompts import build_proofread_prompt
from envyaml import EnvYAML



class JsonFormRenderer:
    """Renders dynamic forms from JSON configuration."""

    def __init__(self, parent_frame, form_config: Dict[str, Any], on_submit_callback, on_exit_callback=None):
        self.parent = parent_frame
        self.config = form_config
        self.on_submit = on_submit_callback
        self.on_exit = on_exit_callback
        self.widgets = {}
        self.values = {}
        self.result_text = None
        self.result_frame = None

    def render(self):
        """Render the form based on JSON config."""
        # Clear existing widgets
        for widget in self.parent.winfo_children():
            widget.destroy()

        # Create form fields
        for field in self.config.get('fields', []):
            self._create_field(field)

        # Create prompt display/edit area
        self._create_prompt_area()

        # Create action buttons
        if 'actions' in self.config:
            self._create_actions(self.config['actions'])

        # Create result area
        self._create_result_area()

    def _create_field(self, field: Dict[str, Any]):
        """Create a single form field."""
        field_id = field['id']
        field_type = field['type']
        label_text = field.get('label', field_id)

        # Create label
        label = ttk.Label(self.parent, text=label_text)
        label.pack(anchor='w', pady=(10, 0))

        # Create widget based on type
        if field_type == 'textarea':
            widget = scrolledtext.ScrolledText(self.parent, height=8, wrap=tk.WORD)
            if field.get('prefill_from_clipboard'):
                # Will be set later from command line args
                pass
        elif field_type == 'text':
            widget = ttk.Entry(self.parent)
        elif field_type == 'select':
            widget = ttk.Combobox(self.parent, values=[opt.get('label', opt['value']) for opt in field['options']])
            widget.set(field.get('default', ''))
        elif field_type == 'radio':
            # Create frame for radio buttons
            radio_frame = ttk.Frame(self.parent)
            widget = tk.StringVar(value=field.get('default', ''))
            for option in field.get('options', []):
                opt_value = option if isinstance(option, str) else option['value']
                opt_label = option if isinstance(option, str) else option.get('label', opt_value)
                ttk.Radiobutton(radio_frame, text=opt_label, variable=widget, value=opt_value).pack(side=tk.LEFT, padx=5)
            # Store the variable
            self.widgets[field_id] = widget
        elif field_type == 'checkbox':
            widget = ttk.Checkbutton(self.parent, text="")
            widget.state(['!alternate'])  # Unchecked by default
            if field.get('default', False):
                widget.state(['selected'])

        self.widgets[field_id] = widget

        # Pack the widget
        if field_type == 'radio':
            radio_frame.pack(anchor='w', pady=(0, 5))
        elif field_type == 'textarea':
            widget.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        else:
            widget.pack(fill=tk.X, pady=(0, 10))

    def _create_actions(self, actions: List[Dict[str, Any]]):
        """Create action buttons."""
        button_frame = ttk.Frame(self.parent)
        button_frame.pack(fill=tk.X, pady=10)

        for action in actions:
            btn = ttk.Button(button_frame, text=action['label'],
                           command=lambda a=action: self._handle_action(a))
            btn.pack(side=tk.LEFT, padx=5)

    def _create_prompt_area(self):
        """Create prompt display/edit area."""
        # Prompt selector frame
        prompt_frame = ttk.LabelFrame(self.parent, text="Prompt Template", padding="5")
        prompt_frame.pack(fill=tk.X, pady=(10, 0))

        # Load available prompts from config
        settings = get_settings()
        available_prompts = list(settings.prompts.contexts.keys()) if hasattr(settings, 'prompts') and hasattr(settings.prompts, 'contexts') else ['general']

        # Prompt dropdown
        prompt_label = ttk.Label(prompt_frame, text="Context:")
        prompt_label.pack(side=tk.LEFT, padx=(0, 5))

        self.prompt_var = tk.StringVar(value=available_prompts[0] if available_prompts else 'general')
        prompt_combo = ttk.Combobox(prompt_frame, textvariable=self.prompt_var,
                                   values=available_prompts, state="readonly", width=20)
        prompt_combo.pack(side=tk.LEFT, padx=(0, 10))

        # Current prompt display area
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, height=4, wrap=tk.WORD, state='disabled')
        self.prompt_text.pack(fill=tk.X, pady=(5, 0))

        # Bind prompt change to update display
        prompt_combo.bind("<<ComboboxSelected>>", self._on_prompt_change)

        # Initial prompt display
        self._update_prompt_display()

    def _on_prompt_change(self, event=None):
        """Handle prompt selection change."""
        self._update_prompt_display()

    def _update_prompt_display(self):
        """Update the prompt display area with current context info."""
        selected_context = self.prompt_var.get()
        settings = get_settings()

        if hasattr(settings, 'prompts') and hasattr(settings.prompts, 'contexts') and selected_context in settings.prompts.contexts:
            context_desc = settings.prompts.contexts[selected_context]
            display_text = f"Context: {selected_context}\nDescription: {context_desc}"
        else:
            display_text = f"Context: {selected_context}\nDescription: Custom context"

        if self.prompt_text:
            self.prompt_text.config(state='normal')
            self.prompt_text.delete("1.0", tk.END)
            self.prompt_text.insert("1.0", display_text)
            self.prompt_text.config(state='disabled')

    def _create_result_area(self):
        """Create the result display area."""
        # Result section frame
        self.result_frame = ttk.LabelFrame(self.parent, text="Result", padding="5")
        self.result_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Result text area
        self.result_text = scrolledtext.ScrolledText(self.result_frame, height=8, wrap=tk.WORD, state='disabled')
        self.result_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Result action buttons
        result_button_frame = ttk.Frame(self.result_frame)
        result_button_frame.pack(fill=tk.X)

        ttk.Button(result_button_frame, text="Copy to Clipboard",
                  command=self._copy_result_to_clipboard).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(result_button_frame, text="Exit",
                  command=self._handle_exit).pack(side=tk.RIGHT)

    def display_result(self, result: str):
        """Display result in the inline result area."""
        if self.result_text:
            self.result_text.config(state='normal')
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert("1.0", result)
            self.result_text.config(state='disabled')

    def _copy_result_to_clipboard(self):
        """Copy the current result to clipboard."""
        if self.result_text:
            result = self.result_text.get("1.0", tk.END).strip()
            if result:
                self.parent.clipboard_clear()
                self.parent.clipboard_append(result)

    def _use_result_as_input(self):
        """Use the result as input for the form."""
        if self.result_text:
            result = self.result_text.get("1.0", tk.END).strip()
            if result:
                # Find the input text field and set its value
                for field in self.config.get('fields', []):
                    if field.get('prefill_from_clipboard') or field['id'] == 'input_text':
                        self.set_field_value(field['id'], result)
                        break

    def _clear_result(self):
        """Clear the result area."""
        if self.result_text:
            self.result_text.config(state='normal')
            self.result_text.delete("1.0", tk.END)
            self.result_text.config(state='disabled')

    def _handle_exit(self):
        """Handle exit button click."""
        if self.on_exit:
            self.on_exit()
        else:
            # Default to quitting the parent window
            parent = self.parent
            while parent and not isinstance(parent, tk.Tk):
                parent = parent.master
            if parent:
                parent.quit()

    def _handle_action(self, action: Dict[str, Any]):
        """Handle button click."""
        # Collect form values
        self.values = self._get_form_values()

        # Call the submit callback
        if self.on_submit:
            self.on_submit(action, self.values)

    def _get_form_values(self) -> Dict[str, Any]:
        """Get current values from all form fields."""
        values = {}
        for field_id, widget in self.widgets.items():
            field_config = next((f for f in self.config.get('fields', []) if f['id'] == field_id), {})
            field_type = field_config.get('type')

            if field_type == 'textarea':
                values[field_id] = widget.get("1.0", tk.END).strip()
            elif field_type == 'text':
                values[field_id] = widget.get()
            elif field_type == 'select':
                values[field_id] = widget.get()
            elif field_type == 'radio':
                values[field_id] = widget.get()
            elif field_type == 'checkbox':
                values[field_id] = bool('selected' in widget.state())

        return values

    def set_field_value(self, field_id: str, value: str):
        """Set a field value programmatically."""
        if field_id not in self.widgets:
            return

        widget = self.widgets[field_id]
        field_config = next((f for f in self.config.get('fields', []) if f['id'] == field_id), {})
        field_type = field_config.get('type')

        if field_type == 'textarea':
            widget.delete("1.0", tk.END)
            widget.insert("1.0", value)
        elif field_type == 'text':
            widget.delete(0, tk.END)
            widget.insert(0, value)
        elif field_type == 'select':
            widget.set(value)
        elif field_type == 'radio':
            widget.set(value)
        elif field_type == 'checkbox':
            if value:
                widget.state(['selected'])
            else:
                widget.state(['!selected'])


class DynamicFormClient:
    """Multi-tab dynamic form client with MCP server integration."""

    def __init__(self, root, config_file: str = None):
        self.root = root
        self.config_file = config_file or os.path.join(os.path.dirname(__file__), 'form_config.json')
        self.config = self._load_config()
        self.active_tab = None
        self._oci_client = None
        self.selected_model = None
        self.available_models = self._load_available_models()

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

    def _load_config(self) -> Dict[str, Any]:
        """Load JSON form configuration."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create default config if file doesn't exist
            return self._create_default_config()

    def _load_available_models(self) -> List[str]:
        """Load available LLM models from docs/llm_models.md."""
        models_file = os.path.join(os.path.dirname(__file__), '..', 'docs', 'llm_models.md')
        models = []

        try:
            with open(models_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('- '):
                        # Extract model name from format: "- model.name – description"
                        parts = line[2:].split(' – ', 1)
                        if len(parts) >= 1:
                            model_part = parts[0].strip()
                            if model_part:
                                models.append(model_part)
        except FileNotFoundError:
            # Fallback to default model if file not found
            settings = get_settings()
            models = [settings.oci.default_model]

        return models

    def _create_model_selector(self):
        """Create the model selector dropdown at the top of the window."""
        # Model selector frame
        model_frame = ttk.Frame(self.root)
        model_frame.pack(fill=tk.X, padx=10, pady=5)

        # Label
        ttk.Label(model_frame, text="LLM Model:").pack(side=tk.LEFT, padx=(0, 5))

        # Model dropdown
        self.model_var = tk.StringVar()
        settings = get_settings()
        self.model_var.set(settings.oci.default_model)  # Set default

        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var,
                                       values=self.available_models, state="readonly", width=40)
        self.model_combo.pack(side=tk.LEFT, padx=(0, 10))

        # Bind model change to update client
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        # Refresh button
        ttk.Button(model_frame, text="🔄", width=3,
                  command=self._refresh_models).pack(side=tk.LEFT)

    def _on_model_change(self, event=None):
        """Handle model selection change."""
        selected_model = self.model_var.get()
        if selected_model != self.selected_model:
            self.selected_model = selected_model
            # Reset client so it uses the new model
            self._oci_client = None
            self.status_var.set(f"Model changed to: {selected_model}")

    def _refresh_models(self):
        """Refresh the list of available models."""
        old_model = self.model_var.get()
        self.available_models = self._load_available_models()

        # Update the combobox values
        if hasattr(self, 'model_combo'):
            self.model_combo['values'] = self.available_models
            # If current model is still available, keep it; otherwise set to first available
            if old_model in self.available_models:
                self.model_var.set(old_model)
            elif self.available_models:
                self.model_var.set(self.available_models[0])
                self._on_model_change()  # Trigger model change event

        self.status_var.set(f"Models refreshed: {len(self.available_models)} available")

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default JSON configuration."""
        config = {
            "title": "AI Text Tools",
            "window": {"width": 700, "height": 600},
            "smart_defaults": {
                "terminal_apps": ["terminal", "iterm", "console", "hyper", "warp"],
                "communication_apps": ["mail", "messages", "slack", "discord", "teams", "notion", "obsidian"],
                "browser_apps": ["safari", "chrome", "firefox", "edge", "preview", "acrobat", "reader"],
                "default_tab": "Proofread"
            },
            "tabs": [
                {
                    "name": "Proofread",
                    "server": "proofread",
                    "default_for": ["communication_apps"],
                    "fields": [
                        {
                            "id": "input_text",
                            "type": "textarea",
                            "label": "Text to Proofread",
                            "prefill_from_clipboard": True
                        },
                        {
                            "id": "context",
                            "type": "radio",
                            "label": "Context",
                            "options": ["slack", "email", "general"],
                            "default": "general"
                        },
                        {
                            "id": "allow_rewrite",
                            "type": "checkbox",
                            "label": "Allow rewriting for better clarity",
                            "default": True
                        }
                    ],
                    "actions": [
                        {"id": "proofread", "label": "Proofread", "tool_template": "proofread_{context}"}
                    ]
                },
                {
                    "name": "Explain",
                    "server": "techlookup",
                    "default_for": ["browser_apps"],
                    "fields": [
                        {
                            "id": "input_text",
                            "type": "textarea",
                            "label": "Technical Text to Explain",
                            "prefill_from_clipboard": True
                        }
                    ],
                    "actions": [
                        {"id": "explain", "label": "Explain", "tool": "explain_tech_text"}
                    ]
                },
                {
                    "name": "Commands",
                    "server": "techlookup",
                    "default_for": ["terminal_apps"],
                    "fields": [
                        {
                            "id": "input_text",
                            "type": "textarea",
                            "label": "Task Description",
                            "prefill_from_clipboard": True,
                            "placeholder": "Describe what you want to do..."
                        },
                        {
                            "id": "os",
                            "type": "select",
                            "label": "Operating System",
                            "options": [
                                {"value": "macos", "label": "macOS"},
                                {"value": "linux", "label": "Linux"}
                            ],
                            "default": "macos"
                        }
                    ],
                    "actions": [
                        {"id": "commands", "label": "Get Commands", "tool": "list_linux_commands"}
                    ]
                },
                {
                    "name": "Question",
                    "fields": [
                        {
                            "id": "input_text",
                            "type": "textarea",
                            "label": "Question or Prompt",
                            "prefill_from_clipboard": True,
                            "placeholder": "Ask anything..."
                        }
                    ],
                    "actions": [
                        {"id": "question", "label": "Ask", "tool": "ask_question"}
                    ]
                }
            ],
            "global_actions": [
                {"id": "copy_result", "label": "Copy Result to Clipboard"},
                {"id": "close", "label": "Close"}
            ]
        }

        # Save default config
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

        return config

    def _setup_ui(self):
        """Set up the main UI."""
        self.root.title(self.config.get('title', 'AI Text Tools'))

        # Set window size
        window_config = self.config.get('window', {})
        width = window_config.get('width', 700)
        height = window_config.get('height', 600)
        self.root.geometry(f"{width}x{height}")

        # Create model selector at the top
        self._create_model_selector()

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        # Create tabs
        self.tab_frames = {}
        self.form_renderers = {}
        for tab_config in self.config.get('tabs', []):
            tab_name = tab_config['name']
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=tab_name)
            self.tab_frames[tab_name] = frame

            # Create form renderer for this tab
            renderer = JsonFormRenderer(frame, tab_config, self._handle_form_submit, self.root.quit)
            self.form_renderers[tab_name] = renderer
            renderer.render()

        # Global actions at bottom
        self._create_global_actions()

        # Status bar
        self.status_var = tk.StringVar(value="Initializing...")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Set default tab based on active app
        self._set_smart_default_tab()

        # Prefill clipboard content
        self._prefill_clipboard_content()

    def _create_global_actions(self):
        """Create global action buttons."""
        action_frame = ttk.Frame(self.root)
        action_frame.pack(fill=tk.X, padx=10, pady=5)

        for action in self.config.get('global_actions', []):
            if action['id'] == 'copy_result':
                btn = ttk.Button(action_frame, text=action['label'], command=self._copy_result_to_clipboard)
                btn.pack(side=tk.LEFT, padx=5)
            elif action['id'] == 'close':
                btn = ttk.Button(action_frame, text=action['label'], command=self.root.quit)
                btn.pack(side=tk.LEFT, padx=5)

    def _set_smart_default_tab(self):
        """Set the default tab based on active application."""
        active_app = getattr(self.args, 'app', '') or ''
        smart_config = self.config.get('smart_defaults', {})

        default_tab = smart_config.get('default_tab', 'Proofread')

        if active_app:
            app_lower = active_app.lower()

            # Check each category
            for category, apps in smart_config.items():
                if category.endswith('_apps') and isinstance(apps, list):
                    if any(app_keyword in app_lower for app_keyword in apps):
                        # Find which tab this category maps to
                        for tab_config in self.config.get('tabs', []):
                            if category in tab_config.get('default_for', []):
                                default_tab = tab_config['name']
                                break
                        break

        # Set the active tab
        for i, tab_config in enumerate(self.config.get('tabs', [])):
            if tab_config['name'] == default_tab:
                self.notebook.select(i)
                self.active_tab = default_tab
                break

    def _prefill_clipboard_content(self):
        """Prefill clipboard content into appropriate fields."""
        clipboard_text = getattr(self.args, 'clipboard', '') or ''

        if clipboard_text:
            # Prefill in all tabs that have prefill_from_clipboard fields
            for tab_name, renderer in self.form_renderers.items():
                for field in renderer.config.get('fields', []):
                    if field.get('prefill_from_clipboard'):
                        renderer.set_field_value(field['id'], clipboard_text)

    def _handle_form_submit(self, action: Dict[str, Any], values: Dict[str, Any]):
        """Handle form submission."""
        current_tab = self.notebook.tab(self.notebook.select(), "text")
        tab_config = next((t for t in self.config['tabs'] if t['name'] == current_tab), {})

        if not tab_config:
            return

        # Update status
        self.status_var.set("Processing...")

        # Run processing in background thread
        thread = threading.Thread(target=self._process_request,
                                args=(tab_config, action, values))
        thread.daemon = True
        thread.start()

    def _get_oci_client(self):
        """Get or create OCI client."""
        if self._oci_client is None:
            settings = get_settings()
            config = EnvYAML("config.yaml")
            self._oci_client = OCIOpenAIHelper.get_client(
                model_name=settings.oci.default_model,
                config=config,
            )
        return self._oci_client

    def _process_request(self, tab_config: Dict[str, Any], action: Dict[str, Any], values: Dict[str, Any]):
        """Process the request using direct LLM calls."""
        try:
            # Get the client
            client = self._get_oci_client()

            # Determine action type and call appropriate function
            action_id = action.get('id')
            if action_id == 'proofread':
                result = self._do_proofread(values)
            elif action_id == 'explain':
                result = self._do_explain(values)
            elif action_id == 'commands':
                result = self._do_commands(values)
            elif action_id == 'question':
                result = self._do_question(values)
            else:
                result = f"Unknown action: {action_id}"

            # Display result
            self.root.after(0, lambda: self._display_result(result))

        except Exception as e:
            exc_msg = str(e).strip()
            if not exc_msg:
                exc_msg = f"{type(e).__name__}"
            error_msg = f"Processing error: {exc_msg}"
            self.root.after(0, lambda: self._show_error(error_msg))

    def _display_result(self, result: str):
        """Display the processing result inline."""
        # Get current tab renderer and display result inline
        current_tab = self.notebook.tab(self.notebook.select(), "text")
        renderer = self.form_renderers.get(current_tab)
        if renderer:
            renderer.display_result(result)

        # Store result for copying
        self.last_result = result

        self.status_var.set("Ready")

    def _use_result_as_input(self, result: Optional[str]):
        """Use the result as input for the current tab."""
        if not result:
            return

        current_tab = self.notebook.tab(self.notebook.select(), "text")
        renderer = self.form_renderers.get(current_tab)
        if renderer:
            # Find the input text field
            for field in renderer.config.get('fields', []):
                if field.get('prefill_from_clipboard') or field['id'] == 'input_text':
                    renderer.set_field_value(field['id'], result)
                    break

    def _copy_result_to_clipboard(self):
        """Copy the last result to clipboard."""
        if hasattr(self, 'last_result') and self.last_result:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.last_result)
            self.status_var.set("Result copied to clipboard")

    def _do_proofread(self, values: Dict[str, Any]) -> str:
        """Perform proofreading using direct LLM call."""
        try:
            text = values.get('input_text', '')
            context = values.get('context', 'general')
            allow_rewrite = values.get('allow_rewrite', True)

            client = self._get_oci_client()
            prompt = build_proofread_prompt(
                text=text,
                context_key=context,
                instructions="",
                can_rewrite=allow_rewrite,
            )

            messages = [{"role": "user", "content": prompt}]
            response = client.invoke(messages, max_tokens=1000, temperature=0.3)
            return str(response.content).strip()

        except Exception as e:
            return f"Error proofreading text: {str(e)}"

    def _do_explain(self, values: Dict[str, Any]) -> str:
        """Explain technical text using direct LLM call."""
        try:
            text = values.get('input_text', '')
            client = self._get_oci_client()

            prompt = (
                "Explain the following technical content in an easy to understand paragraph, for a general audience with some computer experience but not an expert.\n\n"
                f"Content:\n{text}\n"
            )

            messages = [{"role": "user", "content": prompt}]
            response = client.invoke(messages, max_tokens=400, temperature=0.2)
            return str(response.content).strip()

        except Exception as e:
            return f"Error explaining text: {str(e)}"

    def _do_commands(self, values: Dict[str, Any]) -> str:
        """Generate commands using direct LLM call."""
        try:
            query = values.get('input_text', '')
            os_type = values.get('os', 'macos')
            client = self._get_oci_client()

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

            return '\n'.join(lines)

        except Exception as e:
            return f"Error generating commands: {str(e)}"

    def _do_question(self, values: Dict[str, Any]) -> str:
        """Ask a direct question to the LLM."""
        try:
            question = values.get('input_text', '')
            client = self._get_oci_client()

            messages = [{"role": "user", "content": question}]
            response = client.invoke(messages, max_tokens=1000, temperature=0.7)
            return str(response.content).strip()

        except Exception as e:
            return f"Error asking question: {str(e)}"

    def _show_error(self, message: str):
        """Show error message."""
        print(f"❌ GUI Error: {message}")
        self.status_var.set("Error occurred")
        messagebox.showerror("Error", message)


def main():
    # Check if config file exists, create if not
    config_file = os.path.join(os.path.dirname(__file__), 'form_config.json')

    root = tk.Tk()
    app = DynamicFormClient(root, config_file)

    # Bring window to front
    root.lift()
    root.focus_force()
    root.attributes('-topmost', True)
    root.after(100, lambda: root.attributes('-topmost', False))

    root.mainloop()


if __name__ == "__main__":
    main()
