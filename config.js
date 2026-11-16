// Tunnel API manzili. Oxirida "/" bo'lmasin.
window.HUMO_API = "https://ideal-anime-prep-ago.trycloudflare.com";

// Test rejimida faqat oldindan sozlangan tunnel manzili ishlatiladi.
window.HUMO_TEST = true;
if (window.HUMO_TEST) {
  const q = new URLSearchParams(location.search).get("api");
  if (q && q.replace(/\/$/, "") === window.HUMO_API) window.HUMO_API = q.replace(/\/$/, "");
}
