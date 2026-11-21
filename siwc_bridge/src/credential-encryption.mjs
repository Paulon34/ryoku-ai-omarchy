/**
 * OS-backed CredentialEncryption for Linux Secret Service / KWallet via keytar.
 * No plaintext fallback. Refuses when the secret store is unavailable.
 */
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import keytar from "keytar";

const SERVICE = "ryoku-ai-omarchy";
const ACCOUNT = "siwc-file-encryption-key-v1";
const PROVIDER_ID = "linux-libsecret-aes-gcm-v1";

async function probeKeytar() {
  try {
    // Touch the secret service without creating secrets on a mere availability check.
    await keytar.findCredentials(SERVICE);
    return true;
  } catch {
    return false;
  }
}

async function loadOrCreateKey() {
  let encoded = await keytar.getPassword(SERVICE, ACCOUNT);
  if (!encoded) {
    encoded = randomBytes(32).toString("base64");
    await keytar.setPassword(SERVICE, ACCOUNT, encoded);
  }
  const key = Buffer.from(encoded, "base64");
  if (key.length !== 32) {
    throw new Error("Stored encryption key has an unexpected length.");
  }
  return key;
}

/** @returns {import('@siwc/local').CredentialEncryption} */
export function createLinuxCredentialEncryption() {
  return {
    id: PROVIDER_ID,
    async isAvailable() {
      return probeKeytar();
    },
    async encrypt(plaintext) {
      if (!(await probeKeytar())) {
        throw new Error(
          "Armazenamento seguro indisponível (Secret Service/KWallet). Desbloqueie o chaveiro e tente de novo.",
        );
      }
      const key = await loadOrCreateKey();
      const iv = randomBytes(12);
      const cipher = createCipheriv("aes-256-gcm", key, iv);
      const ciphertext = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
      const tag = cipher.getAuthTag();
      return Buffer.concat([iv, tag, ciphertext]);
    },
    async decrypt(ciphertext) {
      if (!(await probeKeytar())) {
        throw new Error(
          "Armazenamento seguro indisponível (Secret Service/KWallet). Desbloqueie o chaveiro e tente de novo.",
        );
      }
      const buf = Buffer.from(ciphertext);
      if (buf.length < 28) {
        throw new Error("Ciphertext inválido.");
      }
      const iv = buf.subarray(0, 12);
      const tag = buf.subarray(12, 28);
      const data = buf.subarray(28);
      const key = await loadOrCreateKey();
      const decipher = createDecipheriv("aes-256-gcm", key, iv);
      decipher.setAuthTag(tag);
      return Buffer.concat([decipher.update(data), decipher.final()]).toString("utf8");
    },
  };
}

/** In-memory provider for automated tests only — never used by the CLI path. */
export function createMemoryCredentialEncryption(seed = "ryoku-test-key-32-bytes-exact!!") {
  const key = Buffer.from(seed).subarray(0, 32);
  return {
    id: "memory-test-aes-gcm-v1",
    isAvailable() {
      return true;
    },
    encrypt(plaintext) {
      const iv = randomBytes(12);
      const cipher = createCipheriv("aes-256-gcm", key, iv);
      const ciphertext = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
      const tag = cipher.getAuthTag();
      return Buffer.concat([iv, tag, ciphertext]);
    },
    decrypt(ciphertext) {
      const buf = Buffer.from(ciphertext);
      const iv = buf.subarray(0, 12);
      const tag = buf.subarray(12, 28);
      const data = buf.subarray(28);
      const decipher = createDecipheriv("aes-256-gcm", key, iv);
      decipher.setAuthTag(tag);
      return Buffer.concat([decipher.update(data), decipher.final()]).toString("utf8");
    },
  };
}
