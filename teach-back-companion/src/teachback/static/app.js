// Teach-Back Companion front end. All server data is rendered with textContent (never innerHTML).
"use strict";

const state = { plans: [], plan: null, view: "health", level: "standard", lastTopic: null, chat: [], fs: 18 };
const main = document.getElementById("main");

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const k of kids.flat()) {
    if (k === null || k === undefined || k === false) continue;
    n.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return n;
}

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "Something went wrong. Please try again.");
  return body;
}
const post = (path, data) => api(path, { method: "POST", body: JSON.stringify(data) });

function sourceTag(kind) {
  const map = { care_plan: ["plan", "From your care plan"], education: ["edu", "General information"],
                companion: ["companion", "Companion"], help: ["help", "Get help"] };
  const [cls, label] = map[kind] || map.companion;
  return el("span", { class: `source ${cls}` }, label);
}

function setView(view) {
  state.view = view;
  location.hash = state.plan ? `#/${state.plan.id}/${view}` : "#/";
  document.querySelectorAll("#tabs button").forEach(b =>
    b.setAttribute("aria-current", b.dataset.view === view ? "page" : "false"));
  render();
  main.focus();
}

function render() {
  main.replaceChildren();
  if (!state.plan) return renderLanding();
  const views = { health: renderHealth, medicines: renderMedicines, plan: renderPlan, check: renderCheck,
                  ask: renderAsk, reminders: renderReminders, staff: renderStaff };
  (views[state.view] || renderHealth)();
}

// ---------------------------------------------------------------- landing
function renderLanding() {
  main.append(
    el("h1", {}, "Understand your care plan, in your own words"),
    el("p", {}, "This companion explains the instructions your care team gave you, lets you ask questions, and helps you check your understanding by explaining things back in your own words (teach-back)."),
    el("p", { class: "notice" }, "This is a demonstration with fictional patients. It is not connected to any health record, does not give medical advice, and does not make decisions about your care."),
    el("h2", {}, "Choose a demo patient"),
    el("div", { class: "grid" }, state.plans.map(p => el("button", {
      type: "button", class: "card patient-card", onclick: () => choosePlan(p.id) },
      el("strong", {}, `${p.name} (fictional)`), `${p.diagnoses.join(", ")} · age ${p.age}`))),
  );
}

async function choosePlan(id, view = "health") {
  state.plan = await api(`/api/plans/${id}`);
  state.chat = []; state.lastTopic = null;
  document.getElementById("patient-tag").textContent = `${state.plan.patient.display_name} (fictional demo patient)`;
  document.getElementById("tabs").hidden = false;
  const team = document.getElementById("help-team");
  team.replaceChildren(...state.plan.care_team.map(c => el("li", {}, `${c.role}: ${c.contact}`)));
  setView(view);
}

// ---------------------------------------------------------------- my health
async function renderHealth() {
  const p = state.plan;
  main.append(el("h1", {}, "My health"), el("p", { class: "notice" }, p.notice));
  for (const d of p.diagnoses) {
    const card = el("section", { class: "card", "aria-labelledby": `dx-${d.id}` });
    card.append(el("h2", { id: `dx-${d.id}` }, d.name),
      sourceTag("care_plan"), el("p", {}, d.documented_note));
    const topic = await api(`/api/education/${d.education_topic}`);
    const body = el("div", { "aria-live": "polite" });
    const levelBtns = ["simple", "standard", "detailed"].map(lv => el("button", {
      type: "button", "aria-pressed": String(lv === state.level),
      onclick: () => { state.level = lv; render(); } }, { simple: "Simple", standard: "Standard", detailed: "More detail" }[lv]));
    body.append(sourceTag("education"), el("p", {}, topic.levels[state.level]),
      el("h3", {}, "Key points"), el("ul", { class: "clean" }, topic.key_points.map(k => el("li", {}, k))),
      el("h3", {}, "Questions you could ask your care team"),
      el("ul", { class: "clean" }, topic.questions_to_ask.map(k => el("li", {}, k))),
      el("p", { class: "muted" }, "Learn more: ", ...topic.sources.map(s => el("a", { href: s.url, rel: "noopener noreferrer", target: "_blank" }, s.title))));
    card.append(el("div", { class: "levels", role: "group", "aria-label": "Explanation level" }, levelBtns), body);
    main.append(card);
  }
}

