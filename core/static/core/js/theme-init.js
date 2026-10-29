/* Runs before first paint so there is no theme flash. Loaded synchronously from <head>. */
(function () {
  try {
    var saved = localStorage.getItem('studysync-theme');
    var theme = saved || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) { document.documentElement.setAttribute('data-theme', 'light'); }
})();
