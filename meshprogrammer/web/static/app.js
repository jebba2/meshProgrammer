async function getJSON(url) {
  const response = await fetch(url);
  return response.json();
}

async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json();
}

function renderResult(el, data) {
  if (data.ok) {
    const { ok, ...rest } = data;
    el.textContent = "Done. " + JSON.stringify(rest);
    el.classList.remove("result-error");
    el.classList.add("result-ok");
  } else {
    const retryHint = data.needs_password ? " Enter the password above and try again." : "";
    el.textContent = "Error: " + data.error + retryHint;
    el.classList.remove("result-ok");
    el.classList.add("result-error");
  }
}

function getConnection(form) {
  const type = form.elements.connectionType.value;
  if (type === "ble") {
    const value = form.elements.ble.value.trim();
    return { port: null, ble: value || "any" };
  }
  const value = form.elements.port.value.trim();
  return { port: value || null, ble: null };
}

async function handleScanClick(button) {
  const fieldset = button.closest(".connection");
  const kind = button.dataset.scan; // "port" or "ble"
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = kind === "ble" ? "Scanning (~10s)..." : "Scanning...";
  try {
    const data = await getJSON(kind === "ble" ? "/api/scan?ble=1" : "/api/scan");
    const items = kind === "ble" ? data.ble_devices : data.ports;
    const select = fieldset.querySelector(`[data-scan-results="${kind}"]`);
    select.innerHTML = "";
    for (const item of items || []) {
      const option = document.createElement("option");
      option.value = item;
      option.textContent = item;
      select.appendChild(option);
    }
    if (items && items.length > 0) {
      fieldset.querySelector(`input[name="${kind}"]`).value = select.value;
      fieldset.querySelector(`input[value="${kind}"]`).checked = true;
    }
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

function injectConnectionFields() {
  const template = document.getElementById("connection-fields-template");
  document.querySelectorAll("form[data-connection]").forEach((form) => {
    form.appendChild(template.content.cloneNode(true));
    form.querySelectorAll("[data-scan]").forEach((button) => {
      button.addEventListener("click", () => handleScanClick(button));
    });
    form.querySelectorAll("select[data-scan-results]").forEach((select) => {
      const kind = select.dataset.scanResults;
      select.addEventListener("change", () => {
        form.querySelector(`input[name="${kind}"]`).value = select.value;
      });
    });
  });
}

async function refreshDevices() {
  const data = await getJSON("/api/list");
  const list = document.getElementById("device-list");
  list.innerHTML = "";
  for (const deviceEntry of data.devices) {
    const li = document.createElement("li");
    const suffix = deviceEntry.backups.length === 1 ? "" : "s";
    li.textContent = `${deviceEntry.node_id} (${deviceEntry.backups.length} backup${suffix})`;
    list.appendChild(li);
  }
}

async function refreshChannels() {
  const data = await getJSON("/api/list-channels");
  const list = document.getElementById("channel-list");
  list.innerHTML = "";
  for (const channelSet of data.channel_sets) {
    const li = document.createElement("li");
    li.textContent = channelSet.name + (channelSet.encrypted ? " (encrypted)" : "");
    list.appendChild(li);
  }
}

function wireRefreshButtons() {
  document.querySelectorAll("[data-refresh]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.refresh === "devices") refreshDevices();
      else refreshChannels();
    });
  });
}

function wireBackupForm() {
  document.getElementById("backup-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const body = {
      ...getConnection(form),
      encrypt: form.elements.encrypt.checked,
      password: form.elements.password.value || null,
    };
    const data = await postJSON("/api/backup", body);
    renderResult(document.getElementById("backup-result"), data);
    if (data.ok) refreshDevices();
  });
}

function wireRestoreForm() {
  document.getElementById("restore-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const mode = document.querySelector('input[name="restoreMode"]:checked').value;
    const body = { ...getConnection(form), password: form.elements.password.value || null };
    if (mode === "node") {
      body.node_id = form.elements.node_id.value || null;
    } else if (mode === "file") {
      body.node_id = form.elements.node_id_for_file.value || null;
      body.filename = form.elements.filename.value || null;
    }
    const data = await postJSON("/api/restore", body);
    renderResult(document.getElementById("restore-result"), data);
  });
}

function wireDeviceBackupsForm() {
  document.getElementById("device-backups-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = await postJSON("/api/device-backups", getConnection(event.target));
    renderResult(document.getElementById("device-backups-result"), data);
  });
}

function wireExportChannelsForm() {
  document.getElementById("export-channels-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const body = {
      ...getConnection(form),
      name: form.elements.name.value,
      encrypt: form.elements.encrypt.checked,
      password: form.elements.password.value || null,
    };
    const data = await postJSON("/api/export-channels", body);
    renderResult(document.getElementById("export-channels-result"), data);
    if (data.ok) refreshChannels();
  });
}

function wireImportChannelsForm() {
  document.getElementById("import-channels-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const body = {
      ...getConnection(form),
      name: form.elements.name.value,
      password: form.elements.password.value || null,
    };
    const data = await postJSON("/api/import-channels", body);
    renderResult(document.getElementById("import-channels-result"), data);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  injectConnectionFields();
  wireRefreshButtons();
  wireBackupForm();
  wireRestoreForm();
  wireDeviceBackupsForm();
  wireExportChannelsForm();
  wireImportChannelsForm();
  refreshDevices();
  refreshChannels();
});
