import { assetPathToUrl, escapeHtml } from "../core/api.js";

let activeDragDropGesture = null;

export function renderQuestionCard(question, { mode = "study", index = 1, response = null } = {}) {
    const card = document.createElement("article");
    card.className = "panel question-card";
    card.dataset.questionId = question.id;
    card.dataset.questionType = question.type;
    card.dataset.questionConfig = JSON.stringify(question);

    const header = document.createElement("div");
    header.className = "question-card__header";
    header.innerHTML = `
        <div>
            <p class="eyebrow">Question ${index}</p>
            <h2>${escapeHtml(question.title || question.statement.slice(0, 80))}</h2>
        </div>
        <div class="badge-row">
            <span class="badge">${escapeHtml(question.type.replaceAll("_", " "))}</span>
            <span class="badge">${escapeHtml(question.difficulty || "intermediate")}</span>
        </div>
    `;
    card.appendChild(header);

    card.appendChild(renderQuestionMetadata(question));

    const statement = document.createElement("div");
    statement.className = "question-card__statement";
    statement.innerHTML = `<p>${escapeHtml(question.statement)}</p>`;
    card.appendChild(statement);

    const body = document.createElement("div");
    card.appendChild(body);

    if (question.type === "single_select" || question.type === "multiple_choice") {
        body.appendChild(renderChoiceQuestion(question, mode));
    } else if (question.type === "hot_spot") {
        body.appendChild(renderHotspotQuestion(question, mode));
    } else if (question.type === "drag_drop") {
        body.appendChild(renderDragDropQuestion(question, mode));
    }

    if (mode === "study") {
        const footer = document.createElement("div");
        footer.className = "button-row";
        footer.innerHTML = `<button class="button button--secondary js-check-question" type="button">Check answer</button>`;
        card.appendChild(footer);
    }

    const feedback = document.createElement("div");
    feedback.className = "feedback-slot";
    card.appendChild(feedback);

    if (response) {
        applyResponse(card, response);
    }

    return card;
}

function renderQuestionMetadata(question) {
    const items = [
        ...(question.tags || []).map((value) => ({ group: "tag", groupLabel: "Tag", value })),
        ...(question.topics || []).map((value) => ({ group: "topic", groupLabel: "Topic", value })),
    ];

    const metadata = document.createElement("div");

    if (!items.length) {
        metadata.className = "meta-row muted";
        metadata.textContent = "No tags or topics assigned.";
        return metadata;
    }

    metadata.className = "selection-field__chips question-card__meta";
    metadata.innerHTML = items
        .map((item) => `
            <span class="selection-chip selection-chip--static" data-group="${escapeHtml(item.group)}">
                <span class="selection-chip__group">${escapeHtml(item.groupLabel)}</span>
                <span class="selection-chip__value">${escapeHtml(item.value)}</span>
            </span>
        `)
        .join("");

    return metadata;
}

function renderChoiceQuestion(question, mode) {
    const isSingle = question.type === "single_select";
    const wrapper = document.createElement("fieldset");
    const name = `question-${question.id}`;
    for (const option of question.options || []) {
        const label = document.createElement("label");
        label.className = "question-option";
        label.innerHTML = `
            <input type="${isSingle ? "radio" : "checkbox"}" name="${name}" value="${escapeHtml(option.key)}" ${mode === "results" ? "disabled" : ""}>
            <span>${escapeHtml(option.text)}</span>
        `;
        wrapper.appendChild(label);
    }
    return wrapper;
}

function renderHotspotQuestion(question, mode) {
    const dropdowns = (question.config?.dropdowns || []).slice().sort((left, right) => left.order - right.order);
    if (!dropdowns.length) {
        return renderLegacyHotspotQuestion(question, mode);
    }

    const wrapper = document.createElement("div");
    wrapper.className = "stack-gap";
    const asset = question.assets?.[0];
    if (asset?.file_path) {
        const frame = document.createElement("div");
        frame.className = "hotspot-frame";
        frame.innerHTML = `<img src="${assetPathToUrl(asset.file_path)}" alt="${escapeHtml(asset?.meta?.alt || question.title || "Hot spot image")}">`;
        wrapper.appendChild(frame);
    }

    const hint = document.createElement("p");
    hint.className = "muted";
    hint.textContent =
        mode === "results"
            ? "Submitted dropdown selections for each numbered marker are shown below."
            : "Choose one option for each numbered marker shown in the image.";
    wrapper.appendChild(hint);

    const fields = document.createElement("div");
    fields.className = "hotspot-dropdowns";
    dropdowns.forEach((dropdown) => {
        const field = document.createElement("label");
        field.className = "hotspot-dropdown-row";
        field.innerHTML = `
            <strong class="hotspot-dropdown-row__index">${escapeHtml(String(dropdown.order))}.</strong>
            <select data-hotspot-dropdown-id="${escapeHtml(dropdown.id)}" aria-label="${escapeHtml(dropdown.label || `Dropdown ${dropdown.order}`)}" ${mode === "results" ? "disabled" : ""}>
                <option value="">Select an option</option>
                ${(dropdown.options || [])
                    .map((option) => `<option value="${escapeHtml(option)}">${escapeHtml(option)}</option>`)
                    .join("")}
            </select>
        `;
        fields.appendChild(field);
    });
    wrapper.appendChild(fields);

    return wrapper;
}

