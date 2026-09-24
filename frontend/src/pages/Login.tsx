import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import type { Location } from 'react-router-dom';
import { Utensils } from 'lucide-react';
import { useAuth } from '../contexts';

function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: Location })?.from?.pathname || '/agent';

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | string[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('请输入用户名和密码。');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      await login({ username: username.trim(), password });
      navigate(from, { replace: true });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '登录失败，请稍后重试。';
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

          <div className="mm-eyebrow mt-7">按不同目标，给出真正适合的建议</div>
          <h1>
            每个人的饮食方案，
            <br />
            <em>都应该不一样。</em>
          </h1>
          <p>
            MealMate 会结合你的目标、口味、人数和现有食材，提供个性化建议、食谱方案、饮食计划与记录，让不同需求都有对应解法。
          </p>
          <div className="mm-auth-features">
            <div className="mm-auth-feature">个性化建议</div>
            <div className="mm-auth-feature">多日计划</div>
            <div className="mm-auth-feature">食谱与食材</div>
          </div>
          <div className="mm-auth-plate" aria-hidden="true" />
        </section>

        <section className="mm-auth-panel">
          <div className="mm-auth-card">
            <div className="mm-eyebrow">Welcome back</div>
            <h2>欢迎回到 MealMate</h2>
            <p>登录后继续你的个性化建议、饮食计划与知识库。</p>

            <form className="mm-auth-form" onSubmit={handleSubmit}>
              <div className="mm-field">
                <label htmlFor="login-username">用户名</label>
                <input
                  id="login-username"
                  className="mm-input"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  autoComplete="username"
                />
              </div>

              <div className="mm-field">
                <label htmlFor="login-password">密码</label>
                <input
                  id="login-password"
                  className="mm-input"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  autoComplete="current-password"
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
                {isLoading ? '正在登录...' : '登录'}
              </button>
            </form>

            <p className="mm-auth-switch">
              还没有账号？{' '}
              <Link to="/register">创建一个账号</Link>
            </p>
            <div className="mm-auth-mini">
              <span>会话记忆</span>
              <span>个人知识库</span>
              <span>数据隔离</span>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default LoginPage;
