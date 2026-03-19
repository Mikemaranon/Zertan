import { createAddableSelect } from "../components/addable-select.js";
import { escapeHtml, formatPercent, request } from "../core/api.js";

export async function initLiveExamsPage() {
    const payload = await request("/api/live-exams");

    if (payload.mode === "administrator") {
        initAdministratorView(payload);
        return;
    }

    initUserView(payload.assignments || []);
}

function initAdministratorView(payload) {
    const openModalButton = document.getElementById("live-exam-open-modal");
    const list = document.getElementById("live-exams-admin-list");
    const canCreate = (payload.available_exams || []).length > 0 && (payload.available_users || []).length > 0;
    const modal = bindLiveExamModal({
        availableExams: payload.available_exams || [],
        availableUsers: payload.available_users || [],
        onCreated: async () => {
            const refreshed = await request("/api/live-exams");
            renderAdministratorList(list, refreshed.live_exams || []);
        },
    });

    renderAdministratorList(list, payload.live_exams || []);
    if (openModalButton) {
        openModalButton.disabled = !canCreate;
    }
    openModalButton?.addEventListener("click", () => modal.open());
}

function initUserView(assignments) {
    const list = document.getElementById("live-exams-user-list");
    if (!list) {
        return;
    }

    list.innerHTML = assignments.length
        ? assignments
            .map(
                (assignment) => `
            <article class="card">
                <div class="section-heading">
                    <div>
                        <p class="eyebrow">${escapeHtml(assignment.exam_code)}</p>
                        <h2>${escapeHtml(assignment.live_exam_title || assignment.exam_title)}</h2>
                    </div>
                    ${renderStatusBadge(assignment.assignment_status)}
                </div>
                <p class="muted">${escapeHtml(assignment.live_exam_description || "")}</p>
                ${assignment.live_exam_instructions ? `<div class="live-exam-note"><strong>Instructions</strong><p class="muted">${escapeHtml(assignment.live_exam_instructions)}</p></div>` : ""}
                <div class="live-exam-card__metrics">
                    ${renderMetric("Source exam", escapeHtml(assignment.exam_code))}
                    ${renderMetric("Provider", escapeHtml(assignment.exam_provider))}
                    ${renderMetric("Questions", assignment.question_count)}
                    ${renderMetric("Time limit", assignment.time_limit_minutes ? `${assignment.time_limit_minutes} min` : "Not set")}
                </div>
                <div class="button-row">
                    ${renderUserActionButton(assignment)}
                </div>
            </article>
        `
            )
            .join("")
        : `<div class="empty-state">No live exams have been assigned to you.</div>`;

    list.querySelectorAll(".js-live-exam-start").forEach((button) => {
        button.addEventListener("click", async (event) => {
            const assignmentId = event.currentTarget.dataset.assignmentId;
            const response = await request(`/api/live-exams/assignments/${assignmentId}/start`, {
                method: "POST",
            });
            window.location.href = `/attempts/${response.attempt_id}/run`;
        });
    });
}

function renderAdministratorList(container, liveExams) {
    if (!container) {
        return;
    }

    container.innerHTML = liveExams.length
        ? liveExams
            .map((liveExam) => renderAdminCard(liveExam))
            .join("")
        : `<div class="empty-state">No live exams have been created yet.</div>`;

    container.querySelectorAll(".js-live-exam-toggle").forEach((button) => {
        button.addEventListener("click", (event) => {
            const card = event.currentTarget.closest(".js-live-exam-card");
            const isExpanded = card?.classList.toggle("is-expanded");
            event.currentTarget.setAttribute("aria-expanded", isExpanded ? "true" : "false");
            event.currentTarget.setAttribute("aria-label", isExpanded ? "Collapse live exam details" : "Expand live exam details");
        });
    });

    container.querySelectorAll(".js-live-exam-close").forEach((button) => {
        button.addEventListener("click", async (event) => {
            const liveExamId = event.currentTarget.dataset.liveExamId;
            const card = event.currentTarget.closest(".card");
            const title = card?.querySelector("h2")?.textContent?.trim() || "this live exam";
            const confirmed = window.confirm(`Close ${title}? It will disappear from Live Exams but all recorded data will remain available.`);
            if (!confirmed) {
                return;
            }
            await request(`/api/live-exams/${liveExamId}/close`, { method: "POST" });
            const refreshed = await request("/api/live-exams");
            renderAdministratorList(container, refreshed.live_exams || []);
        });
    });

    container.querySelectorAll(".js-live-exam-delete").forEach((button) => {
        button.addEventListener("click", async (event) => {
            const liveExamId = event.currentTarget.dataset.liveExamId;
            const card = event.currentTarget.closest(".card");
            const title = card?.querySelector("h2")?.textContent?.trim() || "this live exam";
            const confirmed = window.confirm(`Delete ${title}? This removes the live exam, its assignments, and all attempts created from it.`);
            if (!confirmed) {
                return;
            }
            await request(`/api/live-exams/${liveExamId}`, { method: "DELETE" });
            const refreshed = await request("/api/live-exams");
            renderAdministratorList(container, refreshed.live_exams || []);
        });
    });
}

