(() => {
    const $ = (id) => document.getElementById(id);
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const initial = JSON.parse($("page-state").textContent || "{}");
    const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
    const numbers = new Intl.NumberFormat();
    const countLabels = {
        paragraphs: ["paragraph", "paragraphs"],
        headings: ["heading", "headings"],
        table: ["table", "tables"],
        images: ["image", "images"],
        links: ["link", "links"],
        quotes: ["quote", "quotes"],
    };

    const readForm = $("read-form");
    const urlInput = $("page-url");
    const readButton = $("read-button");
    const readStatus = $("read-status");
    const readError = $("read-error");
    const workspace = $("workspace");
    const thread = $("thread");
    const findings = $("findings");
    const askForm = $("ask-form");
    const questionInput = $("question");
    const askButton = $("ask-button");
    const askError = $("ask-error");
    const dataPanel = $("data-panel");

    let aiEnabled = Boolean(initial.aiEnabled);
    let busy = false;
    let lastUrl = "";
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

    function reveal(node) {
        if (animate && !reduceMotion.matches) node.classList.add("reveal");
        return node;
    }

    function setBusy(isBusy, button) {
        busy = isBusy;
        [readButton, askButton].forEach((control) => {
            if (!control) return;
            control.disabled = isBusy;
            control.classList.toggle("is-loading", isBusy && control === button);
        });
        thread.querySelectorAll(".suggestion, .retry").forEach((control) => { control.disabled = isBusy; });
        document.querySelectorAll(".example").forEach((control) => { control.disabled = isBusy; });
    }

    function quoteBlock(text) {
        const quote = el("p", "quote");
        quote.append(el("mark", "", `“${text}”`));
        return quote;
    }

    /* Source column */
    function renderSource(chat) {
        $("source-host").textContent = chat.host;
        $("source-title").textContent = chat.title;
        $("strip-host").textContent = chat.host;
        $("strip-title").textContent = chat.title;
        const link = $("source-url");
        link.href = chat.url;
        link.textContent = chat.url;
        const counts = $("source-counts");
        counts.replaceChildren();
        Object.entries(chat.counts || {}).forEach(([key, value]) => {
            if (!value || !countLabels[key]) return;
            const item = el("li");
            item.append(el("strong", "", numbers.format(value)), ` ${countLabels[key][value === 1 ? 0 : 1]}`);
            counts.append(item);
        });
        document.title = `${chat.title} – WebScrapeAI`;
        $("data-url").value = chat.url;
    }

    function renderFindings(list, placeholder) {
        findings.replaceChildren();
        if (!list || !list.length) {
            findings.append(el("p", "findings-empty", placeholder));
            return;
        }
        const ul = el("ul", "finding-list");
        list.forEach((finding) => {
            const item = reveal(el("li"));
            item.append(el("p", "finding-point", finding.point));
            if (finding.quote) item.append(quoteBlock(finding.quote));
            ul.append(item);
        });
        findings.append(ul);
    }

    /* Conversation */
    function renderSuggestions(questions) {
        thread.querySelectorAll(".ask-next").forEach((group) => group.remove());
        if (!questions || !questions.length || !askForm) return;
        const group = reveal(el("li", "ask-next"));
        const label = el("p", "ask-next-label", "Ask next");
        label.id = `ask-next-${Date.now()}`;
        const list = el("div", "suggestion-list");
        list.setAttribute("role", "group");
        list.setAttribute("aria-labelledby", label.id);
        questions.forEach((question) => {
            const chip = el("button", "suggestion", question);
            chip.type = "button";
            chip.disabled = busy;
            chip.addEventListener("click", () => ask(question));
            list.append(chip);
        });
        group.append(label, list);
        thread.append(group);
    }

    function addAssistant(message) {
        const item = reveal(el("li", `turn turn-${message.kind === "overview" ? "overview" : "answer"}`));
        if (message.kind === "overview") item.append(el("h3", "turn-label", "Overview"));
        item.append(el("p", "answer-text", message.text));
        // The overview's evidence is shown with Key findings, so only answers list citations.
        if (message.kind !== "overview" && message.citations && message.citations.length) {
            const sources = el("div", "citations");
            sources.append(el("p", "citations-label", "From the page"));
            message.citations.forEach((citation) => sources.append(quoteBlock(citation)));
            item.append(sources);
        }
        thread.append(item);
        return item;
    }

    function addQuestion(text) {
        const item = reveal(el("li", "turn turn-question"));
        item.append(el("p", "question-text", text));
        thread.append(item);
        return item;
    }

    function addPending(text) {
        const item = el("li", "turn turn-pending");
        item.setAttribute("role", "status");
        const line = el("p", "pending-text");
        line.append(el("span", "spinner is-on"), text);
        item.append(line);
        thread.append(item);
        item.scrollIntoView({ block: "nearest", behavior: reduceMotion.matches ? "auto" : "smooth" });
        return item;
    }

    function addError(text, retry) {
        const item = el("li", "turn turn-error");
        item.setAttribute("role", "alert");
        item.append(el("p", "alert-text", text));
        const button = el("button", "quiet-button retry", "Try again");
        button.type = "button";
        button.addEventListener("click", () => { item.remove(); retry(); });
        item.append(button);
        thread.append(item);
        return item;
    }

    function renderThread(chat) {
        thread.replaceChildren();
        let lastQuestions = [];
        chat.messages.forEach((message) => {
            if (message.role === "user") {
                addQuestion(message.text);
            } else {
                addAssistant(message);
                lastQuestions = message.questions || [];
            }
        });
        if (!aiEnabled) {
            const note = el("li", "turn turn-note");
            note.append(el("p", "answer-text", "AI answers are off on this server, so there's no overview or chat. Open Extracted data and exports to browse and download what the page contains."));
            thread.append(note);
        }
        const overview = chat.messages.find((message) => message.kind === "overview");
        renderFindings(overview && overview.findings, aiEnabled ? "Key findings appear with the overview." : "Key findings need AI answers, which are off on this server.");
        renderSuggestions(lastQuestions);
    }

    async function requestOverview() {
        renderFindings([], "Key findings appear with the overview.");
        const pending = addPending("Writing the overview…");
        setBusy(true, null);
        try {
            const overview = await postJson("/api/overview");
            pending.remove();
            thread.prepend(addAssistant(overview));
            renderFindings(overview.findings, "This page didn't yield clear findings. Ask a question instead.");
            renderSuggestions(overview.questions);
        } catch (error) {
            pending.remove();
            addError(error.message, requestOverview);
            renderFindings([], "Key findings appear once the overview loads.");
        } finally {
            setBusy(false);
        }
    }

    async function ask(question, existingQuestion) {
        if (busy || !askForm) return;
        askError.hidden = true;
        thread.querySelectorAll(".ask-next").forEach((group) => group.remove());
        const questionItem = existingQuestion || addQuestion(question);
        const pending = addPending("Answering…");
        questionInput.value = "";
        setBusy(true, askButton);
        try {
            const reply = await postJson("/api/ask", { question });
            pending.remove();
            addAssistant(reply);
            renderSuggestions(reply.questions);
        } catch (error) {
            pending.remove();
            addError(error.message, () => ask(question, questionItem));
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
        enterWorkspace(chat);
        dataPanel.open = false;
        dataPanel.querySelector(".data-result")?.remove();
        dataPanel.querySelector(".export-form")?.remove();
        workspace.scrollIntoView({ block: "start", behavior: reduceMotion.matches ? "auto" : "smooth" });
        $("source-title").focus({ preventScroll: true });
        if (aiEnabled) requestOverview();
    }

    function enterWorkspace(chat) {
        document.body.classList.add("has-page");
        renderSource(chat);
        renderThread(chat);
        workspace.hidden = false;
        dataPanel.hidden = false;
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
        askForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const question = questionInput.value.trim();
            if (!question) {
                askError.textContent = "Type a question, or pick one under Ask next.";
                askError.hidden = false;
                questionInput.focus();
                return;
            }
            ask(question);
        });
    }

    $("data-link").addEventListener("click", () => { dataPanel.open = true; });

    // On narrow screens the strip keeps the source in view once its full title has scrolled away.
    const strip = document.querySelector(".source-strip");
    if ("IntersectionObserver" in window) {
        new IntersectionObserver(([entry]) => {
            strip.classList.toggle("is-pinned", !entry.isIntersecting && entry.boundingClientRect.top < 0);
        }).observe($("source-title"));
    }
    $("source-title").tabIndex = -1;

    if (initial.chat) {
        enterWorkspace(initial.chat);
    }
    animate = true;
    if (initial.chat) {
        const hasOverview = initial.chat.messages.some((message) => message.kind === "overview");
        if (aiEnabled && !hasOverview) requestOverview();
    }
})();
