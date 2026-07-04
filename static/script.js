(function () {
  const root = document.documentElement;
  const toggle = document.getElementById('theme-toggle');
  const stored = localStorage.getItem('scanline-theme');
  const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;

  root.setAttribute('data-theme', stored || (prefersLight ? 'light' : 'dark'));

  toggle.addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    localStorage.setItem('scanline-theme', next);
  });
})();
