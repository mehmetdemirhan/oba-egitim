import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function pushDestekleniyor() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

/** Service worker'ı kaydet (uygulama açılışında bir kez). */
export async function swKaydet() {
  if (!("serviceWorker" in navigator)) return null;
  try { return await navigator.serviceWorker.register("/sw.js"); } catch { return null; }
}

/** "default" | "granted" | "denied" | "desteklenmiyor" */
export function bildirimDurumu() {
  if (!pushDestekleniyor()) return "desteklenmiyor";
  return Notification.permission;
}

/** İzin iste + aboneliği backend'e kaydet. */
export async function pushAboneOl() {
  if (!pushDestekleniyor()) throw new Error("Tarayıcınız bildirimleri desteklemiyor.");
  const izin = await Notification.requestPermission();
  if (izin !== "granted") throw new Error("Bildirim izni verilmedi.");
  const reg = await navigator.serviceWorker.ready;
  const { data } = await axios.get(`${API}/push/vapid-public`);
  if (!data.public_key) throw new Error("Sunucuda bildirim yapılandırılmamış.");
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(data.public_key),
  });
  await axios.post(`${API}/push/abone`, { subscription: sub.toJSON() });
  return true;
}

/** Bu cihazın aboneliğini kaldır. */
export async function pushAbonelikBitir() {
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) {
      await axios.delete(`${API}/push/abone`, { data: { endpoint: sub.endpoint } });
      await sub.unsubscribe();
    }
  } catch {}
}
