/* ===== Auth pages (Login / Register) ===== */
const AuthPage = {
  // Validation rules (keep in sync with backend)
  _rules: {
    username: {
      minLen: 2,
      maxLen: 32,
      pattern: /^[a-zA-Z0-9_\u4e00-\u9fff]+$/,
      patternMsg: "只能包含字母、数字、下划线或中文",
    },
    password: {
      minLen: 8,
      maxLen: 128,
      requireLetter: /[a-zA-Z]/,
      requireDigit: /\d/,
    },
  },

  render(container) {
    container.innerHTML = `
      <div class="auth-container">
        <div style="text-align:center;margin-bottom:32px">
          <div style="font-size:36px;margin-bottom:8px">💰</div>
          <h1 style="font-size:22px;font-weight:700">Autocoin</h1>
          <p style="color:var(--text-muted);font-size:14px;margin-top:4px">个人记账应用</p>
        </div>
        <div class="card" style="padding:28px">
          <div class="auth-tabs">
            <button class="auth-tab active" data-tab="login">登录</button>
            <button class="auth-tab" data-tab="register">注册</button>
          </div>

          <form id="login-form">
            <label class="form-field" style="margin-bottom:14px">
              <span class="form-label">用户名</span>
              <input type="text" id="login-username" required autocomplete="username" placeholder="请输入用户名">
            </label>
            <label class="form-field" style="margin-bottom:20px">
              <span class="form-label">密码</span>
              <input type="password" id="login-password" required autocomplete="current-password" placeholder="请输入密码">
            </label>
            <button type="submit" class="btn btn-primary" style="width:100%;padding:10px;font-size:15px;justify-content:center">登录</button>
          </form>

          <form id="register-form" style="display:none">
            <label class="form-field" style="margin-bottom:14px">
              <span class="form-label">用户名 <span style="font-weight:400;color:var(--neutral)">(2-32位，字母/数字/下划线/中文)</span></span>
              <input type="text" id="reg-username" required maxlength="32" autocomplete="username" placeholder="请输入用户名">
              <span class="field-hint" id="hint-username"></span>
            </label>
            <label class="form-field" style="margin-bottom:14px">
              <span class="form-label">密码 <span style="font-weight:400;color:var(--neutral)">(至少8位，需含字母和数字)</span></span>
              <input type="password" id="reg-password" required maxlength="128" autocomplete="new-password" placeholder="请输入密码">
              <span class="field-hint" id="hint-password"></span>
            </label>
            <label class="form-field" style="margin-bottom:20px">
              <span class="form-label">确认密码</span>
              <input type="password" id="reg-password2" required autocomplete="new-password" placeholder="再次输入密码">
              <span class="field-hint" id="hint-password2"></span>
            </label>
            <button type="submit" class="btn btn-primary" style="width:100%;padding:10px;font-size:15px;justify-content:center">注册</button>
          </form>

          <div id="auth-error" style="margin-top:14px;font-size:13px;color:var(--expense);text-align:center"></div>
        </div>
      </div>
    `;

    AuthPage._bindTabs(container);
    AuthPage._bindLogin(container);
    AuthPage._bindRegister(container);
    AuthPage._bindRealtimeValidation(container);
  },

  /** Validate username, return error message or "" */
  _checkUsername(val) {
    const r = AuthPage._rules.username;
    if (val.length < r.minLen) return `用户名至少${r.minLen}个字符`;
    if (val.length > r.maxLen) return `用户名最多${r.maxLen}个字符`;
    if (!r.pattern.test(val)) return r.patternMsg;
    return "";
  },

  /** Validate password, return error message or "" */
  _checkPassword(val) {
    const r = AuthPage._rules.password;
    if (val.length < r.minLen) return `密码至少${r.minLen}个字符`;
    if (!r.requireLetter.test(val)) return "密码需要包含至少一个字母";
    if (!r.requireDigit.test(val)) return "密码需要包含至少一个数字";
    return "";
  },

  /** Set hint text + color on a .field-hint element */
  _setHint(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.style.color = msg ? "var(--expense)" : "var(--income)";
  },

  _bindRealtimeValidation(container) {
    const usernameInput = container.querySelector("#reg-username");
    const pwInput = container.querySelector("#reg-password");
    const pw2Input = container.querySelector("#reg-password2");
    const hintU = container.querySelector("#hint-username");
    const hintP = container.querySelector("#hint-password");
    const hintP2 = container.querySelector("#hint-password2");

    usernameInput.addEventListener("input", () => {
      const v = usernameInput.value.trim();
      if (!v) { AuthPage._setHint(hintU, ""); return; }
      AuthPage._setHint(hintU, AuthPage._checkUsername(v));
    });

    pwInput.addEventListener("input", () => {
      const v = pwInput.value;
      if (!v) { AuthPage._setHint(hintP, ""); return; }
      AuthPage._setHint(hintP, AuthPage._checkPassword(v));
      // Also recheck confirm password
      if (pw2Input.value) {
        AuthPage._setHint(hintP2, pw2Input.value !== v ? "两次密码输入不一致" : "");
      }
    });

    pw2Input.addEventListener("input", () => {
      const v = pw2Input.value;
      if (!v) { AuthPage._setHint(hintP2, ""); return; }
      AuthPage._setHint(hintP2, v !== pwInput.value ? "两次密码输入不一致" : "");
    });
  },

  _bindTabs(container) {
    container.querySelectorAll(".auth-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        const isLogin = tab.dataset.tab === "login";
        container.querySelector("#login-form").style.display = isLogin ? "" : "none";
        container.querySelector("#register-form").style.display = isLogin ? "none" : "";
        container.querySelector("#auth-error").textContent = "";
        container.querySelectorAll(".auth-tab").forEach(t => {
          t.classList.toggle("active", t.dataset.tab === tab.dataset.tab);
        });
      });
    });
  },

  _bindLogin(container) {
    container.querySelector("#login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = container.querySelector("#auth-error");
      errEl.textContent = "";
      try {
        const data = await API.auth.login({
          username: container.querySelector("#login-username").value.trim(),
          password: container.querySelector("#login-password").value,
        });
        Auth.setToken(data.access_token);
        Auth.setUsername(data.username);
        window.location.hash = "#/dashboard";
      } catch (err) {
        errEl.textContent = err.message;
      }
    });
  },

  _bindRegister(container) {
    container.querySelector("#register-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = container.querySelector("#auth-error");
      errEl.textContent = "";

      const username = container.querySelector("#reg-username").value.trim();
      const pw1 = container.querySelector("#reg-password").value;
      const pw2 = container.querySelector("#reg-password2").value;

      // Client-side validation
      const uErr = AuthPage._checkUsername(username);
      if (uErr) { errEl.textContent = uErr; return; }
      const pErr = AuthPage._checkPassword(pw1);
      if (pErr) { errEl.textContent = pErr; return; }
      if (pw1 !== pw2) { errEl.textContent = "两次密码输入不一致"; return; }

      try {
        const data = await API.auth.register({ username, password: pw1 });
        Auth.setToken(data.access_token);
        Auth.setUsername(data.username);
        window.location.hash = "#/dashboard";
      } catch (err) {
        errEl.textContent = err.message;
      }
    });
  },
};
