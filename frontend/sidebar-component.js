// Construye una única barra lateral configurable para el catálogo y la página informativa.
window.renderSidebar = function(options = {}) {
  const {
    targetId = 'sidebarRoot',
    showSearch = true,
    showFilter = true,
    showExportHistory = false,
    activePage = 'home'
  } = options;

  const container = document.getElementById(targetId);
  if (!container) return;

  // Las clases activas dependen de la página, no de la sesión administrativa.
  const homeActiveClass = activePage === 'home' ? 'nav-card--active' : '';
  const aboutActiveClass = activePage === 'about' ? 'nav-link--active' : '';

  // Las secciones opcionales no se insertan, evitando controles inertes en otras vistas.
  container.innerHTML = `
    <div class="sidebar__top">
      <a class="brand" href="/" aria-label="Volver al catálogo inicial">
        <div class="brand__mark">✦</div>
        <div class="brand__text">
          <strong>ArtSim</strong>
        </div>
      </a>
    </div>

    ${showSearch ? `
      <div class="search">
        <label for="searchInput" class="sr-only">Buscar imágenes</label>
        <input id="searchInput" type="search" placeholder="Buscar imágenes..." />
      </div>
    ` : ''}

    ${showFilter ? `
      <section class="sidebar-section">
        <p class="sidebar-section__label">FILTRO DE TIPO</p>
        <details class="dropdown">
          <summary>
            <span id="dropdownSelected">Todos</span>
            <span>⌄</span>
          </summary>
          <div class="dropdown__content" id="dropdownContent"></div>
        </details>
      </section>
    ` : ''}

    <section class="sidebar-section">
      <p class="sidebar-section__label">NAVEGACIÓN</p>

      ${showExportHistory ? `
        <details class="report-history admin-only" id="reportHistory">
          <summary class="nav-card ${homeActiveClass}">
            <span class="nav-card__icon">↺</span>
            <span class="nav-card__text">
              <strong>Historial de archivos exportados</strong>
            </span>
            <span class="nav-card__badge" id="reportHistoryCount">0</span>
          </summary>
          <div class="report-history__content">
            <div class="report-history__status" id="reportHistoryStatus">Cargando historial...</div>
            <div class="report-history__list" id="reportHistoryList"></div>
          </div>
        </details>
      ` : ''}

      <a class="nav-link" href="/admin">
        <span>Permisos de administrador</span>
        <span>›</span>
      </a>

      <a class="nav-link ${aboutActiveClass}" href="/about">
        <span>Acerca de nosotros</span>
        <span>›</span>
      </a>
    </section>

    <div class="sidebar__footer admin-only">
      <div class="user-card">
        <div class="user-card__avatar">AD</div>
        <div class="user-card__info">
          <strong>Administrador</strong>
          <span>admin@artsim.io</span>
        </div>
        <span class="logout" role="button" title="Cerrar sesión">↗</span>
      </div>
    </div>
  `;
};
