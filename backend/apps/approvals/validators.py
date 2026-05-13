from django.core.exceptions import ValidationError

REQUIRED_WORKFLOW_KEYS = {'workflow_name', 'steps'}
REQUIRED_STEP_KEYS = {'step_key', 'step_order', 'approval_type', 'approvers'}
VALID_APPROVAL_TYPES = {'any', 'all', 'majority'}
VALID_APPROVER_TYPES = {'user', 'role', 'group'}
OPTIONAL_NOTIFICATION_KEYS = {'on_activate', 'on_complete', 'on_reject'}


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

    approvers = step['approvers']
    if not isinstance(approvers, list) or len(approvers) == 0:
        raise ValidationError(f"{prefix}: 'approvers' must be a non-empty list.")
    for j, approver in enumerate(approvers):
        _validate_approver(approver, f"{prefix} approver #{j + 1}")

    if 'notifications' in step:
        _validate_step_notifications(step['notifications'], prefix)

    if 'deadline_hours' in step:
        dh = step['deadline_hours']
        if not isinstance(dh, (int, float)) or dh <= 0:
            raise ValidationError(f"{prefix}: 'deadline_hours' must be a positive number.")


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
    if approver['type'] not in VALID_APPROVER_TYPES:
        raise ValidationError(
            f"{label}: 'type' must be one of {sorted(VALID_APPROVER_TYPES)}, got '{approver['type']}'."
        )
    if 'id' not in approver:
        raise ValidationError(f"{label}: missing 'id'.")
    if not isinstance(approver['id'], (int, str)):
        raise ValidationError(f"{label}: 'id' must be an integer or string.")


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
