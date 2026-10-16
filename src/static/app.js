(() => {
    const $ = (id) => document.getElementById(id);
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const initial = JSON.parse($("page-state").textContent || "{}");
    const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
    const numbers = new Intl.NumberFormat();
    const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
    const stats = [
        ["paragraphs", "Paragraphs"],
        ["headings", "Headings"],
        ["links", "Links"],
        ["table", "Tables"],
        ["images", "Images"],
        ["quotes", "Quotes"],
    ];
    // Same SVG paths as the Figma Make design; static strings, never user content.
    const ICONS = {
        arrow: '<svg aria-hidden="true" class="icon" fill="none" height="18" viewBox="0 0 24 24" width="18"><path d="m9 18 6-6-6-6" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/></svg>',
        check: '<svg aria-hidden="true" class="icon" fill="none" height="16" viewBox="0 0 24 24" width="16"><path d="m5 12 4 4L19 6" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/></svg>',
        chevron: '<svg aria-hidden="true" class="icon" fill="none" height="16" viewBox="0 0 24 24" width="16"><path d="m8 10 4 4 4-4" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8"/></svg>',
        external: '<svg aria-hidden="true" class="icon" fill="none" height="16" viewBox="0 0 24 24" width="16"><path d="M14 5h5v5M19 5l-8 8M19 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7"/></svg>',
    };

    const readForm = $("read-form");
    const urlInput = $("page-url");
    const readButton = $("read-button");
    const readStatus = $("read-status");
    const readError = $("read-error");
    const workspace = $("workspace");
    const thread = $("thread");
    const findings = $("findings");
    const findingsCount = $("findings-count");
    const followUp = $("follow-up");
    const suggestions = $("suggestions");
    const askForm = $("ask-form");
    const questionInput = $("question");
    const askButton = $("ask-button");
    const askError = $("ask-error");
    const extractForm = $("extract-form");
    const extractButton = $("extract-button");

    // Keep the reader's place when "Run extraction" reloads the page. Storage can throw in
    // private modes, so failures just skip the restore.
    const dataScrollKey = "webscrapeai-data-scroll-y";
    try {
        const savedDataScroll = sessionStorage.getItem(dataScrollKey);
        if (savedDataScroll !== null) {
            sessionStorage.removeItem(dataScrollKey);
            const scrollY = Number(savedDataScroll);
            if (Number.isFinite(scrollY)) {
                // "instant": the design's smooth scrolling would otherwise animate, and get cut off, on load.
                window.addEventListener("pageshow", () => window.scrollTo({ top: scrollY, behavior: "instant" }), { once: true });
            }
        }
    } catch {
        /* storage unavailable */
    }
    document.querySelectorAll("form.data-form:not(.export-form)").forEach((form) => {
        form.addEventListener("submit", () => {
            try {
                sessionStorage.setItem(dataScrollKey, String(window.scrollY));
            } catch {
                /* storage unavailable */
            }
        });
    });

    let aiEnabled = Boolean(initial.aiEnabled);
    let busy = false;
    let lastUrl = "";
    let pageUrl = "";
    // Entry motion answers an action; restoring a conversation on page load stays still.
    let animate = false;

    async function postJson(path, body = {}) {
        let response;
        try {
            response = await fetch(path, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
                body: JSON.stringify(body),
            });
        } catch {
            throw new Error("The request didn't reach the server. Check your connection and try again.");
        }
        const isJson = (response.headers.get("Content-Type") || "").includes("application/json");
        if (response.status === 429) {
            throw new Error("You've reached the hourly limit for page reads and questions. Wait a few minutes, then try again.");
        }
        if (response.redirected || (response.ok && !isJson)) {
            throw new Error("Your session ended. Reload the page and sign in again.");
        }
        if (!isJson) {
            throw new Error("The server couldn't handle that request. Reload the page and try again.");
        }
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Something went wrong. Try again.");
        return data;
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function icon(name) {
        const template = document.createElement("template");
        template.innerHTML = ICONS[name];
        return template.content.firstChild;
    }

    function reveal(node) {
        if (animate && !reduceMotion.matches) node.classList.add("reveal");
        return node;
    }

    function pad(index) {
        return String(index + 1).padStart(2, "0");
    }

    function setBusy(isBusy, button) {
        busy = isBusy;
        [readButton, askButton, extractButton].forEach((control) => {
            if (!control) return;
            control.disabled = isBusy;
            control.classList.toggle("is-loading", isBusy && control === button);
        });
        document.querySelectorAll(".suggestion, .example, .retry").forEach((control) => { control.disabled = isBusy; });
    }

    /* Source panel */
    function renderSource(chat) {
        $("source-title").textContent = chat.title;
        $("strip-host").textContent = chat.host;
        $("strip-title").textContent = chat.title;
        $("source-host").textContent = chat.host;
        $("source-link").href = chat.url;
        $("source-url").textContent = chat.url;
        const list = $("source-stats");
        list.replaceChildren();
        stats.forEach(([key, label]) => {
            const value = (chat.counts || {})[key];
            if (!value) return;
            const item = el("div");
            item.append(el("dt", "", label), el("dd", "", numbers.format(value)));
            list.append(item);
        });
        list.hidden = !list.children.length;
        document.title = `${chat.title} – WebScrapeAI`;
        $("data-url").value = chat.url;
        pageUrl = chat.url;
    }

    function renderFindings(list, placeholder) {
        findings.replaceChildren();
        const items = (list || []).filter((finding) => finding.point);
        findingsCount.hidden = !items.length;
        findingsCount.textContent = String(items.length);
        if (!items.length) {
            findings.append(el("p", "findings-empty", placeholder));
            return;
        }
        const ol = el("ol");
        items.forEach((finding, index) => {
            const item = reveal(el("li"));
            item.append(el("span", "", pad(index)), el("p", "", finding.point));
            ol.append(item);
        });
        findings.append(ol);
    }

    /* Answer column */
    function splitHeadline(message) {
        const text = (message.text || "").trim();
        if (message.headline) return [message.headline, text];
        const match = text.match(/^(.+?[.!?])\s+([\s\S]+)$/);
        return match ? [match[1], match[2]] : [text, ""];
    }

    function copyParagraphs(text) {
        return text.split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean).map((part) => el("p", "", part));
    }

    function fragmentLink(quote) {
        // Text fragments scroll supporting browsers to the quote; others just open the page.
        const encode = (value) => encodeURIComponent(value).replace(/-/g, "%2D");
        const words = quote.split(/\s+/);
        const fragment = words.length > 10
            ? `${encode(words.slice(0, 5).join(" "))},${encode(words.slice(-5).join(" "))}`
            : encode(quote);
        return `${pageUrl.split("#")[0]}#:~:text=${fragment}`;
    }

    function evidenceSection(items) {
        const section = reveal(el("section", "evidence-section"));
        const heading = el("div", "evidence-heading");
        const titles = el("div");
        titles.append(
            el("div", "eyebrow", "Supporting evidence"),
            el("h3", "", `${items.length} ${items.length === 1 ? "passage" : "passages"} from the page`),
        );
        heading.append(titles, el("span", "confidence", "Verified quotes"));
        const list = el("div", "evidence-list");
        items.forEach((item, index) => {
            const details = el("details");
            if (index === 0) details.open = true;
            const summary = el("summary");
            const label = el("span");
            label.append(el("strong", "", item.title), el("small", "", item.meta));
            const chevron = el("span", "summary-chevron");
            chevron.append(icon("chevron"));
            summary.append(el("span", "evidence-number", pad(index)), label, chevron);
            const content = el("div", "evidence-content");
            const link = el("a", "", "Open source passage ");
            link.href = fragmentLink(item.quote);
            link.target = "_blank";
            link.rel = "noreferrer";
            link.append(icon("external"));
            content.append(el("blockquote", "", `“${item.quote}”`), link);
            details.append(summary, content);
            list.append(details);
        });
        section.append(heading, list);
        return section;
    }

    function shortQuote(quote) {
        const words = quote.split(/\s+/);
        return words.length > 9 ? `${words.slice(0, 9).join(" ")}…` : quote;
    }

    function overviewNodes(message) {
        const [headline, body] = splitHeadline(message);
        const section = reveal(el("section", "overview"));
        const titles = el("div");
        titles.append(el("div", "eyebrow accent", "Research overview"), el("h2", "", headline));
        section.append(titles);
        if (body) section.append(el("p", "", body));
        const nodes = [section];
        const quoted = (message.findings || []).filter((finding) => finding.quote);
        if (quoted.length) {
            nodes.push(evidenceSection(quoted.map((finding) => ({ title: finding.point, meta: "Key finding", quote: finding.quote }))));
        }
        return nodes;
    }

    function relabelQuestions() {
        const labels = thread.querySelectorAll(".question-block .question-label");
        labels.forEach((label, index) => {
            label.textContent = index === labels.length - 1 ? "Current question" : "Earlier question";
        });
    }

    function addQuestion(text) {
        const section = reveal(el("section", "question-block"));
        section.append(el("div", "question-label"), el("h3", "", text));
        thread.append(section);
        relabelQuestions();
        return section;
    }

    function answerKicker(label, loading) {
        const kicker = el("div", "answer-kicker");
        const mark = el("span", "answer-check");
        mark.append(loading ? el("span", "spinner") : icon("check"));
        kicker.append(mark, label);
        return kicker;
    }

    function addAnswer(message) {
        const [headline, body] = splitHeadline(message);
        const block = reveal(el("section", "answer-block"));
        block.append(answerKicker("Answer"), el("h3", "", headline));
        const paragraphs = copyParagraphs(body);
        if (paragraphs.length) {
            const copy = el("div", "answer-copy");
            if (paragraphs.length > 1 && body.length > 420) copy.classList.add("two-column");
            copy.append(...paragraphs);
            block.append(copy);
        }
        thread.append(block);
        const citations = message.citations || [];
        if (citations.length) {
            thread.append(evidenceSection(citations.map((quote) => ({ title: shortQuote(quote), meta: "Quoted from the page", quote }))));
        }
    }

    function addPending(kind) {
        let node;
        if (kind === "overview") {
            node = el("section", "overview is-pending");
            const titles = el("div");
            const line = el("p", "pending-line");
            line.append(el("span", "spinner"), "Writing the overview…");
            titles.append(el("div", "eyebrow accent", "Research overview"), line);
            node.append(titles);
        } else {
            node = el("section", "answer-block is-pending");
            node.append(answerKicker("Answering…", true));
        }
        node.setAttribute("role", "status");
        thread.append(node);
        return node;
    }

    function addError(text, retry, before) {
        const node = el("div", "alert");
        node.setAttribute("role", "alert");
        node.append(el("p", "alert-text", text));
        const button = el("button", "secondary-button retry", "Try again");
        button.type = "button";
        button.addEventListener("click", () => { node.remove(); retry(); });
        node.append(button);
        if (before) thread.insertBefore(node, before);
        else thread.append(node);
    }

    function renderSuggestions(questions) {
        suggestions.replaceChildren();
        (questions || []).forEach((question, index) => {
            const button = reveal(el("button", "suggestion"));
            button.type = "button";
            button.disabled = busy;
            button.append(el("span", "", pad(index)), el("span", "suggestion-text", question), icon("arrow"));
            button.addEventListener("click", () => ask(question));
            suggestions.append(button);
        });
        suggestions.hidden = !suggestions.children.length;
        followUp.hidden = !aiEnabled;
    }

    function renderThread(chat) {
        thread.replaceChildren();
        let lastQuestions = [];
        chat.messages.forEach((message) => {
            if (message.role === "user") {
                addQuestion(message.text);
            } else if (message.kind === "overview") {
                thread.append(...overviewNodes(message));
                lastQuestions = message.questions || [];
            } else {
                addAnswer(message);
                lastQuestions = message.questions || [];
            }
        });
        if (!aiEnabled) {
            const note = el("section", "overview");
            const titles = el("div");
            titles.append(el("div", "eyebrow", "Research overview"), el("h2", "", "AI answers are off on this server."));
            note.append(titles, el("p", "", "There's no overview or chat until OPENAI_API_KEY is set. Use Extract from source to browse and download what the page contains."));
            thread.append(note);
        }
        const overview = chat.messages.find((message) => message.kind === "overview");
        renderFindings(
            overview && overview.findings,
            aiEnabled ? "Key findings appear with the overview." : "Key findings need AI answers, which are off on this server.",
        );
        renderSuggestions(lastQuestions);
    }

    async function requestOverview() {
        renderFindings([], "Key findings appear with the overview.");
        const pending = addPending("overview");
        thread.prepend(pending);
        setBusy(true, null);
        try {
            const overview = await postJson("/api/overview");
            pending.replaceWith(...overviewNodes(overview));
            renderFindings(overview.findings, "This page didn't yield clear findings. Ask a question instead.");
            renderSuggestions(overview.questions);
        } catch (error) {
            addError(error.message, requestOverview, pending);
            pending.remove();
            renderFindings([], "Key findings appear once the overview loads.");
        } finally {
            setBusy(false);
        }
    }

    async function ask(question, existingQuestion) {
        if (busy || !askForm) return;
        askError.hidden = true;
        if (!existingQuestion) addQuestion(question);
        const pending = addPending("answer");
        questionInput.value = "";
        setBusy(true, askButton);
        try {
            const reply = await postJson("/api/ask", { question });
            pending.remove();
            addAnswer(reply);
            renderSuggestions(reply.questions);
        } catch (error) {
            pending.remove();
            addError(error.message, () => ask(question, true));
        } finally {
            setBusy(false);
            questionInput.focus({ preventScroll: true });
        }
    }

    function showReadError(message) {
        readError.querySelector(".alert-text").textContent = message;
        readError.hidden = false;
    }

    async function readPage(url) {
        if (busy) return;
        lastUrl = url;
        readError.hidden = true;
        readStatus.textContent = "Fetching and reading the page…";
        readButton.querySelector(".button-label").textContent = "Reading…";
        setBusy(true, readButton);
        let chat;
        try {
            chat = await postJson("/api/page", { url });
        } catch (error) {
            readStatus.textContent = "";
            showReadError(error.message);
            urlInput.focus();
            return;
        } finally {
            readButton.querySelector(".button-label").textContent = "Read page";
            setBusy(false);
        }
        aiEnabled = chat.ai_enabled;
        readStatus.textContent = `Read “${chat.title}”.`;
        urlInput.value = chat.url;
        $("extracted")?.remove();
        enterWorkspace(chat);
        $("source-title").focus({ preventScroll: true });
        if (aiEnabled) requestOverview();
    }

    function enterWorkspace(chat) {
        document.body.classList.add("has-page");
        renderSource(chat);
        renderThread(chat);
        workspace.hidden = false;
        reveal(workspace);
    }

    readForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const url = urlInput.value.trim();
        if (!url) {
            showReadError("Enter a webpage address, like en.wikipedia.org/wiki/Web_scraping.");
            urlInput.focus();
            return;
        }
        readPage(url);
    });

    $("read-retry").addEventListener("click", () => readPage(lastUrl || urlInput.value.trim()));

    document.querySelectorAll(".example").forEach((button) => {
        button.addEventListener("click", () => {
            urlInput.value = button.dataset.url;
            readPage(button.dataset.url);
        });
    });

    if (askForm) {
        $("ask-hint").textContent = `Enter adds a new line. Press ${isMac ? "⌘" : "Ctrl"} + Enter to ask.`;
        askForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const question = questionInput.value.trim();
            if (!question) {
                askError.textContent = "Type a question, or pick one of the suggested questions.";
                askError.hidden = false;
                questionInput.focus();
                return;
            }
            ask(question);
        });
        questionInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                askForm.requestSubmit();
            }
        });
    }

    /* Extract from source: a regular form post that re-reads the page on the server. */
    const elementSelect = $("element");
    elementSelect.addEventListener("change", () => { $("table-field").hidden = elementSelect.value !== "table"; });
    extractForm.addEventListener("submit", () => {
        extractButton.classList.add("is-loading");
        extractButton.querySelector(".button-label").textContent = "Extracting…";
        $("extract-note").textContent = "Reading the page again to extract it…";
        // Disable after the browser has captured the form data.
        setTimeout(() => { extractButton.disabled = true; });
    });

    // On narrow screens the strip keeps the source in view once its full title has scrolled away.
    const strip = document.querySelector(".source-strip");
    if ("IntersectionObserver" in window) {
        new IntersectionObserver(([entry]) => {
            strip.classList.toggle("is-pinned", !entry.isIntersecting && entry.boundingClientRect.top < 0);
        }).observe($("source-title"));
    }

    if (initial.chat) {
        enterWorkspace(initial.chat);
    } else if (initial.url && !workspace.hidden) {
        // Extraction results without a stored chat (for example after it expired).
        const host = (() => { try { return new URL(initial.url).hostname; } catch { return initial.url; } })();
        renderSource({ url: initial.url, title: host, host, counts: {} });
        renderFindings([], "Read the page again to get key findings.");
        followUp.hidden = true;
    }
    animate = true;
    if (initial.chat && aiEnabled && !initial.chat.messages.some((message) => message.kind === "overview")) {
        requestOverview();
    }
})();
