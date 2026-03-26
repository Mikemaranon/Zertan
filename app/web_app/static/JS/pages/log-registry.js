import { escapeHtml, request } from "../core/api.js";

export async function initLogRegistryPage() {
    const nodes = {
        examContainer: document.getElementById("log-registry-exams"),
        scopeSelect: document.getElementById("log-registry-group-select"),
        scopeHelp: document.getElementById("log-registry-scope-help"),
        exportButton: document.getElementById("log-registry-export-scope"),
        deleteButton: document.getElementById("log-registry-delete-scope"),
        errorNode: document.getElementById("log-registry-overview-error"),
    };
    if (!nodes.examContainer || !nodes.scopeSelect || !nodes.scopeHelp || !nodes.exportButton || !nodes.deleteButton) {
        throw new Error("Log registry overview markup is incomplete.");
    }

    const state = {
        exams: [],
        scopeOptions: [],
        permissions: {},
    };

    nodes.scopeSelect.addEventListener("change", () => {
        renderScopeSelector(nodes, state, { preserveValue: true });
        renderExams(nodes, state);
    });
    nodes.exportButton.addEventListener("click", () => {
        const href = buildScopeExportHref(state, nodes.scopeSelect.value);
        if (href) {
            window.location.href = href;
        }
    });
    nodes.deleteButton.addEventListener("click", async () => {
        const href = buildScopeDeleteHref(state, nodes.scopeSelect.value);
        if (!href) {
            return;
        }
        if (!window.confirm("Delete the logs for the current scope? This cannot be undone.")) {
            return;
        }
        await request(href, { method: "DELETE" });
        await loadOverview(nodes, state);
    });

    await loadOverview(nodes, state);
}

export async function initLogRegistryDetailPage(context) {
    markRegistryLinkActive();
    const examId = Number(context.exam_id || 0);
    if (!examId) {
        throw new Error("The log registry detail page requires an exam_id.");
    }

    const nodes = {
        title: document.getElementById("log-registry-detail-title"),
        subtitle: document.getElementById("log-registry-detail-subtitle"),
        meta: document.getElementById("log-registry-detail-meta"),
        exportButton: document.getElementById("log-registry-export-exam"),
        deleteButton: document.getElementById("log-registry-delete-exam"),
        errorNode: document.getElementById("log-registry-detail-error"),
        entries: document.getElementById("log-registry-entries"),
        diffModalTitle: document.getElementById("log-registry-diff-modal-title"),
        diffModalSubtitle: document.getElementById("log-registry-diff-modal-subtitle"),
        diffModalContent: document.getElementById("log-registry-diff-modal-content"),
    };
    if (!nodes.title || !nodes.subtitle || !nodes.meta || !nodes.exportButton || !nodes.deleteButton || !nodes.entries) {
        throw new Error("Log registry detail markup is incomplete.");
    }

    const state = {
        logs: [],
    };
    const diffModal = bindManagedModal({
        modalId: "log-registry-diff-modal",
        backdropId: "log-registry-diff-modal-backdrop",
        closeButtonId: "log-registry-diff-modal-close",
    });

    nodes.exportButton.addEventListener("click", () => {
        window.location.href = `/api/log-registry/export?scope=exam&exam_id=${examId}`;
    });
    nodes.deleteButton.addEventListener("click", async () => {
        if (!window.confirm("Delete all logs for this exam? This cannot be undone.")) {
            return;
        }
        await request(`/api/log-registry?scope=exam&exam_id=${examId}`, { method: "DELETE" });
        await loadExamDetail(examId, nodes, state);
    });
    nodes.entries.addEventListener("click", (event) => {
        const button = event.target.closest(".js-open-log-diff");
        if (!button) {
            return;
        }
        const logId = Number(button.dataset.logId || 0);
        const entry = state.logs.find((item) => Number(item.id) === logId);
        if (!entry) {
            return;
        }
        nodes.diffModalTitle.textContent = `${entry.action || "Change"} diff`;
        nodes.diffModalSubtitle.textContent = `${entry.question?.label || "Exam metadata"} · ${formatDateTime(entry.created_at)}`;
        nodes.diffModalContent.innerHTML = formatDiffHtml(entry.diff_text || "");
        diffModal.open();
    });

    await loadExamDetail(examId, nodes, state);
}

async function loadOverview(nodes, state) {
    nodes.errorNode.textContent = "";
    const payload = await request("/api/log-registry");
    state.exams = payload.exams || [];
    state.scopeOptions = payload.scope_options || [];
    state.permissions = payload.permissions || {};
    renderScopeSelector(nodes, state, { preserveValue: true });
    renderExams(nodes, state);
}

