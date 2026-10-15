export const DEFAULT_API_URL = 'http://16.176.162.28:8000';
import { getSessionCookie, removeSessionCookie } from './cookies';

let apiRootUrl = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

/**
 * Gets the current active root API URL.
 * Checks for window-level context or local storage configuration before falling back to the default.
 */
export function getApiUrl(): string {
  return (window as any).VITE_API_URL || localStorage.getItem('VITE_API_URL') || apiRootUrl;
}

/**
 * Changes the active root API URL dynamically.
 */
export function setApiUrl(newUrl: string): void {
  apiRootUrl = newUrl;
  localStorage.setItem('VITE_API_URL', newUrl);
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: any;
  headers?: Record<string, string>;
}

export async function request(path: string, options: RequestOptions = {}) {
  const method = options.method || 'GET';
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  const token = getSessionCookie('auth_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const fetchOptions: RequestInit = {
    method,
    headers,
  };

  if (options.body) {
    if (options.body instanceof FormData) {
      // For YAML config uploads, remove Content-Type header so browser sets multipart boundary automatically
      delete headers['Content-Type'];
      fetchOptions.body = options.body;
    } else {
      fetchOptions.body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(`${getApiUrl()}${path}`, fetchOptions);

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg = data?.detail || 'An unexpected error occurred';
    if (response.status === 401) {
      removeSessionCookie('auth_token');
      removeSessionCookie('auth_user');
      window.dispatchEvent(new Event('auth-logout'));
    }
    throw new Error(errorMsg);
  }

  return data;
}

export const api = {
  get: (path: string, headers?: Record<string, string>) => request(path, { method: 'GET', headers }),
  post: (path: string, body?: any, headers?: Record<string, string>) => request(path, { method: 'POST', body, headers }),
  patch: (path: string, body?: any, headers?: Record<string, string>) => request(path, { method: 'PATCH', body, headers }),
  delete: (path: string, headers?: Record<string, string>) => request(path, { method: 'DELETE', headers }),
};
