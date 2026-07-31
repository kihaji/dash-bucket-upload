import { describe, expect, it } from 'vitest';
import { createSpeedEstimator } from '../speed';

describe('createSpeedEstimator', () => {
    it('converges toward a steady transfer rate', () => {
        const est = createSpeedEstimator(3000);
        let speed = 0;
        // 1 MB every 100 ms = 10 MB/s
        for (let t = 0; t <= 10000; t += 100) {
            speed = est.update((t / 100) * 1_000_000, t);
        }
        expect(speed).toBeGreaterThan(9_000_000);
        expect(speed).toBeLessThan(11_000_000);
    });

    it('returns 0 before two samples exist', () => {
        const est = createSpeedEstimator();
        expect(est.update(1000, 0)).toBe(0);
    });

    it('ignores backwards progress (failed part rollback)', () => {
        const est = createSpeedEstimator(1000);
        est.update(0, 0);
        const before = est.update(10_000_000, 1000);
        const after = est.update(2_000_000, 1100);
        expect(after).toBe(before);
    });

    it('decays during a stall', () => {
        const est = createSpeedEstimator(1000);
        est.update(0, 0);
        const fast = est.update(10_000_000, 1000);
        const stalled = est.update(10_000_000, 5000);
        expect(stalled).toBeLessThan(fast);
    });
});
