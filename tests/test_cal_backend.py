"""Test cases for Calculator backend using pytest"""

import sys
import os

# Add parent directory to path to import backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from backend.cal_backend import Calculator


class TestCalculator:
    """Test suite for Calculator class"""

    @pytest.fixture
    def calc(self):
        """Create a Calculator instance for each test"""
        return Calculator()

    # --- Addition tests ---
    def test_add_positive_numbers(self, calc):
        assert calc.add(2, 3) == 5

    def test_add_negative_numbers(self, calc):
        assert calc.add(-2, -3) == -5

    def test_add_mixed_numbers(self, calc):
        assert calc.add(-2, 5) == 3

    def test_add_floats(self, calc):
        assert calc.add(2.5, 3.1) == 5.6

    def test_add_zero(self, calc):
        assert calc.add(5, 0) == 5
        assert calc.add(0, 0) == 0

    # --- Subtraction tests ---
    def test_subtract_positive_numbers(self, calc):
        assert calc.subtract(10, 4) == 6

    def test_subtract_negative_result(self, calc):
        assert calc.subtract(3, 8) == -5

    def test_subtract_floats(self, calc):
        assert calc.subtract(5.5, 2.2) == 3.3

    def test_subtract_zero(self, calc):
        assert calc.subtract(5, 0) == 5

    # --- Multiplication tests ---
    def test_multiply_positive_numbers(self, calc):
        assert calc.multiply(4, 5) == 20

    def test_multiply_by_zero(self, calc):
        assert calc.multiply(100, 0) == 0
        assert calc.multiply(0, 0) == 0

    def test_multiply_negative_numbers(self, calc):
        assert calc.multiply(-3, -4) == 12
        assert calc.multiply(-3, 4) == -12

    def test_multiply_floats(self, calc):
        assert calc.multiply(2.5, 4) == 10.0

    # --- Division tests ---
    def test_divide_positive_numbers(self, calc):
        assert calc.divide(20, 4) == 5.0

    def test_divide_floats(self, calc):
        assert calc.divide(7, 2) == 3.5

    def test_divide_negative_numbers(self, calc):
        assert calc.divide(-10, 2) == -5.0
        assert calc.divide(-10, -2) == 5.0

    def test_divide_by_zero_raises_error(self, calc):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.divide(10, 0)

    def test_divide_zero_by_number(self, calc):
        assert calc.divide(0, 5) == 0.0

    # --- Power tests ---
    def test_power_positive_exponent(self, calc):
        assert calc.power(2, 3) == 8
        assert calc.power(5, 2) == 25

    def test_power_zero_exponent(self, calc):
        assert calc.power(5, 0) == 1
        assert calc.power(0, 0) == 1  # Python defines 0**0 as 1

    def test_power_negative_exponent(self, calc):
        assert calc.power(2, -1) == 0.5
        assert calc.power(2, -2) == 0.25

    def test_power_float_exponent(self, calc):
        assert calc.power(4, 0.5) == 2.0  # Square root

    # --- Modulo tests ---
    def test_modulo_positive_numbers(self, calc):
        assert calc.modulo(10, 3) == 1
        assert calc.modulo(15, 5) == 0

    def test_modulo_negative_numbers(self, calc):
        assert calc.modulo(-10, 3) == 2  # Python modulo behavior
        assert calc.modulo(10, -3) == -2

    def test_modulo_by_zero_raises_error(self, calc):
        with pytest.raises(ValueError, match="Cannot modulo by zero"):
            calc.modulo(10, 0)

    def test_modulo_zero(self, calc):
        assert calc.modulo(0, 5) == 0


# --- Edge case tests ---
class TestCalculatorEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.fixture
    def calc(self):
        return Calculator()

    def test_very_large_numbers(self, calc):
        assert calc.add(1e10, 1e10) == 2e10
        assert calc.multiply(1e5, 1e5) == 1e10

    def test_very_small_numbers(self, calc):
        result = calc.add(1e-10, 1e-10)
        assert abs(result - 2e-10) < 1e-15

    def test_precision(self, calc):
        # Floating point precision
        result = calc.divide(1, 3)
        assert abs(result - 0.3333333333333333) < 1e-15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])