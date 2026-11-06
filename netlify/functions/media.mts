// Serves clinic photos and videos that live in Telegram (stored as bot file_ids).
// The bot token stays on the server: the browser only ever sees /api/media/<key>.
// Requires the BOT_TOKEN environment variable (same bot that uploaded the files).

const MEDIA: Record<string, string> = {
  intro_video: "BAACAgIAAxkBAAMUatoq6czKj2y4lhz-7vkwma6mszcAAlCoAAIcrthKQyzOA3DQknI9BA",
  location_video: "BAACAgIAAxkBAAMWatorBfi345N7z4IldNjbqT4kjigAAlyoAAIcrthKEgyGhJAf3eA9BA",
  extra_video_AAMM: "BAACAgIAAxkBAAMMatoqnuTvZJaXFRoEoqmbKJ9Ti3AAAjyoAAIcrthK1rtwOZNcgy49BA",
  doctor_hasan: "AgACAgIAAxkBAAMcauD5aMYAAX8Ge1uPDjBO-xgFrZkUAAJyJWsbZygJSw7qKYIyPvXNAQADAgADeQADPQQ",
  doctor_zuhriddin: "AgACAgIAAxkBAAMaauD5ZLz-YLWoqL1VGutAx4-kLesAAnAlaxtnKAlL2agHXmfmbecBAAMCAAN4AAM9BA",
  certificates: "AgACAgIAAxkBAAMsatoxL0QvTWnvtyettY8Lh1lbs9EAAsYgaxtgKdBKPApuiEZDi4cBAAMCAAN3AAM9BA",
  surgery_photo: "AgACAgIAAxkBAAMqatoww-tDc6nHNM5YaKlO38XhPgoAAnghaxtittFKWlRCVzSJ4LUBAAMCAAN3AAM9BA",
  work_video: "BAACAgIAAxkBAAMiatovbTL7vQHU_Ovuj9zC619-9AoAAvmtAAJittFK9KQZ9pOFeSE9BA",
  patients_video: "BAACAgIAAxkBAAMmatowaZl_RBzpcGg7LauU57t8DkQAAvWoAAIcrthKV4y1hoi1_kg9BA",
  hemorrhoid_1: "BAACAgIAAxkBAAMgatovP-exDO-gc_ywUb3-POwAAbceAAL2rQACYrbRSnIVT8N3ITDpPQQ",
  hemorrhoid_2: "BAACAgIAAxkBAAMaatot825AQb5K92VBaSkAAa8TeIK0AALnrQACYrbRSjPJvgnnHPCnPQQ",
  laser_video_1: "BAACAgIAAxkBAAMKatoqimDCtgYhIMqx2k7ubus2YT0AAkGoAAIcrthKkZF_VOm29r89BA",
  laser_video_2: "BAACAgIAAxkBAAMeauEAAcrVwl70Utjcnf-5dtYYPE6uAAK9rwACZygJSxveoS0BTAWXPQQ",
  laser_photo: "AgACAgIAAxkBAAMgauEDa9NJexCPkeHJr3xgUyUG0eEAAqwlaxtnKAlLUzJPiFS35_EBAAMCAAN3AAM9BA",
  ward_normal_video: "BAACAgIAAxkBAAMWauD5J6YoltiURR3E3gO-Y_mQHzkAAnevAAJnKAlLGczRX0RrfSo9BA",
  ward_normal_photo: "AgACAgIAAxkBAAMiauEGZ8QixIoj-QplLOmHV5DuWIAAAsUlaxtnKAlLoTsP_gABzyGZAQADAgADdwADPQQ",
  ward_lux2_video: "BAACAgIAAxkBAAMYauD5OHbPbhlXWLXpGN0rRe-gU5EAAnivAAJnKAlLjNRkdvfvT809BA",
  ward_lux2_photo: "AgACAgIAAxkBAAMkauEKmcQ5LyCIfG669Qrt7VrEha4AAtUlaxtnKAlLqkqJyCX7XbgBAAMCAAN3AAM9BA",
  ward_lux3_video: "BAACAgIAAxkBAAMUauD5DCKZJ2jHasn1geg4ahLBCf8AAnWvAAJnKAlLBJs2Gvw2g249BA",
  ward_lux3_photo: "AgACAgIAAxkBAAMmauELbFeX2mzyi6WTid-XVfntZ6cAAtolaxtnKAlLDEVAnA4jMIQBAAMCAAN3AAM9BA",
  ward_bathroom: "AgACAgIAAxkBAAMoauEMFpJz5QO4YmkS9XQ8NPmBQycAAtslaxtnKAlL3H8IhT-sld8BAAMCAAN3AAM9BA",
  logo: "AgACAgIAAxkBAAMqauEMn3Ey7Lh2_lJnD4RMkUaQATgAAuAlaxtnKAlLY8tvNFkMwToBAAMCAAN4AAM9BA",
};

function contentTypeFor(path: string, isVideo: boolean): string {
  const ext = path.split(".").pop()?.toLowerCase();
  if (ext === "jpg" || ext === "jpeg") return "image/jpeg";
  if (ext === "png") return "image/png";
  if (ext === "webp") return "image/webp";
  if (ext === "mov") return "video/quicktime";
  if (ext === "mp4" || isVideo) return "video/mp4";
  return "image/jpeg";
}

export default async (req: Request, context: { params: Record<string, string> }) => {
  const key = context.params.key;
  const fileId = key ? MEDIA[key] : undefined;
  if (!fileId) return new Response("Not found", { status: 404 });

  const token = process.env.BOT_TOKEN;
  if (!token) return new Response("Media is not configured", { status: 503 });

  const meta = await fetch(`https://api.telegram.org/bot${token}/getFile?file_id=${encodeURIComponent(fileId)}`);
  const json = (await meta.json().catch(() => null)) as { ok?: boolean; result?: { file_path?: string } } | null;
  const filePath = json?.ok ? json.result?.file_path : undefined;
  if (!filePath) return new Response("Media unavailable", { status: 502 });

  const headers: Record<string, string> = {};
  const range = req.headers.get("range");
  if (range) headers.Range = range;

  const upstream = await fetch(`https://api.telegram.org/file/bot${token}/${filePath}`, { headers });
  if (!upstream.ok || !upstream.body) return new Response("Media unavailable", { status: 502 });

  const out = new Headers({
    "Content-Type": contentTypeFor(filePath, fileId.startsWith("BAAC")),
    "Accept-Ranges": "bytes",
  });
  for (const h of ["content-length", "content-range"]) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  if (upstream.status === 200) {
    out.set("Cache-Control", "public, max-age=86400");
    out.set("Netlify-CDN-Cache-Control", "public, durable, max-age=604800, stale-while-revalidate=86400");
  } else {
    out.set("Cache-Control", "no-store");
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
};

export const config = { path: "/api/media/:key", method: ["GET", "HEAD"] };
