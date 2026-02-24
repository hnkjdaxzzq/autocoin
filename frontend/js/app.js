/* ===== Hash Router ===== */
const ROUTES = {
  "/login":        AuthPage,
  "/dashboard":    Dashboard,
  "/transactions": Transactions,
  "/import":       Import,
  "/stats":        Stats,
};

const PUBLIC_ROUTES = ["/login"];

function navigate() {
  const hash = window.location.hash.replace("#", "") || "/dashboard";
  const route = ROUTES[hash] ? hash : "/dashboard";

  // Auth guard
  if (!PUBLIC_ROUTES.includes(route) && !Auth.isLoggedIn()) {
    window.location.hash = "#/login";
    return;
  }
  if (route === "/login" && Auth.isLoggedIn()) {
    window.location.hash = "#/dashboard";
    return;
  }

  const loggedIn = Auth.isLoggedIn();
  const sidebar = document.getElementById("sidebar");
  const bottomBar = document.getElementById("bottom-bar");

  // Show/hide navigation
  sidebar.style.display = loggedIn ? "" : "none";
  if (bottomBar) bottomBar.style.display = loggedIn ? "" : "none";

  // Update active nav links (sidebar + bottom bar)
  document.querySelectorAll("[data-route]").forEach(a => {
    a.classList.toggle("active", a.dataset.route === route);
  });

  // Update username display
  const userEl = document.getElementById("user-display");
  if (userEl && loggedIn) {
    userEl.textContent = Auth.getUsername() || "";
  }

  const app = document.getElementById("app");
  app.style.marginLeft = loggedIn ? "" : "0";
  app.innerHTML = "";

  try {
    ROUTES[route].render(app);
  } catch (err) {
    app.innerHTML = `<div class="loading" style="color:#ef4444">渲染错误: ${err.message}</div>`;
    console.error(err);
  }
}

function logout() {
  Auth.clear();
  window.location.hash = "#/login";
}

/* ===== Mobile "我的" popup ===== */
function initMePopup() {
  const btn = document.getElementById("bottom-bar-me");
  if (!btn) return;

  // Create popup element once
  let popup = document.getElementById("me-popup");
  if (!popup) {
    popup = document.createElement("div");
    popup.id = "me-popup";
    popup.className = "me-popup";
    popup.innerHTML = `
      <div class="me-popup-user" id="me-popup-username"></div>
      <button class="me-popup-logout" onclick="logout()">退出登录</button>
    `;
    document.body.appendChild(popup);
  }

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const username = Auth.getUsername() || "";
    document.getElementById("me-popup-username").textContent = username;
    popup.classList.toggle("show");
  });

  // Close on outside click
  document.addEventListener("click", (e) => {
    if (popup.classList.contains("show") && !popup.contains(e.target) && e.target !== btn) {
      popup.classList.remove("show");
    }
  });
}

window.addEventListener("hashchange", navigate);
window.addEventListener("load", async () => {
  initMePopup();
  // Validate stored token on app start
  if (Auth.isLoggedIn()) {
    try {
      const user = await API.auth.me();
      Auth.setUsername(user.username);
    } catch (e) {
      Auth.clear();
    }
  }

  if (!window.location.hash || window.location.hash === "#") {
    window.location.hash = Auth.isLoggedIn() ? "#/dashboard" : "#/login";
  } else {
    navigate();
  }
});
