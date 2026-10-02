/**
 * app.js — FakeNews GPT Application Controller
 * Provides an authentic ChatGPT conversational interface for 3-layer fake news verification.
 */

// ── Application State ─────────────────────────────────────────────
const state = {
  currentSessionId: null,
  currentQuery: '',
  useBert: true,
  isGenerating: false,
  selectedModel: 'full',
  theme: localStorage.getItem('fakenews_theme') || 'dark',
  history: JSON.parse(localStorage.getItem('fakenews_history') || '[]'),
  lastResult: null,
  speechRecognition: null,
  isRecording: false
};

// ── DOM Element Cache ─────────────────────────────────────────────
const elements = {
  appLayout: document.getElementById('app-layout'),
  sidebar: document.getElementById('sidebar'),
  sidebarBackdrop: document.getElementById('sidebar-backdrop'),
  historyList: document.getElementById('history-list'),
  historyEmpty: document.getElementById('history-empty'),
  chatContainer: document.getElementById('chat-container'),
  heroScreen: document.getElementById('hero-screen'),
  messagesStream: document.getElementById('messages-stream'),
  promptTextarea: document.getElementById('prompt-textarea'),
  sendBtn: document.getElementById('send-btn'),
  micBtn: document.getElementById('mic-btn'),
  bertEngineDot: document.getElementById('bert-engine-dot'),
  bertToggleCheckbox: document.getElementById('bert-toggle-checkbox'),
  modelSelectorBtn: document.getElementById('model-selector-btn'),
  modelDropdownMenu: document.getElementById('model-dropdown-menu'),
  currentModelName: document.getElementById('current-model-name'),
  scrollBottomAnchor: document.getElementById('scroll-bottom-anchor'),
  toastContainer: document.getElementById('toast-container')
};

// ── Initialization ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initTextarea();
  initKeyboardShortcuts();
  initVoiceRecognition();
  renderHistoryList();
  updateBertEngineIndicator();

  // Close dropdown on outside click
  document.addEventListener('click', (e) => {
    if (!elements.modelSelectorBtn.contains(e.target) && !elements.modelDropdownMenu.contains(e.target)) {
      elements.modelDropdownMenu.classList.remove('open');
    }
  });
});

// ── Theme Management ──────────────────────────────────────────────
function initTheme() {
  setTheme(state.theme);
  const themeSelect = document.getElementById('theme-select');
  if (themeSelect) themeSelect.value = state.theme;
}

function setTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('fakenews_theme', theme);
  const themeSelect = document.getElementById('theme-select');
  if (themeSelect) themeSelect.value = theme;
}

function toggleTheme() {
  const newTheme = state.theme === 'dark' ? 'light' : 'dark';
  setTheme(newTheme);
  showToast(`Switched to ${newTheme} theme`);
}

// ── Sidebar Toggle ────────────────────────────────────────────────
function toggleSidebar(forceState) {
  const isMobile = window.innerWidth <= 768;
  if (isMobile) {
    const isOpen = forceState !== undefined ? forceState : !elements.sidebar.classList.contains('mobile-open');
    if (isOpen) {
      elements.sidebar.classList.add('mobile-open');
      elements.sidebarBackdrop.classList.add('active');
    } else {
      elements.sidebar.classList.remove('mobile-open');
      elements.sidebarBackdrop.classList.remove('active');
    }
  } else {
    elements.sidebar.classList.toggle('collapsed');
  }
}

// ── Textarea Auto-Resize & Submit ─────────────────────────────────
function initTextarea() {
  const textarea = elements.promptTextarea;

  textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
    const hasText = textarea.value.trim().length > 0;
    elements.sendBtn.disabled = !hasText || state.isGenerating;
  });

  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!elements.sendBtn.disabled) {
        handleSendPrompt();
      }
    }
  });
}

function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      startNewChat();
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      toggleSidebar();
    }
  });
}

// ── Model Selection & Toggles ─────────────────────────────────────
function toggleModelDropdown() {
  elements.modelDropdownMenu.classList.toggle('open');
}

