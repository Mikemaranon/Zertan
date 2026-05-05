import { escapeHtml } from "../core/api.js";

export function renderKpiSkeletons(container, count = 6) {
    if (!container) {
        return;
    }
    setLoadingMarkup(
        container,
        Array.from({ length: count }, () => `
            <div class="kpi-card skeleton-card skeleton-card--kpi">
                ${buildSkeletonLine("42%", "skeleton-line--small")}
                ${buildSkeletonLine("70%", "skeleton-line--value")}
            </div>
        `).join("")
    );
}

export function renderCardSkeletons(
    container,
    {
        count = 4,
        showBadge = true,
        chips = 0,
        actions = 0,
        compact = false,
    } = {}
) {
    if (!container) {
        return;
    }
    setLoadingMarkup(
        container,
        Array.from({ length: count }, () => `
            <div class="card skeleton-card ${compact ? "skeleton-card--compact" : ""}">
                <div class="section-heading">
                    <div class="skeleton-stack">
                        ${buildSkeletonLine("28%", "skeleton-line--small")}
                        ${buildSkeletonLine("72%", "skeleton-line--title")}
                    </div>
                    ${showBadge ? buildSkeletonBadge("88px") : ""}
                </div>
                <div class="skeleton-stack skeleton-stack--tight">
                    ${buildSkeletonLine("100%")}
                    ${buildSkeletonLine("88%")}
                    ${buildSkeletonLine("54%")}
                </div>
                ${chips ? `<div class="badge-row">${Array.from({ length: chips }, () => buildSkeletonChip()).join("")}</div>` : ""}
                ${actions ? `<div class="button-row skeleton-actions">${Array.from({ length: actions }, (_, index) => buildSkeletonButton(index === 0 ? "148px" : "124px")).join("")}</div>` : ""}
            </div>
        `).join("")
    );
}

export function renderQuestionSkeletons(container, count = 5) {
    if (!container) {
        return;
    }
    setLoadingMarkup(
        container,
        Array.from({ length: count }, (_, index) => `
            <article class="panel question-card skeleton-question-card">
                <div class="question-card__header">
                    <div class="skeleton-stack">
                        ${buildSkeletonLine("116px", "skeleton-line--small")}
                        ${buildSkeletonLine(index % 2 === 0 ? "58%" : "66%", "skeleton-line--title")}
                    </div>
                    <div class="badge-row">
                        ${buildSkeletonBadge("92px")}
                        ${buildSkeletonBadge("84px")}
                    </div>
                </div>
                <div class="badge-row">
                    ${buildSkeletonChip()}
                    ${buildSkeletonChip("110px")}
                </div>
                <div class="skeleton-stack">
                    ${buildSkeletonLine("100%")}
                    ${buildSkeletonLine("96%")}
                    ${buildSkeletonLine("64%")}
                </div>
                <div class="skeleton-stack skeleton-stack--tight">
                    ${Array.from({ length: 4 }, () => `<div class="skeleton-option">${buildSkeletonDot()}${buildSkeletonLine("74%")}</div>`).join("")}
                </div>
                <div class="button-row skeleton-actions">
                    ${buildSkeletonButton("132px")}
                </div>
            </article>
        `).join("")
    );
}

export function renderSelectionFieldSkeleton(container, { count = 2, includePanels = true } = {}) {
    if (!container) {
        return;
    }
    setLoadingMarkup(
        container,
        `
            <div class="skeleton-toolbar">
                ${Array.from({ length: count }, () => `
                    <div class="skeleton-field">
                        ${buildSkeletonLine("120px", "skeleton-line--small")}
                        ${buildSkeletonInput()}
                    </div>
                `).join("")}
            </div>
            ${includePanels ? `
                <div class="study-filters__active builder-filters-summary skeleton-field-group">
                    <div class="selection-field__top">
                        ${buildSkeletonLine("110px", "skeleton-line--small")}
                    </div>
                    <div class="selection-field__mode-grid">
                        ${Array.from({ length: 2 }, () => `
                            <div class="selection-field__mode-panel skeleton-panel">
                                <div class="selection-field__top">
                                    ${buildSkeletonLine("76px", "skeleton-line--small")}
                                    ${buildSkeletonButton("84px", "skeleton-button--small")}
                                </div>
                                <div class="badge-row">
                                    ${buildSkeletonChip("86px")}
                                    ${buildSkeletonChip("94px")}
                                </div>
                            </div>
                        `).join("")}
                    </div>
                </div>
            ` : ""}
        `
    );
}

