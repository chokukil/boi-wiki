export function isExactDisabledAdapterResponse(item) {
  if (!item || typeof item !== "object") return false;
  let path = "";
  try { path = new URL(String(item.url || ""), "http://localhost").pathname; }
  catch { return false; }
  const detail = item.payload?.detail;
  return path === "/api/science/interpret"
    && item.status === 503
    && detail?.code === "science_interpretation_unavailable"
    && detail?.diagnostic_code === "adapter_disabled";
}