function selectModel(modelKey, displayName, useBert) {
  state.selectedModel = modelKey;
  state.useBert = useBert;
  elements.currentModelName.textContent = displayName;
  elements.bertToggleCheckbox.checked = useBert;
  const modalToggle = document.getElementById('modal-bert-toggle');
  if (modalToggle) modalToggle.checked = useBert;

  updateBertEngineIndicator();
  elements.modelDropdownMenu.classList.remove('open');

  // Update checkmarks in dropdown
  const items = elements.modelDropdownMenu.querySelectorAll('.dropdown-item');
  items.forEach(item => item.classList.remove('selected'));
  if (modelKey === 'full') items[0].classList.add('selected');
  else items[1].classList.add('selected');

  showToast(`Switched model to ${displayName}`);
}

function handleBertToggle(checkbox) {
  state.useBert = checkbox.checked;
  updateBertEngineIndicator();
  const modalToggle = document.getElementById('modal-bert-toggle');
  if (modalToggle) modalToggle.checked = state.useBert;
  showToast(`BERT AI Classifier: ${state.useBert ? 'Enabled' : 'Disabled'}`);
}

function syncBertModal(checkbox) {
  state.useBert = checkbox.checked;
  elements.bertToggleCheckbox.checked = state.useBert;
  updateBertEngineIndicator();
}

function updateBertEngineIndicator() {
  if (elements.bertEngineDot) {
    if (state.useBert) {
      elements.bertEngineDot.classList.add('on');
    } else {
      elements.bertEngineDot.classList.remove('on');
    }
  }
}

// ── Voice Dictation (Speech Recognition) ──────────────────────────
function initVoiceRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    elements.micBtn.style.display = 'none';
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    state.isRecording = true;
    elements.micBtn.classList.add('recording');
    elements.promptTextarea.placeholder = 'Listening... Speak your claim now';
  };

  recognition.onresult = (event) => {
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      transcript += event.results[i][0].transcript;
    }
    elements.promptTextarea.value = transcript;
    elements.promptTextarea.dispatchEvent(new Event('input'));
  };

  recognition.onerror = () => {
    stopVoiceRecognition();
  };

  recognition.onend = () => {
    stopVoiceRecognition();
  };

  state.speechRecognition = recognition;
}

function toggleVoiceRecognition() {
  if (!state.speechRecognition) {
    showToast('Speech recognition not supported in this browser.');
    return;
  }
  if (state.isRecording) {
    state.speechRecognition.stop();
  } else {
    try {
      state.speechRecognition.start();
    } catch {
      stopVoiceRecognition();
    }
  }
}

function stopVoiceRecognition() {
  state.isRecording = false;
  elements.micBtn.classList.remove('recording');
  elements.promptTextarea.placeholder = 'Message FakeNews GPT or paste a news headline...';
}

// ── Speech Synthesis (Text-to-Speech) ─────────────────────────────
function speakText(text) {
  if (!('speechSynthesis' in window)) return;
  const ttsEnabled = document.getElementById('tts-toggle')?.checked ?? true;
  if (!ttsEnabled) return;

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.05;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}

// ── Suggestion Card Submit ────────────────────────────────────────
function submitExample(claimText) {
  elements.promptTextarea.value = claimText;
  elements.promptTextarea.dispatchEvent(new Event('input'));
  handleSendPrompt();
}

// ── Start New Chat ────────────────────────────────────────────────
function startNewChat() {
  state.currentSessionId = null;
  state.lastResult = null;
  elements.messagesStream.innerHTML = '';
  elements.heroScreen.style.display = 'flex';
  elements.promptTextarea.value = '';
  elements.promptTextarea.style.height = 'auto';
  elements.sendBtn.disabled = true;
  elements.promptTextarea.focus();
  toggleSidebar(false);
}

