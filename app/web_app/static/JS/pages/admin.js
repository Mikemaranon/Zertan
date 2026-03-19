import { renderDashboardLoadingState, renderDashboardView } from "../components/dashboard-view.js";
import { createGroupScopePicker } from "../components/group-scope-picker.js";
import { createSearchResultsPopover } from "../components/search-results-popover.js";
import { assetPathToUrl, escapeHtml, focusFieldForDesktop, request } from "../core/api.js";

export async function initAdminPage() {
    ensureAdminDom();

    const state = {
        users: [],
        groups: [],
        features: [],
        selectedGroupMemberIds: [],
        activeGroupViewId: null,
    };

    const nodes = {
        userList: document.getElementById("admin-users-list"),
        userScroll: document.getElementById("admin-users-scroll"),
        userSearchInput: document.getElementById("admin-user-search"),
        groupList: document.getElementById("admin-groups-list"),
        groupScroll: document.getElementById("admin-groups-scroll"),
        groupSearchInput: document.getElementById("admin-group-search"),
        userCreateButton: document.getElementById("admin-user-create"),
        groupCreateButton: document.getElementById("admin-group-create"),
        userForm: document.getElementById("admin-user-form"),
        userErrorNode: document.getElementById("admin-error"),
        userModalTitle: document.getElementById("admin-user-modal-title"),
        userGroupsField: document.getElementById("admin-user-groups-field"),
        groupForm: document.getElementById("admin-group-form"),
        groupErrorNode: document.getElementById("admin-group-error"),
        groupModalTitle: document.getElementById("admin-group-modal-title"),
        groupMemberSearchInput: document.getElementById("admin-group-user-search"),
        groupMemberResults: document.getElementById("admin-group-user-results"),
        groupMembersContainer: document.getElementById("admin-group-members"),
        groupViewTitle: document.getElementById("admin-group-view-title"),
        groupViewSubtitle: document.getElementById("admin-group-view-subtitle"),
        groupViewSearchInput: document.getElementById("admin-group-view-search"),
        groupViewMembers: document.getElementById("admin-group-view-members"),
        featureContainer: document.getElementById("admin-feature-toggles"),
        featureErrorNode: document.getElementById("admin-feature-error"),
    };

    const userModal = bindManagedModal({
        modalId: "admin-user-modal",
        backdropId: "admin-user-modal-backdrop",
        closeButtonId: "admin-user-modal-close",
        cancelButtonId: "admin-user-form-cancel",
        onClose: () => resetUserForm(nodes, userGroupPicker),
    });
    const groupModal = bindManagedModal({
        modalId: "admin-group-modal",
        backdropId: "admin-group-modal-backdrop",
        closeButtonId: "admin-group-modal-close",
        cancelButtonId: "admin-group-form-cancel",
        onClose: () => resetGroupForm(nodes, state),
    });
    const groupViewModal = bindManagedModal({
        modalId: "admin-group-view-modal",
        backdropId: "admin-group-view-modal-backdrop",
        closeButtonId: "admin-group-view-modal-close",
        onClose: () => resetGroupView(nodes, state),
    });
    const dashboardModal = bindAdminDashboardModal();

    if (
        !nodes.userList ||
        !nodes.userScroll ||
        !nodes.userSearchInput ||
        !nodes.groupList ||
        !nodes.groupScroll ||
        !nodes.groupSearchInput ||
        !nodes.userCreateButton ||
        !nodes.groupCreateButton ||
        !nodes.userForm ||
        !nodes.userGroupsField ||
        !nodes.groupForm ||
        !nodes.groupMemberSearchInput ||
        !nodes.groupMemberResults ||
        !nodes.groupMembersContainer ||
        !nodes.groupViewTitle ||
        !nodes.groupViewSubtitle ||
        !nodes.groupViewSearchInput ||
        !nodes.groupViewMembers ||
        !nodes.featureContainer
    ) {
        throw new Error("Admin workspace markup is incomplete. Reload the page and try again.");
    }

    const groupMemberPopover = createSearchResultsPopover(nodes.groupMemberSearchInput, nodes.groupMemberResults, {
        maxHeight: 320,
        renderPanel: renderGroupMemberSearchResults,
    });
    const userGroupPicker = createGroupScopePicker(nodes.userGroupsField, {
        searchLabel: "Search groups",
        searchPlaceholder: "Search by name or code",
        selectedLabel: "Assigned groups",
        emptySearchMessage: "Type a group name or code to search available groups.",
        emptySelectionMessage: "No groups assigned yet",
    });

    function renderUsers() {
        const groupsByUserId = buildGroupsByUserId(state.groups);
        const query = nodes.userSearchInput.value.trim().toLowerCase();
        const filteredUsers = state.users.filter((user) => {
            if (!query) {
                return true;
            }
            const groupNames = (groupsByUserId.get(user.id) || []).map((group) => group.name);
            return [user.display_name, user.login_name, user.role, user.status, ...groupNames].some((value) =>
                String(value || "").toLowerCase().includes(query)
            );
        });

        nodes.userList.innerHTML = filteredUsers.length
            ? filteredUsers.map((user) => renderUserCard(user, groupsByUserId.get(user.id) || [])).join("")
            : `<div class="empty-state">No users match the current search.</div>`;

        updateDirectoryHeight(nodes.userList, nodes.userScroll);
    }

    function renderGroups() {
        const query = nodes.groupSearchInput.value.trim().toLowerCase();
        const filteredGroups = state.groups.filter((group) => {
            if (!query) {
                return true;
            }
            const memberTerms = (group.members || []).flatMap((member) => [member.login_name, member.display_name]);
            return [group.name, group.description, group.code, ...memberTerms].some((value) =>
                String(value || "").toLowerCase().includes(query)
            );
        });

        nodes.groupList.innerHTML = filteredGroups.length
            ? filteredGroups.map((group) => renderGroupCard(group)).join("")
            : `<div class="empty-state">No groups match the current search.</div>`;

        updateDirectoryHeight(nodes.groupList, nodes.groupScroll);
    }

    function renderFeatureToggles() {
        nodes.featureContainer.innerHTML = state.features.length
            ? state.features
                .map(
                    (feature) => `
                <label class="feature-toggle-row" data-feature-key="${feature.feature_key}">
                    <div class="feature-toggle-row__copy">
                        <strong>${escapeHtml(feature.label)}</strong>
                        <p class="muted">${escapeHtml(feature.description || "")}</p>
                    </div>
                    <span class="feature-toggle">
                        <input class="js-feature-toggle" type="checkbox" ${feature.enabled ? "checked" : ""}>
                        <span class="feature-toggle__track" aria-hidden="true"></span>
                    </span>
                </label>
            `,
                )
                .join("")
            : `<div class="empty-state">No feature toggles are configured yet.</div>`;
    }

    function renderSelectedGroupMembers() {
        const selectedUsers = state.selectedGroupMemberIds
            .map((userId) => state.users.find((user) => Number(user.id) === Number(userId)))
            .filter(Boolean);

        if (!selectedUsers.length) {
            nodes.groupMembersContainer.innerHTML = `
                <button class="selection-chip selection-chip--empty" type="button" tabindex="-1">
                    No users added yet
                </button>
            `;
            return;
        }

        nodes.groupMembersContainer.innerHTML = selectedUsers
            .map(
                (user) => `
                <button class="selection-chip" type="button" data-user-id="${user.id}" data-group="user">
                    <span class="selection-chip__group">${escapeHtml(user.login_name)}</span>
                    <span class="selection-chip__value">${escapeHtml(user.display_name)}</span>
                </button>
            `,
            )
            .join("");
    }

    function renderGroupMemberSearchResults() {
        const query = nodes.groupMemberSearchInput.value.trim().toLowerCase();
        if (!query) {
            nodes.groupMemberResults.innerHTML = `<div class="empty-state">Type a login name to search available users.</div>`;
            return;
        }

        const matches = state.users.filter((user) =>
            String(user.login_name || "").toLowerCase().includes(query)
        );

        if (!matches.length) {
            nodes.groupMemberResults.innerHTML = `<div class="empty-state">No users match the current login search.</div>`;
            return;
        }

        nodes.groupMemberResults.innerHTML = matches
            .map((user) => {
                const isAdded = state.selectedGroupMemberIds.includes(Number(user.id));
                return `
                    <div class="admin-picker-result">
                        <div>
                            <strong>${escapeHtml(user.login_name)}</strong>
                            <p class="muted">${escapeHtml(user.display_name)} · ${escapeHtml(user.role)}</p>
                        </div>
                        <button
                            class="button ${isAdded ? "button--danger js-remove-group-member" : "button--secondary js-add-group-member"} button--small"
                            type="button"
                            data-user-id="${user.id}"
                        >
                            ${isAdded ? "Delete" : "Add"}
                        </button>
                    </div>
                `;
            })
            .join("");
    }

    async function loadUsers() {
        const data = await request("/api/admin/users");
        state.users = data.users || [];
        renderUsers();
        renderGroupMemberSearchResults();
        renderSelectedGroupMembers();
    }

    async function loadGroups() {
        const data = await request("/api/admin/user-groups");
        state.groups = data.groups || [];
        userGroupPicker?.setOptions(state.groups);
        renderGroups();
        renderUsers();
        renderActiveGroupView(nodes, state);
    }

    async function loadFeatures() {
        const data = await request("/api/admin/features");
        state.features = data.features || [];
        state.features.forEach(syncFeatureNavigation);
        renderFeatureToggles();
    }

    async function handleUserSubmit(event) {
        event.preventDefault();
        nodes.userErrorNode.textContent = "";
        const userId = document.getElementById("admin-user-id").value;
        const payload = {
            display_name: document.getElementById("admin-display-name").value.trim(),
            login_name: document.getElementById("admin-login-name").value.trim(),
            password: document.getElementById("admin-password").value,
            role: document.getElementById("admin-role").value,
            status: document.getElementById("admin-status").value,
            group_ids: userGroupPicker?.getValues() || [],
        };

        try {
            await request(userId ? `/api/admin/users/${userId}` : "/api/admin/users", {
                method: userId ? "PUT" : "POST",
                body: payload,
            });
            userModal.close();
            await Promise.all([loadUsers(), loadGroups()]);
        } catch (error) {
            nodes.userErrorNode.textContent = error.message;
        }
    }

    async function handleGroupSubmit(event) {
        event.preventDefault();
        nodes.groupErrorNode.textContent = "";
        const groupId = document.getElementById("admin-group-id").value;
        const payload = {
            name: document.getElementById("admin-group-name").value.trim(),
            description: document.getElementById("admin-group-description").value.trim(),
            user_ids: [...state.selectedGroupMemberIds],
        };

        try {
            await request(groupId ? `/api/admin/user-groups/${groupId}` : "/api/admin/user-groups", {
                method: groupId ? "PUT" : "POST",
                body: payload,
            });
            groupModal.close();
            await loadGroups();
        } catch (error) {
            nodes.groupErrorNode.textContent = error.message;
        }
    }

    async function handleFeatureToggleChange(event) {
        const input = event.target.closest(".js-feature-toggle");
        if (!input) {
            return;
        }

        const row = input.closest("[data-feature-key]");
        const featureKey = row?.dataset.featureKey;
        const enabled = input.checked;
        const previousValue = !enabled;
        nodes.featureErrorNode.textContent = "";
        input.disabled = true;

        try {
            const payload = await request(`/api/admin/features/${featureKey}`, {
                method: "PUT",
                body: { enabled },
            });
            state.features = state.features.map((feature) =>
                feature.feature_key === featureKey ? payload.feature : feature
            );
            syncFeatureNavigation(payload.feature);
            renderFeatureToggles();
        } catch (error) {
            input.checked = previousValue;
            input.disabled = false;
            nodes.featureErrorNode.textContent = error.message;
        }
    }

    nodes.userCreateButton.addEventListener("click", () => openUserCreateModal(nodes, userModal, userGroupPicker));
    nodes.groupCreateButton.addEventListener("click", () => openGroupCreateModal(nodes, state, groupModal));
    nodes.userSearchInput.addEventListener("input", renderUsers);
    nodes.groupSearchInput.addEventListener("input", renderGroups);
    nodes.groupViewSearchInput.addEventListener("input", () => renderActiveGroupView(nodes, state));
    nodes.userForm.addEventListener("submit", handleUserSubmit);
    nodes.groupForm.addEventListener("submit", handleGroupSubmit);
    nodes.featureContainer.addEventListener("change", handleFeatureToggleChange);

    nodes.userList.addEventListener("click", async (event) => {
        const card = event.target.closest("[data-user-id]");
        if (!card) {
            return;
        }
        const user = state.users.find((entry) => String(entry.id) === card.dataset.userId);
        if (!user) {
            return;
        }

        if (event.target.closest(".js-view-user")) {
            dashboardModal.open(user);
            return;
        }

        if (event.target.closest(".js-edit-user")) {
            openUserEditModal(nodes, state, userModal, user, userGroupPicker);
            return;
        }

        if (event.target.closest(".js-delete-user")) {
            if (!window.confirm(`Delete user ${user.login_name}?`)) {
                return;
            }
            await request(`/api/admin/users/${user.id}`, { method: "DELETE" });
            await Promise.all([loadUsers(), loadGroups()]);
        }
    });

    nodes.groupList.addEventListener("click", async (event) => {
        const card = event.target.closest("[data-group-id]");
        if (!card) {
            return;
        }
        const group = state.groups.find((entry) => String(entry.id) === card.dataset.groupId);
        if (!group) {
            return;
        }

        if (event.target.closest(".js-edit-group")) {
            openGroupEditModal(nodes, state, groupModal, group);
            return;
        }

        if (event.target.closest(".js-view-group")) {
            openGroupViewModal(nodes, state, groupViewModal, group);
            return;
        }

        if (event.target.closest(".js-delete-group")) {
            if (!window.confirm(`Delete group ${group.name}?`)) {
                return;
            }
            await request(`/api/admin/user-groups/${group.id}`, { method: "DELETE" });
            await loadGroups();
        }
    });

    nodes.groupMemberResults.addEventListener("click", (event) => {
        const addButton = event.target.closest(".js-add-group-member");
        if (addButton) {
            const userId = Number(addButton.dataset.userId);
            if (!state.selectedGroupMemberIds.includes(userId)) {
                state.selectedGroupMemberIds = [...state.selectedGroupMemberIds, userId];
                renderSelectedGroupMembers();
                renderGroupMemberSearchResults();
                groupMemberPopover.refresh();
            }
            return;
        }

        const removeButton = event.target.closest(".js-remove-group-member");
        if (removeButton) {
            const userId = Number(removeButton.dataset.userId);
            state.selectedGroupMemberIds = state.selectedGroupMemberIds.filter((value) => value !== userId);
            renderSelectedGroupMembers();
            renderGroupMemberSearchResults();
            groupMemberPopover.refresh();
        }
    });

    nodes.groupMembersContainer.addEventListener("click", (event) => {
        const chip = event.target.closest("[data-user-id]");
        if (!chip) {
            return;
        }
        state.selectedGroupMemberIds = state.selectedGroupMemberIds.filter(
            (userId) => Number(userId) !== Number(chip.dataset.userId)
        );
        renderSelectedGroupMembers();
        renderGroupMemberSearchResults();
    });

    window.addEventListener("resize", () => {
        updateDirectoryHeight(nodes.userList, nodes.userScroll);
        updateDirectoryHeight(nodes.groupList, nodes.groupScroll);
    });

    await Promise.all([loadUsers(), loadGroups(), loadFeatures()]);
}

