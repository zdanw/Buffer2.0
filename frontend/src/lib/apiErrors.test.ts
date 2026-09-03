import { describe, expect, it } from 'vitest';
import {
  isConnectionError,
  mapErrorCategory,
  sanitizeMessage,
  toUserFacingMessage,
} from './apiErrors';

const t = (key: string) => key;

describe('sanitizeMessage', () => {
  it('blocks developer script commands', () => {
    expect(sanitizeMessage('.\\scripts\\backend.ps1 start', 'fallback')).toBe('fallback');
  });

  it('blocks axios network noise', () => {
    expect(sanitizeMessage('Network Error', 'fallback')).toBe('fallback');
  });

  it('allows user-facing validation messages', () => {
    expect(sanitizeMessage('Brand slug already exists', 'fallback')).toBe('Brand slug already exists');
  });
});

describe('toUserFacingMessage', () => {
  it('maps connection errors to fallback', () => {
    const error = { message: 'Network Error' };
    expect(toUserFacingMessage(error, 'connection-fallback')).toBe('connection-fallback');
  });

  it('returns sanitized API detail when present', () => {
    const error = {
      response: { status: 400, data: { detail: 'Inactive user' } },
    };
    expect(toUserFacingMessage(error, 'fallback')).toBe('Inactive user');
  });
});

describe('isConnectionError', () => {
  it('detects gateway failures', () => {
    expect(isConnectionError({ response: { status: 503 } })).toBe(true);
  });
});

describe('mapErrorCategory', () => {
  it('maps known categories to i18n keys', () => {
    expect(mapErrorCategory('generate_task_failed', t, 'fallback')).toBe(
      'errors.categories.generateTaskFailed',
    );
  });

  it('uses fallback for unknown categories', () => {
    expect(mapErrorCategory('unknown_internal_code', t, 'fallback')).toBe('fallback');
  });
});
