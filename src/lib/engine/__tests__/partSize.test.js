import { describe, expect, it } from 'vitest';
import { MiB, DEFAULT_MIN_PART, MAX_PART, TARGET_MAX_PARTS, computePartSize, buildParts } from '../partSize';

const GiB = 1024 * MiB;

describe('computePartSize', () => {
    it('uses the 16 MiB floor for small files', () => {
        expect(computePartSize(0)).toBe(DEFAULT_MIN_PART);
        expect(computePartSize(MiB)).toBe(DEFAULT_MIN_PART);
        expect(computePartSize(10 * GiB)).toBe(DEFAULT_MIN_PART);
    });

    it('keeps huge files under the S3 part cap', () => {
        for (const size of [200 * GiB, 1024 * GiB, 5 * 1024 * GiB]) {
            const part = computePartSize(size);
            expect(size / part).toBeLessThanOrEqual(TARGET_MAX_PARTS);
            expect(part % MiB).toBe(0);
            expect(part).toBeLessThanOrEqual(MAX_PART);
        }
    });

    it('honors the server override', () => {
        expect(computePartSize(10 * GiB, 32 * MiB)).toBe(32 * MiB);
    });
});

describe('buildParts', () => {
    it('splits a file into 1-based parts covering every byte', () => {
        const parts = buildParts(12, 5);
        expect(parts).toEqual([
            { partNumber: 1, start: 0, end: 5, size: 5 },
            { partNumber: 2, start: 5, end: 10, size: 5 },
            { partNumber: 3, start: 10, end: 12, size: 2 },
        ]);
    });

    it('gives a zero-byte file one empty part so multipart can complete', () => {
        expect(buildParts(0, 5)).toEqual([{ partNumber: 1, start: 0, end: 0, size: 0 }]);
    });

    it('handles an exact multiple without an empty tail part', () => {
        expect(buildParts(10, 5)).toHaveLength(2);
    });
});
