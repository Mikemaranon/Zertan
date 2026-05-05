import { getPageContext, request, splitCommaValues } from "../core/api.js";

const ALLOWED_HOTSPOT_FILE_EXTENSIONS = new Set([".png", ".jpg", ".svg"]);

export async function initQuestionEditorPage(pageContext) {
    const form = document.getElementById("question-form");
    const header = document.getElementById("question-editor-header");
    const errorNode = document.getElementById("question-form-error");
    const typeSelect = document.getElementById("question-type");
    const assetFileInput = document.getElementById("question-asset-file");
    const cancelButton = document.getElementById("cancel-question-button");
    const returnPath = pageContext.return_to || "";
    let loadedQuestion = null;
    let currentExamId = pageContext.exam_id || null;

    header.innerHTML = `
        <div>
            <h2>${pageContext.question_id ? "Edit question" : "Create question"}</h2>
            <p class="muted">Editing is available inside study mode workflows for reviewer roles and above.</p>
        </div>
    `;

    bindEditorButtons();
    typeSelect.addEventListener("change", updateVisibleSections);
    cancelButton.addEventListener("click", () => {
        window.location.href = resolveReturnPath(returnPath, currentExamId, pageContext);
    });
    assetFileInput.addEventListener("change", () => {
        const validationMessage = validateHotspotAssetSelection(assetFileInput);
        if (validationMessage) {
            errorNode.textContent = validationMessage;
            assetFileInput.value = "";
            return;
        }
        if (errorNode.textContent === "Hot spot images must use .png, .jpg, or .svg files.") {
            errorNode.textContent = "";
        }
    });

    if (pageContext.question_id) {
        const data = await request(`/api/questions/${pageContext.question_id}`);
        loadedQuestion = data.question;
        currentExamId = loadedQuestion.exam_id;
        fillQuestionForm(loadedQuestion);
    } else {
        document.getElementById("question-position").value = "";
        addOptionRow();
        addOptionRow();
    }

    updateVisibleSections();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorNode.textContent = "";

        const payload = buildPayloadFromForm();
        const formData = new FormData();
        formData.append("payload", JSON.stringify(payload));
        const assetFile = assetFileInput.files[0];
        const validationMessage = validateHotspotAssetSelection(assetFileInput);
        if (validationMessage) {
            errorNode.textContent = validationMessage;
            return;
        }
        if (assetFile) {
            formData.append("asset_file", assetFile);
            formData.append("asset_type", "image");
            formData.append("asset_alt", document.getElementById("question-asset-alt").value.trim());
        }

        try {
            if (pageContext.question_id) {
                await request(`/api/questions/${pageContext.question_id}`, {
                    method: "PUT",
                    formData,
                });
            } else {
                await request(`/api/exams/${currentExamId}/questions`, {
                    method: "POST",
                    formData,
                });
            }
            window.location.href = returnPath || `/exams/${currentExamId}`;
        } catch (error) {
            errorNode.textContent = error.message;
        }
    });

    document.getElementById("archive-question-button").addEventListener("click", async () => {
        if (!pageContext.question_id) {
            errorNode.textContent = "Save the question before archiving it.";
            return;
        }
        await request(`/api/questions/${pageContext.question_id}/archive`, { method: "POST" });
        window.location.href = returnPath || `/exams/${currentExamId}`;
    });
}

function resolveReturnPath(returnPath, currentExamId, pageContext) {
    if (returnPath) {
        return returnPath;
    }
    if (currentExamId) {
        return `/exams/${currentExamId}`;
    }
    if (pageContext.exam_id) {
        return `/exams/${pageContext.exam_id}`;
    }
    return "/management/exams";
}

function bindEditorButtons() {
    document.getElementById("add-option-button").addEventListener("click", () => addOptionRow());
    document.getElementById("add-hotspot-dropdown-button").addEventListener("click", () => addHotspotDropdownRow());
    document.getElementById("add-item-button").addEventListener("click", () => addItemRow());
    document.getElementById("add-destination-button").addEventListener("click", () => addDestinationRow());
}

