import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { uploadFile } from '../fileUpload';
import { xhrPut } from '../xhrPut';
import { CORS_ETAG_HINT } from '../transports/direct';

vi.mock('../xhrPut', () => ({ xhrPut: vi.fn() }));

const jsonResponse = (data) => ({ ok: true, json: async () => data });
const errorResponse = (status, message) => ({ ok: false, status, json: async () => ({ error: message }) });

function makeFile(size, name = 'data.bin') {
    const blob = new Blob([new Uint8Array(size)]);
    return { name, size, type: 'application/octet-stream', slice: (s, e) => blob.slice(s, e) };
}

function makeFetch({ mode = 'direct', partSize = 5, overrides = {} } = {}) {
    const calls = [];
    const fetchImpl = vi.fn(async (url, opts) => {
        const route = url.split('?')[0].split('/').pop();
        const body = JSON.parse(opts.body);
        calls.push({ route, body });
        if (overrides[route]) {
            return overrides[route](body);
        }
        if (route === 'create') {
            return jsonResponse({ bucket: 'bkt', key: 'pre/uuid/data.bin', s3UploadId: 'U1', partSize, mode });
        }
        if (route === 'sign-parts') {
            return jsonResponse({
                urls: Object.fromEntries(body.partNumbers.map((n) => [n, `http://bucket/part-${n}`])),
            });
        }
        if (route === 'complete') {
            return jsonResponse({ bucket: 'bkt', key: body.key, filename: 'data.bin', size: 12, etag: '"final"' });
        }
        if (route === 'abort') {
            return jsonResponse({ aborted: true });
        }
        throw new Error(`unexpected route ${route}`);
    });
    return { fetchImpl, calls };
}

const noTokenLimit = () => Promise.resolve(() => {});

const baseOpts = (fetchImpl) => ({
    apiBase: '/dash-bucket-upload',
    uploadId: 'default',
    acquireToken: noTokenLimit,
    fetchImpl,
});

beforeEach(() => {
    xhrPut.mockReset();
    let n = 0;
    xhrPut.mockImplementation(async () => {
        n += 1;
        return { status: 200, etag: `"etag-${n}"`, responseText: '' };
    });
});

afterEach(() => {
    vi.useRealTimers();
});

describe('uploadFile (direct transport)', () => {
    it('creates, uploads all parts, and completes with sorted part numbers', async () => {
        const { fetchImpl, calls } = makeFetch();
        const progress = [];
        const result = await uploadFile({
            ...baseOpts(fetchImpl),
            file: makeFile(12),
            onProgress: (loaded) => progress.push(loaded),
        });

        expect(result).toMatchObject({ bucket: 'bkt', filename: 'data.bin', size: 12 });
        expect(xhrPut).toHaveBeenCalledTimes(3); // 12 bytes / partSize 5 = parts of 5,5,2
        const complete = calls.find((c) => c.route === 'complete');
        expect(complete.body.parts.map((p) => p.partNumber)).toEqual([1, 2, 3]);
        expect(complete.body.parts.every((p) => p.etag.startsWith('"etag-'))).toBe(true);
        expect(progress[progress.length - 1]).toBe(12);
        expect(calls.some((c) => c.route === 'abort')).toBe(false);
    });

    it('retries a 503 part failure and still succeeds', async () => {
        vi.useFakeTimers();
        let attempts = 0;
        xhrPut.mockImplementation(async () => {
            attempts += 1;
            if (attempts === 1) {
                const err = new Error('service unavailable');
                err.status = 503;
                throw err;
            }
            return { status: 200, etag: `"etag-${attempts}"`, responseText: '' };
        });
        const { fetchImpl, calls } = makeFetch({ partSize: 12 });
        const promise = uploadFile({ ...baseOpts(fetchImpl), file: makeFile(12) });
        await vi.advanceTimersByTimeAsync(60000);
        const result = await promise;
        expect(result.size).toBe(12);
        expect(attempts).toBe(2);
        expect(calls.some((c) => c.route === 'abort')).toBe(false);
    });

    it('refreshes the presigned URL on 403 without burning an attempt', async () => {
        let attempts = 0;
        xhrPut.mockImplementation(async (url) => {
            attempts += 1;
            if (attempts === 1) {
                const err = new Error('expired');
                err.status = 403;
                throw err;
            }
            return { status: 200, etag: '"fresh"', responseText: String(url) };
        });
        const { fetchImpl, calls } = makeFetch({ partSize: 12 });
        await uploadFile({ ...baseOpts(fetchImpl), file: makeFile(12) });
        expect(attempts).toBe(2);
        // Two sign-parts calls: the initial window and the 403 refresh.
        expect(calls.filter((c) => c.route === 'sign-parts')).toHaveLength(2);
    });

    it('fails fast with the CORS hint when the ETag header is unreadable', async () => {
        xhrPut.mockImplementation(async () => ({ status: 200, etag: null, responseText: '' }));
        const { fetchImpl, calls } = makeFetch({ partSize: 12 });
        await expect(uploadFile({ ...baseOpts(fetchImpl), file: makeFile(12) })).rejects.toThrow(CORS_ETAG_HINT);
        expect(xhrPut).toHaveBeenCalledTimes(1); // config errors are not retried
        expect(calls.some((c) => c.route === 'abort')).toBe(true);
    });

    it('aborts the multipart upload when canceled mid-flight', async () => {
        xhrPut.mockImplementation(
            (url, body, { signal }) => new Promise((resolve, reject) => {
                signal.addEventListener('abort', () => {
                    const err = new Error('canceled');
                    err.isAbort = true;
                    reject(err);
                });
            })
        );
        const { fetchImpl, calls } = makeFetch({ partSize: 12 });
        const controller = new AbortController();
        const promise = uploadFile({ ...baseOpts(fetchImpl), file: makeFile(12), signal: controller.signal });
        await new Promise((r) => setTimeout(r, 10));
        controller.abort();
        await expect(promise).rejects.toMatchObject({ isAbort: true });
        await new Promise((r) => setTimeout(r, 10));
        expect(calls.some((c) => c.route === 'abort')).toBe(true);
    });

    it('surfaces server validation errors from /create verbatim', async () => {
        const { fetchImpl } = makeFetch({
            overrides: { create: () => errorResponse(413, 'file exceeds the maximum size of 100 bytes') },
        });
        await expect(uploadFile({ ...baseOpts(fetchImpl), file: makeFile(12) })).rejects.toMatchObject({
            message: 'file exceeds the maximum size of 100 bytes',
            phase: 'create',
        });
        expect(xhrPut).not.toHaveBeenCalled();
    });
});

describe('uploadFile (relay transport)', () => {
    it('PUTs parts to the relay route and reads etags from the JSON body', async () => {
        xhrPut.mockImplementation(async (url) => ({
            status: 200,
            etag: null,
            responseText: JSON.stringify({
                partNumber: Number(new URL(url, 'http://x').searchParams.get('partNumber')),
                etag: '"relay-etag"',
            }),
        }));
        const { fetchImpl, calls } = makeFetch({ mode: 'relay', partSize: 5 });
        const result = await uploadFile({ ...baseOpts(fetchImpl), file: makeFile(12) });
        expect(result.size).toBe(12);
        // Relay mode never presigns.
        expect(calls.some((c) => c.route === 'sign-parts')).toBe(false);
        const putUrl = xhrPut.mock.calls[0][0];
        expect(putUrl).toContain('/part?');
        expect(putUrl).toContain('s3UploadId=U1');
    });
});
