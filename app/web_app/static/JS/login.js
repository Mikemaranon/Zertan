async function handleLoginSubmit(event) {
    event.preventDefault(); // Prevent default form submission

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const errorMessage = document.getElementById("error-message");

    try {
        const response = await login(username, password)

        const data = await response.json();
        console.log(data);

        if (response.ok && data.token) {
            store_token(data.token);
            console.log("token: ", data.token);
            loadPage("/");
        } else {
            errorMessage.textContent = data.error || "An error occurred.";
            errorMessage.style.display = "block";
        }
    } catch (error) {
        console.error("Error during login:", error);
        errorMessage.textContent = "Incorrect user, please try again.";
        errorMessage.style.display = "block";
    }
}

document.addEventListener("DOMContentLoaded", function () {
    const loginForm = document.getElementById("login-form");
    
    loginForm.addEventListener("submit", handleLoginSubmit);
});