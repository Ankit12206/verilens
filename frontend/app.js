/* ═══════════════════════════════════════════════════════════════
   VeriLens – Frontend Application Logic
   Handles tab switching, API calls, and dynamic UI rendering.
═══════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin;

// ─── Sample Test Data ──────────────────────────────────────────────────────────
const SAMPLES = {
  rumor: "BREAKING: Government has secretly banned all private vehicles from major cities starting next Monday. Sources say police will begin confiscating cars from tomorrow morning. Share this before it gets deleted!",
  real: "The Reserve Bank of India maintained its benchmark interest rate at 6.5% for the seventh consecutive meeting, citing controlled inflation and steady economic growth in the latest monetary policy committee review.",
  clickbait: "SHOCKING: This common household item is SECRETLY killing your family every night! Doctors are horrified and Big Pharma doesn't want you to know. Act NOW before it is too late!!!"
};

// ─── Initialize Lucide Icons & Check API Health ───────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
  checkAPIHealth();
  setupDragDrop();
});

// ─── API Health Check ──────────────────────────────────────────────────────────
async function checkAPIHealth() {
  const statusEl = document.getElementById("api-status");
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) });
    if (resp.ok) {
      const data = await resp.json();
      const activeEngines = [];
      if (data.gemini_available) activeEngines.push("Gemini");
      if (data.openrouter_available) activeEngines.push("OpenRouter");
      if (data.fact_check_api_available) activeEngines.push("Google FactCheck");
      if (data.serpapi_available) activeEngines.push("SerpAPI");

      let badgeText = "Fallback Mode";
      if (activeEngines.length > 1) {
        badgeText = `Multi-API (${activeEngines.join(" + ")}) ✓`;
      } else if (activeEngines.length === 1) {
        badgeText = `${activeEngines[0]} ✓`;
      }

      statusEl.innerHTML = `
        <div class="w-2 h-2 bg-green-400 rounded-full"></div>
        <span class="text-green-400 text-sm">API Online · ${badgeText}</span>
      `;
    } else {
      throw new Error("API returned error");
    }
  } catch {
    statusEl.innerHTML = `
      <div class="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
      <span class="text-red-400 text-sm">API Offline – Start backend first</span>
    `;
  }
}

// ─── Tab Switching ─────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.add("hidden"));
  document.getElementById(`tab-${name}`).classList.add("active");
  document.getElementById(`panel-${name}`).classList.remove("hidden");
  hideResults();
  lucide.createIcons();
}

// ─── Sample Loader ─────────────────────────────────────────────────────────────
function loadSample(key) {
  document.getElementById("text-input").value = SAMPLES[key];
}

// ─── File Upload Handling ──────────────────────────────────────────────────────
let selectedFile = null;
function handleFileSelect(event) {
  const file = event.target.files[0];
  if (!file) return;
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    const preview = document.getElementById("image-preview");
    preview.src = e.target.result;
    document.getElementById("image-preview-container").classList.remove("hidden");
  };
  reader.readAsDataURL(file);
}

function setupDragDrop() {
  const zone = document.getElementById("drop-zone");
  if (!zone) return;
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("border-brand-500"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("border-brand-500"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("border-brand-500");
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      selectedFile = file;
      const reader = new FileReader();
      reader.onload = ev => {
        document.getElementById("image-preview").src = ev.target.result;
        document.getElementById("image-preview-container").classList.remove("hidden");
      };
      reader.readAsDataURL(file);
    }
  });
}

// ─── Show / Hide UI States ─────────────────────────────────────────────────────
function showLoading(step = "Extracting claims...") {
  document.getElementById("loading").classList.remove("hidden");
  document.getElementById("results").classList.add("hidden");
  document.getElementById("loading-step").textContent = step;
}
function hideLoading() {
  document.getElementById("loading").classList.add("hidden");
}
function hideResults() {
  document.getElementById("results").classList.add("hidden");
}
function updateLoadingStep(step) {
  document.getElementById("loading-step").textContent = step;
}

// ─── API Calls ────────────────────────────────────────────────────────────────
async function analyzeText() {
  const text = document.getElementById("text-input").value.trim();
  if (text.length < 10) return alert("Please enter at least 10 characters of text.");

  showLoading("Extracting claims from text...");
  setTimeout(() => updateLoadingStep("Running live fact-checks..."), 1500);
  setTimeout(() => updateLoadingStep("Building Narrative Matrix..."), 4000);

  try {
    const resp = await fetch(`${API_BASE}/api/analyze-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    hideLoading();
    renderReport(data);
  } catch (err) {
    hideLoading();
    alert(`Error: ${err.message}\n\nMake sure the backend is running:\nuvicorn app.main:app --reload`);
  }
}

async function analyzeImage() {
  const imageUrl = document.getElementById("image-url-input").value.trim();
  const caption = document.getElementById("image-caption").value.trim();

  if (!imageUrl && !selectedFile) return alert("Please provide an image URL or upload an image file.");

  showLoading("Loading and fingerprinting image...");
  setTimeout(() => updateLoadingStep("Running reverse context search..."), 2000);
  setTimeout(() => updateLoadingStep("Checking for temporal discrepancies..."), 4500);

  try {
    const formData = new FormData();
    if (imageUrl) formData.append("image_url", imageUrl);
    if (caption)  formData.append("caption", caption);
    if (selectedFile) formData.append("file", selectedFile);

    const resp = await fetch(`${API_BASE}/api/analyze-image`, { method: "POST", body: formData });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    hideLoading();
    renderReport(data);
  } catch (err) {
    hideLoading();
    alert(`Error: ${err.message}`);
  }
}

async function analyzeMultimodal() {
  const text = document.getElementById("multi-text").value.trim();
  const imageUrl = document.getElementById("multi-image-url").value.trim();

  if (text.length < 10) return alert("Please enter article text.");

  showLoading("Running multimodal analysis...");
  setTimeout(() => updateLoadingStep("Verifying text claims..."), 1500);
  setTimeout(() => updateLoadingStep("Analyzing image provenance..."), 3500);
  setTimeout(() => updateLoadingStep("Synthesizing final verdict..."), 6000);

  try {
    const formData = new FormData();
    formData.append("text", text);
    if (imageUrl) formData.append("image_url", imageUrl);

    const resp = await fetch(`${API_BASE}/api/analyze-multimodal`, { method: "POST", body: formData });
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    hideLoading();
    renderReport(data);
  } catch (err) {
    hideLoading();
    alert(`Error: ${err.message}`);
  }
}

// ─── Report Rendering ──────────────────────────────────────────────────────────
function renderReport(data) {
  // Scroll to results
  document.getElementById("results").classList.remove("hidden");

  // ── Trust Score Gauge ──
  const score = data.credibility_score || 0;
  const circumference = 314;
  const offset = circumference - (score / 100) * circumference;
  const ring = document.getElementById("score-ring");
  ring.style.strokeDashoffset = circumference; // Reset
  setTimeout(() => {
    ring.style.strokeDashoffset = offset;
    ring.style.stroke = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";
  }, 100);

  // Animate number counter
  animateCounter("score-number", 0, score, 1000);

  // ── Verdict Badge ──
  const verdict = data.overall_verdict || "UNVERIFIED";
  const verdictLabels = {
    AUTHENTIC: "✅ Authentic",
    MOSTLY_TRUE: "🟢 Mostly True",
    MISLEADING: "⚠️ Misleading",
    CONTRADICTED: "❌ Contradicted",
    CONTEXT_HIJACKED: "🚨 Context Hijacked",
    UNVERIFIED: "❓ Unverified",
    SATIRE_LIKELY: "🎭 Likely Satire"
  };
  const badge = document.getElementById("verdict-badge");
  badge.className = `inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold mb-3 border verdict-${verdict}`;
  document.getElementById("verdict-label").textContent = verdictLabels[verdict] || verdict;

  document.getElementById("summary-text").textContent = data.summary_explanation || "";
  document.getElementById("sensationalism-score").textContent = `${data.sensationalism_score}/10`;
  document.getElementById("analyzed-at").textContent = new Date(data.analyzed_at).toLocaleString();

  // ── Claims ──
  const claimsSection = document.getElementById("claims-section");
  if (data.claims && data.claims.length > 0) {
    claimsSection.classList.remove("hidden");
    document.getElementById("claims-container").innerHTML = data.claims.map(renderClaimCard).join("");
  } else {
    claimsSection.classList.add("hidden");
  }

  // ── Image / Media Verification ──
  const mediaSection = document.getElementById("media-section");
  if (data.media_verification && data.media_verification.checked) {
    mediaSection.classList.remove("hidden");
    document.getElementById("media-content").innerHTML = renderMediaCheck(data.media_verification);
  } else {
    mediaSection.classList.add("hidden");
  }

  // ── Narrative Matrix ──
  const narrativeSection = document.getElementById("narrative-section");
  if (data.narrative_matrix && data.narrative_matrix.perspectives && data.narrative_matrix.perspectives.length > 0) {
    narrativeSection.classList.remove("hidden");
    const classes = ["viral", "mainstream", "official"];
    document.getElementById("narrative-container").innerHTML =
      data.narrative_matrix.perspectives.map((p, i) => renderPerspectiveCard(p, classes[i] || "mainstream")).join("");
    document.getElementById("consensus-text").textContent = data.narrative_matrix.consensus_verdict || "";
  } else {
    narrativeSection.classList.add("hidden");
  }

  lucide.createIcons();

  // Smooth scroll to results
  document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ─── Component Renderers ───────────────────────────────────────────────────────
function renderClaimCard(claim) {
  const statusIcons = { VERIFIED: "check-circle", CONTRADICTED: "x-circle", UNPROVEN: "help-circle" };
  const icon = statusIcons[claim.status] || "help-circle";
  const confidencePct = Math.round((claim.confidence || 0) * 100);

  const citations = (claim.citations || []).slice(0, 3).map(c =>
    `<a href="${c.url}" target="_blank" rel="noopener" class="citation-link">🔗 ${c.source || c.title}</a>`
  ).join("");

  return `
    <div class="claim-card ${claim.status}">
      <div class="flex items-start gap-3">
        <i data-lucide="${icon}" class="w-5 h-5 mt-0.5 shrink-0 ${claim.status === 'VERIFIED' ? 'text-green-400' : claim.status === 'CONTRADICTED' ? 'text-red-400' : 'text-yellow-400'}"></i>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-2">
            <span class="badge badge-${claim.status}">${claim.status}</span>
            <span class="text-xs text-gray-500 font-mono">Confidence: ${confidencePct}%</span>
          </div>
          <p class="text-sm text-gray-200 font-medium mb-1">"${claim.claim}"</p>
          <p class="text-xs text-gray-400 mb-2">${claim.explanation || ""}</p>
          <div class="h-1 bg-surface-700 rounded-full w-full mb-2">
            <div class="confidence-bar" style="width:${confidencePct}%"></div>
          </div>
          ${citations ? `<div class="mt-2">${citations}</div>` : ""}
        </div>
      </div>
    </div>`;
}

function renderMediaCheck(media) {
  if (media.is_context_hijacked) {
    return `
      <div class="hijack-alert">
        <div class="flex items-start gap-3">
          <i data-lucide="alert-triangle" class="w-6 h-6 text-pink-400 shrink-0 mt-0.5"></i>
          <div>
            <p class="font-bold text-pink-300 mb-1">⚠️ Context Hijack Detected</p>
            <p class="text-sm text-gray-300">${media.warning_message || ""}</p>
            ${media.earliest_found_year ? `<p class="text-xs text-gray-500 mt-2 font-mono">📅 Image first seen: ~${media.earliest_found_year}</p>` : ""}
            ${media.original_context ? `<p class="text-xs text-gray-400 mt-1">📌 Original context: "${media.original_context}"</p>` : ""}
            ${media.discrepancy_details ? `<p class="text-xs text-orange-300 mt-2">⚡ ${media.discrepancy_details}</p>` : ""}
          </div>
        </div>
      </div>`;
  } else {
    return `
      <div class="safe-alert">
        <div class="flex items-start gap-3">
          <i data-lucide="check-circle-2" class="w-6 h-6 text-green-400 shrink-0 mt-0.5"></i>
          <div>
            <p class="font-bold text-green-300 mb-1">Image Context Appears Normal</p>
            ${media.earliest_found_year ? `<p class="text-sm text-gray-400">Image origin: approximately ${media.earliest_found_year}.</p>` : ""}
            ${media.warning_message ? `<p class="text-xs text-yellow-400 mt-1">${media.warning_message}</p>` : ""}
            ${media.original_context ? `<p class="text-xs text-gray-500 mt-1">Context: "${media.original_context}"</p>` : ""}
          </div>
        </div>
      </div>`;
  }
}

function renderPerspectiveCard(perspective, cssClass) {
  const label = perspective.label || "Unknown";
  const summary = perspective.summary || "No data available.";
  const urls = (perspective.source_urls || []).filter(Boolean).slice(0, 2);

  return `
    <div class="perspective-card ${cssClass}">
      <p class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">${label}</p>
      <p class="text-sm text-gray-200 leading-relaxed">${summary}</p>
      ${urls.map(u => `<a href="${u}" target="_blank" rel="noopener" class="citation-link mt-2">🔗 ${extractDomain(u)}</a>`).join("")}
    </div>`;
}

// ─── Utility Functions ─────────────────────────────────────────────────────────
function animateCounter(elementId, from, to, duration) {
  const el = document.getElementById(elementId);
  const start = performance.now();
  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    el.textContent = Math.round(from + (to - from) * easeOut(progress));
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

function extractDomain(url) {
  try { return new URL(url).hostname.replace("www.", ""); }
  catch { return url; }
}
