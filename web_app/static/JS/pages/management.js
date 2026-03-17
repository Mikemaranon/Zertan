import { escapeHtml, request, splitCommaValues } from "../core/api.js";

export async function initManagementPage() {
    const examList = document.getElementById("management-exam-list");
    const examForm = document.getElementById("exam-form");
    const importForm = document.getElementById("import-form");
    const examError = document.getElementById("exam-form-error");
    const importError = document.getElementById("import-error");

    async function loadExams() {
        const data = await request("/api/exams");
        examList.innerHTML = data.exams
            .map(
                (exam) => {
                    const officialLink = exam.official_url
                        ? `
                <div class="exam-reference">
                    <a class="meta-link" href="${escapeHtml(exam.official_url)}" target="_blank" rel="noopener noreferrer">Official exam page</a>
                </div>
            `
                        : "";
                    return `
            <div class="card" data-exam-id="${exam.id}">
                <div class="section-heading">
                    <div>
                        <h3>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h3>
                        <p class="muted">${escapeHtml(exam.provider)}</p>
                    </div>
                    <span class="badge">${escapeHtml(exam.status)}</span>
                </div>
                <p class="muted">${escapeHtml(exam.description || "")}</p>
                ${officialLink}
                <div class="badge-row">${(exam.tags || []).map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join("")}</div>
                <div class="button-row">
                    <button class="button button--secondary button--small js-edit-exam" type="button">Edit metadata</button>
                    <a class="button button--secondary button--small" href="/exams/${exam.id}/questions/new">Create question</a>
                    <a class="button button--secondary button--small" href="/exams/${exam.id}">Study mode</a>
                    <button class="button button--primary button--small js-export-exam" type="button">Export package</button>
                </div>
            </div>
        `;
                }
            )
            .join("");

        examList.querySelectorAll(".js-edit-exam").forEach((button) => {
            button.addEventListener("click", async (event) => {
                const examId = event.currentTarget.closest("[data-exam-id]").dataset.examId;
                const payload = await request(`/api/exams/${examId}`);
                fillForm(payload.exam);
            });
        });

        examList.querySelectorAll(".js-export-exam").forEach((button) => {
            button.addEventListener("click", (event) => {
                const examId = event.currentTarget.closest("[data-exam-id]").dataset.examId;
                window.location.href = `/api/import-export/exams/${examId}/export`;
            });
        });
    }

    examForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        examError.textContent = "";
        const examId = document.getElementById("exam-id").value;
        const payload = {
            code: document.getElementById("exam-code").value.trim(),
            title: document.getElementById("exam-title").value.trim(),
            provider: document.getElementById("exam-provider").value.trim(),
            description: document.getElementById("exam-description").value.trim(),
            official_url: document.getElementById("exam-official-url").value.trim(),
            difficulty: document.getElementById("exam-difficulty").value,
            status: document.getElementById("exam-status").value,
            tags: splitCommaValues(document.getElementById("exam-tags").value),
        };

        try {
            await request(examId ? `/api/exams/${examId}` : "/api/exams", {
                method: examId ? "PUT" : "POST",
                body: payload,
            });
            resetForm();
            await loadExams();
        } catch (error) {
            examError.textContent = error.message;
        }
    });

    importForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        importError.textContent = "";
        const fileInput = document.getElementById("import-package");
        if (!fileInput.files.length) {
            importError.textContent = "Select a package file.";
            return;
        }
        const formData = new FormData();
        formData.append("package", fileInput.files[0]);
        try {
            await request("/api/import-export/exams/import", {
                method: "POST",
                formData,
            });
            fileInput.value = "";
            await loadExams();
        } catch (error) {
            importError.textContent = error.message;
        }
    });

    document.getElementById("exam-form-reset").addEventListener("click", resetForm);
    await loadExams();
}

function fillForm(exam) {
    document.getElementById("exam-id").value = exam.id;
    document.getElementById("exam-code").value = exam.code;
    document.getElementById("exam-title").value = exam.title;
    document.getElementById("exam-provider").value = exam.provider;
    document.getElementById("exam-description").value = exam.description || "";
    document.getElementById("exam-official-url").value = exam.official_url || "";
    document.getElementById("exam-difficulty").value = exam.difficulty || "intermediate";
    document.getElementById("exam-status").value = exam.status || "draft";
    document.getElementById("exam-tags").value = (exam.tags || []).join(", ");
}

function resetForm() {
    document.getElementById("exam-id").value = "";
    document.getElementById("exam-form").reset();
}
