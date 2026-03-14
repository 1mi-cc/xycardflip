// Lightweight IndexedDB wrapper for token persistence with at-rest encryption.

const DB_NAME = "xyzw_token_db";
const DB_VERSION = 1;
const STORE_KV = "kv";
const STORE_GAME_TOKENS = "gameTokens";

const ENC_VERSION = 1;
const IS_DEV
  = typeof import.meta !== "undefined"
    && import.meta.env
    && Boolean(import.meta.env.DEV);
const DEV_FALLBACK_SECRET = "dev-token-encryption-secret";
const ENV_SECRET
  = (typeof import.meta !== "undefined"
    && import.meta.env
    && String(import.meta.env.VITE_TOKEN_ENCRYPTION_SECRET || "").trim())
  || "";
const ENC_SECRET = ENV_SECRET || (IS_DEV ? DEV_FALLBACK_SECRET : "");

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_KV)) {
        db.createObjectStore(STORE_KV, { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains(STORE_GAME_TOKENS)) {
        db.createObjectStore(STORE_GAME_TOKENS, { keyPath: "roleId" });
      }
    };

    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore(storeName, mode, fn) {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    const result = fn(store);
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

function bytesToBase64(bytes) {
  let binary = "";
  const view = new Uint8Array(bytes);
  for (let i = 0; i < view.byteLength; i += 1) {
    binary += String.fromCharCode(view[i]);
  }
  return btoa(binary);
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    out[i] = binary.charCodeAt(i);
  }
  return out;
}

async function deriveAesKey(saltBytes) {
  if (!ENC_SECRET) {
    throw new Error(
      "VITE_TOKEN_ENCRYPTION_SECRET is required in production for token encryption.",
    );
  }
  const secretBytes = textEncoder.encode(String(ENC_SECRET));
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    secretBytes,
    { name: "PBKDF2" },
    false,
    ["deriveKey"],
  );
  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: saltBytes,
      iterations: 120000,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

async function encryptPayload(value) {
  if (!crypto?.subtle)
    return value;
  try {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const key = await deriveAesKey(salt);
    const plaintext = textEncoder.encode(JSON.stringify(value));
    const cipher = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv },
      key,
      plaintext,
    );
    return {
      __enc__: true,
      v: ENC_VERSION,
      salt: bytesToBase64(salt),
      iv: bytesToBase64(iv),
      data: bytesToBase64(cipher),
    };
  } catch (error) {
    if (IS_DEV) {
      console.warn("Token encryption failed in dev mode, fallback to plaintext:", error);
      return value;
    }
    console.error("Token encryption failed in production:", error);
    throw error;
  }
}

async function decryptPayload(value) {
  if (!value || typeof value !== "object" || !value.__enc__) {
    return value;
  }
  if (!crypto?.subtle) {
    return undefined;
  }
  try {
    const salt = base64ToBytes(String(value.salt || ""));
    const iv = base64ToBytes(String(value.iv || ""));
    const cipher = base64ToBytes(String(value.data || ""));
    const key = await deriveAesKey(salt);
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, cipher);
    return JSON.parse(textDecoder.decode(plain));
  } catch (error) {
    console.warn("Token decryption failed:", error);
    return undefined;
  }
}

// KV helpers
export async function getKV(key) {
  const result = await withStore(STORE_KV, "readonly", (store) => {
    return new Promise((resolve, reject) => {
      const req = store.get(key);
      req.onsuccess = () => resolve(req.result ? req.result.value : undefined);
      req.onerror = () => reject(req.error);
    });
  });
  return decryptPayload(result);
}

export async function setKV(key, value) {
  const encrypted = await encryptPayload(value);
  return withStore(STORE_KV, "readwrite", (store) => {
    store.put({ key, value: encrypted });
  });
}

export async function deleteKV(key) {
  return withStore(STORE_KV, "readwrite", (store) => {
    store.delete(key);
  });
}

// User token
export async function getUserToken() {
  return getKV("userToken");
}
export async function setUserToken(token) {
  return setKV("userToken", token);
}
export async function clearUserToken() {
  return deleteKV("userToken");
}

// Game tokens (per role)
export async function getAllGameTokens() {
  const rows = await withStore(STORE_GAME_TOKENS, "readonly", (store) => {
    return new Promise((resolve, reject) => {
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  });

  const map = {};
  const decryptJobs = (rows || []).map(async (item) => {
    if (!item || !item.roleId)
      return;
    const roleId = item.roleId;
    const tokenData = await decryptPayload(item.payload ?? item);
    if (tokenData)
      map[roleId] = tokenData;
  });
  await Promise.all(decryptJobs);
  return map;
}

export async function putGameToken(roleId, tokenData) {
  const encryptedPayload = await encryptPayload({ ...tokenData, roleId });
  return withStore(STORE_GAME_TOKENS, "readwrite", (store) => {
    store.put({ roleId, payload: encryptedPayload });
  });
}

export async function deleteGameToken(roleId) {
  return withStore(STORE_GAME_TOKENS, "readwrite", (store) => {
    store.delete(roleId);
  });
}

export async function clearGameTokens() {
  return withStore(STORE_GAME_TOKENS, "readwrite", (store) => {
    store.clear();
  });
}

// Migration from localStorage for backward compatibility
export async function migrateFromLocalStorageIfNeeded() {
  try {
    const existing = await getAllGameTokens();
    const hasAny = existing && Object.keys(existing).length > 0;
    const userTok = await getUserToken();
    const hasUser = !!userTok;

    // If DB already has data, skip
    if (hasAny || hasUser)
      return { migrated: false };

    // Try migrate from localStorage
    const lsUser = localStorage.getItem("userToken");
    const lsGameTokensRaw = localStorage.getItem("gameTokens");
    let lsGameTokens = {};
    try {
      lsGameTokens = lsGameTokensRaw ? JSON.parse(lsGameTokensRaw) : {};
    } catch {
      lsGameTokens = {};
    }

    const lsHasAny
      = lsUser || (lsGameTokens && Object.keys(lsGameTokens).length > 0);
    if (!lsHasAny)
      return { migrated: false };

    if (lsUser)
      await setUserToken(lsUser);
    for (const [roleId, tokenData] of Object.entries(lsGameTokens || {})) {
      await putGameToken(roleId, tokenData);
    }

    return { migrated: true };
  } catch (e) {
    console.warn("Token DB migration skipped:", e);
    return { migrated: false, error: e?.message };
  }
}
