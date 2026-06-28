/* ===== Hash Router ===== */
const ROUTES = {
  "/login":        AuthPage,
  "/dashboard":    Dashboard,
  "/transactions": Transactions,
  "/broker-income-analysis": BrokerIncomeAnalysis,
  "/import":       Import,
  "/rules":        RulesPage,
  "/stats":        Stats,
  "/data-management": DataManagement,
  "/ai-analysis": AiClassification,
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

/* ===== Sidebar User Hover Menu ===== */
function initSidebarUserMenu() {
  const info = document.getElementById("sidebar-user-info");
  const menu = document.getElementById("sidebar-user-menu");
  if (!info || !menu) return;

  let hideTimer = null;

  function showMenu() {
    clearTimeout(hideTimer);
    menu.classList.add("show");
  }

  function hideMenu() {
    hideTimer = setTimeout(() => {
      menu.classList.remove("show");
    }, 200);
  }

  info.addEventListener("mouseenter", showMenu);
  menu.addEventListener("mouseenter", showMenu);
  info.addEventListener("mouseleave", hideMenu);
  menu.addEventListener("mouseleave", hideMenu);

  // Close on click outside
  document.addEventListener("click", (e) => {
    if (menu.classList.contains("show") && !info.contains(e.target) && !menu.contains(e.target)) {
      menu.classList.remove("show");
    }
  });
}

/* ===== Change Password Modal ===== */
function showChangePasswordModal() {
  // Close any open hover menu
  const menu = document.getElementById("sidebar-user-menu");
  if (menu) menu.classList.remove("show");

  // Create overlay
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.id = "change-password-overlay";

  overlay.innerHTML = `
    <div class="modal-dialog modal-dialog-sm">
      <div class="modal-title">修改密码</div>
      <div class="modal-body">
        <div class="form-field" style="margin-bottom:12px">
          <label class="form-label">原密码</label>
          <input type="password" id="cp-old-password" placeholder="请输入原密码">
        </div>
        <div class="form-field" style="margin-bottom:12px">
          <label class="form-label">新密码</label>
          <input type="password" id="cp-new-password" placeholder="请输入新密码（至少8位，含字母和数字）">
        </div>
        <div class="form-field" style="margin-bottom:0">
          <label class="form-label">确认新密码</label>
          <input type="password" id="cp-confirm-password" placeholder="请再次输入新密码">
        </div>
        <div id="cp-error" class="field-hint" style="color:var(--expense);margin-top:8px"></div>
      </div>
      <div class="modal-buttons">
        <button class="btn btn-ghost" onclick="closeChangePasswordModal()">取消</button>
        <button class="btn btn-primary" onclick="submitChangePassword()">确认</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // Focus first input
  setTimeout(() => {
    const firstInput = document.getElementById("cp-old-password");
    if (firstInput) firstInput.focus();
  }, 100);

  // Close on overlay click
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) closeChangePasswordModal();
  });

  // Enter/Escape key support
  overlay.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) submitChangePassword();
    if (e.key === "Escape") closeChangePasswordModal();
  });
}

function closeChangePasswordModal() {
  const overlay = document.getElementById("change-password-overlay");
  if (overlay) overlay.remove();
}

async function submitChangePassword() {
  const errorEl = document.getElementById("cp-error");
  const oldPw = document.getElementById("cp-old-password").value;
  const newPw = document.getElementById("cp-new-password").value;
  const confirmPw = document.getElementById("cp-confirm-password").value;

  // Clear previous error
  errorEl.textContent = "";

  // Client-side validation
  if (!oldPw) {
    errorEl.textContent = "请输入原密码";
    return;
  }
  if (!newPw) {
    errorEl.textContent = "请输入新密码";
    return;
  }
  if (newPw.length < 8) {
    errorEl.textContent = "新密码至少8个字符";
    return;
  }
  if (!/[a-zA-Z]/.test(newPw)) {
    errorEl.textContent = "新密码需要包含至少一个字母";
    return;
  }
  if (!/\d/.test(newPw)) {
    errorEl.textContent = "新密码需要包含至少一个数字";
    return;
  }
  if (newPw !== confirmPw) {
    errorEl.textContent = "两次输入的新密码不一致";
    return;
  }

  try {
    await API.auth.changePassword({ old_password: oldPw, new_password: newPw });
    closeChangePasswordModal();
    showToast("密码修改成功");
  } catch (err) {
    errorEl.textContent = err.message;
  }
}

/* ===== Toast notification ===== */
let toastTimer = null;

function showToast(message) {
  let toast = document.getElementById("toast-message");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast-message";
    toast.className = "toast-message";
    document.body.appendChild(toast);
  }
  clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("show");
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 2500);
}

/* ===== Dark mode ===== */
function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute("data-theme") === "dark";
  const next = isDark ? "light" : "dark";
  html.setAttribute("data-theme", next);
  localStorage.setItem("autocoin_theme", next);
  if (typeof Charts !== "undefined" && Charts.refreshAll) {
    requestAnimationFrame(() => Charts.refreshAll());
  }
}

function initTheme() {
  const saved = localStorage.getItem("autocoin_theme");
  if (saved === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else if (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    document.documentElement.setAttribute("data-theme", "dark");
  }
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
      <button class="me-popup-action" onclick="window.location.hash='#/rules'">分类规则</button>
      <button class="me-popup-action" onclick="toggleTheme()">🌓 切换主题</button>
      <button class="me-popup-action" onclick="showChangePasswordModal()">🔑 修改密码</button>
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
  initTheme();
  initMePopup();
  initSidebarUserMenu();
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