function renderLegacyHotspotQuestion(question, mode) {
    const wrapper = document.createElement("div");
    wrapper.className = "stack-gap";
    const asset = question.assets?.[0];
    const frame = document.createElement("div");
    frame.className = "hotspot-frame";
    frame.dataset.locked = mode === "results" ? "true" : "false";
    frame.innerHTML = `<img src="${assetPathToUrl(asset?.file_path)}" alt="${escapeHtml(asset?.meta?.alt || question.title || "Hot spot image")}">`;
    wrapper.appendChild(frame);

    const hint = document.createElement("p");
    hint.className = "muted";
    hint.textContent = mode === "results" ? "Submitted location shown below." : "Click the image to place your answer.";
    wrapper.appendChild(hint);

    frame.addEventListener("click", (event) => {
        if (frame.dataset.locked === "true") {
            return;
        }
        const rect = frame.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width) * 100;
        const y = ((event.clientY - rect.top) / rect.height) * 100;
        frame.dataset.x = x.toFixed(2);
        frame.dataset.y = y.toFixed(2);
        drawHotspotMarker(frame, x, y);
    });

    return wrapper;
}

function renderDragDropQuestion(question, mode) {
    const config = normalizeDragDropConfig(question);
    const wrapper = document.createElement("div");
    wrapper.className = "stack-gap drag-drop-question";
    wrapper.dataset.mappings = JSON.stringify({});
    wrapper.dataset.dragDropMode = config.mode;
    wrapper.dataset.interactive = mode !== "results" ? "true" : "false";

    const layout = document.createElement("div");
    layout.className = "drag-drop-layout";

    const bank = document.createElement("div");
    bank.className = "drag-bank";
    for (const item of config.items) {
        const itemNode = document.createElement("div");
        itemNode.className = "drag-item";
        itemNode.dataset.itemId = item.id;
        itemNode.dataset.bankItem = "true";
        itemNode.dataset.sourceDestinationId = "";
        itemNode.textContent = item.label;
        bank.appendChild(itemNode);
    }

    const zones = document.createElement("div");
    zones.className = "drag-zones";
    for (const destination of config.destinations) {
        const zone = document.createElement("div");
        zone.className = "drop-zone";
        zone.dataset.destinationId = destination.id;
        zone.innerHTML = `
            <p class="muted">${escapeHtml(destination.label)}</p>
            <div class="assigned-label"></div>
        `;
        zones.appendChild(zone);
    }

    layout.appendChild(bank);
    layout.appendChild(zones);
    wrapper.appendChild(layout);

    if (mode !== "results") {
        const reset = document.createElement("button");
        reset.className = "button button--secondary button--small";
        reset.type = "button";
        reset.textContent = "Reset mappings";
        reset.addEventListener("click", () => {
            wrapper.dataset.mappings = JSON.stringify({});
            syncDragDropView(wrapper, question);
        });
        wrapper.appendChild(reset);
    }

    syncDragDropView(wrapper, question);
    if (mode !== "results") {
        bindDragDropPointerInteractions(wrapper);
    }
    return wrapper;
}

function assignDragDropValue(wrapper, itemId, destinationId, question, sourceDestinationId = "") {
    if (!itemId || !destinationId) {
        return;
    }
    const mappings = normalizeDragDropMappings(JSON.parse(wrapper.dataset.mappings || "{}"), question);
    const config = normalizeDragDropConfig(question);
    if (sourceDestinationId && sourceDestinationId !== destinationId) {
        delete mappings[sourceDestinationId];
    }
    if (config.mode === "U") {
        Object.keys(mappings).forEach((mappedDestinationId) => {
            if (mappings[mappedDestinationId] === itemId && mappedDestinationId !== destinationId) {
                delete mappings[mappedDestinationId];
            }
        });
    }
    mappings[destinationId] = itemId;
    wrapper.dataset.mappings = JSON.stringify(mappings);
    syncDragDropView(wrapper, question);
}

