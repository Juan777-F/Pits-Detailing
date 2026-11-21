document.addEventListener('DOMContentLoaded', function () {
  const sidebar = document.getElementById('sidebar');
  const menuToggle = document.querySelector('.menu-toggle');
  const modalBackdrop = document.getElementById('modal-backdrop');
  const notificationPanel = document.getElementById('notification-panel');
  const notificationButton = document.querySelector('.notification-button');
  const searchInput = document.getElementById('global-search');
  const currencyInputs = document.querySelectorAll('[data-currency-input]');

  currencyInputs.forEach(function (input) {
    input.addEventListener('input', function () {
      const cursor = input.selectionStart || 0;
      const digitsBeforeCursor = input.value.slice(0, cursor).replace(/\D/g, '').length;
      const digits = input.value.replace(/\D/g, '');
      input.value = digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

      let nextCursor = 0;
      let countedDigits = 0;
      while (nextCursor < input.value.length && countedDigits < digitsBeforeCursor) {
        if (/\d/.test(input.value[nextCursor])) countedDigits += 1;
        nextCursor += 1;
      }
      input.setSelectionRange(nextCursor, nextCursor);
    });
  });

  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function () {
      form.querySelectorAll('[data-currency-input]').forEach(function (input) {
        input.value = input.value.replace(/\./g, '');
      });
    });
  });

  function setModalOpen(isOpen) {
    if (!modalBackdrop) return;
    modalBackdrop.hidden = !isOpen;
    if (isOpen) {
      const firstField = modalBackdrop.querySelector('input');
      if (firstField) firstField.focus();
    }
  }

  if (menuToggle && sidebar) {
    menuToggle.addEventListener('click', function () {
      if (window.matchMedia('(max-width: 760px)').matches) {
        sidebar.classList.toggle('open');
        menuToggle.setAttribute('aria-expanded', String(sidebar.classList.contains('open')));
      } else {
        sidebar.classList.toggle('collapsed');
      }
    });

    document.addEventListener('click', function (event) {
      if (
        window.matchMedia('(max-width: 760px)').matches &&
        sidebar.classList.contains('open') &&
        !sidebar.contains(event.target) &&
        !menuToggle.contains(event.target)
      ) {
        sidebar.classList.remove('open');
        menuToggle.setAttribute('aria-expanded', 'false');
      }
    });
  }

  document.querySelectorAll('[data-open-modal]').forEach(function (button) {
    button.addEventListener('click', function () {
      setModalOpen(true);
    });
  });

  document.querySelectorAll('[data-close]').forEach(function (button) {
    button.addEventListener('click', function () {
      const element = document.getElementById(button.dataset.close);
      if (!element) return;
      if (element === modalBackdrop) {
        setModalOpen(false);
      } else {
        element.hidden = true;
        if (element === notificationPanel && notificationButton) {
          notificationButton.setAttribute('aria-expanded', 'false');
        }
      }
    });
  });

  if (modalBackdrop) {
    modalBackdrop.addEventListener('click', function (event) {
      if (event.target === modalBackdrop) setModalOpen(false);
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      setModalOpen(false);
      if (notificationPanel) notificationPanel.hidden = true;
      if (sidebar) sidebar.classList.remove('open');
    }
  });

  if (notificationButton && notificationPanel) {
    notificationPanel.hidden = true;
    notificationButton.setAttribute('aria-expanded', 'false');
    notificationButton.addEventListener('click', function () {
      notificationPanel.hidden = !notificationPanel.hidden;
      notificationButton.setAttribute('aria-expanded', String(!notificationPanel.hidden));
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      const query = searchInput.value.trim().toLocaleLowerCase();
      document.querySelectorAll('[data-search-list] .vehicle-card, .jornada-item, .payment-card').forEach(function (item) {
        item.hidden = !item.textContent.toLocaleLowerCase().includes(query);
      });
    });
  }
});