// ---------------------------------------------------------------- items
function itemCard(i, { showStatus = true } = {}) {
  const card = el("section", { class: "card", "aria-labelledby": `it-${i.id}` },
    el("h2", { id: `it-${i.id}` }, i.title),
    el("div", { class: "pair" },
      el("div", { class: "orig" }, sourceTag("care_plan"), el("p", {}, i.original)),
      el("div", { class: "plainv" }, el("span", { class: "source edu" }, "In plain words"), el("p", {}, i.plain))),
  );
  if (i.when) {
    const d = new Date(i.when);
    card.append(el("p", {}, el("strong", {}, "Planned date: "),
      d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }) +
      (i.has_time ? ` at ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}` : "")));
  }
  if (showStatus) {
    const statusLabel = { not_started: "Not reviewed yet", reviewed: "Reviewed", done: "Done" };
    const pill = el("span", { class: `pill ${i.status}` }, statusLabel[i.status]);
    const setStatus = async s => { await post(`/api/plans/${state.plan.id}/tasks/${i.id}`, { status: s }); i.status = s; render(); };
    card.append(el("div", { class: "status-row" }, pill,
      el("button", { type: "button", onclick: () => setStatus("reviewed") }, "I've read this"),
      i.task ? el("button", { type: "button", onclick: () => setStatus("done") }, "Mark done") : null,
      el("button", { type: "button", onclick: () => { state.checkItem = i.id; setView("check"); } }, "Explain it back"),
      i.task ? el("button", { type: "button", onclick: () => { state.remindItem = i.id; setView("reminders"); } }, "Set a reminder") : null));
  }
  return card;
}

function renderMedicines() {
  const meds = state.plan.items.filter(i => i.kind === "medication");
  main.append(el("h1", {}, "My medicines"),
    el("p", {}, "Each medicine shows the exact instructions from your care plan next to a plain-language version. The plain version never changes your dose or timing."),
    el("p", { class: "notice" }, "Questions about changing, stopping or missing a dose? Ask your pharmacist or care team. This companion will not advise on that."),
    ...meds.map(i => itemCard(i)));
}

function renderPlan() {
  const order = ["warning", "instruction", "appointment", "test", "medication"];
  const heads = { warning: "Warning signs", instruction: "Instructions", appointment: "Appointments", test: "Tests", medication: "Medicines" };
  main.append(el("h1", {}, "My care plan"),
    el("p", {}, "Original instructions from your care team, with a plain-language version beside each. If anything is missing or unclear, ask your care team rather than guessing."));
  for (const k of order) {
    const items = state.plan.items.filter(i => i.kind === k);
    if (items.length) main.append(el("h2", {}, heads[k]), ...items.map(i => itemCard(i)));
  }
}

// ---------------------------------------------------------------- teach-back
function renderCheck() {
  const items = state.plan.items;
  const sel = el("select", { id: "tb-item" }, items.map(i => el("option", { value: i.id, selected: i.id === state.checkItem }, i.title)));
  const box = el("textarea", { id: "tb-text", "aria-describedby": "tb-hint" });
  const result = el("div", { "aria-live": "polite" });
  const showItem = el("div");
  const refresh = () => {
    const i = items.find(x => x.id === sel.value);
    state.checkItem = i.id;
    showItem.replaceChildren(el("details", {}, el("summary", {}, "Read the instruction first"),
      el("blockquote", {}, i.original), el("p", {}, i.plain)));
  };
  sel.addEventListener("change", () => { refresh(); result.replaceChildren(); });
  refresh();
  const submit = async () => {
    result.replaceChildren(el("p", { class: "muted" }, "Checking…"));
    try {
      const r = await post(`/api/plans/${state.plan.id}/teachback`, { item_id: sel.value, text: box.value });
      result.replaceChildren(teachBackResult(r));
    } catch (e) { result.replaceChildren(el("p", { class: "result-concern" }, e.message)); }
  };
  main.append(el("h1", {}, "Check my understanding"),
    el("p", {}, "Teach-back means explaining an instruction in your own words. It helps you and your care team spot anything that is confusing. It is not a test, and there are no wrong answers here."),
    el("div", { class: "card" },
      el("label", { for: "tb-item" }, "Which instruction?"), sel, showItem,
      el("label", { for: "tb-text" }, "In your own words, what does this instruction mean for you?"),
      el("p", { id: "tb-hint", class: "muted" }, "For example: what to do, how often, and when to call. What you type is not saved."),
      box, el("div", { class: "status-row" }, el("button", { type: "button", class: "primary", onclick: submit }, "Check my explanation"))),
    result);
}

