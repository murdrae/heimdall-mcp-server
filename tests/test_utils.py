"""
Test utilities for ensuring deterministic behavior across all tests.
"""

import os
import random
from typing import Any

import numpy as np
import torch
import transformers


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

    # PyTorch CPU
    torch.manual_seed(seed)

    # PyTorch GPU (if available)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

        # CUDA deterministic operations
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    # PyTorch deterministic algorithms (for supported operations)
    torch.use_deterministic_algorithms(True, warn_only=True)

    # Set environment variable for Python hash randomization
    # Note: This only affects subprocesses, not the current process
    os.environ["PYTHONHASHSEED"] = str(seed)

    # Transformers library determinism
    transformers.set_seed(seed)

    # Set environment variables for additional determinism
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"


def reset_model_weights(model: torch.nn.Module, seed: int = 42) -> None:
    """
    Reset all weights in a PyTorch model deterministically.

    Args:
        model: The PyTorch model to reset
        seed: The seed to use for weight initialization
    """
    torch.manual_seed(seed)

    def init_weights(m: torch.nn.Module) -> None:
        if isinstance(m, torch.nn.Linear):
            torch.nn.init.xavier_uniform_(m.weight)
            if m.bias is not None:
                torch.nn.init.zeros_(m.bias)
        elif isinstance(m, torch.nn.Conv2d):
            torch.nn.init.kaiming_uniform_(m.weight)
            if m.bias is not None:
                torch.nn.init.zeros_(m.bias)
        elif isinstance(m, torch.nn.BatchNorm1d | torch.nn.BatchNorm2d):
            torch.nn.init.ones_(m.weight)
            torch.nn.init.zeros_(m.bias)

    model.apply(init_weights)


def create_deterministic_tensor(shape: tuple[int, ...], seed: int = 42) -> torch.Tensor:
    """
    Create a deterministic tensor with the given shape.

    Args:
        shape: The shape of the tensor to create
        seed: The seed to use for generation

    Returns:
        A deterministic tensor
    """
    torch.manual_seed(seed)
    return torch.randn(shape)


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


def assert_tensors_equal(
    tensor1: torch.Tensor, tensor2: torch.Tensor, rtol: float = 1e-5, atol: float = 1e-8
) -> None:
    """
    Assert that two tensors are equal within tolerance.

    Args:
        tensor1: First tensor
        tensor2: Second tensor
        rtol: Relative tolerance
        atol: Absolute tolerance
    """
    assert tensor1.shape == tensor2.shape, (
        f"Shape mismatch: {tensor1.shape} vs {tensor2.shape}"
    )
    assert torch.allclose(tensor1, tensor2, rtol=rtol, atol=atol), (
        "Tensors are not equal within tolerance"
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
