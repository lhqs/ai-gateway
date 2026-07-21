import {
  Activity,
  ArrowRight,
  Braces,
  Check,
  Clipboard,
  Gauge,
  GitBranch,
  Github,
  Layers3,
  LockKeyhole,
  Mail,
  Menu,
  Route,
  ServerCog,
  ShieldCheck,
  X
} from "lucide-react";
import { useEffect, useState } from "react";

const consoleViews = [
  {
    id: "dashboard",
    label: "运行总览",
    image: "/product/dashboard.png",
    alt: "LHQS AI Gateway Dashboard，展示请求量、成功率、延迟和最近调用"
  },
  {
    id: "routes",
    label: "路由策略",
    image: "/product/routes.png",
    alt: "LHQS AI Gateway 路由管理界面"
  },
  {
    id: "workbench",
    label: "调试工作台",
    image: "/product/workbench.png",
    alt: "LHQS AI Gateway 在线模型调试工作台"
  }
] as const;

const features = [
  {
    icon: Braces,
    index: "01",
    title: "统一与原生，双模接入",
    description: "兼容 OpenAI Chat Completions，同时保留 Gemini 等供应商原生协议的完整能力。"
  },
  {
    icon: GitBranch,
    index: "02",
    title: "自动故障转移",
    description: "主模型异常时按策略切换备用模型，流式请求在首个 token 前完成无感重试。"
  },
  {
    icon: Gauge,
    index: "03",
    title: "限流、缓存与成本治理",
    description: "用 Redis 承接高频治理，把请求额度、缓存命中与模型定价收敛到同一套策略。"
  },
  {
    icon: Activity,
    index: "04",
    title: "每次调用都有据可查",
    description: "统一记录 token、延迟、费用与原生响应，快速定位模型、客户端和路由问题。"
  }
] as const;