function renderScopeSelector(nodes, state, { preserveValue = false } = {}) {
    const currentValue = preserveValue ? nodes.scopeSelect.value : "";
    const isAdmin = Boolean(state.permissions.can_export_domain);
    const options = [
        {
            value: "all",
            label: isAdmin ? "All exams (domain)" : "All accessible exams",
        },
        ...(state.scopeOptions || []).map((group) => ({
            value: `group:${group.id}`,
            label: `${group.name} (${group.code})`,
        })),
    ];
    nodes.scopeSelect.innerHTML = options
        .map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)
        .join("");

    const allowedValues = new Set(options.map((option) => option.value));
    nodes.scopeSelect.value = allowedValues.has(currentValue) ? currentValue : "all";

    const selectedValue = nodes.scopeSelect.value;
    const isGroupScope = selectedValue.startsWith("group:");
    nodes.exportButton.disabled = !isAdmin && !isGroupScope;
    nodes.deleteButton.hidden = !state.permissions.can_delete_logs;
    nodes.deleteButton.disabled = false;

    if (isGroupScope) {
        nodes.scopeHelp.textContent = "The exam list is filtered to the selected group, and the export applies to that group scope.";
        nodes.exportButton.textContent = "Export group logs";
        nodes.deleteButton.textContent = "Delete group logs";
        return;
    }

    if (isAdmin) {
        nodes.scopeHelp.textContent = "Administrators can export or clear the whole log domain from this scope.";
        nodes.exportButton.textContent = "Export domain logs";
        nodes.deleteButton.textContent = "Delete domain logs";
        return;
    }

    nodes.scopeHelp.textContent = "Select one of your groups to export group-level logs. The current view still shows all accessible exams.";
    nodes.exportButton.textContent = "Export group logs";
    nodes.deleteButton.hidden = true;
}

function renderExams(nodes, state) {
    const selectedValue = nodes.scopeSelect.value;
    const selectedGroupId = selectedValue.startsWith("group:") ? Number(selectedValue.split(":")[1]) : null;
    const exams = selectedGroupId
        ? state.exams.filter((exam) => (exam.group_ids || []).includes(selectedGroupId))
        : state.exams;

    nodes.examContainer.innerHTML = exams.length
        ? exams.map((exam) => renderExamCard(exam)).join("")
        : `<div class="empty-state">No exams are available in the current scope.</div>`;
}

function renderExamCard(exam) {
    const scopeLabel = exam.is_global_scope
        ? `<span class="badge badge--neutral">Global</span>`
        : (exam.scope_groups || []).map((group) => `<span class="badge badge--info">${escapeHtml(group.name)}</span>`).join("");
    return `
        <article class="log-registry-card">
            <div class="log-registry-card__top">
                <div>
                    <p class="eyebrow">${escapeHtml(exam.provider || "Exam")}</p>
                    <h3>${escapeHtml(exam.code)} · ${escapeHtml(exam.title)}</h3>
                </div>
                <a class="button button--secondary button--small" href="/log-registry/exams/${exam.id}">Open logs</a>
            </div>
            <p class="muted">${escapeHtml(exam.description || "No description available.")}</p>
            <div class="log-registry-card__meta">
                <span><strong>${Number(exam.log_count || 0)}</strong> logs</span>
                <span>Latest: ${escapeHtml(formatDateTime(exam.latest_log_at))}</span>
            </div>
            <div class="badge-row">${scopeLabel || `<span class="badge badge--neutral">No group scope</span>`}</div>
        </article>
    `;
}

async function loadExamDetail(examId, nodes, state) {
    nodes.errorNode.textContent = "";
    const payload = await request(`/api/log-registry/exams/${examId}`);
    const exam = payload.exam || {};
    const logs = payload.logs || [];
    const permissions = payload.permissions || {};
    state.logs = logs;

    markRegistryLinkActive();
    nodes.title.textContent = `${exam.code || "Exam"} log registry`;
    nodes.subtitle.textContent = exam.title || "Recorded changes for this exam.";
    nodes.meta.innerHTML = renderDetailMeta(exam, logs.length);
    nodes.deleteButton.hidden = !permissions.can_delete_logs;
    nodes.entries.innerHTML = logs.length
        ? logs.map((entry) => renderLogEntry(entry)).join("")
        : `<div class="empty-state">No logs have been recorded for this exam yet.</div>`;
}

