import { escapeHtml, request } from "../core/api.js";
import { createAddableSelect } from "../components/addable-select.js";

export async function initExamBuilderPage(pageContext) {
    const layout = document.querySelector(".exam-builder-layout");
    const summaryPanel = document.querySelector(".builder-summary-panel");
    const configPanel = document.querySelector(".builder-config-panel");
    const summary = document.getElementById("builder-exam-summary");
    const form = document.getElementById("exam-builder-form");
    const errorNode = document.getElementById("builder-error");

    const data = await request(`/api/exams/${pageContext.exam_id}/builder-meta`);
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
    const sharedChipsContainers = {
        includeContainer: document.getElementById("builder-filters-include"),
        excludeContainer: document.getElementById("builder-filters-exclude"),
        includeEmptyLabel: "No included filters",
        excludeEmptyLabel: "No excluded filters",
    };
    const clearIncludeButton = document.getElementById("builder-filters-include-clear");
    const clearExcludeButton = document.getElementById("builder-filters-exclude-clear");
    let topicsField;
    let tagsField;
    let typesField;
    const syncClearButtons = () => {
        const topics = topicsField.getValues();
        const tags = tagsField.getValues();
        const types = typesField.getValues();
        clearIncludeButton.disabled = !topics.include.length && !tags.include.length && !types.include.length;
        clearExcludeButton.disabled = !topics.exclude.length && !tags.exclude.length && !types.exclude.length;
    };

    topicsField = createAddableSelect(document.getElementById("builder-topics-field"), {
        id: "builder-topics",
        label: "Topics",
        options: meta.topics || [],
        placeholder: "Select a topic",
        sharedChipsContainers,
        sharedChipGroup: "topic",
        sharedChipGroupLabel: "Topic",
        sharedChipLabel: (value) => value,
        onChange: syncClearButtons,
    });
    tagsField = createAddableSelect(document.getElementById("builder-tags-field"), {
        id: "builder-tags",
        label: "Tags",
        options: meta.tags || [],
        placeholder: "Select a tag",
        sharedChipsContainers,
        sharedChipGroup: "tag",
        sharedChipGroupLabel: "Tag",
        sharedChipLabel: (value) => value,
        onChange: syncClearButtons,
    });
    typesField = createAddableSelect(document.getElementById("builder-types-field"), {
        id: "builder-types",
        label: "Question types",
        options: meta.question_types || [],
        placeholder: "Select a question type",
        formatLabel: (value) => value.replaceAll("_", " "),
        sharedChipsContainers,
        sharedChipGroup: "type",
        sharedChipGroupLabel: "Type",
        sharedChipLabel: (value) => value.replaceAll("_", " "),
        onChange: syncClearButtons,
    });

    clearIncludeButton.addEventListener("click", () => {
        topicsField.setModeValues("include", []);
        tagsField.setModeValues("include", []);
        typesField.setModeValues("include", []);
    });
    clearExcludeButton.addEventListener("click", () => {
        topicsField.setModeValues("exclude", []);
        tagsField.setModeValues("exclude", []);
        typesField.setModeValues("exclude", []);
    });

    syncClearButtons();
    bindSummaryPanelHeight(layout, summaryPanel, configPanel);

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorNode.textContent = "";
        const payload = {
            topics: topicsField.getValues(),
            tags: tagsField.getValues(),
            question_types: typesField.getValues(),
            question_count: Number(document.getElementById("builder-count").value || 10),
            difficulty: document.getElementById("builder-difficulty").value || null,
            random_order: document.getElementById("builder-random").checked,
            time_limit_minutes: Number(document.getElementById("builder-time-limit").value || 0) || null,
        };
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
