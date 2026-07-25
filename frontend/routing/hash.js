export function parseHash() {
  const rawHash = window.location.hash.slice(1) || "home";
  const [path, query = ""] = rawHash.split("?");
  const parts = path.split("/").filter(Boolean);
  return { parts, params: new URLSearchParams(query) };
}

export function getPage(params) {
  const value = Number.parseInt(params.get("page") || "1", 10);
  return Number.isFinite(value) && value > 0 ? value : 1;
}
