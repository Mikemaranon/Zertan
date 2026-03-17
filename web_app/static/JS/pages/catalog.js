import { escapeHtml, request } from "../core/api.js";

export async function initCatalogPage() {
    const container = document.getElementById("catalog-list");
    const data = await request("/api/exams");

    container.innerHTML = data.exams
        .map(
            (exam) => `
        <article class="card">
            <div class="section-heading">
                <div>
                    <p class="eyebrow">${escapeHtml(exam.provider)}</p>
                    <h2>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h2>
                </div>
                <span class="badge">${escapeHtml(exam.difficulty)}</span>
            </div>
            <p class="muted">${escapeHtml(exam.description || "")}</p>
            <div class="badge-row">
                ${(exam.tags || []).map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join("")}
            </div>
            <p class="muted">${exam.question_count} questions</p>
            <div class="button-row">
                <a class="button button--primary" href="/exams/${exam.id}">Open study mode</a>
                <a class="button button--secondary" href="/exams/${exam.id}/builder">Build exam</a>
            </div>
        </article>
    `
        )
        .join("");
}