function teachBackResult(r) {
  const wrap = el("div", { class: "card" });
  if (r.safety && (r.safety.level === "emergency" || r.safety.level === "crisis")) {
    wrap.append(el("div", { class: "emergency-box", role: "alert" }, el("p", {}, el("strong", {}, r.safety.message))));
  }
  const cls = r.concerns.length ? "result-concern" : "result-review";  // never a reassuring "all good" colour
  wrap.append(el("p", { class: cls }, r.summary));
  if (r.concerns.length) {
    wrap.append(el("h2", {}, "Points to check with your care team"));
    for (const c of r.concerns) wrap.append(el("div", { class: "card" }, el("p", {}, c.message),
      sourceTag("care_plan"), el("blockquote", {}, c.original)));
  }
  if (r.covered.length) wrap.append(el("h3", {}, "Points the tool recognized"), el("ul", { class: "clean" }, r.covered.map(f => el("li", {}, f.statement))));
  if (r.not_mentioned.length) wrap.append(el("h3", {}, "Not mentioned yet"), el("ul", { class: "clean" }, r.not_mentioned.map(f => el("li", {}, f.statement))));
  if (r.follow_up) wrap.append(el("p", { class: "muted" }, r.follow_up));
  if (r.limits) wrap.append(el("p", { class: "notice" }, r.limits));
  return wrap;
}

// ---------------------------------------------------------------- ask
function renderAsk() {
  const log = el("div", { class: "chat", role: "log", "aria-live": "polite", "aria-label": "Conversation" });
  const input = el("input", { id: "ask-input", type: "text", maxlength: "1000", autocomplete: "off" });
  const send = async text => {
    const msg = (text ?? input.value).trim();
    if (!msg) return;
    input.value = "";
    state.chat.push({ me: msg });
    paint();
    try {
      const a = await post(`/api/plans/${state.plan.id}/chat`, { message: msg, level: state.level, last_topic: state.lastTopic });
      if (a.topic) state.lastTopic = a.topic;
      state.level = a.level || state.level;
      state.chat.push({ bot: a });
    } catch (e) { state.chat.push({ bot: { blocks: [{ source: "companion", text: e.message }], suggestions: [] } }); }
    paint();
    input.focus();
  };
  const paint = () => {
    log.replaceChildren(...state.chat.map(m => m.me ? el("div", { class: "msg me" }, el("span", { class: "sr-only" }, "You said: "), m.me)
      : el("div", { class: "msg bot" }, el("span", { class: "sr-only" }, "Companion: "),
          m.bot.safety && ["emergency", "crisis"].includes(m.bot.safety.level) ? el("div", { class: "emergency-box", role: "alert" }, el("strong", {}, m.bot.safety.message)) : null,
          m.bot.blocks.filter(b => !(m.bot.safety && ["emergency", "crisis"].includes(m.bot.safety.level) && b.source === "companion"))
            .map(b => el("div", { class: "block" }, sourceTag(b.source), b.label ? el("div", { class: "muted" }, b.label) : null, el("p", {}, b.text),
              b.url ? el("a", { href: b.url, rel: "noopener noreferrer", target: "_blank", class: "muted" }, "Source") : null)),
          m.bot.suggestions && m.bot.suggestions.length ? el("div", { class: "chips" }, m.bot.suggestions.map(s => el("button", { type: "button", onclick: () => send(s) }, s))) : null)));
    log.lastElementChild && log.lastElementChild.scrollIntoView({ block: "nearest" });
  };
  const starters = ["Explain my diagnosis", "What are my medicines for?", "What are my warning signs?", "When is my next appointment?", "What questions should I ask?"];
  main.append(el("h1", {}, "Ask"),
    el("p", {}, "Ask about your diagnosis, your medicines, your appointments or a word you don't know. Answers come from your care plan or a general education library, and are labelled so you can tell which is which."),
    el("p", { class: "notice" }, "This is not for urgent problems. If you think it may be an emergency, call 911."),
    el("div", { class: "chips" }, starters.map(s => el("button", { type: "button", onclick: () => send(s) }, s))),
    el("div", { class: "card" }, log,
      el("form", { onsubmit: e => { e.preventDefault(); send(); } },
        el("label", { for: "ask-input" }, "Your question"), input,
        el("div", { class: "status-row" }, el("button", { type: "submit", class: "primary" }, "Ask"),
          el("button", { type: "button", onclick: () => send("Can you explain that more simply?") }, "Say it more simply")))));
  paint();
}