function renderDetailMeta(exam, totalLogs) {
    const groups = exam.is_global_scope
        ? "Global"
        : (exam.scope_groups || []).map((group) => group.name).join(", ");
    return `
        <div class="log-registry-meta-card">
            <span class="muted">Exam</span>
            <strong>${escapeHtml(exam.code || "n/a")}</strong>
        </div>
        <div class="log-registry-meta-card">
            <span class="muted">Provider</span>
            <strong>${escapeHtml(exam.provider || "n/a")}</strong>
        </div>
        <div class="log-registry-meta-card">
            <span class="muted">Scope</span>
            <strong>${escapeHtml(groups || "n/a")}</strong>
        </div>
        <div class="log-registry-meta-card">
            <span class="muted">Logs</span>
            <strong>${totalLogs}</strong>
        </div>
    `;
}

function renderLogEntry(entry) {
    const actionClass = `log-registry-entry__action--${escapeHtml(entry.action || "update")}`;
    const question = entry.question || {};
    const actor = entry.actor || {};
    const exam = entry.exam || {};
    return `
        <article class="log-registry-entry">
            <div class="log-registry-entry__header">
                <div class="log-registry-entry__identity">
                    <span class="log-registry-entry__action ${actionClass}">${escapeHtml((entry.action || "").toUpperCase())}</span>
                    <strong>${escapeHtml(question.label || "Exam metadata")}</strong>
                    <span class="muted">${escapeHtml(exam.code || "")}</span>
                </div>
                <span class="muted">${escapeHtml(formatDateTime(entry.created_at))}</span>
            </div>
            <div class="log-registry-entry__meta">
                <span><strong>Actor:</strong> ${escapeHtml(actor.display_name || actor.login_name || "Unknown")}</span>
                <span><strong>Login:</strong> ${escapeHtml(actor.login_name || "n/a")}</span>
                <span><strong>Role:</strong> ${escapeHtml(actor.role || "n/a")}</span>
                <span><strong>Type:</strong> ${escapeHtml(question.type || entry.entity_type || "n/a")}</span>
            </div>
            <div class="log-registry-entry__footer">
                <p class="muted">${escapeHtml(entry.details || "")}</p>
                <button class="button button--secondary button--small js-open-log-diff" type="button" data-log-id="${entry.id}">See diff</button>
            </div>
        </article>
    `;
}

function formatDiffHtml(diffText) {
    if (!diffText) {
        return escapeHtml("No textual diff available.");
    }
    return diffText
        .split("\n")
        .map((line) => {
            const escaped = escapeHtml(line);
            if (line.startsWith("+") && !line.startsWith("+++")) {
                return `<span class="log-diff-line log-diff-line--add">${escaped}</span>`;
            }
            if (line.startsWith("-") && !line.startsWith("---")) {
                return `<span class="log-diff-line log-diff-line--remove">${escaped}</span>`;
            }
            if (line.startsWith("@@")) {
                return `<span class="log-diff-line log-diff-line--context">${escaped}</span>`;
            }
            return `<span class="log-diff-line">${escaped}</span>`;
        })
        .join("");
}

function bindManagedModal({ modalId, backdropId, closeButtonId }) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById(backdropId);
    const closeButton = document.getElementById(closeButtonId);
    let isClosing = false;

    if (!modal || !backdrop || !closeButton) {
        return {
            open() {},
            close() {},
        };
    }

    function open() {
        if (!modal.hidden && modal.dataset.state === "open") {
            return;
        }
        isClosing = false;
        modal.hidden = false;
        modal.dataset.state = "closed";
        document.body.classList.add("modal-open");
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
                modal.dataset.state = "open";
            });
        });
    }

    function close() {
        if (modal.hidden || isClosing) {
            return;
        }
        isClosing = true;
        modal.dataset.state = "closing";
        document.body.classList.remove("modal-open");
        window.setTimeout(() => {
            modal.hidden = true;
            modal.dataset.state = "closed";
            isClosing = false;
        }, 300);
    }

    closeButton.addEventListener("click", close);
    backdrop.addEventListener("click", close);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            close();
        }
    });

    return { open, close };
}

function buildScopeExportHref(state, selectedValue) {
    if (selectedValue.startsWith("group:")) {
        return `/api/log-registry/export?scope=group&group_id=${Number(selectedValue.split(":")[1])}`;
    }
    if (state.permissions.can_export_domain) {
        return "/api/log-registry/export?scope=domain";
    }
    return "";
}

function buildScopeDeleteHref(state, selectedValue) {
    if (!state.permissions.can_delete_logs) {
        return "";
    }
    if (selectedValue.startsWith("group:")) {
        return `/api/log-registry?scope=group&group_id=${Number(selectedValue.split(":")[1])}`;
    }
    return "/api/log-registry?scope=domain";
}

function markRegistryLinkActive() {
    const link = document.querySelector('.sidebar-nav a[href="/log-registry"]');
    link?.classList.add("active");
}

function formatDateTime(value) {
    if (!value) {
        return "n/a";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
        return value;
    }
    return parsed.toLocaleString();
}
