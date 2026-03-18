import { escapeHtml, request } from "../core/api.js";

export async function initQuestionManagementPage(pageContext) {
    const header = document.getElementById("question-management-header");
    const searchInput = document.getElementById("question-management-search");
    const countNode = document.getElementById("question-management-count");
    const list = document.getElementById("question-management-list");
    const returnPath = `/management/exams/${pageContext.exam_id}/questions`;

    const data = await request(`/api/exams/${pageContext.exam_id}/questions`);
    const exam = data.exam;
    const questions = data.questions || [];

    header.innerHTML = `
        <div>
            <p class="eyebrow">${escapeHtml(exam.provider)}</p>
            <h2>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h2>
            <p class="muted">Manage questions separately from study mode. Search the bank, edit entries, or remove them when permitted.</p>
        </div>
        <div class="button-row">
            ${exam.can_edit_questions ? `<a class="button button--primary" href="/exams/${exam.id}/questions/new?return_to=${encodeURIComponent(returnPath)}">Create question</a>` : ""}
            <a class="button button--secondary" href="/management/exams">Back to management</a>
        </div>
    `;

    searchInput.addEventListener("input", renderQuestions);

    async function handleDelete(question) {
        const confirmed = window.confirm(
            `Delete question #${question.id}? This permanently removes the question and any attempt answers linked to it.`,
        );
        if (!confirmed) {
            return;
        }
        await request(`/api/questions/${question.id}`, { method: "DELETE" });
        const index = questions.findIndex((item) => item.id === question.id);
        if (index >= 0) {
            questions.splice(index, 1);
        }
        renderQuestions();
    }

    function renderQuestions() {
        const searchTerm = searchInput.value.trim().toLowerCase();
        const visibleQuestions = questions.filter((question) => {
            if (!searchTerm) {
                return true;
            }
            const haystack = [
                String(question.id),
                question.title || "",
                question.type || "",
                question.difficulty || "",
                question.status || "",
                ...(question.tags || []),
                ...(question.topics || []),
            ]
                .join(" ")
                .toLowerCase();
            return haystack.includes(searchTerm);
        });

        countNode.textContent = `${visibleQuestions.length} question${visibleQuestions.length === 1 ? "" : "s"}`;
        list.innerHTML = "";

        if (!visibleQuestions.length) {
            list.innerHTML = `<div class="empty-state">No questions match the current search.</div>`;
            return;
        }

        visibleQuestions.forEach((question) => {
            const title = question.title || `Question #${question.id}`;
            const card = document.createElement("article");
            card.className = "card question-management-card";
            card.innerHTML = `
                <div class="section-heading">
                    <div>
                        <h3>${escapeHtml(title)}</h3>
                        <p class="muted">Question #${question.id} · Position ${question.position || 0}</p>
                    </div>
                    <span class="badge">${escapeHtml(question.status)}</span>
                </div>
                <div class="badge-row">
                    <span class="badge">${escapeHtml((question.type || "").replaceAll("_", " "))}</span>
                    <span class="badge">${escapeHtml(question.difficulty || "intermediate")}</span>
                    <span class="badge">${escapeHtml(`${question.option_count || 0} options`)}</span>
                    <span class="badge">${escapeHtml(`${question.asset_count || 0} assets`)}</span>
                </div>
                <div class="meta-row muted">
                    <span>Tags: ${question.tags?.length ? escapeHtml(question.tags.join(", ")) : "none"}</span>
                    <span>Topics: ${question.topics?.length ? escapeHtml(question.topics.join(", ")) : "none"}</span>
                </div>
                <div class="meta-row muted">
                    <span>Updated: ${escapeHtml(question.updated_at || "n/a")}</span>
                    <span>Created: ${escapeHtml(question.created_at || "n/a")}</span>
                </div>
                <div class="button-row">
                    ${question.can_edit ? `<a class="button button--secondary button--small" href="/questions/${question.id}/edit?return_to=${encodeURIComponent(returnPath)}">Edit</a>` : ""}
                    ${question.can_delete ? `<button class="button button--danger button--small js-delete-question" type="button">Delete</button>` : ""}
                </div>
            `;
            const deleteButton = card.querySelector(".js-delete-question");
            if (deleteButton) {
                deleteButton.addEventListener("click", async () => {
                    try {
                        await handleDelete(question);
                    } catch (error) {
                        window.alert(error.message);
                    }
                });
            }
            list.appendChild(card);
        });
    }

    renderQuestions();
}