function ensureAdminDom() {
    ensurePrimaryAdminLayout();
    ensureAdminUserModal();
    ensureAdminGroupModal();
    ensureAdminGroupViewModal();
}

function ensurePrimaryAdminLayout() {
    const hasNewLayout =
        document.getElementById("admin-user-create") &&
        document.getElementById("admin-group-create") &&
        document.getElementById("admin-groups-list");
    if (hasNewLayout) {
        return;
    }

    const grid = document.querySelector(".content-body > .grid.grid--two");
    if (!grid) {
        return;
    }

    grid.innerHTML = `
        <div class="panel">
            <div class="section-heading">
                <div>
                    <h2>User directory</h2>
                    <p class="muted">Manage platform access, edit user records, and inspect personal dashboards.</p>
                </div>
                <button id="admin-user-create" class="button button--primary" type="button" aria-label="Create user">+</button>
            </div>
            <div class="admin-directory-tools">
                <label class="admin-directory-search">
                    <span>Search users</span>
                    <input id="admin-user-search" type="search" placeholder="Search by name, login name, role, or status">
                </label>
            </div>
            <div id="admin-users-scroll" class="admin-users-scroll">
                <div id="admin-users-list" class="list-stack"></div>
            </div>
        </div>
        <div class="panel">
            <div class="section-heading">
                <div>
                    <h2>User groups</h2>
                    <p class="muted">Create reusable user scopes and manage memberships from the admin workspace.</p>
                </div>
                <button id="admin-group-create" class="button button--primary" type="button" aria-label="Create group">+</button>
            </div>
            <div class="admin-directory-tools">
                <label class="admin-directory-search">
                    <span>Search groups</span>
                    <input id="admin-group-search" type="search" placeholder="Search by name, description, or member">
                </label>
            </div>
            <div id="admin-groups-scroll" class="admin-users-scroll">
                <div id="admin-groups-list" class="list-stack"></div>
            </div>
        </div>
    `;
}

