import { escapeHtml, focusFieldForDesktop, request, splitCommaValues } from "../core/api.js";
import { confirmAction } from "../components/confirm-modal.js";
import { createGroupScopePicker } from "../components/group-scope-picker.js";
import { clearBusyState, renderCardSkeletons, renderErrorState } from "../components/loading-state.js";

const MAX_IMPORT_PACKAGE_SIZE = 5 * 1024 * 1024;
const IS_LITE_MODE = document.body.dataset.liteMode === "true";
const scopeState = {
    options: [],
    permissions: {
        allow_global: false,
        allow_groups: false,
    },
};

export async function initManagementPage() {
    const examList = document.getElementById("management-exam-list");
    const examForm = document.getElementById("exam-form");
    const importForm = document.getElementById("import-form");
    const examError = document.getElementById("exam-form-error");
    const importError = document.getElementById("import-error");
    const examFormModalTitle = document.getElementById("exam-form-modal-title");
    const examFormModalSubtitle = document.getElementById("exam-form-modal-subtitle");
    const examScopeMode = document.getElementById("exam-scope-mode");
    const importScopeMode = document.getElementById("import-scope-mode");
    const openExamFormButton = document.getElementById("open-exam-form-modal");
    const openImportFormButton = document.getElementById("open-import-form-modal");
    const examGroupPicker = createGroupScopePicker(document.getElementById("exam-group-picker"), {
        searchLabel: "Search groups",
        searchPlaceholder: "Search by name or code",
        selectedLabel: "Included groups",
        emptySearchMessage: "Type a group name or code to search available groups.",
    });
    const importGroupPicker = createGroupScopePicker(document.getElementById("import-group-picker"), {
        searchLabel: "Search groups",
        searchPlaceholder: "Search by name or code",
        selectedLabel: "Included groups",
        emptySearchMessage: "Type a group name or code to search available groups.",
    });
    const examFormModal = bindManagedModal({
        modalId: "exam-form-modal",
        backdropId: "exam-form-modal-backdrop",
        closeButtonId: "exam-form-modal-close",
        cancelButtonId: "exam-form-reset",
        onClose: () => resetForm(examGroupPicker),
    });
    const importFormModal = bindManagedModal({
        modalId: "import-form-modal",
        backdropId: "import-form-modal-backdrop",
        closeButtonId: "import-form-modal-close",
        cancelButtonId: "import-form-cancel",
        onClose: () => resetImportForm(importGroupPicker),
    });

    function openCreateExamModal(trigger = null) {
        resetForm(examGroupPicker);
        setExamFormPresentation({
            titleNode: examFormModalTitle,
            subtitleNode: examFormModalSubtitle,
            mode: "create",
        });
        examFormModal.open(trigger);
        focusField("exam-code");
    }

    function openEditExamModal(exam, trigger = null) {
        fillForm(exam, examGroupPicker);
        setExamFormPresentation({
            titleNode: examFormModalTitle,
            subtitleNode: examFormModalSubtitle,
            mode: "edit",
        });
        examFormModal.open(trigger);
        focusField("exam-code");
    }

    function openImportModal(trigger = null) {
        resetImportForm(importGroupPicker);
        importFormModal.open(trigger);
    }

    async function loadExams() {
        renderCardSkeletons(examList, { count: 5, showBadge: true, chips: 3, actions: 4 });
        try {
            const data = await request("/api/exams");
            scopeState.options = data.scope_options || [];
            scopeState.permissions = data.scope_permissions || scopeState.permissions;
            syncScopeControls(examGroupPicker, importGroupPicker);

            examList.innerHTML = data.exams
                .map((exam) => {
                    const scopeLabel = IS_LITE_MODE
                        ? "Local workspace"
                        : exam.is_global_scope
                            ? "Domain"
                            : (exam.scope_groups || []).map((group) => group.name).join(", ");
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
                    <div class="badge-row">
                        <span class="badge">${escapeHtml(scopeLabel)}</span>
                        ${(exam.tags || []).map((tag) => `<span class="badge">${escapeHtml(tag)}</span>`).join("")}
                    </div>
                    <div class="button-row exam-management__actions">
                        ${exam.can_manage ? `<button class="button button--secondary button--small js-edit-exam" type="button">Edit metadata</button>` : ""}
                        ${exam.can_edit_questions ? `<a class="button button--secondary button--small" href="/management/exams/${exam.id}/questions">Edit questions</a>` : ""}
                        ${exam.can_export_package ? `<button class="button button--primary button--small js-export-exam" type="button">Export package</button>` : ""}
                        ${exam.can_manage ? `<button class="button button--danger button--small js-delete-exam" type="button">Delete exam</button>` : ""}
                    </div>
                </div>
            `;
                })
                .join("");
            clearBusyState(examList);

            examList.querySelectorAll(".js-edit-exam").forEach((button) => {
                button.addEventListener("click", async (event) => {
                    const trigger = event.currentTarget;
                    const examId = trigger.closest("[data-exam-id]").dataset.examId;
                    const originalLabel = trigger.textContent;
                    trigger.disabled = true;
                    trigger.textContent = "Loading...";
                    try {
                        const payload = await request(`/api/exams/${examId}`);
                        openEditExamModal(payload.exam, trigger);
                    } finally {
                        trigger.disabled = false;
                        trigger.textContent = originalLabel;
                    }
                });
            });

            examList.querySelectorAll(".js-export-exam").forEach((button) => {
                button.addEventListener("click", (event) => {
                    const examId = event.currentTarget.closest("[data-exam-id]").dataset.examId;
                    window.location.href = `/api/import-export/exams/${examId}/export`;
                });
            });

            examList.querySelectorAll(".js-delete-exam").forEach((button) => {
                button.addEventListener("click", async (event) => {
                    const card = event.currentTarget.closest("[data-exam-id]");
                    const examId = card.dataset.examId;
                    const examTitle = card.querySelector("h3")?.textContent?.trim() || "this exam";
                    const confirmed = await confirmAction({
                        title: "Delete exam",
                        message: `Delete ${examTitle}? This removes the exam, its questions, attempts, answers, and linked assets.`,
                        confirmLabel: "Delete exam",
                        eyebrow: "Management action",
                    });
                    if (!confirmed) {
                        return;
                    }

                    try {
                        await request(`/api/exams/${examId}`, { method: "DELETE" });
                        if (document.getElementById("exam-id").value === examId) {
                            resetForm(examGroupPicker);
                        }
                        await loadExams();
                    } catch (error) {
                        if (examError) {
                            examError.textContent = error.message;
                        }
                    }
                });
            });
        } catch (error) {
            renderErrorState(examList, {
                title: "Unable to load managed exams",
                message: error.message,
                onRetry: loadExams,
            });
        }
    }

    if (examForm && examError) {
        openExamFormButton?.addEventListener("click", (event) => {
            openCreateExamModal(event.currentTarget);
        });
        examScopeMode?.addEventListener("change", () => {
            updateScopeFieldVisibility("exam-scope-mode", "exam-groups-field", "exam-group-picker");
        });
        examForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            examError.textContent = "";
            const selectedGroupIds = readScopeGroupIds(examScopeMode, examGroupPicker);
            if (examScopeMode?.value === "groups" && !selectedGroupIds.length) {
                examError.textContent = "Select at least one group for this exam.";
                return;
            }
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
                group_ids: selectedGroupIds,
            };

            try {
                await request(examId ? `/api/exams/${examId}` : "/api/exams", {
                    method: examId ? "PUT" : "POST",
                    body: payload,
                });
                resetForm(examGroupPicker);
                examFormModal.close();
                await loadExams();
            } catch (error) {
                examError.textContent = error.message;
            }
        });

        setExamFormPresentation({
            titleNode: examFormModalTitle,
            subtitleNode: examFormModalSubtitle,
            mode: "create",
        });
    }

    if (importForm && importError) {
        openImportFormButton?.addEventListener("click", (event) => {
            openImportModal(event.currentTarget);
        });
        importScopeMode?.addEventListener("change", () => {
            updateScopeFieldVisibility("import-scope-mode", "import-groups-field", "import-group-picker");
        });
        importForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            importError.textContent = "";
            const fileInput = document.getElementById("import-package");
            if (!fileInput.files.length) {
                importError.textContent = "Select a package file.";
                return;
            }
            const packageFile = fileInput.files[0];
            if (!String(packageFile.name || "").toLowerCase().endsWith(".zip")) {
                importError.textContent = "Upload a .zip exam package.";
                return;
            }
            if (packageFile.size > MAX_IMPORT_PACKAGE_SIZE) {
                importError.textContent = "Exam packages must be 5 MB or smaller.";
                return;
            }
            const selectedGroupIds = readScopeGroupIds(importScopeMode, importGroupPicker);
            if (importScopeMode?.value === "groups" && !selectedGroupIds.length) {
                importError.textContent = "Select at least one group for the imported exam.";
                return;
            }

            const formData = new FormData();
            formData.append("package", packageFile);
            formData.append("scope_mode", importScopeMode?.value || "global");
            for (const groupId of selectedGroupIds) {
                formData.append("group_ids", String(groupId));
            }

            try {
                await request("/api/import-export/exams/import", {
                    method: "POST",
                    formData,
                });
                resetImportForm(importGroupPicker);
                importFormModal.close();
                await loadExams();
            } catch (error) {
                importError.textContent = error.message;
            }
        });
    }

    await loadExams();
}

function fillForm(exam, examGroupPicker) {
    document.getElementById("exam-id").value = exam.id;
    document.getElementById("exam-code").value = exam.code;
    document.getElementById("exam-title").value = exam.title;
    document.getElementById("exam-provider").value = exam.provider;
    document.getElementById("exam-description").value = exam.description || "";
    document.getElementById("exam-official-url").value = exam.official_url || "";
    document.getElementById("exam-difficulty").value = exam.difficulty || "intermediate";
    document.getElementById("exam-status").value = exam.status || "draft";
    document.getElementById("exam-tags").value = (exam.tags || []).join(", ");
    const examScopeMode = document.getElementById("exam-scope-mode");
    if (examScopeMode) {
        examScopeMode.value = exam.scope_mode || (exam.is_global_scope ? "global" : "groups");
    }
    const errorNode = document.getElementById("exam-form-error");
    if (errorNode) {
        errorNode.textContent = "";
    }
    examGroupPicker?.setValues(exam.group_ids || []);
    examGroupPicker?.clearSearch();
    updateScopeFieldVisibility("exam-scope-mode", "exam-groups-field", "exam-group-picker");
}

function resetForm(examGroupPicker) {
    const form = document.getElementById("exam-form");
    if (!form) {
        return;
    }
    document.getElementById("exam-id").value = "";
    form.reset();
    const errorNode = document.getElementById("exam-form-error");
    if (errorNode) {
        errorNode.textContent = "";
    }
    examGroupPicker?.setValues([]);
    examGroupPicker?.clearSearch();
    updateScopeDefaults();
}

function resetImportForm(importGroupPicker) {
    const form = document.getElementById("import-form");
    if (!form) {
        return;
    }
    form.reset();
    const errorNode = document.getElementById("import-error");
    if (errorNode) {
        errorNode.textContent = "";
    }
    importGroupPicker?.setValues([]);
    importGroupPicker?.clearSearch();
    updateScopeDefaults();
}

function syncScopeControls(examGroupPicker, importGroupPicker) {
    if (IS_LITE_MODE) {
        return;
    }
    examGroupPicker?.setOptions(scopeState.options);
    importGroupPicker?.setOptions(scopeState.options);
    configureScopeMode("exam-scope-mode", "exam-scope-hint");
    configureScopeMode("import-scope-mode", "import-scope-hint");
    updateScopeDefaults();
}

function configureScopeMode(selectId, hintId) {
    const select = document.getElementById(selectId);
    const hint = document.getElementById(hintId);
    if (!select || !hint) {
        return;
    }

    const allowGlobal = Boolean(scopeState.permissions.allow_global);
    const allowGroups = Boolean(scopeState.permissions.allow_groups);
    const globalOption = select.querySelector('option[value="global"]');
    const groupsOption = select.querySelector('option[value="groups"]');

    if (globalOption) {
        globalOption.disabled = !allowGlobal;
        globalOption.hidden = !allowGlobal;
    }
    if (groupsOption) {
        groupsOption.disabled = !allowGroups;
        groupsOption.hidden = !allowGroups;
    }

    if (!allowGlobal && allowGroups) {
        select.value = "groups";
        hint.textContent = scopeState.options.length
            ? "Examiners can only assign exams to the groups they belong to."
            : "You do not belong to any group, so you cannot create or import exams yet.";
    } else if (allowGlobal) {
        hint.textContent = "Administrators can publish to the full domain or restrict availability to selected groups.";
    } else {
        hint.textContent = "No exam availability options are currently available for this account.";
    }

    select.disabled = !allowGlobal && !allowGroups;
    updateScopeFieldVisibility(
        selectId,
        selectId === "exam-scope-mode" ? "exam-groups-field" : "import-groups-field",
        selectId === "exam-scope-mode" ? "exam-group-picker" : "import-group-picker",
    );
}

function updateScopeDefaults() {
    const examScopeMode = document.getElementById("exam-scope-mode");
    const importScopeMode = document.getElementById("import-scope-mode");
    if (!examScopeMode && !importScopeMode) {
        return;
    }
    if (examScopeMode && !scopeState.permissions.allow_global && scopeState.permissions.allow_groups) {
        examScopeMode.value = "groups";
    }
    if (importScopeMode && !scopeState.permissions.allow_global && scopeState.permissions.allow_groups) {
        importScopeMode.value = "groups";
    }
    updateScopeFieldVisibility("exam-scope-mode", "exam-groups-field", "exam-group-picker");
    updateScopeFieldVisibility("import-scope-mode", "import-groups-field", "import-group-picker");
}

function updateScopeFieldVisibility(modeId, fieldId, containerId) {
    const modeNode = document.getElementById(modeId);
    const fieldNode = document.getElementById(fieldId);
    const containerNode = document.getElementById(containerId);
    if (!modeNode || !fieldNode || !containerNode) {
        return;
    }
    const useGroups = modeNode.value === "groups";
    fieldNode.hidden = !useGroups;
    containerNode.dataset.required = useGroups ? "true" : "false";
}

function readScopeGroupIds(modeNode, picker) {
    if (!modeNode || !picker || modeNode.value !== "groups") {
        return [];
    }
    return picker.getValues();
}

function setExamFormPresentation({ titleNode, subtitleNode, mode }) {
    if (titleNode) {
        titleNode.textContent = mode === "edit" ? "Update exam" : "Create exam";
    }
    if (subtitleNode) {
        subtitleNode.textContent = mode === "edit"
            ? "Update metadata for the selected certification bank."
            : "Manage metadata for structured certification banks.";
    }
}

function bindManagedModal({ modalId, backdropId, closeButtonId, cancelButtonId, onClose }) {
    const modal = document.getElementById(modalId);
    const backdrop = document.getElementById(backdropId);
    const closeButton = document.getElementById(closeButtonId);
    const cancelButton = cancelButtonId ? document.getElementById(cancelButtonId) : null;
    if (!modal || !backdrop || !closeButton) {
        return { open() {}, close() {} };
    }

    let isClosing = false;
    let lastTrigger = null;

    function open(trigger = null) {
        if (!modal.hidden && modal.dataset.state === "open") {
            return;
        }
        lastTrigger = trigger instanceof HTMLElement ? trigger : document.activeElement;
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
            if (typeof onClose === "function") {
                onClose();
            }
            if (lastTrigger instanceof HTMLElement && lastTrigger.isConnected) {
                lastTrigger.focus({ preventScroll: true });
            }
        }, 300);
    }

    closeButton.addEventListener("click", close);
    backdrop.addEventListener("click", close);
    cancelButton?.addEventListener("click", close);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            close();
        }
    });

    return { open, close };
}

function focusField(id) {
    window.setTimeout(() => {
        const field = document.getElementById(id);
        focusFieldForDesktop(field, { select: true });
    }, 140);
}
