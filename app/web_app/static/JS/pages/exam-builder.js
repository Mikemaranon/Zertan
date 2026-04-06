import { escapeHtml, request } from "../core/api.js";
import { createAddableSelect } from "../components/addable-select.js";

const STANDARD_SELECTION_MODE = "standard";
const ERROR_FOCUS_SELECTION_MODE = "error_focus";
const DEFAULT_FAILURE_PERCENTAGE_THRESHOLD = 40;

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

    summary.innerHTML = `
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

    syncModeBanner({
        modeBanner,
        introCopy,
        selectionMode,
        errorFocusMeta: meta.error_focus || {},
        failurePercentageThreshold,
    });

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

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorNode.textContent = "";
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
            errorNode.textContent = error.message;
        }
    });
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
    const availableQuestionCount = Number(errorFocusMeta.available_question_count || 0);
    introCopy.textContent = "The server assembles a fixed error-focused attempt from your unresolved submitted mistakes and the selected criteria.";
    modeBanner.hidden = false;
    modeBanner.innerHTML = `
        <strong>Error-focused mode</strong>
        <span>
            Questions must reach at least ${resolvedThreshold}% historical failure.
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
