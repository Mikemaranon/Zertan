import { escapeHtml, request } from "../core/api.js";

export async function initAdminPage() {
    const list = document.getElementById("admin-users-list");
    const scrollContainer = document.getElementById("admin-users-scroll");
    const searchInput = document.getElementById("admin-user-search");
    const form = document.getElementById("admin-user-form");
    const errorNode = document.getElementById("admin-error");
    let users = [];

    function renderUsers() {
        const query = searchInput.value.trim().toLowerCase();
        const filteredUsers = users.filter((user) => {
            if (!query) {
                return true;
            }
            return [user.display_name, user.login_name, user.role, user.status].some((value) =>
                String(value).toLowerCase().includes(query)
            );
        });

        list.innerHTML = filteredUsers.length
            ? filteredUsers
            .map(
                (user) => `
            <div class="card" data-user-id="${user.id}">
                <div class="section-heading">
                    <div>
                        <h3>${escapeHtml(user.display_name)}</h3>
                        <p class="muted">${escapeHtml(user.login_name)}</p>
                    </div>
                    <span class="badge">${escapeHtml(user.role)}</span>
                </div>
                <p class="muted">Status: ${escapeHtml(user.status)}</p>
                <div class="button-row">
                    <button class="button button--secondary button--small js-edit-user" type="button">Edit</button>
                    <button class="button button--secondary button--small js-delete-user" type="button">Delete</button>
                </div>
            </div>
        `
            )
            .join("")
            : `<div class="empty-state">No users match the current search.</div>`;

        list.querySelectorAll(".js-edit-user").forEach((button) => {
            button.addEventListener("click", (event) => {
                const card = event.currentTarget.closest("[data-user-id]");
                const user = users.find((item) => String(item.id) === card.dataset.userId);
                fillUserForm(user);
            });
        });

        list.querySelectorAll(".js-delete-user").forEach((button) => {
            button.addEventListener("click", async (event) => {
                const card = event.currentTarget.closest("[data-user-id]");
                await request(`/api/admin/users/${card.dataset.userId}`, { method: "DELETE" });
                await loadUsers();
            });
        });

        updateDirectoryHeight();
    }

    function updateDirectoryHeight() {
        const cards = [...list.querySelectorAll(".card")];
        if (!cards.length) {
            scrollContainer.style.maxHeight = "";
            return;
        }
        const styles = window.getComputedStyle(list);
        const gap = Number.parseFloat(styles.rowGap || styles.gap || "0") || 0;
        const panel = scrollContainer.closest(".panel");
        const panelStyles = panel ? window.getComputedStyle(panel) : null;
        const panelBottomPadding = Number.parseFloat(panelStyles?.paddingBottom || "0") || 0;
        const totalHeight =
            cards.reduce((total, card) => total + card.offsetHeight, 0) + gap * Math.max(cards.length - 1, 0);
        const fourCardHeight =
            cards.slice(0, 4).reduce((total, card) => total + card.offsetHeight, 0) + gap * Math.max(Math.min(cards.length, 4) - 1, 0);
        const viewportSafetyOffset = 12;
        const availableViewportHeight = Math.max(
            220,
            window.innerHeight - scrollContainer.getBoundingClientRect().top - panelBottomPadding - viewportSafetyOffset
        );
        const desiredHeight = cards.length > 4 ? Math.min(fourCardHeight, availableViewportHeight) : Math.min(totalHeight, availableViewportHeight);
        const constrainedHeight = totalHeight > desiredHeight ? Math.ceil(desiredHeight) : null;
        scrollContainer.style.maxHeight = constrainedHeight ? `${constrainedHeight}px` : "";

        if (!constrainedHeight) {
            return;
        }

        window.requestAnimationFrame(() => {
            const pageOverflow = document.documentElement.scrollHeight - window.innerHeight;
            if (pageOverflow <= 0) {
                return;
            }
            const correctedHeight = Math.max(220, constrainedHeight - pageOverflow - 4);
            scrollContainer.style.maxHeight = `${correctedHeight}px`;
        });
    }

    async function loadUsers() {
        const data = await request("/api/admin/users");
        users = data.users;
        renderUsers();
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorNode.textContent = "";
        const userId = document.getElementById("admin-user-id").value;
        const payload = {
            display_name: document.getElementById("admin-display-name").value.trim(),
            login_name: document.getElementById("admin-login-name").value.trim(),
            password: document.getElementById("admin-password").value,
            role: document.getElementById("admin-role").value,
            status: document.getElementById("admin-status").value,
        };
        try {
            await request(userId ? `/api/admin/users/${userId}` : "/api/admin/users", {
                method: userId ? "PUT" : "POST",
                body: payload,
            });
            resetForm();
            await loadUsers();
        } catch (error) {
            errorNode.textContent = error.message;
        }
    });

    document.getElementById("admin-form-reset").addEventListener("click", resetForm);
    searchInput.addEventListener("input", renderUsers);
    window.addEventListener("resize", updateDirectoryHeight);
    await loadUsers();
}

function fillUserForm(user) {
    document.getElementById("admin-user-id").value = user.id;
    document.getElementById("admin-display-name").value = user.display_name;
    document.getElementById("admin-login-name").value = user.login_name;
    document.getElementById("admin-password").value = "";
    document.getElementById("admin-role").value = user.role;
    document.getElementById("admin-status").value = user.status;
}

function resetForm() {
    document.getElementById("admin-user-id").value = "";
    document.getElementById("admin-user-form").reset();
    document.getElementById("admin-role").value = "user";
    document.getElementById("admin-status").value = "active";
}