function unassignDragDropValue(wrapper, destinationId, question) {
    const mappings = normalizeDragDropMappings(JSON.parse(wrapper.dataset.mappings || "{}"), question);
    delete mappings[destinationId];
    wrapper.dataset.mappings = JSON.stringify(mappings);
    syncDragDropView(wrapper, question);
}

function syncDragDropView(wrapper, question) {
    const config = normalizeDragDropConfig(question);
    const mappings = normalizeDragDropMappings(JSON.parse(wrapper.dataset.mappings || "{}"), question);
    const usedItemIds = new Set(Object.values(mappings));

    wrapper.querySelectorAll('.drag-item[data-bank-item="true"]').forEach((itemNode) => {
        const shouldHide = config.mode === "U" && usedItemIds.has(itemNode.dataset.itemId);
        itemNode.hidden = shouldHide;
    });

    wrapper.querySelectorAll(".drop-zone").forEach((zone) => {
        zone.classList.remove("assigned");
        const placeholder = zone.querySelector(".muted");
        const assignedLabel = zone.querySelector(".assigned-label");
        if (placeholder) {
            placeholder.hidden = false;
        }
        assignedLabel.innerHTML = "";
        const itemId = mappings[zone.dataset.destinationId];
        if (itemId) {
            const item = config.items.find((candidate) => candidate.id === itemId);
            assignedLabel.appendChild(
                createDragToken({
                    itemId,
                    label: item?.label || itemId,
                    sourceDestinationId: zone.dataset.destinationId,
                })
            );
            if (placeholder) {
                placeholder.hidden = true;
            }
            zone.classList.add("assigned");
        }
    });
}

function bindDragDropPointerInteractions(wrapper) {
    wrapper.addEventListener("pointerdown", (event) => {
        if (wrapper.dataset.interactive !== "true") {
            return;
        }
        if (!(event.target instanceof Element)) {
            return;
        }
        const token = event.target.closest(".drag-item");
        if (!token || !wrapper.contains(token)) {
            return;
        }
        if (event.pointerType === "mouse" && event.button !== 0) {
            return;
        }

        const itemId = token.dataset.itemId || "";
        if (!itemId) {
            return;
        }

        const card = wrapper.closest(".question-card");
        const question = extractQuestionConfig(card);
        if (!question?.config) {
            return;
        }

        event.preventDefault();
        startDragDropGesture({
            wrapper,
            question,
            token,
            itemId,
            label: token.textContent || itemId,
            sourceDestinationId: token.dataset.sourceDestinationId || "",
            pointerId: event.pointerId,
            clientX: event.clientX,
            clientY: event.clientY,
        });
    });
}

function startDragDropGesture({ wrapper, question, token, itemId, label, sourceDestinationId, pointerId, clientX, clientY }) {
    cancelActiveDragDropGesture();

    const ghost = document.createElement("div");
    ghost.className = "drag-drop-ghost";
    ghost.textContent = label;
    document.body.appendChild(ghost);

    const state = {
        wrapper,
        question,
        token,
        itemId,
        sourceDestinationId,
        pointerId,
        ghost,
        hoverTarget: null,
        move: null,
        end: null,
        cancel: null,
    };

    activeDragDropGesture = state;
    token.classList.add("is-dragging");
    document.body.classList.add("drag-drop-dragging");
    updateDragDropGhostPosition(state, clientX, clientY);
    updateDragDropHoverTarget(state, clientX, clientY);

    state.move = (event) => {
        if (!activeDragDropGesture || event.pointerId !== state.pointerId) {
            return;
        }
        updateDragDropGhostPosition(state, event.clientX, event.clientY);
        updateDragDropHoverTarget(state, event.clientX, event.clientY);
    };

    state.end = (event) => {
        if (!activeDragDropGesture || event.pointerId !== state.pointerId) {
            return;
        }
        finishDragDropGesture(state, event.clientX, event.clientY);
    };

    state.cancel = (event) => {
        if (!activeDragDropGesture || event.pointerId !== state.pointerId) {
            return;
        }
        cancelActiveDragDropGesture();
    };

    document.addEventListener("pointermove", state.move);
    document.addEventListener("pointerup", state.end);
    document.addEventListener("pointercancel", state.cancel);
}