export function renderFormSkeleton(container, { fieldCount = 6, includeBanner = true, actionCount = 2 } = {}) {
    if (!container) {
        return;
    }
    setLoadingMarkup(
        container,
        `
            <div class="skeleton-stack">
                ${buildSkeletonLine("160px", "skeleton-line--title")}
                ${buildSkeletonLine("86%")}
            </div>
            ${includeBanner ? `<div class="skeleton-panel skeleton-panel--banner">${buildSkeletonLine("92%")}${buildSkeletonLine("74%")}</div>` : ""}
            <div class="skeleton-form-grid">
                ${Array.from({ length: fieldCount }, () => `
                    <div class="skeleton-field">
                        ${buildSkeletonLine("110px", "skeleton-line--small")}
                        ${buildSkeletonInput()}
                    </div>
                `).join("")}
            </div>
            <div class="button-row skeleton-actions">
                ${Array.from({ length: actionCount }, (_, index) => buildSkeletonButton(index === 0 ? "182px" : "112px")).join("")}
            </div>
        `
    );
}

export function renderPanelSkeleton(container, { lines = 5, chips = 0 } = {}) {
    if (!container) {
        return;
    }
    setLoadingMarkup(
        container,
        `
            <div class="skeleton-panel">
                <div class="skeleton-stack">
                    ${Array.from({ length: lines }, (_, index) =>
                        buildSkeletonLine(index === lines - 1 ? "58%" : index === 0 ? "72%" : "100%")
                    ).join("")}
                </div>
                ${chips ? `<div class="badge-row">${Array.from({ length: chips }, () => buildSkeletonChip()).join("")}</div>` : ""}
            </div>
        `
    );
}

export function renderPaginationSkeleton(container) {
    if (!container) {
        return;
    }
    setLoadingMarkup(
        container,
        `
            <div class="button-row skeleton-pagination">
                ${buildSkeletonButton("92px", "skeleton-button--small")}
                ${buildSkeletonChip("44px")}
                ${buildSkeletonChip("44px")}
                ${buildSkeletonChip("44px")}
                ${buildSkeletonButton("92px", "skeleton-button--small")}
            </div>
        `
    );
}

export function renderErrorState(
    container,
    {
        title = "Unable to load this section",
        message = "Please try again.",
        retryLabel = "Retry",
        onRetry = null,
    } = {}
) {
    if (!container) {
        return;
    }
    clearBusyState(container);
    container.innerHTML = `
        <div class="load-state" role="status">
            <div class="load-state__copy">
                <strong>${escapeHtml(title)}</strong>
                <p class="muted">${escapeHtml(message)}</p>
            </div>
            ${typeof onRetry === "function" ? `<div class="load-state__actions"><button class="button button--secondary" type="button" data-loading-retry>${escapeHtml(retryLabel)}</button></div>` : ""}
        </div>
    `;
    if (typeof onRetry === "function") {
        container.querySelector("[data-loading-retry]")?.addEventListener("click", () => {
            onRetry();
        });
    }
}

export function clearBusyState(container) {
    if (!container) {
        return;
    }
    container.removeAttribute("data-loading-state");
    container.setAttribute("aria-busy", "false");
}

function setLoadingMarkup(container, markup) {
    container.dataset.loadingState = "true";
    container.setAttribute("aria-busy", "true");
    container.innerHTML = markup;
}

function buildSkeletonLine(width = "100%", extraClass = "") {
    const className = ["skeleton-block", "skeleton-line", extraClass].filter(Boolean).join(" ");
    return `<span class="${className}" style="width:${width};"></span>`;
}

function buildSkeletonBadge(width = "80px") {
    return `<span class="skeleton-block skeleton-badge" style="width:${width};"></span>`;
}

function buildSkeletonChip(width = "88px") {
    return `<span class="skeleton-block skeleton-chip" style="width:${width};"></span>`;
}

function buildSkeletonButton(width = "136px", extraClass = "") {
    return `<span class="skeleton-block skeleton-button ${extraClass}" style="width:${width};"></span>`;
}

function buildSkeletonInput() {
    return `<span class="skeleton-block skeleton-input"></span>`;
}

function buildSkeletonDot() {
    return `<span class="skeleton-block skeleton-dot"></span>`;
}
