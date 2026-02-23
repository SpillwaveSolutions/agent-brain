"""Simple calculator module for testing code ingestion."""

from typing import Union


Number = Union[int, float]


def add(a: Number, b: Number) -> Number:
    """Add two numbers together."""
    return a + b


def subtract(a: Number, b: Number) -> Number:
    """Subtract b from a."""
    return a - b


def multiply(a: Number, b: Number) -> Number:
    """Multiply two numbers."""
    return a * b


def divide(a: Number, b: Number) -> float:
    """Divide a by b.

    Raises:
        ZeroDivisionError: If b is zero.
    """
    if b == 0:
        raise ZeroDivisionError("Cannot divide by zero")
    return a / b


class Calculator:
    """Stateful calculator with history tracking."""

    def __init__(self) -> None:
        self.history: list[str] = []
        self.result: Number = 0

    def compute(self, operation: str, a: Number, b: Number) -> Number:
        """Perform a calculation and record it in history."""
        ops = {
            "add": add,
            "subtract": subtract,
            "multiply": multiply,
            "divide": divide,
        }
        if operation not in ops:
            raise ValueError(f"Unknown operation: {operation}")
        self.result = ops[operation](a, b)
        self.history.append(f"{operation}({a}, {b}) = {self.result}")
        return self.result

    def get_history(self) -> list[str]:
        """Return the computation history."""
        return list(self.history)
