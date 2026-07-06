const $ = (id) => document.getElementById(id);

const inputs = $("inputs");
const downloadBtn = $("downloadBtn");
const cancelBtn = $("cancelBtn");
const sampleBtn = $("sampleBtn");
const results = $("results");
const files = $("files");
const progress = $("progress");
const progressBar = progress.querySelector("span");
const progressText = progress.querySelector(".progress-text");
const translateToggle = $("translateToggle");
const apiKey = $("apiKey");
const saveKeyBtn = $("saveKeyBtn");
const keyStatus = $("keyStatus");

const STORAGE_KEY = "paperdownload_deepseek_key";

let abortController = null;
let pendingCards = new Map(); // query -> DOM element

// --- API Key persistence ---

function loadApiKey() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    apiKey.value = saved;
    updateKeyStatus(true);
  }
}

function saveApiKey() {
  const key = apiKey.value.trim();
  if (key) {
    localStorage.setItem(STORAGE_KEY, key);
    updateKeyStatus(true);
  } else {
    localStorage.removeItem(STORAGE_KEY);
    updateKeyStatus(false);
  }
}

function updateKeyStatus(saved) {
  keyStatus.textContent = saved ? "✓ 已保存" : "";
  keyStatus.className = saved ? "key-status ok" : "key-status";
}

saveKeyBtn.addEventListener("click", saveApiKey);
apiKey.addEventListener("change", () => updateKeyStatus(false));
apiKey.addEventListener("input", () => updateKeyStatus(false));

// --- Sample data ---

sampleBtn.addEventListener("click", () => {
  inputs.value = [
    "2307.09288",
    "10.48550/arXiv.2307.09288",
    "10.1101/2020.01.01.123456",
  ].join("\n");
});

// --- Clear / refresh ---

$("clearResults").addEventListener("click", () => {
  results.className = "results empty";
  results.textContent = "结果会显示在这里。";
});

$("refreshFiles").addEventListener("click", loadFiles);

// --- Download (streaming) ---

downloadBtn.addEventListener("click", () => {
  const value = inputs.value.trim();
  if (!value) {
    showMessage("请输入至少一个 DOI、arXiv 编号或 URL。", true);
    return;
  }
  startDownload(value);
});

cancelBtn.addEventListener("click", () => {
  if (abortController) {
    abortController.abort();
    setBusy(false);
    showMessage("下载已取消。", false);
  }
});

async function startDownload(value) {
  abortController = new AbortController();
  setBusy(true);
  results.className = "results";
  results.replaceChildren();
  pendingCards.clear();

  if (apiKey.value.trim()) {
    saveApiKey();
  }

  try {
    const response = await fetch("/api/download/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inputs: value,
        translate: translateToggle.checked,
        api_key: translateToggle.checked ? (apiKey.value.trim() || null) : null,
      }),
      signal: abortController.signal,
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value: chunk } = await reader.read();
      if (done) break;

      buffer += decoder.decode(chunk, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6);
        if (!payload) continue;

        let event;
        try {
          event = JSON.parse(payload);
        } catch {
          continue;
        }

        switch (event.type) {
          case "start":
            // Create pending cards for all queries upfront
            for (const q of event.queries) {
              const card = buildPendingCard(q);
              results.appendChild(card);
              pendingCards.set(q, card);
            }
            updateProgress({ done: 0, total: event.total });
            break;

          case "status":
            // Real-time per-item stage updates (e.g. "processing")
            if (event.stages) {
              updateStages(event.stages);
            }
            break;

          case "result":
            // Replace pending card with real result
            updateCardFromResult(event.data);
            updateProgress(event.progress);
            if (event.stages) {
              updateStages(event.stages);
            }
            break;

          case "done":
            // Mark any remaining pending as cancelled
            for (const [q, card] of pendingCards) {
              setCardStage(card, "cancelled");
            }
            break;
        }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") {
      // user cancelled
    } else {
      showMessage(`请求失败：${err.message}`, true);
    }
  } finally {
    setBusy(false);
    await loadFiles();
  }
}

// --- Pending card ---

