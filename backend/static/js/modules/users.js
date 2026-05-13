(() => {
  'use strict';

  // Password visibility toggle (if present on user forms)
  document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.togglePassword);
      if (!target) return;
      target.type = target.type === 'password' ? 'text' : 'password';
      btn.textContent = target.type === 'password' ? 'Show' : 'Hide';
    });
  });
})();
