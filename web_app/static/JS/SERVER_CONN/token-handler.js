const TOKEN_KEY = "auth_token";

function store_token(token) {
    try {
        delete_token(); // Clear any existing token
    } catch (error) {
        console.error("Error deleting existing token:", error);
    }
    localStorage.setItem(TOKEN_KEY, token);
    console.log("Token stored:", token);
}

function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

function delete_token() {
    localStorage.removeItem(TOKEN_KEY);
}

async function login(username, password) {
    const endpoint = "/login";
    if (!username || !password) {
        throw new Error("Username and password are required.");
    }

    const options = {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ username, password })
    };

    console.log("loging... :", endpoint, options);

    try {
        const response = await fetch(endpoint, options);

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }
        return response;
    } catch (error) {
        console.error("Error in API request:", error);
        throw error;
    }
}

async function send_API_request(method, endpoint, body = null) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
        throw new Error("No authentication token found.");
    }

    const options = {
        method: method.toUpperCase(),
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token
        }
    };
    
    if (body && method.toUpperCase() !== "GET") {
        options.body = JSON.stringify(body);
    }

    console.log("Fetching:", endpoint, options);

    try {
        const response = await fetch(endpoint, options);

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }
        return response;
    } catch (error) {
        console.error("Error in API request:", error);
        throw error;
    }
}

async function loadPage(url) {
    const token = getToken();
    try {
        const response = await send_API_request("GET", url);
        window.location.href = response.url
    } catch (error) {
        console.error("Error loading page:", error);
        // window.location.href = "/login";
    }
}