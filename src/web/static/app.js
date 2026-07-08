"use strict";

const ROLE_LABEL = { buyer: "Comprador", seller: "Vendedor", mediator: "Mediador" };

const SCENARIO_FIELDS = {
  constraints: [
    "min_unit_price", "max_unit_price", "min_quantity", "max_quantity",
    "earliest_delivery_deadline", "latest_delivery_deadline",
  ],
  buyer_preferences: ["buyer_target_unit_price", "buyer_target_quantity", "buyer_target_delivery_deadline"],
  seller_preferences: ["seller_target_unit_price", "seller_target_quantity", "seller_target_delivery_deadline"],
  buyer_guardrails: ["buyer_max_acceptable_unit_price", "buyer_min_acceptable_quantity", "buyer_latest_acceptable_deadline"],
  seller_guardrails: ["seller_min_acceptable_unit_price", "seller_min_acceptable_quantity", "seller_earliest_acceptable_deadline"],
};

let defaults = null;

async function init() {
  const res = await fetch("/api/defaults");
  defaults = await res.json();

  const providers = defaults.providers;
  for (const id of ["buyer-provider", "seller-provider"]) {
    const sel = document.getElementById(id);
    providers.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
  }
  document.getElementById("buyer-provider").value = "openrouter";
  document.getElementById("seller-provider").value = "openrouter";

  const dl = document.getElementById("model-list");
  (defaults.openrouter_models || []).forEach((m) => {
    const opt = document.createElement("option");
    opt.value = m;
    dl.appendChild(opt);
  });

  if (!defaults.openrouter_key_present) {
    document.getElementById("key-warning").classList.remove("hidden");
  }

  fillScenario(defaults.scenario);
  document.getElementById("run-btn").addEventListener("click", runNegotiation);
}

function fillScenario(s) {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
  set("min_unit_price", s.constraints.min_unit_price);
  set("max_unit_price", s.constraints.max_unit_price);
  set("min_quantity", s.constraints.min_quantity);
  set("max_quantity", s.constraints.max_quantity);
  set("earliest_delivery_deadline", s.constraints.earliest_delivery_deadline);
  set("latest_delivery_deadline", s.constraints.latest_delivery_deadline);
  set("buyer_target_unit_price", s.buyer_preferences.target_unit_price);
  set("buyer_target_quantity", s.buyer_preferences.target_quantity);
  set("buyer_target_delivery_deadline", s.buyer_preferences.target_delivery_deadline);
  set("seller_target_unit_price", s.seller_preferences.target_unit_price);
  set("seller_target_quantity", s.seller_preferences.target_quantity);
  set("seller_target_delivery_deadline", s.seller_preferences.target_delivery_deadline);
  set("buyer_max_acceptable_unit_price", s.buyer_guardrails.buyer_max_acceptable_unit_price);
  set("buyer_min_acceptable_quantity", s.buyer_guardrails.buyer_min_acceptable_quantity);
  set("buyer_latest_acceptable_deadline", s.buyer_guardrails.buyer_latest_acceptable_deadline);
  set("seller_min_acceptable_unit_price", s.seller_guardrails.seller_min_acceptable_unit_price);
  set("seller_min_acceptable_quantity", s.seller_guardrails.seller_min_acceptable_quantity);
  set("seller_earliest_acceptable_deadline", s.seller_guardrails.seller_earliest_acceptable_deadline);
}

function num(id) { return parseFloat(document.getElementById(id).value); }
function int(id) { return parseInt(document.getElementById(id).value, 10); }
function val(id) { return document.getElementById(id).value; }

function buildScenarioPayload() {
  return {
    constraints: {
      min_unit_price: num("min_unit_price"),
      max_unit_price: num("max_unit_price"),
      min_quantity: int("min_quantity"),
      max_quantity: int("max_quantity"),
      earliest_delivery_deadline: val("earliest_delivery_deadline"),
      latest_delivery_deadline: val("latest_delivery_deadline"),
    },
    buyer_preferences: {
      target_unit_price: num("buyer_target_unit_price"),
      target_quantity: int("buyer_target_quantity"),
      target_delivery_deadline: val("buyer_target_delivery_deadline"),
    },
    seller_preferences: {
      target_unit_price: num("seller_target_unit_price"),
      target_quantity: int("seller_target_quantity"),
      target_delivery_deadline: val("seller_target_delivery_deadline"),
    },
    buyer_guardrails: {
      buyer_max_acceptable_unit_price: num("buyer_max_acceptable_unit_price"),
      buyer_min_acceptable_quantity: int("buyer_min_acceptable_quantity"),
      buyer_latest_acceptable_deadline: val("buyer_latest_acceptable_deadline"),
    },
    seller_guardrails: {
      seller_min_acceptable_unit_price: num("seller_min_acceptable_unit_price"),
      seller_min_acceptable_quantity: int("seller_min_acceptable_quantity"),
      seller_earliest_acceptable_deadline: val("seller_earliest_acceptable_deadline"),
    },
  };
}

