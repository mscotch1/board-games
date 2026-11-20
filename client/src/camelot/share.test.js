import { describe, expect, it, vi } from 'vitest';
import { canShare, shareInvite } from './share.js';

const data = { title: 'Camelot', text: 'Join me', url: 'https://example.test/g/x' };

describe('canShare', () => {
  it('is false without the Web Share API', () => {
    expect(canShare({}, data)).toBe(false);
    expect(canShare(undefined, data)).toBe(false);
  });
  it('is true when share exists and canShare is absent', () => {
    expect(canShare({ share: () => {} }, data)).toBe(true);
  });
  it('asks canShare when it exists', () => {
    expect(canShare({ share: () => {}, canShare: () => false }, data)).toBe(false);
    expect(canShare({ share: () => {}, canShare: () => true }, data)).toBe(true);
  });
});

describe('shareInvite', () => {
  it('passes the data on', async () => {
    const share = vi.fn().mockResolvedValue();
    expect(await shareInvite({ share }, data)).toBe('shared');
    expect(share).toHaveBeenCalledWith(data);
  });
  it('treats closing the sheet as a cancel, not a failure', async () => {
    const share = vi.fn().mockRejectedValue(Object.assign(new Error('x'), { name: 'AbortError' }));
    expect(await shareInvite({ share }, data)).toBe('cancelled');
  });
  it('reports other errors', async () => {
    expect(await shareInvite({ share: () => Promise.reject(new Error('no')) }, data)).toBe('failed');
  });
});
