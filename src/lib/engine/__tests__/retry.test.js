import { describe, expect, it, vi } from 'vitest';
import { backoffDelay, isRetryableStatus, withRetry } from '../retry';

const FAST = { base: 1, cap: 5, jitter: 0 };

describe('backoffDelay', () => {
    it('grows exponentially with jitter and caps out', () => {
        const rand = () => 0.5;
        expect(backoffDelay(0, { base: 1000, cap: 15000, jitter: 500 }, rand)).toBe(1250);
        expect(backoffDelay(1, { base: 1000, cap: 15000, jitter: 500 }, rand)).toBe(2250);
        expect(backoffDelay(10, { base: 1000, cap: 15000, jitter: 500 }, rand)).toBe(15000);
    });
});

describe('isRetryableStatus', () => {
    it('retries network errors, 429 and 5xx only', () => {
        expect(isRetryableStatus(0)).toBe(true);
        expect(isRetryableStatus(429)).toBe(true);
        expect(isRetryableStatus(500)).toBe(true);
        expect(isRetryableStatus(503)).toBe(true);
        expect(isRetryableStatus(400)).toBe(false);
        expect(isRetryableStatus(403)).toBe(false);
        expect(isRetryableStatus(200)).toBe(false);
    });
});

describe('withRetry', () => {
    it('retries retryable failures then succeeds', async () => {
        let calls = 0;
        const fn = vi.fn(async () => {
            calls += 1;
            if (calls < 3) {
                const err = new Error('boom');
                err.status = 503;
                throw err;
            }
            return 'ok';
        });
        await expect(withRetry(fn, { backoffOpts: FAST })).resolves.toBe('ok');
        expect(fn).toHaveBeenCalledTimes(3);
    });

    it('does not retry non-retryable errors', async () => {
        const fn = vi.fn(async () => {
            const err = new Error('bad request');
            err.status = 400;
            throw err;
        });
        await expect(withRetry(fn, { backoffOpts: FAST })).rejects.toThrow('bad request');
        expect(fn).toHaveBeenCalledTimes(1);
    });

    it('gives up after maxAttempts', async () => {
        const fn = vi.fn(async () => {
            const err = new Error('down');
            err.status = 500;
            throw err;
        });
        await expect(withRetry(fn, { maxAttempts: 4, backoffOpts: FAST })).rejects.toThrow('down');
        expect(fn).toHaveBeenCalledTimes(4);
    });

    it('never retries aborts', async () => {
        const fn = vi.fn(async () => {
            const err = new Error('aborted');
            err.isAbort = true;
            err.status = 0;
            throw err;
        });
        await expect(withRetry(fn, { backoffOpts: FAST })).rejects.toThrow('aborted');
        expect(fn).toHaveBeenCalledTimes(1);
    });
});