function renderAdminCard(liveExam) {
    return `
        <article class="card live-exam-card js-live-exam-card">
            <div class="live-exam-card__summary">
                <div class="live-exam-card__identity">
                    <p class="eyebrow">${escapeHtml(liveExam.exam_code)}</p>
                    <h2>${escapeHtml(liveExam.title)}</h2>
                    ${liveExam.description ? `<p class="muted live-exam-card__description">${escapeHtml(liveExam.description)}</p>` : ""}
                </div>
                <div class="live-exam-card__summary-actions">
                    <div class="button-row live-exam-card__button-row">
                        <button class="button button--secondary button--small js-live-exam-close" data-live-exam-id="${liveExam.id}" type="button">Close exam</button>
                        <button class="button button--danger button--small js-live-exam-delete" data-live-exam-id="${liveExam.id}" type="button">Delete exam</button>
                    </div>
                    <button class="live-exam-card__toggle js-live-exam-toggle" type="button" aria-expanded="false" aria-label="Expand live exam details">
                        <span aria-hidden="true">▾</span>
                    </button>
                </div>
            </div>
            <div class="live-exam-card__details">
                ${liveExam.instructions ? `<div class="live-exam-note"><strong>Instructions</strong><p class="muted">${escapeHtml(liveExam.instructions)}</p></div>` : ""}
                <div class="live-exam-card__metrics">
                    ${renderMetric("Source exam", escapeHtml(liveExam.exam_code))}
                    ${renderMetric("Assigned", liveExam.counts.assigned)}
                    ${renderMetric("Pending", liveExam.counts.pending)}
                    ${renderMetric("In progress", liveExam.counts.in_progress)}
                    ${renderMetric("Completed", liveExam.counts.completed)}
                    ${renderMetric("Questions", liveExam.question_count)}
                    ${renderMetric("Time limit", liveExam.time_limit_minutes ? `${liveExam.time_limit_minutes} min` : "Not set")}
                </div>
                <div class="live-exam-assignment-list">
                    ${(liveExam.assignments || []).length
                        ? liveExam.assignments
                            .map(
                                (assignment) => `
                            <div class="live-exam-assignment-row">
                                <div class="live-exam-assignment-row__identity">
                                    <strong>${escapeHtml(assignment.display_name)}</strong>
                                    <span class="muted">@${escapeHtml(assignment.login_name)}</span>
                                </div>
                                <div class="live-exam-assignment-row__actions">
                                    ${renderStatusBadge(assignment.assignment_status)}
                                    ${assignment.score_percent !== null && assignment.score_percent !== undefined ? `<span class="badge">${formatPercent(assignment.score_percent)}</span>` : ""}
                                    ${renderAdminAttemptLink(assignment)}
                                </div>
                            </div>
                        `
                            )
                            .join("")
                        : `<div class="empty-state">No users are assigned to this live exam.</div>`}
                </div>
            </div>
        </article>
    `;
}

