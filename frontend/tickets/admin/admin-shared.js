// Compartido entre las pantallas de /admin/*: sesión, barra de navegación,
// utilidades de formato y el picker de vehículo usado por reportes.html y
// vehiculo.html.

const NAV_ACTIVE = ["rounded-lg", "px-4", "py-2", "text-sm", "font-semibold", "bg-white", "text-brand-dark", "shadow-sm"];
const NAV_INACTIVE = ["rounded-lg", "px-4", "py-2", "text-sm", "font-semibold", "text-white/70", "hover:text-white"];

function formatDate(value) {
  return new Intl.DateTimeFormat("es-MX", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

async function requireSession() {
  const response = await fetch("/api/admin/me");
  if (!response.ok) {
    location.href = "/admin";
    return null;
  }
  const data = await response.json();
  return data.department;
}

async function logout() {
  await fetch("/api/admin/logout", { method: "POST" });
  location.href = "/admin";
}

function renderNav(activeKey, dept) {
  const nav = document.getElementById("adminNav");
  if (!nav) return;
  const links = [
    { key: "dashboard", label: "Dashboard", href: "/admin/dashboard" },
    { key: "tickets", label: "Tickets", href: "/admin/tickets" },
    { key: "configuracion", label: "Configuración", href: "/admin/configuracion" }
  ];
  nav.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 bg-gradient-to-br from-brand-dark to-brand px-4 py-5 sm:px-6 text-white">
      <div class="min-w-0">
        <h2 class="truncate text-lg font-bold">${dept ? dept.name : "Panel"}</h2>
        <div class="mt-0.5 truncate text-xs text-blue-200">${dept ? "Departamento: " + dept.slug : ""}</div>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        ${links.map(l => `<a href="${l.href}" class="${(l.key === activeKey ? NAV_ACTIVE : NAV_INACTIVE).join(" ")}">${l.label}</a>`).join("")}
        <button class="rounded-lg border border-white/30 bg-white/15 px-4 py-2 text-sm font-semibold transition hover:bg-white/25" onclick="logout()">Cerrar sesión</button>
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
    <div class="my-8 w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
      <div class="mb-4 flex items-start justify-between gap-3">
        <h3 id="exportModalTitle" class="text-lg font-bold text-brand-dark">Descargar reporte</h3>
        <button class="text-2xl leading-none text-slate-400 hover:text-slate-600" onclick="closeExportModal()">&times;</button>
      </div>
      <p id="exportModalCount" class="mb-3 text-xs text-slate-500">Elige qué columnas incluir en el Excel.</p>
      <div class="mb-3 flex gap-3 text-xs font-semibold text-brand">
        <button onclick="exportSelectAll(true)" class="underline">Seleccionar todas</button>
        <button onclick="exportSelectAll(false)" class="underline">Ninguna</button>
      </div>
      <div id="exportColumnsList" class="mb-5 max-h-64 space-y-2 overflow-y-auto rounded-lg border border-slate-100 p-3"></div>
      <div id="exportModalError" class="mb-3 hidden text-xs font-semibold text-red-600"></div>
      <button class="w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-bold text-white hover:bg-emerald-700" onclick="downloadExportXlsx()">⬇️ Descargar XLSX</button>
    </div>
  `;
  document.body.appendChild(div);
}

// columns: [{ key, label, format? }] — format(rawValue) es opcional, para
// columnas de fecha u otros valores que no deben ir crudos al Excel.
// rows: array de objetos planos con esas keys.
function openExportModal({ title, columns, rows, filenameBase }) {
  ensureExportModal();
  exportModalState = { columns, rows, filenameBase };
  document.getElementById("exportModalTitle").textContent = title || "Descargar reporte";
  document.getElementById("exportModalCount").textContent = `${rows.length} fila${rows.length === 1 ? "" : "s"} · elige qué columnas incluir`;
  document.getElementById("exportModalError").classList.add("hidden");
  document.getElementById("exportColumnsList").innerHTML = columns.map((c, i) => `
    <label class="flex items-center gap-2 text-sm text-slate-700">
      <input type="checkbox" data-col-index="${i}" checked class="h-4 w-4">
      ${c.label}
    </label>
  `).join("");
  document.getElementById("exportModal").classList.remove("hidden");
  document.getElementById("exportModal").classList.add("flex");
}

function closeExportModal() {
  const el = document.getElementById("exportModal");
  if (el) { el.classList.add("hidden"); el.classList.remove("flex"); }
}

function exportSelectAll(value) {
  document.querySelectorAll("#exportColumnsList input[type=checkbox]").forEach(cb => cb.checked = value);
}

function downloadExportXlsx() {
  if (!exportModalState) return;
  const errorEl = document.getElementById("exportModalError");
  const checked = Array.from(document.querySelectorAll("#exportColumnsList input[type=checkbox]:checked"))
    .map(cb => exportModalState.columns[Number(cb.dataset.colIndex)]);
  if (!checked.length) {
    errorEl.textContent = "Elige al menos una columna.";
    errorEl.classList.remove("hidden");
    return;
  }

  const data = exportModalState.rows.map(row => {
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