function ensureAdminUserModal() {
    if (document.getElementById("admin-user-modal")) {
        return;
    }
    document.body.insertAdjacentHTML(
        "beforeend",
        `
        <div id="admin-user-modal" class="profile-modal admin-form-modal" hidden>
            <div id="admin-user-modal-backdrop" class="profile-modal__backdrop"></div>
            <div class="profile-modal__dialog admin-form-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="admin-user-modal-title">
                <button id="admin-user-modal-close" class="profile-modal__close" type="button" aria-label="Close user form">Close</button>
                <div class="admin-form-modal__body">
                    <form id="admin-user-form" class="form-stack">
                        <div class="section-heading">
                            <div>
                                <h2 id="admin-user-modal-title">Create user</h2>
                                <p class="muted">Manage platform access and role assignments.</p>
                            </div>
                        </div>
                        <input id="admin-user-id" type="hidden">
                        <label><span>Name</span><input id="admin-display-name" type="text" required></label>
                        <label><span>Login name</span><input id="admin-login-name" type="text" required></label>
                        <label><span>Password</span><input id="admin-password" type="password"></label>
                        <label>
                            <span>Role</span>
                            <select id="admin-role">
                                <option value="user">User</option>
                                <option value="reviewer">Reviewer</option>
                                <option value="examiner">Examiner</option>
                                <option value="administrator">Administrator</option>
                            </select>
                        </label>
                        <label>
                            <span>Status</span>
                            <select id="admin-status">
                                <option value="active">Active</option>
                                <option value="disabled">Disabled</option>
                            </select>
                        </label>
                        <div id="admin-user-groups-field"></div>
                        <div id="admin-error" class="error-message"></div>
                        <div class="button-row">
                            <button class="button button--primary" type="submit">Save user</button>
                            <button id="admin-user-form-cancel" class="button button--secondary" type="button">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        `,
    );
}

