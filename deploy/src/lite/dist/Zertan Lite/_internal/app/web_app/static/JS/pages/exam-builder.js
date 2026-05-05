import { escapeHtml, request } from "../core/api.js";
import { createAddableSelect } from "../components/addable-select.js";
import {
    clearBusyState,
    renderErrorState,
    renderFormSkeleton,
    renderPanelSkeleton,
    renderSelectionFieldSkeleton,
} from "../components/loading-state.js";

const STANDARD_SELECTION_MODE = "standard";
const ERROR_FOCUS_SELECTION_MODE = "error_focus";
const DEFAULT_FAILURE_PERCENTAGE_THRESHOLD = 40;
const DEFAULT_MINIMUM_FAILURE_COUNT = 2;

export async function initExamBuilderPage(pageContext) {
    const layout = document.querySelector(".exam-builder-layout");
    const summaryPanel = document.querySelector(".builder-summary-panel");
    const configPanel = document.querySelector(".builder-config-panel");
    const summary = document.getElementById("builder-exam-summary");
    const form = document.getElementById("exam-builder-form");
    const errorNode = document.getElementById("builder-error");
    const introCopy = document.getElementById("builder-intro-copy");
    const modeBanner = document.getElementById("builder-mode-banner");

    const selectionMode = getSelectionModeFromUrl();
    const failurePercentageThreshold = getFailurePercentageThresholdFromUrl();

    const renderLoadingState = () => {
        if (introCopy) {
            introCopy.innerHTML = `<span class="skeleton-block skeleton-line" style="width:82%;"></span>`;
        }
        if (modeBanner) {
            modeBanner.hidden = false;
            renderPanelSkeleton(modeBanner, { lines: 2 });
        }
        renderPanelSkeleton(summary, { lines: 4, chips: 2 });
        renderSelectionFieldSkeleton(document.getElementById("builder-content-field"), { count: 1, includePanels: false });
        renderSelectionFieldSkeleton(document.getElementById("builder-types-field"), { count: 1, includePanels: false });
        form.querySelectorAll("label").forEach((label) => {
            label.hidden = true;
        });
        renderFormSkeleton(configPanel.querySelector(".form-stack"), { fieldCount: 4, includeBanner: false, actionCount: 2 });
    };

    const setStaticFormVisibility = (isVisible) => {
        form.querySelectorAll("label").forEach((label) => {
            label.hidden = !isVisible;
        });
        const buttonRow = form.querySelector(".button-row");
        if (buttonRow) {
            buttonRow.hidden = !isVisible;
        }
    };

    const loadBuilder = async () => {
        errorNode.textContent = "";
        renderLoadingState();
        try {
            const builderMetaUrl =
                selectionMode === ERROR_FOCUS_SELECTION_MODE
                    ? `/api/exams/${pageContext.exam_id}/builder-meta?failure_percentage_threshold=${encodeURIComponent(String(failurePercentageThreshold))}`
                    : `/api/exams/${pageContext.exam_id}/builder-meta`;
            const data = await request(builderMetaUrl);
            const { exam, builder_meta: meta } = data;
            const officialLink = exam.official_url
                ? `
            <div class="exam-reference">
                <a class="meta-link" href="${escapeHtml(exam.official_url)}" target="_blank" rel="noopener noreferrer">Official exam page</a>
            </div>
        `
                : "";

            form.innerHTML = `
                <div class="section-heading">
                    <div>
                        <h2>Exam builder</h2>
                        <p id="builder-intro-copy" class="muted">The server assembles a fixed attempt from the selected criteria.</p>
                    </div>
                </div>
                <div id="builder-mode-banner" class="builder-mode-banner" hidden></div>
                <div id="builder-content-field"></div>
                <div id="builder-types-field"></div>
                <label>
                    <span>Difficulty</span>
                    <select id="builder-difficulty">
                        <option value="">Any difficulty</option>
                        <option value="foundational">Foundational</option>
                        <option value="intermediate">Intermediate</option>
                        <option value="advanced">Advanced</option>
                    </select>
                </label>
                <label>
                    <span>Number of questions</span>
                    <input id="builder-count" type="number" min="1" value="10">
                </label>
                <label>
                    <span>Time limit in minutes</span>
                    <input id="builder-time-limit" type="number" min="0" value="0">
                </label>
                <label class="checkbox-line">
                    <input id="builder-random" type="checkbox" checked>
                    <span>Random order</span>
                </label>
                <div id="builder-error" class="error-message"></div>
                <div class="button-row">
                    <button class="button button--primary" type="submit">Create formal attempt</button>
                    <a class="button button--secondary" href="/exams/${pageContext.exam_id}">Cancel</a>
                </div>
            `;

            const nextSummary = document.getElementById("builder-exam-summary");
            nextSummary.innerHTML = `
            <p class="eyebrow">${escapeHtml(exam.provider)}</p>
            <h2>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h2>
            <p class="muted">${escapeHtml(exam.description || "")}</p>
            ${officialLink}
            <div class="badge-row">
                <span class="badge">${escapeHtml(exam.difficulty)}</span>
                <span class="badge">${exam.question_count} questions in bank</span>
            </div>
            <div class="study-filters__active builder-filters-summary">
                <div class="selection-field__top">
                    <span class="selection-field__label">Selected filters</span>
                </div>
                <div class="selection-field__mode-grid">
                    <div class="selection-field__mode-panel">
                        <div class="selection-field__top">
                            <span class="selection-field__mode-title">Include</span>
                            <button id="builder-filters-include-clear" class="button button--secondary button--small" type="button">Clear</button>
                        </div>
                        <div id="builder-filters-include" class="selection-field__chips selection-field__chips--shared"></div>
                    </div>
                    <div class="selection-field__mode-panel">
                        <div class="selection-field__top">
                            <span class="selection-field__mode-title">Exclude</span>
                            <button id="builder-filters-exclude-clear" class="button button--secondary button--small" type="button">Clear</button>
                        </div>
                        <div id="builder-filters-exclude" class="selection-field__chips selection-field__chips--shared"></div>
                    </div>
                </div>
            </div>
        `;
            clearBusyState(nextSummary);

            const nextIntroCopy = document.getElementById("builder-intro-copy");
            const nextModeBanner = document.getElementById("builder-mode-banner");
            const nextErrorNode = document.getElementById("builder-error");
            clearBusyState(form);

            syncModeBanner({
                modeBanner: nextModeBanner,
                introCopy: nextIntroCopy,
                selectionMode,
                errorFocusMeta: meta.error_focus || {},
                failurePercentageThreshold,
            });
            clearBusyState(nextModeBanner);

            const sharedChipsContainers = {
                includeContainer: document.getElementById("builder-filters-include"),
                excludeContainer: document.getElementById("builder-filters-exclude"),
                includeEmptyLabel: "No included filters",
                excludeEmptyLabel: "No excluded filters",
            };
            const clearIncludeButton = document.getElementById("builder-filters-include-clear");
            const clearExcludeButton = document.getElementById("builder-filters-exclude-clear");
            let contentField;
            let typesField;
            const syncClearButtons = () => {
                const content = contentField.getValues();
                const types = typesField.getValues();
                clearIncludeButton.disabled = !content.include.length && !types.include.length;
                clearExcludeButton.disabled = !content.exclude.length && !types.exclude.length;
            };

            contentField = createAddableSelect(document.getElementById("builder-content-field"), {
                id: "builder-content",
                label: "Content filters",
                options: buildContentFilterOptions(meta),
                searchable: true,
                searchPlaceholder: "Search tags or topics",
                emptySearchMessage: "Type to search available tags and topics.",
                noResultsMessage: "No tags or topics match the current search.",
                sharedChipsContainers,
                sharedChipGroup: (_value, option) => option.group,
                sharedChipGroupLabel: (_value, option) => option.groupLabel,
                sharedChipLabel: (_value, option) => option.label.replace(/^(Tag|Topic)\s+\u00b7\s+/u, ""),
                onChange: syncClearButtons,
            });
            typesField = createAddableSelect(document.getElementById("builder-types-field"), {
                id: "builder-types",
                label: "Question types",
                options: meta.question_types || [],
                searchable: true,
                searchPlaceholder: "Search question types",
                emptySearchMessage: "Type to search available question types.",
                noResultsMessage: "No question types match the current search.",
                formatLabel: (value) => value.replaceAll("_", " "),
                sharedChipsContainers,
                sharedChipGroup: "type",
                sharedChipGroupLabel: "Type",
                sharedChipLabel: (value) => value.replaceAll("_", " "),
                onChange: syncClearButtons,
            });

            clearIncludeButton.addEventListener("click", () => {
                contentField.setModeValues("include", []);
                typesField.setModeValues("include", []);
            });
            clearExcludeButton.addEventListener("click", () => {
                contentField.setModeValues("exclude", []);
                typesField.setModeValues("exclude", []);
            });

            syncClearButtons();
            bindSummaryPanelHeight(layout, summaryPanel, configPanel);

            form.addEventListener(
                "submit",
                async (event) => {
                    event.preventDefault();
                    nextErrorNode.textContent = "";
                    const selectedContent = splitContentFilterValues(contentField.getValues());
                    const payload = {
                        topics: selectedContent.topics,
                        tags: selectedContent.tags,
                        question_types: typesField.getValues(),
                        question_count: Number(document.getElementById("builder-count").value || 10),
                        difficulty: document.getElementById("builder-difficulty").value || null,
                        random_order: document.getElementById("builder-random").checked,
                        time_limit_minutes: Number(document.getElementById("builder-time-limit").value || 0) || null,
                        selection_mode: selectionMode,
                    };
                    if (selectionMode === ERROR_FOCUS_SELECTION_MODE) {
                        payload.error_focus = {
                            failure_percentage_threshold: failurePercentageThreshold,
                        };
                    }
                    try {
                        const result = await request(`/api/exams/${pageContext.exam_id}/builder`, {
                            method: "POST",
                            body: payload,
                        });
                        window.location.href = `/attempts/${result.attempt_id}/run?page=1`;
                    } catch (error) {
                        nextErrorNode.textContent = error.message;
                    }
                },
                { once: true }
            );
        } catch (error) {
            renderErrorState(summary, {
                title: "Unable to load exam builder",
                message: error.message,
                onRetry: loadBuilder,
            });
            if (modeBanner) {
                modeBanner.hidden = true;
            }
            if (introCopy) {
                introCopy.textContent = "Builder configuration is currently unavailable.";
            }
            setStaticFormVisibility(false);
            errorNode.textContent = "";
        }
    };

    await loadBuilder();
}

