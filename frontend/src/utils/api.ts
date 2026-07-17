export interface ApiRequestOptions extends RequestInit {
  timeout?: number;
  retries?: number;
  backoffFactor?: number;
}

const DEFAULT_TIMEOUT = 10000; // 10s
const DEFAULT_RETRIES = 3;
const DEFAULT_BACKOFF = 300; // ms

// Helper to delay execution
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export class ApiError extends Error {
  status: number;
  statusText: string;
  data: any;

  constructor(status: number, statusText: string, data: any) {
    super(`API Error ${status}: ${statusText}`);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.data = data;
  }
}

/**
 * Fetch wrapper supporting timeouts, custom headers (role switching),
 * and automatic retries with exponential backoff for idempotent requests.
 */
export async function apiFetch<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const {
    timeout = DEFAULT_TIMEOUT,
    retries = DEFAULT_RETRIES,
    backoffFactor = DEFAULT_BACKOFF,
    ...fetchOptions
  } = options;

  let baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  if (!baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
    baseUrl = `https://${baseUrl}`;
  }
  const url = `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`;

  // Get active role from localStorage for dynamic client-side auth switches
  const currentRole = localStorage.getItem('vertex_role') || 'user';
  
  const headers = new Headers(fetchOptions.headers);
  if (!headers.has('Content-Type') && !(fetchOptions.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('X-Role', currentRole);
  fetchOptions.headers = headers;

  const method = (fetchOptions.method || 'GET').toUpperCase();
  const isIdempotent = method === 'GET' || method === 'PUT' || method === 'DELETE';

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      if (attempt > 0) {
        // Wait with exponential backoff: factor * 2^attempt
        const delay = backoffFactor * Math.pow(2, attempt);
        await sleep(delay);
      }

      const response = await fetch(url, {
        ...fetchOptions,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        let errorData;
        try {
          errorData = await response.json();
        } catch {
          errorData = await response.text();
        }
        throw new ApiError(response.status, response.statusText, errorData);
      }

      // Check if there is content to parse
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return (await response.json()) as T;
      }
      return {} as T;

    } catch (err: any) {
      clearTimeout(timeoutId);
      
      if (err.name === 'AbortError') {
        lastError = new Error(`Request timed out after ${timeout}ms`);
      } else {
        lastError = err;
      }

      // Only retry if it's an idempotent method, or if we got a network error (not an HTTP error status code)
      const isHttpError = err instanceof ApiError;
      const isServerSideError = isHttpError && (err.status >= 500 || err.status === 429);
      const isNetworkError = !isHttpError;
      
      const shouldRetry = (isIdempotent || isNetworkError || isServerSideError) && attempt < retries;

      if (!shouldRetry) {
        throw lastError;
      }
    }
  }

  throw lastError || new Error('Request failed');
}
