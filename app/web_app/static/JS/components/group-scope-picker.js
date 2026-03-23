import { createSearchResultsPopover } from "./search-results-popover.js";
import { escapeHtml } from "../core/api.js";

export function createGroupScopePicker(container, {
    searchLabel = "Search groups",
    searchPlaceholder = "Search groups",
    selectedLabel = "Included groups",
    emptySearchMessage = "Type to search available groups.",
    emptySelectionMessage = "No groups added yet",
} = {}) {
    if (!container) {
        return null;
    }

    let groups = [];
    let selectedGroupIds = [];

    container.classList.add("selection-field");
    container.innerHTML = `
        <div class="exam-scope-picker">
            <div class="exam-scope-picker__search">
                <label>
                    <span>${escapeHtml(searchLabel)}</span>
                    <input class="exam-scope-picker__input" type="search" placeholder="${escapeHtml(searchPlaceholder)}">
                </label>
                <div class="admin-picker-results exam-scope-picker__results"></div>
            </div>
            <div class="selection-field exam-scope-picker__selection-box">
                <div class="selection-field__top">
                    <span class="selection-field__label">${escapeHtml(selectedLabel)}</span>
                </div>
                <div class="selection-field__chips exam-scope-picker__chips"></div>
            </div>
        </div>
    `;

    const searchInput = container.querySelector(".exam-scope-picker__input");
    const resultsNode = container.querySelector(".exam-scope-picker__results");
    const chipsNode = container.querySelector(".exam-scope-picker__chips");

    const normalizeIds = (values) =>
        Array.from(new Set((values || []).map((value) => Number(value)).filter((value) => value > 0)));

    const renderSelected = () => {
        const selectedGroups = selectedGroupIds
            .map((groupId) => groups.find((group) => Number(group.id) === Number(groupId)))
            .filter(Boolean);

        if (!selectedGroups.length) {
            chipsNode.innerHTML = `
                <button class="selection-chip selection-chip--empty" type="button" tabindex="-1">
                    ${escapeHtml(emptySelectionMessage)}
                </button>
            `;
            return;
        }

        chipsNode.innerHTML = selectedGroups
            .map(
                (group) => `
                    <button class="selection-chip" type="button" data-group-id="${group.id}" data-group="group">
                        <span class="selection-chip__group">${escapeHtml(group.code)}</span>
                        <span class="selection-chip__value">${escapeHtml(group.name)}</span>
                    </button>
                `,
            )
            .join("");
    };

    function renderResults() {
        const query = searchInput.value.trim().toLowerCase();
        if (!query) {
            resultsNode.innerHTML = `<div class="empty-state">${escapeHtml(emptySearchMessage)}</div>`;
            return;
        }

        const matches = groups.filter((group) =>
            [group.name, group.code, group.description].some((value) => String(value || "").toLowerCase().includes(query))
        );

        if (!matches.length) {
            resultsNode.innerHTML = `<div class="empty-state">No groups match the current search.</div>`;
            return;
        }

        resultsNode.innerHTML = matches
            .map((group) => {
                const isSelected = selectedGroupIds.includes(Number(group.id));
                return `
                    <div class="admin-picker-result" data-group-id="${group.id}">
                        <div>
                            <strong>${escapeHtml(group.name)}</strong>
                            <p class="muted">${escapeHtml(`${group.code} · ${group.member_count || 0} members`)}</p>
                        </div>
                        <button
                            class="button ${isSelected ? "button--danger js-remove-group" : "button--secondary js-add-group"} button--small"
                            type="button"
                            data-group-id="${group.id}"
                        >
                            ${isSelected ? "Delete" : "Add"}
                        </button>
                    </div>
                `;
            })
            .join("");
    }

    const resultsPopover = createSearchResultsPopover(searchInput, resultsNode, {
        maxHeight: 280,
        renderPanel: renderResults,
    });

    const render = () => {
        selectedGroupIds = normalizeIds(selectedGroupIds).filter((groupId) =>
            groups.some((group) => Number(group.id) === Number(groupId))
        );
        renderSelected();
        renderResults();
    };

    resultsNode.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-group-id]");
        if (!button) {
            return;
        }
        const groupId = Number(button.dataset.groupId);
        if (button.classList.contains("js-add-group")) {
            if (!selectedGroupIds.includes(groupId)) {
                selectedGroupIds = [...selectedGroupIds, groupId];
            }
        } else if (button.classList.contains("js-remove-group")) {
            selectedGroupIds = selectedGroupIds.filter((value) => value !== groupId);
        }
        render();
        resultsPopover.refresh();
    });

    chipsNode.addEventListener("click", (event) => {
        const chip = event.target.closest("[data-group-id]");
        if (!chip) {
            return;
        }
        selectedGroupIds = selectedGroupIds.filter((value) => value !== Number(chip.dataset.groupId));
        render();
    });

    const api = {
        setOptions(nextGroups) {
            groups = Array.isArray(nextGroups) ? [...nextGroups] : [];
            render();
        },
        getValues() {
            return [...selectedGroupIds];
        },
        setValues(values) {
            selectedGroupIds = normalizeIds(values);
            render();
        },
        clearSearch() {
            searchInput.value = "";
            renderResults();
        },
    };

    container.__groupScopePicker = api;
    render();
    return api;
}