function buildPendingCard(query) {
  const template = $("resultTemplate");
  const node = template.content.firstElementChild.cloneNode(true);
  node.classList.add("pending");
  node.dataset.query = query;
  node.querySelector(".query").textContent = query;
  node.querySelector(".title").textContent = "等待中…";
  node.querySelector(".meta").textContent = "";
  node.querySelector(".file-link").classList.add("hidden");
  return node;
}

// --- Update card from result ---

function updateCardFromResult(item) {
  const card = pendingCards.get(item.query);
  pendingCards.delete(item.query);
  if (!card) return;

  card.classList.remove("pending");
  if (item.status !== "success") card.classList.add("failed");

  card.querySelector(".title").textContent =
    item.title || item.file || item.error || "未命名";

  const metaParts = [];
  if (item.status === "success") {
    metaParts.push(`${item.source || "OA"} · ${item.file || "已下载"}`);
  }
  if (item.translate_error) {
    metaParts.push(`翻译失败: ${item.translate_error}`);
  }

  const link = card.querySelector(".file-link");
  if (item.status === "success") {
    link.href = `/downloads/${encodeURIComponent(item.file)}`;
    link.textContent = "打开 PDF";
    link.classList.remove("hidden");
  } else if (item.status === "blocked" && item.pdf_url) {
    metaParts.push(`PDF 已找到，但站点拒绝后端直连：${item.error || "HTTP 403"}`);
    link.href = item.pdf_url;
    link.textContent = "在浏览器打开 PDF";
    link.classList.remove("hidden");
  } else {
    metaParts.push(`失败 · ${item.error || "未知错误"}`);
    link.classList.add("hidden");
  }

  card.querySelector(".meta").textContent = metaParts.join(" · ");
}

// --- Stage badges on pending cards ---

function updateStages(stages) {
  for (const [query, stage] of Object.entries(stages)) {
    const card = pendingCards.get(query);
    if (card) {
      setCardStage(card, stage);
    }
  }
}

function setCardStage(card, stage) {
  const labels = {
    queued: "排队中…",
    processing: "处理中…",
    success: "✓ 完成",
    blocked: "⚠ 需手动下载",
    failed: "✗ 失败",
    cancelled: "已取消",
  };
  card.querySelector(".meta").textContent = labels[stage] || stage;
  card.classList.toggle("stage-processing", stage === "processing");
}

// --- Progress ---

function updateProgress(p) {
  if (!p || p.total === 0) return;
  const pct = Math.round((p.done / p.total) * 100);
  progressBar.style.width = pct + "%";
  progressBar.style.animation = "none";
  progressText.textContent = `${p.done}/${p.total} 完成`;
}

// --- Busy state ---

function setBusy(isBusy) {
  downloadBtn.classList.toggle("hidden", isBusy);
  cancelBtn.classList.toggle("hidden", !isBusy);
  progress.classList.toggle("hidden", !isBusy);

  if (!isBusy) {
    progressBar.style.width = "";
    progressBar.style.animation = "";
    progressText.textContent = "";
    abortController = null;
  }
}

// --- Messages ---

function showMessage(message, failed = false) {
  results.className = "results";
  const card = document.createElement("article");
  card.className = `result-card ${failed ? "failed" : ""}`;
  card.innerHTML =
    '<div class="status-dot"></div><div class="result-body"><div class="title"></div></div>';
  card.querySelector(".title").textContent = message;
  results.replaceChildren(card);
}

// --- File list ---

async function loadFiles() {
  const response = await fetch("/api/files");
  const data = await response.json();
  if (!data.length) {
    files.className = "files empty";
    files.textContent = "暂无文件。";
    return;
  }
  files.className = "files";
  files.replaceChildren(
    ...data.map((file) => {
      const row = document.createElement("div");
      row.className = "file-row";
      const size = formatSize(file.size);
      row.innerHTML =
        '<a target="_blank" rel="noopener"></a><span class="file-size"></span>';
      row.querySelector("a").href = file.url;
      row.querySelector("a").textContent = file.name;
      row.querySelector(".file-size").textContent = size;
      return row;
    })
  );
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// --- Init ---

loadApiKey();
loadFiles().catch(() => {});
