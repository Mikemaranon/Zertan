import { escapeHtml } from "../core/api.js";

export function createAddableSelect(container, {
    id,
    label,
    options = [],
    placeholder = "Select an option",
    includeLabel = "Include",
    excludeLabel = "Exclude",
    formatLabel = (value) => value,
    initialValues = { include: [], exclude: [] },
    onChange = null,
    sharedChipsContainers = null,
    sharedChipGroup = "",
    sharedChipGroupLabel = label,
    sharedChipLabel = (value) => formatLabel(value),
} = {}) {
    const normalizedOptions = Array.from(new Set(options.filter(Boolean)));
    let selectedValues = normalizeModeValues(initialValues, normalizedOptions);
    const usesSharedChips = Boolean(
        sharedChipsContainers?.includeContainer && sharedChipsContainers?.excludeContainer
    );

    container.classList.add("selection-field");
    container.innerHTML = `
        <div class="selection-field__top">
            <span class="selection-field__label">${escapeHtml(label)}</span>
            <div class="selection-field__actions">
                <button class="button button--secondary button--small" type="button" data-selection-mode="include">${escapeHtml(includeLabel)}</button>
                <button class="button button--secondary button--small" type="button" data-selection-mode="exclude">${escapeHtml(excludeLabel)}</button>
            </div>
        </div>
        <select id="${escapeHtml(id)}">
            <option value="">${escapeHtml(placeholder)}</option>
            ${normalizedOptions
                .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(formatLabel(value))}</option>`)
                .join("")}
        </select>
        ${
            usesSharedChips
                ? ""
                : `
            <div class="selection-field__mode-grid">
                <div class="selection-field__mode-panel">
                    <div class="selection-field__mode-title">Include</div>
                    <div class="selection-field__chips" data-chips-mode="include"></div>
                </div>
                <div class="selection-field__mode-panel">
                    <div class="selection-field__mode-title">Exclude</div>
                    <div class="selection-field__chips" data-chips-mode="exclude"></div>
                </div>
            </div>
        `
        }
    `;

    const includeButton = container.querySelector('[data-selection-mode="include"]');
    const excludeButton = container.querySelector('[data-selection-mode="exclude"]');
    const select = container.querySelector("select");
    const localChips = usesSharedChips
        ? null
        : {
            include: container.querySelector('[data-chips-mode="include"]'),
            exclude: container.querySelector('[data-chips-mode="exclude"]'),
        };
    const sharedStores = usesSharedChips
        ? {
            include: getSharedChipsStore(
                sharedChipsContainers.includeContainer,
                sharedChipsContainers.includeEmptyLabel || "No included filters"
            ),
            exclude: getSharedChipsStore(
                sharedChipsContainers.excludeContainer,
                sharedChipsContainers.excludeEmptyLabel || "No excluded filters"
            ),
        }
        : null;

    const notifyChange = () => {
        if (typeof onChange === "function") {
            onChange({
                include: [...selectedValues.include],
                exclude: [...selectedValues.exclude],
            });
        }
    };

    const renderChipsForMode = (mode) => {
        const modeValues = selectedValues[mode];
        if (usesSharedChips) {
            sharedStores[mode].setGroup(`${id}:${mode}`, {
                group: sharedChipGroup || id,
                groupLabel: sharedChipGroupLabel || label,
                values: modeValues,
                formatLabel: sharedChipLabel,
                removeValue(value) {
                    selectedValues[mode] = selectedValues[mode].filter((item) => item !== value);
                    renderChips();
                    notifyChange();
                },
            });
            return;
        }

        if (!modeValues.length) {
            localChips[mode].innerHTML = `<button class="selection-chip selection-chip--empty" type="button" tabindex="-1">${
                mode === "include" ? "No included filters" : "No excluded filters"
            }</button>`;
            return;
        }

        localChips[mode].innerHTML = modeValues
            .map((value) => `
                <button class="selection-chip" type="button" data-mode="${escapeHtml(mode)}" data-value="${escapeHtml(value)}">
                    ${escapeHtml(formatLabel(value))}
                </button>
            `)
            .join("");
    };

    const renderChips = () => {
        renderChipsForMode("include");
        renderChipsForMode("exclude");
    };

    const addSelectedValue = (mode) => {
        const value = select.value;
        if (!value || selectedValues[mode].includes(value)) {
            return;
        }
        const oppositeMode = mode === "include" ? "exclude" : "include";
        selectedValues[mode] = [...selectedValues[mode], value];
        selectedValues[oppositeMode] = selectedValues[oppositeMode].filter((item) => item !== value);
        renderChips();
        notifyChange();
    };

    const setValues = (values = { include: [], exclude: [] }) => {
        selectedValues = normalizeModeValues(values, normalizedOptions);
        renderChips();
    };

    const setModeValues = (mode, values = []) => {
        const nextValues = normalizeModeValues(
            {
                include: selectedValues.include,
                exclude: selectedValues.exclude,
                [mode]: values,
            },
            normalizedOptions,
        );
        const oppositeMode = mode === "include" ? "exclude" : "include";
        nextValues[oppositeMode] = nextValues[oppositeMode].filter((value) => !nextValues[mode].includes(value));
        selectedValues = nextValues;
        renderChips();
        notifyChange();
    };

    includeButton.addEventListener("click", () => addSelectedValue("include"));
    excludeButton.addEventListener("click", () => addSelectedValue("exclude"));
    select.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            addSelectedValue("include");
        }
    });

    if (localChips) {
        Object.entries(localChips).forEach(([mode, chipsContainer]) => {
            chipsContainer.addEventListener("click", (event) => {
                const chip = event.target.closest(".selection-chip[data-value]");
                if (!chip) {
                    return;
                }
                selectedValues[mode] = selectedValues[mode].filter((value) => value !== chip.dataset.value);
                renderChips();
                notifyChange();
            });
        });
    }

    setValues(initialValues);

    return {
        getValues() {
            return {
                include: [...selectedValues.include],
                exclude: [...selectedValues.exclude],
            };
        },
        setValues(values) {
            setValues(values);
            notifyChange();
        },
        setModeValues(mode, values) {
            setModeValues(mode, values);
        },
    };
}

function getSharedChipsStore(container, emptyLabel = "No filters added") {
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
                container.innerHTML = `<button class="selection-chip selection-chip--empty" type="button" tabindex="-1">${escapeHtml(emptyLabel)}</button>`;
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

function normalizeModeValues(values, options) {
    const normalized = Array.isArray(values)
        ? { include: values, exclude: [] }
        : {
            include: values?.include || [],
            exclude: values?.exclude || [],
        };
    const include = Array.from(new Set(normalized.include.filter((value) => options.includes(value))));
    const exclude = Array.from(
        new Set(normalized.exclude.filter((value) => options.includes(value) && !include.includes(value)))
    );
    return { include, exclude };
}
