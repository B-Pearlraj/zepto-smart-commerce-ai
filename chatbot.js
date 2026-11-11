/* ==========================================================
   Zepto Smart Commerce AI - floating document chatbot
   - Round avatar launcher with a green "online" dot (bottom-right)
   - Click it to open a chat box; ask questions about the documents
     the admin uploaded (answers come from POST /chatbot/ask)
   - Plain JavaScript, no dependencies. Safe to run more than once.
   ========================================================== */
(function () {
  "use strict";

  var host = window;
  if (host.ZeptoChatbot) { return; }

  var STORAGE_KEY = "zc_chat_v1";
  var MAX_STORED = 40;
  var MAX_HISTORY = 6;
  var REQUEST_TIMEOUT_MS = 90000;
  var RETRY_STATUSES = [502, 503, 504];
  var MAX_ATTEMPTS = 2;

  var DEFAULTS = {
    apiBase: "",
    theme: "dark",
    avatarUrl: "",
    title: "Zepto Assistant",
    subtitle: "Ask me about our documents",
    bottomOffset: 88,
    rightOffset: 24,
    welcome: "Hi! \uD83D\uDC4B I can answer questions from our uploaded documents. What would you like to know?",
    suggestions: ["What documents can you answer from?"]
  };

  var cfg = {};
  var messages = [];          // {role: "user"|"assistant", content, sources?, error?}
  var busy = false;
  var built = false;
  var els = {};
  var doc = document;

  // ---------------------------------------------------------
  // helpers
  // ---------------------------------------------------------
  function merge(target, source) {
    Object.keys(source || {}).forEach(function (k) {
      if (source[k] !== undefined && source[k] !== null) { target[k] = source[k]; }
    });
    return target;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Minimal, safe markdown: escapes everything first, then adds
  // **bold**, `code` and "- " / "* " / bullet lists.
  function renderText(text) {
    var lines = String(text || "").split(/\r?\n/);
    var html = "";
    var inList = false;

    function inline(s) {
      return esc(s)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    }

    lines.forEach(function (line) {
      var bullet = line.match(/^\s*(?:[-*\u2022])\s+(.*)$/);
      if (bullet) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += "<li>" + inline(bullet[1]) + "</li>";
        return;
      }
      if (inList) { html += "</ul>"; inList = false; }
      if (line.trim() === "") { html += "<br>"; return; }
      html += "<p>" + inline(line) + "</p>";
    });

    if (inList) { html += "</ul>"; }
    return html.replace(/(<br>)+$/, "");
  }

  function save() {
    try {
      var keep = messages.slice(-MAX_STORED);
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(keep));
    } catch (e) { /* storage may be blocked - ignore */ }
  }

  function load() {
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      if (Array.isArray(parsed)) { messages = parsed; }
    } catch (e) { messages = []; }
  }

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  // ---------------------------------------------------------
  // DOM
  // ---------------------------------------------------------
  function avatarMarkup(className) {
    if (cfg.avatarUrl) {
      return '<img class="' + className + '" alt="" src="' + esc(cfg.avatarUrl) + '">';
    }
    return '<div class="' + (className === "zc-avatar" ? "zc-avatar-fallback" : "zc-hav") + '">\u26A1</div>';
  }

  function build() {
    var root = doc.createElement("div");
    root.id = "zc-root";
    root.setAttribute("data-theme", cfg.theme);

    root.innerHTML =
      '<button type="button" class="zc-launcher" aria-label="Open chat assistant" aria-expanded="false">' +
        avatarMarkup("zc-avatar") +
        '<span class="zc-close-icon" aria-hidden="true">\u2715</span>' +
        '<span class="zc-dot" title="Online"></span>' +
      '</button>' +
      '<section class="zc-panel" role="dialog" aria-label="Chat assistant">' +
        '<div class="zc-header">' +
          avatarMarkup("zc-hav") +
          '<div class="zc-titles">' +
            '<p class="zc-title"></p>' +
            '<p class="zc-subtitle"></p>' +
          '</div>' +
          '<button type="button" class="zc-hbtn zc-clear" title="Clear chat" aria-label="Clear chat">\u21BB</button>' +
          '<button type="button" class="zc-hbtn zc-min" title="Close" aria-label="Close chat">\u2715</button>' +
        '</div>' +
        '<div class="zc-messages" aria-live="polite"></div>' +
        '<div class="zc-chips"></div>' +
        '<form class="zc-form" autocomplete="off">' +
          '<textarea class="zc-input" rows="1" maxlength="2000" placeholder="Ask about the documents..." aria-label="Your question"></textarea>' +
          '<button type="submit" class="zc-send" aria-label="Send">\u27A4</button>' +
        '</form>' +
        '<div class="zc-foot">Answers come from the uploaded documents</div>' +
      '</section>';

    doc.body.appendChild(root);

    els.root = root;
    els.launcher = root.querySelector(".zc-launcher");
    els.dot = root.querySelector(".zc-dot");
    els.panel = root.querySelector(".zc-panel");
    els.title = root.querySelector(".zc-title");
    els.subtitle = root.querySelector(".zc-subtitle");
    els.messages = root.querySelector(".zc-messages");
    els.chips = root.querySelector(".zc-chips");
    els.form = root.querySelector(".zc-form");
    els.input = root.querySelector(".zc-input");
    els.send = root.querySelector(".zc-send");

    els.launcher.addEventListener("click", toggle);
    root.querySelector(".zc-min").addEventListener("click", close);
    root.querySelector(".zc-clear").addEventListener("click", clearChat);

    els.form.addEventListener("submit", function (e) {
      e.preventDefault();
      submit();
    });

    els.input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        submit();
      }
    });

    els.input.addEventListener("input", autoGrow);

    doc.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && els.root.classList.contains("zc-open")) { close(); }
    });

    built = true;
  }

  function applyConfig() {
    els.root.setAttribute("data-theme", cfg.theme === "light" ? "light" : "dark");
    els.root.style.setProperty("--zc-bottom", (Number(cfg.bottomOffset) || 88) + "px");
    els.root.style.setProperty("--zc-right", (Number(cfg.rightOffset) || 24) + "px");
    els.title.textContent = cfg.title;
    els.subtitle.textContent = cfg.subtitle;

    // refresh avatars if the image changed
    var imgs = els.root.querySelectorAll("img.zc-avatar, img.zc-hav");
    Array.prototype.forEach.call(imgs, function (img) {
      if (cfg.avatarUrl && img.getAttribute("src") !== cfg.avatarUrl) {
        img.setAttribute("src", cfg.avatarUrl);
      }
    });
  }

  function autoGrow() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 110) + "px";
  }

  // ---------------------------------------------------------
  // rendering messages
  // ---------------------------------------------------------
  function scrollBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function messageNode(m) {
    var div = doc.createElement("div");
    var kind = m.error ? "zc-error" : (m.role === "user" ? "zc-user" : "zc-bot");
    div.className = "zc-msg " + kind;

    if (m.role === "user") {
      div.innerHTML = "<p>" + esc(m.content) + "</p>";
    } else {
      div.innerHTML = renderText(m.content);
    }

    if (m.sources && m.sources.length) {
      var wrap = doc.createElement("div");
      wrap.className = "zc-sources";
      m.sources.forEach(function (s) {
        var chip = doc.createElement("span");
        chip.className = "zc-source";
        chip.title = s.snippet || s.title;
        chip.textContent = "\uD83D\uDCC4 " + s.title;
        wrap.appendChild(chip);
      });
      div.appendChild(wrap);
    }
    return div;
  }

  function renderAll() {
    els.messages.innerHTML = "";

    var welcome = { role: "assistant", content: cfg.welcome };
    els.messages.appendChild(messageNode(welcome));

    messages.forEach(function (m) { els.messages.appendChild(messageNode(m)); });

    renderChips();
    scrollBottom();
  }

  function renderChips() {
    els.chips.innerHTML = "";
    if (messages.length || !cfg.suggestions || !cfg.suggestions.length) {
      els.chips.style.display = "none";
      return;
    }
    els.chips.style.display = "flex";
    cfg.suggestions.forEach(function (text) {
      var b = doc.createElement("button");
      b.type = "button";
      b.className = "zc-chip";
      b.textContent = text;
      b.addEventListener("click", function () { ask(text); });
      els.chips.appendChild(b);
    });
  }

  function showTyping() {
    var t = doc.createElement("div");
    t.className = "zc-typing";
    t.innerHTML = "<span></span><span></span><span></span>";
    els.messages.appendChild(t);
    scrollBottom();
    return t;
  }

  function showNote(text) {
    var n = doc.createElement("div");
    n.className = "zc-wake";
    n.textContent = text;
    els.messages.appendChild(n);
    scrollBottom();
    return n;
  }

  // ---------------------------------------------------------
  // open / close
  // ---------------------------------------------------------
  function open() {
    els.root.classList.add("zc-open");
    els.launcher.setAttribute("aria-expanded", "true");
    els.launcher.setAttribute("aria-label", "Close chat assistant");
    scrollBottom();
    checkStatus();
    setTimeout(function () { els.input.focus(); }, 60);
  }

  function close() {
    els.root.classList.remove("zc-open");
    els.launcher.setAttribute("aria-expanded", "false");
    els.launcher.setAttribute("aria-label", "Open chat assistant");
  }

  function toggle() {
    if (els.root.classList.contains("zc-open")) { close(); } else { open(); }
  }

  function clearChat() {
    messages = [];
    save();
    renderAll();
  }

  // ---------------------------------------------------------
  // network
  // ---------------------------------------------------------
  function apiUrl(path) {
    return String(cfg.apiBase || "").replace(/\/+$/, "") + path;
  }

  function checkStatus() {
    if (!cfg.apiBase) { return; }
    fetch(apiUrl("/chatbot/status"), { method: "GET" })
      .then(function (res) {
        els.dot.classList.toggle("zc-offline", !res.ok);
        els.dot.title = res.ok ? "Online" : "Unavailable";
      })
      .catch(function () {
        els.dot.classList.add("zc-offline");
        els.dot.title = "Waking up...";
      });
  }

  function postQuestion(question, history) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, REQUEST_TIMEOUT_MS);

    return fetch(apiUrl("/chatbot/ask"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, history: history }),
      signal: controller.signal
    }).then(function (res) {
      clearTimeout(timer);
      return res.text().then(function (text) {
        var data = {};
        try { data = text ? JSON.parse(text) : {}; } catch (e) { data = {}; }
        if (!res.ok) {
          var detail = data.detail;
          if (Array.isArray(detail)) { detail = detail.map(function (d) { return d.msg; }).join("; "); }
          var err = new Error(detail || ("Request failed (HTTP " + res.status + ")"));
          err.status = res.status;
          throw err;
        }
        return data;
      });
    }).catch(function (err) {
      clearTimeout(timer);
      throw err;
    });
  }

  // Retries while a sleeping Render service wakes up.
  function askWithRetry(question, history, onRetry) {
    var attempt = 0;

    function run() {
      attempt += 1;
      return postQuestion(question, history).catch(function (err) {
        var transient = err.name === "AbortError" ||
          err instanceof TypeError ||
          RETRY_STATUSES.indexOf(err.status) !== -1;

        if (transient && attempt < MAX_ATTEMPTS) {
          if (onRetry) { onRetry(attempt); }
          return sleep(2500).then(run);
        }
        throw err;
      });
    }
    return run();
  }

  // A no-cors request succeeds whenever the server is up, even if the
  // browser blocks reading the reply - so it tells "server down" apart
  // from "server up but chatbot/CORS not enabled".
  function diagnose() {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 8000);
    return fetch(apiUrl("/health"), { method: "GET", mode: "no-cors", signal: controller.signal })
      .then(function () {
        clearTimeout(timer);
        return "The server is online, but the chatbot service isn't responding. The backend probably needs to be redeployed - please tell the admin.";
      })
      .catch(function () {
        clearTimeout(timer);
        return "I couldn't reach the server. It may still be waking up (free hosting) - please try again in a minute.";
      });
  }

  // ---------------------------------------------------------
  // sending
  // ---------------------------------------------------------
  function submit() {
    var text = els.input.value.trim();
    if (!text) { return; }
    els.input.value = "";
    autoGrow();
    ask(text);
  }

  function setBusy(state) {
    busy = state;
    els.send.disabled = state;
    els.input.disabled = state;
    if (!state) { els.input.focus(); }
  }

  function ask(question) {
    if (busy || !question) { return; }
    if (!cfg.apiBase) {
      messages.push({ role: "assistant", content: "The chatbot is not connected to the backend yet.", error: true });
      renderAll();
      return;
    }

    var history = messages
      .filter(function (m) { return !m.error; })
      .slice(-MAX_HISTORY)
      .map(function (m) { return { role: m.role, content: m.content }; });

    messages.push({ role: "user", content: question });
    save();
    renderAll();

    setBusy(true);
    var typing = showTyping();
    var note = null;

    askWithRetry(question, history, function () {
      if (!note) { note = showNote("The server is waking up - this can take up to a minute..."); }
    }).then(function (data) {
      messages.push({
        role: "assistant",
        content: data.answer || "Sorry, I couldn't generate an answer.",
        sources: data.sources || []
      });
      els.dot.classList.remove("zc-offline");
    }).catch(function (err) {
      var msg;
      if (err.status === 429) {
        msg = "You're asking quickly - please wait a few seconds and try again.";
      } else if (err.status === 404 || err.status === 503) {
        msg = "The chatbot service isn't available on the server yet. Please ask the admin to check the backend deployment.";
        els.dot.classList.add("zc-offline");
      } else if (err.name === "AbortError" || err instanceof TypeError || RETRY_STATUSES.indexOf(err.status) !== -1) {
        els.dot.classList.add("zc-offline");
        return diagnose().then(function (m) {
          messages.push({ role: "assistant", content: m, error: true });
        });
      } else {
        msg = err.message || "Something went wrong. Please try again.";
      }
      messages.push({ role: "assistant", content: msg, error: true });
    }).then(function () {
      if (typing.parentNode) { typing.parentNode.removeChild(typing); }
      if (note && note.parentNode) { note.parentNode.removeChild(note); }
      save();
      renderAll();
      setBusy(false);
    });
  }

  // ---------------------------------------------------------
  // public API
  // ---------------------------------------------------------
  function init(userConfig) {
    cfg = merge(merge({}, DEFAULTS), userConfig || {});

    if (!built) {
      load();
      build();
      renderAll();
    }
    applyConfig();
  }

  host.ZeptoChatbot = { init: init, open: function () { if (built) { open(); } }, close: function () { if (built) { close(); } } };

  // Auto-start when a config was provided before this script loaded.
  if (host.__ZC_CONFIG__) { init(host.__ZC_CONFIG__); }
})();
