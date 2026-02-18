/* ===== Hash Router ===== */
const ROUTES = {
  "/dashboard":    Dashboard,
  "/transactions": Transactions,
  "/import":       Import,
  "/stats":        Stats,
};

function navigate() {
  const hash = window.location.hash.replace("#", "");
  const route = hash && ROUTES[hash] ? hash : "/dashboard";
  const module = ROUTES[route];

  // Update active nav link
  document.querySelectorAll("#sidebar a").forEach(a => {
    a.classList.toggle("active", a.dataset.route === route);
  });

  const app = document.getElementById("app");
  app.innerHTML = "";
  try {
    module.render(app);
  } catch (err) {
    app.innerHTML = `<div class="loading" style="color:#ef4444">渲染错误: ${err.message}</div>`;
    console.error(err);
  }
}

window.addEventListener("hashchange", navigate);
window.addEventListener("load", () => {
  if (!window.location.hash) {
    window.location.hash = "#/dashboard";
  } else {
    navigate();
  }
});
