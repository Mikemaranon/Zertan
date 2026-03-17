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
    sharedChipsContainer = null,
    sharedChipGroup = "",
    sharedChipGroupLabel = label,
    sharedChipLabel = (value) => formatLabel(value),
} = {}) {
    const normalizedOptions = Array.from(new Set(options.filter(Boolean)));
    let selectedValues = [];
    const usesSharedChips = Boolean(sharedChipsContainer);

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
        ${usesSharedChips ? "" : '<div class="selection-field__chips"></div>'}
    `;

    const addButton = container.querySelector("button");
    const select = container.querySelector("select");
    const chips = container.querySelector(".selection-field__chips");
    const sharedStore = usesSharedChips ? getSharedChipsStore(sharedChipsContainer) : null;

    const notifyChange = () => {
        if (typeof onChange === "function") {
            onChange([...selectedValues]);
        }
    };

    const renderChips = () => {
        if (usesSharedChips) {
            sharedStore.setGroup(id, {
                group: sharedChipGroup || id,
                groupLabel: sharedChipGroupLabel || label,
                values: selectedValues,
                formatLabel: sharedChipLabel,
                removeValue(value) {
                    selectedValues = selectedValues.filter((item) => item !== value);
                    renderChips();
                    notifyChange();
                },
            });
            return;
        }

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

    if (chips) {
        chips.addEventListener("click", (event) => {
            const chip = event.target.closest(".selection-chip[data-value]");
            if (!chip) {
                return;
            }
            selectedValues = selectedValues.filter((value) => value !== chip.dataset.value);
            renderChips();
            notifyChange();
        });
    }

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

function getSharedChipsStore(container) {
    if (container.__selectionChipStore) {
        return container.__selectionChipStore;
    }

    const store = {
        groups: new Map(),
        setGroup(id, config) {
            this.groups.set(id, config);
            this.render();
        },
        render() {
            const items = [];
            this.groups.forEach((config, ownerId) => {
                for (const value of config.values) {
                    items.push({
                        ownerId,
                        group: config.group,
                        groupLabel: config.groupLabel,
                        value,
                        label: config.formatLabel(value),
                    });
                }
            });

            if (!items.length) {
                container.innerHTML = `<button class="selection-chip selection-chip--empty" type="button" tabindex="-1">No filters added</button>`;
                return;
            }

            container.innerHTML = items
                .map((item) => `
                    <button class="selection-chip" type="button" data-owner-id="${escapeHtml(item.ownerId)}" data-group="${escapeHtml(item.group)}" data-group-label="${escapeHtml(item.groupLabel)}" data-value="${escapeHtml(item.value)}">
                        <span class="selection-chip__group">${escapeHtml(item.groupLabel)}</span>
                        <span class="selection-chip__value">${escapeHtml(item.label)}</span>
                    </button>
                `)
                .join("");
        },
    };

    container.addEventListener("click", (event) => {
        const chip = event.target.closest(".selection-chip[data-owner-id][data-value]");
        if (!chip) {
            return;
        }
        const group = store.groups.get(chip.dataset.ownerId);
        if (!group) {
            return;
        }
        group.removeValue(chip.dataset.value);
    });

    container.__selectionChipStore = store;
    store.render();
    return store;
}
