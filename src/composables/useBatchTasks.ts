import { reactive, ref } from "vue";

import type { Ref } from "vue";

type RunType = "daily" | "cron";

interface LogEntry {
  time: string;
  message: string;
  type: string;
}

interface TokenItem {
  id: string;
  name?: string;
  token?: string;
}

interface ScheduledTask {
  id: string;
  name: string;
  runType: RunType;
  runTime: string | null;
  cronExpression: string;
  selectedTokens: string[];
  selectedTasks: string[];
  enabled: boolean;
  connectedTokens?: string[];
}

interface TaskFormState {
  name: string;
  runType: RunType;
  runTime: Date | string | number | undefined | null;
  cronExpression: string;
  selectedTokens: string[];
  selectedTasks: string[];
  enabled: boolean;
}

interface TaskOption {
  label: string;
  value: string;
}

interface MessageApi {
  warning: (msg: string) => void;
  success: (msg: string) => void;
}

interface UseBatchTasksOptions {
  tokens: Ref<TokenItem[]>;
  tokenStore: any;
  message: MessageApi;
  addLog: (entry: LogEntry) => void;
  resolveTaskFunction: (taskName: string) => unknown;
  storageKey?: string;
}

const DEFAULT_STORAGE_KEY = "scheduledTasks";

const AVAILABLE_TASKS: TaskOption[] = [
  { label: "日常任务", value: "startBatch" },
  { label: "领取挂机", value: "claimHangUpRewards" },
  { label: "一键加钟", value: "batchAddHangUpTime" },
  { label: "重置罐子", value: "resetBottles" },
  { label: "一键领取罐子", value: "batchlingguanzi" },
  { label: "一键爬塔", value: "climbTower" },
  { label: "一键答题", value: "batchStudy" },
  { label: "智能发车", value: "batchSmartSendCar" },
  { label: "一键收车", value: "batchClaimCars" },
  { label: "批量开箱", value: "batchOpenBox" },
  { label: "领取宝箱积分", value: "batchClaimBoxPointReward" },
  { label: "批量钓鱼", value: "batchFish" },
  { label: "批量招募", value: "batchRecruit" },
  { label: "一键宝库前3层", value: "batchbaoku13" },
  { label: "一键宝库4,5层", value: "batchbaoku45" },
  { label: "一键梦境", value: "batchmengjing" },
  { label: "一键俱乐部签到", value: "batchclubsign" },
  { label: "一键竞技场战斗3次", value: "batcharenafight" },
  { label: "一键钓鱼补齐", value: "batchTopUpFish" },
  { label: "一键竞技场补齐", value: "batchTopUpArena" },
  { label: "一键领取怪异塔免费道具", value: "batchClaimFreeEnergy" },
  { label: "一键购买四圣碎片", value: "legion_storebuygoods" },
  { label: "一键黑市采购", value: "store_purchase" },
  { label: "免费领取珍宝阁", value: "collection_claimfreereward" },
];

function nowTime(): string {
  return new Date().toLocaleTimeString();
}

function asTokenList(tokenStore: any, tokens: Ref<TokenItem[]>): TokenItem[] {
  const storeTokens = tokenStore?.gameTokens;
  if (Array.isArray(storeTokens) && storeTokens.length > 0) {
    return storeTokens;
  }
  return Array.isArray(tokens.value) ? tokens.value : [];
}

function resetTaskForm(taskForm: TaskFormState): void {
  Object.assign(taskForm, {
    name: "",
    runType: "daily",
    runTime: undefined,
    cronExpression: "",
    selectedTokens: [],
    selectedTasks: [],
    enabled: true,
  });
}

