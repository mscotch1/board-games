/**
 * The code for the next game between the same two players. Both clients work
 * it out the same way, so they meet in a fresh room instead of the old one
 * (which the server may not have noticed closing yet).
 */
export function rematchCode(code) {
  const match = /^(.*)-r(\d+)$/.exec(code);
  return match ? `${match[1]}-r${Number(match[2]) + 1}` : `${code}-r1`;
}