// ── Main Verification Flow ────────────────────────────────────────
async function handleSendPrompt() {
  const query = elements.promptTextarea.value.trim();
  if (!query || query.length < 5 || state.isGenerating) return;

  state.isGenerating = true;
  state.currentQuery = query;

  // Clear & reset input
  elements.promptTextarea.value = '';
  elements.promptTextarea.style.height = 'auto';
  elements.sendBtn.disabled = true;
  elements.sendBtn.classList.add('loading');

  // Hide empty state hero
  elements.heroScreen.style.display = 'none';

  // 1. Render User Message
  renderUserMessage(query);
  scrollToBottom();

  // 2. Render Assistant Placeholder with live Thinking Accordion
  const assistantMsgId = `assistant-${Date.now()}`;
  const assistantRow = renderAssistantThinkingRow(assistantMsgId);
  scrollToBottom();

  // Live timer for reasoning display
  const startTime = Date.now();
  const timerInterval = setInterval(() => {
    const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(1);
    const thinkingHeader = document.getElementById(`${assistantMsgId}-thinking-time`);
    if (thinkingHeader) thinkingHeader.textContent = `Thinking for ${elapsedSec}s...`;
  }, 100);

  // Progressive step simulation
  simulateThinkingSteps(assistantMsgId);

  try {
    const response = await fetch('/api/examine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        use_bert: state.useBert
      })
    });

    clearInterval(timerInterval);

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.error || `Server responded with ${response.status}`);
    }

    const result = await response.json();
    state.lastResult = { query, ...result };

    // Finalize thinking state
    finishThinkingAccordion(assistantMsgId, result.elapsed || ((Date.now() - startTime) / 1000).toFixed(1));

    // Render Verdict Result inside the Assistant Bubble
    renderVerdictInMessage(assistantMsgId, query, result);

    // Save to history
    saveToHistory(query, result);

    // Speak aloud if enabled
    const speechSummary = `Verdict: ${result.verdict}. ${result.summary || ''}`;
    speakText(speechSummary);

  } catch (err) {
    clearInterval(timerInterval);
    renderErrorMessage(assistantMsgId, err.message);
  } finally {
    state.isGenerating = false;
    elements.sendBtn.classList.remove('loading');
    elements.promptTextarea.focus();
    scrollToBottom();
  }
}

// ── Render Helpers ────────────────────────────────────────────────
function renderUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'message-row user';
  row.innerHTML = `
    <div class="user-message-bubble">${escapeHtml(text)}</div>
  `;
  elements.messagesStream.appendChild(row);
}

function renderAssistantThinkingRow(msgId) {
  const row = document.createElement('div');
  row.className = 'message-row assistant';
  row.id = msgId;

  row.innerHTML = `
    <div class="assistant-avatar">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    </div>
    <div class="assistant-message-content" id="${msgId}-content">
      <div class="thinking-accordion open" id="${msgId}-thinking">
        <div class="thinking-accordion-header" onclick="toggleAccordion('${msgId}-thinking')">
          <div class="thinking-header-left">
            <div class="thinking-spinner"></div>
            <span class="thinking-done-icon">✓</span>
            <span id="${msgId}-thinking-time">Thinking...</span>
          </div>
          <svg class="thinking-chevron" viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </div>
        <div class="thinking-steps-body">
          <div class="thinking-step-item active" id="${msgId}-step-1">
            <span class="step-icon-indicator">🔍</span>
            <span>Querying Google Fact Check database &amp; Wikipedia entities...</span>
          </div>
          <div class="thinking-step-item" id="${msgId}-step-2">
            <span class="step-icon-indicator">📡</span>
            <span>Searching global real-time news wire (GDELT &amp; NewsAPI)...</span>
          </div>
          <div class="thinking-step-item" id="${msgId}-step-3">
            <span class="step-icon-indicator">🤖</span>
            <span>Executing RoBERTa/BERT deep neural classifier...</span>
          </div>
          <div class="thinking-step-item" id="${msgId}-step-4">
            <span class="step-icon-indicator">⚖️</span>
            <span>Synthesizing multi-layer evidence &amp; confidence scores...</span>
          </div>
        </div>
      </div>
      <div id="${msgId}-result-body"></div>
    </div>
  `;

  elements.messagesStream.appendChild(row);
  return row;
}

