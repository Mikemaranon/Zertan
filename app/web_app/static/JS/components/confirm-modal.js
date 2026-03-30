let modalState = null;

export function bindConfirmModal() {
    ensureConfirmModal();
}

export function confirmAction({
    title = "Confirm action",
    message = "",
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    eyebrow = "Confirmation",
    confirmVariant = "danger",
} = {}) {
    const state = ensureConfirmModal();

    return new Promise((resolve) => {
        state.queue.push({
            title,
            message,
            confirmLabel,
            cancelLabel,
            eyebrow,
            confirmVariant,
            resolve,
        });
        pumpQueue(state);
    });
}

function ensureConfirmModal() {
    if (modalState) {
        return modalState;
    }

    const existingModal = document.getElementById("confirm-modal");
    if (existingModal) {
        modalState = createStateFromDom(existingModal);
        return modalState;
    }

    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
        <div id="confirm-modal" class="profile-modal confirm-modal" hidden>
            <div id="confirm-modal-backdrop" class="profile-modal__backdrop"></div>
            <div class="profile-modal__dialog confirm-modal__dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-modal-title" aria-describedby="confirm-modal-message">
                <button id="confirm-modal-close" class="profile-modal__close" type="button" aria-label="Close confirmation dialog">Close</button>
                <div class="confirm-modal__body">
                    <div class="section-heading confirm-modal__header">
                        <div>
                            <p id="confirm-modal-eyebrow" class="eyebrow">Confirmation</p>
                            <h2 id="confirm-modal-title">Confirm action</h2>
                            <p id="confirm-modal-message" class="muted"></p>
                        </div>
                    </div>
                    <div class="button-row confirm-modal__actions">
                        <button id="confirm-modal-cancel" class="button button--secondary" type="button">Cancel</button>
                        <button id="confirm-modal-confirm" class="button button--danger" type="button">Confirm</button>
                    </div>
                </div>
            </div>
        </div>
    `.trim();
    const modalElement = wrapper.firstElementChild;
    if (!(modalElement instanceof HTMLElement)) {
        throw new Error("Could not create the confirmation modal.");
    }
    document.body.appendChild(modalElement);

    modalState = createStateFromDom(document.getElementById("confirm-modal"));
    return modalState;
}

function createStateFromDom(modal) {
    const state = {
        modal,
        backdrop: document.getElementById("confirm-modal-backdrop"),
        closeButton: document.getElementById("confirm-modal-close"),
        titleNode: document.getElementById("confirm-modal-title"),
        messageNode: document.getElementById("confirm-modal-message"),
        eyebrowNode: document.getElementById("confirm-modal-eyebrow"),
        cancelButton: document.getElementById("confirm-modal-cancel"),
        confirmButton: document.getElementById("confirm-modal-confirm"),
        queue: [],
        activeRequest: null,
        isClosing: false,
        lastFocusedElement: null,
    };

    const handleCancel = () => resolveActiveRequest(state, false);
    const handleConfirm = () => resolveActiveRequest(state, true);

    state.closeButton?.addEventListener("click", handleCancel);
    state.backdrop?.addEventListener("click", handleCancel);
    state.cancelButton?.addEventListener("click", handleCancel);
    state.confirmButton?.addEventListener("click", handleConfirm);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !state.modal.hidden) {
            resolveActiveRequest(state, false);
        }
    });

    return state;
}

function pumpQueue(state) {
    if (state.activeRequest || state.isClosing) {
        return;
    }

    const nextRequest = state.queue.shift();
    if (!nextRequest) {
        return;
    }

    state.activeRequest = nextRequest;
    state.lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    state.eyebrowNode.textContent = nextRequest.eyebrow;
    state.titleNode.textContent = nextRequest.title;
    state.messageNode.textContent = nextRequest.message;
    state.cancelButton.textContent = nextRequest.cancelLabel;
    state.confirmButton.textContent = nextRequest.confirmLabel;
    syncConfirmButtonVariant(state.confirmButton, nextRequest.confirmVariant);

    openModal(state);
}

function openModal(state) {
    if (!state.modal.hidden && state.modal.dataset.state === "open") {
        return;
    }

    state.isClosing = false;
    state.modal.hidden = false;
    state.modal.dataset.state = "closed";
    document.body.classList.add("modal-open");
    window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
            state.modal.dataset.state = "open";
            state.confirmButton.focus({ preventScroll: true });
        });
    });
}

function closeModal(state, onClosed) {
    if (state.modal.hidden || state.isClosing) {
        return;
    }

    state.isClosing = true;
    state.modal.dataset.state = "closing";
    document.body.classList.remove("modal-open");
    window.setTimeout(() => {
        state.modal.hidden = true;
        state.modal.dataset.state = "closed";
        state.isClosing = false;
        if (typeof onClosed === "function") {
            onClosed();
        }
        pumpQueue(state);
    }, 300);
}

function resolveActiveRequest(state, result) {
    if (!state.activeRequest) {
        return;
    }

    const { resolve } = state.activeRequest;
    state.activeRequest = null;
    closeModal(state, () => {
        if (state.lastFocusedElement && document.contains(state.lastFocusedElement)) {
            state.lastFocusedElement.focus({ preventScroll: true });
        }
        state.lastFocusedElement = null;
        resolve(result);
    });
}

function syncConfirmButtonVariant(button, variant) {
    button.classList.remove("button--danger", "button--primary", "button--secondary");
    if (variant === "primary") {
        button.classList.add("button--primary");
        return;
    }
    if (variant === "secondary") {
        button.classList.add("button--secondary");
        return;
    }
    button.classList.add("button--danger");
}
