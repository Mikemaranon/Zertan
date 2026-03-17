import { escapeHtml, request } from "../core/api.js";
import { createAddableSelect } from "../components/addable-select.js";

export async function initExamBuilderPage(pageContext) {
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
    `;

    const topicsField = createAddableSelect(document.getElementById("builder-topics-field"), {
        id: "builder-topics",
        label: "Topics",
        options: meta.topics || [],
        placeholder: "Select a topic",
    });
    const tagsField = createAddableSelect(document.getElementById("builder-tags-field"), {
        id: "builder-tags",
        label: "Tags",
        options: meta.tags || [],
        placeholder: "Select a tag",
    });
    const typesField = createAddableSelect(document.getElementById("builder-types-field"), {
        id: "builder-types",
        label: "Question types",
        options: meta.question_types || [],
        placeholder: "Select a question type",
        formatLabel: (value) => value.replaceAll("_", " "),
    });

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
