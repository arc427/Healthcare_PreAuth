const TOKEN_KEY = "preauthToken";
const ROLE_KEY = "preauthRole";
const USER_KEY = "preauthUsername";

const statusStyles = {
  Pending: "bg-amber-100 text-amber-800",
  Approved: "bg-emerald-100 text-emerald-800",
  Rejected: "bg-rose-100 text-rose-800",
};

const loginView = document.getElementById("login-view");
const hospitalView = document.getElementById("hospital-view");
const insurerView = document.getElementById("insurer-view");
const sessionBar = document.getElementById("session-bar");
const sessionLabel = document.getElementById("session-label");
const loginForm = document.getElementById("login-form");
const loginMessage = document.getElementById("login-message");
const form = document.getElementById("submit-form");
const submitMessage = document.getElementById("submit-message");
const insurerMessage = document.getElementById("insurer-message");
const requestsBody = document.getElementById("requests-body");
const networkStatus = document.getElementById("network-status");
const refreshBtn = document.getElementById("refresh-btn");
const logoutBtn = document.getElementById("logout-btn");

let contractConfig = null;
let chainContract = null;
let pollTimer = null;

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

function getRole() {
  return localStorage.getItem(ROLE_KEY) || "";
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function errorDetail(payload, fallback) {
  if (!payload) return fallback;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail) && payload.detail[0]?.msg) return payload.detail[0].msg;
  return fallback;
}

function setBanner(el, text, ok) {
  el.textContent = text;
  el.className = `mt-4 rounded-lg px-3 py-2 text-sm ${
    ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"
  }`;
}

function showMessage(text, ok) {
  setBanner(submitMessage, text, ok);
}

function showInsurerMessage(text, ok) {
  setBanner(insurerMessage, text, ok);
}

function statusBadge(status) {
  const cls = statusStyles[status] || "bg-slate-100 text-slate-700";
  return `<span class="inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${cls}">${status}</span>`;
}

function applyRoleView(role) {
  const loggedIn = Boolean(role && getToken());
  loginView.classList.toggle("hidden", loggedIn);
  hospitalView.classList.toggle("hidden", role !== "hospital");
  insurerView.classList.toggle("hidden", role !== "insurer");
  sessionBar.classList.toggle("hidden", !loggedIn);
  sessionBar.classList.toggle("flex", loggedIn);
  if (loggedIn) {
    sessionLabel.textContent = `Signed in as ${localStorage.getItem(USER_KEY) || role}`;
  }
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  if (role === "insurer") {
    loadRequests();
    pollTimer = setInterval(() => {
      loadRequests().catch(() => {});
    }, 8000);
  }
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_KEY);
  applyRoleView("");
}

async function loadConfig() {
  const health = await fetch("/api/health").then((res) => res.json());
  if (!health.hardhatConnected) {
    networkStatus.textContent = "Hardhat node is offline (http://127.0.0.1:8545)";
    return;
  }
  if (!health.contractDeployed) {
    networkStatus.textContent = "Hardhat is up. Deploy the contract to continue.";
    return;
  }

  contractConfig = await fetch("/api/config").then((res) => res.json());
  networkStatus.textContent = "Network connected";

  if (window.ethers) {
    const provider = new ethers.JsonRpcProvider(contractConfig.rpcUrl);
    chainContract = new ethers.Contract(contractConfig.address, contractConfig.abi, provider);
  }
}

async function readOnChainStatus(requestId) {
  if (!chainContract) return null;
  try {
    const result = await chainContract.getRequest(requestId);
    const code = Number(result.status ?? result[3]);
    return ["Pending", "Approved", "Rejected"][code] || "Unknown";
  } catch (error) {
    console.warn("Client-side chain read failed", error);
    return null;
  }
}

