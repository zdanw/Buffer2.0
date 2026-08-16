import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login, setToken, setRefreshToken } from '../api/auth';
import type { LoginData } from '../api/auth';
import {
  LIMITS,
  alertValidationErrors,
} from '@/lib/formValidation';
import { useI18n } from '@/i18n/useI18n';
import { useValidators } from '@/i18n/helpers';
import AuthLayout from '@/components/AuthLayout';

function Login() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const v = useValidators();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (
      alertValidationErrors([
        v.required(t('login.username'), username),
        v.maxLen(t('login.username'), username, LIMITS.username.max),
        v.required(t('login.password'), password),
        v.minLen(t('login.password'), password, LIMITS.password.min),
        v.maxLen(t('login.password'), password, LIMITS.password.max),
      ])
    ) {
      return;
    }
    setLoading(true);

    try {
      const data: LoginData = { username, password };
      const response = await login(data);

      if (response && response.access_token) {
        setToken(response.access_token);
        if (response.refresh_token) {
          setRefreshToken(response.refresh_token);
        }
        navigate('/products', { replace: true });
      } else {
        setError(t('login.responseError'));
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string | Array<{ msg?: string }> } } };
      const errorDetail = axiosErr.response?.data?.detail;
      if (errorDetail && Array.isArray(errorDetail)) {
        setError(errorDetail.map((e) => e.msg).filter(Boolean).join(', ') || t('login.failed'));
      } else if (typeof errorDetail === 'string') {
        setError(errorDetail);
      } else {
        setError(t('login.failed'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title={t('login.title')} subtitle={t('login.subtitle')}>
      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm border border-red-100">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-ink-700 mb-1">
            {t('login.username')}
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            maxLength={LIMITS.username.max}
            className="w-full px-4 py-3 border border-canvas-border rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent transition-all"
            placeholder={t('placeholders.login.username')}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-ink-700 mb-1">
            {t('login.password')}
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={LIMITS.password.min}
            maxLength={LIMITS.password.max}
            className="w-full px-4 py-3 border border-canvas-border rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent transition-all"
            placeholder={t('placeholders.login.password')}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-forge-600 text-white font-semibold rounded-lg hover:bg-forge-700 focus:ring-4 focus:ring-forge-200 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? t('login.submitting') : t('login.submit')}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-ink-500">
        {t('login.noAccount')}{' '}
        <Link to="/signup" className="font-medium text-forge-600 hover:text-forge-700">
          {t('login.signUpLink')}
        </Link>
      </p>
    </AuthLayout>
  );
}

export default Login;