function ensureAdminGroupModal() {
    if (document.getElementById("admin-group-modal")) {
        return;
    }
    document.body.insertAdjacentHTML(
        "beforeend",
        `
        <div id="admin-group-modal" class="profile-modal admin-form-modal" hidden>
            <div id="admin-group-modal-backdrop" class="profile-modal__backdrop"></div>
            <div class="profile-modal__dialog admin-form-modal__dialog admin-form-modal__dialog--wide" role="dialog" aria-modal="true" aria-labelledby="admin-group-modal-title">
                <button id="admin-group-modal-close" class="profile-modal__close" type="button" aria-label="Close group form">Close</button>
                <div class="admin-form-modal__body">
                    <form id="admin-group-form" class="form-stack">
                        <div class="section-heading">
                            <div>
                                <h2 id="admin-group-modal-title">Create group</h2>
                                <p class="muted">Use login-based search to add members and maintain group definitions.</p>
                            </div>
                        </div>
                        <input id="admin-group-id" type="hidden">
                        <label><span>Group name</span><input id="admin-group-name" type="text" required></label>
                        <label><span>Description</span><textarea id="admin-group-description" rows="3" placeholder="Optional description"></textarea></label>
                        <div class="admin-group-picker">
                            <label>
                                <span>Find users by login name</span>
                                <input id="admin-group-user-search" type="search" placeholder="Search users by login name">
                            </label>
                            <div id="admin-group-user-results" class="admin-picker-results"></div>
                        </div>
                        <div class="selection-field admin-group-members-field">
                            <div class="selection-field__top">
                                <span class="selection-field__label">Selected users</span>
                            </div>
                            <div id="admin-group-members" class="selection-field__chips"></div>
                        </div>
                        <div id="admin-group-error" class="error-message"></div>
                        <div class="button-row">
                            <button class="button button--primary" type="submit">Save group</button>
                            <button id="admin-group-form-cancel" class="button button--secondary" type="button">Cancel</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        `,
    );
}

