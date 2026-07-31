import { apiPost } from '../api';
import { xhrPut } from '../xhrPut';

// How many presigned URLs to request ahead of the scheduler in one /sign-parts
// call. Server caps a batch at 100.
const SIGN_WINDOW = 25;

export const CORS_ETAG_HINT =
    'S3 did not expose the ETag response header to the browser. ' +
    'The bucket CORS configuration must include ExposeHeaders: ["ETag"] ' +
    'and allow the PUT method from this origin.';

/**
 * Direct-to-bucket transport: PUT each part to a presigned S3 URL.
 * Presigned URLs are fetched in batched windows ahead of demand; a 403 on a
 * part PUT (expired presign) refreshes that part's URL once per attempt.
 */
export function createDirectTransport({ apiBase, uploadId, key, s3UploadId, allPartNumbers, fetchImpl }) {
    const urlCache = new Map();
    let signInFlight = null;

    async function signWindow(neededPartNumber) {
        const missing = allPartNumbers.filter((n) => !urlCache.has(n));
        // Always include the part we need, then fill the window in order.
        const batch = [neededPartNumber, ...missing.filter((n) => n !== neededPartNumber)].slice(0, SIGN_WINDOW);
        const { urls } = await apiPost(
            `${apiBase}/sign-parts`,
            { uploadId, key, s3UploadId, partNumbers: batch },
            { fetchImpl }
        );
        Object.entries(urls).forEach(([partNumber, url]) => urlCache.set(Number(partNumber), url));
    }

    function startSign(partNumber) {
        const request = signWindow(partNumber).finally(() => {
            signInFlight = null;
        });
        signInFlight = request;
        return request;
    }

    async function urlFor(partNumber) {
        // Serialize sign requests so concurrent parts share one window fetch.
        while (!urlCache.has(partNumber)) {
            await (signInFlight || startSign(partNumber));
        }
        return urlCache.get(partNumber);
    }

    return {
        async uploadPart(part, blob, { onProgress, signal } = {}) {
            const url = await urlFor(part.partNumber);
            let result;
            try {
                result = await xhrPut(url, blob, { onProgress, signal });
            } catch (err) {
                if (err.status === 403) {
                    // Presigned URL likely expired — refresh and retry once
                    // within this attempt.
                    urlCache.delete(part.partNumber);
                    const freshUrl = await urlFor(part.partNumber);
                    result = await xhrPut(freshUrl, blob, { onProgress, signal });
                } else {
                    throw err;
                }
            }
            if (!result.etag) {
                const err = new Error(CORS_ETAG_HINT);
                err.isConfigError = true;
                throw err;
            }
            return { partNumber: part.partNumber, etag: result.etag };
        },
    };
}
