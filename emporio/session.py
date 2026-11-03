"""UI-independent verification state with a small session-local attempt limit."""

from dataclasses import dataclass

from emporio.store import Store


@dataclass
class Verification:
    customer_id: int | None = None
    failures: int = 0

    def verify(self, store: Store, email: str, phone: str) -> bool:
        self.customer_id = None
        if self.failures >= 5:
            return False
        self.customer_id = store.verify_customer(email, phone)
        if self.customer_id is None:
            self.failures += 1
            return False
        self.failures = 0
        return True
