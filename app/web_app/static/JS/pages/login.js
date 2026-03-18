import { request } from "../core/api.js";

export async function initLoginPage() {
    const form = document.getElementById("login-form");
    const errorMessage = document.getElementById("error-message");
    const seededAccountsToggle = document.getElementById("seeded-accounts-toggle");
    const seededAccountsList = document.getElementById("seeded-accounts-list");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorMessage.textContent = "";
        errorMessage.hidden = true;

        try {
            await request("/api/auth/login", {
                method: "POST",
                body: {
                    login_name: document.getElementById("login-name").value,
                    password: document.getElementById("password").value,
                },
            });
            window.location.href = "/dashboard";
        } catch (error) {
            errorMessage.textContent = error.message;
            errorMessage.hidden = false;
        }
    });

    if (seededAccountsToggle && seededAccountsList) {
        seededAccountsToggle.addEventListener("click", () => {
            const nextHidden = !seededAccountsList.hidden;
            seededAccountsList.hidden = nextHidden;
            seededAccountsToggle.setAttribute("aria-expanded", String(!nextHidden));
            seededAccountsToggle.setAttribute(
                "aria-label",
                nextHidden ? "Show seeded accounts" : "Hide seeded accounts",
            );
        });
    }
}