function simulateThinkingSteps(msgId) {
  setTimeout(() => {
    markStep(msgId, 'step-1', 'step-2');
  }, 1200);

  setTimeout(() => {
    markStep(msgId, 'step-2', 'step-3');
  }, 2800);

  setTimeout(() => {
    markStep(msgId, 'step-3', 'step-4');
  }, 4400);
}

function markStep(msgId, prevStep, nextStep) {
  const prev = document.getElementById(`${msgId}-${prevStep}`);
  const next = document.getElementById(`${msgId}-${nextStep}`);
  if (prev) {
    prev.classList.remove('active');
    prev.classList.add('done');
  }
  if (next) {
    next.classList.add('active');
  }
}

function finishThinkingAccordion(msgId, elapsed) {
  const accordion = document.getElementById(`${msgId}-thinking`);
  if (!accordion) return;

  accordion.classList.add('done');
  accordion.classList.remove('open');

  const timeLabel = document.getElementById(`${msgId}-thinking-time`);
  if (timeLabel) {
    timeLabel.textContent = `Thought for ${elapsed}s • 3 verification layers checked`;
  }

  // Mark all steps done
  for (let i = 1; i <= 4; i++) {
    const s = document.getElementById(`${msgId}-step-${i}`);
    if (s) {
      s.classList.remove('active');
      s.classList.add('done');
    }
  }
}

function toggleAccordion(id) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle('open');
}

// ── Render Verdict Card & Details ─────────────────────────────────
const VERDICT_CONFIG = {
  REAL: {
    cls: 'real',
    badgeCls: 'real',
    icon: '✅',
    label: 'LIKELY REAL NEWS',
    tagline: 'Corroborated by verified sources with high confidence'
  },
  FAKE: {
    cls: 'fake',
    badgeCls: 'fake',
    icon: '❌',
    label: 'LIKELY FAKE NEWS',
    tagline: 'Contradicted or debunked by fact-checkers and evidence'
  },
  MISLEADING: {
    cls: 'misleading',
    badgeCls: 'misleading',
    icon: '⚠️',
    label: 'MISLEADING / NEEDS CONTEXT',
    tagline: 'Contains partial truths or distorted context'
  },
  UNVERIFIED: {
    cls: 'unverified',
    badgeCls: 'unverified',
    icon: '🔍',
    label: 'UNVERIFIED — CHECK MANUALLY',
    tagline: 'Inconclusive signals or insufficient global coverage'
  }
};