function syncModeBanner({ modeBanner, introCopy, selectionMode, errorFocusMeta, failurePercentageThreshold }) {
    if (!modeBanner || !introCopy) {
        return;
    }

    if (selectionMode !== ERROR_FOCUS_SELECTION_MODE) {
        introCopy.textContent = "The server assembles a fixed attempt from the selected criteria.";
        modeBanner.hidden = false;
        modeBanner.innerHTML = `
            <strong>Standard mode</strong>
            <span>
                The attempt is assembled from the full question bank using the builder filters you define here.
            </span>
        `;
        return;
    }

    const resolvedThreshold = Number(
        errorFocusMeta.failure_percentage_threshold ?? failurePercentageThreshold ?? DEFAULT_FAILURE_PERCENTAGE_THRESHOLD
    );
    const minimumFailureCount = Number(errorFocusMeta.minimum_failure_count || DEFAULT_MINIMUM_FAILURE_COUNT);
    const availableQuestionCount = Number(errorFocusMeta.available_question_count || 0);
    introCopy.textContent = "The server assembles a fixed error-focused attempt from your unresolved submitted mistakes and the selected criteria.";
    modeBanner.hidden = false;
    modeBanner.innerHTML = `
        <strong>Error-focused mode</strong>
        <span>
            Questions must be unresolved, missed at least ${minimumFailureCount} times in submitted attempts, and reach at least ${resolvedThreshold}% historical failure.
            ${availableQuestionCount ? `${availableQuestionCount} unresolved question${availableQuestionCount === 1 ? "" : "s"} currently qualify before builder filters are applied.` : "No unresolved mistakes currently qualify before builder filters are applied."}
        </span>
    `;
}

