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

    header.innerHTML = `
        <div>
            <p class="eyebrow">${escapeHtml(exam.provider)}</p>
            <h2>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h2>
            <p class="muted">${escapeHtml(exam.description || "")}</p>
        </div>
        <div class="button-row">
            <a class="button button--primary" href="/exams/${exam.id}/builder">Start exam mode</a>
            ${exam.can_edit_questions ? `<a class="button button--secondary" href="/exams/${exam.id}/questions/new">Create question</a>` : ""}
        </div>
    `;

    filters.innerHTML = `
        <div id="filter-tags-field"></div>
        <div id="filter-topics-field"></div>
        <div id="filter-types-field"></div>
        <div class="study-filters__active">
            <div class="selection-field__top">
                <span class="selection-field__label">Active filters</span>
                <button id="study-filters-clear" class="button button--secondary button--small" type="button">Clear</button>
            </div>
            <div id="study-filters-active" class="selection-field__chips selection-field__chips--shared"></div>
        </div>
    `;
    const sharedChipsContainer = document.getElementById("study-filters-active");
    const clearButton = document.getElementById("study-filters-clear");

    const tagFilter = createAddableSelect(document.getElementById("filter-tags-field"), {
        id: "filter-tag",
        label: "Tags",
        options: exam.builder_meta.tags || [],
        placeholder: "All tags",
        sharedChipsContainer,
        sharedChipGroup: "tag",
        sharedChipGroupLabel: "Tag",
        sharedChipLabel: (value) => value,
        onChange: renderQuestions,
    });
    const topicFilter = createAddableSelect(document.getElementById("filter-topics-field"), {
        id: "filter-topic",
        label: "Topics",
        options: exam.builder_meta.topics || [],
        placeholder: "All topics",
        sharedChipsContainer,
        sharedChipGroup: "topic",
        sharedChipGroupLabel: "Topic",
        sharedChipLabel: (value) => value,
        onChange: renderQuestions,
    });
    const typeFilter = createAddableSelect(document.getElementById("filter-types-field"), {
        id: "filter-type",
        label: "Question type",
        options: exam.builder_meta.question_types || [],
        placeholder: "All question types",
        formatLabel: (type) => type.replaceAll("_", " "),
        sharedChipsContainer,
        sharedChipGroup: "type",
        sharedChipGroupLabel: "Type",
        sharedChipLabel: (type) => type.replaceAll("_", " "),
        onChange: renderQuestions,
    });

    clearButton.addEventListener("click", () => {
        tagFilter.setValues([]);
        topicFilter.setValues([]);
        typeFilter.setValues([]);
    });

    function renderQuestions() {
        const selectedTags = tagFilter.getValues();
        const selectedTopics = topicFilter.getValues();
        const selectedTypes = typeFilter.getValues();
        clearButton.disabled = !selectedTags.length && !selectedTopics.length && !selectedTypes.length;

        const visible = questions.filter((question) => {
            const tagMatch = !selectedTags.length || selectedTags.some((tag) => (question.tags || []).includes(tag));
            const topicMatch = !selectedTopics.length || selectedTopics.some((topic) => (question.topics || []).includes(topic));
            const typeMatch = !selectedTypes.length || selectedTypes.includes(question.type);
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
            if (exam.can_edit_questions) {
                const actions = document.createElement("div");
                actions.className = "button-row";
                actions.innerHTML = `<a class="button button--secondary button--small" href="/questions/${question.id}/edit">Edit question</a>`;
                card.appendChild(actions);
            }
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