function renderVerdictInMessage(msgId, query, data) {
  const resultContainer = document.getElementById(`${msgId}-result-body`);
  if (!resultContainer) return;

  const verdict = data.verdict || 'UNVERIFIED';
  const cfg = VERDICT_CONFIG[verdict] || VERDICT_CONFIG.UNVERIFIED;

  const confPct = Math.round((data.confidence || 0) * 100);
  const truthPct = Math.round((data.truth_score || 0.5) * 100);
  const truthScoreStr = (data.truth_score !== undefined ? data.truth_score : 0.5).toFixed(2);
  const dominantLayer = (data.dominant_layer || 'Multi-Layer Synthesis').replace('Layer', 'L');

  // Layer details
  const ld = data.layer_details || {};
  const l1 = ld.layer1 || {};
  const l2 = ld.layer2 || {};
  const l3 = ld.layer3 || {};

  const l1Hint = (l1.verdict || 'unverified').toLowerCase();
  const l2Hint = (l2.verdict || 'unverified').toLowerCase();
  const l3Hint = (l3.verdict || 'uncertain').toLowerCase();

  // Sources
  const uniqueSources = [...new Set((data.sources || []).filter(Boolean))];

  resultContainer.innerHTML = `
    <!-- Verdict Banner -->
    <div class="verdict-banner ${cfg.cls}">
      <div class="verdict-header-row">
        <div class="verdict-badge-pill ${cfg.badgeCls}">
          <span>${cfg.icon}</span>
          <span>${cfg.label}</span>
        </div>
        <div class="verdict-meta-chips">
          <span class="verdict-meta-chip">⏱ ${data.elapsed || '—'}s</span>
          <span class="verdict-meta-chip">🎯 ${dominantLayer}</span>
        </div>
      </div>

      <!-- Meter Gauges -->
      <div class="verdict-meters-grid">
        <div class="meter-box">
          <div class="meter-header">
            <span>Confidence Level</span>
            <span class="meter-val">${confPct}%</span>
          </div>
          <div class="meter-track">
            <div class="meter-fill conf" style="width: ${confPct}%"></div>
          </div>
        </div>
        <div class="meter-box">
          <div class="meter-header">
            <span>Truth Metric</span>
            <span class="meter-val">${truthScoreStr} / 1.0</span>
          </div>
          <div class="meter-track">
            <div class="meter-fill truth" style="width: ${truthPct}%"></div>
          </div>
        </div>
      </div>

      <!-- Executive Summary -->
      <div class="verdict-summary-text">
        ${escapeHtml(data.summary || cfg.tagline)}
      </div>
    </div>

    <!-- 3 Verification Layers -->
    <div class="layers-grid">
      <!-- Layer 1 -->
      <div class="layer-mini-card">
        <div class="layer-mini-header">
          <span class="layer-title-text">📡 Layer 1: News Wire</span>
          <span class="layer-tag ${getBadgeClass(l1Hint)}">${l1Hint}</span>
        </div>
        <div class="layer-stat-row">
          <span>GDELT Articles</span>
          <span class="layer-stat-value">${l1.gdelt_articles ?? '—'}</span>
        </div>
        <div class="layer-stat-row">
          <span>Credibility Index</span>
          <span class="layer-stat-value">${l1.combined_score ?? '—'}</span>
        </div>
        <div class="layer-stat-row">
          <span>Wikipedia Match</span>
          <span class="layer-stat-value">${l1.wiki_page ? escapeHtml(l1.wiki_page) : 'None'}</span>
        </div>
      </div>

      <!-- Layer 2 -->
      <div class="layer-mini-card">
        <div class="layer-mini-header">
          <span class="layer-title-text">🔍 Layer 2: Fact Check</span>
          <span class="layer-tag ${getBadgeClass(l2Hint)}">${l2Hint}</span>
        </div>
        <div class="layer-stat-row">
          <span>Google Fact Check</span>
          <span class="layer-stat-value">${l2.google_fc_found ? '✓ Matched' : 'No claim record'}</span>
        </div>
        <div class="layer-stat-row">
          <span>Official Rating</span>
          <span class="layer-stat-value">${l2.google_fc_rating ? escapeHtml(l2.google_fc_rating) : '—'}</span>
        </div>
        <div class="layer-stat-row">
          <span>Publisher</span>
          <span class="layer-stat-value">${l2.google_fc_publisher ? escapeHtml(l2.google_fc_publisher) : '—'}</span>
        </div>
      </div>

      <!-- Layer 3 -->
      <div class="layer-mini-card">
        <div class="layer-mini-header">
          <span class="layer-title-text">🤖 Layer 3: BERT NLP</span>
          <span class="layer-tag ${getBadgeClass(l3Hint)}">${l3Hint}</span>
        </div>
        <div class="layer-stat-row">
          <span>Architecture</span>
          <span class="layer-stat-value">${l3.model ? escapeHtml(l3.model.replace('hamzab/', '').substring(0, 16)) : 'RoBERTa'}</span>
        </div>
        <div class="layer-stat-row">
          <span>Neural Truth</span>
          <span class="layer-stat-value">${l3.truth_score !== undefined ? l3.truth_score.toFixed(3) : '—'}</span>
        </div>
        <div class="layer-stat-row">
          <span>Model Confidence</span>
          <span class="layer-stat-value">${l3.confidence !== undefined ? Math.round(l3.confidence * 100) + '%' : '—'}</span>
        </div>
      </div>
    </div>

    <!-- Evidence Section -->
    ${(data.evidence && data.evidence.length > 0) ? `
      <div class="evidence-section">
        <div class="section-heading">
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
            <polyline points="9 11 12 14 22 4"></polyline>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
          </svg>
          Key Findings &amp; Evidence
        </div>
        <ul class="evidence-items-list">
          ${data.evidence.map(item => `
            <li class="evidence-item">
              <span class="evidence-bullet">•</span>
              <span>${escapeHtml(item)}</span>
            </li>
          `).join('')}
        </ul>
      </div>
    ` : ''}

    <!-- Citations / Sources -->
    ${uniqueSources.length > 0 ? `
      <div class="sources-section">
        <div class="section-heading">
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="2" y1="12" x2="22" y2="12"></line>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
          </svg>
          Verified Sources &amp; Citations (${uniqueSources.length})
        </div>
        <div class="sources-chips-wrap">
          ${uniqueSources.slice(0, 6).map(url => {
            const domain = extractDomain(url);
            return `
              <a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" class="source-citation-chip" title="${escapeHtml(url)}">
                <span>🔗</span>
                <span>${escapeHtml(domain)}</span>
              </a>
            `;
          }).join('')}
        </div>
      </div>
    ` : ''}

    <!-- Assistant Action Bar -->
    <div class="message-actions-bar">
      <button class="action-tool-btn" title="Copy answer" onclick="copyMessageText('${msgId}')">
        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
      </button>

      <button class="action-tool-btn" title="Read aloud" onclick="speakVerdict('${msgId}')">
        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
          <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>
        </svg>
      </button>

      <button class="action-tool-btn" title="Good response" onclick="handleFeedback(this, 'up')">
        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
        </svg>
      </button>

      <button class="action-tool-btn" title="Bad response" onclick="handleFeedback(this, 'down')">
        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
          <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
        </svg>
      </button>

      <button class="action-tool-btn" title="Re-check this claim" onclick="recheckClaim('${escapeHtml(query)}')">
        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
      </button>
    </div>
  `;
}

