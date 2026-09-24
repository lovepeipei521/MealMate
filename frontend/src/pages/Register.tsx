import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Utensils } from 'lucide-react';
import { useAuth } from '../contexts';

function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | string[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('请输入用户名和密码。');
      return;
    }
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致。');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      await register({ username: username.trim(), password });
      navigate('/agent', { replace: true });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '注册失败，请稍后重试。';
      setError(msg.includes('\n') ? msg.split('\n').map(s => s.trim()).filter(Boolean) : msg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mm-auth-page">
      <main className="mm-auth-shell">
        <section className="mm-auth-art">
          <div className="flex items-center gap-3">
            <div className="mm-brand-mark">
              <Utensils />
            </div>
            <div>
              <div className="mm-brand-name">MealMate</div>
              <div className="mm-brand-sub">KITCHEN NOTES</div>
            </div>
          </div>

          <div className="mm-eyebrow mt-7">从你的目标开始</div>
          <h1>
            建立你的
            <br />
            <em>专属饮食助手。</em>
          </h1>
          <p>
            注册后可按减脂、增肌、家庭备餐、日常健康管理等不同需求，获得不同建议、食谱、食材搭配与执行计划。
          </p>
          <div className="mm-auth-features">
            <div className="mm-auth-feature">✓ 个性化饮食建议</div>
            <div className="mm-auth-feature">✓ 多日计划与食材方案</div>
            <div className="mm-auth-feature">✓ 对话、知识库与统计</div>
          </div>
          <div className="mm-auth-plate" aria-hidden="true" />
        </section>

        <section className="mm-auth-panel">
          <div className="mm-auth-card">
            <div className="mm-eyebrow">Create account</div>
            <h2>加入 MealMate</h2>
            <p>创建账号，开始制定更适合你的饮食方案。</p>

            <form className="mm-auth-form" onSubmit={handleSubmit}>
              <div className="mm-field">
                <label htmlFor="register-username">用户名</label>
                <input
                  id="register-username"
                  className="mm-input"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="3–32 个字符"
                  autoComplete="username"
                />
              </div>

              <div className="mm-field">
                <label htmlFor="register-password">密码</label>
                <input
                  id="register-password"
                  className="mm-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="至少 8 位"
                  autoComplete="new-password"
                />
              </div>

              <div className="mm-field">
                <label htmlFor="register-confirm-password">确认密码</label>
                <input
                  id="register-confirm-password"
                  className="mm-input"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="再次输入密码"
                  autoComplete="new-password"
                />
              </div>

              {error && (
                <div className="mm-auth-error">
                  {Array.isArray(error) ? (
                    <ul className="ml-4 list-disc">
                      {error.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  ) : (
                    <div>{error}</div>
                  )}
                </div>
              )}

              <button type="submit" disabled={isLoading} className="mm-auth-submit">
                {isLoading ? '正在创建账号...' : '创建账号'}
              </button>
            </form>

            <p className="mm-auth-switch">
              已经有账号？{' '}
              <Link to="/login">去登录</Link>
            </p>
            <div className="mm-auth-mini">
              <span>注册即同意隐私说明</span>
              <span>本地优先存储</span>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default RegisterPage;
