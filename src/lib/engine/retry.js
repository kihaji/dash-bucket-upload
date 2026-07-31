export const MAX_PART_ATTEMPTS = 4;
export const MAX_API_ATTEMPTS = 3;

/**
 * Exponential backoff with jitter: min(base * 2^attempt + jitter, cap).
 * `attempt` is 0-based. `rand` is injectable for tests.
 */
export function backoffDelay(attempt, { base = 1000, cap = 15000, jitter = 500 } = {}, rand = Math.random) {
    return Math.min(base * 2 ** attempt + rand() * jitter, cap);
}

/**
 * Whether an HTTP status is worth retrying. Status 0 is a network error
 * (connection refused, CORS failure, dropped connection).
 */
export function isRetryableStatus(status) {
    return status === 0 || status === 429 || status >= 500;
}

export function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Run `fn` up to `maxAttempts` times, backing off between attempts.
 * Retries when `shouldRetry(error)` returns true; rethrows otherwise.
 * Aborts immediately (rethrowing the error) if `signal` is aborted.
 */
export async function withRetry(fn, { maxAttempts = MAX_PART_ATTEMPTS, shouldRetry, signal, backoffOpts } = {}) {
    let lastError;
    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        if (signal && signal.aborted) {
            throw lastError || new Error('aborted');
        }
        try {
            return await fn(attempt);
        } catch (err) {
            lastError = err;
            const retryable = shouldRetry ? shouldRetry(err) : isRetryableStatus(err.status || 0);
            if (err.isAbort || !retryable || attempt === maxAttempts - 1) {
                throw err;
            }
            await sleep(backoffDelay(attempt, backoffOpts));
        }
    }
    throw lastError;
}