function renderRows(rows) {
  if (!rows.length) {
    requestsBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-slate-400">No requests yet.</td></tr>`;
    return;
  }

  requestsBody.innerHTML = rows
    .map((row) => {
      const pending = row.status === "Pending";
      const details = `${row.patientId} · ${row.diagnosis} · ${row.procedureCode}`;
      const timeStr = row.timestamp ? new Date(row.timestamp * 1000).toLocaleString() : "Just now";
      return `
        <tr class="border-b border-slate-100 align-top">
          <td class="py-3 pr-3 font-mono font-semibold">#${row.requestId}</td>
          <td class="py-3 pr-3 text-slate-700">${details}</td>
          <td class="py-3 pr-3 text-xs text-slate-500">${timeStr}</td>
          <td class="py-3 pr-3">${statusBadge(row.status)}</td>
          <td class="py-3">
            <button
              data-id="${row.requestId}"
              class="evaluate-btn rounded-md border px-2.5 py-1 text-xs font-medium ${
                pending
                  ? "border-clinic-700 text-clinic-700 hover:bg-clinic-50"
                  : "cursor-not-allowed border-slate-200 text-slate-400"
              }"
              ${pending ? "" : "disabled"}
            >
              Auto-Evaluate via Smart Contract
            </button>
          </td>
        </tr>
      `;
    })
    .join("");

  document.querySelectorAll(".evaluate-btn").forEach((button) => {
    button.addEventListener("click", () => evaluateRequest(Number(button.dataset.id)));
  });
}

async function loadRequests() {
  const response = await fetch("/api/requests", { headers: authHeaders() });
  if (response.status === 401) {
    logout();
    return;
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unable to load requests." }));
    requestsBody.innerHTML = `<tr><td colspan="5" class="py-8 text-center text-rose-500">${errorDetail(error, "Unable to load requests.")}</td></tr>`;
    return;
  }
  const rows = await response.json();
  await Promise.all(
    rows.map(async (row) => {
      const live = await readOnChainStatus(row.requestId);
      if (live) row.status = live;
    })
  );
  renderRows(rows);
}

async function evaluateRequest(requestId) {
  const response = await fetch("/api/evaluate", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ requestId }),
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    logout();
    return;
  }
  if (!response.ok) {
    showInsurerMessage(errorDetail(payload, "Evaluation failed."), false);
    return;
  }
  const txInfo = payload.txHash ? ` (Tx: ${payload.txHash.slice(0, 10)}…)` : "";
  showInsurerMessage(`Request #${requestId} evaluated to ${payload.status}${txInfo}.`, true);
  await loadRequests();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const response = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: document.getElementById("username").value.trim(),
      password: document.getElementById("password").value,
    }),
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 404) {
    setBanner(loginMessage, "Login API is not loaded. Restart the FastAPI server and refresh.", false);
    return;
  }
  if (!response.ok) {
    setBanner(loginMessage, errorDetail(payload, "Login failed."), false);
    return;
  }
  localStorage.setItem(TOKEN_KEY, payload.token);
  localStorage.setItem(ROLE_KEY, payload.role);
  localStorage.setItem(USER_KEY, payload.username);
  loginForm.reset();
  loginMessage.className = "mt-4 hidden";
  applyRoleView(payload.role);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = {
    patientId: document.getElementById("patientId").value.trim(),
    diagnosis: document.getElementById("diagnosis").value.trim(),
    procedureCode: document.getElementById("procedureCode").value.trim(),
  };
  const response = await fetch("/api/request", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401) {
    logout();
    return;
  }
  if (!response.ok) {
    showMessage(errorDetail(payload, "Submission failed."), false);
    return;
  }
  form.reset();
  const txInfo = payload.txHash ? ` (Tx: ${payload.txHash.slice(0, 10)}…)` : "";
  showMessage(`Submitted request #${payload.requestId}${txInfo}.`, true);
});

refreshBtn.addEventListener("click", loadRequests);
logoutBtn.addEventListener("click", logout);

loadConfig().catch((error) => {
  networkStatus.textContent = "Unable to reach the API.";
  console.error(error);
});

applyRoleView(getRole());
