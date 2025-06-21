"""
Test utilities for ensuring deterministic behavior across all tests.
"""

import os
import random
from typing import Any

import numpy as np


def setup_deterministic_testing(seed: int = 42) -> None:
    """
    Configure all random sources for completely deterministic test behavior.

    This function sets seeds for all known sources of randomness in the cognitive
    memory system to ensure tests produce identical results across runs.

    Args:
        seed: The random seed to use for all generators
    """
    # Python built-in random
    random.seed(seed)

    # NumPy
    np.random.seed(seed)

    # Set environment variable for Python hash randomization
    # Note: This only affects subprocesses, not the current process
    os.environ["PYTHONHASHSEED"] = str(seed)

    # Transformers library determinism (replaced with NumPy seed)
    np.random.seed(seed)


def reset_model_weights(model: Any, seed: int = 42) -> None:
    """
    Reset model weights deterministically (NumPy-based).

    Args:
        model: The model to reset
        seed: The seed to use for weight initialization
    """
    np.random.seed(seed)
    # Model weight initialization now handled by NumPy-based implementations
    # This function is maintained for compatibility but actual weight
    # initialization should be done in the model implementation


def create_deterministic_array(shape: tuple[int, ...], seed: int = 42) -> np.ndarray:
    """
    Create a deterministic array with the given shape.

    Args:
        shape: The shape of the array to create
        seed: The seed to use for generation

    Returns:
        A deterministic NumPy array
    """
    np.random.seed(seed)
    return np.random.randn(*shape)


def create_deterministic_uuid(seed: int = 42) -> str:
    """
    Create a deterministic UUID-like string for testing.

    Args:
        seed: The seed to use for generation

    Returns:
        A deterministic UUID-like string
    """
    random.seed(seed)
    return f"test-{seed:08d}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"


class DeterministicTestMixin:
    """
    Mixin class that automatically sets up deterministic behavior for test classes.
    """

    def setup_method(self) -> None:
        """Set up deterministic testing before each test method."""
        setup_deterministic_testing()

    def teardown_method(self) -> None:
        """Clean up after each test method."""
        # Reset any global state if needed
        pass


def assert_arrays_equal(
    array1: np.ndarray, array2: np.ndarray, rtol: float = 1e-5, atol: float = 1e-8
) -> None:
    """
    Assert that two arrays are equal within tolerance.

    Args:
        array1: First array
        array2: Second array
        rtol: Relative tolerance
        atol: Absolute tolerance
    """
    assert array1.shape == array2.shape, (
        f"Shape mismatch: {array1.shape} vs {array2.shape}"
    )
    assert np.allclose(array1, array2, rtol=rtol, atol=atol), (
        "Arrays are not equal within tolerance"
    )


def patch_time_dependent_functions() -> Any:
    """
    Return a context manager that patches time-dependent functions for deterministic testing.

    Returns:
        A context manager that can be used in tests
    """
    from contextlib import contextmanager
    from datetime import datetime
    from unittest.mock import patch

    @contextmanager
    def patched_datetime():
        fixed_datetime = datetime(2024, 1, 1, 12, 0, 0)

        with patch("cognitive_memory.core.memory.datetime") as mock_datetime_class:
            mock_datetime_class.now.return_value = fixed_datetime
            mock_datetime_class.side_effect = lambda *args, **kw: datetime(*args, **kw)
            yield mock_datetime_class

    return patched_datetime()
