#!/usr/bin/env node
/**
 * Trusted local SIWC bridge for Ryoku.
 * Speaks one JSON object per line on stdin/stdout. Never prints tokens.
 *
 * Env:
 *   RYOKU_SIWC_STORAGE_DIR — absolute storage directory
 *   RYOKU_SIWC_TEST_MEMORY_CRYPTO=1 — test-only memory encryption (CI/unit)
 */
import { createInterface } from "node:readline";
import { homedir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import { createChatGPT, ChatGPTError, CHATGPT_USAGE_URL } from "@siwc/local";
import {
  createLinuxCredentialEncryption,
  createMemoryCredentialEncryption,
} from "./credential-encryption.mjs";

const APP_NAME = "Ryoku AI";
const APP_ID = "ryoku-ai-omarchy";

function openSystemBrowser(url) {
  const opener =
    process.platform === "darwin"
      ? "open"
      : process.platform === "win32"
        ? "cmd"
        : "xdg-open";
  const args = process.platform === "win32" ? ["/c", "start", "", url] : [url];
  const child = spawn(opener, args, { stdio: "ignore", detached: true });
  child.unref();
}

function storageDir() {
  const fromEnv = process.env.RYOKU_SIWC_STORAGE_DIR;
  if (fromEnv) {
    if (!fromEnv.startsWith("/")) {
      throw new Error("RYOKU_SIWC_STORAGE_DIR must be absolute.");
    }
    return fromEnv;
  }
  return join(homedir(), ".config", APP_ID);
}

function encryptionProvider() {
  if (process.env.RYOKU_SIWC_TEST_MEMORY_CRYPTO === "1") {
    return createMemoryCredentialEncryption();
  }
  return createLinuxCredentialEncryption();
}

function publicError(error) {
  if (error instanceof ChatGPTError) {
    return {
      ok: false,
      error: {
        code: error.code,
        message: error.message,
        retryable: Boolean(error.retryable),
      },
    };
  }
  return {
    ok: false,
    error: {
      code: "bridge_error",
      message: error instanceof Error ? error.message : "Unexpected bridge failure.",
      retryable: false,
    },
  };
}

function sanitizeSession(session) {
  return {
    status: session.status,
    sharing: Boolean(session.sharing),
    profileId: session.profileId ?? null,
    profileLabel: session.profileLabel ?? null,
    identity: session.identity
      ? {
          name: session.identity.name ?? null,
          email: session.identity.email ?? null,
        }
      : null,
    error: session.error
      ? {
          code: session.error.code,
          message: session.error.message,
          retryable: Boolean(session.error.retryable),
        }
      : null,
  };
}

const chatgpt = createChatGPT({
  appName: APP_NAME,
  appId: APP_ID,
  redirectPort: 0,
  storageDir: storageDir(),
  credentialEncryption: encryptionProvider(),
  openBrowser: openSystemBrowser,
  sendHostId: true,
});

async function handle(command) {
  const { op, args = {} } = command;
  switch (op) {
    case "ping":
      return { ok: true, result: { pong: true, usageUrl: CHATGPT_USAGE_URL } };
    case "session":
      return { ok: true, result: sanitizeSession(await chatgpt.getSession()) };
    case "profiles":
      return { ok: true, result: await chatgpt.listProfiles() };
    case "login": {
      const session = await chatgpt.signIn({
        ...(args.newProfile ? { newProfile: true } : {}),
        ...(args.profileId ? { profileId: args.profileId } : {}),
        ...(args.reconsent ? { reconsent: true } : {}),
      });
      return { ok: true, result: sanitizeSession(session) };
    }
    case "logout":
      await chatgpt.disconnect();
      return { ok: true, result: sanitizeSession(await chatgpt.getSession()) };
    case "select_profile": {
      if (typeof args.profileId !== "string" || !args.profileId) {
        throw new ChatGPTError("invalid_config", "Informe profileId.");
      }
      return { ok: true, result: sanitizeSession(await chatgpt.selectProfile(args.profileId)) };
    }
    case "models": {
      const models = await chatgpt.listModels();
      return { ok: true, result: models.map((m) => ({ slug: m.slug, displayName: m.displayName })) };
    }
    case "chat": {
      const model = args.model;
      const input = args.input;
      if (typeof model !== "string" || !model) {
        throw new ChatGPTError("invalid_config", "Informe o modelo.");
      }
      if (typeof input !== "string" || !input.trim()) {
        throw new ChatGPTError("invalid_config", "Informe a mensagem.");
      }
      const instructions =
        typeof args.instructions === "string" && args.instructions.trim()
          ? args.instructions
          : "You are Ryoku, a helpful terminal assistant for Omarchy/Arch Linux. Reply clearly and concisely.";
      let streamed = "";
      const result = await chatgpt.streamResponse({
        model,
        input,
        instructions,
        onDelta: (delta) => {
          streamed += delta;
          // Stream deltas as separate NDJSON events; final reply still returned once.
          process.stdout.write(
            `${JSON.stringify({ ok: true, event: "delta", text: delta })}\n`,
          );
        },
      });
      return { ok: true, result: { text: result.text || streamed } };
    }
    case "cancel_login":
      chatgpt.cancelSignIn();
      return { ok: true, result: { cancelled: true } };
    default:
      throw new ChatGPTError("invalid_config", `Operação desconhecida: ${op}`);
  }
}

const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of rl) {
  const trimmed = line.trim();
  if (!trimmed) continue;
  let command;
  try {
    command = JSON.parse(trimmed);
  } catch {
    process.stdout.write(
      `${JSON.stringify({ ok: false, error: { code: "invalid_json", message: "Linha JSON inválida.", retryable: false } })}\n`,
    );
    continue;
  }
  try {
    const response = await handle(command);
    process.stdout.write(`${JSON.stringify(response)}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify(publicError(error))}\n`);
  }
}