// ---------------------------------------------------------------- reminders
async function renderReminders() {
  const tasks = state.plan.items.filter(i => i.task);
  const list = await api(`/api/plans/${state.plan.id}/reminders`);
  const sel = el("select", { id: "rem-item" }, tasks.map(i => el("option", { value: i.id, selected: i.id === state.remindItem }, i.task.label)));
  const when = el("input", { id: "rem-when", type: "datetime-local", required: true });
  const repeat = el("input", { id: "rem-repeat", type: "checkbox" });
  const repeatWrap = el("div", { class: "status-row" }, repeat, el("label", { for: "rem-repeat", class: "inline-label" }, "Repeat every day"));
  const detail = el("div");
  const msg = el("p", { "aria-live": "polite" });
  const refresh = () => {
    const i = tasks.find(t => t.id === sel.value);
    state.remindItem = i.id;
    repeatWrap.hidden = i.task.type !== "daily";
    if (repeatWrap.hidden) repeat.checked = false;
    detail.replaceChildren(sourceTag("care_plan"), el("blockquote", {}, i.original),
      i.when ? el("p", { class: "muted" }, `Planned date: ${new Date(i.when).toLocaleString()}. Reminders must be before this.`) : null,
      i.kind === "medication" ? el("p", { class: "muted" }, "You choose the time. If you are not sure when to take a medicine, ask your pharmacist.") : null);
  };
  sel.addEventListener("change", refresh);
  refresh();
  const add = async e => {
    e.preventDefault();
    if (!when.value) { msg.textContent = "Please choose a date and time."; return; }
    try {
      await post(`/api/plans/${state.plan.id}/reminders`, { item_id: sel.value, remind_at: when.value, repeat: repeat.checked ? "daily" : "none" });
      render();
    } catch (err) { msg.textContent = err.message; msg.className = "result-concern"; }
  };
  main.append(el("h1", {}, "Reminders"),
    el("p", {}, "Reminders can be set only for tasks in your care plan, at times you choose."),
    el("p", { class: "notice" }, "Demo only: reminders appear on this page while it is open. They are not sent to your phone, and closing the page means you may miss them."),
    el("form", { class: "card", onsubmit: add },
      el("label", { for: "rem-item" }, "Task"), sel, detail,
      el("label", { for: "rem-when" }, "Remind me at"), when, repeatWrap,
      el("div", { class: "status-row" }, el("button", { type: "submit", class: "primary" }, "Add reminder")), msg),
    el("h2", {}, "Your reminders"),
    list.length ? el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Task"), el("th", {}, "When"), el("th", {}, "Repeats"), el("th", {}, el("span", { class: "sr-only" }, "Actions")))),
      el("tbody", {}, list.map(r => el("tr", {}, el("td", {}, r.label), el("td", {}, new Date(r.remind_at).toLocaleString()),
        el("td", {}, r.repeat === "daily" ? "Daily" : r.acknowledged_at ? "Done" : "No"),
        el("td", {}, el("button", { type: "button", onclick: async () => { await api(`/api/reminders/${r.id}`, { method: "DELETE" }); render(); } }, "Delete"))))))
      : el("p", { class: "muted" }, "No reminders yet."));
}

async function pollReminders() {
  if (!state.plan) return;
  try {
    const due = await api(`/api/plans/${state.plan.id}/reminders/due`);
    const box = document.getElementById("toasts");
    for (const r of due) {
      if (document.getElementById(`toast-${r.id}`)) continue;
      box.append(el("div", { class: "toast", id: `toast-${r.id}`, role: "status" },
        el("strong", {}, `Reminder: ${r.label}`), el("p", {}, r.instruction),
        el("button", { type: "button", class: "primary", onclick: async e => { await post(`/api/reminders/${r.id}/ack`, {}); e.target.closest(".toast").remove(); } }, "OK")));
    }
  } catch (_) { /* offline: try again next time */ }
}