function updateVisibleSections() {
    const type = document.getElementById("question-type").value;
    document.getElementById("choice-section").classList.toggle("is-visible", ["single_select", "multiple_choice"].includes(type));
    document.getElementById("hotspot-section").classList.toggle("is-visible", type === "hot_spot");
    document.getElementById("dragdrop-section").classList.toggle("is-visible", type === "drag_drop");
    if (["single_select", "multiple_choice"].includes(type) && !document.querySelectorAll(".option-row").length) {
        addOptionRow();
        addOptionRow();
    }
    if (type === "hot_spot" && !document.querySelectorAll(".hotspot-dropdown-row").length) {
        addHotspotDropdownRow();
    }
    normalizeSingleSelectCorrectOption();
}

function fillQuestionForm(question) {
    const dragDropConfig = normalizeDragDropConfig(question.config || {});
    document.getElementById("question-id").value = question.id;
    document.getElementById("question-title").value = question.title || "";
    document.getElementById("question-statement").value = question.statement || "";
    document.getElementById("question-explanation").value = question.explanation || "";
    document.getElementById("question-type").value = question.type;
    document.getElementById("question-difficulty").value = question.difficulty || "intermediate";
    document.getElementById("question-tags").value = (question.tags || []).join(", ");
    document.getElementById("question-topics").value = (question.topics || []).join(", ");
    document.getElementById("question-status").value = question.status || "active";
    document.getElementById("question-position").value = question.position || 1;

    document.getElementById("options-list").innerHTML = "";
    (question.options || []).forEach((option) => addOptionRow(option));

    document.getElementById("hotspot-dropdowns-list").innerHTML = "";
    (question.config?.dropdowns || []).forEach((dropdown) => addHotspotDropdownRow(dropdown));

    document.getElementById("items-list").innerHTML = "";
    document.getElementById("dragdrop-mode").value = dragDropConfig.mode;
    dragDropConfig.items.forEach((item) => addItemRow(item));
    document.getElementById("destinations-list").innerHTML = "";
    dragDropConfig.destinations.forEach((destination) => addDestinationRow(destination, findItemIdByDestination(dragDropConfig.mappings, destination.id)));

    if (!question.options?.length) {
        addOptionRow();
        addOptionRow();
    }
    if (question.type === "hot_spot" && !(question.config?.dropdowns || []).length) {
        addHotspotDropdownRow();
    }
    updateVisibleSections();
}

function buildPayloadFromForm() {
    const type = document.getElementById("question-type").value;
    const payload = {
        title: document.getElementById("question-title").value.trim(),
        statement: document.getElementById("question-statement").value.trim(),
        explanation: document.getElementById("question-explanation").value.trim(),
        type,
        difficulty: document.getElementById("question-difficulty").value,
        tags: splitCommaValues(document.getElementById("question-tags").value),
        topics: splitCommaValues(document.getElementById("question-topics").value),
        status: document.getElementById("question-status").value,
        position: parseOptionalPositiveInteger(document.getElementById("question-position").value),
        assets: [],
    };

    if (["single_select", "multiple_choice"].includes(type)) {
        payload.options = Array.from(document.querySelectorAll(".option-row")).map((row, index) => ({
            key: row.querySelector(".option-key").value.trim() || String.fromCharCode(65 + index),
            text: row.querySelector(".option-text").value.trim(),
            is_correct: row.querySelector(".option-correct").checked,
        }));
        payload.config = {};
    }

    if (type === "hot_spot") {
        payload.options = [];
        payload.config = {
            dropdowns: Array.from(document.querySelectorAll(".hotspot-dropdown-row")).map((row, index) => ({
                id: row.querySelector(".hotspot-dropdown-id").value.trim() || `dropdown-${index + 1}`,
                order: Number(row.querySelector(".hotspot-dropdown-order").value || index + 1),
                label: row.querySelector(".hotspot-dropdown-label").value.trim(),
                options: splitLineValues(row.querySelector(".hotspot-dropdown-options").value),
                correct_option: row.querySelector(".hotspot-dropdown-correct").value.trim(),
            })),
        };
    }

    if (type === "drag_drop") {
        const items = Array.from(document.querySelectorAll(".item-row")).map((row, index) => ({
            id: row.querySelector(".item-id").value.trim() || `item-${index + 1}`,
            label: row.querySelector(".item-label").value.trim(),
        }));
        const destinations = Array.from(document.querySelectorAll(".destination-row")).map((row, index) => ({
            id: row.querySelector(".destination-id").value.trim() || `destination-${index + 1}`,
            label: row.querySelector(".destination-label").value.trim(),
        }));
        const mappings = {};
        Array.from(document.querySelectorAll(".destination-row")).forEach((row) => {
            const destinationId = row.querySelector(".destination-id").value.trim();
            const itemId = row.querySelector(".destination-match").value.trim();
            if (destinationId && itemId) {
                mappings[destinationId] = itemId;
            }
        });
        payload.config = {
            mode: document.getElementById("dragdrop-mode").value,
            items,
            destinations,
            mappings,
        };
        payload.options = [];
    }

    return payload;
}

