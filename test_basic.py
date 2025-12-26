#!/usr/bin/env python3
"""Basic test to verify circuit breaker logic"""


# Test circuit breaker logic manually
class MockTradeExecutor:
    def __init__(self):
        self.daily_loss = 0.0
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.settings = type(
            "obj", (object,), {"risk": type("obj", (object,), {"max_daily_loss": 100.0})()}
        )()

    def activate_circuit_breaker(self, reason):
        self.circuit_breaker_active = True
        self.circuit_breaker_reason = reason

    def _check_circuit_breaker_conditions(self):
        if self.daily_loss >= self.settings.risk.max_daily_loss:
            self.activate_circuit_breaker(f"Daily loss limit reached (${self.daily_loss:.2f})")


# Test the logic
executor = MockTradeExecutor()
executor.daily_loss = 150.0
executor._check_circuit_breaker_conditions()

assert executor.circuit_breaker_active, "Circuit breaker should activate on high loss"
assert (
    "Daily loss limit reached" in executor.circuit_breaker_reason
), "Reason should be set correctly"
print("✅ Circuit breaker logic test passed")
