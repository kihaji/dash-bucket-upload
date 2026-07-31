const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];

export function humanBytes(bytes) {
    if (bytes === null || bytes === undefined || Number.isNaN(bytes)) {
        return '';
    }
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < UNITS.length - 1) {
        value /= 1024;
        unit += 1;
    }
    const digits = value >= 100 || unit === 0 ? 0 : 1;
    return `${value.toFixed(digits)} ${UNITS[unit]}`;
}

export function humanSpeed(bytesPerSecond) {
    if (!bytesPerSecond || bytesPerSecond <= 0) {
        return '';
    }
    return `${humanBytes(bytesPerSecond)}/s`;
}
