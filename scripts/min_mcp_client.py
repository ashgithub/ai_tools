#!/usr/bin/env python3
"""
GUI Client for the Proofreading MCP Server.
Provides a user interface to proofread text in different contexts (Slack, Email, General).
Allows iterative proofreading until the user is satisfied.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client


class ProofreadClient:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Proofreader")
        self.root.geometry("800x700")

        # Server configuration
        self.server_url = "http://127.0.0.1:8000/sse"
        
        # Create UI components first
        self.create_widgets()
        
        # Current text being proofread
        self.current_text = ""
        self.proofread_history = []

    def create_widgets(self):
        """Create the GUI components."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="wens")

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(4, weight=1)

        # Title
        title_label = ttk.Label(main_frame, text="AI Proofreader", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Context selection
        context_frame = ttk.LabelFrame(main_frame, text="Context", padding="5")
        context_frame.grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 10))

        self.context_var = tk.StringVar(value="slack")
        ttk.Radiobutton(context_frame, text="Slack", variable=self.context_var, value="slack").grid(row=0, column=0, padx=5)
        ttk.Radiobutton(context_frame, text="Email", variable=self.context_var, value="email").grid(row=0, column=1, padx=5)
        ttk.Radiobutton(context_frame, text="General Text", variable=self.context_var, value="text").grid(row=0, column=2, padx=5)

        # Rewrite option
        self.rewrite_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(context_frame, text="Allow rewriting for better clarity", variable=self.rewrite_var).grid(row=1, column=0, columnspan=3, pady=(5, 0))

        # Input section
        input_frame = ttk.LabelFrame(main_frame, text="Original Text", padding="5")
        input_frame.grid(row=2, column=0, columnspan=2, sticky="wens", pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=1)

        self.input_text = scrolledtext.ScrolledText(input_frame, height=8, wrap=tk.WORD)
        self.input_text.grid(row=0, column=0, sticky="wens")

        # Instructions
        ttk.Label(main_frame, text="Additional Instructions (optional):").grid(row=3, column=0, sticky="w", pady=(0, 5))
        self.instructions_entry = ttk.Entry(main_frame)
        self.instructions_entry.grid(row=3, column=1, sticky="we", pady=(0, 10))

        # Output section
        output_frame = ttk.LabelFrame(main_frame, text="Proofread Result", padding="5")
        output_frame.grid(row=4, column=0, columnspan=2, sticky="wens", pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output_text = scrolledtext.ScrolledText(output_frame, height=8, wrap=tk.WORD, state='disabled')
        self.output_text.grid(row=0, column=0, sticky="wens")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=(0, 10))

        self.proofread_button = ttk.Button(button_frame, text="Proofread", command=self.proofread_text)
        self.proofread_button.grid(row=0, column=0, padx=(0, 10))

        self.accept_button = ttk.Button(button_frame, text="Accept & Copy", command=self.accept_result, state='disabled')
        self.accept_button.grid(row=0, column=1, padx=(0, 10))

        self.iterate_button = ttk.Button(button_frame, text="Use as Input", command=self.iterate_with_result, state='disabled')
        self.iterate_button.grid(row=0, column=2, padx=(0, 10))

        self.clear_button = ttk.Button(button_frame, text="Clear All", command=self.clear_all)
        self.clear_button.grid(row=0, column=3)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=6, column=0, columnspan=2, sticky="we")

    def proofread_text(self):
        """Send text to MCP server for proofreading."""
        text = self.input_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Input Required", "Please enter some text to proofread.")
            return

        instructions = self.instructions_entry.get().strip()
        context = self.context_var.get()
        can_rewrite = self.rewrite_var.get()

        # Update status
        self.status_var.set("Proofreading...")
        self.proofread_button.config(state='disabled')

        # Run in thread to avoid blocking UI
        thread = threading.Thread(target=self._call_proofread_api, args=(text, context, instructions, can_rewrite))
        thread.daemon = True
        thread.start()

    def _call_proofread_api(self, text, context, instructions, can_rewrite):
        """Call the MCP proofreading API - same pattern as minimal test."""
        try:
            # Run async code in this thread
            asyncio.run(self._async_proofread(text, context, instructions, can_rewrite))
        except Exception as e:
            error_msg = f"Error: {e}"
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self._show_error(error_msg))

    async def _async_proofread(self, text, context, instructions, can_rewrite):
        """Async method to call the MCP tool - same pattern as minimal test."""
        try:
            # Determine tool name based on context
            tool_name = f"proofread_{context}"
            
            # Connect using SSE transport (same as minimal test)
            async with sse_client(self.server_url) as (read_stream, write_stream):
                # Create client session (same as minimal test)
                async with ClientSession(read_stream, write_stream) as session:
                    # Initialize the session (same as minimal test)
                    await session.initialize()
                    
                    # Call the tool (same as minimal test)
                    result = await session.call_tool(
                        tool_name,
                        arguments={
                            "text": text,
                            "instructions": instructions,
                            "can_rewrite": can_rewrite
                        }
                    )
                    
                    # Extract text from result (same as minimal test)
                    if result.content and len(result.content) > 0:
                        proofread_text = result.content[0].text
                    else:
                        proofread_text = "No result returned"
                    
                    # Update UI in main thread
                    self.root.after(0, lambda: self._display_result(proofread_text, text))
                    
        except Exception as e:
            error_msg = f"Error: {e}"
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: self._show_error(error_msg))

    def _display_result(self, proofread_text, original_text):
        """Display the proofread result in the UI."""
        self.output_text.config(state='normal')
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", proofread_text)
        self.output_text.config(state='disabled')

        # Enable action buttons
        self.accept_button.config(state='normal')
        self.iterate_button.config(state='normal')

        # Update status
        self.status_var.set("Proofreading complete")
        self.proofread_button.config(state='normal')

        # Store for history
        self.current_text = proofread_text
        self.proofread_history.append((original_text, proofread_text))

    def _show_error(self, error_msg):
        """Show error message in UI."""
        self.output_text.config(state='normal')
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", f"Error: {error_msg}")
        self.output_text.config(state='disabled')

        self.status_var.set("Error occurred")
        self.proofread_button.config(state='normal')

    def accept_result(self):
        """Accept the current result and copy to clipboard."""
        if self.current_text:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_text)
            messagebox.showinfo("Success", "Proofread text copied to clipboard!")

    def iterate_with_result(self):
        """Use the proofread result as new input for further editing."""
        if self.current_text:
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", self.current_text)
            self.output_text.config(state='normal')
            self.output_text.delete("1.0", tk.END)
            self.output_text.config(state='disabled')
            self.accept_button.config(state='disabled')
            self.iterate_button.config(state='disabled')
            self.status_var.set("Result moved to input for further editing")

    def clear_all(self):
        """Clear all text fields and reset state."""
        self.input_text.delete("1.0", tk.END)
        self.instructions_entry.delete(0, tk.END)
        self.output_text.config(state='normal')
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state='disabled')
        self.accept_button.config(state='disabled')
        self.iterate_button.config(state='disabled')
        self.current_text = ""
        self.status_var.set("Ready")


def main():
    root = tk.Tk()
    app = ProofreadClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()