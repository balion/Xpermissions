(() => {
  'use strict';

  // Sidebar toggle for mobile
  const sidebarToggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('sidebar');

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', () => {
      sidebar.classList.toggle('sidebar-open');
    });

    document.addEventListener('click', (e) => {
      if (!sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
        sidebar.classList.remove('sidebar-open');
      }
    });
  }

  // Delete modal: populate action URL and object name
  const deleteModal = document.getElementById('deleteModal');
  if (deleteModal) {
    deleteModal.addEventListener('show.bs.modal', (event) => {
      const trigger = event.relatedTarget;
      const name = trigger.getAttribute('data-name') || '';
      const url = trigger.getAttribute('data-url') || '';

      const nameEl = deleteModal.querySelector('#deleteTargetName');
      const form = deleteModal.querySelector('#deleteForm');

      if (nameEl) nameEl.textContent = name;
      if (form && url) form.action = url;
    });
  }

  // Auto-dismiss alerts after 5 seconds
  document.querySelectorAll('.alert.alert-dismissible').forEach((alert) => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) bsAlert.close();
    }, 5000);
  });
})();
