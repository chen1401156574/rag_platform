export type JwtSubject = {
  user_id?: string | number;
  user_name?: string;
  role?: string | null;
  status?: number | string | boolean | null;
};

function decodeBase64Url(value: string) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
  return window.atob(padded);
}

export function decodeJwtSubject(token: string | null | undefined): JwtSubject | null {
  if (!token) return null;
  const rawToken = token.replace(/^Bearer\s+/i, "");
  const payload = rawToken.split(".")[1];
  if (!payload) return null;

  try {
    const claims = JSON.parse(decodeBase64Url(payload));
    const subject = claims.subject ?? claims.sub;
    if (subject && typeof subject === "object") {
      return subject as JwtSubject;
    }
    return null;
  } catch {
    return null;
  }
}

export function isAdminSubject(subject: JwtSubject | null | undefined) {
  const status = subject?.status === undefined || subject?.status === null ? 1 : Number(subject.status);
  return subject?.role === "admin" && status === 1;
}
