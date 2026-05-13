(() => {
  'use strict';

  // Format JSON data blocks on audit detail page
  document.querySelectorAll('.audit-data-pre').forEach((pre) => {
    try {
      const raw = pre.textContent.trim();
      if (raw && raw !== '{}') {
        pre.textContent = JSON.stringify(JSON.parse(raw), null, 2);
      }
    } catch (_) {
      // Not valid JSON — leave as-is
    }
  });
})();
