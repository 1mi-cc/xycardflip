import { reactive } from "vue";

export function useCardFlipOpsData() {
  const requestSeq = reactive({
    health: 0,
    overview: 0,
    automation: 0,
    autotrade: 0,
    executionRetry: 0,
    lists: 0,
    executionLogs: 0,
  });

  const nextRequestId = (key) => {
    requestSeq[key] = Number(requestSeq[key] || 0) + 1;
    return requestSeq[key];
  };

  const isLatestRequest = (key, requestId) =>
    Number(requestSeq[key] || 0) === Number(requestId || 0);

  const isBusyError = (error) =>
    Number(error?.status || 0) === 409 || Boolean(error?.payload?.busy);

  const normalizeText = (value) => {
    if (typeof value === "string") {
      const text = value.trim();
      return text && text !== "[object Object]" ? text : "";
    }
    if (Array.isArray(value)) {
      return value
        .map((item) => normalizeText(item))
        .filter(Boolean)
        .join("；");
    }
    if (!value || typeof value !== "object") {
      return "";
    }

    for (const key of ["detail", "message", "reason", "error", "msg"]) {
      const text = normalizeText(value[key]);
      if (text)
        return text;
    }

    const pairs = Object.entries(value)
      .map(([key, item]) => {
        const text = normalizeText(item);
        return text ? `${key}: ${text}` : "";
      })
      .filter(Boolean);
    return pairs.join("；");
  };

  const getErrorMessage = (error, fallback = "请求失败，请稍后重试") =>
    normalizeText(error?.payload)
    || normalizeText(error?.message)
    || fallback;

  return {
    nextRequestId,
    isLatestRequest,
    isBusyError,
    getErrorMessage,
  };
}

export default useCardFlipOpsData;
