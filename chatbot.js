/* ============================================================
   Zepto Smart Commerce AI - floating document chat box

   Load it with one <script> tag (the Streamlit app does this for you):

     <script src="https://zepto-smart-commerce-ai.onrender.com/widget/chatbot.js"
             data-theme="dark"></script>

   Optional settings - either data-* attributes on the script tag, or
   window.ZEPTO_CHATBOT_CONFIG = { ... } set before the script loads:

     api          backend base URL      (default: the site the script came from)
     theme        "dark" | "light"      (default: dark)
     title        header title          (default: Document Assistant)
     logo         round logo image URL  (default: <api>/widget/chat-logo.png,
                                         falls back to a purple lightning icon)
     bottom       distance from the bottom edge in px (default 24)
     welcome      first message
     suggestions  array of quick-question buttons (default none)

   JavaScript API:  ZeptoChatbot.open()  .close()  .setTheme('light')
   ============================================================ */
(function () {
    'use strict';

    if (window.ZeptoChatbot && window.ZeptoChatbot.__loaded) { return; }
    if (document.getElementById('zchat-root')) { return; }

    var script = document.currentScript;

    function attr(name) {
        return script ? script.getAttribute('data-' + name) : null;
    }

    var userCfg = window.ZEPTO_CHATBOT_CONFIG || {};

    function setting(name, fallback) {
        if (userCfg[name] !== undefined && userCfg[name] !== null && userCfg[name] !== '') { return userCfg[name]; }
        var fromAttr = attr(name);
        return (fromAttr !== null && fromAttr !== '') ? fromAttr : fallback;
    }

    var scriptUrl = null;
    try { scriptUrl = script && script.src ? new URL(script.src) : null; } catch (e) { scriptUrl = null; }

    var API = String(setting('api', scriptUrl ? scriptUrl.origin : '')).replace(/\/+$/, '');
    var VERSION = scriptUrl ? scriptUrl.search : '';
    var TITLE = setting('title', 'Document Assistant');
    var LOGO = setting('logo', API + '/widget/chat-logo.png');
    var BOTTOM = parseInt(setting('bottom', '24'), 10);
    var WELCOME = setting('welcome',
        'Hi! 👋 I\'m the Zepto document assistant. Ask me anything about the uploaded documents and I\'ll answer from them.');
    var SUGGESTIONS = Array.isArray(userCfg.suggestions) ? userCfg.suggestions : [];

    var STORAGE_KEY = 'zchat:v1';
    var MAX_LEN = 1000;
    var REQUEST_TIMEOUT_MS = 100000;   // a sleeping Render server can need ~60 s to wake up

    // ---------- load the stylesheet ----------
    if (!document.getElementById('zchat-css')) {
        var link = document.createElement('link');
        link.id = 'zchat-css';
        link.rel = 'stylesheet';
        link.href = API + '/widget/chatbot.css' + VERSION;
        document.head.appendChild(link);
    }

    // ---------- tiny helpers ----------
    function el(tag, className, props) {
        var node = document.createElement(tag);
        if (className) { node.className = className; }
        if (props) {
            Object.keys(props).forEach(function (key) {
                if (key === 'text') { node.textContent = props[key]; }
                else { node.setAttribute(key, props[key]); }
            });
        }
        return node;
    }

    function escapeHtml(text) {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;')
                   .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function inline(text) {
        return escapeHtml(text)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    }

    // very small, safe markdown: **bold**, `code`, bullet / numbered lists
    function formatBot(text) {
        var html = '';
        var inList = false;

        text.split('\n').forEach(function (line) {
            var item = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);

            if (item) {
                if (!inList) { html += '<ul>'; inList = true; }
                html += '<li>' + inline(item[1]) + '</li>';
            } else {
                if (inList) { html += '</ul>'; inList = false; }
                html += inline(line) + '\n';
            }
        });

        if (inList) { html += '</ul>'; }
        return html.replace(/\n+$/, '');
    }

    function logoNode() {
        var wrap = el('div', 'zchat-logo-fallback', { text: '⚡' });

        if (LOGO) {
            var img = el('img', 'zchat-logo', { alt: '', src: LOGO });
            img.addEventListener('error', function () {
                if (img.parentNode) { img.parentNode.replaceChild(el('div', 'zchat-logo-fallback', { text: '⚡' }), img); }
            });
            return img;
        }
        return wrap;
    }

    // ---------- state ----------
    var messages = [];        // [{ role: 'user' | 'assistant', content }]
    var busy = false;
    var typingNode = null;
    var state = 'online';     // online | waking | offline
    var statusTries = 0;

    function loadSaved() {
        try {
            var raw = window.sessionStorage.getItem(STORAGE_KEY);
            var parsed = raw ? JSON.parse(raw) : [];
            if (Array.isArray(parsed)) { messages = parsed.slice(-60); }
        } catch (e) { messages = []; }
    }

    function save() {
        try { window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-60))); } catch (e) { /* ignore */ }
    }

    // ---------- build the DOM ----------
    var root = el('div', '', { id: 'zchat-root' });
    root.setAttribute('data-theme', setting('theme', 'dark') === 'light' ? 'light' : 'dark');
    root.setAttribute('data-state', 'online');
    if (!isNaN(BOTTOM)) { root.style.setProperty('--z-bottom', BOTTOM + 'px'); }

    // launcher
    var launcher = el('button', 'zchat-launcher', { type: 'button', 'aria-label': 'Open chat', title: 'Chat with us' });
    launcher.appendChild(logoNode());
    launcher.appendChild(el('span', 'zchat-dot'));

    // panel
    var panel = el('section', 'zchat-panel', { role: 'dialog', 'aria-label': TITLE });

    var header = el('div', 'zchat-header');
    var avatar = el('div', 'zchat-avatar');
    avatar.appendChild(logoNode());
    avatar.appendChild(el('span', 'zchat-dot'));
    var titleBox = el('div', 'zchat-title');
    titleBox.appendChild(el('strong', '', { text: TITLE }));
    var subtitle = el('span', '', { text: 'Online · answers from uploaded documents' });
    titleBox.appendChild(subtitle);
    var clearBtn = el('button', 'zchat-icon-btn', { type: 'button', 'aria-label': 'Clear chat', title: 'Clear chat', text: '🗑' });
    var closeBtn = el('button', 'zchat-icon-btn', { type: 'button', 'aria-label': 'Close chat', title: 'Close', text: '✕' });
    header.appendChild(avatar);
    header.appendChild(titleBox);
    header.appendChild(clearBtn);
    header.appendChild(closeBtn);

    var list = el('div', 'zchat-messages', { 'aria-live': 'polite' });
    var chips = el('div', 'zchat-chips');

    var form = el('form', 'zchat-form', { autocomplete: 'off' });
    var input = el('textarea', 'zchat-input', {
        rows: '1', maxlength: String(MAX_LEN),
        placeholder: 'Ask about the documents…', 'aria-label': 'Your question'
    });
    var sendBtn = el('button', 'zchat-send', { type: 'submit', 'aria-label': 'Send' });
    sendBtn.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.4 20.4 21 12 3.4 3.6 3.4 10l12 2-12 2z"/></svg>';
    form.appendChild(input);
    form.appendChild(sendBtn);

    var foot = el('div', 'zchat-foot', { text: 'AI answers come only from the uploaded documents.' });

    panel.appendChild(header);
    panel.appendChild(list);
    panel.appendChild(chips);
    panel.appendChild(form);
    panel.appendChild(foot);

    root.appendChild(panel);
    root.appendChild(launcher);

    // ---------- rendering ----------
    function scrollDown() { list.scrollTop = list.scrollHeight; }

    function renderMessage(role, text, opts) {
        opts = opts || {};
        var bubble = el('div', 'zchat-msg ' + (role === 'user' ? 'zchat-user' : 'zchat-bot'));

        if (role === 'user') {
            bubble.textContent = text;
        } else {
            bubble.innerHTML = formatBot(text);
            if (opts.error) { bubble.className += ' zchat-error'; }
        }

        if (opts.sources && opts.sources.length) {
            var box = el('div', 'zchat-sources');
            opts.sources.forEach(function (name) {
                box.appendChild(el('span', 'zchat-source', { text: '📄 ' + name, title: name }));
            });
            bubble.appendChild(box);
        }

        if (opts.retryText) {
            var retry = el('button', 'zchat-retry', { type: 'button', text: 'Try again' });
            retry.addEventListener('click', function () {
                if (busy) { return; }
                bubble.remove();
                ask(opts.retryText, true);
            });
            bubble.appendChild(retry);
        }

        list.appendChild(bubble);
        scrollDown();
        return bubble;
    }

    function showTyping() {
        typingNode = el('div', 'zchat-typing', { 'aria-label': 'Assistant is typing' });
        typingNode.innerHTML = '<i></i><i></i><i></i>';
        list.appendChild(typingNode);
        scrollDown();
    }

    function hideTyping() {
        if (typingNode && typingNode.parentNode) { typingNode.parentNode.removeChild(typingNode); }
        typingNode = null;
    }

    function renderChips() {
        chips.innerHTML = '';
        if (messages.length || !SUGGESTIONS.length) { return; }

        SUGGESTIONS.slice(0, 4).forEach(function (question) {
            var chip = el('button', 'zchat-chip', { type: 'button', text: String(question) });
            chip.addEventListener('click', function () { ask(String(question)); });
            chips.appendChild(chip);
        });
    }

    function renderAll() {
        list.innerHTML = '';
        renderMessage('assistant', WELCOME);
        messages.forEach(function (m) { renderMessage(m.role, m.content); });
        renderChips();
    }

    function setBusy(value) {
        busy = value;
        sendBtn.disabled = value;
    }

    // ---------- backend calls ----------
    function fetchJson(path, options, timeoutMs) {
        var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
        var timer = controller ? setTimeout(function () { controller.abort(); }, timeoutMs) : null;
        options = options || {};
        if (controller) { options.signal = controller.signal; }

        return fetch(API + path, options).then(function (response) {
            return response.json().catch(function () { return {}; }).then(function (data) {
                if (!response.ok) {
                    var detail = data && data.detail;
                    var message = typeof detail === 'string' ? detail : 'Request failed (HTTP ' + response.status + ').';
                    var error = new Error(message);
                    error.status = response.status;
                    throw error;
                }
                return data;
            });
        }).finally(function () { if (timer) { clearTimeout(timer); } });
    }

    function setState(next) {
        state = next;
        root.setAttribute('data-state', next);
        subtitle.textContent =
            next === 'online' ? 'Online · answers from uploaded documents' :
            next === 'waking' ? 'Waking up… this can take up to a minute' :
                                'Offline · please try again shortly';
    }

    function checkStatus() {
        return fetchJson('/api/chat/status', { method: 'GET' }, 10000).then(function () {
            statusTries = 0;
            setState('online');
        }).catch(function (error) {
            setState(error && error.name === 'AbortError' ? 'waking' : 'offline');

            // keep trying quietly while a sleeping server starts up
            if (statusTries < 8) {
                statusTries += 1;
                setTimeout(checkStatus, 6000);
            }
        });
    }

    function friendlyError(error) {
        if (error && error.status && error.status < 500 && error.message) { return error.message; }
        if (error && error.name === 'AbortError') {
            return 'The server is taking too long to answer. It may be waking up - please try again in a moment.';
        }
        if (error && error.status) {
            return error.message || 'The assistant is temporarily unavailable. Please try again in a moment.';
        }
        return 'I couldn\'t reach the server. It may be waking up - please try again in a few seconds.';
    }

    function ask(text, isRetry) {
        text = String(text || '').trim().slice(0, MAX_LEN);
        if (!text || busy) { return; }

        // history sent to the server = earlier turns only
        var earlier = isRetry ? messages.slice(0, -1) : messages;   // on retry the question is already the last message
        var history = earlier.slice(-6).map(function (m) { return { role: m.role, content: m.content }; });

        if (!isRetry) {
            messages.push({ role: 'user', content: text });
            renderMessage('user', text);
        }
        chips.innerHTML = '';
        save();

        setBusy(true);
        showTyping();

        fetchJson('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: text, history: history })
        }, REQUEST_TIMEOUT_MS).then(function (data) {
            hideTyping();
            var answer = (data && data.answer) || 'Sorry, I could not find an answer.';
            messages.push({ role: 'assistant', content: answer });
            save();
            renderMessage('assistant', answer, { sources: data.sources || [] });
            setState('online');
        }).catch(function (error) {
            hideTyping();
            renderMessage('assistant', friendlyError(error), {
                error: true,
                retryText: (error && error.status && error.status < 500) ? null : text
            });
            if (!error || !error.status || error.status >= 500) { statusTries = 0; checkStatus(); }
        }).then(function () {
            setBusy(false);
            input.focus();
        });
    }

    // ---------- open / close ----------
    function open() {
        root.classList.add('zchat-open');
        launcher.setAttribute('aria-expanded', 'true');
        scrollDown();
        setTimeout(function () { input.focus(); }, 50);
        if (state !== 'online') { statusTries = 0; checkStatus(); }
    }

    function close() {
        root.classList.remove('zchat-open');
        launcher.setAttribute('aria-expanded', 'false');
        launcher.focus();
    }

    function resetChat() {
        if (busy) { return; }
        messages = [];
        save();
        renderAll();
    }

    // ---------- events ----------
    launcher.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    clearBtn.addEventListener('click', resetChat);

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        var text = input.value;
        input.value = '';
        input.style.height = 'auto';
        ask(text);
    });

    input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event('submit', { cancelable: true }));
        }
        event.stopPropagation();       // keep the host page's keyboard shortcuts out of the box
    });

    input.addEventListener('input', function () {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 110) + 'px';
    });

    root.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && root.classList.contains('zchat-open')) { close(); }
    });

    // ---------- start ----------
    loadSaved();
    renderAll();
    document.body.appendChild(root);
    checkStatus();                      // also wakes a sleeping backend

    window.ZeptoChatbot = {
        __loaded: true,
        open: open,
        close: close,
        setTheme: function (theme) { root.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark'); }
    };
})();
