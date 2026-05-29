/* ATE — lógica del frontend: streaming SSE + timeline en vivo + evidencia. */

const $ = (sel) => document.querySelector(sel);
const transcript = $("#transcript");
const promptEl = $("#prompt");
const sendBtn = $("#send-btn");
const composer = $("#composer");

let PASOS = [];
let busy = false;

// --------------------------------------------------------------------------
// Utilidades
// --------------------------------------------------------------------------

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function linkify(text) {
  return escapeHtml(text).replace(
    /(https?:\/\/[^\s,)]+)(?=[\s,).]|$)/g,
    '<a href="$1" target="_blank" rel="noopener">$1</a>'
  );
}

const PILL = {
  ok: ["ok", "ok"],
  sin_datos: ["neutral", "sin datos"],
  sin_candidato: ["neutral", "sin candidato"],
  sin_fuentes: ["neutral", "sin fuentes"],
  no_configurado: ["warn", "no configurado"],
  offline: ["neutral", "offline"],
  error: ["error", "error"],
  error_red: ["error", "error de red"],
  error_http: ["error", "error http"],
  error_parseo: ["error", "error de parseo"],
};
function pill(estado) {
  const [cls, label] = PILL[estado] || ["neutral", estado || "—"];
  return `<span class="pill ${cls}">${escapeHtml(label)}</span>`;
}
function statChips(items) {
  return (
    '<div class="stats">' +
    items
      .map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`)
      .join("") +
    "</div>"
  );
}

// --------------------------------------------------------------------------
// Init
// --------------------------------------------------------------------------

async function init() {
  // Tema persistido
  const saved = localStorage.getItem("ate-theme");
  if (saved) document.documentElement.dataset.theme = saved;
  updateThemeIcon();

  try {
    const cfg = await fetch("/api/config").then((r) => r.json());
    PASOS = cfg.pasos || [];
    renderConfig(cfg);
  } catch (e) {
    PASOS = [
      { node: "planificador", label: "Planificación" },
      { node: "extraccion", label: "Extracción de fuentes" },
      { node: "rag", label: "Planes de gobierno" },
      { node: "contraste", label: "Contraste" },
      { node: "validador", label: "Validación de fuentes" },
      { node: "generador", label: "Síntesis final" },
    ];
  }
  wireEvents();
}

function renderConfig(cfg) {
  $("#st-red").textContent = cfg.offline ? "Offline" : "Online";
  $("#st-llm").textContent = cfg.llm_available ? cfg.llm_provider : "determinista";

  $("#cand-list").innerHTML = (cfg.candidatos || [])
    .map((c) => `<li><span class="nm">${escapeHtml(c.nombre)}</span><span class="pt">${escapeHtml(c.partido)}</span></li>`)
    .join("");

  const ejemplos = [
    "¿Qué propone Iván Cepeda sobre derechos humanos?",
    "¿Qué contratos tiene Sergio Fajardo en SECOP?",
    "Sanciones de Claudia López en la Procuraduría",
    "Financiación de campaña de Paloma Valencia",
  ];
  $("#example-chips").innerHTML = ejemplos
    .map((e) => `<button class="chip" type="button">${escapeHtml(e)}</button>`)
    .join("");
  $("#example-chips")
    .querySelectorAll(".chip")
    .forEach((b) =>
      b.addEventListener("click", () => {
        promptEl.value = b.textContent;
        submit();
      })
    );
}

function wireEvents() {
  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    submit();
  });
  promptEl.addEventListener("input", autosize);
  promptEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  });
  $("#analysis-toggle").addEventListener("change", (e) => {
    document.body.classList.toggle("analysis", e.target.checked);
    $("#analysis-label").textContent = e.target.checked ? "Análisis" : "Solo respuesta";
  });
  $("#theme-btn").addEventListener("click", toggleTheme);
  $("#menu-btn").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
}

function autosize() {
  promptEl.style.height = "auto";
  promptEl.style.height = Math.min(promptEl.scrollHeight, 140) + "px";
}

function toggleTheme() {
  const cur = document.documentElement.dataset.theme === "light" ? "light" : "dark";
  const next = cur === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("ate-theme", next);
  updateThemeIcon();
}
function updateThemeIcon() {
  const dark = document.documentElement.dataset.theme !== "light";
  $("#theme-btn").textContent = dark ? "☾" : "☀";
}

// --------------------------------------------------------------------------
// Flujo de consulta
// --------------------------------------------------------------------------

function submit() {
  const q = promptEl.value.trim();
  if (!q || busy) return;
  $("#empty")?.remove();

  appendUser(q);
  promptEl.value = "";
  autosize();

  const { msg, steps, timerEl, slowEl, answerEl } = appendAssistant();
  setBusy(true);

  const started = performance.now();
  let done = false;
  const timer = setInterval(() => {
    const s = (performance.now() - started) / 1000;
    timerEl.textContent = s.toFixed(1) + "s";
    if (s > 25 && !done) slowEl.classList.add("show");
  }, 100);

  const doneSet = new Set();
  setActive(steps, doneSet);

  const es = new EventSource("/api/ask?q=" + encodeURIComponent(q));

  es.addEventListener("step", (ev) => {
    const d = JSON.parse(ev.data);
    const el = steps[d.node];
    if (el) {
      el.classList.remove("active");
      el.classList.add("done");
      if (d.detail) el.querySelector(".step-detail").textContent = d.detail;
    }
    doneSet.add(d.node);
    setActive(steps, doneSet);
  });

  es.addEventListener("done", (ev) => {
    const d = JSON.parse(ev.data);
    done = true;
    clearInterval(timer);
    Object.values(steps).forEach((el) => {
      el.classList.remove("active");
      el.classList.add("done");
    });
    answerEl.innerHTML = linkify(d.answer || "Sin respuesta.");
    if ((d.llm_info || {}).used_fallback) {
      const note = document.createElement("p");
      note.className = "llm-note";
      note.textContent = "Generada en modo determinista (sin LLM).";
      answerEl.after(note);
    }
    renderEvidence(msg, d.evidence || {});
    msg.classList.remove("live");
    es.close();
    setBusy(false);
    scrollToBottom();
  });

  es.addEventListener("error", () => {
    if (done) return;
    done = true;
    clearInterval(timer);
    answerEl.innerHTML =
      '<span class="pending">Se interrumpió la conexión con el servidor. Verifica que el servidor esté activo e inténtalo de nuevo.</span>';
    msg.classList.remove("live");
    es.close();
    setBusy(false);
  });

  scrollToBottom();
}

function setActive(steps, doneSet) {
  let activated = false;
  for (const p of PASOS) {
    const el = steps[p.node];
    if (!el) continue;
    el.classList.remove("active");
    if (!activated && !doneSet.has(p.node)) {
      el.classList.add("active");
      activated = true;
    }
  }
}

function setBusy(b) {
  busy = b;
  sendBtn.disabled = b;
  sendBtn.classList.toggle("busy", b);
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    transcript.scrollTop = transcript.scrollHeight;
  });
}

// --------------------------------------------------------------------------
// Construcción de mensajes
// --------------------------------------------------------------------------

function appendUser(text) {
  const div = document.createElement("div");
  div.className = "msg user";
  div.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  transcript.appendChild(div);
}

function appendAssistant() {
  const msg = document.createElement("div");
  msg.className = "msg assistant live";

  const stepsHtml = PASOS.map(
    (p) => `
    <div class="step" data-node="${p.node}">
      <div class="step-dot">${p.icon || ""}</div>
      <div class="step-body">
        <div class="step-label">${escapeHtml(p.label)}</div>
        <div class="step-detail"></div>
        <div class="shimmer"></div>
      </div>
    </div>`
  ).join("");

  msg.innerHTML = `
    <div class="who">Agente ATE</div>
    <div class="answer"><span class="pending">Analizando la evidencia…</span></div>
    <div class="analysis-block">
      <div class="timeline">
        <div class="timeline-head">
          <span class="t"><span class="dot-live"></span> Flujo de análisis</span>
          <span class="timer">0.0s</span>
        </div>
        <div class="steps">${stepsHtml}</div>
        <div class="slow-hint">⏳ Consultando fuentes oficiales en vivo; esto puede tardar unos segundos…</div>
      </div>
      <div class="evidence"></div>
    </div>`;

  transcript.appendChild(msg);

  const steps = {};
  msg.querySelectorAll(".step").forEach((el) => (steps[el.dataset.node] = el));
  return {
    msg,
    steps,
    timerEl: msg.querySelector(".timer"),
    slowEl: msg.querySelector(".slow-hint"),
    answerEl: msg.querySelector(".answer"),
  };
}

// --------------------------------------------------------------------------
// Evidencia
// --------------------------------------------------------------------------

function card(idx, title, openByDefault, bodyHtml) {
  return `
    <details class="evi-card" ${openByDefault ? "open" : ""}>
      <summary><span class="idx">${idx}</span> ${escapeHtml(title)} <span class="chev">›</span></summary>
      <div class="evi-body">${bodyHtml}</div>
    </details>`;
}

function renderEvidence(msg, ev) {
  const box = msg.querySelector(".evidence");
  let html = "";

  if (ev.plan) {
    const p = ev.plan;
    const cand = p.candidato ? p.candidato.nombre_canonico : "No detectado";
    html += card(
      "①",
      "Planificación",
      false,
      `<div class="row"><b>Intención:</b> ${escapeHtml(p.intencion)} &nbsp;·&nbsp; <b>Candidato:</b> ${escapeHtml(cand)}</div>
       <div class="row"><b>Tools:</b> ${escapeHtml((p.tools || []).join(", ") || "ninguna")}</div>
       <div class="cap">${escapeHtml(p.razonamiento || "")}</div>`
    );
  }

  if (ev.extraccion) {
    const rs = ev.extraccion.resultados || [];
    const body =
      rs.length === 0
        ? '<div class="cap">No se invocaron tools para esta pregunta.</div>'
        : rs
            .map((r) => {
              const urls = (r.urls_oficiales || [])
                .map((u) => `<div class="row"><a href="${escapeHtml(u)}" target="_blank" rel="noopener">${escapeHtml(u)}</a></div>`)
                .join("");
              return `<div class="row"><b>${escapeHtml(r.fuente)}</b> ${pill(r.estado)} <span class="cap">${r.total_resultados} resultado(s)</span></div>
                      ${r.mensaje ? `<div class="cap">${escapeHtml(r.mensaje)}</div>` : ""}${urls}`;
            })
            .join('<div style="height:8px"></div>');
    html += card("②", `Extracción de fuentes (${rs.length})`, false, body);
  }

  if (ev.rag) {
    const r = ev.rag;
    const pas = (r.pasajes || [])
      .map(
        (p) =>
          `<blockquote>${escapeHtml(p.texto)}</blockquote><div class="cap">— ${escapeHtml(p.candidato_nombre)}, pág. ${p.pagina} (score ${Number(p.score).toFixed(4)})</div>`
      )
      .join("");
    html += card(
      "③",
      "Planes de gobierno (RAG)",
      false,
      `<div class="row">${pill(r.estado)}</div>${r.mensaje ? `<div class="cap">${escapeHtml(r.mensaje)}</div>` : ""}${pas}`
    );
  }

  if (ev.contraste) {
    const c = ev.contraste;
    const incs = (c.inconsistencias || [])
      .map(
        (i) =>
          `<div class="incons"><span class="tipo">${escapeHtml(i.tipo)}</span><div>${escapeHtml(i.descripcion)}</div>${i.evidencia_dato ? `<div class="cap">Dato: ${escapeHtml(i.evidencia_dato)}</div>` : ""}${(i.fuentes || []).length ? `<div class="cap">Fuentes: ${escapeHtml(i.fuentes.join(", "))}</div>` : ""}</div>`
      )
      .join("");
    const okMsg =
      c.estado === "ok" && (c.inconsistencias || []).length === 0
        ? '<div class="cap" style="color:var(--ok)">Sin inconsistencias entre propuestas y datos reales.</div>'
        : "";
    html += card(
      "④",
      "Contraste",
      true,
      `<div class="row">${pill(c.estado)}</div>${c.mensaje ? `<div class="cap">${escapeHtml(c.mensaje)}</div>` : ""}
       ${statChips([
         ["Propuestas", c.n_propuestas_analizadas],
         ["Contratos", c.n_contratos_analizados],
         ["Sanciones", c.n_sanciones_analizadas],
         ["Inconsist.", (c.inconsistencias || []).length],
       ])}${incs}${okMsg}`
    );
  }

  if (ev.validacion) {
    const v = ev.validacion;
    const fuentes = (v.fuentes_validadas || [])
      .map(
        (f) =>
          `<div class="row">${f.es_oficial ? "✅" : "⚠️"} <a href="${escapeHtml(f.url)}" target="_blank" rel="noopener">${escapeHtml(f.url)}</a> — <code>${escapeHtml(f.dominio_detectado)}</code></div>`
      )
      .join("");
    html += card(
      "⑤",
      "Validación de fuentes",
      false,
      statChips([
        ["Oficiales", v.fuentes_oficiales],
        ["No oficiales", v.fuentes_no_oficiales],
        ["Inaccesibles", v.fuentes_inaccesibles],
      ]) + fuentes
    );
  }

  box.innerHTML = html;
}

init();
