"""Data-driven step conditions.

A step may carry an optional ``conditions`` block that is evaluated against the
workflow's ``content_object`` when the step is about to be activated. If the
conditions are not met the step is skipped and the workflow moves on. This keeps
workflows fully generic — e.g. "require finance approval only when amount > 1000".

Config shape::

    "conditions": {
        "match": "all",            # "all" (default) or "any"
        "rules": [
            {"field": "amount", "operator": "gt", "value": 1000},
            {"field": "status", "operator": "eq", "value": "pending_approval"}
        ]
    }

``field`` supports dotted paths (``"owner.email"``) resolved by attribute access.
"""
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

MATCH_ALL = 'all'
MATCH_ANY = 'any'
VALID_MATCH = {MATCH_ALL, MATCH_ANY}

# Operators that compare against a ``value`` from the config.
BINARY_OPERATORS = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'contains'}
# Operators that only inspect the resolved field (no ``value`` required).
UNARY_OPERATORS = {'is_null', 'is_not_null', 'is_true', 'is_false', 'is_empty', 'is_not_empty'}

_OPERATORS: dict[str, Callable[[Any, Any], bool]] = {
    'eq': lambda a, e: a == e,
    'ne': lambda a, e: a != e,
    'gt': lambda a, e: a is not None and a > e,
    'gte': lambda a, e: a is not None and a >= e,
    'lt': lambda a, e: a is not None and a < e,
    'lte': lambda a, e: a is not None and a <= e,
    'in': lambda a, e: a in e,
    'not_in': lambda a, e: a not in e,
    'contains': lambda a, e: bool(a) and e in a,
    'is_null': lambda a, e: a is None,
    'is_not_null': lambda a, e: a is not None,
    'is_true': lambda a, e: bool(a) is True,
    'is_false': lambda a, e: bool(a) is False,
    'is_empty': lambda a, e: not a,
    'is_not_empty': lambda a, e: bool(a),
}

VALID_OPERATORS = set(_OPERATORS)


def evaluate_conditions(conditions: dict | None, obj: Any) -> bool:
    """Return True if *obj* satisfies *conditions* (empty/missing → True)."""
    if not conditions:
        return True

    rules = conditions.get('rules') or []
    if not rules:
        return True

    match = conditions.get('match', MATCH_ALL)
    results = [_evaluate_rule(rule, obj) for rule in rules]
    return any(results) if match == MATCH_ANY else all(results)


def _evaluate_rule(rule: dict, obj: Any) -> bool:
    actual = _resolve_field(obj, rule.get('field'))
    return _apply_operator(rule.get('operator'), actual, rule.get('value'))


def _resolve_field(obj: Any, field: str | None) -> Any:
    """Resolve a (possibly dotted) attribute path on *obj*; missing → None."""
    if not field:
        return None
    current = obj
    for part in str(field).split('.'):
        if current is None:
            return None
        current = getattr(current, part, None)
    return current


def _apply_operator(operator_name: str | None, actual: Any, expected: Any) -> bool:
    func = _OPERATORS.get(operator_name)
    if func is None:
        logger.warning("Unknown condition operator '%s'.", operator_name)
        return False
    try:
        return bool(func(actual, expected))
    except TypeError:
        logger.warning(
            "Condition operator '%s' failed on incompatible types (%r, %r).",
            operator_name, actual, expected,
        )
        return False
