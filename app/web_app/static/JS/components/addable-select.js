import { escapeHtml } from "../core/api.js";
import { createSearchResultsPopover } from "./search-results-popover.js";

export function createAddableSelect(container, {
    id,
    label,
    options = [],
    placeholder = "Select an option",
    searchable = false,
    searchPlaceholder = "Type to search available options",
    emptySearchMessage = "Type to search available options.",
    noResultsMessage = "No options match the current search.",
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
    const normalizedOptions = normalizeOptions(options, formatLabel);
    const optionValues = normalizedOptions.map((option) => option.value);
    const optionMap = new Map(normalizedOptions.map((option) => [option.value, option]));
    let selectedValues = normalizeModeValues(initialValues, optionValues);
    let activeMode = "include";
    const usesSharedChips = Boolean(
        sharedChipsContainers?.includeContainer && sharedChipsContainers?.excludeContainer
    );

    container.classList.add("selection-field");
    container.innerHTML = `
        <div class="selection-field__top">
            <span class="selection-field__label">${escapeHtml(label)}</span>
            ${
                searchable
                    ? ""
                    : `
                <div class="selection-field__actions">
                    <button class="button button--secondary button--small" type="button" data-selection-mode="include">${escapeHtml(includeLabel)}</button>
                    <button class="button button--secondary button--small" type="button" data-selection-mode="exclude">${escapeHtml(excludeLabel)}</button>
                </div>
            `
            }
        </div>
        ${
            searchable
                ? `
            <div class="selection-field__search">
                <input id="${escapeHtml(id)}" class="selection-field__search-input" type="search" placeholder="${escapeHtml(searchPlaceholder)}" autocomplete="off">
            </div>
        `
                : `
            <select id="${escapeHtml(id)}">
                <option value="">${escapeHtml(placeholder)}</option>
                ${normalizedOptions
                    .map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(option.label)}</option>`)
                    .join("")}
            </select>
        `
        }
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
    const select = searchable ? null : container.querySelector("select");
    const searchInput = searchable ? container.querySelector(".selection-field__search-input") : null;
    const searchResults = searchable ? createFloatingResultsLayer() : null;
    const searchPopover = searchable
        ? createSearchResultsPopover(searchInput, searchResults, {
            maxHeight: 320,
            renderPanel: renderSearchResults,
        })
        : null;
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
    const getOptionMeta = (value) => optionMap.get(value) || createFallbackOption(value, formatLabel);
    const resolveValueLabel = (value) => {
        const option = getOptionMeta(value);
        return option.label || formatLabel(value, option);
    };
    const resolveSharedChipGroup = (value) => {
        const option = getOptionMeta(value);
        return typeof sharedChipGroup === "function" ? sharedChipGroup(value, option) : sharedChipGroup || option.group || id;
    };
    const resolveSharedChipGroupLabel = (value) => {
        const option = getOptionMeta(value);
        return typeof sharedChipGroupLabel === "function"
            ? sharedChipGroupLabel(value, option)
            : sharedChipGroupLabel || option.groupLabel || label;
    };
    const resolveSharedChipLabel = (value) => {
        const option = getOptionMeta(value);
        return sharedChipLabel(value, option);
    };

    const renderModeButtons = () => {
        const buttonMap = {
            include: includeButton,
            exclude: excludeButton,
        };
        Object.entries(buttonMap).forEach(([mode, button]) => {
            if (!button) {
                return;
            }
            const isActive = mode === activeMode;
            button.classList.toggle("button--primary", isActive);
            button.classList.toggle("button--secondary", !isActive);
            button.setAttribute("aria-pressed", String(isActive));
        });
    };

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
            const groupedValues = new Map();
            modeValues.forEach((value) => {
                const group = resolveSharedChipGroup(value);
                const groupLabel = resolveSharedChipGroupLabel(value);
                const ownerId = `${id}:${mode}:${group}`;
                if (!groupedValues.has(ownerId)) {
                    groupedValues.set(ownerId, {
                        ownerId,
                        group,
                        groupLabel,
                        values: [],
                    });
                }
                groupedValues.get(ownerId).values.push(value);
            });

            sharedStores[mode].clearGroupPrefix(`${id}:${mode}:`);
            groupedValues.forEach((groupConfig) => {
                sharedStores[mode].setGroup(groupConfig.ownerId, {
                    group: groupConfig.group,
                    groupLabel: groupConfig.groupLabel,
                    values: groupConfig.values,
                    formatLabel: resolveSharedChipLabel,
                    removeValue(value) {
                        selectedValues[mode] = selectedValues[mode].filter((item) => item !== value);
                        renderChips();
                        notifyChange();
                    },
                });
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
                    ${escapeHtml(resolveValueLabel(value))}
                </button>
            `)
            .join("");
    };

    const getSearchMatches = () => {
        if (!searchable) {
            return [];
        }

        const query = searchInput.value.trim().toLowerCase();
        if (!query) {
            return [];
        }

        return normalizedOptions.filter((option) =>
            option.searchTerms.some((term) => String(term || "").toLowerCase().includes(query))
        );
    };

    function renderSearchResults() {
        if (!searchable) {
            return;
        }

        const query = searchInput.value.trim().toLowerCase();
        if (!query) {
            searchResults.innerHTML = `<div class="empty-state">${escapeHtml(emptySearchMessage)}</div>`;
            return;
        }

        const matches = getSearchMatches();
        if (!matches.length) {
            searchResults.innerHTML = `<div class="empty-state">${escapeHtml(noResultsMessage)}</div>`;
            return;
        }

        searchResults.innerHTML = matches
            .map((option) => {
                const value = option.value;
                const isIncluded = selectedValues.include.includes(value);
                const isExcluded = selectedValues.exclude.includes(value);

                return `
                    <div class="selection-field__result">
                        <div>
                            <strong>${escapeHtml(option.label)}</strong>
                        </div>
                        <div class="selection-field__result-actions">
                            <button
                                class="button ${isIncluded ? "button--primary" : "button--secondary"} button--small"
                                type="button"
                                data-mode="include"
                                data-value="${escapeHtml(value)}"
                                aria-pressed="${isIncluded ? "true" : "false"}"
                            >
                                ${escapeHtml(includeLabel)}
                            </button>
                            <button
                                class="button ${isExcluded ? "button--danger" : "button--secondary"} button--small"
                                type="button"
                                data-mode="exclude"
                                data-value="${escapeHtml(value)}"
                                aria-pressed="${isExcluded ? "true" : "false"}"
                            >
                                ${escapeHtml(excludeLabel)}
                            </button>
                        </div>
                    </div>
                `;
            })
            .join("");
    }

    const renderChips = () => {
        renderModeButtons();
        renderChipsForMode("include");
        renderChipsForMode("exclude");
        renderSearchResults();
    };

    const addValue = (mode, value) => {
        if (!value || selectedValues[mode].includes(value)) {
            return;
        }
        const previousSearchScrollTop = searchPopover?.isOpen() ? searchResults.scrollTop : null;
        const oppositeMode = mode === "include" ? "exclude" : "include";
        selectedValues[mode] = [...selectedValues[mode], value];
        selectedValues[oppositeMode] = selectedValues[oppositeMode].filter((item) => item !== value);
        renderChips();
        notifyChange();
        restoreSearchResultsScroll(previousSearchScrollTop);
    };

    const removeValue = (mode, value) => {
        if (!value || !selectedValues[mode].includes(value)) {
            return;
        }
        const previousSearchScrollTop = searchPopover?.isOpen() ? searchResults.scrollTop : null;
        selectedValues[mode] = selectedValues[mode].filter((item) => item !== value);
        renderChips();
        notifyChange();
        restoreSearchResultsScroll(previousSearchScrollTop);
    };

    const addSelectedValue = (mode) => {
        if (!select) {
            return;
        }
        addValue(mode, select.value);
    };

    const setValues = (values = { include: [], exclude: [] }) => {
        selectedValues = normalizeModeValues(values, optionValues);
        renderChips();
    };

    const setModeValues = (mode, values = []) => {
        const nextValues = normalizeModeValues(
            {
                include: selectedValues.include,
                exclude: selectedValues.exclude,
                [mode]: values,
            },
            optionValues,
        );
        const oppositeMode = mode === "include" ? "exclude" : "include";
        nextValues[oppositeMode] = nextValues[oppositeMode].filter((value) => !nextValues[mode].includes(value));
        selectedValues = nextValues;
        renderChips();
        notifyChange();
    };

    const restoreSearchResultsScroll = (scrollTop) => {
        if (scrollTop === null || scrollTop === undefined || !searchPopover?.isOpen()) {
            searchPopover?.updatePosition();
            return;
        }
        window.requestAnimationFrame(() => {
            searchResults.scrollTop = scrollTop;
            searchPopover.updatePosition();
        });
    };

    includeButton?.addEventListener("click", () => {
        activeMode = "include";
        addSelectedValue("include");
    });
    excludeButton?.addEventListener("click", () => {
        activeMode = "exclude";
        addSelectedValue("exclude");
    });
    if (select) {
        select.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                addSelectedValue("include");
            }
        });
    }
    if (searchInput && searchResults) {
        searchInput.addEventListener("keydown", (event) => {
            if (event.key !== "Enter") {
                return;
            }
            event.preventDefault();
            const firstMatch = getSearchMatches()[0];
            if (firstMatch) {
                addValue("include", firstMatch.value);
            }
        });
        searchInput.addEventListener("blur", () => {
            window.setTimeout(() => {
                const activeNode = document.activeElement;
                if (activeNode === searchInput || searchResults.contains(activeNode)) {
                    return;
                }
                searchPopover?.close();
            }, 0);
        });
        searchResults.addEventListener("click", (event) => {
            const button = event.target.closest("button[data-value]");
            if (!button) {
                return;
            }
            const value = button.dataset.value;
            const mode = button.dataset.mode;
            if (!value || !["include", "exclude"].includes(mode)) {
                return;
            }
            if (selectedValues[mode].includes(value)) {
                removeValue(mode, value);
                return;
            }
            addValue(mode, value);
        });
    }

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
        clearGroupPrefix(prefix) {
            this.groups.forEach((_, key) => {
                if (key.startsWith(prefix)) {
                    this.groups.delete(key);
                }
            });
            this.render();
        },
        clear() {
            this.groups.clear();
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

function createFloatingResultsLayer() {
    const node = document.createElement("div");
    node.className = "selection-field__results";
    node.hidden = true;
    return node;
}

function normalizeOptions(options, formatLabel) {
    const normalized = new Map();
    options.filter(Boolean).forEach((option) => {
        const entry = typeof option === "object" && option !== null
            ? {
                value: String(option.value || "").trim(),
                label: String(option.label || formatLabel(option.value || "", option) || "").trim(),
                group: String(option.group || "").trim(),
                groupLabel: String(option.groupLabel || "").trim(),
                searchTerms: Array.from(new Set([
                    option.value,
                    option.label,
                    option.group,
                    option.groupLabel,
                    ...(option.searchTerms || []),
                ].filter(Boolean).map((value) => String(value)))),
            }
            : createFallbackOption(option, formatLabel);

        if (entry.value) {
            normalized.set(entry.value, entry);
        }
    });

    return Array.from(normalized.values());
}

function createFallbackOption(value, formatLabel) {
    return {
        value: String(value || "").trim(),
        label: String(formatLabel(value) || value || "").trim(),
        group: "",
        groupLabel: "",
        searchTerms: Array.from(new Set([value, formatLabel(value)].filter(Boolean).map((item) => String(item)))),
    };
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
