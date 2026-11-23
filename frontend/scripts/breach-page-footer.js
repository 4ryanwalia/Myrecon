module.exports = function breachPageFooter(hasEmailCheck = false) {
  const lookup = hasEmailCheck ? `  <script src="/assets/js/env.js?v=10" defer></script>
  <script src="/assets/js/config.js?v=10" defer></script>
  <script src="/assets/js/breach-check.js" defer></script>
` : "";
  return `
  <footer class="footer">
    <div class="container"><div class="footer-bottom">
      <span>&copy; 2026 MyRecon · myrecon.xyz</span>
      <span><a href="/breaches/case-files/" style="color:var(--text-dim)">Case Files</a> · <a href="/breaches/" style="color:var(--text-dim)">Breaches</a> · <a href="/guides/" style="color:var(--text-dim)">Guides</a> · <a href="/privacy.html" style="color:var(--text-dim)">Privacy</a> · <a href="/cookies.html">Cookies</a> · <a href="/terms.html">Terms</a> · <a href="/cookies.html#manage" data-cookie-settings>Cookie policy</a></span>
    </div></div>
  </footer>
  <script src="/assets/js/editorial-shell.js" defer></script>
${lookup}  <script src="/assets/js/consent.js?v=10" defer></script>
  <script src="/assets/js/fx.js?v=8" defer></script>
</body>
</html>
`;
};
