const $ = id => document.getElementById(id);
let registering = false;
let currentPage = 1;
let totalPages = 1;
let selectedReceipt = null;
let user = null;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  })[char]);
}
async function api(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const response = await fetch(url, { credentials:"same-origin", ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Request failed.");
  return data;
}
function showWorkspace() {
  $("authView").classList.add("hidden");
  $("workspace").classList.remove("hidden");
  $("logoutBtn").classList.remove("hidden");
  $("userLabel").textContent = user?.name || "";
}
function showAuth() {
  $("authView").classList.remove("hidden");
  $("workspace").classList.add("hidden");
  $("logoutBtn").classList.add("hidden");
}
function renderHistory(data) {
  totalPages = Math.max(1, data.pages || 1);
  $("count").textContent = data.total + " saved";
  $("pageLabel").textContent = "Page " + data.page + " of " + totalPages;
  $("prevPage").disabled = currentPage <= 1;
  $("nextPage").disabled = currentPage >= totalPages;
  $("historyList").innerHTML = data.items.length ? data.items.map(item => {
    const merchant = item.receipt?.merchant || item.receipt?.vendor || "Untitled receipt";
    const total = item.receipt?.total ?? "Total not detected";
    return '<button type="button" class="receipt-row ' + (selectedReceipt === item.receipt_id ? "active" : "") +
      '" data-open="' + esc(item.receipt_id) + '"><span><strong>' + esc(merchant) +
      '</strong><small>' + esc(item.created_at.slice(0,10)) + ' · ' + esc(total) +
      '</small></span><span class="status ' + esc(item.status) + '">' + esc(item.status.replace("_"," ")) + '</span></button>';
  }).join("") : '<p class="muted">No receipts yet. Upload your first receipt to get started.</p>';
}
async function loadHistory() {
  const q = $("query").value.trim();
  const data = await api("/receipts?page=" + currentPage + "&page_size=15&q=" + encodeURIComponent(q));
  renderHistory(data);
}
async function openReceipt(id) {
  selectedReceipt = id;
  const item = await api("/receipts/" + encodeURIComponent(id));
  $("emptyDetail").classList.add("hidden");
  $("receiptDetail").classList.remove("hidden");
  const values = item.receipt || {};
  const editable = ["merchant","date","subtotal","tax","total","currency","payment_method"];
  const labels = {merchant:"Merchant",date:"Receipt date",subtotal:"Subtotal",tax:"Tax",total:"Total",currency:"Currency",payment_method:"Payment method"};
  $("receiptDetail").innerHTML = '<div class="section-head"><div><p class="eyebrow">RECEIPT REVIEW</p><h2>' +
    esc(values.merchant || "Receipt details") + '</h2></div><span class="status ' + esc(item.status) + '">' +
    esc(item.status.replace("_"," ")) + '</span></div>' +
    '<img class="receipt-image" src="/receipts/' + encodeURIComponent(id) + '/image?kind=original" alt="Original uploaded receipt">' +
    '<div class="validation"><strong>OCR confidence:</strong> ' + esc(item.ocr?.average_confidence ?? "Not available") +
    ' · <strong>Financial validation:</strong> ' + esc(item.validation?.overall_status ?? "Not available") + '</div>' +
    '<form id="reviewForm"><div class="fields">' + editable.map(key =>
      '<label>' + labels[key] + '<input name="' + key + '" maxlength="200" value="' + esc(values[key] ?? "") + '"></label>'
    ).join("") + '</div><div class="review-actions">' +
    '<button class="primary" name="decision" value="approved">Approve corrected receipt</button>' +
    '<button class="reject" name="decision" value="rejected">Reject receipt</button>' +
    '<button class="quiet" id="deleteReceipt" type="button">Delete</button></div></form>' +
    '<h3>Raw OCR evidence</h3><pre class="raw">' + esc(item.ocr_text) + '</pre>';
  $("reviewForm").onsubmit = async event => {
    event.preventDefault();
    const status = event.submitter?.value;
    if (!["approved","rejected"].includes(status)) return;
    const form = new FormData(event.currentTarget);
    const fields = Object.fromEntries(editable.map(key => [key, form.get(key)]));
    try {
      await api("/receipts/" + encodeURIComponent(id) + "/review", {
        method:"PATCH", body:JSON.stringify({status,fields})
      });
      await loadHistory();
      await openReceipt(id);
    } catch (error) { alert(error.message); }
  };
  $("deleteReceipt").onclick = async () => {
    if (!confirm("Permanently delete this receipt and its stored images?")) return;
    try {
      await api("/receipts/" + encodeURIComponent(id), {method:"DELETE"});
      selectedReceipt = null;
      $("receiptDetail").classList.add("hidden");
      $("emptyDetail").classList.remove("hidden");
      await loadHistory();
    } catch (error) { alert(error.message); }
  };
  await loadHistory();
}
$("authToggle").onclick = () => {
  registering = !registering;
  $("authTitle").textContent = registering ? "Create your account" : "Welcome back";
  $("authSubmit").textContent = registering ? "Create account" : "Sign in";
  $("nameWrap").classList.toggle("hidden", !registering);
  $("password").autocomplete = registering ? "new-password" : "current-password";
  $("authToggle").textContent = registering ? "Already have an account? Sign in" : "Create an account";
  $("authError").textContent = "";
};
$("authForm").onsubmit = async event => {
  event.preventDefault();
  $("authError").textContent = "";
  const payload = {email:$("email").value,password:$("password").value};
  if (registering) payload.name = $("name").value;
  try {
    const result = await api(registering ? "/auth/register" : "/auth/login", {
      method:"POST", body:JSON.stringify(payload)
    });
    user = result.user;
    showWorkspace();
    currentPage = 1;
    await loadHistory();
  } catch (error) { $("authError").textContent = error.message; }
};
$("logoutBtn").onclick = async () => {
  try { await api("/auth/logout", {method:"POST"}); } catch {}
  user = null;
  selectedReceipt = null;
  showAuth();
};
$("uploadForm").onsubmit = async event => {
  event.preventDefault();
  const file = $("receiptFile").files[0];
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) { $("uploadMessage").textContent = "File exceeds 10 MB."; return; }
  const form = new FormData();
  form.append("file", file);
  $("uploadBtn").disabled = true;
  $("uploadMessage").textContent = "Processing image and extracting receipt fields…";
  try {
    const result = await api("/upload-receipt", {method:"POST",body:form});
    $("uploadMessage").textContent = "Receipt processed. Status: " + result.status.replace("_"," ");
    currentPage = 1;
    await loadHistory();
    await openReceipt(result.receipt_id);
    $("uploadForm").reset();
    $("fileLabel").textContent = "Choose receipt image";
  } catch (error) { $("uploadMessage").textContent = error.message; }
  finally { $("uploadBtn").disabled = false; }
};
$("receiptFile").onchange = () => {
  $("fileLabel").textContent = $("receiptFile").files[0]?.name || "Choose receipt image";
};
$("searchForm").onsubmit = async event => {
  event.preventDefault();
  currentPage = 1;
  await loadHistory();
};
$("prevPage").onclick = async () => { if (currentPage > 1) { currentPage--; await loadHistory(); } };
$("nextPage").onclick = async () => { if (currentPage < totalPages) { currentPage++; await loadHistory(); } };
$("historyList").onclick = async event => {
  const button = event.target.closest("[data-open]");
  if (button) await openReceipt(button.dataset.open);
};
(async () => {
  try {
    const data = await api("/auth/me");
    user = data.user;
    showWorkspace();
    await loadHistory();
  } catch { showAuth(); }
})();
