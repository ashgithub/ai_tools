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
from mcp import ClientSession
from mcp.client.sse import sse_client
from ai_tools.utils.config import get_settings



class JsonFormRenderer:
    """Renders dynamic forms from JSON configuration."""

    def __init__(self, parent_frame, form_config: Dict[str, Any], on_submit_callback):
        self.parent = parent_frame
        self.config = form_config
        self.on_submit = on_submit_callback
        self.widgets = {}
        self.values = {}

    def render(self):
        """Render the form based on JSON config."""
        # Clear existing widgets
        for widget in self.parent.winfo_children():
            widget.destroy()

        # Create form fields
        for field in self.config.get('fields', []):
            self._create_field(field)

        # Create action buttons
        if 'actions' in self.config:
            self._create_actions(self.config['actions'])

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
        self.sessions = {}  # MCP server connections
        self.active_tab = None

        # Parse command line arguments
        self.args = self._parse_args()

        # Set up UI
        self._setup_ui()

        # Initialize MCP connections in background
        self._initialize_connections()

    def __del__(self):
        """Clean up connections when the client is destroyed."""
        try:
            # Close all connections
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            for connection in self.sessions.values():
                loop.run_until_complete(connection.close())
        except Exception:
            pass  # Ignore cleanup errors

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

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self.tab_frames = {}
        self.form_renderers = {}
        for tab_config in self.config.get('tabs', []):
            tab_name = tab_config['name']
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=tab_name)
            self.tab_frames[tab_name] = frame

            # Create form renderer for this tab
            renderer = JsonFormRenderer(frame, tab_config, self._handle_form_submit)
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

    def _initialize_connections(self):
        """Initialize MCP server connections in background."""
        self.status_var.set("Connecting to servers...")
        thread = threading.Thread(target=self._connect_to_servers)
        thread.daemon = True
        thread.start()

    def _connect_to_servers(self):
        """Connect to all required MCP servers."""
        try:
            settings = get_settings()
            servers_to_connect = set()

            # Determine which servers we need
            for tab_config in self.config.get('tabs', []):
                server_name = tab_config.get('server')
                if server_name:
                    servers_to_connect.add(server_name)

            # Connect to each server
            for server_name in servers_to_connect:
                if server_name in settings.servers.__dict__:
                    server_cfg = getattr(settings.servers, server_name)
                    try:
                        self._connect_single_server(server_name, server_cfg)
                        print(f"✅ Connected to {server_name} server")
                    except Exception as e:
                        print(f"❌ Failed to connect to {server_name} server: {e}")
                        self.root.after(0, lambda: self.status_var.set(f"Failed to connect to {server_name}"))

            self.root.after(0, lambda: self.status_var.set("Connected - Ready"))

        except Exception as e:
            error_msg = f"Connection error: {e}"
            self.root.after(0, lambda: self.status_var.set(f"Error: {error_msg}"))

    def _connect_single_server(self, server_name: str, server_cfg):
        """Connect to a single MCP server."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._connect_single_server_async(server_name, server_cfg))
        except Exception as e:
            print(f"❌ Failed to connect to {server_name}: {e}")
            raise

    async def _connect_single_server_async(self, server_name: str, server_cfg):
        """Connect to a single MCP server asynchronously."""
        server_url = f"http://{server_cfg.host}:{server_cfg.port}/{server_cfg.transport}"

        # For short-lived app, just test connection and mark as available
        async with sse_client(server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                # Just store a marker that this server is available
                self.sessions[server_name] = True

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

    async def _call_tool_async(self, server_name: str, tool_name: str, arguments: Dict[str, Any]):
        """Call an MCP tool asynchronously."""
        # Get server config
        settings = get_settings()
        if server_name not in settings.servers.__dict__:
            raise Exception(f"Server {server_name} not configured")

        server_cfg = getattr(settings.servers, server_name)
        server_url = f"http://{server_cfg.host}:{server_cfg.port}/{server_cfg.transport}"

        # Create session and call tool
        async with sse_client(server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call the tool
                result = await session.call_tool(tool_name, arguments=arguments)

                # Extract text from result
                if result.content and len(result.content) > 0:
                    content = result.content[0]
                    if hasattr(content, 'text'):
                        return content.text
                    else:
                        return str(content)
                else:
                    return "No result returned"

    def _process_request(self, tab_config: Dict[str, Any], action: Dict[str, Any], values: Dict[str, Any]):
        """Process the request using appropriate MCP server."""
        try:
            server_name = tab_config.get('server')
            if not server_name:
                self.root.after(0, lambda: self._show_error("No server specified for this tab"))
                return

            # Determine tool name
            tool_name = action.get('tool')
            if 'tool_template' in action:
                # Replace template variables
                tool_name = action['tool_template']
                for key, value in values.items():
                    tool_name = tool_name.replace(f"{{{key}}}", str(value))

            if not tool_name:
                self.root.after(0, lambda: self._show_error("No tool specified for this action"))
                return

            # Prepare arguments - only include fields that map to tool parameters
            arguments = {}
            for field in tab_config.get('fields', []):
                field_id = field['id']
                if field_id in values and 'maps_to_tool_param' in field:
                    # Map field to tool parameter
                    param_name = field['maps_to_tool_param']
                    arguments[param_name] = values[field_id]

            # Call the tool
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(self._call_tool_async(server_name, tool_name, arguments))

            # Display result
            self.root.after(0, lambda: self._display_result(result))

        except Exception as e:
            exc_msg = str(e).strip()
            if not exc_msg:
                exc_msg = f"{type(e).__name__}"
            error_msg = f"Processing error: {exc_msg}"
            self.root.after(0, lambda: self._show_error(error_msg))

    def _display_result(self, result: str):
        """Display the processing result."""
        # Create result window
        result_window = tk.Toplevel(self.root)
        result_window.title("Result")
        result_window.geometry("600x400")

        # Result text area
        text_area = scrolledtext.ScrolledText(result_window, wrap=tk.WORD)
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_area.insert("1.0", result)
        text_area.config(state='disabled')

        # Store result for copying
        self.last_result = result

        # Buttons
        button_frame = ttk.Frame(result_window)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(button_frame, text="Copy to Clipboard", command=self._copy_result_to_clipboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Use as Input", command=lambda: self._use_result_as_input(result)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=result_window.destroy).pack(side=tk.RIGHT, padx=5)

        self.status_var.set("Processing complete")

    def _use_result_as_input(self, result: str):
        """Use the result as input for the current tab."""
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
