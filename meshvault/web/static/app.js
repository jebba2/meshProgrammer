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

function renderDeviceBackups(el, data) {
  el.innerHTML = "";
  el.classList.remove("result-ok", "result-error");
  if (!data.ok) {
    el.classList.add("result-error");
    const retryHint = data.needs_password ? " Enter the password above and try again." : "";
    el.textContent = "Error: " + data.error + retryHint;
    return;
  }
  el.classList.add("result-ok");
  const suffix = data.backups.length === 1 ? "" : "s";
  const heading = document.createElement("p");
  heading.textContent = `${data.node_id} (${data.backups.length} backup${suffix})`;
  el.appendChild(heading);
  const list = document.createElement("ul");
  for (const name of data.backups) {
    const li = document.createElement("li");
    li.textContent = name;
    list.appendChild(li);
  }
  el.appendChild(list);
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

function makeDeleteButton(onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Delete";
  button.addEventListener("click", onClick);
  return button;
}

async function deleteBackup(nodeId, filename) {
  if (!confirm(`Delete backup '${filename}' for ${nodeId}? This cannot be undone.`)) return;
  const data = await postJSON("/api/delete-backup", { node_id: nodeId, filename });
  if (!data.ok) {
    alert("Error: " + data.error);
    return;
  }
  refreshDevices();
}

function renderDeviceList(listEl, devices) {
  listEl.innerHTML = "";
  for (const deviceEntry of devices) {
    const li = document.createElement("li");
    const suffix = deviceEntry.backups.length === 1 ? "" : "s";
    const heading = document.createElement("span");
    heading.textContent = `${deviceEntry.node_id} (${deviceEntry.backups.length} backup${suffix})`;
    li.appendChild(heading);

    const backupList = document.createElement("ul");
    for (const filename of deviceEntry.backups) {
      const backupLi = document.createElement("li");
      backupLi.append(filename + " ");
      backupLi.appendChild(makeDeleteButton(() => deleteBackup(deviceEntry.node_id, filename)));
      backupList.appendChild(backupLi);
    }
    li.appendChild(backupList);

    listEl.appendChild(li);
  }
}

async function refreshDevices() {
  const data = await getJSON("/api/list");
  renderDeviceList(document.getElementById("device-list"), data.devices);
  renderDeviceList(document.getElementById("restore-device-list"), data.devices);
}

async function deleteChannelSet(name) {
  if (!confirm(`Delete saved channel set '${name}'? This cannot be undone.`)) return;
  const data = await postJSON("/api/delete-channels", { name });
  if (!data.ok) {
    alert("Error: " + data.error);
    return;
  }
  refreshChannels();
}

function renderChannelSetList(listEl, channelSets) {
  listEl.innerHTML = "";
  for (const channelSet of channelSets) {
    const li = document.createElement("li");
    li.append(channelSet.name + (channelSet.encrypted ? " (encrypted) " : " "));
    li.appendChild(makeDeleteButton(() => deleteChannelSet(channelSet.name)));
    listEl.appendChild(li);
  }
}

async function refreshChannels() {
  const data = await getJSON("/api/list-channels");
  renderChannelSetList(document.getElementById("channel-list"), data.channel_sets);
  renderChannelSetList(document.getElementById("import-channel-sets"), data.channel_sets);
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
    renderDeviceBackups(document.getElementById("device-backups-result"), data);
  });
}

function wireFlashFirmwareForm() {
  document.getElementById("flash-firmware-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultEl = document.getElementById("flash-firmware-result");
    const data = await postJSON("/api/flash-firmware", getConnection(event.target));
    if (!data.ok) {
      renderResult(resultEl, data);
      return;
    }
    const label = data.hardware_model || "unknown hardware model";
    const proceed = confirm(
      `Detected ${data.node_id} (${label}). Open the official Meshtastic web flasher to update its firmware?`
    );
    resultEl.classList.remove("result-error");
    resultEl.classList.add("result-ok");
    if (!proceed) {
      resultEl.textContent = "Cancelled.";
      return;
    }
    window.open("https://flasher.meshtastic.org/", "_blank", "noopener,noreferrer");
    resultEl.textContent = `Detected ${data.node_id} (${label}). Opened the web flasher in a new tab.`;
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
  wireFlashFirmwareForm();
  wireExportChannelsForm();
  wireImportChannelsForm();
  refreshDevices();
  refreshChannels();
});