function addOptionRow(option = {}) {
    const row = document.createElement("div");
    row.className = "row-box option-row inline-grid";
    row.innerHTML = `
        <label><span>Key</span><input class="option-key" type="text" value="${option.key || ""}"></label>
        <label><span>Text</span><input class="option-text" type="text" value="${option.text || ""}"></label>
        <label class="checkbox-line"><input class="option-correct" type="checkbox" ${option.is_correct ? "checked" : ""}><span>Correct</span></label>
        <button class="button button--secondary button--small js-remove-row" type="button">Remove</button>
    `;
    row.querySelector(".option-correct").addEventListener("change", (event) => handleOptionCorrectChange(event.currentTarget));
    attachRemoveHandler(row);
    document.getElementById("options-list").appendChild(row);
    normalizeSingleSelectCorrectOption();
}

function addHotspotDropdownRow(dropdown = {}) {
    const row = document.createElement("div");
    row.className = "row-box hotspot-dropdown-row";
    row.innerHTML = `
        <div class="inline-grid">
            <label><span>Dropdown id</span><input class="hotspot-dropdown-id" type="text" value="${dropdown.id || ""}" placeholder="dropdown-1"></label>
            <label><span>Order number</span><input class="hotspot-dropdown-order" type="number" min="1" value="${dropdown.order ?? ""}"></label>
            <label><span>Label</span><input class="hotspot-dropdown-label" type="text" value="${dropdown.label || ""}" placeholder="Dropdown 1"></label>
        </div>
        <label><span>Options</span><textarea class="hotspot-dropdown-options" rows="4" placeholder="One option per line">${(dropdown.options || []).join("\n")}</textarea></label>
        <label>
            <span>Correct option</span>
            <select class="hotspot-dropdown-correct">
                <option value="">Select the correct option</option>
            </select>
        </label>
        <button class="button button--secondary button--small js-remove-row" type="button">Remove</button>
    `;
    const optionsField = row.querySelector(".hotspot-dropdown-options");
    optionsField.addEventListener("input", () => syncHotspotCorrectOptions(row));
    attachRemoveHandler(row);
    document.getElementById("hotspot-dropdowns-list").appendChild(row);
    syncHotspotCorrectOptions(row, dropdown.correct_option || "");
}

function addItemRow(item = {}) {
    const row = document.createElement("div");
    row.className = "row-box item-row inline-grid";
    row.innerHTML = `
        <label><span>Item id</span><input class="item-id" type="text" value="${item.id || ""}"></label>
        <label><span>Label</span><input class="item-label" type="text" value="${item.label || ""}"></label>
        <button class="button button--secondary button--small js-remove-row" type="button">Remove</button>
    `;
    attachRemoveHandler(row);
    document.getElementById("items-list").appendChild(row);
}

