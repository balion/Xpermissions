(() => {
  'use strict';

  // Toggle API key visibility on project detail page
  const toggleBtn = document.getElementById('toggleApiKey');
  const maskEl = document.querySelector('.api-key-mask');

  if (toggleBtn && maskEl) {
    const realValue = toggleBtn.getAttribute('data-value') || '';
    let visible = false;

    toggleBtn.addEventListener('click', () => {
      visible = !visible;
      maskEl.textContent = visible ? (realValue || '(empty)') : '••••••••••••';
      toggleBtn.textContent = visible ? 'Hide' : 'Show';
    });
  }
})();
