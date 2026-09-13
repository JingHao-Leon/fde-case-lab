import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync, utimesSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PiConversationRuntime } from "../src/adapters/pi/PiConversationRuntime.ts";
import { readJson, STATE_PI_PATH, writeJson } from "../src/feishu/config.ts";

test("pi runtime: ensures session file stats are tracked and hot-reloaded on external modifications", async () => {
  const homeDir = mkdtempSync(join(tmpdir(), "feishu-pi-test-"));
  const previousHome = process.env.HOME;
  process.env.HOME = homeDir;
  try {
    const wsDir = join(homeDir, "ws");
    const runtime = new PiConversationRuntime(wsDir);
    const key = "p2p:ou_test";

    // 初始状态下无 session
    assert.equal(runtime.getStatus(key).hasActiveRun, false);

    // 模拟存在一个 session 文件
    const sessionFile = join(homeDir, "session_001.jsonl");
    writeFileSync(sessionFile, JSON.stringify({ role: "user", content: "hello" }) + "\n", "utf8");

    // 保存到 state
    const state = readJson(STATE_PI_PATH, { sessions: {} });
    state.sessions[key] = sessionFile;
    writeJson(STATE_PI_PATH, state);
    (runtime as any).state.sessions[key] = sessionFile;

    // 验证 recordSessionFileStat 和 ensureSessionFresh 的行为
    const anyRuntime = runtime as any;
    anyRuntime.recordSessionFileStat(key, sessionFile);
    const recorded = anyRuntime.sessionFileStats.get(key);
    assert.ok(recorded, "should record initial file stat");
    assert.ok(recorded.mtimeMs > 0);
    assert.ok(recorded.size > 0);

    // 模拟外部写入（电脑终端追加了新内容）
    writeFileSync(sessionFile, JSON.stringify({ role: "user", content: "hello" }) + "\n" + JSON.stringify({ role: "assistant", content: "hi from terminal" }) + "\n", "utf8");
    // 更新 mtime
    const now = new Date(Date.now() + 2000);
    utimesSync(sessionFile, now, now);

    // 模拟 cachedPromise
    let oldDisposed = false;
    const oldSessionMock = {
      sessionId: "s1",
      sessionFile,
      dispose: () => { oldDisposed = true; },
      messages: [],
    };
    anyRuntime.sessions.set(key, Promise.resolve(oldSessionMock));

    // 模拟 createSession 返回新 session
    let createdNew = false;
    const newSessionMock = {
      sessionId: "s2",
      sessionFile,
      dispose: () => {},
      messages: [{ role: "user", content: "hello" }, { role: "assistant", content: "hi from terminal" }],
    };
    anyRuntime.createSession = async (_k: string) => {
      createdNew = true;
      anyRuntime.recordSessionFileStat(key, sessionFile);
      return newSessionMock;
    };

    // 触发 ensureSessionFresh
    const freshSession = await anyRuntime.ensureSessionFresh(key);
    assert.equal(oldDisposed, true, "old session should be disposed");
    assert.equal(createdNew, true, "new session should be created via re-open");
    assert.equal(freshSession.sessionId, "s2");

    // 再次调用时，若无外部修改，不应重复重载
    createdNew = false;
    const sameSession = await anyRuntime.ensureSessionFresh(key);
    assert.equal(createdNew, false, "should not reload again if file unchanged");
    assert.equal(sameSession.sessionId, "s2");
  } finally {
    if (previousHome === undefined) delete process.env.HOME;
    else process.env.HOME = previousHome;
    rmSync(homeDir, { recursive: true, force: true });
  }
});
