"""
Sigma condition grammar parser and evaluator (ENH-015).

Background
----------
The engine previously "evaluated" conditions like this::

    if condition == "selection":
        return selection_match
    elif "and not filter" in condition:
        return selection_match          # <-- filter IGNORED
    else:
        return selection_match          # <-- everything else IGNORED

So `selection and not filter` fired on traffic the rule was written to exclude
(false positives that erode analyst trust), and `selection1 or selection2`,
`1 of them`, `all of them` and any negation were silently mis-evaluated (false
negatives that miss real attacks).

This module implements the actual Sigma condition grammar:

    condition   := or_expr
    or_expr     := and_expr ( "or" and_expr )*
    and_expr    := not_expr ( "and" not_expr )*
    not_expr    := "not" not_expr | primary
    primary     := "(" or_expr ")"
                 | quantifier
                 | IDENTIFIER
    quantifier  := ( "1" | "any" | "all" ) "of" ( "them" | pattern )

`pattern` supports the wildcard form Sigma uses for selection groups, e.g.
`all of selection_*`.

Reference: https://sigmahq.io/docs/basics/conditions.html

Aggregation conditions (`| count() > 5`) are NOT handled here -- they are
evaluated at batch level by the engine's count-rule path. `split_aggregation()`
separates them.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence


class SigmaConditionError(ValueError):
    """Raised when a condition string cannot be parsed."""


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    (?P<lparen>\() |
    (?P<rparen>\)) |
    (?P<ident>[A-Za-z_][A-Za-z0-9_*]*|1) |
    (?P<ws>\s+)
    """,
    re.VERBOSE,
)

_KEYWORDS = {"and", "or", "not", "of", "them", "all", "any"}


@dataclass(frozen=True)
class Token:
    kind: str  # 'ident' | 'lparen' | 'rparen'
    value: str


def tokenize(condition: str) -> List[Token]:
    """Split a condition string into tokens."""
    tokens: List[Token] = []
    position = 0

    while position < len(condition):
        match = _TOKEN_RE.match(condition, position)
        if not match:
            raise SigmaConditionError(
                f"Unexpected character {condition[position]!r} at position {position} "
                f"in condition: {condition!r}"
            )
        position = match.end()

        if match.lastgroup == "ws":
            continue
        tokens.append(Token(match.lastgroup, match.group()))

    return tokens


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------


class Node:
    """Base class for condition AST nodes."""

    def evaluate(self, resolver: Callable[[str], bool], names: Sequence[str]) -> bool:
        raise NotImplementedError

    def identifiers(self) -> List[str]:
        """Selection names referenced by this node (for validation)."""
        return []


@dataclass(frozen=True)
class Identifier(Node):
    name: str

    def evaluate(self, resolver, names):
        return resolver(self.name)

    def identifiers(self):
        return [self.name]


@dataclass(frozen=True)
class Not(Node):
    operand: Node

    def evaluate(self, resolver, names):
        return not self.operand.evaluate(resolver, names)

    def identifiers(self):
        return self.operand.identifiers()


@dataclass(frozen=True)
class And(Node):
    left: Node
    right: Node

    def evaluate(self, resolver, names):
        # Short-circuit: matters because resolving a selection runs field
        # matching over the log entry.
        return self.left.evaluate(resolver, names) and self.right.evaluate(
            resolver, names
        )

    def identifiers(self):
        return self.left.identifiers() + self.right.identifiers()


@dataclass(frozen=True)
class Or(Node):
    left: Node
    right: Node

    def evaluate(self, resolver, names):
        return self.left.evaluate(resolver, names) or self.right.evaluate(
            resolver, names
        )

    def identifiers(self):
        return self.left.identifiers() + self.right.identifiers()


@dataclass(frozen=True)
class Quantifier(Node):
    """`1 of them`, `all of them`, `any of selection_*`."""

    mode: str  # 'one' | 'all'
    pattern: str  # 'them' or a glob such as 'selection_*'

    def _targets(self, names: Sequence[str]) -> List[str]:
        if self.pattern == "them":
            return list(names)
        return [n for n in names if fnmatch.fnmatchcase(n, self.pattern)]

    def evaluate(self, resolver, names):
        targets = self._targets(names)
        if not targets:
            # No selection matches the pattern. `all of <empty>` is vacuously
            # true in logic, but for a detection rule that would fire on
            # everything -- so it is treated as no-match, which fails safe.
            return False

        if self.mode == "all":
            return all(resolver(name) for name in targets)
        return any(resolver(name) for name in targets)


