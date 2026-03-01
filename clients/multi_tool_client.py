#!/usr/bin/env python3
"""Universal AI Text Tools GUI client."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Any, Optional

from ai_tools.agent_runtime import AgentRuntimeError, AgentRequest, DeepAgentRuntime
from ai_tools.utils.config import get_settings
from ai_tools.utils.model_cache import ModelCatalogBootstrapError, get_cached_or_refreshed_models

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class UniversalTextToolsGUI:
    """Single-workspace GUI for agentic deep agent workflows."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.args = self._parse_args()
        self.root.title("AI Text Tools")
        self._configure_window_geometry()
        self.root.minsize(900, 700)
        self.root.resizable(True, True)

        self.settings = get_settings()
        self.agent_runtime = DeepAgentRuntime(self.settings)

        self.selected_model: Optional[str] = None
        self.available_models, self.initial_default_model = self._load_available_models()
        self.nudge_presets = self._load_nudge_presets()

        self.last_agent_response: Any | None = None
        self.selected_alternative = tk.StringVar()
        self.selected_text_pair = tk.StringVar()
        self.is_busy = False

        self._setup_ui()
        self._bind_shortcuts()

        if self.args.text is None and not sys.stdin.isatty():
            self.args.text = sys.stdin.read().strip()

        if self.args.text:
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", self.args.text)
            self._run_action()

    def _parse_args(self):
        parser = argparse.ArgumentParser(description="AI Text Tools GUI")
        parser.add_argument("--app", help="Application context hint")
        parser.add_argument("--tab", help="Legacy alias that maps to nudge")
        parser.add_argument("--nudge", help="Nudge hint for schema selection")
        parser.add_argument("--text", help="Input text")
        parser.add_argument("--window-x", type=int, help="Window X")
        parser.add_argument("--window-y", type=int, help="Window Y")
        parser.add_argument("--window-width", type=int, default=900, help="Window width")
        parser.add_argument("--window-height", type=int, default=800, help="Window height")
        return parser.parse_args()

    def _configure_window_geometry(self):
        width = max(900, self.args.window_width)
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

    def _load_nudge_presets(self) -> list[str]:
        presets = ["auto"]
        for item in self.settings.agentic_routing.nudge_presets:
            if item and item not in presets:
                presets.append(item)
        return presets

    def _load_available_models(self) -> tuple[list[str], str]:
        try:
            catalog = get_cached_or_refreshed_models(self.settings)
        except ModelCatalogBootstrapError as exc:
            fallback_default = (self.settings.oci.default_model or "").strip() or "openai.gpt-5"
            logger.warning(
                "Model catalog unavailable; using fallback model=%s error=%s",
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
            raise ModelCatalogBootstrapError("Model catalog is empty after cache/OCI loading.")
        if not default_model or default_model not in models:
            default_model = models[0]
        return models, default_model

    def _setup_ui(self):
        self._create_model_selector()
        self._create_nudge_bar()

        body = ttk.Frame(self.root)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        header = ttk.Frame(body)
        header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(header, text="Input").pack(side=tk.LEFT)
        ttk.Label(
            header,
            text="Run: Cmd/Ctrl+Enter  Done: Cmd/Ctrl+D",
            foreground="#666666",
        ).pack(side=tk.RIGHT)

        self.input_text = scrolledtext.ScrolledText(body, height=11, wrap=tk.WORD)
        self.input_text.pack(fill=tk.BOTH, expand=False, pady=(0, 8))

        self.results_notebook = ttk.Notebook(body)
        self.results_notebook.pack(fill=tk.BOTH, expand=True)

        self.response_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(self.response_frame, text="Response")

        self.summary_text = scrolledtext.ScrolledText(self.results_notebook, height=10, wrap=tk.WORD, state="disabled")
        self.results_notebook.add(self.summary_text, text="Execution Summary")

        action_row = ttk.Frame(body)
        action_row.pack(fill=tk.X, pady=(8, 0))

        self.run_button = ttk.Button(action_row, text="Run", command=self._run_action)
        self.run_button.pack(side=tk.LEFT)
        self.done_button = ttk.Button(action_row, text="Done", command=self._done_action)
        self.done_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(action_row, text="Copy Output", command=self._copy_output).pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(fill=tk.X, side=tk.BOTTOM)

    def _create_model_selector(self):
        row = ttk.Frame(self.root)
        row.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(row, text="LLM Model:").pack(side=tk.LEFT, padx=(0, 5))
        self.model_var = tk.StringVar(value=self.initial_default_model)
        self.model_combo = ttk.Combobox(row, textvariable=self.model_var, values=self.available_models, state="readonly", width=40)
        self.model_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.model_combo.bind("<<ComboboxSelected>>", self._on_model_change)

        self.refresh_button = ttk.Button(row, text="Refresh Models", command=self._run_refresh_models)
        self.refresh_button.pack(side=tk.LEFT)

    def _create_nudge_bar(self):
        row = ttk.Frame(self.root)
        row.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(row, text="Nudge:").pack(side=tk.LEFT, padx=(0, 5))

        cli_nudge = (self.args.nudge or self.args.tab or self.settings.agentic_routing.default_nudge or "auto").strip().lower()
        if cli_nudge and cli_nudge not in self.nudge_presets:
            self.nudge_presets.append(cli_nudge)

        self.nudge_var = tk.StringVar(value=cli_nudge if cli_nudge else "auto")
        self.nudge_combo = ttk.Combobox(row, textvariable=self.nudge_var, values=self.nudge_presets, state="readonly", width=24)
        self.nudge_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.nudge_combo.bind("<<ComboboxSelected>>", self._on_nudge_change)

        ttk.Label(row, text="App context:").pack(side=tk.LEFT, padx=(0, 5))
        self.app_var = tk.StringVar(value=(self.args.app or "").strip())
        self.app_entry = ttk.Entry(row, textvariable=self.app_var, width=24)
        self.app_entry.pack(side=tk.LEFT)
        self.nudge_help = tk.StringVar(value="")
        ttk.Label(row, textvariable=self.nudge_help, foreground="#666666").pack(side=tk.LEFT, padx=(10, 0))
        self._refresh_nudge_help()

    def _bind_shortcuts(self):
        self.root.bind("<Command-Return>", lambda _e: self._run_action())
        self.root.bind("<Control-Return>", lambda _e: self._run_action())
        self.root.bind("<Command-d>", lambda _e: self._done_action())
        self.root.bind("<Control-d>", lambda _e: self._done_action())

    def _on_model_change(self, _event=None):
        self.selected_model = self.model_var.get()
        self.status_var.set(f"Model: {self.selected_model}")

    def _on_nudge_change(self, _event=None):
        self._refresh_nudge_help()

    def _refresh_nudge_help(self):
        nudge = (self.nudge_var.get() or "auto").strip().lower()
        if nudge in {"proofread", "slack", "email"}:
            self.nudge_help.set("Expected output: corrected + rewritten")
        elif nudge in {"commands", "command", "shell", "terminal"}:
            self.nudge_help.set("Expected output: 1-3 alternatives")
        else:
            self.nudge_help.set("Expected output: single text")

    def _set_busy(self, busy: bool):
        self.is_busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.run_button.config(state=state)
        self.done_button.config(state=state)
        self.refresh_button.config(state=state)
        self.model_combo.config(state="disabled" if busy else "readonly")
        self.nudge_combo.config(state="disabled" if busy else "readonly")

    def _build_request(self, text: str) -> AgentRequest:
        nudge = (self.nudge_var.get() or "").strip().lower()
        options: dict[str, Any] = {}
        if nudge and nudge != "auto":
            options["nudge"] = nudge

        return AgentRequest(
            input_text=text,
            ui_tab=nudge or "universal",
            app_context=(self.app_var.get() or None),
            options=options,
            selected_model=self.model_var.get(),
        )

    def _render_summary(self, summary: str):
        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", tk.END)
        self.summary_text.insert("1.0", summary)
        self.summary_text.config(state="disabled")

    def _run_action(self):
        if self.is_busy:
            return
        text = self.input_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Input Required", "Please enter text.")
            return

        request = self._build_request(text)
        self._render_summary(self.agent_runtime.preview_execution_summary(request))
        self.status_var.set("Processing request...")
        self._set_busy(True)

        def worker():
            started = time.time()
            try:
                response = self.agent_runtime.invoke(request)
                elapsed = time.time() - started
                self.root.after(0, lambda: self._display_result(response))
                self.root.after(0, lambda: self.status_var.set(f"Response ready ({elapsed:.2f}s)"))
            except AgentRuntimeError as exc:
                self.root.after(0, lambda e=exc: messagebox.showerror("Error", f"{e.code}: {e.message}"))
                self.root.after(0, lambda e=exc: self.status_var.set(f"Error: {e.code}"))
            except Exception as exc:  # pragma: no cover
                self.root.after(0, lambda e=exc: messagebox.showerror("Error", f"Failed: {e}"))
                self.root.after(0, lambda: self.status_var.set("Error"))
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _run_refresh_models(self):
        if self.is_busy:
            return
        self.status_var.set("Refreshing models...")
        self._set_busy(True)

        def worker():
            try:
                refresh_request = AgentRequest(
                    input_text="",
                    ui_tab="refresh",
                    app_context=(self.app_var.get() or None),
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

                def apply_ui():
                    self.available_models = models
                    self.initial_default_model = default_model
                    self.model_combo["values"] = self.available_models
                    self.model_var.set(self.initial_default_model)
                    self.selected_model = self.initial_default_model
                    self.status_var.set(f"Models refreshed ({len(self.available_models)} available)")

                self.root.after(0, apply_ui)
            except Exception as exc:
                self.root.after(0, lambda e=exc: messagebox.showerror("Refresh Failed", str(e)))
                self.root.after(0, lambda e=exc: self.status_var.set(f"Refresh failed: {e}"))
            finally:
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _display_result(self, response):
        self.last_agent_response = response
        for child in self.response_frame.winfo_children():
            child.destroy()

        structured = response.structured_output or {}
        render_kind = response.render_kind

        if render_kind == "alternatives":
            self.selected_alternative = tk.StringVar()
            alternatives = structured.get("alternatives", []) if isinstance(structured, dict) else []
            if isinstance(alternatives, list):
                for idx, item in enumerate(alternatives, start=1):
                    if not isinstance(item, dict):
                        continue
                    value = str(item.get("value", "")).strip()
                    explanation = str(item.get("explanation", "")).strip()
                    if not value:
                        continue
                    card = ttk.LabelFrame(self.response_frame, text=f"Option {idx}", padding=6)
                    card.pack(fill=tk.X, padx=4, pady=4)
                    ttk.Radiobutton(card, text=value, variable=self.selected_alternative, value=value).pack(anchor=tk.W)
                    if explanation:
                        ttk.Label(card, text=explanation, wraplength=760, justify=tk.LEFT).pack(anchor=tk.W, pady=(2, 0))
                if alternatives and isinstance(alternatives[0], dict):
                    self.selected_alternative.set(str(alternatives[0].get("value", "")).strip())
            if not self.response_frame.winfo_children():
                ttk.Label(self.response_frame, text=response.output_text, wraplength=760, justify=tk.LEFT).pack(anchor=tk.W)

        elif render_kind == "text_pair":
            corrected = str(structured.get("corrected", "")).strip() if isinstance(structured, dict) else ""
            rewritten = str(structured.get("rewritten", "")).strip() if isinstance(structured, dict) else ""
            self.selected_text_pair = tk.StringVar(value=rewritten or corrected)

            chooser = ttk.Frame(self.response_frame)
            chooser.pack(fill=tk.X, padx=4, pady=(4, 2))
            ttk.Label(chooser, text="Use version:").pack(side=tk.LEFT, padx=(0, 8))
            ttk.Radiobutton(chooser, text="Rewritten", variable=self.selected_text_pair, value=rewritten).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Radiobutton(chooser, text="Corrected", variable=self.selected_text_pair, value=corrected).pack(side=tk.LEFT)

            notebook = ttk.Notebook(self.response_frame)
            notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

            rewritten_tab = ttk.Frame(notebook)
            notebook.add(rewritten_tab, text="Rewritten")
            rewritten_text = scrolledtext.ScrolledText(rewritten_tab, height=16, wrap=tk.WORD)
            rewritten_text.pack(fill=tk.BOTH, expand=True)
            rewritten_text.insert("1.0", rewritten)
            rewritten_text.config(state="disabled")

            corrected_tab = ttk.Frame(notebook)
            notebook.add(corrected_tab, text="Corrected")
            corrected_text = scrolledtext.ScrolledText(corrected_tab, height=16, wrap=tk.WORD)
            corrected_text.pack(fill=tk.BOTH, expand=True)
            corrected_text.insert("1.0", corrected)
            corrected_text.config(state="disabled")

            notebook.select(0)

            def on_change(event):
                selected = event.widget.tab(event.widget.select(), "text")
                self.selected_text_pair.set(rewritten if selected == "Rewritten" else corrected)

            notebook.bind("<<NotebookTabChanged>>", on_change)
        else:
            text = str((structured.get("text") if isinstance(structured, dict) else "") or response.output_text).strip()
            widget = scrolledtext.ScrolledText(self.response_frame, height=18, wrap=tk.WORD)
            widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            widget.insert("1.0", text)
            widget.config(state="disabled")

        if response.execution_summary:
            self._render_summary(response.execution_summary)
        self.results_notebook.select(0)

    def _copy_output(self):
        response = self.last_agent_response
        if not response:
            self.status_var.set("Nothing to copy.")
            return

        if response.render_kind == "alternatives":
            output = self.selected_alternative.get().strip() or response.primary_output.strip()
        elif response.render_kind == "text_pair":
            output = self.selected_text_pair.get().strip() or response.primary_output.strip()
        else:
            output = response.primary_output.strip()

        if not output:
            self.status_var.set("Nothing to copy.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(output)
        self.status_var.set("Output copied to clipboard.")

    def _done_action(self):
        response = self.last_agent_response
        if not response:
            print("no result")
            self.root.quit()
            sys.exit(0)

        if response.render_kind == "alternatives":
            output = self.selected_alternative.get().strip() or response.primary_output.strip() or "no result"
        elif response.render_kind == "text_pair":
            output = self.selected_text_pair.get().strip() or response.primary_output.strip() or "no result"
        else:
            output = response.primary_output.strip() or "no result"

        print(output)
        self.root.quit()
        sys.exit(0)


def main():
    root = tk.Tk()
    try:
        UniversalTextToolsGUI(root)
    except ModelCatalogBootstrapError as exc:
        print(f"[MODEL_CATALOG_BOOTSTRAP_ERROR] script={__file__} error={exc}", file=sys.stderr)
        root.destroy()
        raise SystemExit(22)

    root.lift()
    root.focus_force()
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))
    root.mainloop()


if __name__ == "__main__":
    main()
