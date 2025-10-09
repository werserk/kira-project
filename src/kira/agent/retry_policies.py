"""Retry policies and error handling for agent execution.

Phase 3, Item 12: Budgets, retries, and error handling.
Implements exponential backoff and circuit breaker patterns.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

logger = logging.getLogger(__name__)

__all__ = [
    "RetryPolicy",
    "CircuitBreaker",
    "RetryableError",
    "with_retry",
    "create_retry_policy",
]


class RetryableError(Exception):
    """Raised for transient errors that should be retried."""

    pass


@dataclass
class RetryPolicy:
    """Retry policy with exponential backoff.

    Attributes
    ----------
    max_retries
        Maximum number of retry attempts
    base_delay
        Base delay in seconds for exponential backoff
    max_delay
        Maximum delay between retries
    exponential_base
        Base for exponential backoff calculation
    jitter
        Add random jitter to delays (0.0-1.0)
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with exponential backoff.

        Parameters
        ----------
        attempt
            Retry attempt number (0-indexed)

        Returns
        -------
        float
            Delay in seconds
        """
        import random

        # Exponential backoff: base_delay * exponential_base ^ attempt
        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)

        # Add jitter to prevent thundering herd
        if self.jitter > 0:
            jitter_amount = delay * self.jitter * random.random()
            delay += jitter_amount

        return delay

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if error should be retried.

        Parameters
        ----------
        attempt
            Current attempt number (0-indexed)
        error
            Exception that occurred

        Returns
        -------
        bool
            True if should retry
        """
        if attempt >= self.max_retries:
            return False

        # Retry transient errors
        if isinstance(error, RetryableError):
            return True

        # Retry specific error types (timeout, rate limit, etc.)
        error_name = type(error).__name__
        retryable_errors = ["TimeoutError", "LLMTimeoutError", "LLMRateLimitError", "ConnectionError"]

        return error_name in retryable_errors


@dataclass
class CircuitBreaker:
    """Circuit breaker pattern for repeated failures.

    States:
    - CLOSED: Normal operation, allow requests
    - OPEN: Too many failures, block requests
    - HALF_OPEN: Testing if service recovered
    """

    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    success_threshold: int = 2  # successes needed to close circuit

    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _state: str = field(default="CLOSED", init=False)  # CLOSED, OPEN, HALF_OPEN
    _opened_at: datetime | None = field(default=None, init=False)

    def record_success(self) -> None:
        """Record a successful operation."""
        if self._state == "HALF_OPEN":
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info("Circuit breaker closing after successful recovery")
                self._close()
        elif self._state == "CLOSED":
            # Reset failure count on success
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation."""
        if self._state == "CLOSED":
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                logger.warning(f"Circuit breaker opening after {self._failure_count} failures")
                self._open()
        elif self._state == "HALF_OPEN":
            logger.warning("Circuit breaker re-opening after test failure")
            self._open()

    def is_allowed(self) -> bool:
        """Check if requests are allowed.

        Returns
        -------
        bool
            True if request should be allowed
        """
        if self._state == "CLOSED":
            return True

        if self._state == "OPEN":
            # Check if recovery timeout has passed
            if self._opened_at:
                elapsed = (datetime.now(UTC) - self._opened_at).total_seconds()
                if elapsed >= self.recovery_timeout:
                    logger.info("Circuit breaker entering half-open state for testing")
                    self._state = "HALF_OPEN"
                    self._success_count = 0
                    return True
            return False

        # HALF_OPEN: allow limited requests for testing
        return True

    def _open(self) -> None:
        """Open the circuit breaker."""
        self._state = "OPEN"
        self._opened_at = datetime.now(UTC)
        self._failure_count = 0

    def _close(self) -> None:
        """Close the circuit breaker."""
        self._state = "CLOSED"
        self._opened_at = None
        self._failure_count = 0
        self._success_count = 0

    def get_state(self) -> str:
        """Get current circuit breaker state.

        Returns
        -------
        str
            Current state: CLOSED, OPEN, or HALF_OPEN
        """
        return self._state

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._close()
        logger.info("Circuit breaker reset")


def with_retry(
    func: Callable[..., Any],
    retry_policy: RetryPolicy,
    circuit_breaker: CircuitBreaker | None = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute function with retry policy.

    Parameters
    ----------
    func
        Function to execute
    retry_policy
        Retry policy to apply
    circuit_breaker
        Optional circuit breaker
    *args
        Positional arguments for func
    **kwargs
        Keyword arguments for func

    Returns
    -------
    Any
        Result from func

    Raises
    ------
    Exception
        If all retries exhausted or circuit breaker open
    """
    # Check circuit breaker
    if circuit_breaker and not circuit_breaker.is_allowed():
        raise RetryableError(f"Circuit breaker is {circuit_breaker.get_state()}, blocking request")

    last_error = None
    attempt = 0

    while attempt <= retry_policy.max_retries:
        try:
            result = func(*args, **kwargs)

            # Record success
            if circuit_breaker:
                circuit_breaker.record_success()

            return result

        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1} failed: {e}")

            # Record failure
            if circuit_breaker:
                circuit_breaker.record_failure()

            # Check if should retry
            if not retry_policy.should_retry(attempt, e):
                logger.error(f"Not retrying error: {e}")
                raise

            # Calculate delay
            if attempt < retry_policy.max_retries:
                delay = retry_policy.get_delay(attempt)
                logger.info(f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{retry_policy.max_retries})")
                time.sleep(delay)

            attempt += 1

    # All retries exhausted
    logger.error(f"All {retry_policy.max_retries} retries exhausted")
    if last_error:
        raise last_error
    raise RetryableError("All retries exhausted")


def create_retry_policy(
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    enable_circuit_breaker: bool = True,
) -> tuple[RetryPolicy, CircuitBreaker | None]:
    """Factory function to create retry policy and circuit breaker.

    Parameters
    ----------
    max_retries
        Maximum number of retries
    base_delay
        Base delay for exponential backoff
    max_delay
        Maximum delay between retries
    enable_circuit_breaker
        Enable circuit breaker pattern

    Returns
    -------
    tuple
        (RetryPolicy, CircuitBreaker or None)
    """
    retry_policy = RetryPolicy(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
    )

    circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None

    logger.info(
        f"Created retry policy: max_retries={max_retries}, "
        f"base_delay={base_delay}, circuit_breaker={enable_circuit_breaker}"
    )

    return retry_policy, circuit_breaker