function validateCronExpression(expression: string): { valid: boolean; message: string } {
  if (!expression)
    return { valid: false, message: "Cron表达式不能为空" };

  const cronParts = expression.split(" ").filter(Boolean);
  if (cronParts.length !== 5) {
    return { valid: false, message: "Cron表达式必须包含5个字段：分 时 日 月 周" };
  }

  const [minute, hour, dayOfMonth, month, dayOfWeek] = cronParts;

  const validateCronField = (field: string, min: number, max: number, fieldName: string) => {
    // Safe cron field regex: matches *, */n, n, n-m, n,m,o, n-m/s, n/s
    // Avoids super-linear backtracking by using non-overlapping alternation only.
    const cronFieldRegex = /^(?:\*(?:\/\d+)?|\d+(?:-\d+)?(?:\/\d+)?(?:,\d+(?:-\d+)?(?:\/\d+)?)*)$/;
    if (!cronFieldRegex.test(field)) {
      return { valid: false, message: `${fieldName}字段格式错误` };
    }
    if (/^\d+$/.test(field)) {
      const num = Number.parseInt(field, 10);
      if (num < min || num > max) {
        return { valid: false, message: `${fieldName}字段必须在${min}-${max}之间` };
      }
    }
    return { valid: true, message: "" };
  };

  const minuteValidation = validateCronField(minute, 0, 59, "分钟");
  if (!minuteValidation.valid)
    return minuteValidation;

  const hourValidation = validateCronField(hour, 0, 23, "小时");
  if (!hourValidation.valid)
    return hourValidation;

  const dayOfMonthValidation = validateCronField(dayOfMonth, 1, 31, "日期");
  if (!dayOfMonthValidation.valid)
    return dayOfMonthValidation;

  const monthValidation = validateCronField(month, 1, 12, "月份");
  if (!monthValidation.valid)
    return monthValidation;

  const dayOfWeekValidation = validateCronField(dayOfWeek, 0, 7, "星期");
  if (!dayOfWeekValidation.valid)
    return dayOfWeekValidation;

  return { valid: true, message: "Cron表达式格式正确" };
}

