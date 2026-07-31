import { xhrPut } from '../xhrPut';

/**
 * Relay transport: PUT each part to the widget's Flask route, which streams it
 * into the bucket server-side. Same one-request-per-part shape as the direct
 * transport so the fileUpload state machine is transport-agnostic.
 */
export function createRelayTransport({ apiBase, uploadId, key, s3UploadId }) {
    return {
        async uploadPart(part, blob, { onProgress, signal } = {}) {
            const params = new URLSearchParams({
                uploadId,
                key,
                s3UploadId,
                partNumber: String(part.partNumber),
            });
            const result = await xhrPut(`${apiBase}/part?${params}`, blob, {
                headers: { 'Content-Type': 'application/octet-stream' },
                onProgress,
                signal,
            });
            const body = JSON.parse(result.responseText);
            return { partNumber: body.partNumber, etag: body.etag };
        },
    };
}
