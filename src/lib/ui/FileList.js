import React from 'react';
import PropTypes from 'prop-types';
import FileRow from './FileRow';
import * as styles from './styles';

const FileList = ({ files, onCancel }) => {
    const entries = Object.values(files);
    if (entries.length === 0) {
        return null;
    }
    return (
        <ul style={styles.fileList}>
            {entries.map((entry) => (
                <FileRow key={entry.fileId} entry={entry} onCancel={onCancel} />
            ))}
        </ul>
    );
};

FileList.propTypes = {
    files: PropTypes.object.isRequired,
    onCancel: PropTypes.func.isRequired,
};

export default FileList;
