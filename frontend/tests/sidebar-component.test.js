// Comprueba el HTML compartido de la barra lateral y sus reglas de colapso.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');


function renderSidebar(options = {}) {
  const container = { innerHTML: '' };
  const document = {
    getElementById(id) {
      return id === 'sidebarRoot' ? container : null;
    }
  };
  const context = vm.createContext({ document, window: {} });
  const componentPath = path.join(__dirname, '..', 'sidebar-component.js');
  vm.runInContext(fs.readFileSync(componentPath, 'utf8'), context);
  context.window.renderSidebar(options);
  return container.innerHTML;
}


test('brand links back to the initial catalog with an accessible label', () => {
  const html = renderSidebar();

  assert.match(
    html,
    /<a class="brand" href="\/" aria-label="Volver al catálogo inicial">/
  );
  assert.match(html, /<strong>ArtSim<\/strong>/);
  assert.doesNotMatch(html, /<div class="brand">/);
});


test('sidebar collapse is available without an admin session on desktop and mobile', () => {
  const stylesPath = path.join(__dirname, '..', 'styles.css');
  const styles = fs.readFileSync(stylesPath, 'utf8');

  assert.doesNotMatch(styles, /body\.is-admin\s+#sidebarToggle:checked/);
  assert.match(styles, /@media \(min-width: 981px\)[\s\S]*#sidebarToggle:checked\s*~\s*\.app-shell\s*\{/);
  assert.match(styles, /@media \(max-width: 980px\)[\s\S]*#sidebarToggle:checked\s*~\s*\.app-shell \.sidebar\s*\{[\s\S]*display:\s*none/);
});
