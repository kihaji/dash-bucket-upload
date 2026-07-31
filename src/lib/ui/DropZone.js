import React, { useRef, useState } from 'react';
import PropTypes from 'prop-types';
import * as styles from './styles';

/**
 * dcc.Upload-style drop zone: dashed border, click-to-pick via a hidden
 * <input type="file">, drag-and-drop with an active highlight.
 */
const DropZone = ({
    multiple,
    accept,
    disabled,
    style,
    className,
    styleActive,
    styleDisabled,
    children,
    onFiles,
}) => {
    const inputRef = useRef(null);
    const [dragActive, setDragActive] = useState(false);
    // Drag events fire on children too; count enters/leaves so the highlight
    // only clears when the pointer truly leaves the zone.
    const dragDepth = useRef(0);

    const mergedStyle = {
        ...styles.dropZone,
        ...(style || {}),
        ...(dragActive && !disabled ? { ...styles.dropZoneActive, ...(styleActive || {}) } : {}),
        ...(disabled ? { ...styles.dropZoneDisabled, ...(styleDisabled || {}) } : {}),
    };

    const handleFiles = (fileList) => {
        if (disabled || !fileList || fileList.length === 0) {
            return;
        }
        let selected = [...fileList];
        if (!multiple) {
            selected = selected.slice(0, 1);
        }
        onFiles(selected);
    };

    return (
        <div
            style={mergedStyle}
            className={className}
            role="button"
            tabIndex={disabled ? -1 : 0}
            aria-disabled={disabled}
            onClick={() => {
                if (!disabled && inputRef.current) {
                    inputRef.current.click();
                }
            }}
            onKeyDown={(e) => {
                if (!disabled && (e.key === 'Enter' || e.key === ' ') && inputRef.current) {
                    e.preventDefault();
                    inputRef.current.click();
                }
            }}
            onDragEnter={(e) => {
                e.preventDefault();
                dragDepth.current += 1;
                setDragActive(true);
            }}
            onDragOver={(e) => e.preventDefault()}
            onDragLeave={(e) => {
                e.preventDefault();
                dragDepth.current -= 1;
                if (dragDepth.current <= 0) {
                    dragDepth.current = 0;
                    setDragActive(false);
                }
            }}
            onDrop={(e) => {
                e.preventDefault();
                dragDepth.current = 0;
                setDragActive(false);
                handleFiles(e.dataTransfer.files);
            }}
        >
            {children || (
                <span>
                    {'Drag and Drop or '}
                    <a style={{ textDecoration: 'underline', color: 'inherit' }}>Select Files</a>
                </span>
            )}
            <input
                ref={inputRef}
                type="file"
                multiple={multiple}
                accept={accept || undefined}
                disabled={disabled}
                style={{ display: 'none' }}
                onChange={(e) => {
                    handleFiles(e.target.files);
                    // Allow re-selecting the same file.
                    e.target.value = '';
                }}
            />
        </div>
    );
};

DropZone.propTypes = {
    multiple: PropTypes.bool,
    accept: PropTypes.string,
    disabled: PropTypes.bool,
    style: PropTypes.object,
    className: PropTypes.string,
    styleActive: PropTypes.object,
    styleDisabled: PropTypes.object,
    children: PropTypes.node,
    onFiles: PropTypes.func.isRequired,
};

export default DropZone;