function bindLiveExamModal({ availableExams, availableUsers, onCreated }) {
    const modal = document.getElementById("live-exam-modal");
    const form = document.getElementById("live-exam-form");
    const sourceSelect = document.getElementById("live-exam-source");
    const hintNode = document.getElementById("live-exam-source-hint");
    const errorNode = document.getElementById("live-exam-form-error");
    const closeButton = document.getElementById("live-exam-modal-close");
    const cancelButton = document.getElementById("live-exam-form-cancel");
    const backdrop = document.getElementById("live-exam-modal-backdrop");
    const questionCountInput = document.getElementById("live-exam-question-count");
    const timeLimitInput = document.getElementById("live-exam-time-limit");
    const difficultySelect = document.getElementById("live-exam-difficulty");
    const randomCheckbox = document.getElementById("live-exam-random");
    const sharedChipsContainers = {
        includeContainer: document.getElementById("live-exam-filters-include"),
        excludeContainer: document.getElementById("live-exam-filters-exclude"),
        includeEmptyLabel: "No included filters",
        excludeEmptyLabel: "No excluded filters",
    };
    const clearIncludeButton = document.getElementById("live-exam-filters-include-clear");
    const clearExcludeButton = document.getElementById("live-exam-filters-exclude-clear");
    let isClosing = false;
    let sourceRequestId = 0;
    let topicsField = null;
    let tagsField = null;
    let typesField = null;

    if (!modal || !form || !sourceSelect) {
        return { open() {} };
    }

    const userPicker = createUserAssignmentField(
        document.getElementById("live-exam-users-field"),
        availableUsers,
    );

    sourceSelect.innerHTML = availableExams.length
        ? [
            `<option value="">Select an exam</option>`,
            ...availableExams.map(
                (exam) => `<option value="${exam.id}">${escapeHtml(exam.code)}</option>`
            ),
        ].join("")
        : `<option value="">No eligible exams available</option>`;

    const syncClearButtons = () => {
        const topics = topicsField?.getValues() || { include: [], exclude: [] };
        const tags = tagsField?.getValues() || { include: [], exclude: [] };
        const types = typesField?.getValues() || { include: [], exclude: [] };
        clearIncludeButton.disabled = !topics.include.length && !tags.include.length && !types.include.length;
        clearExcludeButton.disabled = !topics.exclude.length && !tags.exclude.length && !types.exclude.length;
    };

    clearIncludeButton?.addEventListener("click", () => {
        topicsField?.setModeValues("include", []);
        tagsField?.setModeValues("include", []);
        typesField?.setModeValues("include", []);
    });
    clearExcludeButton?.addEventListener("click", () => {
        topicsField?.setModeValues("exclude", []);
        tagsField?.setModeValues("exclude", []);
        typesField?.setModeValues("exclude", []);
    });

    sourceSelect.addEventListener("change", async () => {
        await loadSourceMeta();
    });

    async function loadSourceMeta() {
        const selectedExam = availableExams.find((exam) => String(exam.id) === String(sourceSelect.value));
        const requestId = ++sourceRequestId;

        resetBuilderFields();
        updateSourceHint(selectedExam, questionCountInput, hintNode);
        if (!selectedExam) {
            return;
        }

        try {
            const response = await request(`/api/exams/${selectedExam.id}/builder-meta`);
            if (requestId !== sourceRequestId) {
                return;
            }
            const meta = response.builder_meta || {};
            topicsField = createAddableSelect(document.getElementById("live-exam-topics-field"), {
                id: "live-exam-topics",
                label: "Topics",
                options: meta.topics || [],
                placeholder: "Select a topic",
                sharedChipsContainers,
                sharedChipGroup: "topic",
                sharedChipGroupLabel: "Topic",
                sharedChipLabel: (value) => value,
                onChange: syncClearButtons,
            });
            tagsField = createAddableSelect(document.getElementById("live-exam-tags-field"), {
                id: "live-exam-tags",
                label: "Tags",
                options: meta.tags || [],
                placeholder: "Select a tag",
                sharedChipsContainers,
                sharedChipGroup: "tag",
                sharedChipGroupLabel: "Tag",
                sharedChipLabel: (value) => value,
                onChange: syncClearButtons,
            });
            typesField = createAddableSelect(document.getElementById("live-exam-types-field"), {
                id: "live-exam-types",
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
            syncClearButtons();
        } catch (error) {
            errorNode.textContent = error.message;
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorNode.textContent = "";

        const payload = {
            title: document.getElementById("live-exam-title").value.trim(),
            exam_id: Number(sourceSelect.value),
            topics: topicsField?.getValues() || { include: [], exclude: [] },
            tags: tagsField?.getValues() || { include: [], exclude: [] },
            question_types: typesField?.getValues() || { include: [], exclude: [] },
            difficulty: difficultySelect.value || "",
            question_count: Number(questionCountInput.value),
            time_limit_minutes: Number(timeLimitInput.value || 0),
            random_order: randomCheckbox.checked,
            description: document.getElementById("live-exam-description").value.trim(),
            instructions: document.getElementById("live-exam-instructions").value.trim(),
            user_ids: userPicker.getValues(),
        };

        try {
            await request("/api/live-exams", {
                method: "POST",
                body: payload,
            });
            resetLiveExamForm();
            closeModal(modal, () => {
                isClosing = false;
            });
            if (typeof onCreated === "function") {
                await onCreated();
            }
        } catch (error) {
            errorNode.textContent = error.message;
        }
    });

    function resetBuilderFields() {
        document.getElementById("live-exam-topics-field").innerHTML = "";
        document.getElementById("live-exam-tags-field").innerHTML = "";
        document.getElementById("live-exam-types-field").innerHTML = "";
        if (sharedChipsContainers.includeContainer.__selectionChipStore) {
            sharedChipsContainers.includeContainer.__selectionChipStore.clear();
        } else {
            sharedChipsContainers.includeContainer.innerHTML = `<button class="selection-chip selection-chip--empty" type="button" tabindex="-1">No included filters</button>`;
        }
        if (sharedChipsContainers.excludeContainer.__selectionChipStore) {
            sharedChipsContainers.excludeContainer.__selectionChipStore.clear();
        } else {
            sharedChipsContainers.excludeContainer.innerHTML = `<button class="selection-chip selection-chip--empty" type="button" tabindex="-1">No excluded filters</button>`;
        }
        topicsField = null;
        tagsField = null;
        typesField = null;
        syncClearButtons();
    }

    function resetLiveExamForm() {
        form.reset();
        sourceSelect.value = "";
        questionCountInput.value = "";
        questionCountInput.max = "";
        hintNode.textContent = "Select a source exam to see the available question count.";
        difficultySelect.value = "";
        randomCheckbox.checked = true;
        userPicker.reset();
        resetBuilderFields();
        errorNode.textContent = "";
    }

    const requestClose = () => {
        if (isClosing) {
            return;
        }
        isClosing = true;
        resetLiveExamForm();
        closeModal(modal, () => {
            isClosing = false;
        });
    };

    closeButton?.addEventListener("click", requestClose);
    cancelButton?.addEventListener("click", requestClose);
    backdrop?.addEventListener("click", requestClose);
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            requestClose();
        }
    });

    resetLiveExamForm();

    return {
        open() {
            if (!availableExams.length || !availableUsers.length) {
                return;
            }
            modal.hidden = false;
            modal.dataset.state = "closed";
            document.body.classList.add("modal-open");
            window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => {
                    modal.dataset.state = "open";
                });
            });
        },
    };
}