function renderErrorMessage(msgId, errorText) {
  const resultContainer = document.getElementById(`${msgId}-result-body`);
  if (!resultContainer) return;

  resultContainer.innerHTML = `
    <div class="verdict-banner fake">
      <div class="verdict-header-row">
        <div class="verdict-badge-pill fake">
          <span>⚠️</span>
          <span>Verification Error</span>
        </div>
      </div>
      <div class="verdict-summary-text">
        ${escapeHtml(errorText)}
      </div>
    </div>
  `;
}

// ── Actions & Interactivity ───────────────────────────────────────
function copyMessageText(msgId) {
  const msgEl = document.getElementById(msgId);
  if (!msgEl) return;
  const summaryEl = msgEl.querySelector('.verdict-summary-text');
  const badgeEl = msgEl.querySelector('.verdict-badge-pill');

  const textToCopy = `[FakeNews GPT Verification]\nVerdict: ${badgeEl ? badgeEl.textContent.trim() : ''}\nSummary: ${summaryEl ? summaryEl.textContent.trim() : ''}`;
  navigator.clipboard.writeText(textToCopy).then(() => {
    showToast('Copied verification summary to clipboard!');
  });
}

function speakVerdict(msgId) {
  const msgEl = document.getElementById(msgId);
  if (!msgEl) return;
  const summaryEl = msgEl.querySelector('.verdict-summary-text');
  const badgeEl = msgEl.querySelector('.verdict-badge-pill');
  if (summaryEl && badgeEl) {
    speakText(`${badgeEl.textContent.trim()}. ${summaryEl.textContent.trim()}`);
  }
}

function handleFeedback(btn, type) {
  btn.classList.toggle('active');
  showToast(type === 'up' ? 'Thanks for the feedback!' : 'Feedback noted. We will tune our weights.');
}

function recheckClaim(claim) {
  elements.promptTextarea.value = claim;
  elements.promptTextarea.dispatchEvent(new Event('input'));
  handleSendPrompt();
}

// ── History Persistence & Management ──────────────────────────────
function saveToHistory(query, result) {
  const item = {
    id: 'claim-' + Date.now(),
    query: query,
    verdict: result.verdict || 'UNVERIFIED',
    timestamp: Date.now(),
    data: result
  };

  // Add to top, max 25 items
  state.history.unshift(item);
  if (state.history.length > 25) state.history.pop();
  localStorage.setItem('fakenews_history', JSON.stringify(state.history));
  renderHistoryList();
}

