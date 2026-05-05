import { escapeHtml, request } from "../core/api.js";
import { bindAttemptModeModal } from "../components/attempt-mode-modal.js";
import { clearBusyState, renderCardSkeletons, renderErrorState } from "../components/loading-state.js";

export async function initCatalogPage() {
    const container = document.getElementById("catalog-list");
    const loadCatalog = async () => {
        renderCardSkeletons(container, { count: 6, showBadge: true, chips: 3, actions: 2 });
        try {
            const data = await request("/api/exams");

            container.innerHTML = data.exams
                .map((exam) => {
                    const officialLink = exam.official_url
                        ? `
                <div class="exam-reference">
                    <a class="meta-link" href="${escapeHtml(exam.official_url)}" target="_blank" rel="noopener noreferrer">Official exam page</a>
                </div>
            `
                        : "";
                    return `
            <article class="card">
                <div class="section-heading">
                    <div>
                        <p class="eyebrow">${escapeHtml(exam.provider)}</p>
                        <h2>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h2>
                    </div>
                    <span class="badge">${escapeHtml(exam.difficulty)}</span>
                </div>
                <p class="muted">${escapeHtml(exam.description || "")}</p>
                ${officialLink}
                <div class="badge-row">
                    ${(exam.tags || []).map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join("")}
                </div>
                <p class="muted">${exam.question_count} questions</p>
                <div class="button-row">
                    <a class="button button--primary" href="/exams/${exam.id}">Open study mode</a>
                    <button class="button button--secondary" type="button" data-build-exam data-exam-id="${exam.id}">Build exam</button>
                </div>
            </article>
        `;
                })
                .join("");
            clearBusyState(container);

            container.querySelectorAll("[data-build-exam]").forEach((button) => {
                button.addEventListener("click", async () => {
                    const examId = Number(button.getAttribute("data-exam-id"));
                    if (!examId) {
                        return;
                    }

                    const originalLabel = button.textContent;
                    button.disabled = true;
                    button.textContent = "Loading...";

                    try {
                        const payload = await request(`/api/exams/${examId}/builder-meta`);
                        const modal = bindAttemptModeModal({
                            examId,
                            errorFocusMeta: payload.builder_meta?.error_focus,
                            loadErrorFocusMeta: async (failurePercentageThreshold) => {
                                const response = await request(
                                    `/api/exams/${examId}/builder-meta?failure_percentage_threshold=${encodeURIComponent(String(failurePercentageThreshold))}`
                                );
                                return response.builder_meta?.error_focus || {};
                            },
                        });
                        modal.open(button);
                    } finally {
                        button.disabled = false;
                        button.textContent = originalLabel;
                    }
                });
            });
        } catch (error) {
            renderErrorState(container, {
                title: "Unable to load catalog",
                message: error.message,
                onRetry: loadCatalog,
            });
        }
    };

    await loadCatalog();
}
