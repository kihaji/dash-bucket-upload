# HTTP routes

`BucketUploadManager` registers five routes under `url_prefix` (default
`/dash-bucket-upload`). The component is their only intended client, but they
are documented here for debugging, proxy configuration and custom clients.

Every route runs `auth_check` first. Every request after `/create` names its
config (`uploadId`) and object `key`, and the key is checked against that
config's `<prefix>/<uuid4>/<filename>` pattern. The server keeps no other state
between requests.

## `POST /create`

Validates the file and starts a multipart upload. Both modes.

```json title="Request"
{"uploadId": "default", "filename": "data.csv", "size": 104857600, "contentType": "text/csv"}
```

```json title="Response 200"
{
  "bucket": "uploads",
  "key": "incoming/0b8f5c2e-6a51-4d47-8e0c-5f1f9d1f3a77/data.csv",
  "s3UploadId": "2~kHn...",
  "partSize": 16777216,
  "mode": "direct"
}
```

`mode` comes from the server's config. The browser follows it, so changing a
config's mode needs no client change.

## `POST /sign-parts`

Returns presigned part URLs. Direct mode only.

```json title="Request"
{"uploadId": "default", "key": "incoming/0b8f.../data.csv", "s3UploadId": "2~kHn...", "partNumbers": [1, 2, 3]}
```

```json title="Response 200"
{"urls": {"1": "https://...", "2": "https://...", "3": "https://..."}}
```

At most 100 part numbers per request, each between 1 and 10,000. The component
asks for 25 at a time.

## `PUT /part`

Receives one part and streams it to the bucket. Relay mode only.

```text title="Request"
PUT /dash-bucket-upload/part?uploadId=default&key=incoming%2F0b8f...%2Fdata.csv&s3UploadId=2~kHn...&partNumber=1
Content-Type: application/octet-stream

<part bytes>
```

```json title="Response 200"
{"partNumber": 1, "etag": "\"5d41402abc4b2a76b9719d911017c592\""}
```

The body may be at most the part size plus 1 MiB (5 GiB plus 1 MiB when the
size is automatic).

## `POST /complete`

Completes the multipart upload and reads the final size back from the bucket.

```json title="Request"
{
  "uploadId": "default",
  "key": "incoming/0b8f.../data.csv",
  "s3UploadId": "2~kHn...",
  "parts": [{"partNumber": 1, "etag": "\"5d41...\""}, {"partNumber": 2, "etag": "\"7d79...\""}]
}
```

```json title="Response 200"
{"bucket": "uploads", "key": "incoming/0b8f.../data.csv", "filename": "data.csv", "size": 104857600, "etag": "\"a1b2...-2\""}
```

## `POST /abort`

Aborts the multipart upload and discards its parts.

```json title="Request"
{"uploadId": "default", "key": "incoming/0b8f.../data.csv", "s3UploadId": "2~kHn..."}
```

```json title="Response 200"
{"aborted": true}
```

## Errors

Every error is JSON of the form `{"error": "<message>"}`. The component shows
the message in `lastError`. An error without a JSON body came from something
in front of the Dash app, such as a reverse proxy.

| Status | Message | Cause |
|---|---|---|
| 400 | `request body must be a JSON object` | Missing or malformed JSON body |
| 400 | `uploadId is required`, `s3UploadId is required` | Missing field |
| 400 | `filename is required`, `invalid filename`, `filename too long` | Filename failed sanitizing |
| 400 | `size must be a non-negative integer` | Bad `size` |
| 400 | `file extension .x is not allowed` | `allowed_extensions` |
| 400 | `content type x is not allowed` | `allowed_mime_types` |
| 400 | `partNumbers must be a list of 1-100 part numbers in [1, 10000]` | Bad `/sign-parts` request |
| 400 | `partNumber must be an integer`, `partNumber must be in [1, 10000]` | Bad `/part` request |
| 400 | `parts must be a non-empty list of {partNumber, etag}` | Bad `/complete` request |
| 403 | `not authorized` | `auth_check` returned `False` |
| 403 | `key does not belong to this upload configuration` | Key doesn't match the config's pattern |
| 403 | `sign-parts is only available in direct mode` | Config is in relay mode |
| 403 | `part upload is only available in relay mode` | Config is in direct mode |
| 404 | `unknown uploadId 'x'` | No config with that name in this process |
| 413 | `file exceeds the maximum size of N bytes` | `max_file_size` |
| 413 | `part exceeds the maximum part size` | Relay part body too large |
| 502 | `bucket operation failed: <Code>` | The store returned an error (`AccessDenied`, `NoSuchBucket`, …) |
| 502 | `bucket request failed: <ExceptionName>` | Connection, TLS or credential failure before the store answered |
| 504 | `bucket request failed: ConnectTimeoutError` or `ReadTimeoutError` | The store didn't answer in time |

For 502 and 504 the server logs the full underlying message; see
[Troubleshooting](../guide/troubleshooting.md#502-or-504-from-create).

## Retries

The component retries with exponential backoff and jitter (1 s, 2 s, 4 s, …,
capped at 15 s):

- **JSON routes** (`/create`, `/sign-parts`, `/complete`, `/abort`): up to 3
  attempts, for network errors, 429 and 5xx only. A 4xx fails immediately.
- **Part uploads**: up to 4 attempts per part, for any failure except a
  cancellation or the missing-ETag CORS error. In direct mode, a 403 also
  refreshes the presigned URL once within the attempt.
