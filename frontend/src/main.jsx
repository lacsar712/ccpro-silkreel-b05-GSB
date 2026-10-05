import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api, clearToken, setToken, token } from "./api.js";
import "./app.css";

const STATUS_LABEL = { soaking: "浸茧", reeling: "缫丝中", reeled: "已缫完" };
const ROLE_LABEL = { admin: "管理员", worker: "缫丝工" };

function Login({ onOk }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123456");
  const [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault();
    setErr("");
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(data.access_token);
      onOk();
    } catch (ex) {
      setErr(ex.message);
    }
  }
  return (
    <div class="login">
      <h1>江口缫丝坞</h1>
      <p>汤温环盆作业台，不是列表台账。</p>
      <form onSubmit={submit} autocomplete="off">
        <label>
          用户名
          <input name="username" autocomplete="off" value={username} onInput={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          密码
          <input name="password" type="password" autocomplete="off" value={password} onInput={(e) => setPassword(e.target.value)} />
        </label>
        <p class="hint">已预填 admin / 123456，另有 worker / 123456</p>
        <button type="submit">登录</button>
      </form>
      {err && <p class="err">{err}</p>}
    </div>
  );
}

function Topbar({ view, onNav, user, onLogout }) {
  return (
    <div class="topbar">
      <div>
        <h1>江口缫丝坞</h1>
        <p>缫丝盆环状作业台 · 汤温登记间隔由管理员设定</p>
      </div>
      <div class="nav">
        <button class={view === "yard" ? "on" : ""} onClick={() => onNav("yard")}>
          环盆作业台
        </button>
        <button class={view === "interval" ? "on" : ""} onClick={() => onNav("interval")}>
          汤温间隔
        </button>
        <span class="who">
          {user.username} · {ROLE_LABEL[user.role] || user.role}
        </span>
        <button onClick={onLogout}>退出</button>
      </div>
    </div>
  );
}

function Drawer({ picked, intervalMin, temp, setTemp, onWrite, onSetStatus, err }) {
  const [, beat] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => beat((x) => x + 1), 15000);
    return () => clearInterval(timer);
  }, []);

  let cooldown = "";
  if (picked.latestTakenAt && intervalMin != null) {
    const elapsedMin = (Date.now() - new Date(picked.latestTakenAt).getTime()) / 60000;
    if (elapsedMin < intervalMin) {
      cooldown = `距上次登记未满 ${intervalMin} 分钟，再登会被挡下`;
    }
  }

  return (
    <div class="drawer">
      <h3>
        {picked.code} · {STATUS_LABEL[picked.status]}
      </h3>
      <p>
        最近汤温：{picked.latestTempC ?? "无"} ℃ · 记录 {picked.readingCount} 次
        {intervalMin != null && ` · 登记间隔 ${intervalMin} 分钟`}
      </p>
      <input value={temp} onInput={(e) => setTemp(e.target.value)} />
      <button onClick={onWrite}>登记汤温</button>
      <div>
        <button onClick={() => onSetStatus("soaking")}>浸茧</button>
        <button onClick={() => onSetStatus("reeling")}>缫丝中</button>
        <button onClick={() => onSetStatus("reeled")}>已缫完</button>
      </div>
      {cooldown && <p class="hint">{cooldown}</p>}
      {err && <p class="err">{err}</p>}
    </div>
  );
}

