import { assetPathToUrl, escapeHtml } from "../core/api.js";

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

    const metadata = document.createElement("div");
    metadata.className = "meta-row muted";
    metadata.innerHTML = `
        <span>Topics: ${question.topics?.length ? escapeHtml(question.topics.join(", ")) : "none"}</span>
        <span>Tags: ${question.tags?.length ? escapeHtml(question.tags.join(", ")) : "none"}</span>
    `;
    card.appendChild(metadata);

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
        field.className = "selection-field";
        field.innerHTML = `
            <span class="selection-field__top">
                <strong>${escapeHtml(String(dropdown.order))}.</strong>
                <span>${escapeHtml(dropdown.label || `Dropdown ${dropdown.order}`)}</span>
            </span>
            <select data-hotspot-dropdown-id="${escapeHtml(dropdown.id)}" ${mode === "results" ? "disabled" : ""}>
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
    const wrapper = document.createElement("div");
    wrapper.className = "stack-gap";
    wrapper.dataset.mappings = JSON.stringify({});

    const bank = document.createElement("div");
    bank.className = "grid grid--cards drag-bank";
    for (const item of question.config?.items || []) {
        const itemNode = document.createElement("div");
        itemNode.className = "drag-item";
        itemNode.draggable = mode !== "results";
        itemNode.dataset.itemId = item.id;
        itemNode.textContent = item.label;
        itemNode.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/plain", item.id);
        });
        bank.appendChild(itemNode);
    }

    const zones = document.createElement("div");
    zones.className = "grid grid--cards";
    for (const destination of question.config?.destinations || []) {
        const zone = document.createElement("div");
        zone.className = "drop-zone";
        zone.dataset.destinationId = destination.id;
        zone.innerHTML = `
            <strong>${escapeHtml(destination.label)}</strong>
            <p class="muted">Drop one item here</p>
            <div class="assigned-label"></div>
        `;
        if (mode !== "results") {
            zone.addEventListener("dragover", (event) => {
                event.preventDefault();
                zone.classList.add("is-active");
            });
            zone.addEventListener("dragleave", () => zone.classList.remove("is-active"));
            zone.addEventListener("drop", (event) => {
                event.preventDefault();
                zone.classList.remove("is-active");
                const itemId = event.dataTransfer.getData("text/plain");
                assignDragDropValue(wrapper, itemId, destination.id, question);
            });
        }
        zones.appendChild(zone);
    }

    wrapper.appendChild(bank);
    wrapper.appendChild(zones);

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
    return wrapper;
}

function assignDragDropValue(wrapper, itemId, destinationId, question) {
    const mappings = JSON.parse(wrapper.dataset.mappings || "{}");
    Object.keys(mappings).forEach((key) => {
        if (mappings[key] === destinationId) {
            delete mappings[key];
        }
    });
    mappings[itemId] = destinationId;
    wrapper.dataset.mappings = JSON.stringify(mappings);
    syncDragDropView(wrapper, question);
}

function syncDragDropView(wrapper, question) {
    const mappings = JSON.parse(wrapper.dataset.mappings || "{}");
    wrapper.querySelectorAll(".drop-zone").forEach((zone) => {
        zone.classList.remove("assigned");
        const assignedLabel = zone.querySelector(".assigned-label");
        assignedLabel.textContent = "";
        const entry = Object.entries(mappings).find(([, destinationId]) => destinationId === zone.dataset.destinationId);
        if (entry) {
            const [itemId] = entry;
            const item = (question.config?.items || []).find((candidate) => candidate.id === itemId);
            assignedLabel.textContent = item?.label || itemId;
            zone.classList.add("assigned");
        }
    });
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
        return { mappings: JSON.parse(wrapper?.dataset.mappings || "{}") };
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
            wrapper.dataset.mappings = JSON.stringify(response.mappings || {});
            const question = extractQuestionConfig(card);
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
        const mappings = correctAnswer || {};
        return `Correct mapping: ${Object.entries(mappings).map(([item, destination]) => `${item} -> ${destination}`).join(", ")}`;
    }
    return "";
}

function extractQuestionConfig(card) {
    return JSON.parse(card.dataset.questionConfig || "{}");
}

export function attachQuestionConfig(card, question) {
    card.dataset.questionConfig = JSON.stringify(question);
}