function ensureAdminGroupViewModal() {
    if (document.getElementById("admin-group-view-modal")) {
        return;
    }
    document.body.insertAdjacentHTML(
        "beforeend",
        `
        <div id="admin-group-view-modal" class="profile-modal admin-form-modal" hidden>
            <div id="admin-group-view-modal-backdrop" class="profile-modal__backdrop"></div>
            <div class="profile-modal__dialog admin-form-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="admin-group-view-title">
                <button id="admin-group-view-modal-close" class="profile-modal__close" type="button" aria-label="Close group members">Close</button>
                <div class="admin-form-modal__body">
                    <section class="form-stack">
                        <div class="section-heading">
                            <div>
                                <h2 id="admin-group-view-title">Group members</h2>
                                <p id="admin-group-view-subtitle" class="muted">Members assigned to this group.</p>
                            </div>
                        </div>
                        <div class="admin-directory-tools admin-group-view-tools">
                            <label class="admin-directory-search">
                                <span>Search users</span>
                                <input id="admin-group-view-search" type="search" placeholder="Search by name, login name, role, or status">
                            </label>
                        </div>
                        <div id="admin-group-view-members" class="admin-group-view-list list-stack"></div>
                    </section>
                </div>
            </div>
        </div>
        `,
    );
}

function renderUserCard(user, groups) {
    const groupsLabel = groups.length
        ? groups.map((group) => group.name).join(", ")
        : "No groups assigned";
    return `
        <div class="card admin-directory-card" data-user-id="${user.id}">
            <div class="section-heading">
                <div>
                    <h3>${escapeHtml(user.display_name)}</h3>
                    <p class="muted">${escapeHtml(user.login_name)}</p>
                </div>
                <span class="badge">${escapeHtml(user.role)}</span>
            </div>
            <div class="admin-directory-card__meta">
                <span>Status: <strong>${escapeHtml(user.status)}</strong></span>
                <span title="${escapeHtml(groupsLabel)}">Groups: <strong>${groups.length}</strong></span>
            </div>
            <div class="button-row">
                <button class="button button--secondary button--small js-view-user" type="button">View</button>
                <button class="button button--secondary button--small js-edit-user" type="button">Edit</button>
                <button class="button button--danger button--small js-delete-user" type="button">Delete</button>
            </div>
        </div>
    `;
}

