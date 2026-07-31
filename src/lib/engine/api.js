import { withRetry, MAX_API_ATTEMPTS } from './retry';

/**
 * POST JSON to a widget API route and parse the JSON response.
 * Server errors arrive as {"error": message} — surfaced verbatim.
 * Retries network errors / 429 / 5xx up to MAX_API_ATTEMPTS.
 */
export async function apiPost(url, payload, { signal, fetchImpl } = {}) {
    const doFetch = fetchImpl || ((...args) => fetch(...args));
    return withRetry(
        async () => {
            let response;
            try {
                response = await doFetch(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    signal,
                });
            } catch (err) {
                if (signal && signal.aborted) {
                    err.isAbort = true;
                    throw err;
                }
                err.status = 0;
                err.isNetworkError = true;
                throw err;
            }
            if (!response.ok) {
                let message = `request to ${url} failed with status ${response.status}`;
                try {
                    const body = await response.json();
                    if (body && body.error) {
                        message = body.error;
                    }
                } catch {
                    // non-JSON error body; keep the generic message
                }
                const err = new Error(message);
                err.status = response.status;
                throw err;
            }
            return response.json();
        },
        { maxAttempts: MAX_API_ATTEMPTS, signal }
    );
}
