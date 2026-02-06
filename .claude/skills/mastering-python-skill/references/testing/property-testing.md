# Property-Based Testing with Hypothesis

## Contents

- [Quick Snippets](#quick-snippets)
- [Core Concepts](#core-concepts)
- [Production Examples](#production-examples)
  - [Example 1: Basic Property Testing](#example-1-basic-property-testing)
  - [Example 2: Custom Strategies](#example-2-custom-strategies)
  - [Example 3: Stateful Testing](#example-3-stateful-testing)
  - [Example 4: Testing Data Structures](#example-4-testing-data-structures)
- [Common Patterns](#common-patterns)
- [Pitfalls to Avoid](#pitfalls-to-avoid)
- [See Also](#see-also)

---

## Quick Snippets

| Task | Code |
|------|------|
| Basic property test | `@given(st.integers())` |
| Multiple args | `@given(st.text(), st.integers())` |
| List of integers | `st.lists(st.integers())` |
| Dict strategy | `st.dictionaries(st.text(), st.integers())` |
| Constrained int | `st.integers(min_value=0, max_value=100)` |
| Optional value | `st.none() \| st.integers()` |
| Fixed examples | `@example("edge_case")` |
| Composite strategy | `@st.composite` |
| Assume constraint | `assume(len(s) > 0)` |
| Set max examples | `@settings(max_examples=500)` |
| Reproduce failure | `@reproduce_failure(...)` |

---

## Core Concepts

Property-based testing generates random inputs to find edge cases that example-based tests miss. Instead of writing specific test cases, you define properties that should always hold:

**Key Properties to Test**:
- **Invariants**: Conditions that must always be true (sorted list stays sorted)
- **Round-trip**: Encode then decode returns original (serialize/deserialize)
- **Idempotence**: Applying operation twice equals once (deduplicate)
- **Commutativity**: Order doesn't matter (set operations)
- **Oracle**: Compare against known-correct implementation

**Hypothesis Features**:
- **Strategies**: Generators for different data types
- **Shrinking**: Automatically simplifies failing cases to minimal examples
- **Example database**: Remembers and replays past failures
- **Stateful testing**: Tests sequences of operations

---

## Production Examples

### Example 1: Basic Property Testing

**Use case**: Test functions with mathematical properties.

```python
#!/usr/bin/env python3
"""Basic property-based testing with Hypothesis."""

from hypothesis import given, assume, example, settings
from hypothesis import strategies as st


def reverse_list(lst: list) -> list:
    """Reverse a list."""
    return lst[::-1]


def sort_list(lst: list[int]) -> list[int]:
    """Sort a list of integers."""
    return sorted(lst)


def encode_string(s: str) -> str:
    """Simple encoding: reverse and uppercase."""
    return s[::-1].upper()


def decode_string(s: str) -> str:
    """Decode: lowercase and reverse."""
    return s[::-1].lower()


# Property: Reversing twice returns original
@given(st.lists(st.integers()))
def test_reverse_twice_is_identity(lst: list[int]) -> None:
    """Reversing a list twice should return the original."""
    assert reverse_list(reverse_list(lst)) == lst


# Property: Reversed list has same length
@given(st.lists(st.integers()))
def test_reverse_preserves_length(lst: list[int]) -> None:
    """Reversing should not change length."""
    assert len(reverse_list(lst)) == len(lst)


# Property: Sorted list is ordered
@given(st.lists(st.integers()))
def test_sorted_is_ordered(lst: list[int]) -> None:
    """Sorted list should have each element <= next element."""
    sorted_lst = sort_list(lst)
    for i in range(len(sorted_lst) - 1):
        assert sorted_lst[i] <= sorted_lst[i + 1]


# Property: Sorting preserves elements
@given(st.lists(st.integers()))
def test_sorted_preserves_elements(lst: list[int]) -> None:
    """Sorting should keep all original elements."""
    sorted_lst = sort_list(lst)
    assert sorted(lst) == sorted(sorted_lst)  # Same multiset


# Property: Round-trip (encode then decode)
@given(st.text(alphabet=st.characters(whitelist_categories=("L",))))
def test_encode_decode_roundtrip(s: str) -> None:
    """Encoding then decoding should return lowercase original."""
    # Note: Our encode uppercases, decode lowercases
    assert decode_string(encode_string(s)) == s.lower()


# Using assume() to filter inputs
@given(st.integers(), st.integers())
def test_division_property(a: int, b: int) -> None:
    """Test that (a // b) * b + (a % b) == a for non-zero b."""
    assume(b != 0)  # Skip when b is zero
    assert (a // b) * b + (a % b) == a


# Adding explicit edge cases with @example
@given(st.lists(st.integers()))
@example([])  # Ensure empty list is tested
@example([1])  # Single element
@example([1, 1, 1])  # All same elements
def test_reverse_with_examples(lst: list[int]) -> None:
    """Test with both random and specific examples."""
    assert reverse_list(reverse_list(lst)) == lst


# Configuring test settings
@settings(max_examples=200, deadline=None)
@given(st.lists(st.integers(min_value=-1000, max_value=1000), max_size=100))
def test_with_custom_settings(lst: list[int]) -> None:
    """Run more examples with no time deadline."""
    sorted_lst = sort_list(lst)
    assert len(sorted_lst) == len(lst)


# Testing text with specific constraints
@given(st.text(min_size=1, max_size=100))
def test_non_empty_text_properties(s: str) -> None:
    """Properties of non-empty strings."""
    assert len(s) >= 1
    assert s[0] == s[0]  # First char exists


# Testing with multiple strategies
@given(
    st.lists(st.integers(), min_size=1),
    st.integers(min_value=0),
)
def test_list_indexing(lst: list[int], idx: int) -> None:
    """Test list indexing with valid index."""
    assume(idx < len(lst))  # Ensure valid index
    assert lst[idx] == lst[idx]  # Element exists


if __name__ == "__main__":
    # Run a single test
    test_reverse_twice_is_identity()
    print("All property tests passed!")
```

**Key points**:
- Properties describe what should ALWAYS be true, not specific outputs
- `assume()` filters invalid inputs (use sparingly)
- `@example()` adds specific cases alongside random ones

---

### Example 2: Custom Strategies

**Use case**: Generate domain-specific test data.

```python
#!/usr/bin/env python3
"""Custom Hypothesis strategies for domain objects."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from hypothesis import given, assume
from hypothesis import strategies as st


@dataclass(frozen=True)
class Email:
    """Validated email address."""

    local: str
    domain: str

    def __str__(self) -> str:
        return f"{self.local}@{self.domain}"

    @classmethod
    def parse(cls, email_str: str) -> "Email":
        """Parse email string."""
        if "@" not in email_str:
            raise ValueError("Invalid email: missing @")
        local, domain = email_str.rsplit("@", 1)
        if not local or not domain:
            raise ValueError("Invalid email: empty parts")
        return cls(local=local, domain=domain)


@dataclass(frozen=True)
class User:
    """User model."""

    id: int
    name: str
    email: Email
    age: int
    created_at: datetime


@dataclass(frozen=True)
class Order:
    """Order model."""

    id: str
    user_id: int
    items: list[str]
    total: float
    status: str


# Strategy for valid email local parts
email_local_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789._-"),
    min_size=1,
    max_size=64,
).filter(lambda s: not s.startswith(".") and not s.endswith("."))

# Strategy for valid domain names
domain_strategy = st.from_regex(
    r"[a-z][a-z0-9-]{0,61}[a-z0-9]\.[a-z]{2,}",
    fullmatch=True,
)

# Combined email strategy
email_strategy = st.builds(
    Email,
    local=email_local_strategy,
    domain=domain_strategy,
)


# Composite strategy for complex objects
@st.composite
def user_strategy(draw) -> User:
    """Generate valid User objects."""
    user_id = draw(st.integers(min_value=1, max_value=1_000_000))
    name = draw(st.text(min_size=1, max_size=100).filter(str.strip))
    email = draw(email_strategy)
    age = draw(st.integers(min_value=0, max_value=150))

    # Created_at should be in the past
    now = datetime.now()
    days_ago = draw(st.integers(min_value=0, max_value=3650))
    created_at = now - timedelta(days=days_ago)

    return User(
        id=user_id,
        name=name,
        email=email,
        age=age,
        created_at=created_at,
    )


# Strategy using st.builds for simpler cases
order_strategy = st.builds(
    Order,
    id=st.uuids().map(str),
    user_id=st.integers(min_value=1),
    items=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10),
    total=st.floats(min_value=0.01, max_value=10000.0, allow_nan=False),
    status=st.sampled_from(["pending", "processing", "shipped", "delivered"]),
)


# Strategy for JSON-like data
json_primitives = st.none() | st.booleans() | st.integers() | st.floats(
    allow_nan=False, allow_infinity=False
) | st.text()


@st.composite
def json_strategy(draw, max_depth: int = 3) -> Any:
    """Generate JSON-compatible nested structures."""
    if max_depth <= 0:
        return draw(json_primitives)

    return draw(
        st.one_of(
            json_primitives,
            st.lists(st.deferred(lambda: json_strategy(max_depth=max_depth - 1))),
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.deferred(lambda: json_strategy(max_depth=max_depth - 1)),
            ),
        )
    )


# Tests using custom strategies
@given(email_strategy)
def test_email_roundtrip(email: Email) -> None:
    """Email can be converted to string and back."""
    email_str = str(email)
    parsed = Email.parse(email_str)
    assert parsed == email


@given(user_strategy())
def test_user_properties(user: User) -> None:
    """User objects have valid properties."""
    assert user.id > 0
    assert len(user.name) > 0
    assert user.age >= 0
    assert user.created_at <= datetime.now()


@given(order_strategy)
def test_order_has_items(order: Order) -> None:
    """Orders always have at least one item."""
    assert len(order.items) >= 1
    assert order.total > 0


@given(st.lists(user_strategy(), min_size=2, max_size=10))
def test_user_ids_scenario(users: list[User]) -> None:
    """Test with lists of users."""
    ids = [u.id for u in users]
    # IDs might not be unique (that's ok, strategy doesn't enforce it)
    assert len(ids) == len(users)


@given(json_strategy())
def test_json_is_serializable(data: Any) -> None:
    """Generated JSON-like data can be serialized."""
    import json

    # Should not raise
    serialized = json.dumps(data)
    deserialized = json.loads(serialized)
    # Note: Some precision loss for floats is expected
    assert type(deserialized) == type(data) or isinstance(data, float)


# Strategy with recursive structure
@st.composite
def tree_strategy(draw, max_depth: int = 4) -> dict:
    """Generate tree-like nested dictionaries."""
    name = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))))
    value = draw(st.integers())

    if max_depth <= 1:
        return {"name": name, "value": value, "children": []}

    num_children = draw(st.integers(min_value=0, max_value=3))
    children = [
        draw(tree_strategy(max_depth=max_depth - 1)) for _ in range(num_children)
    ]

    return {"name": name, "value": value, "children": children}


@given(tree_strategy())
def test_tree_structure(tree: dict) -> None:
    """Tree has required structure."""
    assert "name" in tree
    assert "value" in tree
    assert "children" in tree
    assert isinstance(tree["children"], list)


if __name__ == "__main__":
    test_email_roundtrip()
    test_user_properties()
    print("Custom strategy tests passed!")
```

**Key points**:
- `@st.composite` allows drawing from multiple strategies with logic
- `st.builds` constructs objects from strategies for each field
- Use `st.deferred` for recursive strategies
- `filter()` removes invalid values (but can slow generation)

---

### Example 3: Stateful Testing

**Use case**: Test sequences of operations maintain invariants.

```python
#!/usr/bin/env python3
"""Stateful testing with Hypothesis for sequences of operations."""

from hypothesis import settings
from hypothesis.stateful import (
    RuleBasedStateMachine,
    Bundle,
    rule,
    invariant,
    precondition,
    initialize,
    consumes,
)
from hypothesis import strategies as st
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BankAccount:
    """Simple bank account for testing."""

    account_id: str
    balance: float = 0.0
    is_frozen: bool = False

    def deposit(self, amount: float) -> None:
        if self.is_frozen:
            raise ValueError("Account is frozen")
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self.balance += amount

    def withdraw(self, amount: float) -> None:
        if self.is_frozen:
            raise ValueError("Account is frozen")
        if amount <= 0:
            raise ValueError("Withdrawal must be positive")
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount

    def freeze(self) -> None:
        self.is_frozen = True

    def unfreeze(self) -> None:
        self.is_frozen = False


@dataclass
class Bank:
    """Bank managing multiple accounts."""

    accounts: dict[str, BankAccount] = field(default_factory=dict)

    def create_account(self, account_id: str) -> BankAccount:
        if account_id in self.accounts:
            raise ValueError("Account already exists")
        account = BankAccount(account_id=account_id)
        self.accounts[account_id] = account
        return account

    def close_account(self, account_id: str) -> None:
        if account_id not in self.accounts:
            raise ValueError("Account not found")
        if self.accounts[account_id].balance != 0:
            raise ValueError("Cannot close account with non-zero balance")
        del self.accounts[account_id]

    def transfer(self, from_id: str, to_id: str, amount: float) -> None:
        if from_id not in self.accounts or to_id not in self.accounts:
            raise ValueError("Account not found")
        self.accounts[from_id].withdraw(amount)
        self.accounts[to_id].deposit(amount)

    def total_balance(self) -> float:
        return sum(acc.balance for acc in self.accounts.values())


class BankStateMachine(RuleBasedStateMachine):
    """Stateful test for Bank operations."""

    def __init__(self) -> None:
        super().__init__()
        self.bank = Bank()
        self.model_balances: dict[str, float] = {}  # Track expected balances
        self.model_frozen: dict[str, bool] = {}

    # Bundle stores created account IDs for use in later rules
    accounts = Bundle("accounts")

    @initialize()
    def init_bank(self) -> None:
        """Reset state at start of each test run."""
        self.bank = Bank()
        self.model_balances = {}
        self.model_frozen = {}

    @rule(target=accounts, account_id=st.text(min_size=1, max_size=10))
    def create_account(self, account_id: str) -> str:
        """Create a new account."""
        if account_id in self.model_balances:
            # Account exists, should raise
            try:
                self.bank.create_account(account_id)
                assert False, "Should have raised"
            except ValueError:
                pass
            return account_id  # Return existing for bundle

        self.bank.create_account(account_id)
        self.model_balances[account_id] = 0.0
        self.model_frozen[account_id] = False
        return account_id

    @rule(account=accounts, amount=st.floats(min_value=0.01, max_value=1000.0))
    def deposit(self, account: str, amount: float) -> None:
        """Deposit money into account."""
        if account not in self.model_balances:
            return

        if self.model_frozen[account]:
            try:
                self.bank.accounts[account].deposit(amount)
                assert False, "Should have raised for frozen account"
            except ValueError:
                pass
        else:
            self.bank.accounts[account].deposit(amount)
            self.model_balances[account] += amount

    @rule(account=accounts, amount=st.floats(min_value=0.01, max_value=1000.0))
    def withdraw(self, account: str, amount: float) -> None:
        """Withdraw money from account."""
        if account not in self.model_balances:
            return

        if self.model_frozen[account]:
            try:
                self.bank.accounts[account].withdraw(amount)
                assert False, "Should have raised for frozen account"
            except ValueError:
                pass
        elif amount > self.model_balances[account]:
            try:
                self.bank.accounts[account].withdraw(amount)
                assert False, "Should have raised for insufficient funds"
            except ValueError:
                pass
        else:
            self.bank.accounts[account].withdraw(amount)
            self.model_balances[account] -= amount

    @rule(from_acc=accounts, to_acc=accounts, amount=st.floats(min_value=0.01, max_value=100.0))
    @precondition(lambda self: len(self.model_balances) >= 2)
    def transfer(self, from_acc: str, to_acc: str, amount: float) -> None:
        """Transfer between accounts."""
        if from_acc not in self.model_balances or to_acc not in self.model_balances:
            return
        if from_acc == to_acc:
            return
        if self.model_frozen[from_acc] or self.model_frozen[to_acc]:
            return
        if amount > self.model_balances[from_acc]:
            return

        self.bank.transfer(from_acc, to_acc, amount)
        self.model_balances[from_acc] -= amount
        self.model_balances[to_acc] += amount

    @rule(account=accounts)
    def freeze_account(self, account: str) -> None:
        """Freeze an account."""
        if account not in self.model_balances:
            return
        self.bank.accounts[account].freeze()
        self.model_frozen[account] = True

    @rule(account=accounts)
    def unfreeze_account(self, account: str) -> None:
        """Unfreeze an account."""
        if account not in self.model_balances:
            return
        self.bank.accounts[account].unfreeze()
        self.model_frozen[account] = False

    @rule(account=consumes(accounts))
    @precondition(lambda self: len(self.model_balances) > 0)
    def close_account(self, account: str) -> None:
        """Close an account (consumes it from bundle)."""
        if account not in self.model_balances:
            return

        if self.model_balances[account] != 0:
            try:
                self.bank.close_account(account)
                assert False, "Should have raised for non-zero balance"
            except ValueError:
                pass
        else:
            self.bank.close_account(account)
            del self.model_balances[account]
            del self.model_frozen[account]

    @invariant()
    def balances_match_model(self) -> None:
        """Invariant: Real balances match our model."""
        for account_id, expected in self.model_balances.items():
            actual = self.bank.accounts[account_id].balance
            assert abs(actual - expected) < 0.001, f"Balance mismatch for {account_id}"

    @invariant()
    def balances_non_negative(self) -> None:
        """Invariant: All balances are non-negative."""
        for account in self.bank.accounts.values():
            assert account.balance >= 0

    @invariant()
    def total_balance_conserved(self) -> None:
        """Invariant: Total money in system matches deposits minus withdrawals."""
        expected_total = sum(self.model_balances.values())
        actual_total = self.bank.total_balance()
        assert abs(actual_total - expected_total) < 0.001


# Create test class from state machine
TestBankOperations = BankStateMachine.TestCase


# Simpler stateful test for a stack
class StackMachine(RuleBasedStateMachine):
    """Test a stack implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[int] = []
        self.model: list[int] = []

    @rule(value=st.integers())
    def push(self, value: int) -> None:
        self.stack.append(value)
        self.model.append(value)

    @rule()
    @precondition(lambda self: len(self.model) > 0)
    def pop(self) -> None:
        actual = self.stack.pop()
        expected = self.model.pop()
        assert actual == expected

    @invariant()
    def stack_matches_model(self) -> None:
        assert self.stack == self.model


TestStack = StackMachine.TestCase


if __name__ == "__main__":
    # Run stateful tests
    TestBankOperations().runTest()
    TestStack().runTest()
    print("Stateful tests passed!")
```

**Key points**:
- `Bundle` stores values created by rules for use in later rules
- `@invariant` checks properties after every rule execution
- `@precondition` controls when rules can run
- `consumes()` removes items from bundle when used

---

### Example 4: Testing Data Structures

**Use case**: Verify data structure implementations.

```python
#!/usr/bin/env python3
"""Property testing for data structures."""

from hypothesis import given, assume
from hypothesis import strategies as st
from dataclasses import dataclass
from typing import Generic, TypeVar, Iterator
from collections.abc import MutableMapping

K = TypeVar("K")
V = TypeVar("V")


class SimpleCache(MutableMapping[K, V]):
    """LRU cache implementation to test."""

    def __init__(self, max_size: int = 100) -> None:
        self.max_size = max_size
        self._data: dict[K, V] = {}
        self._access_order: list[K] = []

    def __getitem__(self, key: K) -> V:
        if key not in self._data:
            raise KeyError(key)
        # Move to end (most recently used)
        self._access_order.remove(key)
        self._access_order.append(key)
        return self._data[key]

    def __setitem__(self, key: K, value: V) -> None:
        if key in self._data:
            self._access_order.remove(key)
        elif len(self._data) >= self.max_size:
            # Evict least recently used
            lru_key = self._access_order.pop(0)
            del self._data[lru_key]

        self._data[key] = value
        self._access_order.append(key)

    def __delitem__(self, key: K) -> None:
        del self._data[key]
        self._access_order.remove(key)

    def __iter__(self) -> Iterator[K]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


# Property: Cache behaves like dict for basic operations
@given(st.dictionaries(st.text(min_size=1), st.integers()))
def test_cache_stores_values(items: dict[str, int]) -> None:
    """Cache should store and retrieve values like a dict."""
    cache: SimpleCache[str, int] = SimpleCache(max_size=1000)

    for key, value in items.items():
        cache[key] = value

    for key, expected in items.items():
        assert cache[key] == expected


# Property: Size never exceeds max_size
@given(
    st.lists(st.tuples(st.text(min_size=1, max_size=10), st.integers()), min_size=0, max_size=200),
    st.integers(min_value=1, max_value=50),
)
def test_cache_respects_max_size(items: list[tuple[str, int]], max_size: int) -> None:
    """Cache should never exceed max_size."""
    cache: SimpleCache[str, int] = SimpleCache(max_size=max_size)

    for key, value in items:
        cache[key] = value
        assert len(cache) <= max_size


# Property: Recent items are kept
@given(st.lists(st.text(min_size=1, max_size=5), min_size=10, max_size=20, unique=True))
def test_lru_keeps_recent(keys: list[str]) -> None:
    """Most recent items should be kept."""
    max_size = 5
    cache: SimpleCache[str, int] = SimpleCache(max_size=max_size)

    for i, key in enumerate(keys):
        cache[key] = i

    # Last max_size keys should still be in cache
    recent_keys = keys[-max_size:]
    for key in recent_keys:
        assert key in cache


# Property: Delete removes item
@given(
    st.dictionaries(st.text(min_size=1), st.integers(), min_size=1),
)
def test_delete_removes_item(items: dict[str, int]) -> None:
    """Deleted items should not be accessible."""
    cache: SimpleCache[str, int] = SimpleCache()

    for key, value in items.items():
        cache[key] = value

    key_to_delete = list(items.keys())[0]
    del cache[key_to_delete]

    assert key_to_delete not in cache
    assert len(cache) == len(items) - 1


# Testing a sorted list implementation
class SortedList:
    """Maintains elements in sorted order."""

    def __init__(self) -> None:
        self._items: list[int] = []

    def insert(self, value: int) -> None:
        """Insert value maintaining sorted order."""
        # Binary search for insert position
        low, high = 0, len(self._items)
        while low < high:
            mid = (low + high) // 2
            if self._items[mid] < value:
                low = mid + 1
            else:
                high = mid
        self._items.insert(low, value)

    def remove(self, value: int) -> bool:
        """Remove first occurrence of value."""
        try:
            self._items.remove(value)
            return True
        except ValueError:
            return False

    def __contains__(self, value: int) -> bool:
        # Binary search
        low, high = 0, len(self._items)
        while low < high:
            mid = (low + high) // 2
            if self._items[mid] == value:
                return True
            elif self._items[mid] < value:
                low = mid + 1
            else:
                high = mid
        return False

    def __iter__(self) -> Iterator[int]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def to_list(self) -> list[int]:
        return list(self._items)


# Property: Always sorted
@given(st.lists(st.integers()))
def test_sorted_list_always_sorted(values: list[int]) -> None:
    """SortedList should always maintain sorted order."""
    sl = SortedList()
    for v in values:
        sl.insert(v)

    items = sl.to_list()
    assert items == sorted(items)


# Property: Contains all inserted items
@given(st.lists(st.integers()))
def test_sorted_list_contains_inserted(values: list[int]) -> None:
    """All inserted values should be findable."""
    sl = SortedList()
    for v in values:
        sl.insert(v)

    for v in values:
        assert v in sl


# Property: Remove actually removes
@given(st.lists(st.integers(), min_size=1))
def test_sorted_list_remove(values: list[int]) -> None:
    """Removed values should not be present."""
    sl = SortedList()
    for v in values:
        sl.insert(v)

    to_remove = values[0]
    initial_count = sum(1 for v in values if v == to_remove)

    sl.remove(to_remove)

    # Count remaining
    remaining = sum(1 for v in sl if v == to_remove)
    assert remaining == initial_count - 1


# Property: Comparing implementations (oracle testing)
@given(st.lists(st.integers()))
def test_sorted_list_matches_builtin_sort(values: list[int]) -> None:
    """SortedList should produce same result as sorted()."""
    sl = SortedList()
    for v in values:
        sl.insert(v)

    assert sl.to_list() == sorted(values)


# Testing set operations
@given(st.frozensets(st.integers()), st.frozensets(st.integers()))
def test_set_union_properties(a: frozenset[int], b: frozenset[int]) -> None:
    """Union should have commutativity and other properties."""
    # Commutativity
    assert a | b == b | a

    # Union contains both sets
    assert a.issubset(a | b)
    assert b.issubset(a | b)

    # Size property
    assert len(a | b) <= len(a) + len(b)


@given(st.frozensets(st.integers()), st.frozensets(st.integers()))
def test_set_intersection_properties(a: frozenset[int], b: frozenset[int]) -> None:
    """Intersection should satisfy set theory properties."""
    # Commutativity
    assert a & b == b & a

    # Intersection is subset of both
    assert (a & b).issubset(a)
    assert (a & b).issubset(b)

    # Size property
    assert len(a & b) <= min(len(a), len(b))


if __name__ == "__main__":
    test_cache_stores_values()
    test_sorted_list_always_sorted()
    test_set_union_properties()
    print("Data structure property tests passed!")
```

**Key points**:
- Oracle testing compares your implementation against a reference (like Python's `sorted()`)
- Test invariants that should always hold (sorted order, size limits)
- Use set theory properties for testing set-like structures

---

## Common Patterns

### Pattern: Testing Serialization Round-Trip
```python
@given(st.builds(MyDataClass, field1=st.text(), field2=st.integers()))
def test_json_roundtrip(obj):
    """Serialize then deserialize should return equal object."""
    json_str = obj.to_json()
    restored = MyDataClass.from_json(json_str)
    assert restored == obj
```

### Pattern: Testing Parser with Printer
```python
@given(valid_ast_strategy())
def test_parser_printer_roundtrip(ast):
    """Pretty-print then parse should return same AST."""
    printed = printer.print(ast)
    parsed = parser.parse(printed)
    assert parsed == ast
```

### Pattern: Comparing Fast and Slow Implementations
```python
@given(st.lists(st.integers()))
def test_fast_matches_slow(data):
    """Optimized version should match naive implementation."""
    slow_result = naive_algorithm(data)
    fast_result = optimized_algorithm(data)
    assert fast_result == slow_result
```

---

## Pitfalls to Avoid

**Don't do this:**
```python
# Over-filtering makes tests useless
@given(st.integers())
def test_with_too_many_assumes(x):
    assume(x > 0)
    assume(x < 100)
    assume(x % 2 == 0)
    assume(x % 5 == 0)
    # Very few values pass - test doesn't explore well
```

**Do this instead:**
```python
# Use targeted strategies
@given(st.integers(min_value=1, max_value=99).filter(lambda x: x % 10 == 0))
def test_with_strategy(x):
    # Values: 10, 20, 30, 40, 50, 60, 70, 80, 90
    assert 0 < x < 100
```

---

**Don't do this:**
```python
# Testing implementation details
@given(st.lists(st.integers()))
def test_internal_structure(lst):
    sorted_lst = my_sort(lst)
    # Don't test internal state!
    assert sorted_lst._comparison_count < len(lst) ** 2
```

**Do this instead:**
```python
# Test observable behavior
@given(st.lists(st.integers()))
def test_sorting_correctness(lst):
    sorted_lst = my_sort(lst)
    # Test what matters: order and elements
    assert sorted_lst == sorted(lst)
```

---

## See Also

- [pytest-essentials.md](pytest-essentials.md) - Core pytest patterns
- [mocking-strategies.md](mocking-strategies.md) - Test doubles and isolation
- [error-handling.md](../patterns/error-handling.md) - Exception handling
