(function () {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('resume-input');
  const body = document.getElementById('dropzone-body');
  const jdInput = document.getElementById('jd-input');
  const charCount = document.getElementById('char-count');
  const form = document.getElementById('scan-form');
  const submitBtn = document.getElementById('submit-btn');

  function renderFileName(file) {
    if (!file) return;
    body.classList.add('has-file');
    body.innerHTML =
      '<svg viewBox="0 0 24 24" width="28" height="28" class="dropzone-icon">' +
      '<path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
      '<p><strong>' + file.name + '</strong></p>' +
      '<p class="dropzone-hint">Click to replace</p>';
  }

  fileInput.addEventListener('change', () => renderFileName(fileInput.files[0]));

  ['dragenter', 'dragover'].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add('is-dragover');
    })
  );
  ['dragleave', 'drop'].forEach((evt) =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove('is-dragover');
    })
  );
  dropzone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file) {
      fileInput.files = e.dataTransfer.files;
      renderFileName(file);
    }
  });

  jdInput.addEventListener('input', () => {
    charCount.textContent = jdInput.value.length + ' characters';
  });

  form.addEventListener('submit', () => {
    submitBtn.classList.add('is-loading');
    submitBtn.disabled = true;
  });
})();
