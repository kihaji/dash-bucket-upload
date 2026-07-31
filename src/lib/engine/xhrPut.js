/**
 * Promise-wrapped XMLHttpRequest PUT.
 *
 * XHR (not fetch) because upload progress events are required — fetch upload
 * streaming lacks progress and is not universally available.
 *
 * Resolves {status, etag, responseText} on 2xx. Rejects with an Error carrying
 * {status, isAbort, isNetworkError, responseText} otherwise. Cancellation via
 * an AbortSignal: aborting rejects with {isAbort: true}.
 */
export function xhrPut(url, body, { headers = {}, onProgress, signal } = {}) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        const fail = (message, extra) => {
            const err = new Error(message);
            Object.assign(err, { status: xhr.status || 0, responseText: xhr.responseText || '', ...extra });
            reject(err);
        };

        if (signal) {
            if (signal.aborted) {
                const err = new Error('upload aborted');
                err.isAbort = true;
                reject(err);
                return;
            }
            signal.addEventListener('abort', () => xhr.abort(), { once: true });
        }

        xhr.open('PUT', url);
        Object.entries(headers).forEach(([name, value]) => xhr.setRequestHeader(name, value));

        if (xhr.upload && onProgress) {
            xhr.upload.onprogress = (e) => onProgress(e.loaded, e.total);
        }

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                resolve({
                    status: xhr.status,
                    etag: xhr.getResponseHeader('ETag'),
                    responseText: xhr.responseText,
                });
            } else {
                fail(`PUT failed with status ${xhr.status}`);
            }
        };
        xhr.onerror = () => fail('network error during PUT', { isNetworkError: true });
        xhr.onabort = () => fail('upload aborted', { isAbort: true });
        xhr.ontimeout = () => fail('PUT timed out', { isNetworkError: true });

        xhr.send(body);
    });
}
