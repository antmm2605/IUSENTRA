import time
from dataclasses import dataclass, field


@dataclass
class Bucket:
    capacity: int
    refill_per_minute: int
    tokens: float = field(init=False)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def consume(self, amount: int = 1) -> bool:
        now = time.time()
        elapsed = now - self.updated_at
        self.updated_at = now

        refill = (elapsed / 60.0) * self.refill_per_minute
        self.tokens = min(self.capacity, self.tokens + refill)

        if self.tokens >= amount:
            self.tokens -= amount
            return True

        return False


class InMemoryRateLimiter:
    def __init__(self, capacity: int = 30, refill_per_minute: int = 10):
        self.capacity = capacity
        self.refill_per_minute = refill_per_minute
        self.buckets: dict[str, Bucket] = {}

    def check(self, key: str, amount: int = 1) -> None:
        bucket = self.buckets.get(key)

        if not bucket:
            bucket = Bucket(
                capacity=self.capacity,
                refill_per_minute=self.refill_per_minute,
            )
            self.buckets[key] = bucket

        if not bucket.consume(amount):
            raise PermissionError("Limite richieste Lex AI superato. Riprova tra poco.")
