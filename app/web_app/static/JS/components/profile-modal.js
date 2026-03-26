import { assetPathToUrl, escapeHtml, focusFieldForDesktop, getCurrentUser, request } from "../core/api.js";

export function bindProfileModal() {
    const modal = document.getElementById("profile-modal");
    if (!modal) {
        return;
    }

    const openButtons = [...document.querySelectorAll("[data-open-profile-modal]")];
    const closeButton = document.getElementById("profile-modal-close");
    const backdrop = document.getElementById("profile-modal-backdrop");
    const editToggle = document.getElementById("profile-edit-toggle");
    const editPanel = document.getElementById("profile-edit-panel");
    const cancelButton = document.getElementById("profile-form-cancel");
    const form = document.getElementById("profile-credentials-form");
    const avatarInput = document.getElementById("profile-avatar-input");
    const avatarError = document.getElementById("profile-avatar-error");
    const formError = document.getElementById("profile-form-error");
    const examCountNode = document.getElementById("profile-exam-count");
    const titleNode = document.getElementById("profile-modal-title");
    const roleNode = document.getElementById("profile-role");
    const loginNameNode = document.getElementById("profile-login-name");
    const groupsNode = document.getElementById("profile-groups");
    const nameInput = document.getElementById("profile-display-name");
    const currentPasswordInput = document.getElementById("profile-current-password");
    const newPasswordInput = document.getElementById("profile-new-password");
    const confirmPasswordInput = document.getElementById("profile-confirm-password");
    const avatarNode = document.getElementById("profile-avatar");
    const currentUserData = document.getElementById("current-user-data");

    let currentUser = getCurrentUser();
    let statsLoaded = false;
    let isClosing = false;

    function openModal() {
        if (!modal.hidden && modal.dataset.state === "open") {
            return;
        }
        isClosing = false;
        renderUser();
        resetFormState();
        modal.hidden = false;
        modal.dataset.state = "closed";
        document.body.classList.add("modal-open");
        window.requestAnimationFrame(() => {
            window.requestAnimationFrame(() => {
                modal.dataset.state = "open";
            });
        });
        void loadStats();
    }

    function closeModal() {
        if (modal.hidden || isClosing) {
            return;
        }
        isClosing = true;
        modal.dataset.state = "closing";
        document.body.classList.remove("modal-open");
        hideEditPanel();
        avatarError.textContent = "";
        formError.textContent = "";
        avatarInput.value = "";

        window.setTimeout(() => {
            modal.hidden = true;
            modal.dataset.state = "closed";
            isClosing = false;
        }, 300);
    }

    function renderUser() {
        titleNode.textContent = currentUser.display_name || currentUser.username || currentUser.login_name;
        roleNode.textContent = currentUser.role || "";
        loginNameNode.textContent = currentUser.login_name || "";
        renderGroups();
        nameInput.value = currentUser.display_name || currentUser.username || "";
        renderModalAvatar();
        syncShellUser();
    }

    function renderGroups() {
        if (!groupsNode) {
            return;
        }
        const groups = Array.isArray(currentUser.groups) ? currentUser.groups : [];
        groupsNode.innerHTML = groups.length
            ? groups
                .map(
                    (group) => `
                        <span class="profile-summary__group-chip" title="${escapeHtml(group.code ? `${group.name} (${group.code})` : group.name)}">
                            ${escapeHtml(group.name)}
                        </span>
                    `
                )
                .join("")
            : `<span class="profile-summary__group-empty">No groups assigned</span>`;
    }

    function renderModalAvatar() {
        avatarNode.textContent = "";
        avatarNode.innerHTML = "";
        if (currentUser.avatar_path) {
            const img = document.createElement("img");
            img.className = "profile-avatar__image";
            img.src = assetPathToUrl(currentUser.avatar_path);
            img.alt = currentUser.display_name || currentUser.login_name || "Profile photo";
            avatarNode.appendChild(img);
            return;
        }
        avatarNode.textContent = initialsFor(currentUser.display_name || currentUser.login_name);
    }

    function resetFormState() {
        formError.textContent = "";
        avatarError.textContent = "";
        nameInput.value = currentUser.display_name || "";
        currentPasswordInput.value = "";
        newPasswordInput.value = "";
        confirmPasswordInput.value = "";
        examCountNode.textContent = statsLoaded ? examCountNode.textContent : "Loading activity...";
    }

    function showEditPanel() {
        editPanel.dataset.mode = "editing";
        editToggle.hidden = true;
        focusFieldForDesktop(nameInput);
    }

    function hideEditPanel() {
        editPanel.dataset.mode = "placeholder";
        editToggle.hidden = false;
        currentPasswordInput.value = "";
        newPasswordInput.value = "";
        confirmPasswordInput.value = "";
    }

    async function loadStats() {
        if (statsLoaded) {
            return;
        }
        examCountNode.textContent = "Loading activity...";
        try {
            const data = await request("/api/statistics/me");
            const total = Number(data.kpis?.exams_completed || 0);
            examCountNode.textContent = `${total} exam${total === 1 ? "" : "s"} completed`;
            statsLoaded = true;
        } catch (error) {
            examCountNode.textContent = "Activity unavailable";
        }
    }

    function syncShellUser() {
        currentUser.username = currentUser.display_name;
        if (currentUserData) {
            currentUserData.textContent = JSON.stringify(currentUser);
        }

        document.querySelectorAll("[data-open-profile-modal]").forEach((button) => {
            const nameNode = button.querySelector(".user-chip__name");
            const roleLabel = button.querySelector(".user-chip__role");
            if (nameNode) {
                nameNode.textContent = currentUser.display_name || currentUser.login_name;
            }
            if (roleLabel) {
                roleLabel.textContent = currentUser.role || "";
            }
            updateUserChipAvatar(button);
        });

        const signedInNode = document.querySelector(".header-meta .muted");
        if (signedInNode) {
            signedInNode.textContent = `Signed in as ${currentUser.display_name || currentUser.login_name}`;
        }
    }

    function updateUserChipAvatar(button) {
        const previousAvatar = button.querySelector(".user-chip__avatar");
        const nextAvatar = createChipAvatar();
        if (!previousAvatar) {
            button.prepend(nextAvatar);
            return;
        }
        previousAvatar.replaceWith(nextAvatar);
    }

    function createChipAvatar() {
        if (currentUser.avatar_path) {
            const img = document.createElement("img");
            img.className = "user-chip__avatar user-chip__avatar--image";
            img.src = assetPathToUrl(currentUser.avatar_path);
            img.alt = currentUser.display_name || currentUser.login_name || "Profile photo";
            return img;
        }
        const span = document.createElement("span");
        span.className = "user-chip__avatar";
        span.textContent = initialsFor(currentUser.display_name || currentUser.login_name);
        return span;
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

    openButtons.forEach((button) => {
        button.addEventListener("click", openModal);
    });

    closeButton.addEventListener("click", closeModal);
    backdrop.addEventListener("click", closeModal);
    editToggle.addEventListener("click", showEditPanel);
    cancelButton.addEventListener("click", hideEditPanel);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !modal.hidden) {
            closeModal();
        }
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        formError.textContent = "";

        const passwordFields = [
            currentPasswordInput.value.trim(),
            newPasswordInput.value.trim(),
            confirmPasswordInput.value.trim(),
        ];
        const filledPasswordFields = passwordFields.filter(Boolean).length;
        if (filledPasswordFields !== 0 && filledPasswordFields !== 3) {
            formError.textContent =
                "To change the password, complete current password, new password, and confirm new password, or leave all three blank.";
            return;
        }

        try {
            const payload = await request("/api/auth/profile", {
                method: "PUT",
                body: {
                    display_name: nameInput.value.trim(),
                    current_password: currentPasswordInput.value,
                    new_password: newPasswordInput.value,
                    confirm_password: confirmPasswordInput.value,
                },
            });
            currentUser = payload.user;
            renderUser();
            hideEditPanel();
        } catch (error) {
            formError.textContent = error.message;
        }
    });

    avatarInput.addEventListener("change", async () => {
        avatarError.textContent = "";
        const file = avatarInput.files?.[0];
        if (!file) {
            return;
        }
        const formData = new FormData();
        formData.append("avatar", file);

        try {
            const payload = await request("/api/auth/profile/avatar", {
                method: "POST",
                formData,
            });
            currentUser = payload.user;
            renderUser();
        } catch (error) {
            avatarError.textContent = error.message;
        } finally {
            avatarInput.value = "";
        }
    });
}
