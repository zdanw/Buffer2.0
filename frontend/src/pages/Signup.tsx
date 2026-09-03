import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { register, setToken, setRefreshToken } from '../api/auth';
import {
  LIMITS,
  alertValidationErrors,
} from '@/lib/formValidation';
import { useI18n } from '@/i18n/useI18n';
import { useValidators } from '@/i18n/helpers';
import { toUserFacingMessage } from '@/lib/apiErrors';
import AuthLayout from '@/components/AuthLayout';
import FormLabel from '@/components/FormLabel';

export default function Signup() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const v = useValidators();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (
      alertValidationErrors([
        v.required(t('signup.username'), username),
        v.maxLen(t('signup.username'), username, LIMITS.username.max),
        v.required(t('signup.email'), email),
        v.required(t('signup.password'), password),
        v.minLen(t('signup.password'), password, LIMITS.password.min),
        v.maxLen(t('signup.password'), password, LIMITS.password.max),
      ])
    ) {
      return;
    }
    setLoading(true);

    try {
      const response = await register({
        username: username.trim(),
        email: email.trim(),
        password,
      });

      if (response?.access_token) {
        setToken(response.access_token);
        if (response.refresh_token) {
          setRefreshToken(response.refresh_token);
        }
        navigate('/studio', { replace: true });
      } else {
        setError(t('signup.responseError'));
      }
    } catch (err: unknown) {
      setError(toUserFacingMessage(err, t('signup.failed')));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title={t('signup.title')} subtitle={t('signup.subtitle')}>
      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm border border-red-100">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <FormLabel label={t('signup.username')} required htmlFor="signup-username" className="block text-sm font-medium text-ink-700 mb-1" />
          <input
            id="signup-username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            maxLength={LIMITS.username.max}
            className="w-full px-4 py-3 border border-canvas-border rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent transition-all"
            placeholder={t('placeholders.signup.username')}
          />
        </div>

        <div>
          <FormLabel label={t('signup.email')} required htmlFor="signup-email" className="block text-sm font-medium text-ink-700 mb-1" />
          <input
            id="signup-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full px-4 py-3 border border-canvas-border rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent transition-all"
            placeholder={t('placeholders.signup.email')}
          />
        </div>

        <div>
          <FormLabel label={t('signup.password')} required htmlFor="signup-password" className="block text-sm font-medium text-ink-700 mb-1" />
          <input
            id="signup-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={LIMITS.password.min}
            maxLength={LIMITS.password.max}
            className="w-full px-4 py-3 border border-canvas-border rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent transition-all"
            placeholder={t('placeholders.signup.password')}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-forge-600 text-white font-semibold rounded-lg hover:bg-forge-700 focus:ring-4 focus:ring-forge-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? t('signup.submitting') : t('signup.submit')}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-500">
        {t('signup.hasAccount')}{' '}
        <Link to="/login" className="font-medium text-forge-600 hover:text-forge-700">
          {t('signup.signInLink')}
        </Link>
      </p>
    </AuthLayout>
  );
}
