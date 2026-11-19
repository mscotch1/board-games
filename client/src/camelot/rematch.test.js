import { expect, it } from 'vitest';
import { rematchCode } from './rematch.js';

it('adds a rematch number to a fresh code', () => {
  expect(rematchCode('3518f4ab')).toBe('3518f4ab-r1');
});

it('counts up on later rematches', () => {
  expect(rematchCode('3518f4ab-r1')).toBe('3518f4ab-r2');
  expect(rematchCode('3518f4ab-r9')).toBe('3518f4ab-r10');
});

it('leaves codes that merely look similar alone', () => {
  expect(rematchCode('x-ry')).toBe('x-ry-r1');
  expect(rematchCode('r1')).toBe('r1-r1');
});

it('gives both players the same code', () => {
  expect(rematchCode(rematchCode('abc'))).toBe(rematchCode(rematchCode('abc')));
});