# ---------------------------------------------------------------------------
# Parser (recursive descent)
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: List[Token], source: str):
        self.tokens = tokens
        self.source = source
        self.pos = 0

    def peek(self) -> Optional[Token]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> Token:
        token = self.peek()
        if token is None:
            raise SigmaConditionError(f"Unexpected end of condition: {self.source!r}")
        self.pos += 1
        return token

    def expect_ident(self, value: str) -> None:
        token = self.next()
        if token.kind != "ident" or token.value.lower() != value:
            raise SigmaConditionError(
                f"Expected {value!r} but found {token.value!r} in {self.source!r}"
            )

    def parse(self) -> Node:
        node = self.parse_or()
        if self.peek() is not None:
            raise SigmaConditionError(
                f"Trailing tokens after condition: {self.source!r}"
            )
        return node

    def parse_or(self) -> Node:
        node = self.parse_and()
        while True:
            token = self.peek()
            if token and token.kind == "ident" and token.value.lower() == "or":
                self.next()
                node = Or(node, self.parse_and())
            else:
                return node

    def parse_and(self) -> Node:
        node = self.parse_not()
        while True:
            token = self.peek()
            if token and token.kind == "ident" and token.value.lower() == "and":
                self.next()
                node = And(node, self.parse_not())
            else:
                return node

    def parse_not(self) -> Node:
        token = self.peek()
        if token and token.kind == "ident" and token.value.lower() == "not":
            self.next()
            return Not(self.parse_not())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        token = self.next()

        if token.kind == "lparen":
            node = self.parse_or()
            closing = self.next()
            if closing.kind != "rparen":
                raise SigmaConditionError(
                    f"Expected ')' in condition: {self.source!r}"
                )
            return node

        if token.kind != "ident":
            raise SigmaConditionError(
                f"Unexpected token {token.value!r} in {self.source!r}"
            )

        lowered = token.value.lower()

        # Quantifiers: "1 of them", "all of them", "any of selection_*"
        if lowered in {"1", "all", "any"}:
            following = self.peek()
            if following and following.kind == "ident" and following.value.lower() == "of":
                self.next()  # consume 'of'
                target = self.next()
                if target.kind != "ident":
                    raise SigmaConditionError(
                        f"Expected a selection name after 'of' in {self.source!r}"
                    )
                mode = "all" if lowered == "all" else "one"
                return Quantifier(mode, target.value)

        if lowered in _KEYWORDS:
            raise SigmaConditionError(
                f"Unexpected keyword {token.value!r} in {self.source!r}"
            )

        return Identifier(token.value)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_AGGREGATION_RE = re.compile(r"\|")


def split_aggregation(condition: str) -> tuple[str, Optional[str]]:
    """
    Split `selection | count() > 5` into `("selection", "count() > 5")`.

    Aggregations are evaluated at batch level by the engine's count-rule path,
    not by this parser.
    """
    if "|" not in condition:
        return condition.strip(), None
    head, _, tail = condition.partition("|")
    return head.strip(), tail.strip()


def parse_condition(condition: str) -> Node:
    """
    Parse a Sigma condition string into an evaluable AST.

    Raises:
        SigmaConditionError: if the condition cannot be parsed. Callers must
        treat this as "do not evaluate this rule" rather than "no match": a rule
        that cannot be understood must never be silently treated as passing.
    """
    if condition is None:
        raise SigmaConditionError("Condition is None")

    expression, _ = split_aggregation(condition)
    if not expression.strip():
        raise SigmaConditionError(f"Empty condition: {condition!r}")

    return _Parser(tokenize(expression), condition).parse()


def evaluate_condition(
    condition: str,
    selection_results: Dict[str, bool],
) -> bool:
    """
    Evaluate a Sigma condition against pre-computed selection results.

    Args:
        condition: the rule's condition string.
        selection_results: {selection_name: matched}. Must contain every
            selection block defined by the rule, so `them` / wildcards resolve
            over the full set.

    Raises:
        SigmaConditionError: on unparseable input or an unknown selection name.
    """
    ast = parse_condition(condition)

    # An identifier the rule never defined is a rule authoring error. Failing
    # loudly beats silently treating it as False, which would quietly disable
    # part of a detection.
    unknown = [
        name for name in ast.identifiers() if name not in selection_results
    ]
    if unknown:
        raise SigmaConditionError(
            f"Condition references undefined selection(s) {unknown} "
            f"in: {condition!r}"
        )

    names = list(selection_results)
    return ast.evaluate(lambda name: bool(selection_results.get(name, False)), names)
