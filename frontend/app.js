/* ═══════════════════════════════════════════════════════════════
   VeriLens 2.0 – Frontend Application Logic
   Handles:
   - High-Accuracy Real News & Full Story Explanation
   - Half-Truth ("True but Half") Detection & Reader Impact Warning
   - Low-Coverage Local News Websites + YouTube + Science Analysis
   - Image Forensics (Real vs. AI-Generated + Incident & Location)
   - Continuous Self-Learning Memory & User Teaching Feedback
═══════════════════════════════════════════════════════════════ */

const API_BASE = window.location.origin;
let currentReportId = null;
let selectedFile = null;

// ─── Sample Test Data ──────────────────────────────────────────────────────────
const SAMPLES = {
  real: "ISRO's Chandrayaan-3 mission successfully achieved a soft landing near the Moon's south pole region, making India the first nation to land spacecraft near the lunar south pole and the fourth country to soft-land on the Moon.",
  half: "Government data confirms EV battery fires increased this summer and several electric two-wheelers were recalled by manufacturers, proving electric vehicles are much more likely to catch fire than petrol vehicles!",
  rumor: "BREAKING: Government has secretly banned all private vehicles from major cities starting next Monday. Sources say police will begin confiscating cars from tomorrow morning. Share this before it gets deleted!",
  local_science: "Residents in a local rural district reported sudden groundwater warming and steam rising from borewells overnight, claiming an underground volcano is about to erupt beneath the town."
};

// ─── Initialize Lucide Icons, API Health & Self-Learning Stats ─────────────────
document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
  checkAPIHealth();
  loadLearningStats();
  setupDragDrop();
});

