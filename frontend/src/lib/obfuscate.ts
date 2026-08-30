/**
 * Route ID obfuscation — encodes numeric IDs into short
 * alphanumeric strings so URLs aren't trivially guessable.
 *
 * NOT cryptographically secure — this is obscurity, not auth.
 * Backend authorization still enforces access control.
 *
 * 1    → "1k"
 * 42   → "a2"
 * 999  → "g27"
 * 1234 → "q4y"
 */

const CHARSET = 'abcdefghijklmnopqrstuvwxyz0123456789';
const BASE = CHARSET.length; // 36

/** Encode a positive integer to a short alphanumeric string. */
export function encodeId(id: number | string): string {
  const n = typeof id === 'string' ? parseInt(id, 10) : id;
  if (!Number.isFinite(n) || n < 0) return String(id);

  if (n === 0) return '0';

  let result = '';
  let val = n;
  while (val > 0) {
    result = CHARSET[val % BASE] + result;
    val = Math.floor(val / BASE);
  }

  // Prefix with length digit to avoid leading-zero ambiguity
  return result.length.toString(BASE) + result;
}

/** Decode an obfuscated string back to the original numeric ID. */
export function decodeId(encoded: string): number | null {
  if (!encoded || typeof encoded !== 'string') return null;

  // Prefer the obfuscated interpretation — it is the exact inverse of
  // encodeId, and some encodings are pure digits (e.g. id 32 → "16"), which
  // a naive "is this a plain number?" check would misread.
  const len = parseInt(encoded[0], BASE);
  if (Number.isFinite(len) && len > 0) {
    const body = encoded.slice(1);
    if (body.length === len) {
      let result = 0;
      let valid = true;
      for (const ch of body) {
        const digit = CHARSET.indexOf(ch);
        if (digit === -1) {
          valid = false;
          break;
        }
        result = result * BASE + digit;
      }
      if (valid) return result;
    }
  }

  // Already a plain number? (backward compat with legacy numeric URLs)
  const plain = parseInt(encoded, 10);
  if (!isNaN(plain) && String(plain) === encoded) return plain;

  return null;
}