function Yard() {
  const [board, setBoard] = useState(null);
  const [picked, setPicked] = useState(null);
  const [temp, setTemp] = useState("40");
  const [err, setErr] = useState("");
  const [intervalMin, setIntervalMin] = useState(null);

  async function refresh() {
    const [data, setting] = await Promise.all([
      api("/api/board"),
      api("/api/settings/reading-interval"),
    ]);
    setBoard(data);
    setIntervalMin(setting.minIntervalMinutes);
    if (picked) {
      setPicked(data.basins.find((b) => b.id === picked.id) || data.basins[0]);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
  }, []);

  if (!board) {
    return <div>{err || "装载环盆…"}</div>;
  }

  const n = board.basins.length;
  async function writeTemp() {
    setErr("");
    try {
      const row = await api(`/api/basins/${picked.id}/readings`, {
        method: "POST",
        body: JSON.stringify({ waterTempC: Number(temp) }),
      });
      await refresh();
      setPicked(row);
    } catch (ex) {
      setErr(ex.message);
    }
  }
  async function setStatus(status) {
    setErr("");
    try {
      const row = await api(`/api/basins/${picked.id}/status`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      await refresh();
      setPicked(row);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  return (
    <div>
      <div class="yardhead">
        <h2>{board.filature}</h2>
        <p>
          {board.riverside} · 点盆登记汤温；已缫完须最近汤温 38～42℃
          {intervalMin != null && ` · 同盆登记间隔 ${intervalMin} 分钟`}
        </p>
      </div>
      <div class="ring">
        {board.basins.map((b, i) => {
          const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
          const left = 50 + Math.cos(angle) * 38;
          const top = 50 + Math.sin(angle) * 38;
          return (
            <button
              key={b.id}
              class={`basin ${b.status}`}
              style={{ left: `${left}%`, top: `${top}%` }}
              onClick={() => setPicked(b)}
            >
              <strong>{b.code}</strong>
              <span>{STATUS_LABEL[b.status]}</span>
            </button>
          );
        })}
      </div>
      {picked && (
        <Drawer
          picked={picked}
          intervalMin={intervalMin}
          temp={temp}
          setTemp={setTemp}
          onWrite={writeTemp}
          onSetStatus={setStatus}
          err={err}
        />
      )}
    </div>
  );
}

function IntervalPage({ user }) {
  const isAdmin = user.role === "admin";
  const [minutes, setMinutes] = useState(null);
  const [draft, setDraft] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function load() {
    const data = await api("/api/settings/reading-interval");
    setMinutes(data.minIntervalMinutes);
    setDraft(String(data.minIntervalMinutes));
  }

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, []);

  async function save(e) {
    e.preventDefault();
    setMsg("");
    setErr("");
    try {
      const data = await api("/api/settings/reading-interval", {
        method: "PUT",
        body: JSON.stringify({ minIntervalMinutes: Number(draft) }),
      });
      setMinutes(data.minIntervalMinutes);
      setDraft(String(data.minIntervalMinutes));
      setMsg("已保存");
    } catch (ex) {
      setErr(ex.message);
    }
  }

  if (minutes == null) {
    return <div class="panel">{err ? <p class="err">{err}</p> : "装载间隔…"}</div>;
  }

  return (
    <div class="panel">
      <h2>汤温间隔</h2>
      <p class="bignum">
        {minutes}
        <span> 分钟</span>
      </p>
      <p class="hint">同一盆两次汤温登记至少间隔 {minutes} 分钟；改盆态不看间隔。</p>
      {isAdmin ? (
        <form onSubmit={save}>
          <label>
            最小间隔分钟（至少 5）
            <input
              type="number"
              min="5"
              step="1"
              value={draft}
              onInput={(e) => setDraft(e.target.value)}
            />
          </label>
          <button type="submit">保存间隔</button>
        </form>
      ) : (
        <p class="hint">缫丝工只能查看间隔数字，调整请找管理员。</p>
      )}
      {msg && <p class="ok">{msg}</p>}
      {err && <p class="err">{err}</p>}
    </div>
  );
}

function Shell({ onLogout }) {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("yard");

  useEffect(() => {
    api("/api/auth/me")
      .then(setUser)
      .catch(() => {
        clearToken();
        location.reload();
      });
  }, []);

  if (!user) {
    return <div class="yard">装载…</div>;
  }

  return (
    <div class="yard">
      <Topbar view={view} onNav={setView} user={user} onLogout={onLogout} />
      {view === "yard" ? <Yard /> : <IntervalPage user={user} />}
    </div>
  );
}

function App() {
  const [ready, setReady] = useState(Boolean(token()));
  return ready ? (
    <Shell
      onLogout={() => {
        clearToken();
        location.reload();
      }}
    />
  ) : (
    <Login onOk={() => setReady(true)} />
  );
}

render(<App />, document.getElementById("app"));
