import { escapeHtml } from "../core/api.js";

export function createAddableSelect(container, {
    id,
    label,
    options = [],
    placeholder = "Select an option",
    addLabel = "Add",
    formatLabel = (value) => value,
    initialValues = [],
    onChange = null,
} = {}) {
    const normalizedOptions = Array.from(new Set(options.filter(Boolean)));
    let selectedValues = [];

    container.classList.add("selection-field");
    container.innerHTML = `
        <div class="selection-field__top">
            <span class="selection-field__label">${escapeHtml(label)}</span>
            <button class="button button--secondary button--small" type="button">${escapeHtml(addLabel)}</button>
        </div>
        <select id="${escapeHtml(id)}">
            <option value="">${escapeHtml(placeholder)}</option>
            ${normalizedOptions
                .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(formatLabel(value))}</option>`)
                .join("")}
        </select>
        <div class="selection-field__chips"></div>
    `;

    const addButton = container.querySelector("button");
    const select = container.querySelector("select");
    const chips = container.querySelector(".selection-field__chips");

    const notifyChange = () => {
        if (typeof onChange === "function") {
            onChange([...selectedValues]);
        }
    };

    const renderChips = () => {
        if (!selectedValues.length) {
            chips.innerHTML = `<button class="selection-chip selection-chip--empty" type="button" tabindex="-1">No filters added</button>`;
            return;
        }

        chips.innerHTML = selectedValues
            .map((value) => `
                <button class="selection-chip" type="button" data-value="${escapeHtml(value)}">
                    ${escapeHtml(formatLabel(value))}
                </button>
            `)
            .join("");
    };

    const addSelectedValue = () => {
        const value = select.value;
        if (!value || selectedValues.includes(value)) {
            return;
        }
        selectedValues = [...selectedValues, value];
        renderChips();
        notifyChange();
    };

    const setValues = (values = []) => {
        selectedValues = Array.from(new Set(values.filter((value) => normalizedOptions.includes(value))));
        renderChips();
    };

    addButton.addEventListener("click", addSelectedValue);
    select.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            addSelectedValue();
        }
    });

    chips.addEventListener("click", (event) => {
        const chip = event.target.closest(".selection-chip[data-value]");
        if (!chip) {
            return;
        }
        selectedValues = selectedValues.filter((value) => value !== chip.dataset.value);
        renderChips();
        notifyChange();
    });

    setValues(initialValues);

    return {
        getValues() {
            return [...selectedValues];
        },
        setValues(values) {
            setValues(values);
            notifyChange();
        },
    };
}
