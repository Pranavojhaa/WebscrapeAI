(() => {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const readForm = document.getElementById("read-form");
    const urlInput = document.getElementById("page-url");
    const readButton = document.getElementById("read-button");
    const readError = document.getElementById("read-error");
    const conversation = document.getElementById("conversation");
    const thread = document.getElementById("thread");
    const askForm = document.getElementById("ask-form");
    const questionInput = document.getElementById("question");
    const askButton = document.getElementById("ask-button");
    const askError = document.getElementById("ask-error");
    const dataPanel = document.getElementById("data-panel");
    const dataUrl = document.getElementById("data-url");
    const numbers = new Intl.NumberFormat();
    const countLabels = {
        paragraphs: ["paragraph", "paragraphs"],
        headings: ["heading", "headings"],
        table: ["table", "tables"],
        images: ["image", "images"],
        links: ["link", "links"],
        quotes: ["quote", "quotes"],
    };
    let busy = false;

    async function postJson(path, body) {
        let response;
        try {
            response = await fetch(path, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
                body: JSON.stringify(body),
            });
        } catch {
            throw new Error("You seem to be offline. Check your connection and try again.");
        }
        const isJson = (response.headers.get("Content-Type") || "").includes("application/json");
        if (response.redirected || (!isJson && response.status !== 429 && response.ok)) {
            throw new Error("Your session ended. Reload the page and sign in again.");
        }
        if (response.status === 429) {
            throw new Error("You've hit the hourly limit. Wait a few minutes and try again.");
        }
        if (!isJson) {
            throw new Error("Something went wrong. Reload the page and try again.");
        }
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Something went wrong. Try again.");
        return data;
    }

    function setBusy(button, isBusy) {
        busy = isBusy;
        button.disabled = isBusy;
        button.classList.toggle("is-loading", isBusy);
        thread.querySelectorAll(".suggestion").forEach((chip) => { chip.disabled = isBusy; });
    }

    function showError(element, message) {
        element.textContent = message || "";
        element.hidden = !message;
    }

    function renderSource(chat) {
        document.getElementById("source-host").textContent = chat.host;
        document.getElementById("source-title").textContent = chat.title;
        const link = document.getElementById("source-link");
        link.href = chat.url;
        const counts = document.getElementById("source-counts");
        counts.replaceChildren();
        Object.entries(chat.counts || {}).forEach(([key, value]) => {
            if (!value || !countLabels[key]) return;
            const item = document.createElement("li");
            const amount = document.createElement("strong");
            amount.textContent = numbers.format(value);
            item.append(amount, ` ${countLabels[key][value === 1 ? 0 : 1]}`);
            counts.append(item);
        });
        document.title = `${chat.title} – WebScrapeAI`;
    }

    function messageItem(role) {
        const item = document.createElement("li");
        item.className = `message message-${role}`;
        const speaker = document.createElement("p");
        speaker.className = "speaker";
        speaker.textContent = role === "user" ? "You" : "WebScrapeAI";
        item.append(speaker);
        return item;
    }

    function addMessage(message) {
        const item = messageItem(message.role);
        const text = document.createElement("p");
        text.className = "message-text";
        text.textContent = message.text;
        item.append(text);
        if (message.role === "assistant" && message.questions && message.questions.length) {
            thread.querySelectorAll(".suggestions").forEach((group) => group.remove());
            const group = document.createElement("div");
            group.className = "suggestions";
            group.setAttribute("role", "group");
            group.setAttribute("aria-label", "Suggested questions");
            message.questions.forEach((question) => {
                const chip = document.createElement("button");
                chip.type = "button";
                chip.className = "suggestion";
                chip.textContent = question;
                chip.addEventListener("click", () => ask(question));
                group.append(chip);
            });
            item.append(group);
        }
        thread.append(item);
        return item;
    }

    function addPending(label) {
        const item = messageItem("assistant");
        item.classList.add("is-pending");
        const text = document.createElement("p");
        text.className = "message-text";
        text.textContent = label;
        item.append(text);
        thread.append(item);
        item.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
        return item;
    }

    function renderChat(chat) {
        renderSource(chat);
        thread.replaceChildren();
        chat.messages.forEach(addMessage);
        conversation.hidden = false;
        dataPanel.hidden = false;
        if (dataUrl) dataUrl.value = chat.url;
    }

    async function ask(question) {
        if (busy || !askForm) return;
        showError(askError, "");
        addMessage({ role: "user", text: question });
        const pending = addPending("Thinking…");
        setBusy(askButton, true);
        try {
            const reply = await postJson("/api/ask", { question });
            pending.remove();
            addMessage({ role: "assistant", text: reply.answer, questions: reply.questions });
            questionInput.value = "";
        } catch (error) {
            pending.remove();
            thread.lastElementChild.remove();
            questionInput.value = question;
            showError(askError, error.message);
        } finally {
            setBusy(askButton, false);
            questionInput.focus();
        }
    }

    readForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (busy) return;
        const url = urlInput.value.trim();
        if (!url) {
            showError(readError, "Enter a webpage address, like example.com/article.");
            urlInput.focus();
            return;
        }
        showError(readError, "");
        setBusy(readButton, true);
        readButton.lastElementChild.textContent = "Reading…";
        try {
            const chat = await postJson("/api/page", { url });
            urlInput.value = chat.url;
            renderChat(chat);
            dataPanel.open = false;
            dataPanel.querySelector(".data-result")?.remove();
            dataPanel.querySelector(".export-form")?.remove();
            (questionInput || document.getElementById("source-title")).focus({ preventScroll: true });
            conversation.scrollIntoView({ block: "start" });
        } catch (error) {
            showError(readError, error.message);
            urlInput.focus();
        } finally {
            readButton.lastElementChild.textContent = "Read page";
            setBusy(readButton, false);
        }
    });

    if (askForm) {
        askForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const question = questionInput.value.trim();
            if (!question) {
                showError(askError, "Type a question, or pick one of the suggestions.");
                questionInput.focus();
                return;
            }
            ask(question);
        });
    }

    const state = JSON.parse(document.getElementById("page-state").textContent || "null");
    if (state) renderChat(state);
})();
