import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createTokenPool, createUploadEngine } from '../uploadEngine';
import { uploadFile } from '../fileUpload';

vi.mock('../fileUpload', () => ({ uploadFile: vi.fn() }));

beforeEach(() => {
    // Braces matter: mockReset() returns the mock, and a function returned
    // from a vitest hook is invoked (arg-less) as teardown.
    uploadFile.mockReset();
});

const flush = () => new Promise((r) => setTimeout(r, 10));

describe('createTokenPool', () => {
    it('caps concurrent holders and hands tokens to waiters in order', async () => {
        const pool = createTokenPool(2);
        const r1 = await pool.acquire();
        await pool.acquire();
        let third = false;
        const p3 = pool.acquire().then((release) => {
            third = true;
            return release;
        });
        await flush();
        expect(third).toBe(false); // pool exhausted
        r1();
        const r3 = await p3;
        expect(third).toBe(true);
        r3();
    });
});

describe('createUploadEngine', () => {
    it('runs a batch and reports batch-settled with results only from done files', async () => {
        uploadFile.mockImplementation(async ({ file, onProgress }) => {
            if (file.name === 'bad.bin') {
                const err = new Error('exploded');
                err.phase = 'part';
                throw err;
            }
            onProgress(file.size);
            return { bucket: 'bkt', key: `p/u/${file.name}`, filename: file.name, size: file.size, etag: '"e"' };
        });

        const events = [];
        const engine = createUploadEngine({
            apiBase: '/x',
            uploadId: 'default',
            onEvent: (type, payload) => events.push({ type, payload }),
        });

        engine.addFiles([
            { name: 'good.bin', size: 10 },
            { name: 'bad.bin', size: 20 },
        ]);
        await flush();

        const settled = events.find((e) => e.type === 'batch-settled');
        expect(settled).toBeTruthy();
        expect(settled.payload.results).toHaveLength(1);
        expect(settled.payload.results[0]).toMatchObject({ filename: 'good.bin', status: 'done' });
        expect(settled.payload.failed).toEqual([{ filename: 'bad.bin', message: 'exploded', phase: 'part' }]);
        expect(engine.isUploading()).toBe(false);

        const statuses = Object.values(engine.getState()).map((f) => f.status);
        expect(statuses.sort()).toEqual(['done', 'error']);
    });

    it('rejects oversized files client-side without starting an upload', async () => {
        const events = [];
        const engine = createUploadEngine({
            apiBase: '/x',
            uploadId: 'default',
            maxFileSize: 100,
            onEvent: (type, payload) => events.push({ type, payload }),
        });
        const batchId = engine.addFiles([{ name: 'huge.bin', size: 101 }]);
        expect(batchId).toBeNull();
        expect(uploadFile).not.toHaveBeenCalled();
        const rejected = events.find((e) => e.type === 'rejected');
        expect(rejected.payload.rejected[0].filename).toBe('huge.bin');
    });

    it('cancelFile aborts that file only and the batch still settles', async () => {
        uploadFile.mockImplementation(
            ({ file, signal }) => new Promise((resolve, reject) => {
                signal.addEventListener('abort', () => {
                    const err = new Error('canceled');
                    err.isAbort = true;
                    reject(err);
                });
                if (file.name === 'fast.bin') {
                    resolve({ bucket: 'b', key: 'k', filename: file.name, size: file.size, etag: '"e"' });
                }
            })
        );

        const events = [];
        const engine = createUploadEngine({
            apiBase: '/x',
            uploadId: 'default',
            onEvent: (type, payload) => events.push({ type, payload }),
        });
        engine.addFiles([
            { name: 'fast.bin', size: 1 },
            { name: 'slow.bin', size: 1 },
        ]);
        await flush();
        const slowId = Object.values(engine.getState()).find((f) => f.filename === 'slow.bin').fileId;
        engine.cancelFile(slowId);
        await flush();

        const settled = events.find((e) => e.type === 'batch-settled');
        expect(settled.payload.results.map((r) => r.filename)).toEqual(['fast.bin']);
        expect(engine.getState()[slowId].status).toBe('canceled');
    });
});