// ---------------------------------------------------------------- staff: fidelity evaluator
function renderStaff() {
  const items = state.plan.items;
  const sel = el("select", { id: "ev-item" }, items.map(i => el("option", { value: i.id }, i.title)));
  const lang = el("select", { id: "ev-lang" }, el("option", { value: "" }, "Detect"), el("option", { value: "en" }, "English"), el("option", { value: "es" }, "Spanish"), el("option", { value: "non-en" }, "Other language"));
  const cand = el("textarea", { id: "ev-text" });
  const orig = el("blockquote");
  const out = el("div", { "aria-live": "polite" });
  const refresh = () => { const i = items.find(x => x.id === sel.value); orig.textContent = i.original; cand.value = i.plain; };
  sel.addEventListener("change", refresh); refresh();
  const run = async () => {
    try {
      const r = await post(`/api/plans/${state.plan.id}/evaluate`, { item_id: sel.value, candidate: cand.value, language: lang.value || null });
      out.replaceChildren(el("div", { class: "card" },
        el("p", { class: r.counts.critical ? "result-concern" : r.counts.major ? "result-review" : "result-good" }, el("strong", {}, r.verdict)),
        el("p", { class: "muted" }, `Language: ${r.language} · facts checked: ${r.facts_checked}` +
          (r.readability_candidate && r.readability_candidate.fk_grade != null ? ` · reading grade ${r.readability_source.fk_grade} → ${r.readability_candidate.fk_grade}` : "")),
        r.not_assessed.length ? el("p", { class: "notice" }, `Not assessed automatically: ${r.not_assessed.join("; ")}.`) : null,
        r.issues.length ? el("table", {}, el("thead", {}, el("tr", {}, el("th", {}, "Severity"), el("th", {}, "Check"), el("th", {}, "Detail"))),
          el("tbody", {}, r.issues.map(x => el("tr", {}, el("td", {}, el("span", { class: `sev ${x.severity}` }, x.severity)), el("td", {}, x.check.replaceAll("_", " ")), el("td", {}, x.message)))))
          : el("p", {}, "No issues found by the automated checks.")));
    } catch (e) { out.replaceChildren(el("p", { class: "result-concern" }, e.message)); }
  };
  const bench = el("div");
  const runBench = async () => {
    const b = await api("/api/benchmark");
    bench.replaceChildren(el("p", {}, `${b.detected} of ${b.seeded_errors} seeded errors detected; ${b.false_alarms} false alarms on ${b.clean_cases} clean rewrites.`),
      el("p", { class: "muted" }, b.note));
  };
  main.append(el("h1", {}, "For care teams: instruction fidelity check"),
    el("p", {}, "Paste a rewritten version of an instruction (a plain-language rewrite, an AI-generated explanation, or a translation). The checker compares it with the documented instruction for dose and timing numbers, “do not” statements, 911 instructions and medicine names."),
    el("p", { class: "notice" }, "Automated checks find some kinds of errors. They cannot confirm a text is safe or accurate; a clinician (and a qualified interpreter for translations) must review it."),
    el("div", { class: "card" }, el("label", { for: "ev-item" }, "Instruction"), sel, sourceTag("care_plan"), orig,
      el("label", { for: "ev-text" }, "Rewritten version to check"), cand,
      el("label", { for: "ev-lang" }, "Language"), lang,
      el("div", { class: "status-row" }, el("button", { type: "button", class: "primary", onclick: run }, "Check"))),
    out, el("h2", {}, "Evaluator benchmark (synthetic)"), el("button", { type: "button", onclick: runBench }, "Run benchmark"), bench);
}

// ---------------------------------------------------------------- shell
function setupShell() {
  document.querySelectorAll("#tabs button").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));
  const dlg = document.getElementById("help");
  document.getElementById("help-open").addEventListener("click", () => dlg.showModal());
  document.getElementById("help-close").addEventListener("click", () => dlg.close());
  const size = d => { state.fs = Math.min(26, Math.max(14, state.fs + d)); document.documentElement.style.setProperty("--fs", state.fs + "px"); };
  document.getElementById("text-smaller").addEventListener("click", () => size(-2));
  document.getElementById("text-larger").addEventListener("click", () => size(2));
  document.getElementById("reset-demo").addEventListener("click", async () => {
    if (confirm("Clear all demo reminders and checklist progress?")) { await api("/api/demo/reset", { method: "POST" }); if (state.plan) await choosePlan(state.plan.id, state.view); }
  });
  window.addEventListener("hashchange", () => {
    const [, pid, view] = location.hash.split("/");
    if (pid && (!state.plan || state.plan.id !== pid)) choosePlan(pid, view || "health");
    else if (view && view !== state.view) setView(view);
    else if (!pid && state.plan) { state.plan = null; document.getElementById("tabs").hidden = true; render(); }
  });
  setInterval(pollReminders, 20000);
}

(async function init() {
  setupShell();
  state.plans = await api("/api/plans");
  const [, pid, view] = location.hash.split("/");
  if (pid && state.plans.some(p => p.id === pid)) await choosePlan(pid, view || "health");
  else render();
})();
