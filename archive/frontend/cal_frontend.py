"""Basic Calculator Frontend using Tkinter"""

import sys
import os

# Add parent directory to path to import backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archive.backend.cal_backend import Calculator
import tkinter as tk


class CalculatorApp:
    """GUI Calculator Application"""

    def __init__(self, root):
        self.root = root
        self.calc = Calculator()
        self.current_input = ""
        self.previous_input = ""
        self.operation = None
        self.should_clear = False

        self.setup_window()
        self.create_widgets()

    def setup_window(self):
        """Configure the main window"""
        self.root.title("Calculator")
        self.root.geometry("320x420")
        self.root.resizable(False, False)
        self.root.configure(bg="#2d2d2d")

    def create_widgets(self):
        """Create all UI widgets"""
        # Display
        self.display = tk.Entry(
            self.root,
            font=("Segoe UI", 28),
            justify="right",
            bd=0,
            bg="#1e1e1e",
            fg="#ffffff",
            insertbackground="white",
            highlightthickness=0
        )
        self.display.grid(row=0, column=0, columnspan=4, padx=20, pady=20, sticky="ew")

        # Button layout
        buttons = [
            ("C", 1, 0, "#ff6b6b"), ("⌫", 1, 1, "#ffa500"), ("%", 1, 2, "#ffa500"), ("/", 1, 3, "#ffa500"),
            ("7", 2, 0, "#3d3d3d"), ("8", 2, 1, "#3d3d3d"), ("9", 2, 2, "#3d3d3d"), ("*", 2, 3, "#ffa500"),
            ("4", 3, 0, "#3d3d3d"), ("5", 3, 1, "#3d3d3d"), ("6", 3, 2, "#3d3d3d"), ("-", 3, 3, "#ffa500"),
            ("1", 4, 0, "#3d3d3d"), ("2", 4, 1, "#3d3d3d"), ("3", 4, 2, "#3d3d3d"), ("+", 4, 3, "#ffa500"),
            ("±", 5, 0, "#3d3d3d"), ("0", 5, 1, "#3d3d3d"), (".", 5, 2, "#3d3d3d"), ("=", 5, 3, "#4ec9b0"),
        ]

        for (text, row, col, color) in buttons:
            btn = tk.Button(
                self.root,
                text=text,
                font=("Segoe UI", 18),
                bg=color,
                fg="#ffffff" if color != "#ffa500" else "#1e1e1e",
                activebackground="#555555",
                activeforeground="#ffffff",
                bd=0,
                command=lambda t=text: self.on_button_click(t)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew", ipadx=10, ipady=10)

        # Configure grid weights
        for i in range(6):
            self.root.grid_rowconfigure(i, weight=1)
        for i in range(4):
            self.root.grid_columnconfigure(i, weight=1)

        # Bind keyboard
        self.root.bind("<Key>", self.on_key_press)

    def on_button_click(self, text):
        """Handle button clicks"""
        if text in "0123456789":
            self.input_number(text)
        elif text == ".":
            self.input_decimal()
        elif text in "+-*/":
            self.input_operator(text)
        elif text == "=":
            self.calculate()
        elif text == "C":
            self.clear()
        elif text == "⌫":
            self.backspace()
        elif text == "%":
            self.percentage()
        elif text == "±":
            self.negate()

    def on_key_press(self, event):
        """Handle keyboard input"""
        key = event.char
        if key in "0123456789":
            self.input_number(key)
        elif key == ".":
            self.input_decimal()
        elif key in "+-*/":
            self.input_operator(key)
        elif key == "\r":  # Enter
            self.calculate()
        elif key == "\x08":  # Backspace
            self.backspace()
        elif key == "\x1b":  # Escape
            self.clear()

    def input_number(self, num):
        """Handle number input"""
        if self.should_clear:
            self.current_input = ""
            self.should_clear = False
        if len(self.current_input) < 15:
            self.current_input += num
            self.update_display()

    def input_decimal(self):
        """Handle decimal point"""
        if self.should_clear:
            self.current_input = "0"
            self.should_clear = False
        if "." not in self.current_input:
            self.current_input += "."
            self.update_display()

    def input_operator(self, op):
        """Handle operator input"""
        if self.current_input:
            if self.previous_input and self.operation and not self.should_clear:
                self.calculate()
            self.operation = op
            self.previous_input = self.current_input
            self.current_input = ""
            self.should_clear = False

    def calculate(self):
        """Perform calculation"""
        if not self.previous_input or not self.current_input or not self.operation:
            return

        try:
            a = float(self.previous_input)
            b = float(self.current_input)

            if self.operation == "+":
                result = self.calc.add(a, b)
            elif self.operation == "-":
                result = self.calc.subtract(a, b)
            elif self.operation == "*":
                result = self.calc.multiply(a, b)
            elif self.operation == "/":
                result = self.calc.divide(a, b)
            else:
                return

            # Format result
            if result == int(result):
                result = int(result)
            self.current_input = str(result)
            self.previous_input = ""
            self.operation = None
            self.should_clear = True
            self.update_display()

        except ValueError as e:
            self.display.delete(0, tk.END)
            self.display.insert(0, "Error")
            self.root.after(1500, self.clear)

    def clear(self):
        """Clear all inputs"""
        self.current_input = ""
        self.previous_input = ""
        self.operation = None
        self.should_clear = False
        self.update_display()

    def backspace(self):
        """Remove last character"""
        if self.current_input and not self.should_clear:
            self.current_input = self.current_input[:-1]
            self.update_display()

    def percentage(self):
        """Convert to percentage"""
        if self.current_input:
            try:
                value = float(self.current_input) / 100
                self.current_input = str(value)
                self.update_display()
            except ValueError:
                pass

    def negate(self):
        """Negate current number"""
        if self.current_input:
            try:
                value = float(self.current_input) * -1
                self.current_input = str(int(value)) if value == int(value) else str(value)
                self.update_display()
            except ValueError:
                pass

    def update_display(self):
        """Update the display entry"""
        self.display.delete(0, tk.END)
        if self.current_input:
            self.display.insert(0, self.current_input)
        elif self.previous_input:
            self.display.insert(0, self.previous_input)
        else:
            self.display.insert(0, "0")


def main():
    """Launch the calculator app"""
    root = tk.Tk()
    app = CalculatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()