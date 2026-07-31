import React, { useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import DropZone from '../ui/DropZone';
import FileList from '../ui/FileList';
import { createUploadEngine } from '../engine/uploadEngine';

// Progress prop updates are throttled so multi-GB uploads don't flood the Dash
// renderer with setProps calls.
const PROGRESS_INTERVAL_MS = 250;

/**
 * BucketUpload: a dcc.Upload look-alike that stores files in an S3-compatible
 * bucket instead of pushing bytes through a Dash callback.
 *
 * Files upload either directly from the browser to the bucket (presigned
 * multipart URLs) or via a streaming relay route on the Dash server — the
 * server decides per upload_id. Either way, callbacks receive only the bucket
 * location metadata, never the file contents.
 */
const BucketUpload = ({
    id,
    apiPath = '/dash-bucket-upload',
    uploadId = 'default',
    multiple = true,
    accept = null,
    maxFileSize = null,
    disabled = false,
    maxConcurrency = 6,
    showFileList = true,
    style = null,
    className = null,
    styleActive = null,
    styleDisabled = null,
    children = null,
    setProps,
}) => {
    const [fileState, setFileState] = useState({});
    const uploadedRef = useRef([]);
    const throttleRef = useRef({ last: 0, timer: null });
    const setPropsRef = useRef(setProps);
    setPropsRef.current = setProps;

    const engine = useMemo(
        () => createUploadEngine({
            apiBase: apiPath,
            uploadId,
            maxConcurrency,
            maxFileSize,
            onEvent: (type, payload) => handleEvent(type, payload),
        }),
        [apiPath, uploadId, maxConcurrency, maxFileSize]
    );
    const engineRef = useRef(engine);
    engineRef.current = engine;

    useEffect(() => () => engineRef.current.cancelAll(), []);

    const pushProgress = (files, force) => {
        const apply = () => {
            setFileState(files);
            if (setPropsRef.current) {
                setPropsRef.current({
                    progress: files,
                    isUploading: engineRef.current.isUploading(),
                });
            }
        };
        const t = throttleRef.current;
        const now = Date.now();
        if (force || now - t.last >= PROGRESS_INTERVAL_MS) {
            if (t.timer) {
                clearTimeout(t.timer);
                t.timer = null;
            }
            t.last = now;
            apply();
        } else if (!t.timer) {
            t.timer = setTimeout(() => {
                t.timer = null;
                t.last = Date.now();
                apply();
            }, PROGRESS_INTERVAL_MS - (now - t.last));
        }
    };

    function handleEvent(type, payload) {
        const { files } = payload;
        if (type === 'progress') {
            pushProgress(files, false);
        } else if (type === 'file-settled') {
            pushProgress(files, true);
        } else if (type === 'batch-settled') {
            uploadedRef.current = [...uploadedRef.current, ...payload.results];
            const props = {
                uploadedFiles: uploadedRef.current,
                lastUploadedBatch: payload.results,
                isUploading: engineRef.current.isUploading(),
            };
            if (payload.failed && payload.failed.length > 0) {
                props.lastError = payload.failed[payload.failed.length - 1];
            }
            if (setPropsRef.current) {
                setPropsRef.current(props);
            }
            pushProgress(files, true);
        } else if (type === 'rejected') {
            if (setPropsRef.current && payload.rejected.length > 0) {
                setPropsRef.current({ lastError: payload.rejected[payload.rejected.length - 1] });
            }
        }
    }

    return (
        <div id={id}>
            <DropZone
                multiple={multiple}
                accept={accept}
                disabled={disabled}
                style={style}
                className={className}
                styleActive={styleActive}
                styleDisabled={styleDisabled}
                onFiles={(files) => engine.addFiles(files)}
            >
                {children}
            </DropZone>
            {showFileList && <FileList files={fileState} onCancel={(fileId) => engine.cancelFile(fileId)} />}
        </div>
    );
};

BucketUpload.propTypes = {
    /**
     * The ID used to identify this component in Dash callbacks.
     */
    id: PropTypes.string,

    /**
     * Base path of the server routes registered by BucketUploadManager.
     * Set automatically when the component is constructed with `manager=`.
     */
    apiPath: PropTypes.string,

    /**
     * Name of the server-side upload configuration to use (registered on the
     * BucketUploadManager). Links this widget to a bucket/prefix/mode.
     */
    uploadId: PropTypes.string,

    /**
     * Allow selecting/dropping more than one file at a time.
     */
    multiple: PropTypes.bool,

    /**
     * File-picker accept filter, e.g. ".csv,.parquet" or "image/*".
     */
    accept: PropTypes.string,

    /**
     * Client-side maximum file size in bytes. Files over the limit are
     * rejected before any upload starts (the server enforces its own limit
     * regardless).
     */
    maxFileSize: PropTypes.number,

    /**
     * Disable the drop zone and file picker.
     */
    disabled: PropTypes.bool,

    /**
     * Maximum number of part uploads in flight across all files.
     */
    maxConcurrency: PropTypes.number,

    /**
     * Show the built-in per-file progress list under the drop zone. Set false
     * to build custom progress UI from the `progress` prop.
     */
    showFileList: PropTypes.bool,

    /**
     * Style of the drop zone.
     */
    style: PropTypes.object,

    /**
     * CSS class of the drop zone.
     */
    className: PropTypes.string,

    /**
     * Additional style applied while files are dragged over the drop zone.
     */
    styleActive: PropTypes.object,

    /**
     * Additional style applied while the component is disabled.
     */
    styleDisabled: PropTypes.object,

    /**
     * Custom drop-zone content (replaces "Drag and Drop or Select Files").
     */
    children: PropTypes.node,

    /**
     * (Output) All files uploaded by this component instance, cumulative
     * across its lifetime. List of {bucket, key, filename, size, etag, status}.
     */
    uploadedFiles: PropTypes.arrayOf(PropTypes.object),

    /**
     * (Output) Files from the most recently completed drop/selection batch,
     * set once when every file in the batch has finished. The ergonomic
     * callback Input: fires exactly once per batch with only the new files.
     */
    lastUploadedBatch: PropTypes.arrayOf(PropTypes.object),

    /**
     * (Output) True while any file is uploading.
     */
    isUploading: PropTypes.bool,

    /**
     * (Output) Per-file upload progress keyed by an internal file id:
     * {filename, size, loaded, percent, speedBps, status}. Throttled to ~4
     * updates/second. Intended for custom progress UI, not as a general
     * callback trigger.
     */
    progress: PropTypes.object,

    /**
     * (Output) Most recent upload error: {filename, message, phase}.
     */
    lastError: PropTypes.object,

    /**
     * Dash-assigned callback for updating props.
     */
    setProps: PropTypes.func,
};

export default BucketUpload;
