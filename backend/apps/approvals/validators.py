from django.core.exceptions import ValidationError

from apps.approvals.conditions import UNARY_OPERATORS, VALID_MATCH, VALID_OPERATORS
from apps.approvals.policies import (
    CALLBACK_EVENTS,
    VALID_ON_DEADLINE,
    VALID_ON_NO_APPROVERS,
)

REQUIRED_WORKFLOW_KEYS = {'workflow_name', 'steps'}
REQUIRED_STEP_KEYS = {'step_key', 'step_order', 'approval_type', 'approvers'}
VALID_APPROVAL_TYPES = {'any', 'all', 'majority', 'quorum'}
VALID_APPROVER_TYPES = {'user', 'role', 'group', 'attribute'}
OPTIONAL_NOTIFICATION_KEYS = {
    'on_activate', 'on_complete', 'on_reject', 'on_request_changes', 'on_deadline',
}
VALID_NOTIFICATION_RECIPIENTS = {'approvers', 'requester', 'all'}


def validate_workflow_config(config: dict) -> None:
    """Validate the JSON structure of a workflow config."""
    if not isinstance(config, dict):
        raise ValidationError("Workflow config must be a JSON object.")

    missing = REQUIRED_WORKFLOW_KEYS - config.keys()
    if missing:
        raise ValidationError(f"Workflow config missing required keys: {sorted(missing)}")

    if not isinstance(config.get('workflow_name'), str) or not config['workflow_name'].strip():
        raise ValidationError("'workflow_name' must be a non-empty string.")

    steps = config.get('steps')
    if not isinstance(steps, list) or len(steps) == 0:
        raise ValidationError("'steps' must be a non-empty list.")

    seen_keys: set = set()
    seen_orders: set = set()
    for i, step in enumerate(steps):
        _validate_step(step, i, seen_keys, seen_orders)

    if 'callback' in config:
        cb = config['callback']
        if not isinstance(cb, str) or not cb.strip():
            raise ValidationError("'callback' must be a non-empty string method name.")

    if 'callbacks' in config:
        _validate_callbacks(config['callbacks'])

    if 'allow_concurrent' in config and not isinstance(config['allow_concurrent'], bool):
        raise ValidationError("'allow_concurrent' must be a boolean.")


def _validate_callbacks(callbacks) -> None:
    if not isinstance(callbacks, dict):
        raise ValidationError("'callbacks' must be a JSON object.")
    for key, value in callbacks.items():
        if key not in CALLBACK_EVENTS:
            raise ValidationError(
                f"'callbacks' has unknown event '{key}'. "
                f"Must be one of {sorted(CALLBACK_EVENTS)}."
            )
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(
                f"'callbacks[\"{key}\"]' must be a non-empty string method name."
            )


def _validate_step(step: dict, index: int, seen_keys: set, seen_orders: set) -> None:
    prefix = f"Step #{index + 1}"

    if not isinstance(step, dict):
        raise ValidationError(f"{prefix}: each step must be a JSON object.")

    missing_step = REQUIRED_STEP_KEYS - step.keys()
    if missing_step:
        raise ValidationError(f"{prefix}: missing required keys: {sorted(missing_step)}")

    _validate_step_key(step['step_key'], prefix, seen_keys)
    _validate_step_order(step['step_order'], prefix, seen_orders)

    if step['approval_type'] not in VALID_APPROVAL_TYPES:
        raise ValidationError(
            f"{prefix}: 'approval_type' must be one of {sorted(VALID_APPROVAL_TYPES)}, "
            f"got '{step['approval_type']}'."
        )

    if step['approval_type'] == 'quorum':
        qc = step.get('quorum_count')
        if not isinstance(qc, int) or qc < 1:
            raise ValidationError(
                f"{prefix}: approval_type 'quorum' requires a positive integer 'quorum_count'."
            )

    approvers = step['approvers']
    if not isinstance(approvers, list) or len(approvers) == 0:
        raise ValidationError(f"{prefix}: 'approvers' must be a non-empty list.")
    for j, approver in enumerate(approvers):
        _validate_approver(approver, f"{prefix} approver #{j + 1}")

    if 'notifications' in step:
        _validate_step_notifications(step['notifications'], prefix)

    if 'conditions' in step:
        _validate_step_conditions(step['conditions'], prefix)

    _validate_step_options(step, prefix)


def _validate_step_options(step: dict, prefix: str) -> None:
    """Validate the optional step flags (deadline, policies, self-approval)."""
    if 'deadline_hours' in step:
        dh = step['deadline_hours']
        if not isinstance(dh, (int, float)) or dh <= 0:
            raise ValidationError(f"{prefix}: 'deadline_hours' must be a positive number.")

    if 'on_deadline' in step and step['on_deadline'] not in VALID_ON_DEADLINE:
        raise ValidationError(
            f"{prefix}: 'on_deadline' must be one of {sorted(VALID_ON_DEADLINE)}, "
            f"got '{step['on_deadline']}'."
        )

    if 'on_no_approvers' in step and step['on_no_approvers'] not in VALID_ON_NO_APPROVERS:
        raise ValidationError(
            f"{prefix}: 'on_no_approvers' must be one of {sorted(VALID_ON_NO_APPROVERS)}, "
            f"got '{step['on_no_approvers']}'."
        )

    if 'allow_self_approval' in step and not isinstance(step['allow_self_approval'], bool):
        raise ValidationError(f"{prefix}: 'allow_self_approval' must be a boolean.")


