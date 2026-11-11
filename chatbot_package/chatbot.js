/* ======================================================================
   Zepto Smart Commerce AI - document chatbot widget

   Add to ANY web page:

     <script>
       window.ZEPTO_CHATBOT_CONFIG = {
         apiBase: "https://zepto-smart-commerce-ai.onrender.com"
       };
     </script>
     <script src="https://zepto-smart-commerce-ai.onrender.com/chatbot/chatbot.js"></script>

   Optional settings (all have defaults):
     apiBase       base URL of the FastAPI backend
     title         header title
     subtitle      text under the title
     avatarUrl     image for the round button / header (default: built-in)
     greeting      first message from the bot
     placeholder   input placeholder
     suggestions   ["Question 1", "Question 2"]  quick-reply chips
     position      "right" | "left"
     theme         "light" | "dark" | "auto"
     offsetBottom  px from the bottom edge (default 24)
     offsetSide    px from the side edge (default 24)
     loadCss       false if you already included chatbot.css yourself

   Small API:  ZeptoChatbot.open()  .close()  .toggle()  .clear()
   ====================================================================== */

(function () {
  "use strict";

  if (window.__zeptoChatbotLoaded) {
    return;
  }
  window.__zeptoChatbotLoaded = true;

  // ------------------------------------------------------------------
  // Configuration
  // ------------------------------------------------------------------

  var thisScript = document.currentScript;
  var scriptBase = "";

  if (thisScript && thisScript.src) {
    scriptBase = thisScript.src.replace(/\/chatbot\/chatbot\.js(\?.*)?$/, "");
  }

  // 64x64 friendly assistant face, used when no avatarUrl is given.
  var DEFAULT_AVATAR =
    "data:image/svg+xml;utf8," +
    encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">' +
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0" stop-color="#a855f7"/><stop offset="1" stop-color="#6e1fd1"/>' +
        "</linearGradient></defs>" +
        '<rect width="64" height="64" fill="#0b0d1e"/>' +
        '<rect x="10" y="14" width="44" height="38" rx="14" fill="url(#g)"/>' +
        '<rect x="30" y="6" width="4" height="9" rx="2" fill="#a855f7"/>' +
        '<circle cx="32" cy="6" r="3.5" fill="#12b76a"/>' +
        '<circle cx="24" cy="31" r="4.5" fill="#fff"/>' +
        '<circle cx="40" cy="31" r="4.5" fill="#fff"/>' +
        '<circle cx="25" cy="32" r="2" fill="#161119"/>' +
        '<circle cx="41" cy="32" r="2" fill="#161119"/>' +
        '<path d="M24 42c3 3.5 13 3.5 16 0" stroke="#fff" stroke-width="3" ' +
        'stroke-linecap="round" fill="none"/>' +
        "</svg>"
    );

  var defaults = {
    apiBase: scriptBase,
    title: "Document Assistant",
    subtitle: "Online - ask me about our documents",
    avatarUrl: DEFAULT_AVATAR,
    greeting:
      "Hi! Ask me anything and I'll answer from the documents our team has uploaded.",
    placeholder: "Type your question...",
    suggestions: [],
    position: "right",
    theme: "light",
    offsetBottom: 24,
    offsetSide: 24,
    loadCss: true,
    maxLength: 500,
    maxStoredMessages: 40,
  };

  var userConfig = window.ZEPTO_CHATBOT_CONFIG || {};
  var cfg = {};

  Object.keys(defaults).forEach(function (key) {
    cfg[key] = userConfig[key] !== undefined ? userConfig[key] : defaults[key];
  });

  cfg.apiBase = String(cfg.apiBase || "").replace(/\/+$/, "");

  // ------------------------------------------------------------------
  // Storage (private mode / blocked storage must never break the widget)
  // ------------------------------------------------------------------

  var SESSION_KEY = "zbot_session_id";
  var HISTORY_KEY = "zbot_history_v1";

  function storageGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }

  function storageSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (e) {
      /* ignore */
    }
  }

  function storageRemove(key) {
    try {
      window.localStorage.removeItem(key);
    } catch (e) {
      /* ignore */
    }
  }

  function newSessionId() {
    var random = "";
    for (var i = 0; i < 4; i++) {
      random += Math.random().toString(36).slice(2, 8);
    }
    return "s" + Date.now().toString(36) + random.slice(0, 20);
  }

  var sessionId = storageGet(SESSION_KEY);

  if (!sessionId) {
    sessionId = newSessionId();
    storageSet(SESSION_KEY, sessionId);
  }

  var history = [];

  try {
    history = JSON.parse(storageGet(HISTORY_KEY) || "[]");
    if (!Array.isArray(history)) {
      history = [];
    }
  } catch (e) {
    history = [];
  }

  function saveHistory() {
    if (history.length > cfg.maxStoredMessages) {
      history = history.slice(history.length - cfg.maxStoredMessages);
    }
    storageSet(HISTORY_KEY, JSON.stringify(history));
  }

  // ------------------------------------------------------------------
  // Small DOM helpers
  // ------------------------------------------------------------------

  var SVG_NS = "http://www.w3.org/2000/svg";

  function el(tag, className, attrs) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (attrs) {
      Object.keys(attrs).forEach(function (name) {
        node.setAttribute(name, attrs[name]);
      });
    }
    return node;
  }

  function icon(pathData, size) {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", String(size || 20));
    svg.setAttribute("height", String(size || 20));
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");

    var path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", pathData);
    svg.appendChild(path);

    return svg;
  }

  var ICON_CLOSE = "M18 6 6 18M6 6l12 12";
  var ICON_SEND = "M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z";
  var ICON_TRASH =
    "M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6";

  // ------------------------------------------------------------------
  // Stylesheet
  // ------------------------------------------------------------------

  if (cfg.loadCss && !document.getElementById("zbot-css")) {
    var link = el("link");
    link.id = "zbot-css";
    link.rel = "stylesheet";
    link.href =
      (scriptBase || cfg.apiBase) + "/chatbot/chatbot.css";
    document.head.appendChild(link);
  }

  // ------------------------------------------------------------------
  // Build the widget
  // ------------------------------------------------------------------

  var root = el("div", "zbot-root", {
    "data-open": "false",
    "data-position": cfg.position === "left" ? "left" : "right",
    "data-theme": cfg.theme,
  });
  root.style.setProperty("--zbot-offset-bottom", cfg.offsetBottom + "px");
  root.style.setProperty("--zbot-offset-side", cfg.offsetSide + "px");

  // Panel
  var panel = el("section", "zbot-panel", {
    id: "zbot-panel",
    role: "dialog",
    "aria-label": cfg.title,
  });

  var header = el("div", "zbot-header");

  var headerAvatar = el("div", "zbot-header-avatar");
  var headerImg = el("img", null, { alt: "", src: cfg.avatarUrl });
  headerAvatar.appendChild(headerImg);

  var headerText = el("div", "zbot-header-text");
  var titleEl = el("p", "zbot-title");
  titleEl.textContent = cfg.title;
  var subtitleEl = el("p", "zbot-subtitle");
  subtitleEl.textContent = cfg.subtitle;
  headerText.appendChild(titleEl);
  headerText.appendChild(subtitleEl);

  var clearBtn = el("button", "zbot-icon-btn", {
    type: "button",
    "aria-label": "Clear conversation",
    title: "Clear conversation",
  });
  clearBtn.appendChild(icon(ICON_TRASH, 18));

  var closeBtn = el("button", "zbot-icon-btn", {
    type: "button",
    "aria-label": "Close chat",
    title: "Close",
  });
  closeBtn.appendChild(icon(ICON_CLOSE, 20));

  header.appendChild(headerAvatar);
  header.appendChild(headerText);
  header.appendChild(clearBtn);
  header.appendChild(closeBtn);

  var messagesEl = el("div", "zbot-messages", {
    role: "log",
    "aria-live": "polite",
  });

  var chipsEl = el("div", "zbot-chips");

  var composer = el("div", "zbot-composer");
  var input = el("textarea", "zbot-input", {
    rows: "1",
    maxlength: String(cfg.maxLength),
    placeholder: cfg.placeholder,
    "aria-label": "Your question",
  });
  var sendBtn = el("button", "zbot-send", {
    type: "button",
    "aria-label": "Send message",
  });
  sendBtn.appendChild(icon(ICON_SEND, 18));
  composer.appendChild(input);
  composer.appendChild(sendBtn);

  var footnote = el("div", "zbot-footnote");
  footnote.textContent = "Answers come from uploaded documents only.";

  panel.appendChild(header);
  panel.appendChild(messagesEl);
  panel.appendChild(chipsEl);
  panel.appendChild(composer);
  panel.appendChild(footnote);

  // Launcher (round avatar with green "online" dot)
  var launcher = el("button", "zbot-launcher", {
    type: "button",
    "aria-label": "Open chat",
    "aria-expanded": "false",
    "aria-controls": "zbot-panel",
  });
  var launcherImg = el("img", "zbot-launcher-avatar", {
    alt: "",
    src: cfg.avatarUrl,
  });
  var launcherClose = el("span", "zbot-launcher-close");
  launcherClose.appendChild(icon(ICON_CLOSE, 26));
  var onlineDot = el("span", "zbot-online-dot");
  launcher.appendChild(launcherImg);
  launcher.appendChild(launcherClose);
  launcher.appendChild(onlineDot);

  root.appendChild(panel);
  root.appendChild(launcher);

  // ------------------------------------------------------------------
  // Rendering messages
  // ------------------------------------------------------------------

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, text, options) {
    options = options || {};

    var row = el("div", "zbot-row", { "data-role": role });

    if (options.error) {
      row.setAttribute("data-error", "true");
    }

    var bubble = el("div", "zbot-bubble");
    bubble.textContent = text; // textContent: never interpreted as HTML
    row.appendChild(bubble);

    if (options.sources && options.sources.length) {
      var sourcesEl = el("div", "zbot-sources");
      var label = el("span");
      label.textContent = "Source:";
      sourcesEl.appendChild(label);

      options.sources.forEach(function (source) {
        var chip = el("span", "zbot-source");
        chip.textContent = source.title;
        sourcesEl.appendChild(chip);
      });

      row.appendChild(sourcesEl);
    }

    messagesEl.appendChild(row);
    scrollToBottom();

    return row;
  }

  function showTyping(note) {
    var row = el("div", "zbot-row zbot-typing", { "data-role": "bot" });
    var bubble = el("div", "zbot-bubble", { "aria-label": "Assistant is typing" });

    for (var i = 0; i < 3; i++) {
      bubble.appendChild(el("span", "zbot-dot"));
    }

    row.appendChild(bubble);

    if (note) {
      var noteEl = el("div", "zbot-typing-note");
      noteEl.textContent = note;
      row.appendChild(noteEl);
    }

    messagesEl.appendChild(row);
    scrollToBottom();

    return row;
  }

  function renderHistory() {
    messagesEl.textContent = "";

    if (!history.length) {
      addMessage("bot", cfg.greeting);
    }

    history.forEach(function (item) {
      addMessage(item.role, item.text, {
        sources: item.sources,
        error: item.error,
      });
    });

    renderChips();
  }

  function renderChips() {
    chipsEl.textContent = "";

    var hasUserMessage = history.some(function (item) {
      return item.role === "user";
    });

    if (hasUserMessage || !cfg.suggestions || !cfg.suggestions.length) {
      chipsEl.style.display = "none";
      return;
    }

    chipsEl.style.display = "flex";

    cfg.suggestions.slice(0, 4).forEach(function (text) {
      var chip = el("button", "zbot-chip", { type: "button" });
      chip.textContent = text;
      chip.addEventListener("click", function () {
        sendMessage(text);
      });
      chipsEl.appendChild(chip);
    });
  }

  // ------------------------------------------------------------------
  // Talking to the API
  // ------------------------------------------------------------------

  var busy = false;

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  // The free Render tier sleeps when idle; the first request may need
  // up to a minute. Retry a couple of times on "waking up" responses.
  async function askApi(message, onWaking) {
    var url = cfg.apiBase + "/chatbot/chat";
    var attempts = 3;

    for (var attempt = 1; attempt <= attempts; attempt++) {
      var controller = new AbortController();
      var timer = setTimeout(function () {
        controller.abort();
      }, 70000);

      try {
        var response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: message, session_id: sessionId }),
          signal: controller.signal,
        });

        clearTimeout(timer);

        if ([429, 502, 503, 504].indexOf(response.status) !== -1 && attempt < attempts) {
          onWaking();
          await sleep(4000);
          continue;
        }

        var data = null;

        try {
          data = await response.json();
        } catch (e) {
          data = null;
        }

        if (response.status === 404) {
          throw new Error(
            "The document assistant isn't installed on the server yet. Please try again later."
          );
        }

        if (response.status === 429) {
          throw new Error(
            "The server is busy right now. Please try again in a moment."
          );
        }

        if (!response.ok) {
          var detail = data && data.detail;
          throw new Error(
            typeof detail === "string"
              ? detail
              : "The assistant is unavailable right now."
          );
        }

        return data;
      } catch (error) {
        clearTimeout(timer);

        var isNetwork =
          error.name === "AbortError" || error instanceof TypeError;

        if (isNetwork && attempt < attempts) {
          onWaking();
          await sleep(4000);
          continue;
        }

        if (isNetwork) {
          throw new Error(
            "I can't reach the server right now. It may be starting up - please try again in a minute."
          );
        }

        throw error;
      }
    }
  }

  async function sendMessage(rawText) {
    var text = String(rawText || "").trim();

    if (!text || busy) {
      return;
    }

    text = text.slice(0, cfg.maxLength);
    busy = true;
    sendBtn.disabled = true;
    input.value = "";
    autoResize();

    history.push({ role: "user", text: text });
    addMessage("user", text);
    renderChips();

    var typingRow = showTyping();
    var wakingShown = false;

    try {
      var data = await askApi(text, function () {
        if (!wakingShown) {
          wakingShown = true;
          typingRow.remove();
          typingRow = showTyping("Waking up the server, one moment...");
        }
      });

      typingRow.remove();

      var answer = (data && data.answer) || "Sorry, I didn't get an answer.";
      var sources = (data && data.sources) || [];

      history.push({ role: "bot", text: answer, sources: sources });
      addMessage("bot", answer, { sources: sources });
    } catch (error) {
      typingRow.remove();

      var message = error && error.message ? error.message : "Something went wrong.";

      history.push({ role: "bot", text: message, error: true });
      addMessage("bot", message, { error: true });
    }

    saveHistory();
    busy = false;
    sendBtn.disabled = false;
    input.focus();
  }

  // ------------------------------------------------------------------
  // Open / close
  // ------------------------------------------------------------------

  var warmedUp = false;

  function setOpen(open) {
    root.setAttribute("data-open", open ? "true" : "false");
    launcher.setAttribute("aria-expanded", open ? "true" : "false");
    launcher.setAttribute("aria-label", open ? "Close chat" : "Open chat");

    if (open) {
      scrollToBottom();
      setTimeout(function () {
        input.focus();
      }, 50);

      // Wake the backend while the visitor is still reading/typing.
      if (!warmedUp) {
        warmedUp = true;
        try {
          fetch(cfg.apiBase + "/chatbot/status").catch(function () {});
        } catch (e) {
          /* ignore */
        }
      }
    }
  }

  function isOpen() {
    return root.getAttribute("data-open") === "true";
  }

  function clearConversation() {
    history = [];
    storageRemove(HISTORY_KEY);
    sessionId = newSessionId();
    storageSet(SESSION_KEY, sessionId);
    renderHistory();
  }

  // ------------------------------------------------------------------
  // Events
  // ------------------------------------------------------------------

  function autoResize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 110) + "px";
  }

  launcher.addEventListener("click", function () {
    setOpen(!isOpen());
  });

  closeBtn.addEventListener("click", function () {
    setOpen(false);
    launcher.focus();
  });

  clearBtn.addEventListener("click", clearConversation);

  sendBtn.addEventListener("click", function () {
    sendMessage(input.value);
  });

  input.addEventListener("input", autoResize);

  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendMessage(input.value);
    }
  });

  root.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && isOpen()) {
      setOpen(false);
      launcher.focus();
    }
  });

  // ------------------------------------------------------------------
  // Start
  // ------------------------------------------------------------------

  function mount() {
    renderHistory();
    document.body.appendChild(root);
  }

  if (document.body) {
    mount();
  } else {
    document.addEventListener("DOMContentLoaded", mount);
  }

  window.ZeptoChatbot = {
    open: function () {
      setOpen(true);
    },
    close: function () {
      setOpen(false);
    },
    toggle: function () {
      setOpen(!isOpen());
    },
    clear: clearConversation,
  };
})();