// ─── API Health Check ──────────────────────────────────────────────────────────
async function checkAPIHealth() {
  const statusEl = document.getElementById("api-status");
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(6000) });
    if (resp.ok) {
      const data = await resp.json();
      const activeEngines = [];
      if (data.gemini_available) activeEngines.push("Gemini Vision+Text");
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
        <span class="text-green-400 text-xs md:text-sm">API Online · ${badgeText}</span>
      `;
    } else {
      throw new Error("API returned error");
    }
  } catch {
    statusEl.innerHTML = `
      <div class="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
      <span class="text-red-400 text-xs md:text-sm">API Offline – Start backend first</span>
    `;
  }
}

// ─── Self-Learning Memory Stats Loader ─────────────────────────────────────────
async function loadLearningStats() {
  const pill = document.getElementById("learning-pill");
  const pillText = document.getElementById("learning-pill-text");
  if (!pill || !pillText) return;
  try {
    const resp = await fetch(`${API_BASE}/api/learning-stats`, { signal: AbortSignal.timeout(5000) });
    if (resp.ok) {
      const stats = await resp.json();
      const totalFacts = stats.total_learned_facts ?? 0;
      const totalDomains = stats.total_tracked_sources ?? 0;
      const totalImages = stats.total_learned_images ?? 0;
      pill.classList.remove("hidden");
      pill.classList.add("flex");
      pillText.textContent = `AI Memory: ${totalFacts} Facts · ${totalDomains} Sources · ${totalImages} Images`;
    }
  } catch {
    // Non-blocking
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
  if (SAMPLES[key]) {
    document.getElementById("text-input").value = SAMPLES[key];
  }
}

// ─── File Upload Handling ──────────────────────────────────────────────────────
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
function showLoading(step = "Recalling Self-Learning Memory...") {
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
  const el = document.getElementById("loading-step");
  if (el) el.textContent = step;
}

// ─── API Calls ────────────────────────────────────────────────────────────────
async function analyzeText() {
  const text = document.getElementById("text-input").value.trim();
  if (text.length < 10) return alert("Please enter at least 10 characters of news or claim text.");

  showLoading("Checking Self-Learning Memory & Extracting Claims...");
  const t1 = setTimeout(() => updateLoadingStep("Searching Mainstream News, Local Portals & YouTube..."), 1600);
  const t2 = setTimeout(() => updateLoadingStep("Analyzing Completeness (Full Truth vs. Half-Truth) & Science..."), 3800);

  try {
    const resp = await fetch(`${API_BASE}/api/analyze-text`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    clearTimeout(t1);
    clearTimeout(t2);
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    hideLoading();
    renderReport(data);
    loadLearningStats();
  } catch (err) {
    clearTimeout(t1);
    clearTimeout(t2);
    hideLoading();
    alert(`Error: ${err.message}\n\nMake sure the backend is running.`);
  }
}

async function analyzeImage() {
  const imageUrl = document.getElementById("image-url-input").value.trim();
  const caption = document.getElementById("image-caption").value.trim();

  if (!imageUrl && !selectedFile) return alert("Please provide an image URL or upload an image file.");

  showLoading("Stage 1: Running Vision AI Forensics (Real Photo vs. AI-Generated)...");
  const t1 = setTimeout(() => updateLoadingStep("Stage 2: Identifying Incident, Location & Date..."), 2000);
  const t2 = setTimeout(() => updateLoadingStep("Stage 3: Cross-Checking News Websites & YouTube..."), 4500);

  try {
    const formData = new FormData();
    if (imageUrl) formData.append("image_url", imageUrl);
    if (caption)  formData.append("caption", caption);
    if (selectedFile) formData.append("file", selectedFile);

    const resp = await fetch(`${API_BASE}/api/analyze-image`, { method: "POST", body: formData });
    clearTimeout(t1);
    clearTimeout(t2);
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    hideLoading();
    renderReport(data);
    loadLearningStats();
  } catch (err) {
    clearTimeout(t1);
    clearTimeout(t2);
    hideLoading();
    alert(`Error: ${err.message}`);
  }
}

async function analyzeMultimodal() {
  const text = document.getElementById("multi-text").value.trim();
  const imageUrl = document.getElementById("multi-image-url").value.trim();

  if (text.length < 10) return alert("Please enter article text or headline.");

  showLoading("Running Complete Multimodal Verification...");
  const t1 = setTimeout(() => updateLoadingStep("Checking News Truth, Half-Truth & Science..."), 1800);
  const t2 = setTimeout(() => updateLoadingStep("Verifying Image Authenticity & Incident Location..."), 4000);

  try {
    const formData = new FormData();
    formData.append("text", text);
    if (imageUrl) formData.append("image_url", imageUrl);

    const resp = await fetch(`${API_BASE}/api/analyze-multimodal`, { method: "POST", body: formData });
    clearTimeout(t1);
    clearTimeout(t2);
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    hideLoading();
    renderReport(data);
    loadLearningStats();
  } catch (err) {
    clearTimeout(t1);
    clearTimeout(t2);
    hideLoading();
    alert(`Error: ${err.message}`);
  }
}

// ─── Report Rendering ──────────────────────────────────────────────────────────
function renderReport(data) {
  currentReportId = data.id || data.report_id || null;
  document.getElementById("results").classList.remove("hidden");

  // Reset feedback UI state
  const fbConfirm = document.getElementById("feedback-confirmation");
  const corrBox = document.getElementById("correction-box");
  if (fbConfirm) fbConfirm.classList.add("hidden");
  if (corrBox) corrBox.classList.add("hidden");

  // ── 1. Trust Score Gauge ──
  const score = data.credibility_score ?? 0;
  const circumference = 314;
  const offset = circumference - (score / 100) * circumference;
  const ring = document.getElementById("score-ring");
  ring.style.strokeDashoffset = circumference;
  setTimeout(() => {
    ring.style.strokeDashoffset = offset;
    ring.style.stroke = score >= 75 ? "#22c55e" : score >= 45 ? "#f59e0b" : "#ef4444";
  }, 100);

  animateCounter("score-number", 0, score, 900);

  // ── Verdict Badge ──
  const verdict = data.overall_verdict || "UNVERIFIED";
  const verdictLabels = {
    AUTHENTIC: "✅ Authentic & Verified News",
    MOSTLY_TRUE: "🟢 Mostly True News",
    HALF_TRUTH: "⚠️ True News, But HALF Story (Partial Truth)",
    MISLEADING: "⚠️ Misleading Framing",
    CONTRADICTED: "❌ Fake / Contradicted News",
    CONTEXT_HIJACKED: "🚨 Real Image, Misused Context",
    AI_GENERATED_IMAGE: "🤖 AI-Generated Image Detected",
    UNVERIFIED: "❓ Unverified / Investigating",
    SATIRE_LIKELY: "🎭 Likely Satire"
  };
  const badge = document.getElementById("verdict-badge");
  badge.className = `inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-bold border verdict-${verdict}`;
  document.getElementById("verdict-label").textContent = verdictLabels[verdict] || verdict;

  // ── Coverage Level Badge (Mainstream vs. Local/YouTube Deep Search) ──
  const covBadge = document.getElementById("coverage-badge");
  const covLabel = document.getElementById("coverage-label");
  if (covBadge && covLabel) {
    if (data.coverage_level === "LOW_INTERNET_LOCAL_VERIFIED") {
      covBadge.classList.remove("hidden");
      covLabel.textContent = "📡 Low Web Count → Verified via Local News & YouTube";
    } else if (data.coverage_level === "MINIMAL_OR_NONE") {
      covBadge.classList.remove("hidden");
      covLabel.textContent = "🔬 Rare Topic → Analyzed via Local Search & Science";
    } else if (data.coverage_level === "HIGH_MAINSTREAM") {
      covBadge.classList.remove("hidden");
      covLabel.textContent = "🌐 Verified Across Mainstream & National News";
    } else {
      covBadge.classList.add("hidden");
    }
  }

  document.getElementById("summary-text").textContent = data.summary_explanation || "";
  document.getElementById("sensationalism-score").textContent = `${data.sensationalism_score ?? 0}/10`;
  document.getElementById("analyzed-at").textContent = data.analyzed_at
    ? new Date(data.analyzed_at).toLocaleString()
    : new Date().toLocaleString();

  // ── 2. Half-Truth ("True News, But Half") Section ──
  const halfTruthSection = document.getElementById("half-truth-section");
  const missingCtxText = data.missing_context_full_story || data.missing_context || "";
  const isHalfTruth = Boolean(
    data.is_half_truth ||
    verdict === "HALF_TRUTH" ||
    (data.what_is_true && missingCtxText.length > 15)
  );
  if (isHalfTruth && (data.what_is_true || missingCtxText)) {
    halfTruthSection.classList.remove("hidden");
    document.getElementById("what-is-true-text").textContent =
      data.what_is_true || "Contains a real event or statistic, but omits crucial surrounding facts.";
    document.getElementById("missing-context-text").textContent =
      missingCtxText || data.full_news_explanation || "See complete news explanation below.";
  } else {
    halfTruthSection.classList.add("hidden");
  }

  // ── 3. Full News Explanation Section ──
  const fullNewsSection = document.getElementById("full-news-section");
  if (data.full_news_explanation && data.full_news_explanation.trim().length > 5) {
    fullNewsSection.classList.remove("hidden");
    document.getElementById("full-news-text").textContent = data.full_news_explanation;
  } else {
    fullNewsSection.classList.add("hidden");
  }

  // ── 4. Reader Impact & Awareness Warning Section ──
  const impactSection = document.getElementById("impact-section");
  if (data.reader_impact_warning && data.reader_impact_warning.trim().length > 5) {
    impactSection.classList.remove("hidden");
    document.getElementById("impact-text").textContent = data.reader_impact_warning;
  } else {
    impactSection.classList.add("hidden");
  }

  // ── 5. Facts & Scientific Reasoning Section ──
  const scienceSection = document.getElementById("science-section");
  if (data.facts_and_science_analysis && data.facts_and_science_analysis.trim().length > 5) {
    scienceSection.classList.remove("hidden");
    document.getElementById("science-text").textContent = data.facts_and_science_analysis;
  } else {
    scienceSection.classList.add("hidden");
  }

  // ── 6. Image / Media Forensics & Incident Dossier ──
  const mediaSection = document.getElementById("media-section");
  if (data.media_verification && data.media_verification.checked) {
    mediaSection.classList.remove("hidden");
    document.getElementById("media-content").innerHTML = renderMediaCheck(data.media_verification);
  } else {
    mediaSection.classList.add("hidden");
  }

  // ── 7. Local News Websites & YouTube Broadcasts ──
  const localSection = document.getElementById("local-youtube-section");
  if (data.local_and_youtube_sources && data.local_and_youtube_sources.length > 0) {
    localSection.classList.remove("hidden");
    document.getElementById("local-youtube-container").innerHTML =
      data.local_and_youtube_sources.map(renderLocalOrYoutubeCard).join("");
  } else {
    localSection.classList.add("hidden");
  }

  // ── 8. Claim-by-Claim Breakdown ──
  const claimsSection = document.getElementById("claims-section");
  if (data.claims && data.claims.length > 0) {
    claimsSection.classList.remove("hidden");
    document.getElementById("claims-container").innerHTML = data.claims.map(renderClaimCard).join("");
  } else {
    claimsSection.classList.add("hidden");
  }

  // ── 9. 360° Narrative Matrix ──
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

  // ── 10. Self-Learning Memory Status ──
  const learnText = document.getElementById("learning-status-text");
  if (learnText) {
    const lm = data.learning_metadata || {};
    if (lm.recalled_facts_count && lm.recalled_facts_count > 0) {
      learnText.textContent = `⚡ Instant Memory Recall: Matched ${lm.recalled_facts_count} prior verified lesson(s) in AI Memory. Total learned facts: ${lm.total_learned_facts || 1} · Tracked sources: ${lm.total_tracked_sources || 0}.`;
    } else if (lm.learned_from_this_run) {
      learnText.textContent = `🧠 Learned & Stored: VeriLens extracted the verified facts and source reliability from this analysis into its permanent SQLite memory (${lm.total_learned_facts || 1} facts · ${lm.total_tracked_sources || 0} sources).`;
    } else {
      learnText.textContent = `🧠 Self-Learning Active: Confirm accuracy or teach VeriLens below to reinforce its permanent knowledge base.`;
    }
  }

  lucide.createIcons();
  document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ─── Component Renderers ───────────────────────────────────────────────────────
function renderClaimCard(claim) {
  const statusIcons = {
    VERIFIED: "check-circle",
    HALF_TRUE: "alert-circle",
    CONTRADICTED: "x-circle",
    UNPROVEN: "help-circle"
  };
  const statusColors = {
    VERIFIED: "text-green-400",
    HALF_TRUE: "text-amber-400",
    CONTRADICTED: "text-red-400",
    UNPROVEN: "text-yellow-400"
  };
  const icon = statusIcons[claim.status] || "help-circle";
  const color = statusColors[claim.status] || "text-yellow-400";
  const confidencePct = Math.round((claim.confidence || 0) * 100);

  const citations = (claim.citations || []).slice(0, 4).map(c =>
    `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener" class="citation-link">🔗 ${escapeHtml(c.source || c.title)}</a>`
  ).join("");

  return `
    <div class="claim-card ${claim.status}">
      <div class="flex items-start gap-3">
        <i data-lucide="${icon}" class="w-5 h-5 mt-0.5 shrink-0 ${color}"></i>
        <div class="flex-1 min-w-0">
          <div class="flex flex-wrap items-center gap-2 mb-2">
            <span class="badge badge-${claim.status}">${claim.status === "HALF_TRUE" ? "HALF-TRUE (PARTIAL)" : claim.status}</span>
            <span class="text-xs text-gray-500 font-mono">Confidence: ${confidencePct}%</span>
          </div>
          <p class="text-sm text-gray-100 font-medium mb-1">"${escapeHtml(claim.claim)}"</p>
          <p class="text-xs text-gray-300 mb-2 leading-relaxed">${escapeHtml(claim.explanation || "")}</p>
          <div class="h-1 bg-surface-700 rounded-full w-full mb-2">
            <div class="confidence-bar" style="width:${confidencePct}%"></div>
          </div>
          ${citations ? `<div class="mt-2 flex flex-wrap gap-1">${citations}</div>` : ""}
        </div>
      </div>
    </div>`;
}