function finishDragDropGesture(state, clientX, clientY) {
    const dropTarget = getDragDropTarget(state.wrapper, clientX, clientY);
    if (dropTarget?.classList.contains("drop-zone")) {
        assignDragDropValue(
            state.wrapper,
            state.itemId,
            dropTarget.dataset.destinationId,
            state.question,
            state.sourceDestinationId
        );
    } else if (dropTarget?.classList.contains("drag-bank") && state.sourceDestinationId) {
        unassignDragDropValue(state.wrapper, state.sourceDestinationId, state.question);
    }
    cancelActiveDragDropGesture();
}

function cancelActiveDragDropGesture() {
    if (!activeDragDropGesture) {
        return;
    }
    const state = activeDragDropGesture;
    document.removeEventListener("pointermove", state.move);
    document.removeEventListener("pointerup", state.end);
    document.removeEventListener("pointercancel", state.cancel);
    clearDragDropHoverState(state.wrapper);
    state.token.classList.remove("is-dragging");
    state.ghost.remove();
    document.body.classList.remove("drag-drop-dragging");
    activeDragDropGesture = null;
}

function updateDragDropGhostPosition(state, clientX, clientY) {
    state.ghost.style.left = `${clientX + 18}px`;
    state.ghost.style.top = `${clientY + 18}px`;
}

function updateDragDropHoverTarget(state, clientX, clientY) {
    const nextTarget = getDragDropTarget(state.wrapper, clientX, clientY);
    if (state.hoverTarget === nextTarget) {
        return;
    }
    clearDragDropHoverState(state.wrapper);
    state.hoverTarget = nextTarget;
    if (nextTarget) {
        nextTarget.classList.add("is-active");
    }
}

function clearDragDropHoverState(wrapper) {
    wrapper.querySelectorAll(".drag-bank, .drop-zone").forEach((node) => node.classList.remove("is-active"));
}

function getDragDropTarget(wrapper, clientX, clientY) {
    const target = document.elementFromPoint(clientX, clientY);
    if (!(target instanceof Element)) {
        return null;
    }
    const zone = target.closest(".drop-zone");
    if (zone && wrapper.contains(zone)) {
        return zone;
    }
    const bank = target.closest(".drag-bank");
    if (bank && wrapper.contains(bank)) {
        return bank;
    }
    return null;
}

function drawHotspotMarker(frame, x, y) {
    const existing = frame.querySelector(".hotspot-marker");
    if (existing) {
        existing.remove();
    }
    const marker = document.createElement("div");
    marker.className = "hotspot-marker";
    marker.style.left = `${x}%`;
    marker.style.top = `${y}%`;
    frame.appendChild(marker);
}

export function collectResponse(card) {
    const type = card.dataset.questionType;
    if (type === "single_select") {
        const selected = card.querySelector('input[type="radio"]:checked');
        return { selected: selected?.value || null };
    }
    if (type === "multiple_choice") {
        const selected = Array.from(card.querySelectorAll('input[type="checkbox"]:checked')).map((input) => input.value);
        return { selected };
    }
    if (type === "hot_spot") {
        const dropdowns = Array.from(card.querySelectorAll("[data-hotspot-dropdown-id]"));
        if (dropdowns.length) {
            const selections = {};
            dropdowns.forEach((select) => {
                selections[select.dataset.hotspotDropdownId] = select.value || "";
            });
            return { selections };
        }
        const frame = card.querySelector(".hotspot-frame");
        return {
            x: frame?.dataset.x ? Number(frame.dataset.x) : null,
            y: frame?.dataset.y ? Number(frame.dataset.y) : null,
        };
    }
    if (type === "drag_drop") {
        const wrapper = card.querySelector("[data-mappings]");
        const question = extractQuestionConfig(card);
        return { mappings: normalizeDragDropMappings(JSON.parse(wrapper?.dataset.mappings || "{}"), question) };
    }
    return {};
}

export function applyResponse(card, response) {
    if (!response) {
        return;
    }
    const type = card.dataset.questionType;
    if (type === "single_select") {
        const target = card.querySelector(`input[value="${CSS.escape(response.selected || "")}"]`);
        if (target) {
            target.checked = true;
        }
    }
    if (type === "multiple_choice") {
        for (const value of response.selected || []) {
            const target = card.querySelector(`input[value="${CSS.escape(value)}"]`);
            if (target) {
                target.checked = true;
            }
        }
    }
    if (type === "hot_spot") {
        const dropdowns = Array.from(card.querySelectorAll("[data-hotspot-dropdown-id]"));
        if (dropdowns.length) {
            const selections = response.selections || {};
            dropdowns.forEach((select) => {
                select.value = selections[select.dataset.hotspotDropdownId] || "";
            });
        } else {
            const frame = card.querySelector(".hotspot-frame");
            if (frame && response.x !== null && response.y !== null) {
                frame.dataset.x = response.x;
                frame.dataset.y = response.y;
                drawHotspotMarker(frame, response.x, response.y);
            }
        }
    }
    if (type === "drag_drop") {
        const wrapper = card.querySelector("[data-mappings]");
        if (wrapper) {
            const question = extractQuestionConfig(card);
            wrapper.dataset.mappings = JSON.stringify(normalizeDragDropMappings(response.mappings || {}, question));
            syncDragDropView(wrapper, question);
        }
    }
}

