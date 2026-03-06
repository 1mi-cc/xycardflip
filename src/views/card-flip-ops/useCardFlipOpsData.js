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

  const isLatestRequest = (key, requestId) => Number(requestSeq[key] || 0) === Number(requestId || 0);

  const isBusyError = error => Number(error?.status || 0) === 409 || Boolean(error?.payload?.busy);

  const getErrorMessage = (error, fallback = "request failed") => (
    error?.payload?.message
    || error?.payload?.detail
    || error?.message
    || fallback
  );

  return {
    nextRequestId,
    isLatestRequest,
    isBusyError,
    getErrorMessage,
  };
}

export default useCardFlipOpsData;
