(() => {
  'use strict';

  // Row toggles — work on any permissions-table
  document.querySelectorAll('.permissions-table .row-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      const boxes = [...btn.closest('tr').querySelectorAll('input[type="checkbox"]')];
      const allChecked = boxes.every((cb) => cb.checked);
      boxes.forEach((cb) => { cb.checked = !allChecked; });
    });
  });

  // Column toggles — scoped to the table identified by data-table
  document.querySelectorAll('.col-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tableId = btn.dataset.table;
      const action = btn.dataset.action;
      const table = document.getElementById(tableId);
      if (!table) return;
      const boxes = [...table.querySelectorAll(`input[id$="_${action}"]`)];
      const allChecked = boxes.every((cb) => cb.checked);
      boxes.forEach((cb) => { cb.checked = !allChecked; });
    });
  });

  // Scoped all/none buttons via data-scope + data-action-toggle
  document.querySelectorAll('[data-action-toggle]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const scope = btn.dataset.scope;
      const toggle = btn.dataset.actionToggle;
      const tableId = scope === 'module' ? 'module-table' : 'project-table';
      const table = document.getElementById(tableId);
      if (!table) return;
      const boxes = [...table.querySelectorAll('input[type="checkbox"]')];
      boxes.forEach((cb) => { cb.checked = toggle === 'all'; });
    });
  });
})();
