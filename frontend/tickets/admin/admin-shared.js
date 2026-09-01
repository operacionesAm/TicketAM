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
