import { render } from "preact";
import { useEffect, useState } from "preact/hooks";
import { api, clearToken, setToken, token } from "./api.js";
import "./app.css";

const STATUS_LABEL = { soaking: "浸茧", reeling: "缫丝中", reeled: "已缫完" };

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

function Yard() {
  const [board, setBoard] = useState(null);
  const [picked, setPicked] = useState(null);
  const [temp, setTemp] = useState("40");
  const [err, setErr] = useState("");

  async function refresh() {
    const data = await api("/api/board");
    setBoard(data);
    if (picked) {
      setPicked(data.basins.find((b) => b.id === picked.id) || data.basins[0]);
    }
  }

  useEffect(() => {
    refresh().catch((e) => setErr(e.message));
  }, []);

  if (!board) {
    return (
      <div class="yard">
        {err || "装载环盆…"}
      </div>
    );
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
    <div class="yard">
      <div class="topbar">
        <div>
          <h1>{board.filature}</h1>
          <p>{board.riverside} · 点盆登记汤温；已缫完须最近汤温 38～42℃</p>
        </div>
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
        <div class="drawer">
          <h3>
            {picked.code} · {STATUS_LABEL[picked.status]}
          </h3>
          <p>最近汤温：{picked.latestTempC ?? "无"} ℃ · 记录 {picked.readingCount} 次</p>
          <input value={temp} onInput={(e) => setTemp(e.target.value)} />
          <button onClick={writeTemp}>登记汤温</button>
          <div>
            <button onClick={() => setStatus("soaking")}>浸茧</button>
            <button onClick={() => setStatus("reeling")}>缫丝中</button>
            <button onClick={() => setStatus("reeled")}>已缫完</button>
          </div>
          {err && <p class="err">{err}</p>}
        </div>
      )}
    </div>
  );
}

function IntervalPage({ me }) {
  const [info, setInfo] = useState(null);
  const [minutes, setMinutes] = useState("5");
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const isAdmin = me && me.role === "admin";

  async function refresh(init = false) {
    const data = await api("/api/settings/interval");
    setInfo(data);
    if (init) setMinutes(String(data.minIntervalMinutes));
  }

  useEffect(() => {
    refresh(true).catch((e) => setErr(e.message));
    const timer = setInterval(() => refresh().catch(() => {}), 5000);
    return () => clearInterval(timer);
  }, []);

  async function save(e) {
    e.preventDefault();
    setErr("");
    setOk("");
    try {
      const data = await api("/api/settings/interval", {
        method: "PUT",
        body: JSON.stringify({ minIntervalMinutes: Number(minutes) }),
      });
      setOk(`已保存：最小间隔 ${data.minIntervalMinutes} 分钟`);
      await refresh();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  if (!info) {
    return <div class="yard">{err || "装载间隔…"}</div>;
  }

  return (
    <div class="yard">
      <h1>汤温间隔</h1>
      <p>
        当前最小间隔：<strong>{info.minIntervalMinutes}</strong> 分钟（至少 5）
      </p>
      {me === null ? null : isAdmin ? (
        <form class="interval-form" onSubmit={save}>
          <label>
            最小间隔分钟
            <input
              type="number"
              min="5"
              step="1"
              value={minutes}
              onInput={(e) => setMinutes(e.target.value)}
            />
          </label>
          <button type="submit">保存</button>
        </form>
      ) : (
        <p class="hint">缫丝工只能查看间隔数字，改间隔请找管理员。</p>
      )}
      {ok && <p class="ok">{ok}</p>}
      {err && <p class="err">{err}</p>}
      <table class="interval-table">
        <thead>
          <tr>
            <th>盆位</th>
            <th>上次登记</th>
            <th>还需等待（秒）</th>
          </tr>
        </thead>
        <tbody>
          {info.basins.map((b) => (
            <tr key={b.id}>
              <td>{b.code}</td>
              <td>{b.lastTakenAt ? new Date(b.lastTakenAt).toLocaleString() : "无"}</td>
              <td>{b.waitSeconds > 0 ? b.waitSeconds : "可登记"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function App() {
  const [ready, setReady] = useState(Boolean(token()));
  const [page, setPage] = useState("yard");
  const [me, setMe] = useState(null);

  useEffect(() => {
    if (ready) {
      api("/api/auth/me")
        .then(setMe)
        .catch(() => setMe(null));
    }
  }, [ready]);

  if (!ready) {
    return <Login onOk={() => setReady(true)} />;
  }

  return (
    <div>
      <nav class="topnav">
        <button class={page === "yard" ? "on" : ""} onClick={() => setPage("yard")}>
          环盆作业台
        </button>
        <button class={page === "interval" ? "on" : ""} onClick={() => setPage("interval")}>
          汤温间隔
        </button>
        <span class="spacer" />
        <button
          onClick={() => {
            clearToken();
            location.reload();
          }}
        >
          退出
        </button>
      </nav>
      {page === "yard" ? <Yard /> : <IntervalPage me={me} />}
    </div>
  );
}

render(<App />, document.getElementById("app"));
