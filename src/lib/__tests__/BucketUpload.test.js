// @vitest-environment jsdom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BucketUpload from '../components/BucketUpload.react';
import { createUploadEngine } from '../engine/uploadEngine';

// Each created engine is a controllable fake: tests fire its events directly.
vi.mock('../engine/uploadEngine', () => ({ createUploadEngine: vi.fn() }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let engines;
let container;
let root;

beforeEach(() => {
    engines = [];
    createUploadEngine.mockImplementation((opts) => {
        const engine = {
            opts,
            uploading: false,
            emit: (type, payload) => opts.onEvent(type, payload),
            addFiles: vi.fn(),
            cancelFile: vi.fn(),
            cancelAll: vi.fn(),
            isUploading: () => engine.uploading,
        };
        engines.push(engine);
        return engine;
    });
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(() => {
    act(() => root.unmount());
    container.remove();
    createUploadEngine.mockReset();
});

const render = (props) => act(() => root.render(<BucketUpload id="up" {...props} />));

const fileState = (status) => ({
    f1: { filename: 'a.bin', size: 10, loaded: 10, percent: 100, speedBps: 0, status },
});
const doneResult = { bucket: 'b', key: 'p/u/a.bin', filename: 'a.bin', size: 10, etag: '"e"', status: 'done' };

function uploadOneFile(engine) {
    act(() => {
        engine.emit('file-settled', { files: fileState('done') });
        engine.emit('batch-settled', { files: fileState('done'), results: [doneResult], failed: [] });
    });
}

describe('BucketUpload resetKey', () => {
    it('does not reset on mount', () => {
        const setProps = vi.fn();
        render({ setProps, resetKey: 'initial' });
        expect(setProps).not.toHaveBeenCalled();
    });

    it('clears the file list and output props when resetKey changes', () => {
        const setProps = vi.fn();
        render({ setProps });
        uploadOneFile(engines[0]);
        expect(container.textContent).toContain('a.bin');
        expect(setProps).toHaveBeenCalledWith(expect.objectContaining({ uploadedFiles: [doneResult] }));

        setProps.mockClear();
        render({ setProps, resetKey: 'r1' });

        expect(container.textContent).not.toContain('a.bin');
        expect(setProps).toHaveBeenCalledWith({
            uploadedFiles: null,
            lastUploadedBatch: null,
            progress: null,
            isUploading: false,
            lastError: null,
        });
    });

    it('starts uploadedFiles afresh after a reset', () => {
        const setProps = vi.fn();
        render({ setProps });
        uploadOneFile(engines[0]);
        render({ setProps, resetKey: 'r1' });

        setProps.mockClear();
        uploadOneFile(engines[1]);
        expect(setProps).toHaveBeenCalledWith(expect.objectContaining({ uploadedFiles: [doneResult] }));
    });

    it('cancels in-flight uploads and ignores the old engine afterwards', () => {
        const setProps = vi.fn();
        render({ setProps });
        const old = engines[0];
        old.uploading = true;
        act(() => old.emit('progress', { files: fileState('uploading') }));

        render({ setProps, resetKey: 'r1' });
        expect(old.cancelAll).toHaveBeenCalled();
        expect(engines).toHaveLength(2);

        // The cancellation's settle events arrive after the reset; they must
        // not bring the cleared rows or outputs back.
        setProps.mockClear();
        act(() => {
            old.emit('file-settled', { files: fileState('canceled') });
            old.emit('batch-settled', { files: fileState('canceled'), results: [], failed: [] });
        });
        expect(setProps).not.toHaveBeenCalled();
        expect(container.textContent).not.toContain('a.bin');
    });

    it('still applies a replaced engine\'s events after a config change (no reset)', () => {
        const setProps = vi.fn();
        render({ setProps });
        const old = engines[0];
        old.uploading = true;
        act(() => old.emit('progress', { files: fileState('uploading') }));

        render({ setProps, uploadId: 'other' });
        expect(old.cancelAll).toHaveBeenCalled();
        expect(container.querySelector('button[title="Cancel upload"]')).not.toBeNull();
        act(() => old.emit('file-settled', { files: fileState('canceled') }));
        expect(container.textContent).toContain('✖'); // the row settled as canceled
        expect(container.querySelector('button[title="Cancel upload"]')).toBeNull();
    });

    it('resets again for each new resetKey value', () => {
        const setProps = vi.fn();
        render({ setProps, resetKey: 'r1' });
        render({ setProps, resetKey: 'r2' });
        render({ setProps, resetKey: 'r2' });
        const resets = setProps.mock.calls.filter(([props]) => props.lastUploadedBatch === null);
        expect(resets).toHaveLength(1);
        render({ setProps, resetKey: 'r3' });
        expect(setProps.mock.calls.filter(([props]) => props.lastUploadedBatch === null)).toHaveLength(2);
    });

    it('cancels in-flight uploads on unmount', () => {
        render({ setProps: vi.fn() });
        act(() => root.unmount());
        expect(engines[0].cancelAll).toHaveBeenCalled();
        root = createRoot(container); // afterEach unmounts again
    });
});
