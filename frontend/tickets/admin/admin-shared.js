// Compartido entre las pantallas de /admin/*: sesión, barra de navegación,
// utilidades de formato y el picker de vehículo usado por reportes.html y
// vehiculo.html.

const NAV_ACTIVE = ["rounded-lg", "px-4", "py-2", "text-sm", "font-semibold", "bg-white", "text-brand-dark", "shadow-sm"];
const NAV_INACTIVE = ["rounded-lg", "px-4", "py-2", "text-sm", "font-semibold", "text-white/70", "hover:text-white"];

function formatDate(value) {
  return new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

// Escapa texto de origen no confiable (lo escribe el solicitante público,
// sin login) antes de insertarlo con innerHTML — sin esto, un nombre o
// descripción con HTML/JS se ejecutaría en la sesión del admin que abre el
// ticket. Usar siempre para solicitante_nombre, solicitante_email, campos.*
// y comentarios de observación.
function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// loginPath: por defecto "/admin" (Flota). Otros sistemas de tickets (p.ej.
// Talento AM en /talento/admin) pasan su propia ruta de login — ahí mismo
// vive el panel, igual que "/admin" ya es tanto login como base de Flota.
// expectedSlug (opcional): todos los sistemas comparten la misma cookie de
// sesión de Flask (un solo dominio, una sola sesión "activa" a la vez) —
// sin esto, si quedó una sesión de OTRO departamento activa en este
// navegador (p.ej. no cerraste sesión de Flota antes de entrar a Talento
// AM), esta página cargaría con los tickets/tipos del departamento
// equivocado. Si se pasa, se verifica contra department.slug y, si no
// coincide, se cierra esa sesión ajena y se manda a loginPath en vez de
// dejar pasar datos de otro sistema.
async function requireSession(loginPath = "/admin", expectedSlug = null) {
  const response = await fetch("/api/admin/me");
  if (!response.ok) {
    location.href = loginPath;
    return null;
  }
  const data = await response.json();
  if (expectedSlug && data.department?.slug !== expectedSlug) {
    await fetch("/api/admin/logout", { method: "POST" });
    location.href = loginPath;
    return null;
  }
  return data.department;
}

async function logout(loginPath = "/admin") {
  await fetch("/api/admin/logout", { method: "POST" });
  location.href = loginPath;
}

// basePath: por defecto "/admin" (Flota) — las páginas de otro sistema de
// tickets (p.ej. Talento AM) pasan su propia base ("/talento/admin") para
// que los links del nav y el botón de salir apunten a su propio panel.
// navGradient: par de paradas de degradado para la barra superior — por
// defecto el azul de Flota (usa los colores "brand"/"brand-dark" que cada
// página define en su propio tailwind.config); otro sistema de tickets
// puede pasar cualquier par de clases de color de Tailwind (p.ej.
// "from-rose-600 to-rose-700") para diferenciarse a simple vista.
function renderNav(activeKey, dept, basePath = "/admin", navGradient = "from-brand-dark to-brand") {
  const nav = document.getElementById("adminNav");
  if (!nav) return;
  const links = [
    { key: "dashboard", label: "Dashboard", href: `${basePath}/dashboard` },
    { key: "tickets", label: "Tickets", href: `${basePath}/tickets` },
    { key: "configuracion", label: "Configuración", href: `${basePath}/configuracion` }
  ];
  nav.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 bg-gradient-to-br ${navGradient} px-4 py-5 sm:px-6 text-white">
      <div class="flex min-w-0 items-center gap-3">
        <img src="/tickets/assets/logo-am.png" alt="AM" class="h-8 w-auto shrink-0">
        <h2 class="truncate text-lg font-bold">Sistema de tickets de ${dept ? dept.name : "Panel"}</h2>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        ${links.map(l => `<a href="${l.href}" class="${(l.key === activeKey ? NAV_ACTIVE : NAV_INACTIVE).join(" ")}">${l.label}</a>`).join("")}
        <button class="rounded-lg border border-white/30 bg-white/15 px-4 py-2 text-sm font-semibold transition hover:bg-white/25" onclick="logout('${basePath}')">Cerrar sesión</button>
      </div>
    </div>
  `;
}

function showQrModal(title, imgSrc, codigo) {
  document.getElementById("qrModalTitle").textContent = title;
  document.getElementById("qrModalImg").src = imgSrc;
  const download = document.getElementById("qrModalDownload");
  download.href = imgSrc;
  download.download = `qr-${codigo}.png`;
  document.getElementById("qrModal").classList.remove("hidden");
  document.getElementById("qrModal").classList.add("flex");
}

function closeQrModal() {
  document.getElementById("qrModal").classList.add("hidden");
  document.getElementById("qrModal").classList.remove("flex");
}

// Lista buscable de vehículos donde cada fila enlaza a otra pantalla
// (reportes.html o vehiculo.html deciden el destino vía hrefFor).
function initVehiclePicker({ entities, searchEl, listEl, countEl, hrefFor }) {
  function render() {
    const query = (searchEl.value || "").trim().toLowerCase();
    const filtered = !query ? entities : entities.filter(e => {
      const a = e.atributos || {};
      return [e.codigo, a.marca, a.modelo, a.departamento, a.tipo].join(" ").toLowerCase().includes(query);
    });
    if (countEl) countEl.textContent = `${filtered.length} de ${entities.length} vehículos`;
    if (!filtered.length) {
      listEl.innerHTML = `<div class="col-span-full py-10 text-center text-slate-400">Sin vehículos que coincidan.</div>`;
      return;
    }
    listEl.innerHTML = filtered.map(e => {
      const a = e.atributos || {};
      return `
        <a href="${hrefFor(e)}" class="block rounded-xl bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
          <div class="flex items-center justify-between gap-2">
            <div class="font-mono text-sm font-bold text-brand-dark">${e.codigo}</div>
            <span class="text-xs text-slate-400">${a.estado || ""}</span>
          </div>
          <div class="mt-1 text-sm text-slate-600">${[a.marca, a.modelo].filter(Boolean).join(" ") || e.nombre || "—"}</div>
          <div class="mt-1 text-xs text-slate-400">${a.departamento || ""}</div>
        </a>
      `;
    }).join("");
  }
  searchEl.addEventListener("input", render);
  render();
}

// Exportar a Excel con selector de columnas — reutilizable en cualquier
// pantalla de consulta. Arma su propio modal en el DOM la primera vez que se
// usa (así no hay que repetir el HTML en cada página) usando la librería
// SheetJS, que cada página debe cargar por su cuenta desde el CDN.
let exportModalState = null;

function ensureExportModal() {
  if (document.getElementById("exportModal")) return;
  const div = document.createElement("div");
  div.id = "exportModal";
  div.className = "fixed inset-0 z-50 hidden items-start justify-center overflow-y-auto bg-black/50 p-5";
  div.innerHTML = `
    <div class="my-8 w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl">
      <div class="mb-4 flex items-start justify-between gap-3">
        <h3 id="exportModalTitle" class="text-lg font-bold text-brand-dark">Descargar reporte</h3>
        <button class="text-2xl leading-none text-slate-400 hover:text-slate-600" onclick="closeExportModal()">&times;</button>
      </div>
      <p id="exportModalCount" class="mb-3 text-xs text-slate-500">Elige qué columnas incluir en el Excel.</p>

      <div id="exportDateRangeWrap" class="mb-4 hidden">
        <div class="mb-1.5 flex items-center justify-between">
          <span class="text-xs font-bold uppercase tracking-wide text-slate-400">Rango de fechas</span>
          <button onclick="exportClearDateRange()" class="text-xs font-semibold text-brand underline">Todas las fechas</button>
        </div>
        <div class="flex flex-wrap gap-2">
          <input id="exportFechaDesde" type="date" class="flex-1 rounded-lg border-2 border-slate-200 px-3 py-2 text-sm" onchange="onExportDateRangeChange()">
          <input id="exportFechaHasta" type="date" class="flex-1 rounded-lg border-2 border-slate-200 px-3 py-2 text-sm" onchange="onExportDateRangeChange()">
        </div>
      </div>

      <div class="mb-3 flex gap-3 text-xs font-semibold text-brand">
        <button onclick="exportSelectAll(true)" class="underline">Seleccionar todas</button>
        <button onclick="exportSelectAll(false)" class="underline">Ninguna</button>
      </div>
      <div id="exportColumnsList" class="mb-5 max-h-40 space-y-2 overflow-y-auto rounded-lg border border-slate-100 p-3"></div>

      <div class="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Vista previa</div>
      <div class="mb-5 overflow-x-auto rounded-lg border border-slate-100">
        <table class="w-full text-left text-xs">
          <thead id="exportPreviewHead" class="bg-slate-50 text-slate-500"></thead>
          <tbody id="exportPreviewBody"></tbody>
        </table>
      </div>

      <div id="exportModalError" class="mb-3 hidden text-xs font-semibold text-red-600"></div>
      <button class="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-bold text-white hover:bg-emerald-700" onclick="downloadExportXlsx()">⬇️ Descargar XLSX</button>
    </div>
  `;
  document.body.appendChild(div);
}

// columns: [{ key, label, format? }] — format(rawValue) es opcional, para
// columnas de fecha u otros valores que no deben ir crudos al Excel.
// rows: array de objetos planos con esas keys. dateKey (opcional): key de
// `rows` con una fecha ISO cruda — si se manda, aparece el filtro de rango
// de fechas; si no, esa sección se oculta (p. ej. Inventario no tiene una
// fecha natural por la que filtrar).
function openExportModal({ title, columns, rows, filenameBase, dateKey }) {
  ensureExportModal();
  exportModalState = { columns, rows, filenameBase, dateKey, fechaDesde: null, fechaHasta: null };
  document.getElementById("exportModalTitle").textContent = title || "Descargar reporte";
  document.getElementById("exportModalError").classList.add("hidden");

  document.getElementById("exportDateRangeWrap").classList.toggle("hidden", !dateKey);
  document.getElementById("exportFechaDesde").value = "";
  document.getElementById("exportFechaHasta").value = "";

  document.getElementById("exportColumnsList").innerHTML = columns.map((c, i) => `
    <label class="flex items-center gap-2 text-sm text-slate-700">
      <input type="checkbox" data-col-index="${i}" checked class="h-4 w-4" onchange="renderExportPreview()">
      ${c.label}
    </label>
  `).join("");
  updateExportCount();
  renderExportPreview();
  document.getElementById("exportModal").classList.remove("hidden");
  document.getElementById("exportModal").classList.add("flex");
}

function closeExportModal() {
  const el = document.getElementById("exportModal");
  if (el) { el.classList.add("hidden"); el.classList.remove("flex"); }
}

function exportSelectAll(value) {
  document.querySelectorAll("#exportColumnsList input[type=checkbox]").forEach(cb => cb.checked = value);
  renderExportPreview();
}

function onExportDateRangeChange() {
  if (!exportModalState) return;
  exportModalState.fechaDesde = document.getElementById("exportFechaDesde").value || null;
  exportModalState.fechaHasta = document.getElementById("exportFechaHasta").value || null;
  updateExportCount();
  renderExportPreview();
}

function exportClearDateRange() {
  document.getElementById("exportFechaDesde").value = "";
  document.getElementById("exportFechaHasta").value = "";
  onExportDateRangeChange();
}

function exportFilteredRows() {
  if (!exportModalState) return [];
  const { rows, dateKey, fechaDesde, fechaHasta } = exportModalState;
  if (!dateKey || (!fechaDesde && !fechaHasta)) return rows;
  return rows.filter(row => {
    const raw = row[dateKey];
    if (!raw) return false;
    const t = new Date(raw).getTime();
    if (fechaDesde && t < new Date(fechaDesde + "T00:00:00").getTime()) return false;
    if (fechaHasta && t > new Date(fechaHasta + "T23:59:59").getTime()) return false;
    return true;
  });
}

function updateExportCount() {
  const total = exportModalState.rows.length;
  const filtered = exportFilteredRows().length;
  document.getElementById("exportModalCount").textContent = filtered === total
    ? `${total} fila${total === 1 ? "" : "s"} · elige qué columnas incluir`
    : `${filtered} de ${total} filas (rango de fechas aplicado) · elige qué columnas incluir`;
}

function checkedExportColumns() {
  return Array.from(document.querySelectorAll("#exportColumnsList input[type=checkbox]:checked"))
    .map(cb => exportModalState.columns[Number(cb.dataset.colIndex)]);
}

const EXPORT_PREVIEW_ROWS = 5;

function renderExportPreview() {
  if (!exportModalState) return;
  const checked = checkedExportColumns();
  const head = document.getElementById("exportPreviewHead");
  const body = document.getElementById("exportPreviewBody");
  if (!checked.length) {
    head.innerHTML = "";
    body.innerHTML = `<tr><td class="px-3 py-4 text-center text-slate-400">Elige al menos una columna.</td></tr>`;
    return;
  }
  head.innerHTML = `<tr>${checked.map(c => `<th class="whitespace-nowrap px-3 py-2 font-bold">${c.label}</th>`).join("")}</tr>`;

  const filtradas = exportFilteredRows();
  const muestra = filtradas.slice(0, EXPORT_PREVIEW_ROWS);
  if (!muestra.length) {
    body.innerHTML = `<tr><td colspan="${checked.length}" class="px-3 py-4 text-center text-slate-400">Sin filas para este rango.</td></tr>`;
    return;
  }
  const filas = muestra.map(row => `
    <tr class="border-t border-slate-100">
      ${checked.map(c => {
        const raw = row[c.key] ?? "";
        const value = c.format ? c.format(raw) : raw;
        return `<td class="whitespace-nowrap px-3 py-2 text-slate-600">${value === "" || value === null || value === undefined ? "—" : value}</td>`;
      }).join("")}
    </tr>
  `);
  if (filtradas.length > EXPORT_PREVIEW_ROWS) {
    const resto = filtradas.length - EXPORT_PREVIEW_ROWS;
    filas.push(`<tr class="border-t border-slate-100"><td colspan="${checked.length}" class="px-3 py-2 text-center text-slate-400">… y ${resto} fila${resto === 1 ? "" : "s"} más</td></tr>`);
  }
  body.innerHTML = filas.join("");
}

function downloadExportXlsx() {
  if (!exportModalState) return;
  const errorEl = document.getElementById("exportModalError");
  const checked = checkedExportColumns();
  if (!checked.length) {
    errorEl.textContent = "Elige al menos una columna.";
    errorEl.classList.remove("hidden");
    return;
  }
  const filasFiltradas = exportFilteredRows();
  if (!filasFiltradas.length) {
    errorEl.textContent = "No hay filas para ese rango de fechas.";
    errorEl.classList.remove("hidden");
    return;
  }

  const data = filasFiltradas.map(row => {
    const obj = {};
    checked.forEach(c => {
      const raw = row[c.key] ?? "";
      obj[c.label] = c.format ? c.format(raw) : raw;
    });
    return obj;
  });
  const ws = XLSX.utils.json_to_sheet(data);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Datos");
  const fecha = new Date().toISOString().slice(0, 10);
  XLSX.writeFile(wb, `${exportModalState.filenameBase}-${fecha}.xlsx`);
  closeExportModal();
}
