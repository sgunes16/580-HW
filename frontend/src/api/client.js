async function parseJson(res) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function readApiError(res) {
  const text = await res.text();
  try {
    const j = JSON.parse(text);
    const d = j.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d))
      return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
    if (d && typeof d === "object") return d.message || JSON.stringify(d);
  } catch {
    /* ignore */
  }
  return text || `HTTP ${res.status}`;
}

export async function getSettings() {
  const res = await fetch("/api/settings");
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function putSettings(body) {
  const res = await fetch("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function listDocuments() {
  const res = await fetch("/api/documents/list");
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function uploadPdf(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/documents/upload", {
    method: "POST",
    body: fd,
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

/** Start background indexing. Omit filename to index all PDFs. */
export async function startReindexJob({ filename = null, reset = false } = {}) {
  const res = await fetch("/api/documents/reindex", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, reset }),
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function getReindexJob(jobId) {
  const res = await fetch(
    `/api/documents/reindex/jobs/${encodeURIComponent(jobId)}`
  );
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function deleteDocumentIndex(filename) {
  const res = await fetch(
    `/api/documents/index/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    }
  );
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function deleteAllIndexes() {
  const res = await fetch("/api/documents/index", {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

/**
 * @param {string} question - Current user message
 * @param {Array<{role: 'user'|'assistant', content: string}>} history - Prior turns only
 * @param {string|null} conversationId - Existing chat id from SQLite, or null for new thread
 */
export async function chat(question, history = [], conversationId = null) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      history,
      conversation_id: conversationId,
    }),
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function chatStream(
  question,
  history = [],
  conversationId = null,
  { onStart, onDelta, onDone, onError } = {}
) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      history,
      conversation_id: conversationId,
    }),
  });
  if (!res.ok) throw new Error(await readApiError(res));
  if (!res.body) throw new Error("Streaming is not supported in this browser.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let donePayload = null;

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let newlineIdx = buffer.indexOf("\n");
    while (newlineIdx >= 0) {
      const raw = buffer.slice(0, newlineIdx).trim();
      buffer = buffer.slice(newlineIdx + 1);

      if (raw) {
        const event = JSON.parse(raw);
        if (event.type === "start") {
          onStart?.(event);
        } else if (event.type === "delta") {
          onDelta?.(event.delta || "");
        } else if (event.type === "done") {
          donePayload = event;
          onDone?.(event);
        } else if (event.type === "error") {
          const err = new Error(event.error || "Streaming failed.");
          onError?.(err);
          throw err;
        }
      }

      newlineIdx = buffer.indexOf("\n");
    }

    if (done) break;
  }

  if (!donePayload) {
    throw new Error("Stream ended before completion.");
  }
  return donePayload;
}

export async function listChats() {
  const res = await fetch("/api/chats");
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function getChatMessages(conversationId) {
  const res = await fetch(
    `/api/chats/${encodeURIComponent(conversationId)}/messages`
  );
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}

export async function deleteChat(conversationId) {
  const res = await fetch(`/api/chats/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await readApiError(res));
  return parseJson(res);
}
