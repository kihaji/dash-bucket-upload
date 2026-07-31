import React from 'react';
import PropTypes from 'prop-types';
import { humanBytes, humanSpeed } from '../utils/format';
import * as styles from './styles';

const STATUS_ICONS = {
    done: '✓',
    error: '⚠',
    canceled: '✖',
};

const FileRow = ({ entry, onCancel }) => {
    const { fileId, filename, size, percent, speedBps, status, error } = entry;
    const active = status === 'pending' || status === 'uploading';

    const fillStyle = {
        ...styles.progressFill,
        width: `${status === 'done' ? 100 : percent}%`,
        ...(status === 'error' || status === 'canceled' ? styles.progressFillError : {}),
        ...(status === 'done' ? styles.progressFillDone : {}),
    };

    return (
        <li style={styles.fileRow}>
            <span style={styles.fileName} title={filename}>{filename}</span>
            <span style={styles.fileMeta}>{humanBytes(size)}</span>
            <span style={styles.progressTrack}>
                <span style={{ ...fillStyle, display: 'block' }} />
            </span>
            {active && (
                <span style={styles.fileMeta}>
                    {percent}%{speedBps > 0 ? ` · ${humanSpeed(speedBps)}` : ''}
                </span>
            )}
            {!active && <span style={styles.fileMeta}>{STATUS_ICONS[status] || ''}</span>}
            {status === 'error' && <span style={styles.errorText} title={error}>{error}</span>}
            {active && (
                <button
                    type="button"
                    style={styles.cancelButton}
                    title="Cancel upload"
                    onClick={(e) => {
                        e.stopPropagation();
                        onCancel(fileId);
                    }}
                >
                    {'×'}
                </button>
            )}
        </li>
    );
};

FileRow.propTypes = {
    entry: PropTypes.shape({
        fileId: PropTypes.string,
        filename: PropTypes.string,
        size: PropTypes.number,
        percent: PropTypes.number,
        speedBps: PropTypes.number,
        status: PropTypes.string,
        error: PropTypes.string,
    }).isRequired,
    onCancel: PropTypes.func.isRequired,
};

export default FileRow;
