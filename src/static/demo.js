(() => {
    const buttons = document.querySelectorAll(".demo-site");
    const siteIdInput = document.querySelector("#demo-site-id");
    const promptText = document.querySelector("#demo-prompt");

    for (const button of buttons) {
        button.addEventListener("click", () => {
            for (const otherButton of buttons) {
                const selected = otherButton === button;
                otherButton.classList.toggle("is-selected", selected);
                otherButton.setAttribute("aria-pressed", String(selected));
            }
            siteIdInput.value = button.dataset.siteId;
            promptText.textContent = button.dataset.prompt;
        });
    }
})();
