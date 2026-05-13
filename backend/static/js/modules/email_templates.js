(() => {
  'use strict';

  const getCsrf = () => {
    const el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  };

  const showPreview = (html) => {
    const frame = document.getElementById('preview-frame');
    if (!frame) return;
    frame.srcdoc = html;

    const card = document.getElementById('preview-card');
    if (card) card.style.display = '';

    const status = document.getElementById('preview-status');
    if (status) status.textContent = 'Rendered';
  };

  const showPreviewError = (msg) => {
    const errText = document.getElementById('preview-error-text');
    if (errText) errText.textContent = msg;
    const modal = document.getElementById('previewErrorModal');
    if (modal) bootstrap.Modal.getOrCreateInstance(modal).show();

    const status = document.getElementById('preview-status');
    if (status) status.textContent = 'Error';
  };

  const requestPreview = async (url, mjmlBody) => {
    const status = document.getElementById('preview-status');
    if (status) status.textContent = 'Compiling…';

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrf(),
        },
        body: JSON.stringify({ mjml_body: mjmlBody }),
      });
      const data = await res.json();
      if (data.error) {
        showPreviewError(data.error);
      } else {
        showPreview(data.html);
      }
    } catch (err) {
      showPreviewError(String(err));
    }
  };

  // Form page: preview button uses the textarea content
  const previewBtn = document.getElementById('preview-btn');
  if (previewBtn) {
    previewBtn.addEventListener('click', () => {
      const textarea = document.getElementById('id_mjml_body');
      const url = previewBtn.dataset.url || window.location.pathname.replace(/\/$/, '') + '/preview/';
      const mjmlBody = textarea ? textarea.value : '';
      requestPreview(url, mjmlBody);
    });
  }
})();
