// Auth logic for the frontend

// Get token from local storage
function getToken() {
    return localStorage.getItem("finance_token");
}

// Redirect to login if not authenticated
function requireAuth() {
    const token = getToken();
    const isAuthPage = window.location.pathname === "/login" || window.location.pathname === "/register";
    
    if (!token && !isAuthPage) {
        window.location.href = "/login";
        return;
    }

    if (token && isAuthPage) {
        window.location.href = "/";
        return;
    }

    // Verify token validity if on a protected page
    if (token && !isAuthPage) {
        fetch("/me", {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        }).then(res => {
            if (!res.ok) {
                // Token invalid or expired
                logout();
            } else {
                res.json().then(user => {
                    updateSidebar(user);
                });
            }
        }).catch(err => {
            console.error("Auth check failed", err);
        });
    }
}

// Custom fetch wrapper that automatically adds the Authorization header
async function apiFetch(url, options = {}) {
    const token = getToken();
    const headers = {
        ...options.headers,
    };
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }
    
    const res = await fetch(url, { ...options, headers });
    
    if (res.status === 401) {
        // Unauthorized, token might be expired
        logout();
    }
    
    return res;
}

function logout() {
    localStorage.removeItem("finance_token");
    window.location.href = "/login";
}

// Update sidebar with user info
function updateSidebar(user) {
    const sidebar = document.getElementById("sidebar");
    if (!sidebar) return;

    let profileSection = document.getElementById("user-profile");
    if (!profileSection) {
        profileSection = document.createElement("div");
        profileSection.id = "user-profile";
        profileSection.style.padding = "20px";
        profileSection.style.marginTop = "auto";
        profileSection.style.borderTop = "1px solid var(--glass-border)";
        profileSection.style.display = "flex";
        profileSection.style.flexDirection = "column";
        profileSection.style.gap = "10px";
        
        sidebar.appendChild(profileSection);
    }

    profileSection.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--primary-color); color: white; display: flex; align-items: center; justify-content: center; font-weight: bold;">
                ${user.username.charAt(0).toUpperCase()}
            </div>
            <div style="overflow: hidden;">
                <div style="font-weight: 500; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">${user.username}</div>
                <div style="font-size: 0.8rem; color: var(--text-secondary); text-overflow: ellipsis; white-space: nowrap; overflow: hidden;">${user.email}</div>
            </div>
        </div>
        <button onclick="logout()" class="btn btn-secondary" style="width: 100%; padding: 0.5rem; font-size: 0.9rem;">Log Out</button>
    `;
}

// Run auth check on load
document.addEventListener("DOMContentLoaded", () => {
    requireAuth();
});