function renderMediaCheck(media) {
  const isAI = media.authenticity_verdict === "AI_GENERATED";
  const aiProb = Math.round(media.ai_probability ?? (isAI ? 88 : 8));
  const realProb = 100 - aiProb;

  const authBadge = isAI
    ? `<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40">🤖 AI-Generated / Synthetic Image (${aiProb}% AI Probability)</span>`
    : `<span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-green-500/20 text-green-300 border border-green-500/40">📷 Real Camera Photograph (${realProb}% Authenticity)</span>`;

  const forensicList = media.forensic_analysis || media.ai_detection_reasons || [];
  const reasons = forensicList.map(r =>
    `<li class="text-xs text-gray-300 flex items-start gap-2"><span class="text-brand-400 mt-0.5">•</span><span>${escapeHtml(r)}</span></li>`
  ).join("");

  const sources = (media.discovered_sources || []).slice(0, 4).map(s =>
    `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener" class="citation-link">🔗 ${escapeHtml(s.source || s.title)}</a>`
  ).join("");

  const hijackBanner = media.is_context_hijacked ? `
    <div class="hijack-alert mt-4">
      <p class="font-bold text-pink-300 text-sm mb-1">🚨 Context Hijack / Misleading Caption Detected</p>
      <p class="text-xs text-gray-200 leading-relaxed">${escapeHtml(media.discrepancy_details || media.warning_message || "")}</p>
    </div>
  ` : "";

  return `
    <div class="space-y-4">
      <!-- Task 1: Real vs. AI-Generated Forensics -->
      <div class="bg-surface-900/80 border ${isAI ? 'border-purple-500/50' : 'border-green-500/40'} rounded-xl p-4">
        <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
          <span class="text-xs font-bold uppercase tracking-wider text-gray-400">Task 1 · Image Authenticity (Real vs. AI Detector)</span>
          ${authBadge}
        </div>
        <div class="w-full bg-surface-700 h-2 rounded-full overflow-hidden mb-3">
          <div class="h-full ${isAI ? 'bg-purple-500' : 'bg-green-500'}" style="width: ${isAI ? aiProb : realProb}%"></div>
        </div>
        ${reasons ? `<ul class="space-y-1.5 mt-2">${reasons}</ul>` : ""}
      </div>

      <!-- Task 2: Incident, Location & Date Dossier -->
      <div class="bg-surface-900/80 border border-brand-500/30 rounded-xl p-4">
        <p class="text-xs font-bold uppercase tracking-wider text-brand-400 mb-3">
          Task 2 · Related Incident, Location & Origins
        </p>
        <div class="grid md:grid-cols-3 gap-3 mb-3">
          <div class="bg-surface-800 border border-surface-700 rounded-lg p-3">
            <p class="text-[11px] uppercase text-gray-500 font-semibold">📌 Related Incident</p>
            <p class="text-sm font-bold text-white mt-1">${escapeHtml(media.related_incident || "Identified Visual Scene")}</p>
          </div>
          <div class="bg-surface-800 border border-surface-700 rounded-lg p-3">
            <p class="text-[11px] uppercase text-gray-500 font-semibold">📍 Location Where Taken</p>
            <p class="text-sm font-bold text-brand-300 mt-1">${escapeHtml(media.location_taken || "Location under verification")}</p>
          </div>
          <div class="bg-surface-800 border border-surface-700 rounded-lg p-3">
            <p class="text-[11px] uppercase text-gray-500 font-semibold">📅 Incident Date / Period</p>
            <p class="text-sm font-bold text-amber-300 mt-1">${escapeHtml(media.incident_date || (media.earliest_found_year ? String(media.earliest_found_year) : "Recent / Archival"))}</p>
          </div>
        </div>
        <div class="bg-surface-800/70 border border-surface-700 rounded-lg p-3">
          <p class="text-xs font-semibold text-gray-400 mb-1">📖 Full Incident Story & Visual Context:</p>
          <p class="text-sm text-gray-200 leading-relaxed">${escapeHtml(media.incident_details || media.original_context || media.warning_message || "")}</p>
        </div>
        ${sources ? `<div class="mt-3 flex flex-wrap gap-1.5">${sources}</div>` : ""}
      </div>
      ${hijackBanner}
    </div>`;
}