function renderGroupCard(group) {
    return `
        <div class="card admin-directory-card" data-group-id="${group.id}">
            <div class="section-heading">
                <div>
                    <h3>${escapeHtml(group.name)}</h3>
                    <p class="muted">${escapeHtml(group.code)}</p>
                </div>
                <span class="badge">${group.member_count} users</span>
            </div>
            <p class="muted">${escapeHtml(group.description || "No description provided.")}</p>
            <div class="button-row">
                <button class="button button--secondary button--small js-view-group" type="button">View</button>
                <button class="button button--secondary button--small js-edit-group" type="button">Edit</button>
                <button class="button button--danger button--small js-delete-group" type="button">Delete</button>
            </div>
        </div>
    `;
}

function openUserCreateModal(nodes, modal, userGroupPicker) {
    resetUserForm(nodes, userGroupPicker);
    nodes.userModalTitle.textContent = "Create user";
    modal.open();
    focusField("admin-display-name");
}

function openUserEditModal(nodes, state, modal, user, userGroupPicker) {
    resetUserForm(nodes, userGroupPicker);
    const groupsByUserId = buildGroupsByUserId(state.groups);
    nodes.userModalTitle.textContent = "Edit user";
    document.getElementById("admin-user-id").value = user.id;
    document.getElementById("admin-display-name").value = user.display_name;
    document.getElementById("admin-login-name").value = user.login_name;
    document.getElementById("admin-password").value = "";
    document.getElementById("admin-role").value = user.role;
    document.getElementById("admin-status").value = user.status;
    userGroupPicker?.setValues((groupsByUserId.get(user.id) || []).map((group) => group.id));
    userGroupPicker?.clearSearch();
    modal.open();
    focusField("admin-display-name");
}

function openGroupCreateModal(nodes, state, modal) {
    resetGroupForm(nodes, state);
    nodes.groupModalTitle.textContent = "Create group";
    modal.open();
    focusField("admin-group-name");
}

function openGroupEditModal(nodes, state, modal, group) {
    resetGroupForm(nodes, state);
    nodes.groupModalTitle.textContent = "Edit group";
    document.getElementById("admin-group-id").value = group.id;
    document.getElementById("admin-group-name").value = group.name;
    document.getElementById("admin-group-description").value = group.description || "";
    state.selectedGroupMemberIds = (group.members || []).map((member) => Number(member.id));
    nodes.groupMemberSearchInput.value = "";
    nodes.groupMemberResults.innerHTML = `<div class="empty-state">Type a login name to search available users.</div>`;
    nodes.groupErrorNode.textContent = "";
    modal.open();
    focusField("admin-group-name");
    renderSelectedMembersLater(nodes, state);
}

function openGroupViewModal(nodes, state, modal, group) {
    state.activeGroupViewId = group.id;
    nodes.groupViewSearchInput.value = "";
    renderGroupView(nodes, group);
    modal.open();
}

function renderActiveGroupView(nodes, state) {
    if (!state.activeGroupViewId) {
        return;
    }
    const group = state.groups.find((entry) => Number(entry.id) === Number(state.activeGroupViewId));
    if (!group) {
        nodes.groupViewTitle.textContent = "Group members";
        nodes.groupViewSubtitle.textContent = "This group is no longer available.";
        nodes.groupViewMembers.innerHTML = `<div class="empty-state">The selected group is no longer available.</div>`;
        return;
    }
    renderGroupView(nodes, group);
}

function renderGroupView(nodes, group) {
    const members = group.members || [];
    const query = nodes.groupViewSearchInput.value.trim().toLowerCase();
    const filteredMembers = members.filter((member) => {
        if (!query) {
            return true;
        }
        return [member.display_name, member.login_name, member.role, member.status].some((value) =>
            String(value || "").toLowerCase().includes(query)
        );
    });

    nodes.groupViewTitle.textContent = group.name || "Group members";
    nodes.groupViewSubtitle.textContent = `${members.length} member${members.length === 1 ? "" : "s"} assigned to ${group.name}.`;
    nodes.groupViewMembers.innerHTML = filteredMembers.length
        ? filteredMembers
            .map(
                (member) => `
                    <article class="card admin-group-view-card">
                        <div class="section-heading">
                            <div>
                                <h3>${escapeHtml(member.display_name)}</h3>
                                <p class="muted">${escapeHtml(member.login_name)}</p>
                            </div>
                            <span class="badge">${escapeHtml(member.role)}</span>
                        </div>
                        <p class="muted">Status: ${escapeHtml(member.status)}</p>
                    </article>
                `,
            )
            .join("")
        : `<div class="empty-state">${members.length ? "No users match the current search." : "No users are assigned to this group yet."}</div>`;
}