function getSelectionModeFromUrl() {
    const value = (new URLSearchParams(window.location.search).get("mode") || "").trim().toLowerCase();
    return value === ERROR_FOCUS_SELECTION_MODE ? ERROR_FOCUS_SELECTION_MODE : STANDARD_SELECTION_MODE;
}

function getFailurePercentageThresholdFromUrl() {
    const rawValue = new URLSearchParams(window.location.search).get("failure_percentage_threshold");
    const numeric = Number(rawValue);
    if (!Number.isFinite(numeric)) {
        return DEFAULT_FAILURE_PERCENTAGE_THRESHOLD;
    }
    return Math.max(0, Math.min(100, Math.round(numeric)));
}

function bindSummaryPanelHeight(layout, summaryPanel, configPanel) {
    if (!layout || !summaryPanel || !configPanel) {
        return;
    }

    const syncHeight = () => {
        const columns = window.getComputedStyle(layout).gridTemplateColumns || "";
        const isSingleColumn = !columns.includes(" ");
        if (isSingleColumn) {
            summaryPanel.style.height = "";
            summaryPanel.style.maxHeight = "";
            return;
        }

        const targetHeight = Math.ceil(configPanel.getBoundingClientRect().height);
        summaryPanel.style.height = `${targetHeight}px`;
        summaryPanel.style.maxHeight = `${targetHeight}px`;
    };

    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(syncHeight) : null;
    observer?.observe(configPanel);
    observer?.observe(layout);
    window.addEventListener("resize", syncHeight);
    window.requestAnimationFrame(syncHeight);
}

function buildContentFilterOptions(builderMeta) {
    return [
        ...(builderMeta.tags || []).map((value) => ({
            value: `tag:${value}`,
            label: `Tag · ${value}`,
            group: "tag",
            groupLabel: "Tag",
            searchTerms: [value, "tag"],
        })),
        ...(builderMeta.topics || []).map((value) => ({
            value: `topic:${value}`,
            label: `Topic · ${value}`,
            group: "topic",
            groupLabel: "Topic",
            searchTerms: [value, "topic"],
        })),
    ];
}

function splitContentFilterValues(values) {
    return {
        tags: {
            include: (values.include || []).filter((value) => value.startsWith("tag:")).map((value) => value.slice(4)),
            exclude: (values.exclude || []).filter((value) => value.startsWith("tag:")).map((value) => value.slice(4)),
        },
        topics: {
            include: (values.include || []).filter((value) => value.startsWith("topic:")).map((value) => value.slice(6)),
            exclude: (values.exclude || []).filter((value) => value.startsWith("topic:")).map((value) => value.slice(6)),
        },
    };
}