function setStatus(text, cls) {
  const el = document.getElementById("status");
  el.textContent = text;
  el.className = "status " + cls;
}

function termsLine(t) {
  if (!t) return "";
  return `<div class="terms">💶 <b>${t.unit_price}</b> /ud · 📦 <b>${t.quantity}</b> uds · 📅 <b>${t.delivery_deadline}</b></div>`;
}

function addBubble(turn) {
  const conv = document.getElementById("conversation");
  const div = document.createElement("div");
  div.className = "bubble " + turn.agent_role;
  const latency = turn.provider_latency_ms ? ` · ${Math.round(turn.provider_latency_ms)} ms` : "";
  const model = turn.provider_model_name ? ` (${turn.provider_model_name})` : "";
  let body = `
    <div class="head">
      <span class="role-name">${ROLE_LABEL[turn.agent_role] || turn.agent_role} · R${turn.round_number}${model}${latency}</span>
      <span class="tag ${turn.action_type}">${turn.action_type}</span>
    </div>`;
  if (turn.target_offer_id) body += `<div class="terms muted">↪ sobre ${turn.target_offer_id}</div>`;
  body += termsLine(turn.offer_terms);
  if (turn.rationale) body += `<div class="rationale">“${turn.rationale}”</div>`;
  if (!turn.is_valid) body += `<div class="invalid">✕ inválida: ${(turn.errors || []).join("; ")}</div>`;
  div.innerHTML = body;
  conv.appendChild(div);
  conv.scrollTop = conv.scrollHeight;
}

function bar(value, color) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return `<div class="bar"><div style="width:${pct}%;background:${color}"></div></div>`;
}

function renderResults(data) {
  const el = document.getElementById("results");
  const m = data.metrics;
  const ok = data.agreement_reached && m.valid_agreement;
  let html = `<div class="verdict ${ok ? "ok" : "no"}">${ok ? "✓ Acuerdo alcanzado" : "✗ Sin acuerdo"}</div>`;
  html += `<div class="metric-row"><span>Motivo de cierre</span><span>${data.stopped_reason}</span></div>`;
  if (data.agreement) {
    const a = data.agreement;
    html += termsLine(a.terms);
    html += `<div class="metric-row"><span>Cerrado en ronda</span><span>${a.reached_at_round}</span></div>`;
    html += `<div class="metric-row"><span>Mediado</span><span>${a.mediated ? "sí" : "no"}</span></div>`;
  }
  html += `<div class="metric-row"><span>Utilidad comprador</span><span>${m.buyer_utility}</span></div>${bar(m.buyer_utility, "var(--buyer)")}`;
  html += `<div class="metric-row"><span>Utilidad vendedor</span><span>${m.seller_utility}</span></div>${bar(m.seller_utility, "var(--seller)")}`;
  html += `<div class="metric-row"><span>Utilidad conjunta</span><span>${m.joint_utility}</span></div>`;
  html += `<div class="metric-row"><span>Equilibrio (gap)</span><span>${m.agreement_balance_gap}</span></div>`;
  html += `<div class="metric-row"><span>Viable comprador</span><span>${m.private_feasibility_buyer ? "sí" : "no"}</span></div>`;
  html += `<div class="metric-row"><span>Viable vendedor</span><span>${m.private_feasibility_seller ? "sí" : "no"}</span></div>`;
  html += `<div class="metric-row"><span>Rondas usadas</span><span>${m.rounds_used}</span></div>`;
  el.innerHTML = html;
}

async function runNegotiation() {
  const btn = document.getElementById("run-btn");
  btn.disabled = true;
  document.getElementById("conversation").innerHTML = "";
  document.getElementById("results").innerHTML = '<p class="muted">Negociando…</p>';
  setStatus("Negociando… (los turnos aparecen en tiempo real)", "running");

  const payload = {
    scenario: buildScenarioPayload(),
    buyer: { provider: val("buyer-provider"), model: val("buyer-model") },
    seller: { provider: val("seller-provider"), model: val("seller-model") },
    max_rounds: int("max-rounds"),
    temperature: num("temperature"),
    mediator: {
      enabled: document.getElementById("mediator-enabled").checked,
      start_round: int("mediator-start"),
    },
  };

  try {
    const res = await fetch("/api/negotiate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();
      for (const chunk of chunks) {
        if (!chunk.trim()) continue;
        const lines = chunk.split("\n");
        const event = lines.find((l) => l.startsWith("event:"))?.slice(6).trim();
        const dataLine = lines.find((l) => l.startsWith("data:"))?.slice(5).trim();
        if (!dataLine) continue;
        const data = JSON.parse(dataLine);
        if (event === "turn") addBubble(data);
        else if (event === "done") { renderResults(data); setStatus("Negociación finalizada.", "done"); }
        else if (event === "error") { setStatus("Error: " + data.message, "error"); }
      }
    }
  } catch (err) {
    setStatus("Error de conexión: " + err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

init();
