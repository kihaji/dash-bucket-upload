# Troubleshooting

Start with two things:

1. **The failing request in the browser's developer tools** (Network tab). Find
   the request to `/dash-bucket-upload/...` or to the bucket, and look at its
   status code and response body.
2. **The Dash server's log.** Bucket failures are logged on the
   `dash_bucket_upload.manager` logger with the store's full error message.

The `lastError` prop's `phase` (`validate`, `create`, `part`, `complete`) tells
you which step failed.

## 502 or 504 from `/create`

**Symptom:** uploads fail immediately with `phase: 'create'`, and the
`/create` request returns 502 (sometimes 504). This happens in **both** direct
and relay mode, because `/create` is a server-side call from the Dash server to
the store in either mode.

There are two very different causes, and the response body tells them apart.

### The body is JSON: the store answered with an error

```json
{"error": "bucket operation failed: AccessDenied"}
```

The Dash server reached the store and the store refused. The server log has
the full message. Common codes:

| Code | Likely cause |
|---|---|
| `AccessDenied` | The credentials lack `s3:PutObject` on the bucket (multipart create needs it). Also check bucket policies, and `kms:GenerateDataKey` if the bucket uses SSE-KMS. |
| `NoSuchBucket` | Wrong bucket name, or the wrong `addressing_style` for the store. |
| `InvalidAccessKeyId`, `SignatureDoesNotMatch` | Wrong keys, or a proxy in front of the store rewrites the `Host` header. |
| `AuthorizationHeaderMalformed`, `PermanentRedirect` | On AWS, `region` doesn't match the bucket's region. |
| `RequestTimeTooSkewed` | The server's clock is off by more than 15 minutes. Run NTP. |

### The body is JSON: the store couldn't be reached

```json
{"error": "bucket request failed: EndpointConnectionError"}
```

The request never got a response from the store. The status is 504 for
timeouts and 502 otherwise.

