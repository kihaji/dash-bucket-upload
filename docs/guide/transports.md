# Choosing a transport

Every upload config has a `mode`. It decides how file parts travel to the
bucket. Callback code, keys and outputs are identical in both modes, so you can
switch later without touching your callbacks.

| | `mode='direct'` | `mode='relay'` |
|---|---|---|
| Data path | browser → bucket | browser → Dash server → bucket |
| Dash server load | metadata requests only | streams every byte (bounded memory) |
| Browser must reach the bucket | yes | no |
| Bucket CORS required | yes | no |
| Reverse-proxy body limits matter | no | yes, per part |
| Best for | the biggest files, many concurrent users | locked-down networks, stores without CORS control |

Both modes use S3 multipart uploads and never hold a whole file in memory, on
either side.

## Direct mode

```python
mgr = BucketUploadManager(app, ..., mode = 'direct')
```

1. The browser asks the Dash server to start an upload (`/create`).
2. The server returns presigned URLs for batches of parts (`/sign-parts`).
3. The browser PUTs each part straight to the bucket.
4. The server completes the multipart upload (`/complete`).

The bucket credentials never leave the server; the browser only ever sees
short-lived presigned URLs (`presign_expiration`, default one hour). If a URL
expires mid-upload, the engine requests a fresh one and retries.

!!! note "`/create` still runs on the server"
    Even in direct mode, starting and completing the upload are server-side
    calls. The Dash server must be able to reach the bucket in both modes; direct
    mode additionally needs the *browser* to reach it.

### Bucket CORS

Because the browser talks to the bucket from your app's origin, the bucket must
allow cross-origin PUTs **and expose the `ETag` response header**. Without the
exposed header the browser can upload parts but cannot read their ETags, so the
upload can never be completed. The widget detects this and reports a targeted
error.

=== "AWS S3"

    `aws s3api put-bucket-cors --bucket uploads --cors-configuration file://cors.json`

    ```json
    {
      "CORSRules": [{
        "AllowedOrigins": ["https://your-app.example.com"],
        "AllowedMethods": ["PUT", "GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3600
      }]
    }
    ```

=== "MinIO"

    `mc cors set local/uploads cors.xml`

    ```xml
    <CORSConfiguration>
      <CORSRule>
        <AllowedOrigin>https://your-app.example.com</AllowedOrigin>
        <AllowedMethod>PUT</AllowedMethod>
        <AllowedMethod>GET</AllowedMethod>
        <AllowedMethod>HEAD</AllowedMethod>
        <AllowedHeader>*</AllowedHeader>
        <ExposeHeader>ETag</ExposeHeader>
        <MaxAgeSeconds>3600</MaxAgeSeconds>
      </CORSRule>
    </CORSConfiguration>
    ```

=== "Swift (s3api)"

    CORS lives on the container:

    ```bash
    swift post uploads \
      -H 'X-Container-Meta-Access-Control-Allow-Origin: https://your-app.example.com' \
      -H 'X-Container-Meta-Access-Control-Expose-Headers: etag'
    ```

=== "Ceph RGW"

    RGW accepts the same S3 CORS document as AWS:

    ```bash
    aws s3api put-bucket-cors --endpoint-url https://rgw.example.com \
      --bucket uploads --cors-configuration file://cors.json
    ```

## Relay mode

```python
mgr = BucketUploadManager(app, ..., mode = 'relay')
```

The browser PUTs each part to the Dash server's `/part` route, which streams it
into a bounded spool (8 MiB in memory, then a temporary file) and forwards it
to the bucket. The browser never contacts the bucket, so no CORS configuration
is needed and the bucket can sit on a private network.

The trade-off is that every byte passes through your Dash workers:

- Each in-flight part occupies a worker for as long as it takes to receive and
  forward it. Size your worker count and timeouts accordingly (see
  [Production deployment](production.md)).
- Each part is one HTTP request of up to the part size (16 MiB by default,
  larger for very large files). Reverse proxies must accept bodies that large.

## Mixing modes

Mode is per upload config, so one app can use both:

```python
mgr = BucketUploadManager(app, ..., bucket = 'uploads', mode = 'direct')
mgr.register('internal', bucket = 'private-data', mode = 'relay')

BucketUpload(id = 'public', manager = mgr)                          # direct
BucketUpload(id = 'internal', manager = mgr, upload_id = 'internal') # relay
```
