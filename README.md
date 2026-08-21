# Calculator Project

A simple calculator application with a Python backend and Tkinter GUI frontend.

## Project Structure

```
.
├── backend/
│   └── cal_backend.py      # Core calculator logic
├── frontend/
│   └── cal_frontend.py     # Tkinter GUI application
├── tests/
│   └── test_cal_backend.py # Unit tests (29 tests, 100% pass)
└── README.md               # This file
```

## Backend (`backend/cal_backend.py`)

The `Calculator` class provides static methods for basic arithmetic operations:

| Method | Description |
|--------|-------------|
| `add(a, b)` | Add two numbers |
| `subtract(a, b)` | Subtract b from a |
| `multiply(a, b)` | Multiply two numbers |
| `divide(a, b)` | Divide a by b (raises `ValueError` on division by zero) |
| `power(a, b)` | Raise a to the power of b |
| `modulo(a, b)` | Return remainder of a divided by b (raises `ValueError` on modulo by zero) |

Also includes an interactive CLI demo via `main()`.

### Usage
```python
from backend.cal_backend import Calculator

calc = Calculator()
calc.add(5, 3)        # 8
calc.divide(10, 2)    # 5.0
calc.power(2, 3)      # 8
```

## Frontend (`frontend/cal_frontend.py`)

A modern dark-themed GUI calculator built with Tkinter featuring:

- **Operations**: Add, Subtract, Multiply, Divide
- **Extra functions**: Percentage (%), Negate (±), Backspace (⌫), Clear (C)
- **Keyboard support**: Full keyboard input (numbers, operators, Enter, Backspace, Escape)
- **Display formatting**: Auto-converts whole number floats to integers (e.g., `5.0` → `5`)
- **Error handling**: Shows "Error" for invalid operations (division by zero, etc.)

### Launch the GUI
```bash
python -m frontend.cal_frontend
# or
python frontend/cal_frontend.py
```

## Running Tests

```bash
# Run all tests with coverage
python -m pytest tests/test_cal_backend.py -v --cov=backend --cov-report=term-missing

# Run tests only
python -m pytest tests/test_cal_backend.py -v
```

**Current coverage**: 40% (tests cover all Calculator methods; CLI `main()` is not tested)

## Requirements

- Python 3.8+
- Tkinter (usually included with Python)
- pytest, pytest-cov (for testing)

Install test dependencies:
```bash
pip install pytest pytest-cov
```

## License

MIT