const installCommand = "curl https://gateway.lhqs.ink/v1/chat/completions \\\n  -H \"Authorization: Bearer $LHQS_API_KEY\" \\\n  -H \"Content-Type: application/json\" \\\n  -d '{\"model\":\"gpt-4\",\"messages\":[{\"role\":\"user\",\"content\":\"Hello\"}]}'";

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeView, setActiveView] = useState<(typeof consoleViews)[number]["id"]>("dashboard");
  const [copied, setCopied] = useState(false);
  const selectedView = consoleViews.find((view) => view.id === activeView) ?? consoleViews[0];

  useEffect(() => {
    document.title = "LHQS AI Gateway | 统一、可靠的 AI 模型网关";
    if (window.location.hash) {
      const sectionId = window.location.hash.slice(1);
      window.requestAnimationFrame(() => document.getElementById(sectionId)?.scrollIntoView());
    }
  }, []);

  async function copyCommand() {
    try {
      await navigator.clipboard.writeText(installCommand);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <main className="landing-page">
      <header className="landing-nav-wrap">
        <nav className="landing-nav" aria-label="主导航">
          <a className="brand-lockup" href="/" aria-label="LHQS AI Gateway 首页">
            <img src="/favicon.svg" alt="" />
            <span>LHQS AI Gateway</span>
          </a>

          <div className="landing-nav-links" aria-label="页面导航">
            <a href="#capabilities">核心能力</a>
            <a href="#architecture">架构</a>
            <a href="#console">控制台</a>
            <a href="https://github.com/lhqs/ai-gateway" target="_blank" rel="noreferrer">GitHub</a>
          </div>

          <a className="nav-console-link" href="/login">
            进入控制台
            <ArrowRight size={15} />
          </a>

          <button
            className="mobile-menu-button"
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={menuOpen ? "关闭导航" : "打开导航"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X size={21} /> : <Menu size={21} />}
          </button>
        </nav>

        {menuOpen && (
          <div className="mobile-nav-panel">
            <a href="#capabilities" onClick={() => setMenuOpen(false)}>核心能力</a>
            <a href="#architecture" onClick={() => setMenuOpen(false)}>架构</a>
            <a href="#console" onClick={() => setMenuOpen(false)}>控制台</a>
            <a href="https://github.com/lhqs/ai-gateway" target="_blank" rel="noreferrer">
              GitHub 开源项目 <Github size={15} />
            </a>
            <a href="/login">进入控制台 <ArrowRight size={15} /></a>
          </div>
        )}
      </header>

      <section className="landing-hero" aria-labelledby="hero-title">
        <img
          className="hero-backdrop"
          src="/product/dashboard.png"
          alt=""
          aria-hidden="true"
        />
        <div className="hero-wash" aria-hidden="true" />
        <div className="landing-container hero-content">
          <div className="hero-kicker"><span /> gateway.lhqs.ink</div>
          <h1 id="hero-title">LHQS AI Gateway</h1>
          <p className="hero-statement">一个入口，编排每一种模型。</p>
          <p className="hero-description">
            统一 OpenAI 兼容与供应商原生协议，把路由、故障转移、访问控制、缓存、用量和计费放进一套清晰的治理面。
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="/login">
              打开控制台 <ArrowRight size={17} />
            </a>
            <a
              className="secondary-action"
              href="https://github.com/lhqs/ai-gateway"
              target="_blank"
              rel="noreferrer"
            >
              <Github size={16} /> 查看开源项目
            </a>
          </div>
          <div className="hero-proof" aria-label="产品特性">
            <span><Check size={14} /> OpenAI Compatible</span>
            <span><Check size={14} /> Gemini Native</span>
            <span><Check size={14} /> Self-hosted</span>
          </div>
        </div>
      </section>

      <section className="signal-band" aria-label="核心价值">
        <div className="landing-container signal-grid">
          <p>一套 API Key</p>
          <p>多供应商路由</p>
          <p>流式首 token 守护</p>
          <p>全链路用量观测</p>
        </div>
      </section>

      <section className="capabilities-section" id="capabilities">
        <div className="landing-container">
          <div className="section-heading split-heading">
            <div>
              <span className="section-label">CAPABILITIES / 能力</span>
              <h2>复杂留在网关，<br />接口保持简单。</h2>
            </div>
            <p>
              业务只面对稳定的入口。模型供应商之间的协议差异、可用性波动和价格变化，由网关统一吸收。
            </p>
          </div>

          <div className="feature-list">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <article className="feature-row" key={feature.index}>
                  <span className="feature-index">{feature.index}</span>
                  <Icon className="feature-icon" size={23} />
                  <h3>{feature.title}</h3>
                  <p>{feature.description}</p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      <section className="architecture-section" id="architecture">
        <div className="landing-container architecture-inner">
          <div className="section-heading architecture-heading">
            <span className="section-label">ROUTING / 路由</span>
            <h2>一次请求，走最合适的路径。</h2>
            <p>别名屏蔽底层模型变化，策略决定主备顺序。异常、限流与重试都留在请求链路内部。</p>
          </div>

          <div className="route-map" aria-label="AI 请求路由示意图">
            <div className="route-node route-client">
              <Layers3 size={19} />
              <span>你的应用</span>
              <small>single endpoint</small>
            </div>
            <div className="route-connector"><span>HTTPS</span></div>
            <div className="route-node route-gateway">
              <img src="/favicon-light.svg" alt="" />
              <span>LHQS Gateway</span>
              <small>auth · route · observe</small>
            </div>
            <div className="route-branches" aria-hidden="true"><i /><i /><i /></div>
            <div className="provider-stack">
              <div className="provider-node"><span className="provider-mark openai-mark">O</span><span>OpenAI Compatible</span><small>primary</small></div>
              <div className="provider-node"><span className="provider-mark gemini-mark">G</span><span>Gemini Native</span><small>fallback 01</small></div>
              <div className="provider-node"><span className="provider-mark custom-mark">+</span><span>Custom Provider</span><small>fallback 02</small></div>
            </div>
          </div>

          <div className="architecture-notes">
            <div><ShieldCheck size={18} /><span><strong>访问策略</strong>精确到客户端、模型与原生路径</span></div>
            <div><Route size={18} /><span><strong>路由策略</strong>按权重、主备与失败条件调度</span></div>
            <div><ServerCog size={18} /><span><strong>请求治理</strong>覆盖限流、缓存、日志与计费</span></div>
          </div>
        </div>
      </section>

      <section className="console-section" id="console">
        <div className="landing-container">
          <div className="section-heading split-heading console-heading">
            <div>
              <span className="section-label">CONSOLE / 控制台</span>
              <h2>运营状态，<br />不藏在日志里。</h2>
            </div>
            <p>从总览到单次调用，从模型定价到故障转移链路，日常管理都在一个安静、清晰的工作台完成。</p>
          </div>

          <div className="console-tabs" role="tablist" aria-label="控制台界面">
            {consoleViews.map((view) => (
              <button
                key={view.id}
                type="button"
                role="tab"
                aria-selected={activeView === view.id}
                onClick={() => setActiveView(view.id)}
              >
                {view.label}
              </button>
            ))}
          </div>

          <div className="console-frame">
            <div className="browser-chrome" aria-hidden="true">
              <span /><span /><span />
              <p>gateway.lhqs.ink/{selectedView.id}</p>
            </div>
            <img src={selectedView.image} alt={selectedView.alt} />
          </div>
        </div>
      </section>

      <section className="developer-section">
        <div className="landing-container developer-grid">
          <div className="developer-copy">
            <span className="section-label">DEVELOPER FIRST</span>
            <h2>接入方式不变，<br />模型选择更自由。</h2>
            <p>保留熟悉的 OpenAI 请求格式，只需替换 Base URL 与 API Key。原有 SDK 和业务调用逻辑可以继续工作。</p>
            <div className="security-line"><LockKeyhole size={16} /> API Key 仅在创建或轮换时完整展示</div>
          </div>

          <div className="code-window">
            <div className="code-window-header">
              <span>Terminal</span>
              <button type="button" onClick={copyCommand} title="复制请求示例" aria-label="复制请求示例">
                {copied ? <Check size={16} /> : <Clipboard size={16} />}
              </button>
            </div>
            <pre><code><span className="code-command">curl</span> https://gateway.lhqs.ink/v1/chat/completions \
  -H <span className="code-string">&quot;Authorization: Bearer $LHQS_API_KEY&quot;</span> \
  -H <span className="code-string">&quot;Content-Type: application/json&quot;</span> \
  -d <span className="code-string">&apos;&#123;&quot;model&quot;:&quot;gpt-4&quot;,&quot;messages&quot;:[...]&#125;&apos;</span></code></pre>
            <div className="code-status"><span /> 200 OK <small>· routed in 842 ms</small></div>
          </div>
        </div>
      </section>

      <section className="final-cta">
        <div className="landing-container final-cta-inner">
          <div>
            <span className="section-label">READY WHEN YOU ARE</span>
            <h2>让每次模型调用，<br />都有稳定的去处。</h2>
          </div>
          <a className="light-action" href="/login">进入 gateway.lhqs.ink <ArrowRight size={17} /></a>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-container footer-inner">
          <div className="footer-brand">
            <img src="/favicon.svg" alt="" />
            <div><strong>LHQS AI Gateway</strong><span>Unified AI infrastructure.</span></div>
          </div>
          <div className="footer-meta">
            <span>Built by lhqs</span>
            <a href="https://github.com/lhqs/ai-gateway" target="_blank" rel="noreferrer">
              <Github size={14} /> GitHub
            </a>
            <a href="mailto:lhqs1314@gmail.com"><Mail size={14} /> lhqs1314@gmail.com</a>
            <span>© {new Date().getFullYear()} lhqs</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