function createUserAssignmentField(container, users) {
    if (!container) {
        return {
            getValues: () => [],
            reset: () => {},
        };
    }

    let selectedIds = [];
    container.classList.add("selection-field");
    container.innerHTML = `
        <div class="selection-field__top">
            <span class="selection-field__label">Assigned users</span>
            <div class="selection-field__actions">
                <button id="live-exam-user-add" class="button button--secondary button--small" type="button">Add user</button>
            </div>
        </div>
        <select id="live-exam-users">
            <option value="">Select a user</option>
            ${users.map((user) => `<option value="${user.id}">${escapeHtml(user.display_name)} (${escapeHtml(user.login_name)})</option>`).join("")}
        </select>
        <div id="live-exam-user-list" class="live-exam-user-list"></div>
    `;

    const select = container.querySelector("#live-exam-users");
    const addButton = container.querySelector("#live-exam-user-add");
    const list = container.querySelector("#live-exam-user-list");

    const render = () => {
        if (!selectedIds.length) {
            list.innerHTML = `<div class="empty-state">No users assigned yet.</div>`;
            return;
        }
        list.innerHTML = selectedIds
            .map((userId) => {
                const user = users.find((entry) => entry.id === userId);
                if (!user) {
                    return "";
                }
                return `
                    <article class="live-exam-user-card" data-user-id="${user.id}">
                        <div>
                            <strong>${escapeHtml(user.display_name)}</strong>
                            <p class="muted">@${escapeHtml(user.login_name)}</p>
                        </div>
                        <div class="live-exam-user-card__meta">
                            <span class="badge">${escapeHtml(user.role)}</span>
                            <button class="button button--secondary button--small js-live-exam-user-remove" type="button">Remove</button>
                        </div>
                    </article>
                `;
            })
            .join("");
    };

    const addSelectedUser = () => {
        const userId = Number(select.value);
        if (!userId || selectedIds.includes(userId)) {
            return;
        }
        selectedIds = [...selectedIds, userId];
        select.value = "";
        render();
    };

    addButton.addEventListener("click", addSelectedUser);
    select.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            addSelectedUser();
        }
    });
    list.addEventListener("click", (event) => {
        const button = event.target.closest(".js-live-exam-user-remove");
        if (!button) {
            return;
        }
        const card = button.closest("[data-user-id]");
        const userId = Number(card?.dataset.userId);
        selectedIds = selectedIds.filter((value) => value !== userId);
        render();
    });

    render();

    return {
        getValues() {
            return [...selectedIds];
        },
        reset() {
            selectedIds = [];
            select.value = "";
            render();
        },
    };
}

