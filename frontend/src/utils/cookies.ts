export function setSessionCookie(name: string, value: string): void {
  // Creating a cookie without max-age or expires makes it a session-only cookie.
  // It is destroyed by the browser when the browser session ends.
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; SameSite=Lax;`;
}

export function getSessionCookie(name: string): string | null {
  const nameEQ = name + "=";
  const ca = document.cookie.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) === ' ') c = c.substring(1, c.length);
    if (c.indexOf(nameEQ) === 0) {
      return decodeURIComponent(c.substring(nameEQ.length, c.length));
    }
  }
  return null;
}

export function removeSessionCookie(name: string): void {
  // Set expiration date to the past to immediately delete the cookie.
  document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; SameSite=Lax;`;
}