| Name | Likely cause |
|---|---|
| `EndpointConnectionError` | Wrong `endpoint_url`, DNS failure, firewall, or the store is down. Test from the server host: `curl -I <endpoint_url>`. |
| `ConnectTimeoutError`, `ReadTimeoutError` | A firewall silently dropping packets, or an overloaded store. |
| `SSLError` | Certificate problem, often a private CA. See [TLS with a private CA](stores.md#tls-with-a-private-ca). |
| `NoCredentialsError` | No credentials were passed and boto3's chain found none (for example, no instance role on this host). |
| `ProxyConnectionError` | An outbound HTTP proxy configured through `HTTPS_PROXY` or `botocore_config` is unreachable. |

### The body is an HTML page: a proxy timed out

An HTML page saying **"Proxy Error"** (Apache) or **"502 Bad Gateway"** /
**"504 Gateway Time-out"** (nginx) means the library's handler never answered;
the reverse proxy in front of Dash gave up first. Usually the request was still
waiting on an unreachable store when the proxy's or gunicorn's timeout fired.
The browser retries `/create` up to 3 times, so the user may wait through
several of these.

To fix it:

1. Check the server log for a gunicorn `WORKER TIMEOUT` or a botocore
   connection traceback, and fix the connectivity problem it names.
2. Make the proxy's upstream timeout longer than the bucket client's worst
   case (about 18 seconds with the default [timeouts](stores.md#timeouts-and-retries)),
   so future failures come back as readable JSON.

!!! info "Versions before 0.1.1"
    Before 0.1.1, connection-level failures had no handler and the bucket client
    used botocore's default 60-second connect timeout with retries, so an
    unreachable store nearly always surfaced as a proxy 502. Upgrade to get
    JSON errors, server-side logging and the fast-failing client defaults.

## "S3 did not expose the ETag response header"

**Direct mode only.** Parts upload, but the browser can't read their ETags,
which are needed to complete the upload. Add `ExposeHeaders: ["ETag"]` to the
bucket's CORS rule and allow `PUT` from your app's origin. See
[Bucket CORS](transports.md#bucket-cors).

## "network error during PUT"

**Direct mode:** the browser couldn't talk to the bucket at all. Check the
browser console:

- **A CORS error:** the bucket has no CORS rule for your origin. See
  [Bucket CORS](transports.md#bucket-cors).
- **A DNS or connection error to a hostname like `minio` or `s3.internal`:**
  presigned URLs use the server's `endpoint_url`. If the Dash server reaches the
  store through an internal name (a Docker Compose service name, a cluster DNS
  name), the browser can't resolve it. Use an `endpoint_url` that both the
  server and browsers can reach, or switch to relay mode.
- **Mixed content:** an `https://` app can't PUT to an `http://` bucket. Serve
  the store over HTTPS, or use relay mode.

**Relay mode:** the connection to the Dash server dropped, often a proxy
closing a long request. Check proxy timeouts and body limits.

## Part uploads fail with 403 (direct mode)

The engine refreshes presigned URLs once on a 403, so a persistent 403 isn't
expiry. Usually the signature doesn't match what the store sees:

- A proxy in front of the store changes the `Host` header. With nginx, set
  `proxy_set_header Host $http_host;`.
- `region` differs from the store's configured region.
- The server's clock is wrong, so URLs are already expired when issued.

## Part uploads fail with 413 (relay mode)

The message reads `PUT failed with status 413`. A reverse proxy rejected a part
body larger than its limit. nginx's default `client_max_body_size` is only 1 MB.
Raise it above the part size; see [Reverse proxies](production.md#reverse-proxies).

## "key does not belong to this upload configuration" (403)

The routes check every key against `<prefix>/<uuid4>/<filename>` for the
config named in the request. This fails when:

- A custom `key_generator` produces keys of a different shape. See
  [Custom keys](multiple-widgets.md#custom-keys).
- The config's `prefix` changed while an upload was in flight, for example
  during a rolling deploy.
- Different workers or replicas have different configs. Every process must
  register the same configs.

## "unknown uploadId" (404)

The server process that handled the request has no config with that name. Make
sure `BucketUploadManager(...)` and every `register()` run at module import
time in every worker, **not** inside `if __name__ == '__main__':`. Gunicorn
imports your module and never runs that block.

## "not authorized" (403)

Your `auth_check` returned `False`. If it relies on a login session, make sure
the session cookie is sent on the upload routes (same origin, cookie path
covering `url_prefix`).

## Startup errors

`KeyError: no upload config named 'x' is registered on this manager`
:   A `BucketUpload(manager=mgr, upload_id='x')` was built before
    `mgr.register('x', ...)`. Register first. Without `bucket=` on the
    constructor there is no `'default'` config either.

`ValueError: The name 'dash_bucket_upload_...' is already registered for a different blueprint`
:   Two managers share a `url_prefix`. Give each its own. See
    [Several managers on one app](multiple-widgets.md#several-managers-on-one-app).

`AssertionError: The setup method 'register_blueprint' can no longer be called on the application`
:   The manager was created after the app served its first request, for
    example inside a callback or a lazily called factory. Create it at startup.

`ValueError: pass either access_key= or aws_access_key_id=, not both`
:   Use one spelling per parameter. See [Connection parameters](stores.md#connection-parameters).

## `EntityTooSmall` on `/complete`

A fixed `part_size` below 5 MiB. S3 requires every part except the last to be
at least 5 MiB. Remove `part_size` or raise it.

## Uploads finish but the callback doesn't fire

- The callback must use `lastUploadedBatch` or `uploadedFiles` as its `Input`.
  `progress` and `isUploading` change constantly; `lastUploadedBatch` changes
  once per batch.
- With `prevent_initial_call=False`, the callback also runs at page load with
  `None`. Guard with `if not batch`.
- If every file in the batch failed, `lastUploadedBatch` is `[]`. Check
  `lastError`.
