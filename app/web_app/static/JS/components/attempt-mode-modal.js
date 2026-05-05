import { escapeHtml } from "../core/api.js";

const MODAL_ID = "attempt-mode-modal";
const DEFAULT_FAILURE_PERCENTAGE_THRESHOLD = 40;
const DEFAULT_MINIMUM_FAILURE_COUNT = 2;

export function bindAttemptModeModal({ examId, errorFocusMeta, loadErrorFocusMeta = null }) {
    const state = ensureAttemptModeModal();
    state.examId = examId;
    state.errorFocusMeta = normalizeErrorFocusMeta(errorFocusMeta);
    state.pendingFailurePercentageThreshold = state.errorFocusMeta.failure_percentage_threshold;
    state.loadErrorFocusMeta = typeof loadErrorFocusMeta === "function" ? loadErrorFocusMeta : null;
    renderAttemptModeModal(state);

    return {
        open(triggerElement = null) {
            state.lastFocusedElement = triggerElement instanceof HTMLElement ? triggerElement : document.activeElement;
            openModal(state);
        },
    };
}

function ensureAttemptModeModal() {
    const existing = document.getElementById(MODAL_ID);
    if (existing) {
        return buildState(existing);
    }

    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
        <div id="${MODAL_ID}" class="profile-modal attempt-mode-modal" hidden>
            <div class="profile-modal__backdrop" data-attempt-mode-backdrop></div>
            <div class="profile-modal__dialog attempt-mode-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="attempt-mode-modal-title">
                <button class="profile-modal__close" type="button" aria-label="Close attempt mode selector" data-attempt-mode-close>Close</button>
                <div class="attempt-mode-modal__body">
                    <div class="section-heading attempt-mode-modal__header">
                        <div>
                            <p class="eyebrow">Create Attempt</p>
                            <h2 id="attempt-mode-modal-title">Choose the attempt type</h2>
                            <p class="muted">Select how the server should assemble the formal attempt before opening the builder form.</p>
                        </div>
                    </div>
                    <div class="attempt-mode-modal__options" data-attempt-mode-options></div>
                    <div class="attempt-mode-modal__footer">
                        <p class="muted" data-attempt-mode-summary>Select one mode to continue to the builder form.</p>
                        <div class="button-row">
                            <button class="button button--secondary" type="button" data-attempt-mode-cancel>Cancel</button>
                            <button class="button button--primary" type="button" data-attempt-mode-continue disabled>Continue to builder</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `.trim();

    const modal = wrapper.firstElementChild;
    if (!(modal instanceof HTMLElement)) {
        throw new Error("Could not create attempt mode modal.");
    }
    document.body.appendChild(modal);
    return buildState(modal);
}

function buildState(modal) {
    if (modal._attemptModeState) {
        return modal._attemptModeState;
    }

    const state = {
        modal,
        backdrop: modal.querySelector("[data-attempt-mode-backdrop]"),
        closeButton: modal.querySelector("[data-attempt-mode-close]"),
        cancelButton: modal.querySelector("[data-attempt-mode-cancel]"),
        continueButton: modal.querySelector("[data-attempt-mode-continue]"),
        optionsContainer: modal.querySelector("[data-attempt-mode-options]"),
        summaryNode: modal.querySelector("[data-attempt-mode-summary]"),
        selectedMode: "",
        examId: null,
        errorFocusMeta: normalizeErrorFocusMeta(),
        pendingFailurePercentageThreshold: DEFAULT_FAILURE_PERCENTAGE_THRESHOLD,
        loadErrorFocusMeta: null,
        isClosing: false,
        isLoadingThreshold: false,
        lastFocusedElement: null,
    };

    state.backdrop?.addEventListener("click", () => closeModal(state));
    state.closeButton?.addEventListener("click", () => closeModal(state));
    state.cancelButton?.addEventListener("click", () => closeModal(state));
    state.continueButton?.addEventListener("click", () => {
        if (!state.selectedMode || !state.examId) {
            return;
        }
        const url = new URL(`/exams/${state.examId}/builder`, window.location.origin);
        url.searchParams.set("mode", state.selectedMode);
        if (state.selectedMode === "error_focus") {
            url.searchParams.set("failure_percentage_threshold", String(getSelectedFailureThreshold(state)));
        }
        window.location.href = `${url.pathname}${url.search}`;
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !state.modal.hidden) {
            closeModal(state);
        }
    });

    modal._attemptModeState = state;
    return state;
}

function renderAttemptModeModal(state) {
    const errorFocusMeta = normalizeErrorFocusMeta(state.errorFocusMeta);
    state.pendingFailurePercentageThreshold = normalizeThresholdValue(
        state.pendingFailurePercentageThreshold ?? errorFocusMeta.failure_percentage_threshold
    );
    state.selectedMode = state.selectedMode || "standard";

    state.optionsContainer.innerHTML = `
        ${renderOptionCard({
            mode: "standard",
            title: "Standard",
            description: "Build a formal fixed attempt from the current builder criteria across the exam question bank.",
            details: "Use this when you want a broad certification-style run that is not restricted to your historical mistakes.",
            selectedMode: state.selectedMode,
            disabled: false,
        })}
        ${renderOptionCard({
            mode: "error_focus",
            title: "Error-focused",
            description: "Build a formal fixed attempt from unresolved questions you repeatedly miss in submitted attempts for this exam.",
            details: buildErrorFocusDetails(errorFocusMeta),
            thresholdMarkup: renderErrorFocusThreshold(
                state.pendingFailurePercentageThreshold,
                errorFocusMeta.minimum_failure_count
            ),
            selectedMode: state.selectedMode,
            disabled: false,
        })}
    `;

    state.optionsContainer.querySelectorAll("[data-attempt-mode-option]").forEach((node) => {
        node.addEventListener("click", async () => {
            if (node.dataset.disabled === "true") {
                return;
            }
            const nextMode = node.dataset.attemptModeOption || "standard";
            if (nextMode === state.selectedMode) {
                return;
            }
            state.selectedMode = nextMode;
            if (state.selectedMode === "error_focus") {
                await refreshErrorFocusMeta(state);
            }
            renderAttemptModeModal(state);
        });
    });
    state.optionsContainer.querySelectorAll("[data-attempt-mode-threshold-config]").forEach((node) => {
        node.addEventListener("click", (event) => {
            event.stopPropagation();
        });
        node.addEventListener("mousedown", (event) => {
            event.stopPropagation();
        });
    });
    state.optionsContainer.querySelectorAll("[data-attempt-mode-threshold-input]").forEach((input) => {
        input.addEventListener("click", (event) => {
            event.stopPropagation();
        });
        input.addEventListener("mousedown", (event) => {
            event.stopPropagation();
        });
        input.addEventListener("input", (event) => {
            event.stopPropagation();
            state.pendingFailurePercentageThreshold = normalizeThresholdValue(input.value);
        });
        input.addEventListener("change", async (event) => {
            event.stopPropagation();
            state.pendingFailurePercentageThreshold = normalizeThresholdValue(input.value);
            input.value = String(state.pendingFailurePercentageThreshold);
            if (state.selectedMode === "error_focus") {
                await refreshErrorFocusMeta(state, state.pendingFailurePercentageThreshold);
            }
        });
        input.addEventListener("keydown", async (event) => {
            if (event.key !== "Enter") {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            state.pendingFailurePercentageThreshold = normalizeThresholdValue(input.value);
            input.value = String(state.pendingFailurePercentageThreshold);
            if (state.selectedMode === "error_focus") {
                await refreshErrorFocusMeta(state, state.pendingFailurePercentageThreshold);
            }
        });
    });

    syncFooter(state);
}

function renderOptionCard({ mode, title, description, details, thresholdMarkup = "", selectedMode, disabled }) {
    const classes = [
        "attempt-mode-option",
        mode === "error_focus" ? "attempt-mode-option--expanded" : "",
        selectedMode === mode ? "is-selected" : "",
        disabled ? "is-disabled" : "",
    ]
        .filter(Boolean)
        .join(" ");

    return `
        <div
            class="${classes}"
            data-attempt-mode-option="${mode}"
            data-disabled="${disabled ? "true" : "false"}"
        >
            <div class="attempt-mode-option__layout">
                <div class="attempt-mode-option__content">
                    <div class="attempt-mode-option__top">
                        <strong>${escapeHtml(title)}</strong>
                        <span class="badge">${escapeHtml(mode.replaceAll("_", "-"))}</span>
                    </div>
                    <span class="attempt-mode-option__description">${escapeHtml(description)}</span>
                    <span class="attempt-mode-option__details">${escapeHtml(details)}</span>
                </div>
                ${thresholdMarkup}
            </div>
        </div>
    `;
}

function renderErrorFocusThreshold(threshold, minimumFailureCount) {
    return `
        <div class="attempt-mode-option__config" data-attempt-mode-threshold-config>
            <div class="attempt-mode-option__config-control">
                <input
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    value="${Number(threshold || DEFAULT_FAILURE_PERCENTAGE_THRESHOLD)}"
                    aria-label="Failure percentage threshold"
                    data-attempt-mode-threshold-input
                >
                <span class="attempt-mode-option__config-suffix">%</span>
            </div>
            <span class="attempt-mode-option__config-copy">Only unresolved questions missed at least ${Number(minimumFailureCount || DEFAULT_MINIMUM_FAILURE_COUNT)} times and at or above this percentage will appear.</span>
        </div>
    `;
}

function buildErrorFocusDetails(errorFocusMeta) {
    const failurePercentageThreshold = Number(errorFocusMeta.failure_percentage_threshold || DEFAULT_FAILURE_PERCENTAGE_THRESHOLD);
    const minimumFailureCount = Number(errorFocusMeta.minimum_failure_count || DEFAULT_MINIMUM_FAILURE_COUNT);
    const availableQuestionCount = Number(errorFocusMeta.available_question_count || 0);
    if (!availableQuestionCount) {
        return `No unresolved mistakes currently meet both rules: at least ${minimumFailureCount} failed submitted attempts and ${failurePercentageThreshold}% failure.`;
    }
    return `${availableQuestionCount} unresolved question${availableQuestionCount === 1 ? "" : "s"} currently meet the minimum ${minimumFailureCount} failed submitted attempts and ${failurePercentageThreshold}% failure threshold.`;
}

function syncFooter(state) {
    const selectedMode = state.selectedMode || "";
    state.continueButton.disabled = !selectedMode || state.isLoadingThreshold;
    if (selectedMode === "error_focus") {
        state.summaryNode.textContent = state.isLoadingThreshold
            ? "Refreshing the eligible error-focused questions for this percentage..."
            : "The builder will open in error-focused mode, keeping the formal builder filters while limiting candidates to repeated unresolved mistakes.";
        return;
    }
    state.summaryNode.textContent = "The builder will open in standard mode so you can define the usual formal-attempt parameters.";
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
            state.optionsContainer.querySelector("[data-attempt-mode-option].is-selected")?.focus({ preventScroll: true });
        });
    });
}

function closeModal(state) {
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
        if (state.lastFocusedElement instanceof HTMLElement && document.contains(state.lastFocusedElement)) {
            state.lastFocusedElement.focus({ preventScroll: true });
        }
    }, 300);
}

function normalizeErrorFocusMeta(errorFocusMeta = {}) {
    return {
        available: Boolean(errorFocusMeta.available),
        available_question_count: Number(errorFocusMeta.available_question_count || 0),
        failure_percentage_threshold: normalizeThresholdValue(
            errorFocusMeta.failure_percentage_threshold ?? DEFAULT_FAILURE_PERCENTAGE_THRESHOLD
        ),
        minimum_failure_count: normalizeMinimumFailureCount(
            errorFocusMeta.minimum_failure_count ?? DEFAULT_MINIMUM_FAILURE_COUNT
        ),
    };
}

function normalizeThresholdValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return DEFAULT_FAILURE_PERCENTAGE_THRESHOLD;
    }
    return Math.max(0, Math.min(100, Math.round(numeric)));
}

function normalizeMinimumFailureCount(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
        return DEFAULT_MINIMUM_FAILURE_COUNT;
    }
    return Math.max(1, Math.round(numeric));
}

function getSelectedFailureThreshold(state) {
    return normalizeThresholdValue(state.pendingFailurePercentageThreshold);
}

async function refreshErrorFocusMeta(state, thresholdOverride = null) {
    if (!state.loadErrorFocusMeta) {
        state.errorFocusMeta = normalizeErrorFocusMeta({
            ...state.errorFocusMeta,
            failure_percentage_threshold: thresholdOverride ?? getSelectedFailureThreshold(state),
        });
        state.pendingFailurePercentageThreshold = state.errorFocusMeta.failure_percentage_threshold;
        return;
    }

    state.isLoadingThreshold = true;
    syncFooter(state);
    try {
        const nextMeta = await state.loadErrorFocusMeta(thresholdOverride ?? getSelectedFailureThreshold(state));
        state.errorFocusMeta = normalizeErrorFocusMeta(nextMeta);
        state.pendingFailurePercentageThreshold = state.errorFocusMeta.failure_percentage_threshold;
    } finally {
        state.isLoadingThreshold = false;
        renderAttemptModeModal(state);
    }
}