export function useBatchTasks(options: UseBatchTasksOptions) {
  const {
    tokens,
    tokenStore,
    message,
    addLog,
    resolveTaskFunction,
    storageKey = DEFAULT_STORAGE_KEY,
  } = options;

  const scheduledTasks = ref<ScheduledTask[]>([]);
  const showTaskModal = ref(false);
  const showTasksModal = ref(false);
  const editingTask = ref<ScheduledTask | null>(null);
  const taskForm = reactive<TaskFormState>({
    name: "",
    runType: "daily",
    runTime: undefined,
    cronExpression: "",
    selectedTokens: [],
    selectedTasks: [],
    enabled: true,
  });

  const availableTasks = AVAILABLE_TASKS;

  const loadScheduledTasks = () => {
    try {
      const saved = localStorage.getItem(storageKey);
      if (!saved) {
        scheduledTasks.value = [];
        return;
      }
      const parsed = JSON.parse(saved);
      scheduledTasks.value = Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      console.error("Failed to load scheduled tasks:", error);
      scheduledTasks.value = [];
    }
  };

  const saveScheduledTasks = () => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(scheduledTasks.value));
    } catch (error) {
      console.error("Failed to save scheduled tasks:", error);
    }
  };

  const openTaskModal = () => {
    editingTask.value = null;
    resetTaskForm(taskForm);
    showTaskModal.value = true;
  };

  const editTask = (task: ScheduledTask) => {
    editingTask.value = task;
    const taskData: TaskFormState = { ...task };
    if (task.runType === "daily" && task.runTime && typeof task.runTime === "string") {
      const [hours, minutes] = task.runTime.split(":").map(Number);
      const now = new Date();
      taskData.runTime = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        hours,
        minutes,
      );
    }
    Object.assign(taskForm, taskData);
    showTaskModal.value = true;
  };

  const addTaskSaveLog = (task: ScheduledTask, isNew: boolean) => {
    addLog({
      time: nowTime(),
      message: `=== ${isNew ? "新增" : "修改"}定时任务: ${task.name} ===`,
      type: "info",
    });
    addLog({
      time: nowTime(),
      message: `运行类型: ${task.runType === "daily" ? "每天固定时间" : "Cron表达式"}`,
      type: "info",
    });
    addLog({
      time: nowTime(),
      message: `运行时间: ${task.runType === "daily" ? task.runTime : task.cronExpression}`,
      type: "info",
    });
    addLog({
      time: nowTime(),
      message: `选中账号: ${task.selectedTokens.length} 个`,
      type: "info",
    });
    addLog({
      time: nowTime(),
      message: `选中任务: ${task.selectedTasks.length} 个`,
      type: "info",
    });
    addLog({
      time: nowTime(),
      message: `状态: ${task.enabled ? "启用" : "禁用"}`,
      type: "info",
    });
  };

  const saveTask = () => {
    if (!taskForm.name.trim()) {
      message.warning("请输入任务名称");
      return;
    }

    if (taskForm.runType === "daily" && !taskForm.runTime) {
      message.warning("请选择运行时间");
      return;
    }

    if (taskForm.runType === "cron") {
      if (!taskForm.cronExpression.trim()) {
        message.warning("请输入Cron表达式");
        return;
      }
      const validation = validateCronExpression(taskForm.cronExpression);
      if (!validation.valid) {
        message.warning(validation.message);
        return;
      }
    }

    if (taskForm.selectedTokens.length === 0) {
      message.warning("请选择至少一个账号");
      return;
    }
    if (taskForm.selectedTasks.length === 0) {
      message.warning("请选择至少一个任务");
      return;
    }

    let formattedRunTime: string | null = null;
    if (taskForm.runType === "daily" && taskForm.runTime) {
      const time = new Date(taskForm.runTime);
      formattedRunTime = time.toLocaleTimeString("zh-CN", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
      });
    }

    const taskData: ScheduledTask = {
      id: editingTask.value?.id || `task_${Date.now()}`,
      name: taskForm.name.trim(),
      runType: taskForm.runType,
      runTime: formattedRunTime,
      cronExpression: taskForm.runType === "cron" ? taskForm.cronExpression.trim() : "",
      selectedTokens: [...taskForm.selectedTokens],
      selectedTasks: [...taskForm.selectedTasks],
      enabled: taskForm.enabled,
    };

    const isNew = !editingTask.value;
    if (editingTask.value) {
      const index = scheduledTasks.value.findIndex((t) => t.id === editingTask.value?.id);
      if (index !== -1) {
        scheduledTasks.value[index] = taskData;
      }
    } else {
      scheduledTasks.value.push(taskData);
    }

    saveScheduledTasks();
    addTaskSaveLog(taskData, isNew);
    showTaskModal.value = false;
    message.success("定时任务已保存");
  };

  const deleteTask = (taskId: string) => {
    const task = scheduledTasks.value.find((t) => t.id === taskId);
    if (!task)
      return;
    scheduledTasks.value = scheduledTasks.value.filter((t) => t.id !== taskId);
    saveScheduledTasks();
    addLog({
      time: nowTime(),
      message: `=== 定时任务 ${task.name} 已删除 ===`,
      type: "info",
    });
    message.success("定时任务已删除");
  };

  const toggleTaskEnabled = (taskId: string, enabled: boolean) => {
    const task = scheduledTasks.value.find((t) => t.id === taskId);
    if (!task)
      return;
    task.enabled = enabled;
    saveScheduledTasks();
    addLog({
      time: nowTime(),
      message: `=== 定时任务 ${task.name} 已${enabled ? "启用" : "禁用"} ===`,
      type: "info",
    });
    message.success(`定时任务已${enabled ? "启用" : "禁用"}`);
  };

  const resetRunType = () => {
    if (taskForm.runType === "daily") {
      taskForm.cronExpression = "";
    } else {
      taskForm.runTime = undefined;
    }
  };

  const selectAllTokens = () => {
    taskForm.selectedTokens = (tokens.value || []).map((token) => token.id);
  };

  const deselectAllTokens = () => {
    taskForm.selectedTokens = [];
  };

  const selectAllTasks = () => {
    taskForm.selectedTasks = availableTasks.map((task) => task.value);
  };

  const deselectAllTasks = () => {
    taskForm.selectedTasks = [];
  };

  const checkWebSocketWithRetry = async (
    tokenId: string,
    maxRetries = 3,
    retryDelay = 1000,
  ): Promise<boolean> => {
    for (let i = 0; i < maxRetries; i += 1) {
      const status = tokenStore?.getWebSocketStatus?.(tokenId);
      if (status === "connected")
        return true;

      const tokenList = asTokenList(tokenStore, tokens);
      const tokenName = tokenList.find((t) => t.id === tokenId)?.name || tokenId;

      try {
        addLog({
          time: nowTime(),
          message: `⏳ 账号 ${tokenName} WebSocket未连接，尝试手动连接... (${i + 1}/${maxRetries})`,
          type: "warning",
        });

        const token = tokenList.find((t) => t.id === tokenId);
        if (!token?.token) {
          addLog({
            time: nowTime(),
            message: `⚠️  账号 ${tokenName} 缺少token信息，无法尝试手动连接`,
            type: "warning",
          });
          break;
        }

        if (typeof tokenStore?.createWebSocketConnection === "function") {
          tokenStore.createWebSocketConnection(tokenId, token.token);
        } else if (typeof tokenStore?.selectToken === "function") {
          tokenStore.selectToken(tokenId, true);
        }

        await new Promise((resolve) => setTimeout(resolve, retryDelay));
      } catch (error: any) {
        addLog({
          time: nowTime(),
          message: `❌ 账号 ${tokenName} 尝试手动连接失败: ${error?.message || String(error)}`,
          type: "error",
        });
        await new Promise((resolve) => setTimeout(resolve, retryDelay));
      }
    }

    return tokenStore?.getWebSocketStatus?.(tokenId) === "connected";
  };

  const verifyTaskDependencies = async (task: ScheduledTask) => {
    addLog({
      time: nowTime(),
      message: `=== 开始验证定时任务 ${task.name} 的依赖 ===`,
      type: "info",
    });

    try {
      localStorage.setItem("test", "test");
      localStorage.removeItem("test");
      addLog({
        time: nowTime(),
        message: "✅ localStorage可用",
        type: "info",
      });
    } catch (error: any) {
      addLog({
        time: nowTime(),
        message: `❌ localStorage不可用: ${error?.message || String(error)}`,
        type: "error",
      });
      return false;
    }

    if (!tokenStore || !tokenStore.gameTokens) {
      addLog({
        time: nowTime(),
        message: "❌ Token存储不可用",
        type: "error",
      });
      return false;
    }

    for (const taskName of task.selectedTasks) {
      const taskFunction = resolveTaskFunction(taskName);
      if (typeof taskFunction !== "function") {
        addLog({
          time: nowTime(),
          message: `❌ 任务函数不存在: ${taskName}`,
          type: "error",
        });
        return false;
      }
    }

    const connectedTokens: Array<{ id: string; name: string }> = [];
    const disconnectedTokens: Array<{ id: string; name: string }> = [];
    const tokenList = asTokenList(tokenStore, tokens);

    for (const tokenId of task.selectedTokens) {
      const tokenName = tokenList.find((t) => t.id === tokenId)?.name || tokenId;
      const isConnected = await checkWebSocketWithRetry(tokenId);
      if (isConnected) {
        connectedTokens.push({ id: tokenId, name: tokenName });
      } else {
        disconnectedTokens.push({ id: tokenId, name: tokenName });
      }
    }

    if (connectedTokens.length > 0) {
      addLog({
        time: nowTime(),
        message: `✅ 已连接账号: ${connectedTokens.map((t) => t.name).join(", ")}`,
        type: "info",
      });
    }
    if (disconnectedTokens.length > 0) {
      addLog({
        time: nowTime(),
        message: `⚠️  未连接账号: ${disconnectedTokens.map((t) => t.name).join(", ")}`,
        type: "warning",
      });
    }

    if (connectedTokens.length === 0) {
      addLog({
        time: nowTime(),
        message: `=== 定时任务 ${task.name} 没有可用的连接账号，取消执行 ===`,
        type: "error",
      });
      return false;
    }

    task.connectedTokens = connectedTokens.map((t) => t.id);
    addLog({
      time: nowTime(),
      message: `=== 定时任务 ${task.name} 的依赖验证通过，将执行 ${connectedTokens.length} 个账号 ===`,
      type: "success",
    });
    return true;
  };

  loadScheduledTasks();

  return {
    scheduledTasks,
    showTaskModal,
    showTasksModal,
    editingTask,
    taskForm,
    availableTasks,
    loadScheduledTasks,
    saveScheduledTasks,
    openTaskModal,
    editTask,
    saveTask,
    deleteTask,
    toggleTaskEnabled,
    resetRunType,
    selectAllTokens,
    deselectAllTokens,
    selectAllTasks,
    deselectAllTasks,
    verifyTaskDependencies,
  };
}
