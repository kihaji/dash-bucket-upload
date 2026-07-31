import { uploadFile } from './fileUpload';
import { createSpeedEstimator } from './speed';

/** Simple async semaphore: acquire() resolves to a release function. */
export function createTokenPool(max) {
    let available = max;
    const waiters = [];
    const release = () => {
        const next = waiters.shift();
        if (next) {
            next(release);
        } else {
            available += 1;
        }
    };
    return {
        acquire() {
            if (available > 0) {
                available -= 1;
                return Promise.resolve(release);
            }
            return new Promise((resolve) => waiters.push(resolve));
        },
    };
}

let nextFileId = 0;

/**
 * Engine coordinating uploads for one BucketUpload component instance.
 *
 * State per file: {fileId, batchId, filename, size, loaded, percent, speedBps,
 * status: pending|uploading|done|error|canceled, result, error}.
 *
 * `onEvent(type, payload)` fires with:
 *   'progress'       — any byte-count change (caller throttles)
 *   'file-settled'   — a file reached done/error/canceled
 *   'batch-settled'  — every file from one addFiles() call settled;
 *                      payload.results holds the done files' server results
 */
export function createUploadEngine({
    apiBase,
    uploadId,
    maxConcurrency = 6,
    perFileConcurrency = 4,
    maxFileSize = null,
    onEvent,
    fetchImpl,
}) {
    const pool = createTokenPool(maxConcurrency);
    const files = new Map();
    const batches = new Map();
    let nextBatchId = 0;

    const snapshot = () => Object.fromEntries(
        [...files.entries()].map(([id, f]) => [
            id,
            {
                fileId: id,
                batchId: f.batchId,
                filename: f.filename,
                size: f.size,
                loaded: f.loaded,
                percent: f.size > 0 ? Math.round((f.loaded / f.size) * 100) : (f.status === 'done' ? 100 : 0),
                speedBps: Math.round(f.speedBps),
                status: f.status,
                error: f.error,
            },
        ])
    );

    const emit = (type, payload = {}) => {
        if (onEvent) {
            onEvent(type, { ...payload, files: snapshot() });
        }
    };

    function settleFile(fileId, status, extra = {}) {
        const f = files.get(fileId);
        f.status = status;
        Object.assign(f, extra);
        emit('file-settled', { fileId, status });

        const batch = batches.get(f.batchId);
        batch.remaining -= 1;
        if (batch.remaining === 0) {
            const settled = [...files.values()].filter((x) => x.batchId === f.batchId);
            emit('batch-settled', {
                batchId: f.batchId,
                results: settled.filter((x) => x.status === 'done').map((x) => x.result),
                failed: settled
                    .filter((x) => x.status === 'error')
                    .map((x) => ({ filename: x.filename, message: x.error, phase: x.errorPhase })),
            });
            batches.delete(f.batchId);
        }
    }

    async function runFile(fileId) {
        const f = files.get(fileId);
        f.status = 'uploading';
        emit('progress', { fileId });
        try {
            const result = await uploadFile({
                file: f.file,
                apiBase,
                uploadId,
                acquireToken: () => pool.acquire(),
                perFileConcurrency,
                signal: f.controller.signal,
                fetchImpl,
                onProgress: (loaded) => {
                    f.loaded = loaded;
                    f.speedBps = f.speed.update(loaded);
                    emit('progress', { fileId });
                },
            });
            f.loaded = f.size;
            settleFile(fileId, 'done', { result: { ...result, status: 'done' } });
        } catch (err) {
            if (err.isAbort || f.controller.signal.aborted) {
                settleFile(fileId, 'canceled');
            } else {
                settleFile(fileId, 'error', { error: err.message, errorPhase: err.phase || 'part' });
            }
        }
    }

    return {
        /** Queue a batch of File objects; returns the batch id. */
        addFiles(fileList) {
            const accepted = [];
            const rejected = [];
            [...fileList].forEach((file) => {
                if (maxFileSize && file.size > maxFileSize) {
                    rejected.push({ filename: file.name, message: `file exceeds the maximum size of ${maxFileSize} bytes`, phase: 'validate' });
                } else {
                    accepted.push(file);
                }
            });
            if (rejected.length > 0) {
                emit('rejected', { rejected });
            }
            if (accepted.length === 0) {
                return null;
            }

            const batchId = nextBatchId;
            nextBatchId += 1;
            batches.set(batchId, { remaining: accepted.length });
            accepted.forEach((file) => {
                const fileId = `f${nextFileId}`;
                nextFileId += 1;
                files.set(fileId, {
                    file,
                    batchId,
                    filename: file.name,
                    size: file.size,
                    loaded: 0,
                    speedBps: 0,
                    speed: createSpeedEstimator(),
                    status: 'pending',
                    controller: new AbortController(),
                });
                runFile(fileId);
            });
            return batchId;
        },
        cancelFile(fileId) {
            const f = files.get(fileId);
            if (f && (f.status === 'pending' || f.status === 'uploading')) {
                f.controller.abort();
            }
        },
        cancelAll() {
            files.forEach((f) => {
                if (f.status === 'pending' || f.status === 'uploading') {
                    f.controller.abort();
                }
            });
        },
        isUploading() {
            return [...files.values()].some((f) => f.status === 'pending' || f.status === 'uploading');
        },
        getState: snapshot,
    };
}
