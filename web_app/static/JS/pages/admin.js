import { request } from "../core/api.js";

export async function initAdminPage() {
    const list = document.getElementById("admin-users-list");
    const form = document.getElementById("admin-user-form");
    const errorNode = document.getElementById("admin-error");

    async function loadUsers() {
        const data = await request("/api/admin/users");
        list.innerHTML = data.users
            .map(
                (user) => `
            <div class="card" data-user-id="${user.id}">
                <div class="section-heading">
                    <div>
                        <h3>${user.username}</h3>
                        <p class="muted">${user.email || "No email"}</p>
                    </div>
                    <span class="badge">${user.role}</span>
                </div>
                <p class="muted">Status: ${user.status}</p>
                <div class="button-row">
                    <button class="button button--secondary button--small js-edit-user" type="button">Edit</button>
                    <button class="button button--secondary button--small js-delete-user" type="button">Delete</button>
                </div>
            </div>
        `
            )
            .join("");

        list.querySelectorAll(".js-edit-user").forEach((button) => {
            button.addEventListener("click", (event) => {
                const card = event.currentTarget.closest("[data-user-id]");
                const user = data.users.find((item) => String(item.id) === card.dataset.userId);
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
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorNode.textContent = "";
        const userId = document.getElementById("admin-user-id").value;
        const payload = {
            username: document.getElementById("admin-username").value.trim(),
            email: document.getElementById("admin-email").value.trim(),
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
    await loadUsers();
}

function fillUserForm(user) {
    document.getElementById("admin-user-id").value = user.id;
    document.getElementById("admin-username").value = user.username;
    document.getElementById("admin-email").value = user.email || "";
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
