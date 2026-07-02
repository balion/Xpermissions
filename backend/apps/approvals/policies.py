"""Shared workflow policy constants.

Kept in a standalone module (no app imports) so both the engine and the
validator can use them without creating import cycles.
"""

# on_deadline policies (applied by handle_deadline / process_workflow_deadlines)
DEADLINE_NOTIFY = 'notify'
DEADLINE_SKIP = 'skip'
DEADLINE_AUTO_APPROVE = 'auto_approve'
DEADLINE_AUTO_REJECT = 'auto_reject'
VALID_ON_DEADLINE = {DEADLINE_NOTIFY, DEADLINE_SKIP, DEADLINE_AUTO_APPROVE, DEADLINE_AUTO_REJECT}

# on_no_approvers policies (applied when a step activates but no approver resolves)
NO_APPROVERS_BLOCK = 'block'
NO_APPROVERS_SKIP = 'skip'
VALID_ON_NO_APPROVERS = {NO_APPROVERS_BLOCK, NO_APPROVERS_SKIP}

# workflow-level completion callbacks ("callbacks": {"on_approved": …})
CALLBACK_EVENTS = {'on_approved', 'on_rejected'}
