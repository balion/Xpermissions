/**
 * Visual builder for workflow step `conditions`.
 *
 * Usage: add <div class="condition-builder" data-target="<textarea-id>"></div>
 * anywhere below the JSON config textarea and include this script. The builder
 * parses the JSON, lets the user edit a step's conditions with form controls
 * and writes the result back into the textarea.
 *
 * Operator list mirrors apps/approvals/conditions.py.
 */
(() => {
  'use strict';

  const BINARY_OPERATORS = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'contains'];
  const UNARY_OPERATORS = ['is_null', 'is_not_null', 'is_true', 'is_false', 'is_empty', 'is_not_empty'];
  const ALL_OPERATORS = [...BINARY_OPERATORS, ...UNARY_OPERATORS];
  const LIST_OPERATORS = new Set(['in', 'not_in']);

  const OPERATOR_LABELS = {
    eq: 'equals', ne: 'not equals', gt: '>', gte: '≥', lt: '<', lte: '≤',
    in: 'in list', not_in: 'not in list', contains: 'contains',
    is_null: 'is null', is_not_null: 'is not null', is_true: 'is true',
    is_false: 'is false', is_empty: 'is empty', is_not_empty: 'is not empty',
  };

  function isUnary(op) {
    return UNARY_OPERATORS.includes(op);
  }

  /** Parse a raw value input: JSON first, comma-split for list operators, else string. */
  function parseValue(raw, operator) {
    const text = raw.trim();
    if (LIST_OPERATORS.has(operator)) {
      try {
        const parsed = JSON.parse(text);
        if (Array.isArray(parsed)) return parsed;
      } catch (e) { /* fall through to comma split */ }
      return text.split(',').map((item) => {
        const part = item.trim();
        try { return JSON.parse(part); } catch (e) { return part; }
      }).filter((item) => item !== '');
    }
    try { return JSON.parse(text); } catch (e) { return text; }
  }

  function formatValue(value) {
    if (value === undefined) return '';
    if (Array.isArray(value)) {
      return value.map((item) => (typeof item === 'string' ? item : JSON.stringify(item))).join(', ');
    }
    return typeof value === 'string' ? value : JSON.stringify(value);
  }

  function el(tag, className, attrs = {}) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    Object.entries(attrs).forEach(([key, val]) => node.setAttribute(key, val));
    return node;
  }

  class ConditionBuilder {
    constructor(root) {
      this.root = root;
      this.textarea = document.getElementById(root.dataset.target);
      if (!this.textarea) return;
      this.render();
      this.refreshSteps();

      let debounce;
      this.textarea.addEventListener('input', () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => this.refreshSteps(), 600);
      });
    }

    // ── UI scaffolding ────────────────────────────────────────────────

    render() {
      this.root.innerHTML = '';
      this.root.classList.add('card', 'border-0', 'shadow-sm', 'mt-3');

      const header = el('div', 'card-header bg-white py-2');
      const toggleId = `cb-body-${Math.random().toString(36).slice(2, 8)}`;
      header.innerHTML = `
        <button class="btn btn-link btn-sm text-decoration-none p-0 text-dark fw-semibold"
                type="button" data-bs-toggle="collapse" data-bs-target="#${toggleId}">
          <i class="bi bi-sliders2 me-2 text-secondary"></i>Condition builder
          <i class="bi bi-chevron-down ms-1"></i>
        </button>`;

      const collapse = el('div', 'collapse', { id: toggleId });
      const body = el('div', 'card-body');

      // Step selector + match mode
      const controls = el('div', 'row g-2 align-items-end mb-3');
      controls.innerHTML = `
        <div class="col-sm-6">
          <label class="form-label small fw-semibold mb-1">Step</label>
          <select class="form-select form-select-sm" data-role="step"></select>
        </div>
        <div class="col-sm-6">
          <label class="form-label small fw-semibold mb-1">Apply the step when</label>
          <select class="form-select form-select-sm" data-role="match">
            <option value="all">ALL rules match</option>
            <option value="any">ANY rule matches</option>
          </select>
        </div>`;

      this.rulesContainer = el('div', 'vstack gap-2 mb-2');

      const actions = el('div', 'd-flex flex-wrap gap-2 align-items-center');
      actions.innerHTML = `
        <button type="button" class="btn btn-outline-secondary btn-sm" data-role="add">
          <i class="bi bi-plus-lg me-1"></i>Add rule
        </button>
        <button type="button" class="btn btn-primary btn-sm" data-role="apply">
          <i class="bi bi-check-lg me-1"></i>Apply to step
        </button>
        <button type="button" class="btn btn-outline-danger btn-sm" data-role="clear">
          <i class="bi bi-trash me-1"></i>Remove conditions
        </button>
        <span class="small text-muted flex-grow-1 text-end" data-role="status"></span>`;

      const hint = el('div', 'form-text mt-2');
      hint.textContent = 'Field supports dotted paths (e.g. owner.email). '
        + 'Values: numbers and true/false are detected automatically; '
        + 'for "in list" use comma-separated values.';

      body.append(controls, this.rulesContainer, actions, hint);
      collapse.append(body);
      this.root.append(header, collapse);

      this.stepSelect = this.root.querySelector('[data-role="step"]');
      this.matchSelect = this.root.querySelector('[data-role="match"]');
      this.statusEl = this.root.querySelector('[data-role="status"]');

      this.stepSelect.addEventListener('change', () => this.loadStepConditions());
      this.root.querySelector('[data-role="add"]').addEventListener('click', () => this.addRuleRow());
      this.root.querySelector('[data-role="apply"]').addEventListener('click', () => this.apply());
      this.root.querySelector('[data-role="clear"]').addEventListener('click', () => this.apply(true));
    }

    addRuleRow(rule = {}) {
      const row = el('div', 'd-flex gap-2 align-items-start cb-rule');
      const operatorOptions = ALL_OPERATORS
        .map((op) => `<option value="${op}">${OPERATOR_LABELS[op]}</option>`)
        .join('');
      row.innerHTML = `
        <input type="text" class="form-control form-control-sm" data-role="field"
               placeholder="field (e.g. status)" style="max-width: 32%;">
        <select class="form-select form-select-sm" data-role="operator" style="max-width: 26%;">
          ${operatorOptions}
        </select>
        <input type="text" class="form-control form-control-sm" data-role="value" placeholder="value">
        <button type="button" class="btn btn-outline-danger btn-sm" data-role="remove"
                title="Remove rule" aria-label="Remove rule">
          <i class="bi bi-x-lg"></i>
        </button>`;

      const fieldInput = row.querySelector('[data-role="field"]');
      const operatorSelect = row.querySelector('[data-role="operator"]');
      const valueInput = row.querySelector('[data-role="value"]');

      fieldInput.value = rule.field || '';
      operatorSelect.value = ALL_OPERATORS.includes(rule.operator) ? rule.operator : 'eq';
      valueInput.value = formatValue(rule.value);

      const syncValueState = () => {
        const unary = isUnary(operatorSelect.value);
        valueInput.disabled = unary;
        valueInput.placeholder = unary ? '(no value needed)' : 'value';
        if (unary) valueInput.value = '';
      };
      operatorSelect.addEventListener('change', syncValueState);
      syncValueState();

      row.querySelector('[data-role="remove"]').addEventListener('click', () => row.remove());
      this.rulesContainer.append(row);
    }

    // ── JSON round-trip ───────────────────────────────────────────────

    parseConfig() {
      const text = this.textarea.value.trim();
      if (!text) {
        this.setStatus('Config JSON is empty.', true);
        return null;
      }
      try {
        const config = JSON.parse(text);
        if (!Array.isArray(config.steps)) {
          this.setStatus('Config has no "steps" list.', true);
          return null;
        }
        return config;
      } catch (e) {
        this.setStatus('Fix the JSON first: ' + e.message, true);
        return null;
      }
    }

    refreshSteps() {
      const previous = this.stepSelect.value;
      this.stepSelect.innerHTML = '';
      const config = this.parseConfig();
      if (!config) {
        this.stepSelect.disabled = true;
        return;
      }
      this.stepSelect.disabled = false;
      config.steps.forEach((step) => {
        if (!step || !step.step_key) return;
        const option = el('option');
        option.value = step.step_key;
        const marker = step.conditions ? ' ●' : '';
        option.textContent = `${step.step_order}. ${step.step_key}${marker}`;
        this.stepSelect.append(option);
      });
      if ([...this.stepSelect.options].some((o) => o.value === previous)) {
        this.stepSelect.value = previous;
      }
      this.setStatus('');
      this.loadStepConditions();
    }

    loadStepConditions() {
      this.rulesContainer.innerHTML = '';
      const config = this.parseConfig();
      if (!config) return;
      const step = config.steps.find((s) => s && s.step_key === this.stepSelect.value);
      if (!step) return;
      const conditions = step.conditions || {};
      this.matchSelect.value = conditions.match === 'any' ? 'any' : 'all';
      (conditions.rules || []).forEach((rule) => this.addRuleRow(rule));
      if (!(conditions.rules || []).length) this.addRuleRow();
    }

    collectRules() {
      const rules = [];
      let error = null;
      this.rulesContainer.querySelectorAll('.cb-rule').forEach((row) => {
        const field = row.querySelector('[data-role="field"]').value.trim();
        const operator = row.querySelector('[data-role="operator"]').value;
        const rawValue = row.querySelector('[data-role="value"]').value;
        if (!field && !rawValue.trim()) return; // fully empty row — ignore
        if (!field) {
          error = 'Every rule needs a field.';
          return;
        }
        const rule = { field, operator };
        if (!isUnary(operator)) {
          if (!rawValue.trim()) {
            error = `Rule "${field}": operator "${operator}" needs a value.`;
            return;
          }
          rule.value = parseValue(rawValue, operator);
        }
        rules.push(rule);
      });
      return { rules, error };
    }

    apply(remove = false) {
      const config = this.parseConfig();
      if (!config) return;
      const step = config.steps.find((s) => s && s.step_key === this.stepSelect.value);
      if (!step) {
        this.setStatus('Select a step first.', true);
        return;
      }

      if (remove) {
        delete step.conditions;
      } else {
        const { rules, error } = this.collectRules();
        if (error) {
          this.setStatus(error, true);
          return;
        }
        if (!rules.length) {
          this.setStatus('Add at least one rule (or use "Remove conditions").', true);
          return;
        }
        step.conditions = { match: this.matchSelect.value, rules };
      }

      this.textarea.value = JSON.stringify(config, null, 2);
      this.textarea.dispatchEvent(new Event('input', { bubbles: true }));
      this.setStatus(remove
        ? `Conditions removed from "${step.step_key}".`
        : `Conditions applied to "${step.step_key}".`);
      this.refreshSteps();
    }

    setStatus(message, isError = false) {
      this.statusEl.textContent = message;
      this.statusEl.classList.toggle('text-danger', isError);
      this.statusEl.classList.toggle('text-muted', !isError);
    }
  }

  document.querySelectorAll('.condition-builder[data-target]').forEach((root) => {
    // eslint-disable-next-line no-new
    new ConditionBuilder(root);
  });
})();