function renderHistoryList() {
  const list = elements.historyList;
  list.innerHTML = '';

  if (state.history.length === 0) {
    list.appendChild(elements.historyEmpty);
    return;
  }

  state.history.forEach(item => {
    const div = document.createElement('div');
    div.className = 'history-item';
    div.id = item.id;
    div.title = item.query;

    const dotClass = getBadgeClass(item.verdict.toLowerCase());

    div.innerHTML = `
      <div class="history-item-content" onclick="loadHistoryItem('${item.id}')">
        <span class="history-dot ${dotClass}"></span>
        <span class="history-title">${escapeHtml(item.query)}</span>
      </div>
      <button class="history-delete-btn" title="Delete" onclick="deleteHistoryItem(event, '${item.id}')">
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    `;

    list.appendChild(div);
  });
}

function loadHistoryItem(id) {
  const item = state.history.find(h => h.id === id);
  if (!item) return;

  elements.heroScreen.style.display = 'none';
  elements.messagesStream.innerHTML = '';

  // Render user prompt
  renderUserMessage(item.query);

  // Render assistant completed response
  const msgId = `assistant-hist-${Date.now()}`;
  renderAssistantThinkingRow(msgId);
  finishThinkingAccordion(msgId, item.data.elapsed || '1.5');
  renderVerdictInMessage(msgId, item.query, item.data);

  // Highlight active
  document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
  const activeEl = document.getElementById(id);
  if (activeEl) activeEl.classList.add('active');

  toggleSidebar(false);
  scrollToBottom();
}

function deleteHistoryItem(e, id) {
  e.stopPropagation();
  state.history = state.history.filter(h => h.id !== id);
  localStorage.setItem('fakenews_history', JSON.stringify(state.history));
  renderHistoryList();
}

function clearHistory() {
  if (confirm('Clear all saved claims from history?')) {
    state.history = [];
    localStorage.removeItem('fakenews_history');
    renderHistoryList();
    showToast('Verification history cleared');
  }
}

// ── Modals & Share ────────────────────────────────────────────────
function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.add('open');
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.classList.remove('open');
}

function openShareModal() {
  if (!state.lastResult) {
    showToast('Verify a claim first before exporting.');
    return;
  }
  openModal('share-modal');
}

function copySessionSummary() {
  if (!state.lastResult) return;
  const res = state.lastResult;
  const md = `# FakeNews GPT Fact Check Report
**Claim:** "${res.query}"
**Verdict:** ${res.verdict}
**Confidence:** ${Math.round((res.confidence || 0) * 100)}%
**Truth Score:** ${(res.truth_score || 0.5).toFixed(2)}
**Dominant Layer:** ${res.dominant_layer || 'Multi-Layer'}

## Summary
${res.summary || ''}

## Evidence
${(res.evidence || []).map(e => '- ' + e).join('\n')}

---
*Generated by FakeNews GPT (3-Layer AI System)*`;

  navigator.clipboard.writeText(md).then(() => {
    closeModal('share-modal');
    showToast('Markdown summary copied to clipboard!');
  });
}

function downloadJSONReport() {
  if (!state.lastResult) return;
  const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(state.lastResult, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute('href', dataStr);
  downloadAnchor.setAttribute('download', `fakenews_gpt_${Date.now()}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
  closeModal('share-modal');
  showToast('JSON report downloaded');
}

// ── Utilities ─────────────────────────────────────────────────────
function scrollToBottom() {
  setTimeout(() => {
    elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
  }, 50);
}

function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span>💬</span><span>${escapeHtml(message)}</span>`;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 2800);
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return url.substring(0, 30);
  }
}

function getBadgeClass(hint) {
  if (['real', 'true'].includes(hint)) return 'real';
  if (['fake', 'contradiction', 'false'].includes(hint)) return 'fake';
  if (['mis', 'misleading', 'partial'].includes(hint)) return 'mis';
  return 'unver';
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
