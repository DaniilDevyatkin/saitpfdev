/* Платформа «Шесть» — клиентская логика: часы, консоль согласования,
   периодическая проверка статусов. Без зависимостей. */

(() => {
  "use strict";

  const API = "/svc/approval/api/v1";
  const WORKSPACE = "portfolio";
  const USER = "usr_daniil";
  const ACTIONS = "approval:read,approval:create,approval:decide,approval:cancel";
  const headers = {
    "X-Workspace-ID": WORKSPACE,
    "X-User-ID": USER,
    "X-Actions": ACTIONS,
    "Content-Type": "application/json",
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  /* Часы в пульте — UTC, как и весь журнал платформы. */
  const clock = $("#pult-clock");
  const tick = () => {
    if (!clock) return;
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    clock.textContent = `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} UTC`;
  };
  tick();
  setInterval(tick, 1000);

  /* ── Консоль согласования ─────────────────────────────────────── */

  const listEl = $("#req-list");
  const countEl = $("#req-count");
  const form = $("#review-form");
  const formStatus = $("#form-status");
  const STATUS_RU = {
    pending: "на согласовании",
    approved: "согласовано",
    rejected: "отклонено",
    cancelled: "отменено",
  };

  function requestCard(r) {
    const created = new Date(r.created_at + "Z").toLocaleString("ru-RU", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
    const canDecide = r.status === "pending";
    return `
      <article class="req">
        <div class="req__top">
          <span class="req__title">${esc(r.title)}</span>
          <span class="req__status" data-s="${r.status}">${STATUS_RU[r.status] || r.status}</span>
        </div>
        <div class="req__meta">${esc(r.source_type)} · ${esc(r.source_id)} · ${created} · ${esc(r.created_by)}</div>
        ${r.description ? `<div class="req__meta" style="margin-top:6px;color:var(--ink-soft)">${esc(r.description)}</div>` : ""}
        <div class="req__actions">
          ${
            canDecide
              ? `<button class="btn btn--sm" data-act="approve" data-id="${r.id}">Согласовать</button>
                 <button class="btn btn--sm btn--ghost" data-act="reject" data-id="${r.id}">Отклонить</button>`
              : ""
          }
          <span class="hint-line" style="align-self:center">${r.id.slice(0, 8)}…</span>
        </div>
      </article>`;
  }

  async function loadRequests() {
    if (!listEl) return;
    try {
      const res = await fetch(`${API}/workspaces/${WORKSPACE}/approval-requests?offset=0&limit=20`, {
        headers, cache: "no-store",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const items = data.items || data.results || (Array.isArray(data) ? data : []);
      if (countEl) countEl.textContent = String(items.length);
      listEl.innerHTML = items.length
        ? items.map(requestCard).join("")
        : `<div class="empty">Заявок пока нет. Создайте первую слева — она появится здесь
             через <span class="mono">GET /api/v1/workspaces/portfolio/approval-requests</span>.</div>`;
    } catch (err) {
      listEl.innerHTML = `<div class="empty">Сервис согласования не ответил: <span class="mono">${esc(err.message)}</span>.
        Проверьте <span class="mono">/svc/approval/health</span>.</div>`;
    }
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const [repo, slug] = $("#f-project").value.split("|");
      const title = $("#f-title").value.trim();
      if (!title) {
        formStatus.textContent = "Нужен заголовок заявки.";
        return;
      }
      const submit = $("#f-submit");
      submit.disabled = true;
      formStatus.textContent = "Отправляем…";
      try {
        const res = await fetch(`${API}/workspaces/${WORKSPACE}/approval-requests`, {
          method: "POST",
          headers: { ...headers, "Idempotency-Key": `portal-${Date.now()}-${Math.random().toString(36).slice(2, 8)}` },
          body: JSON.stringify({
            sourceType: "publication",
            sourceId: repo,
            title,
            description: $("#f-desc").value.trim() || `Публикация проекта ${slug}`,
            reviewerUserIds: [USER],
          }),
        });
        if (!res.ok) {
          const body = await res.text();
          throw new Error(`${res.status}: ${body.slice(0, 160)}`);
        }
        form.reset();
        formStatus.textContent = "Заявка создана — она в очереди справа.";
        await loadRequests();
      } catch (err) {
        formStatus.textContent = `Не получилось: ${err.message}`;
      } finally {
        submit.disabled = false;
      }
    });
  }

  if (listEl) {
    listEl.addEventListener("click", async (e) => {
      const btn = e.target.closest("button[data-act]");
      if (!btn) return;
      const { act, id } = btn.dataset;
      btn.disabled = true;
      try {
        const res = await fetch(`${API}/workspaces/${WORKSPACE}/approval-requests/${id}/${act}`, {
          method: "POST",
          headers,
          body: JSON.stringify(
            act === "approve" ? { comment: "Согласовано в консоли платформы" }
                              : { reason: "Отклонено в консоли платформы" }
          ),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        await loadRequests();
      } catch (err) {
        btn.disabled = false;
        listEl.insertAdjacentHTML(
          "afterbegin",
          `<div class="empty">Действие не прошло: <span class="mono">${esc(err.message)}</span></div>`
        );
      }
    });
    loadRequests();
  }

  /* ── Обновление статусов без перезагрузки ─────────────────────── */

  async function refreshStatus() {
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const live = data.components.filter((c) => c.ok).length;
      const dot = $(".topbar__status .dot");
      if (dot) dot.classList.toggle("dot--off", live !== data.components.length);

      // Счётчик в шапке считает проекты, а не компоненты: 6 из 6 — это про реестр.
      const catalogRes = await fetch("/api/catalog", { cache: "no-store" });
      if (catalogRes.ok) {
        const catalog = await catalogRes.json();
        const online = catalog.projects.filter((p) => p.live).length;
        const total = catalog.projects.length;
        $("#live-counter") && ($("#live-counter").textContent = `${online}/${total} в сети`);
        const pultLive = $("#pult-live");
        if (pultLive) pultLive.textContent = `${online}/${total}`;
      }
      const body = $("#status-body");
      if (body) {
        body.innerHTML = data.components
          .map(
            (c) => `<tr>
              <td>${esc(c.name)}</td>
              <td class="mono">${esc(c.path)}</td>
              <td class="mono">${esc(c.role)}</td>
              <td class="mono">${c.ms === null ? "—" : c.ms + " мс"}</td>
              <td><span class="state ${c.ok ? "state--ok" : "state--off"}">
                <span class="dot ${c.ok ? "" : "dot--off"}"></span>${c.ok ? "работает" : "недоступен"}
              </span></td>
            </tr>`
          )
          .join("");
      }
      const st = $("#status-time");
      if (st) {
        st.textContent = "проверено " + new Date().toLocaleTimeString("ru-RU");
      }
    } catch (_) {
      /* тихо: следующая попытка через 20 секунд */
    }
  }
  if (document.querySelector("#status-body")) {
    setInterval(refreshStatus, 20000);
  }
})();