export function lockQuestionCard(card) {
    card.querySelectorAll("input, button, select").forEach((node) => {
        if (!node.classList.contains("js-check-question")) {
            node.disabled = true;
        }
    });
    const hotspot = card.querySelector(".hotspot-frame");
    if (hotspot) {
        hotspot.dataset.locked = "true";
    }
}

export function showFeedback(card, { success, title, body }) {
    const slot = card.querySelector(".feedback-slot");
    slot.innerHTML = `
        <div class="feedback-box ${success ? "success" : "error"}">
            <strong>${escapeHtml(title)}</strong>
            <p>${escapeHtml(body)}</p>
        </div>
    `;
}

export function formatCorrectAnswer(question, correctAnswer) {
    if (question.type === "single_select") {
        const option = (question.options || []).find((candidate) => candidate.key === correctAnswer);
        return `Correct option: ${option?.text || correctAnswer}`;
    }
    if (question.type === "multiple_choice") {
        const labels = (correctAnswer || []).map((key) => {
            const option = (question.options || []).find((candidate) => candidate.key === key);
            return option?.text || key;
        });
        return `Correct options: ${labels.join(", ")}`;
    }
    if (question.type === "hot_spot") {
        if (Array.isArray(correctAnswer) && correctAnswer.length && correctAnswer[0]?.correct_option) {
            return `Correct selections: ${correctAnswer.map((item) => `${item.order}. ${item.correct_option}`).join(" | ")}`;
        }
        return "Correct answer: a point inside the configured valid region.";
    }
    if (question.type === "drag_drop") {
        const config = normalizeDragDropConfig(question);
        const itemLabels = new Map(config.items.map((item) => [item.id, item.label]));
        const destinationLabels = new Map(config.destinations.map((destination) => [destination.id, destination.label]));
        const mappings = normalizeDragDropMappings(correctAnswer || {}, question);
        return `Correct mapping: ${Object.entries(mappings).map(([destinationId, itemId]) => `${destinationLabels.get(destinationId) || destinationId} -> ${itemLabels.get(itemId) || itemId}`).join(", ")}`;
    }
    return "";
}

function normalizeDragDropConfig(question) {
    const config = question?.config || {};
    return {
        mode: ["R", "U"].includes(config.mode) ? config.mode : "U",
        items: (config.items || []).map((item) => ({
            id: item.id,
            label: item.label,
        })),
        destinations: (config.destinations || []).map((destination) => ({
            id: destination.id,
            label: destination.label,
        })),
    };
}

function normalizeDragDropMappings(mappings, question) {
    const config = normalizeDragDropConfig(question);
    const itemIds = new Set(config.items.map((item) => item.id));
    const destinationIds = new Set(config.destinations.map((destination) => destination.id));
    const normalized = {};
    Object.entries(mappings || {}).forEach(([left, right]) => {
        const leftId = String(left || "").trim();
        const rightId = String(right || "").trim();
        if (!leftId || !rightId) {
            return;
        }
        if (destinationIds.has(leftId) && itemIds.has(rightId)) {
            normalized[leftId] = rightId;
            return;
        }
        if (itemIds.has(leftId) && destinationIds.has(rightId)) {
            normalized[rightId] = leftId;
        }
    });
    return normalized;
}

function createDragToken({ itemId, label, sourceDestinationId = "" }) {
    const itemNode = document.createElement("div");
    itemNode.className = "drag-item drag-item--assigned";
    itemNode.dataset.itemId = itemId;
    itemNode.dataset.sourceDestinationId = sourceDestinationId;
    itemNode.textContent = label;
    return itemNode;
}

function extractQuestionConfig(card) {
    return JSON.parse(card.dataset.questionConfig || "{}");
}

export function attachQuestionConfig(card, question) {
    card.dataset.questionConfig = JSON.stringify(question);
}
