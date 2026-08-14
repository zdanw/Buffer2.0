import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, setToken, setRefreshToken } from '../api/auth';
import type { LoginData } from '../api/auth';
import {
  LIMITS,
  alertValidationErrors,
} from '@/lib/formValidation';
import { useI18n } from '@/i18n/useI18n';
import { useValidators } from '@/i18n/helpers';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import BrandLogo from '@/components/BrandLogo';

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
        navigate('/assets', { replace: true });
      } else {
        setError(t('login.responseError'));
      }
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail;
      if (errorDetail && Array.isArray(errorDetail)) {
        setError(errorDetail.map((e: any) => e.msg).join(', ') || t('login.failed'));
      } else {
        setError(errorDetail || t('login.failed'));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <BrandLogo size="xl" className="shadow-md" />
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            {t('login.title')}
          </h1>
          <p className="text-gray-500">
            {t('login.subtitle')}
          </p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('login.username')}
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              maxLength={LIMITS.username.max}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder={t('login.usernamePlaceholder')}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('login.password')}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={LIMITS.password.min}
              maxLength={LIMITS.password.max}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              placeholder={t('login.passwordPlaceholder')}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 focus:ring-4 focus:ring-blue-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {t('login.submitting')}
              </span>
            ) : (
              t('login.submit')
            )}
          </button>
        </form>

        <div className="mt-6">
          <LanguageSwitcher compact variant="light" />
        </div>
      </div>
    </div>
  );
}

export default Login;
