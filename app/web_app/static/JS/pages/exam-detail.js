import { escapeHtml, request } from "../core/api.js";
import { createAddableSelect } from "../components/addable-select.js";
import {
    attachQuestionConfig,
    collectResponse,
    formatCorrectAnswer,
    renderQuestionCard,
    showFeedback,
} from "../components/questions.js";

export async function initExamDetailPage(pageContext) {
    const header = document.getElementById("exam-detail-header");
    const filters = document.getElementById("study-filters");
    const questionContainer = document.getElementById("study-questions");
    const data = await request(`/api/exams/${pageContext.exam_id}/study`);

    const exam = data.exam;
    const questions = data.questions;
    const officialLink = exam.official_url
        ? `
            <div class="exam-reference">
                <a class="meta-link" href="${escapeHtml(exam.official_url)}" target="_blank" rel="noopener noreferrer">Official exam page</a>
            </div>
        `
        : "";

    header.innerHTML = `
        <div>
            <p class="eyebrow">${escapeHtml(exam.provider)}</p>
            <h2>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h2>
            <p class="muted">${escapeHtml(exam.description || "")}</p>
            ${officialLink}
        </div>
        <div class="button-row">
            <a class="button button--primary" href="/exams/${exam.id}/builder">Start exam mode</a>
        </div>
    `;

    filters.innerHTML = `
        <div id="filter-tags-field"></div>
        <div id="filter-topics-field"></div>
        <div id="filter-types-field"></div>
        <div class="study-filters__active">
            <div class="selection-field__top">
                <span class="selection-field__label">Active filters</span>
            </div>
            <div class="selection-field__mode-grid">
                <div class="selection-field__mode-panel">
                    <div class="selection-field__top">
                        <span class="selection-field__mode-title">Include</span>
                        <button id="study-filters-clear-include" class="button button--secondary button--small" type="button">Clear</button>
                    </div>
                    <div id="study-filters-include" class="selection-field__chips selection-field__chips--shared"></div>
                </div>
                <div class="selection-field__mode-panel">
                    <div class="selection-field__top">
                        <span class="selection-field__mode-title">Exclude</span>
                        <button id="study-filters-clear-exclude" class="button button--secondary button--small" type="button">Clear</button>
                    </div>
                    <div id="study-filters-exclude" class="selection-field__chips selection-field__chips--shared"></div>
                </div>
            </div>
        </div>
    `;
    const sharedChipsContainers = {
        includeContainer: document.getElementById("study-filters-include"),
        excludeContainer: document.getElementById("study-filters-exclude"),
        includeEmptyLabel: "No included filters",
        excludeEmptyLabel: "No excluded filters",
    };
    const clearIncludeButton = document.getElementById("study-filters-clear-include");
    const clearExcludeButton = document.getElementById("study-filters-clear-exclude");
    let tagFilter;
    let topicFilter;
    let typeFilter;
    const syncClearButtons = () => {
        const tags = tagFilter.getValues();
        const topics = topicFilter.getValues();
        const types = typeFilter.getValues();
        clearIncludeButton.disabled = !tags.include.length && !topics.include.length && !types.include.length;
        clearExcludeButton.disabled = !tags.exclude.length && !topics.exclude.length && !types.exclude.length;
    };

    tagFilter = createAddableSelect(document.getElementById("filter-tags-field"), {
        id: "filter-tag",
        label: "Tags",
        options: exam.builder_meta.tags || [],
        placeholder: "All tags",
        sharedChipsContainers,
        sharedChipGroup: "tag",
        sharedChipGroupLabel: "Tag",
        sharedChipLabel: (value) => value,
        onChange: renderQuestions,
    });
    topicFilter = createAddableSelect(document.getElementById("filter-topics-field"), {
        id: "filter-topic",
        label: "Topics",
        options: exam.builder_meta.topics || [],
        placeholder: "All topics",
        sharedChipsContainers,
        sharedChipGroup: "topic",
        sharedChipGroupLabel: "Topic",
        sharedChipLabel: (value) => value,
        onChange: renderQuestions,
    });
    typeFilter = createAddableSelect(document.getElementById("filter-types-field"), {
        id: "filter-type",
        label: "Question type",
        options: exam.builder_meta.question_types || [],
        placeholder: "All question types",
        formatLabel: (type) => type.replaceAll("_", " "),
        sharedChipsContainers,
        sharedChipGroup: "type",
        sharedChipGroupLabel: "Type",
        sharedChipLabel: (type) => type.replaceAll("_", " "),
        onChange: renderQuestions,
    });

    clearIncludeButton.addEventListener("click", () => {
        tagFilter.setModeValues("include", []);
        topicFilter.setModeValues("include", []);
        typeFilter.setModeValues("include", []);
    });
    clearExcludeButton.addEventListener("click", () => {
        tagFilter.setModeValues("exclude", []);
        topicFilter.setModeValues("exclude", []);
        typeFilter.setModeValues("exclude", []);
    });

    function renderQuestions() {
        const selectedTags = tagFilter.getValues();
        const selectedTopics = topicFilter.getValues();
        const selectedTypes = typeFilter.getValues();
        syncClearButtons();

        const visible = questions.filter((question) => {
            const questionTags = question.tags || [];
            const questionTopics = question.topics || [];
            const tagMatch =
                (!selectedTags.include.length || selectedTags.include.some((tag) => questionTags.includes(tag))) &&
                !selectedTags.exclude.some((tag) => questionTags.includes(tag));
            const topicMatch =
                (!selectedTopics.include.length || selectedTopics.include.some((topic) => questionTopics.includes(topic))) &&
                !selectedTopics.exclude.some((topic) => questionTopics.includes(topic));
            const typeMatch =
                (!selectedTypes.include.length || selectedTypes.include.includes(question.type)) &&
                !selectedTypes.exclude.includes(question.type);
            return tagMatch && topicMatch && typeMatch;
        });

        questionContainer.innerHTML = "";
        if (!visible.length) {
            questionContainer.innerHTML = `<div class="empty-state">No questions match the selected filters.</div>`;
            return;
        }
        visible.forEach((question, index) => {
            const card = renderQuestionCard(question, { mode: "study", index: index + 1 });
            attachQuestionConfig(card, question);
            card.querySelector(".js-check-question").addEventListener("click", async () => {
                try {
                    const payload = await request(`/api/questions/${question.id}/check`, {
                        method: "POST",
                        body: { response: collectResponse(card) },
                    });
                    showFeedback(card, {
                        success: payload.result.is_correct,
                        title: payload.result.is_correct ? "Correct" : "Incorrect",
                        body: `${formatCorrectAnswer(question, payload.result.correct_answer)} ${payload.result.explanation || ""}`.trim(),
                    });
                } catch (error) {
                    showFeedback(card, {
                        success: false,
                        title: "Unable to check answer",
                        body: error.message,
                    });
                }
            });
            questionContainer.appendChild(card);
        });
    }

    renderQuestions();
}