function addDestinationRow(destination = {}, matchedItemId = "") {
    const row = document.createElement("div");
    row.className = "row-box destination-row inline-grid";
    row.innerHTML = `
        <label><span>Destination id</span><input class="destination-id" type="text" value="${destination.id || ""}"></label>
        <label><span>Label</span><input class="destination-label" type="text" value="${destination.label || ""}"></label>
        <label><span>Matched item id</span><input class="destination-match" type="text" value="${matchedItemId || ""}" placeholder="item-1"></label>
        <button class="button button--secondary button--small js-remove-row" type="button">Remove</button>
    `;
    attachRemoveHandler(row);
    document.getElementById("destinations-list").appendChild(row);
}

function attachRemoveHandler(row) {
    row.querySelector(".js-remove-row").addEventListener("click", () => {
        row.remove();
        normalizeSingleSelectCorrectOption();
    });
}

function handleOptionCorrectChange(checkbox) {
    const type = document.getElementById("question-type").value;
    if (type !== "single_select" || !checkbox.checked) {
        return;
    }

    document.querySelectorAll(".option-correct").forEach((input) => {
        if (input !== checkbox) {
            input.checked = false;
        }
    });
}

function normalizeSingleSelectCorrectOption() {
    if (document.getElementById("question-type").value !== "single_select") {
        return;
    }

    let checkedFound = false;
    document.querySelectorAll(".option-correct").forEach((input) => {
        if (input.checked && !checkedFound) {
            checkedFound = true;
            return;
        }
        if (input.checked) {
            input.checked = false;
        }
    });
}

function findItemIdByDestination(mappings, destinationId) {
    return mappings[destinationId] || "";
}

function normalizeDragDropConfig(config) {
    const items = (config?.items || []).map((item) => ({
        id: item.id || "",
        label: item.label || "",
    }));
    const destinations = (config?.destinations || []).map((destination) => ({
        id: destination.id || "",
        label: destination.label || "",
    }));
    const itemIds = new Set(items.map((item) => item.id));
    const destinationIds = new Set(destinations.map((destination) => destination.id));
    const mappings = {};

    Object.entries(config?.mappings || {}).forEach(([left, right]) => {
        const leftId = String(left || "").trim();
        const rightId = String(right || "").trim();
        if (!leftId || !rightId) {
            return;
        }
        if (destinationIds.has(leftId) && itemIds.has(rightId)) {
            mappings[leftId] = rightId;
            return;
        }
        if (itemIds.has(leftId) && destinationIds.has(rightId)) {
            mappings[rightId] = leftId;
        }
    });

    return {
        mode: ["R", "U"].includes(config?.mode) ? config.mode : "U",
        items,
        destinations,
        mappings,
    };
}

function splitLineValues(value) {
    return value
        .split(/\n|,/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function parseOptionalPositiveInteger(value) {
    const trimmed = String(value || "").trim();
    if (!trimmed) {
        return null;
    }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
        return null;
    }
    return Math.max(1, Math.floor(parsed));
}

function syncHotspotCorrectOptions(row, preferredValue = null) {
    const optionsField = row.querySelector(".hotspot-dropdown-options");
    const select = row.querySelector(".hotspot-dropdown-correct");
    const options = splitLineValues(optionsField.value);
    const nextValue = preferredValue ?? select.value;

    select.innerHTML = `<option value="">Select the correct option</option>`;
    options.forEach((option) => {
        const optionNode = document.createElement("option");
        optionNode.value = option;
        optionNode.textContent = option;
        select.appendChild(optionNode);
    });

    select.disabled = options.length === 0;
    select.value = options.includes(nextValue) ? nextValue : "";
}

function validateHotspotAssetSelection(input) {
    if (document.getElementById("question-type").value !== "hot_spot") {
        return "";
    }

    const file = input.files[0];
    if (!file) {
        return "";
    }

    const fileName = String(file.name || "").toLowerCase();
    const extension = fileName.includes(".") ? `.${fileName.split(".").pop()}` : "";
    if (!ALLOWED_HOTSPOT_FILE_EXTENSIONS.has(extension)) {
        return "Hot spot images must use .png, .jpg, or .svg files.";
    }

    return "";
}
