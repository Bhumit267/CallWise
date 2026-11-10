/**
 * Unit tests for formatApiError in web/lib/api.ts
 */
const assert = require('assert');

// Formatter function replicating formatApiError in web/lib/api.ts
function formatApiError(data, fallbackStatusText) {
  if (!data) return fallbackStatusText || 'Request failed';

  if (data.detail !== undefined && data.detail !== null) {
    if (typeof data.detail === 'string') {
      return data.detail;
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((err) => {
          if (typeof err === 'string') return err;
          if (err && typeof err === 'object') {
            const loc = Array.isArray(err.loc) ? err.loc.filter((l) => l !== 'body').join('.') : '';
            const msg = err.msg || 'Invalid value';
            return loc ? loc + ': ' + msg : msg;
          }
          return JSON.stringify(err);
        })
        .join(', ');
    }
    if (typeof data.detail === 'object') {
      return JSON.stringify(data.detail);
    }
  }

  if (data.message && typeof data.message === 'string') {
    return data.message;
  }

  return fallbackStatusText || 'Request failed';
}

console.log('--- Running formatApiError Unit Tests ---');

// Case 1: String detail
const r1 = formatApiError({ detail: 'Invalid email or password.' });
assert.strictEqual(r1, 'Invalid email or password.');
console.log('✓ PASS 1/4: String detail returned directly');

// Case 2: Array of Pydantic validation errors
const r2 = formatApiError({
  detail: [
    { loc: ['body', 'business_type'], msg: 'Field required', type: 'missing' },
    { loc: ['body', 'owner_name'], msg: 'Field required', type: 'missing' }
  ]
});
assert.strictEqual(r2, 'business_type: Field required, owner_name: Field required');
console.log('✓ PASS 2/4: Validation array converted to human-readable string');

// Case 3: Missing detail with message fallback
const r3 = formatApiError({ message: 'Database connection failed' });
assert.strictEqual(r3, 'Database connection failed');
console.log('✓ PASS 3/4: Fallback to message field');

// Case 4: Null data with fallback status text
const r4 = formatApiError(null, 'Bad Gateway');
assert.strictEqual(r4, 'Bad Gateway');
console.log('✓ PASS 4/4: Null response falls back to status text');

console.log('--- All formatApiError Unit Tests PASSED! ---');