function closeModal(modal, onClosed) {
    document.body.classList.remove("modal-open");
    modal.dataset.state = "closing";
    window.setTimeout(() => {
        modal.hidden = true;
        modal.dataset.state = "closed";
        if (typeof onClosed === "function") {
            onClosed();
        }
    }, 300);
}

function updateSourceHint(selectedExam, questionCountInput, hintNode) {
    if (!selectedExam) {
        hintNode.textContent = "Select a source exam to see the available question count.";
        questionCountInput.value = "";
        questionCountInput.max = "";
        return;
    }
    hintNode.textContent = `${selectedExam.code} currently exposes ${selectedExam.question_count} active questions.`;
    questionCountInput.max = String(selectedExam.question_count);
    if (!questionCountInput.value) {
        questionCountInput.value = String(Math.min(10, selectedExam.question_count));
    }
}

function renderStatusBadge(status) {
    const label = {
        pending: "Pending",
        in_progress: "In progress",
        completed: "Completed",
    }[status] || status;
    return `<span class="badge badge--${status.replace("_", "-")}">${escapeHtml(label)}</span>`;
}

function renderMetric(label, value) {
    return `
        <div class="live-exam-card__metric">
            <span class="muted">${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `;
}

function renderUserActionButton(assignment) {
    if (assignment.assignment_status === "completed" && assignment.attempt_id) {
        return `<a class="button button--secondary" href="/attempts/${assignment.attempt_id}/results">View results</a>`;
    }
    if (assignment.assignment_status === "in_progress") {
        return `<button class="button button--primary js-live-exam-start" data-assignment-id="${assignment.assignment_id}" type="button">Resume exam</button>`;
    }
    return `<button class="button button--primary js-live-exam-start" data-assignment-id="${assignment.assignment_id}" type="button">Start exam</button>`;
}

function renderAdminAttemptLink(assignment) {
    if (assignment.assignment_status === "completed" && assignment.attempt_id) {
        return `<a class="button button--secondary button--small" href="/attempts/${assignment.attempt_id}/results">Open results</a>`;
    }
    if (assignment.assignment_status === "in_progress" && assignment.attempt_id) {
        return `<a class="button button--secondary button--small" href="/attempts/${assignment.attempt_id}/run">Open attempt</a>`;
    }
    return "";
}
