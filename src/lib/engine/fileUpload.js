import { apiPost } from './api';
import { buildParts } from './partSize';
import { withRetry, MAX_PART_ATTEMPTS } from './retry';
import { createDirectTransport } from './transports/direct';
import { createRelayTransport } from './transports/relay';

function tagError(err, phase, filename) {
    err.phase = err.phase || phase;
    err.filename = filename;
    return err;
}

/**
 * Upload one file end-to-end: create multipart upload, PUT all parts through
 * the server-selected transport with bounded concurrency and retry, then
 * complete. Aborts the S3 multipart upload on failure or cancellation.
 *
 * `acquireToken` gates each part PUT on the engine-wide concurrency pool and
 * resolves to a release function.
 *
 * Returns {bucket, key, filename, size, etag}.
 */
export async function uploadFile({
    file,
    apiBase,
    uploadId,
    acquireToken,
    perFileConcurrency = 4,
    onProgress,
    signal,
    fetchImpl,
}) {
    const filename = file.name;

    const created = await apiPost(
        `${apiBase}/create`,
        { uploadId, filename, size: file.size, contentType: file.type || 'application/octet-stream' },
        { signal, fetchImpl }
    ).catch((err) => {
        throw tagError(err, 'create', filename);
    });

    const { key, s3UploadId, partSize, mode } = created;
    const parts = buildParts(file.size, partSize);
    const transportOpts = {
        apiBase,
        uploadId,
        key,
        s3UploadId,
        allPartNumbers: parts.map((p) => p.partNumber),
        fetchImpl,
    };
    const transport = mode === 'relay' ? createRelayTransport(transportOpts) : createDirectTransport(transportOpts);

    const completedParts = [];
    let completedBytes = 0;
    const inFlightLoaded = new Map();

    const reportProgress = () => {
        if (onProgress) {
            let loaded = completedBytes;
            inFlightLoaded.forEach((bytes) => {
                loaded += bytes;
            });
            onProgress(Math.min(loaded, file.size));
        }
    };

    async function uploadOnePart(part) {
        const release = await acquireToken();
        try {
            const blob = file.slice(part.start, part.end);
            const result = await withRetry(
                (attempt) => {
                    // A failed attempt's progress must not linger in the total.
                    inFlightLoaded.set(part.partNumber, 0);
                    reportProgress();
                    return transport.uploadPart(part, blob, {
                        signal,
                        onProgress: (loaded) => {
                            inFlightLoaded.set(part.partNumber, loaded);
                            reportProgress();
                        },
                        attempt,
                    });
                },
                {
                    maxAttempts: MAX_PART_ATTEMPTS,
                    signal,
                    shouldRetry: (err) => !err.isConfigError && !err.isAbort,
                }
            );
            inFlightLoaded.delete(part.partNumber);
            completedBytes += part.size;
            completedParts.push(result);
            reportProgress();
        } finally {
            release();
        }
    }

    // Worker pool: perFileConcurrency workers drain the part queue; the global
    // token pool may throttle further across files.
    const queue = [...parts];
    async function worker() {
        while (queue.length > 0) {
            if (signal && signal.aborted) {
                const err = new Error('upload canceled');
                err.isAbort = true;
                throw err;
            }
            const part = queue.shift();
            await uploadOnePart(part);
        }
    }

    try {
        await Promise.all(
            Array.from({ length: Math.min(perFileConcurrency, parts.length) }, () => worker())
        );

        completedParts.sort((a, b) => a.partNumber - b.partNumber);
        const completed = await apiPost(
            `${apiBase}/complete`,
            { uploadId, key, s3UploadId, parts: completedParts },
            { fetchImpl }
        ).catch((err) => {
            throw tagError(err, 'complete', filename);
        });
        return { ...completed, filename: completed.filename || filename };
    } catch (err) {
        // Best-effort server-side cleanup; the bucket lifecycle rule is the
        // backstop for uploads orphaned by a closed browser.
        apiPost(`${apiBase}/abort`, { uploadId, key, s3UploadId }, { fetchImpl }).catch(() => {});
        throw tagError(err, 'part', filename);
    }
}
