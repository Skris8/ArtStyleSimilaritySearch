// Ejecuta el script del catálogo en un DOM mínimo para verificar los reintentos.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');


function createRuntime(fetchImpl) {
  const gallery = { innerHTML: '' };
  const dropdown = {
    children: [],
    replaceChildren(fragment) {
      this.children = [...fragment.children];
    }
  };
  const document = {
    addEventListener() {},
    querySelector(selector) {
      return selector === '.gallery' ? gallery : null;
    },
    getElementById(id) {
      return id === 'dropdownContent' ? dropdown : null;
    },
    createDocumentFragment() {
      return {
        children: [],
        appendChild(child) {
          this.children.push(child);
        }
      };
    },
    createElement() {
      return { dataset: {} };
    }
  };
  const context = vm.createContext({
    URLSearchParams,
    clearTimeout,
    console: { error() {}, warn() {} },
    document,
    fetch: fetchImpl,
    setTimeout,
    window: { location: { reload() { throw new Error('Unexpected page reload'); } } }
  });
  const htmlPath = path.join(__dirname, '..', 'index.html');
  const html = fs.readFileSync(htmlPath, 'utf8');
  const inlineScript = html.match(/<script>([\s\S]*)<\/script>/);
  assert.ok(inlineScript, 'index.html must contain an inline script');
  vm.runInContext(inlineScript[1], context);
  return { context, dropdown, gallery };
}


function jsonResponse(ok, payload) {
  return {
    ok,
    async json() {
      return payload;
    }
  };
}


test('gallery HTTP errors render retry and preserve filter and search', async () => {
  const urls = [];
  const runtime = createRuntime(async url => {
    urls.push(url);
    return jsonResponse(false, { detail: 'Qdrant unavailable' });
  });

  await vm.runInContext('loadGallery(12, "anime", "cielo")', runtime.context);
  assert.match(runtime.gallery.innerHTML, /Error al cargar/);
  assert.match(runtime.gallery.innerHTML, /data-gallery-retry/);

  runtime.context.fetch = async url => {
    urls.push(url);
    return jsonResponse(true, []);
  };
  await vm.runInContext('pendingGalleryRetry()', runtime.context);

  assert.match(runtime.gallery.innerHTML, /No hay coincidencias/);
  assert.deepEqual(urls, [
    '/api/records?limit=12&type=anime&search=cielo',
    '/api/records?limit=12&type=anime&search=cielo'
  ]);
});


test('initial retry reloads types and records without duplicate options', async () => {
  const runtime = createRuntime(async () => jsonResponse(false, { detail: 'Qdrant unavailable' }));

  await vm.runInContext('loadInitialCatalog()', runtime.context);
  assert.match(runtime.gallery.innerHTML, /Error al cargar/);

  runtime.context.fetch = async url => (
    url === '/api/types'
      ? jsonResponse(true, ['anime'])
      : jsonResponse(true, [])
  );
  await vm.runInContext('pendingGalleryRetry()', runtime.context);
  await vm.runInContext('loadInitialCatalog()', runtime.context);

  assert.deepEqual(runtime.dropdown.children.map(item => item.textContent), ['Todos', 'anime']);
  assert.match(runtime.gallery.innerHTML, /No hay coincidencias/);
});


test('similarity retry repeats the selected record and style request', async () => {
  const urls = [];
  const runtime = createRuntime(async url => {
    urls.push(url);
    return jsonResponse(false, { detail: 'Qdrant unavailable' });
  });

  await vm.runInContext('loadSimilarRecords("point/1", 12, "anime")', runtime.context);
  assert.match(runtime.gallery.innerHTML, /Error al cargar/);

  runtime.context.fetch = async url => {
    urls.push(url);
    return jsonResponse(true, []);
  };
  await vm.runInContext('pendingGalleryRetry()', runtime.context);

  assert.deepEqual(urls, [
    '/api/records/point%2F1/similar?limit=12&type=anime',
    '/api/records/point%2F1/similar?limit=12&type=anime'
  ]);
});
