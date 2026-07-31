export const MiB = 1024 * 1024;
export const DEFAULT_MIN_PART = 16 * MiB;
// S3's per-part maximum. Blob.slice is a zero-copy view, so large parts do
// not load into browser memory.
export const MAX_PART = 5 * 1024 * MiB;
// S3 allows 10,000 parts; leave headroom so rounding never crosses the limit.
export const TARGET_MAX_PARTS = 9500;

/**
 * Choose a part size for a file. Mirrors the server-side computation in
 * dash_bucket_upload/_keys.py — the server's /create response is authoritative;
 * this exists as a documented fallback and a test target.
 */
export function computePartSize(fileSize, override = null) {
    if (override) {
        return override;
    }
    const needed = Math.ceil(fileSize / TARGET_MAX_PARTS);
    const roundedToMiB = Math.ceil(needed / MiB) * MiB;
    return Math.min(Math.max(roundedToMiB, DEFAULT_MIN_PART), MAX_PART);
}

/**
 * Split a file size into part descriptors: [{partNumber, start, end, size}].
 * partNumber is 1-based per the S3 multipart API. A zero-byte file still gets
 * one empty part so the multipart upload can complete.
 */
export function buildParts(fileSize, partSize) {
    const parts = [];
    if (fileSize === 0) {
        return [{ partNumber: 1, start: 0, end: 0, size: 0 }];
    }
    let start = 0;
    let partNumber = 1;
    while (start < fileSize) {
        const end = Math.min(start + partSize, fileSize);
        parts.push({ partNumber, start, end, size: end - start });
        start = end;
        partNumber += 1;
    }
    return parts;
}