function renderLocalOrYoutubeCard(item) {
  const isYT = item.source_type === "youtube" || item.source_type === "YOUTUBE_VIDEO";
  const badge = isYT
    ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-500/20 text-red-300 border border-red-500/30">▶️ YouTube Broadcast</span>`
    : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">🗞️ Local / Regional News</span>`;

  return `
    <div class="bg-surface-900/80 border border-surface-700 rounded-xl p-4 flex flex-col justify-between">
      <div>
        <div class="flex items-center justify-between gap-2 mb-2">
          ${badge}
          <span class="text-xs text-gray-500 font-mono truncate">${escapeHtml(item.source || item.channel_or_portal || "")}</span>
        </div>
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="text-sm font-semibold text-white hover:text-brand-400 transition-colors line-clamp-2">
          ${escapeHtml(item.title)}
        </a>
        <p class="text-xs text-gray-400 mt-1.5 line-clamp-3">${escapeHtml(item.snippet || "")}</p>
      </div>
      <div class="mt-3 pt-2 border-t border-surface-800 flex justify-between items-center">
        <span class="text-[11px] text-gray-500">Verified Source</span>
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="text-xs text-brand-400 hover:underline">Open Source ↗</a>
      </div>
    </div>`;
}

function renderPerspectiveCard(perspective, cssClass) {
  const label = perspective.label || "Perspective";
  const summary = perspective.summary || "No data available.";
  const urls = (perspective.source_urls || []).filter(Boolean).slice(0, 3);

  return `
    <div class="perspective-card ${cssClass}">
      <p class="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">${escapeHtml(label)}</p>
      <p class="text-sm text-gray-200 leading-relaxed">${escapeHtml(summary)}</p>
      <div class="mt-2 flex flex-wrap gap-1">
        ${urls.map(u => `<a href="${escapeHtml(u)}" target="_blank" rel="noopener" class="citation-link">🔗 ${escapeHtml(extractDomain(u))}</a>`).join("")}
      </div>
    </div>`;
}

// ─── Self-Learning User Feedback Handlers ─────────────────────────────────────
function toggleCorrectionBox() {
  const box = document.getElementById("correction-box");
  if (box) box.classList.toggle("hidden");
}

async function sendFeedback(isAccurate) {
  if (!currentReportId) return;
  const confirmEl = document.getElementById("feedback-confirmation");
  const payload = {
    report_id: currentReportId,
    is_accurate: isAccurate,
    correct_verdict: isAccurate ? null : document.getElementById("correction-verdict").value,
    user_correction: isAccurate ? null : document.getElementById("correction-text").value.trim()
  };

  try {
    const resp = await fetch(`${API_BASE}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) throw new Error(await resp.text());
    const res = await resp.json();
    if (confirmEl) {
      confirmEl.textContent = `✅ ${res.message || "Self-learning memory updated!"}`;
      confirmEl.classList.remove("hidden");
    }
    document.getElementById("correction-box").classList.add("hidden");
    loadLearningStats();
  } catch (err) {
    alert(`Could not save feedback: ${err.message}`);
  }
}

// ─── Utility Functions ─────────────────────────────────────────────────────────
function animateCounter(elementId, from, to, duration) {
  const el = document.getElementById(elementId);
  if (!el) return;
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

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