def _validate_step_key(step_key, prefix: str, seen: set) -> None:
    if not isinstance(step_key, str) or not step_key.strip():
        raise ValidationError(f"{prefix}: 'step_key' must be a non-empty string.")
    if step_key in seen:
        raise ValidationError(f"Duplicate step_key '{step_key}'.")
    seen.add(step_key)


def _validate_step_order(step_order, prefix: str, seen: set) -> None:
    if not isinstance(step_order, int) or step_order < 1:
        raise ValidationError(f"{prefix}: 'step_order' must be a positive integer.")
    if step_order in seen:
        raise ValidationError(f"Duplicate step_order {step_order}.")
    seen.add(step_order)


def _validate_approver(approver: dict, label: str) -> None:
    if not isinstance(approver, dict):
        raise ValidationError(f"{label}: must be a JSON object.")
    if 'type' not in approver:
        raise ValidationError(f"{label}: missing 'type'.")
    approver_type = approver['type']
    if approver_type not in VALID_APPROVER_TYPES:
        raise ValidationError(
            f"{label}: 'type' must be one of {sorted(VALID_APPROVER_TYPES)}, got '{approver_type}'."
        )

    if approver_type == 'attribute':
        path = approver.get('path')
        if not isinstance(path, str) or not path.strip():
            raise ValidationError(
                f"{label}: approver type 'attribute' requires a non-empty string 'path'."
            )
        return

    if approver_type == 'user':
        if 'id' not in approver and 'email' not in approver:
            raise ValidationError(f"{label}: requires 'id' or 'email'.")
        if 'id' in approver and not isinstance(approver['id'], (int, str)):
            raise ValidationError(f"{label}: 'id' must be an integer or string.")
        if 'email' in approver and (
            not isinstance(approver['email'], str) or '@' not in approver['email']
        ):
            raise ValidationError(f"{label}: 'email' must be a valid email address string.")
        return

    # role / group — referenced by 'id' or, portably, by 'name'
    if 'id' not in approver and 'name' not in approver:
        raise ValidationError(f"{label}: requires 'id' or 'name'.")
    if 'id' in approver and not isinstance(approver['id'], (int, str)):
        raise ValidationError(f"{label}: 'id' must be an integer or string.")
    if 'name' in approver and (
        not isinstance(approver['name'], str) or not approver['name'].strip()
    ):
        raise ValidationError(f"{label}: 'name' must be a non-empty string.")


def _validate_step_conditions(conditions, prefix: str) -> None:
    if not isinstance(conditions, dict):
        raise ValidationError(f"{prefix}: 'conditions' must be a JSON object.")

    match = conditions.get('match', 'all')
    if match not in VALID_MATCH:
        raise ValidationError(
            f"{prefix}: conditions 'match' must be one of {sorted(VALID_MATCH)}, got '{match}'."
        )

    rules = conditions.get('rules')
    if not isinstance(rules, list) or len(rules) == 0:
        raise ValidationError(f"{prefix}: conditions 'rules' must be a non-empty list.")

    for k, rule in enumerate(rules):
        _validate_condition_rule(rule, f"{prefix} rule #{k + 1}")


def _validate_condition_rule(rule, label: str) -> None:
    if not isinstance(rule, dict):
        raise ValidationError(f"{label}: must be a JSON object.")

    field = rule.get('field')
    if not isinstance(field, str) or not field.strip():
        raise ValidationError(f"{label}: 'field' must be a non-empty string.")

    operator = rule.get('operator')
    if operator not in VALID_OPERATORS:
        raise ValidationError(
            f"{label}: 'operator' must be one of {sorted(VALID_OPERATORS)}, got '{operator}'."
        )

    if operator not in UNARY_OPERATORS and 'value' not in rule:
        raise ValidationError(f"{label}: operator '{operator}' requires a 'value'.")


def _validate_step_notifications(notifications: dict, prefix: str) -> None:
    if not isinstance(notifications, dict):
        raise ValidationError(f"{prefix}: 'notifications' must be a JSON object.")
    for key in notifications:
        if key not in OPTIONAL_NOTIFICATION_KEYS:
            raise ValidationError(
                f"{prefix}: unknown notification event '{key}'. "
                f"Must be one of {sorted(OPTIONAL_NOTIFICATION_KEYS)}."
            )
        entry = notifications[key]
        if not isinstance(entry, dict):
            raise ValidationError(f"{prefix}: notifications['{key}'] must be a JSON object.")
        if 'template' not in entry:
            raise ValidationError(f"{prefix}: notifications['{key}'] missing 'template'.")
        if not isinstance(entry['template'], str) or not entry['template'].strip():
            raise ValidationError(
                f"{prefix}: notifications['{key}']['template'] must be a non-empty string."
            )
        recipients = entry.get('recipients')
        if recipients is not None and recipients not in VALID_NOTIFICATION_RECIPIENTS:
            raise ValidationError(
                f"{prefix}: notifications['{key}']['recipients'] must be one of "
                f"{sorted(VALID_NOTIFICATION_RECIPIENTS)}, got '{recipients}'."
            )