function renderSelectedMembersLater(nodes, state) {
    window.requestAnimationFrame(() => {
        const selectedUsers = state.selectedGroupMemberIds
            .map((userId) => state.users.find((user) => Number(user.id) === Number(userId)))
            .filter(Boolean);
        nodes.groupMembersContainer.innerHTML = selectedUsers.length
            ? selectedUsers
                .map(
                    (user) => `
                        <button class="selection-chip" type="button" data-user-id="${user.id}" data-group="user">
                            <span class="selection-chip__group">${escapeHtml(user.login_name)}</span>
                            <span class="selection-chip__value">${escapeHtml(user.display_name)}</span>
                        </button>
                    `,
                )
                .join("")
            : `<button class="selection-chip selection-chip--empty" type="button" tabindex="-1">No users added yet</button>`;
    });
}

function resetUserForm(nodes, userGroupPicker) {
    document.getElementById("admin-user-id").value = "";
    nodes.userForm.reset();
    document.getElementById("admin-role").value = "user";
    document.getElementById("admin-status").value = "active";
    userGroupPicker?.setValues([]);
    userGroupPicker?.clearSearch();
    nodes.userModalTitle.textContent = "Create user";
    nodes.userErrorNode.textContent = "";
}

function resetGroupForm(nodes, state) {
    document.getElementById("admin-group-id").value = "";
    nodes.groupForm.reset();
    nodes.groupModalTitle.textContent = "Create group";
    nodes.groupErrorNode.textContent = "";
    state.selectedGroupMemberIds = [];
    nodes.groupMemberResults.innerHTML = `<div class="empty-state">Type a login name to search available users.</div>`;
    nodes.groupMembersContainer.innerHTML = `
        <button class="selection-chip selection-chip--empty" type="button" tabindex="-1">
            No users added yet
        </button>
    `;
}

function resetGroupView(nodes, state) {
    state.activeGroupViewId = null;
    nodes.groupViewSearchInput.value = "";
    nodes.groupViewTitle.textContent = "Group members";
    nodes.groupViewSubtitle.textContent = "Members assigned to this group.";
    nodes.groupViewMembers.innerHTML = "";
}

function buildGroupsByUserId(groups) {
    const groupsByUserId = new Map();
    groups.forEach((group) => {
        (group.members || []).forEach((member) => {
            const existing = groupsByUserId.get(member.id) || [];
            existing.push({ id: group.id, name: group.name, code: group.code });
            groupsByUserId.set(member.id, existing);
        });
    });
    return groupsByUserId;
}

