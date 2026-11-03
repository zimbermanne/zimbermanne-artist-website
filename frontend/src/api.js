// Every request to the FastAPI backend goes through this file.
const TOKEN_KEY = "zimbermanne_admin_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function request(path, { method = "GET", body, auth = false, raw = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && getToken()) headers.Authorization = `Bearer ${getToken()}`;
  const res = await fetch(path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
  if (auth && res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event("zimbermanne:signed-out"));
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    const detail = data && (typeof data.detail === "string" ? data.detail : data.message);
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

/* public */
export const getMusic = () => request("/api/music").then((d) => d.albums);
export const getSong = (slug) => request(`/api/song/${encodeURIComponent(slug)}`).catch((e) => (e.status === 404 ? null : Promise.reject(e)));
export const getSite = () => request("/api/site");
export const registerVisit = () => request("/api/visit", { method: "POST" });

// Forms answer { ok, type, message }, also for validation and rate-limit errors.
async function form(path, body) {
  try {
    const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json().catch(() => null);
    if (data && data.message) return data;
    if (data && typeof data.detail === "string") return { ok: false, type: "error", message: data.detail };
  } catch (e) { /* fall through */ }
  return { ok: false, type: "error", message: "Something went wrong. Please try again." };
}
export const sendContact = (b) => form("/api/contact", b);
export const subscribe = (b) => form("/api/subscribe", b);
export const unsubscribeInfo = (t) => request(`/api/unsubscribe/${t}`);
export const unsubscribe = (t) => form(`/api/unsubscribe/${t}`, {});

/* auth */
export const login = (email, password) => request("/api/auth/login", { method: "POST", body: { email, password } });
export const me = () => request("/api/auth/me", { auth: true });
export const changePassword = (current_password, new_password) =>
  request("/api/auth/change-password", { method: "POST", body: { current_password, new_password }, auth: true });

/* admin */
const A = { auth: true };
export const adminStats = () => request("/api/admin/stats", A);
export const adminAlbums = () => request("/api/admin/albums", A);
export const createAlbum = (b) => request("/api/admin/albums", { ...A, method: "POST", body: b });
export const updateAlbum = (id, b) => request(`/api/admin/albums/${id}`, { ...A, method: "PUT", body: b });
export const deleteAlbum = (id) => request(`/api/admin/albums/${id}`, { ...A, method: "DELETE" });
export const createTrack = (albumId, b) => request(`/api/admin/albums/${albumId}/tracks`, { ...A, method: "POST", body: b });
export const updateTrack = (id, b) => request(`/api/admin/tracks/${id}`, { ...A, method: "PUT", body: b });
export const deleteTrack = (id) => request(`/api/admin/tracks/${id}`, { ...A, method: "DELETE" });
export const adminMessages = () => request("/api/admin/messages", A);
export const markMessage = (id, read) => request(`/api/admin/messages/${id}`, { ...A, method: "PATCH", body: { read } });
export const deleteMessage = (id) => request(`/api/admin/messages/${id}`, { ...A, method: "DELETE" });
export const adminSubscribers = () => request("/api/admin/subscribers", A);

export async function downloadSubscribersCsv(all = false) {
  const res = await request(`/api/admin/subscribers.csv${all ? "?all=1" : ""}`, { ...A, raw: true });
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: "fans.csv" });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
