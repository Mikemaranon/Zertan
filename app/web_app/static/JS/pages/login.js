import { request, storeToken } from "../core/api.js";

export async function initLoginPage() {
    const form = document.getElementById("login-form");
    const errorMessage = document.getElementById("error-message");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        errorMessage.textContent = "";

        try {
            const payload = await request("/api/auth/login", {
                method: "POST",
                body: {
                    login_name: document.getElementById("login-name").value,
                    password: document.getElementById("password").value,
                },
            });
            storeToken(payload.token);
            window.location.href = "/dashboard";
        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
}
