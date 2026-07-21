import { useState, useEffect } from 'react';
import { listUsers, createUser, updateUser, deleteUser } from '../api/auth';
import type { UserResponse, CreateUserData, UpdateUserData } from '../api/auth';
import { Plus, Edit2, Trash2, X, Check, UserCog, RefreshCw, Eye, EyeOff } from 'lucide-react';
import {
  LIMITS,
  alertValidationErrors,
  emailFormat,
  maxLen,
  minLen,
  required,
} from '@/lib/formValidation';

const generateRandomPassword = (): string => {
 const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
 let password = '';
 for (let i = 0; i < 12; i++) {
 password += chars.charAt(Math.floor(Math.random() * chars.length));
 }
 return password;
};

function UserManagement() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [newUser, setNewUser] = useState<CreateUserData>({
    username: '',
    email: '',
    password: generateRandomPassword(),
    is_admin: false,
  });
  const [showPassword, setShowPassword] = useState(false);

  const [editForm, setEditForm] = useState<UpdateUserData>({
    email: '',
    password: '',
    is_active: true,
    is_admin: false,
  });

  const fetchUsers = async (opts?: { silent?: boolean }) => {
    try {
      if (!opts?.silent) setLoading(true);
      const data = await listUsers();
      setUsers(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载用户列表失败');
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (
      alertValidationErrors([
        required('用户名', newUser.username),
        minLen('用户名', newUser.username, LIMITS.username.min),
        maxLen('用户名', newUser.username, LIMITS.username.max),
        emailFormat('邮箱', newUser.email, true),
        required('密码', newUser.password),
        minLen('密码', newUser.password, LIMITS.password.min),
        maxLen('密码', newUser.password, LIMITS.password.max),
      ])
    ) {
      return;
    }

    try {
      const userData = {
        ...newUser,
        email: newUser.email || undefined,
      };
      const created = await createUser(userData);
      setUsers((prev) => [...prev, created]);
      setShowCreateModal(false);
      setNewUser({ username: '', email: '', password: generateRandomPassword(), is_admin: false });
      setSuccess('用户创建成功');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0].msg : detail || '创建用户失败');
    }
  };

  const handleEditUser = (user: UserResponse) => {
    setEditingUserId(user.user_id);
    setEditForm({
      email: user.email,
      password: '',
      is_active: user.is_active,
      is_admin: user.is_admin,
    });
    setError('');
    setSuccess('');
  };

  const handleSaveEdit = async (userId: string) => {
    setError('');
    setSuccess('');
    if (
      alertValidationErrors([
        emailFormat('邮箱', editForm.email, true),
        editForm.password
          ? minLen('密码', editForm.password, LIMITS.password.min)
          : null,
        editForm.password
          ? maxLen('密码', editForm.password, LIMITS.password.max)
          : null,
      ])
    ) {
      return;
    }

    try {
      const updateData: UpdateUserData = { ...editForm };
      if (!updateData.password) {
        delete updateData.password;
      }
      const updated = await updateUser(userId, updateData);
      setUsers((prev) => prev.map((u) => (u.user_id === updated.user_id ? updated : u)));
      setEditingUserId(null);
      setSuccess('用户信息更新成功');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || '更新用户失败');
    }
  };

  const handleDeleteUser = async (userId: string) => {
    if (!window.confirm('确定要删除该用户吗？')) {
      return;
    }

    setError('');
    setSuccess('');

    try {
      await deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.user_id !== userId));
      setSuccess('用户删除成功');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除用户失败');
    }
  };

  if (loading && users.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">用户管理</h1>
          <p className="text-gray-500 mt-1">管理系统用户和权限</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          添加用户
        </button>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 text-red-600 rounded-lg">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-4 bg-green-50 text-green-600 rounded-lg">
          {success}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                用户名
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                邮箱
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                密码
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                角色
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                状态
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                创建时间
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((user) => (
              <tr key={user.user_id} className="hover:bg-gray-50">
                {editingUserId === user.user_id ? (
                  <>
                    <td className="px-6 py-4">
                      <span className="font-medium text-gray-900">{user.username}</span>
                    </td>
                    <td className="px-6 py-4">
                      <input
                        type="email"
                        value={editForm.email || ''}
                        onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                        maxLength={LIMITS.email}
                        className="w-full px-3 py-1 border border-gray-300 rounded-md text-sm"
                        placeholder="可选"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <input
                        type="password"
                        value={editForm.password || ''}
                        onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                        minLength={LIMITS.password.min}
                        maxLength={LIMITS.password.max}
                        className="w-full px-3 py-1 border border-gray-300 rounded-md text-sm"
                        placeholder="留空则不修改"
                      />
                    </td>
                    <td className="px-6 py-4">
                      <select
                        value={editForm.is_admin ? 'admin' : 'user'}
                        onChange={(e) => setEditForm({ ...editForm, is_admin: e.target.value === 'admin' })}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm"
                      >
                        <option value="user">普通用户</option>
                        <option value="admin">管理员</option>
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      <select
                        value={editForm.is_active ? 'active' : 'inactive'}
                        onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value === 'active' })}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm"
                      >
                        <option value="active">启用</option>
                        <option value="inactive">禁用</option>
                      </select>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {new Date(user.created_at).toLocaleDateString('zh-CN')}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleSaveEdit(user.user_id)}
                          className="p-1 text-green-600 hover:bg-green-50 rounded"
                        >
                          <Check className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => setEditingUserId(null)}
                          className="p-1 text-gray-400 hover:bg-gray-100 rounded"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                          <UserCog className="w-4 h-4 text-blue-600" />
                        </div>
                        <span className="font-medium text-gray-900">{user.username}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {user.email || '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 font-mono">
                      ********
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_admin
                          ? 'bg-purple-100 text-purple-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {user.is_admin ? '管理员' : '普通用户'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {user.is_active ? '启用' : '禁用'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {new Date(user.created_at).toLocaleDateString('zh-CN')}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleEditUser(user)}
                          className="p-1 text-blue-600 hover:bg-blue-50 rounded"
                        >
                          <Edit2 className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => handleDeleteUser(user.user_id)}
                          className="p-1 text-red-600 hover:bg-red-50 rounded"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-800">添加新用户</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  用户名
                </label>
                <input
                  type="text"
                  value={newUser.username}
                  onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                  required
                  minLength={LIMITS.username.min}
                  maxLength={LIMITS.username.max}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="请输入用户名"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  邮箱 <span className="text-gray-400 font-normal">(可选)</span>
                </label>
                <input
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  maxLength={LIMITS.email}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="请输入邮箱（可选）"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  密码
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={newUser.password}
                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                    required
                    minLength={LIMITS.password.min}
                    maxLength={LIMITS.password.max}
                    className="w-full px-4 py-2 pr-28 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="系统已自动生成密码"
                  />
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="p-1 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => setNewUser({ ...newUser, password: generateRandomPassword() })}
                      className="p-1 text-gray-400 hover:text-gray-600"
                      title="生成随机密码"
                    >
                      <RefreshCw className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_admin"
                  checked={newUser.is_admin}
                  onChange={(e) => setNewUser({ ...newUser, is_admin: e.target.checked })}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label htmlFor="is_admin" className="text-sm text-gray-700">
                  设为管理员
                </label>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  创建
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserManagement;