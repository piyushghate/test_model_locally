"""Basic Calculator Implementation"""


class Calculator:
    """A simple calculator class supporting basic arithmetic operations."""

    @staticmethod
    def add(a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    @staticmethod
    def subtract(a: float, b: float) -> float:
        """Subtract b from a."""
        return a - b

    @staticmethod
    def multiply(a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    @staticmethod
    def divide(a: float, b: float) -> float:
        """Divide a by b. Raises ValueError if dividing by zero."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    @staticmethod
    def power(a: float, b: float) -> float:
        """Raise a to the power of b."""
        return a ** b

    @staticmethod
    def modulo(a: float, b: float) -> float:
        """Return the remainder of a divided by b."""
        if b == 0:
            raise ValueError("Cannot modulo by zero")
        return a % b


def main():
    """Interactive calculator demo."""
    calc = Calculator()

    print("=== Basic Calculator ===")
    print("Operations: add, subtract, multiply, divide, power, modulo")
    print("Type 'quit' to exit\n")

    while True:
        try:
            operation = input("Enter operation: ").strip().lower()

            if operation == 'quit':
                print("Goodbye!")
                break

            if operation not in ['add', 'subtract', 'multiply', 'divide', 'power', 'modulo']:
                print("Invalid operation. Try again.\n")
                continue

            a = float(input("Enter first number: "))
            b = float(input("Enter second number: "))

            result = None
            if operation == 'add':
                result = calc.add(a, b)
            elif operation == 'subtract':
                result = calc.subtract(a, b)
            elif operation == 'multiply':
                result = calc.multiply(a, b)
            elif operation == 'divide':
                result = calc.divide(a, b)
            elif operation == 'power':
                result = calc.power(a, b)
            elif operation == 'modulo':
                result = calc.modulo(a, b)

            print(f"Result: {result}\n")

        except ValueError as e:
            print(f"Error: {e}\n")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Unexpected error: {e}\n")


if __name__ == "__main__":
    main()