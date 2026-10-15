const resetRequestForm = document.getElementById("reset-request-form");
const resetConfirmForm = document.getElementById("reset-confirm-form");
const fragment = new URLSearchParams(window.location.hash.slice(1));
const resetToken = fragment.get("token");

if (resetConfirmForm.dataset.showReset === "true" || resetToken) {
    resetRequestForm.hidden = true;
    resetConfirmForm.hidden = false;
}

if (resetToken) {
    document.getElementById("reset-token").value = resetToken;
    window.history.replaceState(null, "", window.location.pathname);
}
