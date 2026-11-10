/* ==========================================================================
   AI Assistant chat widget (vanilla JS, no dependencies).

   Add to any page, just before </body>:

     <link rel="stylesheet" href="chatbot.css">
     <script src="chatbot.js" defer
             data-api="https://YOUR-ASSISTANT-SERVICE.onrender.com"
             data-logo="images/logo.png"></script>

   Optional attributes on the <script> tag:
     data-title="AI Assistant"        header title
     data-welcome="Hi! ..."           first message
     data-suggestions="Q1|Q2|Q3"      starter question chips (use | between)
     data-accent="#6d5efc"            accent colour
     data-theme="dark|light|auto"     force a theme (default: follow the page)

   Everything is created inside #pa-root, so the page's own HTML, CSS and
   JavaScript are untouched.
   ========================================================================== */
(function () {
  'use strict';

  if (window.__paLoaded) return;
  window.__paLoaded = true;

  // ---------------------------------------------------------------- config
  var script = document.currentScript || document.querySelector('script[src*="chatbot.js"]');
  var data = (script && script.dataset) || {};

  var config = {
    api: (data.api || '').replace(/\/+$/, ''),
    logo: data.logo || '',
    title: data.title || 'AI Assistant',
    welcome:
      data.welcome ||
      "Hi! I'm the AI Assistant. Ask me about projects, technologies, professional experience or services.",
    suggestions: data.suggestions
      ? data.suggestions.split('|').map(function (s) { return s.trim(); }).filter(Boolean)
      : ['What projects have you developed?', 'What technologies have you worked with?', 'What services do you offer?'],
    accent: data.accent || '',
    theme: data.theme || 'auto'
  };

  var STORAGE_KEY = 'pa-chat:v1';
  var MAX_INPUT = 600;
  var REQUEST_TIMEOUT_MS = 75000;
  var SLOW_NOTICE_MS = 6000;

  var messages = [];     // {role: 'user'|'assistant', content, sources?}
  var sending = false;
  var warmedUp = false;

  // ---------------------------------------------------------------- helpers
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // Tiny, safe markdown: **bold**, `code`, "- " bullets, auto-linked http(s) URLs.
  // All text is HTML-escaped first, so model output can never inject markup.
  function inline(text) {
    var s = escapeHtml(text);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(https?:\/\/[^\s<]*[^\s<.,;:!?)\]])/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    return s;
  }

  function renderMarkdown(text) {
    var html = '';
    var inList = false;
    var paragraph = [];

    function flushParagraph() {
      if (paragraph.length) { html += '<p>' + paragraph.join('<br>') + '</p>'; paragraph = []; }
    }
    function closeList() { if (inList) { html += '</ul>'; inList = false; } }

    String(text).replace(/\r/g, '').split('\n').forEach(function (raw) {
      var line = raw.trim();
      var bullet = line.match(/^[-*\u2022]\s+(.*)$/);

      if (!line) { flushParagraph(); closeList(); return; }

      if (bullet) {
        flushParagraph();
        if (!inList) { html += '<ul>'; inList = true; }
        html += '<li>' + inline(bullet[1]) + '</li>';
      } else {
        closeList();
        paragraph.push(inline(line.replace(/^#{1,6}\s+/, '')));
      }
    });

    flushParagraph();
    closeList();
    return html;
  }

  var ICONS = {
    send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>',
    reset: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/></svg>',
    logo: '<svg class="pa-fallback-logo" viewBox="0 0 48 48" aria-hidden="true"><rect width="48" height="48" rx="24" fill="#6d5efc"/><path d="M24 11l3.2 8.8L36 23l-8.8 3.2L24 35l-3.2-8.8L12 23l8.8-3.2z" fill="#fff"/></svg>'
  };

  function logoNode() {
    var holder = el('span');
    holder.style.display = 'contents';

    if (!config.logo) { holder.innerHTML = ICONS.logo; return holder; }

    var img = new Image();
    img.src = config.logo;
    img.alt = '';
    img.decoding = 'async';
    img.addEventListener('error', function () { holder.innerHTML = ICONS.logo; });
    holder.appendChild(img);
    return holder;
  }

  // ---------------------------------------------------------------- state persistence
  function saveState() {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-30))); } catch (e) { /* storage blocked */ }
  }

  function loadState() {
    try {
      var saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]');
      if (Array.isArray(saved)) {
        messages = saved.filter(function (m) {
          return m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string';
        });
      }
    } catch (e) { messages = []; }
  }

  // ---------------------------------------------------------------- DOM
  var root = el('div');
  root.id = 'pa-root';

  var launcher = el('button', 'pa-launcher');
  launcher.type = 'button';
  launcher.setAttribute('aria-label', 'Open ' + config.title);
  launcher.appendChild(logoNode());
  launcher.appendChild(el('span', 'pa-dot'));

  var panel = el('section', 'pa-panel');
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', config.title);

  var header = el('div', 'pa-header');
  var avatar = el('div', 'pa-avatar');
  avatar.appendChild(logoNode());
  avatar.appendChild(el('span', 'pa-dot'));
  var titles = el('div', 'pa-titles');
  titles.appendChild(el('div', 'pa-title', config.title));
  var statusLine = el('div', 'pa-status', 'Online');
  titles.appendChild(statusLine);

  var resetBtn = el('button', 'pa-icon-btn');
  resetBtn.type = 'button';
  resetBtn.title = 'New conversation';
  resetBtn.setAttribute('aria-label', 'Start a new conversation');
  resetBtn.innerHTML = ICONS.reset;

  var closeBtn = el('button', 'pa-icon-btn');
  closeBtn.type = 'button';
  closeBtn.title = 'Close';
  closeBtn.setAttribute('aria-label', 'Close chat');
  closeBtn.innerHTML = ICONS.close;

  header.appendChild(avatar);
  header.appendChild(titles);
  header.appendChild(resetBtn);
  header.appendChild(closeBtn);

  var list = el('div', 'pa-messages');
  list.setAttribute('role', 'log');
  list.setAttribute('aria-live', 'polite');

  var form = el('form', 'pa-composer');
  var input = el('textarea', 'pa-input');
  input.rows = 1;
  input.maxLength = MAX_INPUT;
  input.placeholder = 'Ask about projects, skills, services...';
  input.setAttribute('aria-label', 'Your question');
  var sendBtn = el('button', 'pa-send');
  sendBtn.type = 'submit';
  sendBtn.setAttribute('aria-label', 'Send message');
  sendBtn.innerHTML = ICONS.send;
  form.appendChild(input);
  form.appendChild(sendBtn);

  var footer = el('div', 'pa-footer', 'AI answers come from uploaded documents and may be incomplete.');

  panel.appendChild(header);
  panel.appendChild(list);
  panel.appendChild(form);
  panel.appendChild(footer);
  root.appendChild(panel);
  root.appendChild(launcher);

  // ---------------------------------------------------------------- rendering
  function scrollToBottom() { list.scrollTop = list.scrollHeight; }

  function addBubble(role, content, opts) {
    opts = opts || {};
    var bubble = el('div', 'pa-msg ' + (role === 'user' ? 'pa-user' : 'pa-bot') + (opts.error ? ' pa-error' : ''));

    if (role === 'user') {
      bubble.textContent = content;
    } else {
      bubble.innerHTML = renderMarkdown(content);
      if (opts.sources && opts.sources.length) {
        bubble.appendChild(el('div', 'pa-sources', 'Source: ' + opts.sources.join(', ')));
      }
    }

    list.appendChild(bubble);
    scrollToBottom();
    return bubble;
  }

  function showChips() {
    if (!config.suggestions.length) return;
    var wrap = el('div', 'pa-chips');
    wrap.setAttribute('data-pa-chips', '1');

    config.suggestions.forEach(function (text) {
      var chip = el('button', 'pa-chip', text);
      chip.type = 'button';
      chip.addEventListener('click', function () { ask(text); });
      wrap.appendChild(chip);
    });

    list.appendChild(wrap);
  }

  function removeChips() {
    var chips = list.querySelector('[data-pa-chips]');
    if (chips) chips.remove();
  }

  function renderAll() {
    list.replaceChildren();
    addBubble('assistant', config.welcome);

    messages.forEach(function (m) {
      addBubble(m.role, m.content, { sources: m.sources });
    });

    if (!messages.length) showChips();
  }

  function showTyping() {
    var bubble = el('div', 'pa-msg pa-bot');
    var dots = el('div', 'pa-typing');
    dots.setAttribute('aria-label', 'The assistant is typing');
    dots.appendChild(el('span'));
    dots.appendChild(el('span'));
    dots.appendChild(el('span'));
    bubble.appendChild(dots);
    list.appendChild(bubble);
    scrollToBottom();
    return bubble;
  }

  // ---------------------------------------------------------------- networking
  function apiUrl(path) { return config.api + path; }

  function warmUp() {
    if (warmedUp) return;
    warmedUp = true;
    // Wakes a sleeping Render instance while the visitor is still typing.
    try { fetch(apiUrl('/health'), { mode: 'cors', cache: 'no-store' }).catch(function () {}); } catch (e) {}
  }

  function postChat(payload, signal) {
    return fetch(apiUrl('/api/chat'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: signal
    });
  }

  function friendlyError(status, detail) {
    if (detail) return detail;
    if (status === 429) return "You're sending messages too quickly. Please wait a moment.";
    if (status === 503) return 'The assistant is temporarily unavailable. Please try again shortly.';
    return 'Something went wrong. Please try again.';
  }

  async function ask(text) {
    text = String(text || '').replace(/\s+/g, ' ').trim();
    if (!text || sending) return;

    if (!config.api && !/^https?:/i.test(location.protocol)) {
      addBubble('assistant', 'The assistant is not configured (missing data-api on the script tag).', { error: true });
      return;
    }

    sending = true;
    sendBtn.disabled = true;
    input.value = '';
    autosize();
    removeChips();

    var history = messages.slice(-6).map(function (m) {
      return { role: m.role, content: m.content.slice(0, 1000) };
    });

    messages.push({ role: 'user', content: text });
    addBubble('user', text);
    saveState();

    var typing = showTyping();
    var slowNote = null;
    var slowTimer = setTimeout(function () {
      slowNote = el('div', 'pa-note', 'The assistant is waking up. The first reply can take up to a minute.');
      typing.appendChild(slowNote);
      scrollToBottom();
    }, SLOW_NOTICE_MS);

    var payload = { message: text.slice(0, MAX_INPUT), history: history };

    try {
      var response;
      var controller = new AbortController();
      var timeout = setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS);

      try {
        response = await postChat(payload, controller.signal);
      } catch (networkError) {
        if (networkError && networkError.name === 'AbortError') throw networkError;
        // One quick retry: covers a connection dropped while the server was waking.
        await new Promise(function (r) { setTimeout(r, 1500); });
        response = await postChat(payload, controller.signal);
      } finally {
        clearTimeout(timeout);
      }

      var body = null;
      try { body = await response.json(); } catch (e) { body = null; }

      typing.remove();

      if (!response.ok) {
        addBubble('assistant', friendlyError(response.status, body && typeof body.detail === 'string' ? body.detail : ''), { error: true });
      } else {
        var answer = (body && body.answer) || 'Sorry, I did not receive an answer.';
        var sources = (body && body.sources) || [];
        messages.push({ role: 'assistant', content: answer, sources: sources });
        addBubble('assistant', answer, { sources: sources });
      }
    } catch (error) {
      typing.remove();
      var timedOut = error && error.name === 'AbortError';
      addBubble(
        'assistant',
        timedOut
          ? 'The assistant took too long to respond. Please try again.'
          : "I couldn't reach the assistant. Check your connection and try again.",
        { error: true }
      );
    } finally {
      clearTimeout(slowTimer);
      sending = false;
      sendBtn.disabled = !input.value.trim();
      saveState();
      if (root.classList.contains('pa-open')) input.focus();
    }
  }

  // ---------------------------------------------------------------- open / close
  var previousBodyOverflow = '';
  var mobileQuery = window.matchMedia ? window.matchMedia('(max-width: 520px)') : { matches: false };

  function openChat() {
    root.classList.add('pa-open');
    launcher.setAttribute('aria-expanded', 'true');
    warmUp();
    if (mobileQuery.matches) {
      previousBodyOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
    }
    scrollToBottom();
    setTimeout(function () { input.focus(); }, 50);
  }

  function closeChat() {
    root.classList.remove('pa-open');
    launcher.setAttribute('aria-expanded', 'false');
    if (mobileQuery.matches) document.body.style.overflow = previousBodyOverflow;
    launcher.focus();
  }

  launcher.addEventListener('click', openChat);
  launcher.addEventListener('pointerenter', warmUp);
  launcher.addEventListener('focus', warmUp);
  closeBtn.addEventListener('click', closeChat);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && root.classList.contains('pa-open')) closeChat();
  });

  resetBtn.addEventListener('click', function () {
    if (sending) return;
    messages = [];
    saveState();
    renderAll();
    input.focus();
  });

  // ---------------------------------------------------------------- composer behaviour
  function autosize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  }

  input.addEventListener('input', function () {
    autosize();
    sendBtn.disabled = sending || !input.value.trim();
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    ask(input.value);
  });

  // ---------------------------------------------------------------- theme: follow the host page
  function luminance(color) {
    var m = String(color).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    var p = m[1].split(/[,\s/]+/).filter(Boolean).map(parseFloat);
    if (p.length >= 4 && p[3] === 0) return null; // transparent
    return (0.2126 * p[0] + 0.7152 * p[1] + 0.0722 * p[2]) / 255;
  }

  function detectTheme() {
    if (config.theme === 'dark' || config.theme === 'light') return config.theme;

    var targets = [document.body, document.documentElement];
    for (var i = 0; i < targets.length; i++) {
      if (!targets[i]) continue;
      var l = luminance(getComputedStyle(targets[i]).backgroundColor);
      if (l !== null) return l < 0.5 ? 'dark' : 'light';
    }
    return window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  function applyTheme() { root.setAttribute('data-pa-theme', detectTheme()); }

  var themeTimer = null;
  function scheduleTheme() {
    clearTimeout(themeTimer);
    themeTimer = setTimeout(function () { applyTheme(); setTimeout(applyTheme, 450); }, 60);
  }

  // ---------------------------------------------------------------- start
  function start() {
    if (config.accent) root.style.setProperty('--pa-accent', config.accent);

    loadState();
    renderAll();
    sendBtn.disabled = true;
    document.body.appendChild(root);
    applyTheme();

    if (window.MutationObserver) {
      var observer = new MutationObserver(scheduleTheme);
      observer.observe(document.documentElement, { attributes: true });
      observer.observe(document.body, { attributes: true });
    }
    if (window.matchMedia) {
      var mq = matchMedia('(prefers-color-scheme: light)');
      if (mq.addEventListener) mq.addEventListener('change', scheduleTheme);
    }
    window.addEventListener('load', scheduleTheme);

    window.PearlAssistant = { open: openChat, close: closeChat };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
