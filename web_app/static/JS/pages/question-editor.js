import { getPageContext, request, splitCommaValues } from "../core/api.js";

export async function initQuestionEditorPage(pageContext) {
    const form = document.getElementById("question-form");
    const header = document.getElementById("question-editor-header");
    const errorNode = document.getElementById("question-form-error");
    const typeSelect = document.getElementById("question-type");
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

    if (pageContext.question_id) {
        const data = await request(`/api/questions/${pageContext.question_id}`);
        loadedQuestion = data.question;
        currentExamId = loadedQuestion.exam_id;
        fillQuestionForm(loadedQuestion);
    } else {
        document.getElementById("question-position").value = 1;
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
        const assetFile = document.getElementById("question-asset-file").files[0];
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
            window.location.href = `/exams/${currentExamId}`;
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
        window.location.href = `/exams/${currentExamId}`;
    });
}

function bindEditorButtons() {
    document.getElementById("add-option-button").addEventListener("click", () => addOptionRow());
    document.getElementById("add-region-button").addEventListener("click", () => addRegionRow());
    document.getElementById("add-item-button").addEventListener("click", () => addItemRow());
    document.getElementById("add-destination-button").addEventListener("click", () => addDestinationRow());
}

function updateVisibleSections() {
    const type = document.getElementById("question-type").value;
    document.getElementById("choice-section").classList.toggle("is-visible", ["single_select", "multiple_choice"].includes(type));
    document.getElementById("hotspot-section").classList.toggle("is-visible", type === "hot_spot");
    document.getElementById("dragdrop-section").classList.toggle("is-visible", type === "drag_drop");
}

function fillQuestionForm(question) {
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

    document.getElementById("regions-list").innerHTML = "";
    (question.config?.regions || []).forEach((region) => addRegionRow(region));

    document.getElementById("items-list").innerHTML = "";
    (question.config?.items || []).forEach((item) => addItemRow(item));
    document.getElementById("destinations-list").innerHTML = "";
    (question.config?.destinations || []).forEach((destination) =>
        addDestinationRow(destination, findItemIdByDestination(question.config?.mappings || {}, destination.id))
    );

    if (!question.options?.length) {
        addOptionRow();
        addOptionRow();
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
        position: Number(document.getElementById("question-position").value || 1),
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
            regions: Array.from(document.querySelectorAll(".region-row")).map((row, index) => ({
                id: row.querySelector(".region-id").value.trim() || `region-${index + 1}`,
                x: Number(row.querySelector(".region-x").value),
                y: Number(row.querySelector(".region-y").value),
                width: Number(row.querySelector(".region-width").value),
                height: Number(row.querySelector(".region-height").value),
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
                mappings[itemId] = destinationId;
            }
        });
        payload.config = { items, destinations, mappings };
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
    attachRemoveHandler(row);
    document.getElementById("options-list").appendChild(row);
}

function addRegionRow(region = {}) {
    const row = document.createElement("div");
    row.className = "row-box region-row inline-grid";
    row.innerHTML = `
        <label><span>Region id</span><input class="region-id" type="text" value="${region.id || ""}"></label>
        <label><span>X</span><input class="region-x" type="number" step="0.1" value="${region.x ?? 0}"></label>
        <label><span>Y</span><input class="region-y" type="number" step="0.1" value="${region.y ?? 0}"></label>
        <label><span>Width</span><input class="region-width" type="number" step="0.1" value="${region.width ?? 10}"></label>
        <label><span>Height</span><input class="region-height" type="number" step="0.1" value="${region.height ?? 10}"></label>
        <button class="button button--secondary button--small js-remove-row" type="button">Remove</button>
    `;
    attachRemoveHandler(row);
    document.getElementById("regions-list").appendChild(row);
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
    row.querySelector(".js-remove-row").addEventListener("click", () => row.remove());
}

function findItemIdByDestination(mappings, destinationId) {
    return Object.keys(mappings).find((itemId) => mappings[itemId] === destinationId) || "";
}