function updateDirectoryHeight(list, scrollContainer) {
    const cards = [...list.querySelectorAll(".card")];
    if (!cards.length) {
        scrollContainer.style.maxHeight = "";
        return;
    }
    const grid = scrollContainer.closest(".grid--two");
    const gridTemplateColumns = grid ? window.getComputedStyle(grid).gridTemplateColumns : "";
    const isVerticalLayout = !gridTemplateColumns || !gridTemplateColumns.includes(" ");
    const styles = window.getComputedStyle(list);
    const gap = Number.parseFloat(styles.rowGap || styles.gap || "0") || 0;
    const panel = scrollContainer.closest(".panel");
    const panelStyles = panel ? window.getComputedStyle(panel) : null;
    const panelBottomPadding = Number.parseFloat(panelStyles?.paddingBottom || "0") || 0;
    const maxVisibleCards = isVerticalLayout ? 3 : 4;
    const totalHeight = cards.reduce((total, card) => total + card.offsetHeight, 0) + gap * Math.max(cards.length - 1, 0);
    const targetCardHeight =
        cards.slice(0, maxVisibleCards).reduce((total, card) => total + card.offsetHeight, 0) +
        gap * Math.max(Math.min(cards.length, maxVisibleCards) - 1, 0);
    const viewportSafetyOffset = 27;
    const availableViewportHeight = Math.max(
        220,
        window.innerHeight - scrollContainer.getBoundingClientRect().top - panelBottomPadding - viewportSafetyOffset,
    );
    const desiredHeight = isVerticalLayout
        ? (cards.length > maxVisibleCards ? targetCardHeight : totalHeight)
        : (cards.length > maxVisibleCards ? Math.min(targetCardHeight, availableViewportHeight) : Math.min(totalHeight, availableViewportHeight));
    const constrainedHeight = totalHeight > desiredHeight ? Math.ceil(desiredHeight) : null;
    scrollContainer.style.maxHeight = constrainedHeight ? `${constrainedHeight}px` : "";
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

    function open() {
        if (!modal.hidden && modal.dataset.state === "open") {
            return;
        }
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

function syncFeatureNavigation(feature) {
    if (!feature) {
        return;
    }
    const featureLinks = {
        global_stats_page: {
            href: "/global-stats",
            label: "Global Stats",
            insertAfter: 'a[href="/dashboard"]',
        },
        live_exams_page: {
            href: "/live-exams",
            label: "Live Exams",
            insertAfter: 'a[href="/catalog"]',
        },
    };
    const config = featureLinks[feature.feature_key];
    if (!config) {
        return;
    }
    const nav = document.querySelector(".sidebar-nav");
    if (!nav) {
        return;
    }
    const existingLink = nav.querySelector(`a[href="${config.href}"]`);
    if (!feature.enabled) {
        existingLink?.remove();
        return;
    }
    if (existingLink) {
        return;
    }
    const anchor = nav.querySelector(config.insertAfter);
    const link = document.createElement("a");
    link.href = config.href;
    link.textContent = config.label;
    if (window.location.pathname === config.href) {
        link.classList.add("active");
    }
    if (anchor) {
        anchor.insertAdjacentElement("afterend", link);
        return;
    }
    nav.prepend(link);
}

function bindAdminDashboardModal() {
    const modal = document.getElementById("admin-dashboard-modal");
    if (!modal) {
        return { open() {} };
    }

    const closeButton = document.getElementById("admin-dashboard-modal-close");
    const backdrop = document.getElementById("admin-dashboard-modal-backdrop");
    const avatarNode = document.getElementById("admin-dashboard-avatar");
    const titleNode = document.getElementById("admin-dashboard-user-name");
    const subtitleNode = document.getElementById("admin-dashboard-subtitle");
    const loginNameNode = document.getElementById("admin-dashboard-login-name");
    const roleNode = document.getElementById("admin-dashboard-role");
    const statusNode = document.getElementById("admin-dashboard-status");
    const lastLoginNode = document.getElementById("admin-dashboard-last-login");
    const errorNode = document.getElementById("admin-dashboard-error");
    const dashboardNodes = {
        kpiContainer: document.getElementById("admin-dashboard-kpis"),
        attemptsContainer: document.getElementById("admin-dashboard-attempts"),
        typeContainer: document.getElementById("admin-dashboard-types"),
        examContainer: document.getElementById("admin-dashboard-exams"),
    };

    let isClosing = false;
    let requestSequence = 0;

    function open(user) {
        if (!user) {
            return;
        }
        requestSequence += 1;
        renderUserSummary(user);
        errorNode.textContent = "";
        renderDashboardLoadingState(dashboardNodes);
        showModal();
        void loadDashboard(user.id, requestSequence);
    }

    function showModal() {
        if (!modal.hidden && modal.dataset.state === "open") {
            return;
        }
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

    function closeModal() {
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
        }, 300);
    }

    function renderUserSummary(user) {
        const displayName = user.display_name || user.login_name || "User";
        titleNode.textContent = displayName;
        subtitleNode.textContent = `Viewing the personal dashboard for ${displayName}.`;
        loginNameNode.textContent = user.login_name || "n/a";
        roleNode.textContent = user.role || "n/a";
        statusNode.textContent = user.status || "n/a";
        lastLoginNode.textContent = formatDateTime(user.last_login_at);

        avatarNode.textContent = "";
        avatarNode.innerHTML = "";
        if (user.avatar_path) {
            const image = document.createElement("img");
            image.className = "profile-avatar__image";
            image.src = assetPathToUrl(user.avatar_path);
            image.alt = `${displayName} profile photo`;
            avatarNode.appendChild(image);
            return;
        }
        avatarNode.textContent = initialsFor(displayName);
    }

    async function loadDashboard(userId, token) {
        try {
            const payload = await request(`/api/statistics/users/${userId}`);
            if (token !== requestSequence) {
                return;
            }
            renderUserSummary(payload.user);
            renderDashboardView(dashboardNodes, {
                overviewData: payload.overview,
                personalData: payload.personal,
            });
        } catch (error) {
            if (token !== requestSequence) {
                return;
            }
            errorNode.textContent = error.message;
            const failureMarkup = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
            dashboardNodes.kpiContainer.innerHTML = failureMarkup;
            dashboardNodes.attemptsContainer.innerHTML = failureMarkup;
            dashboardNodes.attemptsContainer.style.maxHeight = "";
            dashboardNodes.typeContainer.innerHTML = failureMarkup;
            dashboardNodes.examContainer.innerHTML = failureMarkup;
        }
    }

    closeButton.addEventListener("click", closeModal);
    backdrop.addEventListener("click", closeModal);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            closeModal();
        }
    });

    return { open };
}

function initialsFor(value) {
    const tokens = String(value || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
    if (!tokens.length) {
        return "?";
    }
    if (tokens.length === 1) {
        return tokens[0].slice(0, 1).toUpperCase();
    }
    return `${tokens[0][0]}${tokens[tokens.length - 1][0]}`.toUpperCase();
}

function formatDateTime(value) {
    if (!value) {
        return "Never";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(date);
}
