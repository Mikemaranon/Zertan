import { formatDuration, request } from "../core/api.js";
import { renderPagination } from "../components/pagination.js";
import { applyResponse, attachQuestionConfig, collectResponse, renderQuestionCard } from "../components/questions.js";

export async function initExamRunnerPage(pageContext) {
    const summary = document.getElementById("attempt-summary");
    const questionContainer = document.getElementById("runner-questions");
    const currentPage = Number(new URLSearchParams(window.location.search).get("page") || 1);
    const data = await request(`/api/attempts/${pageContext.attempt_id}`);
    const attempt = data.attempt;
    const questions = data.questions;
    const totalPages = data.total_pages;

    summary.innerHTML = `
        <div>
            <p class="eyebrow">${attempt.exam_code}</p>
            <h2>${attempt.exam_title}</h2>
            <p class="muted">Formal exam mode. Immediate correction is disabled and only submission generates official statistics.</p>
        </div>
        <div class="badge-row">
            <span class="badge">${attempt.question_count} questions</span>
            <span class="badge">${totalPages} pages</span>
            <span class="badge">Time limit: ${attempt.time_limit_minutes ? `${attempt.time_limit_minutes} minutes` : "not set"}</span>
        </div>
    `;

    const renderPage = () => {
        const pageQuestions = questions.filter((question) => question.page_number === currentPage);
        questionContainer.innerHTML = "";
        pageQuestions.forEach((entry) => {
            const card = renderQuestionCard(entry.question, {
                mode: "exam",
                index: entry.question_order,
                response: entry.response,
            });
            card.dataset.attemptQuestionId = entry.attempt_question_id;
            attachQuestionConfig(card, entry.question);
            questionContainer.appendChild(card);
        });

        renderPagination(document.getElementById("pagination-top"), currentPage, totalPages, navigateToPage);
        renderPagination(document.getElementById("pagination-bottom"), currentPage, totalPages, navigateToPage);
    };

    async function persistCurrentPage() {
        const cards = Array.from(questionContainer.querySelectorAll(".question-card"));
        const answers = cards.map((card) => ({
            attempt_question_id: Number(card.dataset.attemptQuestionId),
            response: collectResponse(card),
        }));
        await request(`/api/attempts/${pageContext.attempt_id}/answers`, {
            method: "POST",
            body: { answers },
        });
    }

    async function navigateToPage(page) {
        await persistCurrentPage();
        window.location.href = `/attempts/${pageContext.attempt_id}/run?page=${page}`;
    }

    document.getElementById("save-page-button").addEventListener("click", async () => {
        await persistCurrentPage();
        alert("Current page saved.");
    });

    document.getElementById("submit-attempt-button").addEventListener("click", async () => {
        if (!window.confirm("Submit this formal attempt? You will not be able to modify answers afterwards.")) {
            return;
        }
        const cards = Array.from(questionContainer.querySelectorAll(".question-card"));
        const answers = cards.map((card) => ({
            attempt_question_id: Number(card.dataset.attemptQuestionId),
            response: collectResponse(card),
        }));
        await request(`/api/attempts/${pageContext.attempt_id}/submit`, {
            method: "POST",
            body: { answers },
        });
        window.location.href = `/attempts/${pageContext.attempt_id}/results`;
    });

    renderPage();
}
