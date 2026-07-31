// Default inline styles mimicking the classic dcc.Upload look. Inline (not a
// CSS file) so the widget ships zero external assets — airgap-safe by
// construction — and so user `style` props merge predictably.

export const dropZone = {
    width: '100%',
    minHeight: '60px',
    lineHeight: '60px',
    borderWidth: '1px',
    borderStyle: 'dashed',
    borderColor: '#c0c4cc',
    borderRadius: '5px',
    textAlign: 'center',
    cursor: 'pointer',
    boxSizing: 'border-box',
    color: '#555',
    fontFamily: 'inherit',
    userSelect: 'none',
};

export const dropZoneActive = {
    borderColor: '#1975fa',
    backgroundColor: 'rgba(25, 117, 250, 0.06)',
};

export const dropZoneDisabled = {
    cursor: 'not-allowed',
    opacity: 0.5,
};

export const fileList = {
    listStyle: 'none',
    margin: '8px 0 0 0',
    padding: 0,
    fontFamily: 'inherit',
    fontSize: '14px',
    color: '#333',
};

export const fileRow = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px 2px',
    lineHeight: '20px',
};

export const fileName = {
    flex: '0 1 auto',
    minWidth: '80px',
    maxWidth: '45%',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
};

export const fileMeta = {
    flex: '0 0 auto',
    color: '#888',
    fontSize: '12px',
    whiteSpace: 'nowrap',
};

export const progressTrack = {
    flex: '1 1 auto',
    height: '8px',
    backgroundColor: '#e8eaef',
    borderRadius: '4px',
    overflow: 'hidden',
};

export const progressFill = {
    height: '100%',
    backgroundColor: '#1975fa',
    borderRadius: '4px',
    transition: 'width 0.2s ease',
};

export const progressFillError = {
    backgroundColor: '#d9534f',
};

export const progressFillDone = {
    backgroundColor: '#5cb85c',
};

export const cancelButton = {
    flex: '0 0 auto',
    border: 'none',
    background: 'none',
    color: '#888',
    cursor: 'pointer',
    fontSize: '16px',
    lineHeight: '16px',
    padding: '0 4px',
};

export const errorText = {
    color: '#d9534f',
    fontSize: '12px',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    maxWidth: '40%',
};
