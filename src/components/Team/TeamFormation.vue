<template>
  <div class="status-card team-formation-card">
    <div class="card-header">
      <img
        alt="阵容"
        class="icon"
        src="/icons/Ob7pyorzmHiJcbab2c25af264d0758b527bc1b61cc3b.png"
      >
      <div class="info">
        <h3>阵容</h3>
        <p>当前使用的战斗阵容</p>
      </div>
      <div class="team-selector">
        <button
          v-for="teamId in availableTeams"
          :key="teamId"
          class="team-button"
          :class="[{ active: currentTeam === teamId }]"
          :disabled="loading || switching"
          @click="selectTeam(teamId)"
        >
          {{ teamId }}
        </button>
        <button
          class="refresh-button"
          title="刷新队伍数据"
          :disabled="loading"
          @click="refreshTeamData(true)"
        >
          <svg
            class="refresh-icon"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
            <path d="M21 3v5h-5" />
            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
            <path d="M3 21v-5h5" />
          </svg>
          <span class="refresh-text">刷新</span>
        </button>
      </div>
    </div>

    <div class="card-content">
      <div class="current-team-info">
        <span class="label">当前阵容</span>
        <span class="team-number">
          <template v-if="!loading">阵容 {{ currentTeam }}</template>
          <template v-else>加载中…</template>
        </span>
      </div>

      <div class="heroes-container">
        <div v-if="!loading" class="heroes-formation">
          <!-- 前排 2个 -->
          <div class="formation-row front-row">
            <div
              v-for="hero in currentTeamHeroes.slice(0, 2)"
              :key="hero.id || hero.name"
              class="hero-item"
            >
              <div class="hero-circle">
                <img
                  v-if="hero.avatar"
                  class="hero-avatar"
                  :alt="hero.name"
                  :src="hero.avatar"
                >
                <div v-else class="hero-placeholder">
                  {{ hero.name?.substring(0, 2) || "?" }}
                </div>
              </div>
              <span class="hero-name">{{ hero.name || "未知" }}</span>
            </div>
          </div>
          <!-- 后排 3个 -->
          <div class="formation-row back-row">
            <div
              v-for="hero in currentTeamHeroes.slice(2)"
              :key="hero.id || hero.name"
              class="hero-item"
            >
              <div class="hero-circle">
                <img
                  v-if="hero.avatar"
                  class="hero-avatar"
                  :alt="hero.name"
                  :src="hero.avatar"
                >
                <div v-else class="hero-placeholder">
                  {{ hero.name?.substring(0, 2) || "?" }}
                </div>
              </div>
              <span class="hero-name">{{ hero.name || "未知" }}</span>
            </div>
          </div>
        </div>

        <div v-if="!loading && !currentTeamHeroes.length" class="empty-team">
          <p>暂无队伍信息</p>
        </div>
        <div v-if="loading" class="empty-team">
          <p>正在加载队伍信息…</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useMessage } from "naive-ui";
import { computed, onMounted, ref, watch } from "vue";

import { useTokenStore } from "@/stores/tokenStore";

const tokenStore = useTokenStore();
const message = useMessage();

const loading = ref(false);
const switching = ref(false);
const currentTeam = ref(1);
const availableTeams = ref<number[]>([1, 2, 3, 4]);

const HERO_DICT: Record<
  number,
  { name: string; type: string; avatar?: string }
> = {
  101: { name: "司马懿", type: "魏国", avatar: "/team/simayi.png" },
  102: { name: "郭嘉", type: "魏国", avatar: "/team/guojia.png" },
  103: { name: "关羽", type: "蜀国", avatar: "/team/guanyu.png" },
  104: { name: "诸葛亮", type: "蜀国", avatar: "/team/zhugeliang.png" },
  105: { name: "周瑜", type: "吴国", avatar: "/team/zhouyu.png" },
  106: { name: "太史慈", type: "吴国", avatar: "/team/taishici.png" },
  107: { name: "吕布", type: "群雄", avatar: "/team/lvbu.png" },
  108: { name: "华佗", type: "群雄", avatar: "/team/huatuo.png" },
  109: { name: "甄姬", type: "魏国", avatar: "/team/zhenji.png" },
  110: { name: "黄月英", type: "蜀国", avatar: "/team/huangyueying.png" },
  111: { name: "孙策", type: "吴国", avatar: "/team/sunce.png" },
  112: { name: "贾诩", type: "群雄", avatar: "/team/jiaxu.png" },
  113: { name: "曹仁", type: "魏国", avatar: "/team/caoren.png" },
  114: { name: "姜维", type: "蜀国", avatar: "/team/jiangwei.png" },
  115: { name: "孙坚", type: "吴国", avatar: "/team/sunjian.png" },
  116: { name: "公孙瓒", type: "群雄", avatar: "/team/gongsunzan.png" },
  117: { name: "典韦", type: "魏国", avatar: "/team/dianwei.png" },
  118: { name: "赵云", type: "蜀国", avatar: "/team/zhaoyun.png" },
  119: { name: "大乔", type: "吴国", avatar: "/team/daqiao.png" },
  120: { name: "张角", type: "群雄", avatar: "/team/zhangjiao.png" },
  201: { name: "徐晃", type: "魏国", avatar: "/team/xuhuang.png" },
  202: { name: "荀彧", type: "魏国", avatar: "/team/xunyu.png" },
  203: { name: "典韦", type: "魏国", avatar: "/team/xiaodianwei.png" },
  204: { name: "张飞", type: "蜀国", avatar: "/team/zhangfei.png" },
  205: { name: "赵云", type: "蜀国", avatar: "/team/xiaozhaoyun.png" },
  206: { name: "庞统", type: "蜀国", avatar: "/team/pangtong.png" },
  207: { name: "鲁肃", type: "吴国", avatar: "/team/lusu.png" },
  208: { name: "陆逊", type: "吴国", avatar: "/team/luxun.png" },
  209: { name: "甘宁", type: "吴国", avatar: "/team/ganning.png" },
  210: { name: "貂蝉", type: "群雄", avatar: "/team/diaochan.png" },
  211: { name: "董卓", type: "群雄", avatar: "/team/dongzhuo.png" },
  212: { name: "张角", type: "群雄", avatar: "/team/xiaozhangjiao.png" },
  213: { name: "张辽", type: "魏国", avatar: "/team/zhangliao.png" },
  214: { name: "夏侯惇", type: "魏国", avatar: "/team/xiahoudun.png" },
  215: { name: "许褚", type: "魏国", avatar: "/team/xuzhu.png" },
  216: { name: "夏侯渊", type: "魏国", avatar: "/team/xiahouyuan.png" },
  217: { name: "魏延", type: "蜀国", avatar: "/team/weiyan.png" },
  218: { name: "黄忠", type: "蜀国", avatar: "/team/huangzhong.png" },
  219: { name: "马超", type: "蜀国", avatar: "/team/machao.png" },
  220: { name: "马岱", type: "蜀国", avatar: "/team/madai.png" },
  221: { name: "吕蒙", type: "吴国", avatar: "/team/lvmeng.png" },
  222: { name: "黄盖", type: "吴国", avatar: "/team/huanggai.png" },
  223: { name: "蔡文姬", type: "魏国", avatar: "/team/caiwenji.png" },
  224: { name: "小乔", type: "吴国", avatar: "/team/xiaoqiao.png" },
  225: { name: "袁绍", type: "群雄", avatar: "/team/yuanshao.png" },
  226: { name: "华雄", type: "群雄", avatar: "/team/huaxiong.png" },
  227: { name: "颜良", type: "群雄", avatar: "/team/yanliang.png" },
  228: { name: "文丑", type: "群雄", avatar: "/team/wenchou.png" },
  301: { name: "周泰", type: "吴国", avatar: "/team/zhoutai.png" },
  302: { name: "许攸", type: "魏国", avatar: "/team/xuyou.png" },
  303: { name: "于禁", type: "魏国", avatar: "/team/yujin.png" },
  304: { name: "张星彩", type: "蜀国", avatar: "/team/zhangxingcai.png" },
  305: { name: "关银屏", type: "蜀国", avatar: "/team/guanyinping.png" },
  306: { name: "关平", type: "蜀国", avatar: "/team/guanping.png" },
  307: { name: "程普", type: "吴国", avatar: "/team/chengpu.png" },
  308: { name: "张昭", type: "吴国", avatar: "/team/zhangzhao.png" },
  309: { name: "陆绩", type: "吴国", avatar: "/team/luji.png" },
  310: { name: "吕玲绮", type: "群雄", avatar: "/team/lvlingqi.png" },
  311: { name: "潘凤", type: "群雄", avatar: "/team/panfeng.png" },
  312: { name: "邢道荣", type: "群雄", avatar: "/team/xingdaorong.png" },
  313: { name: "祝融夫人", type: "群雄", avatar: "/team/zhurongfuren.png" },
  314: { name: "孟获", type: "群雄", avatar: "/team/menghuo.png" },
};

const wsStatus = computed(() => {
  if (!tokenStore.selectedToken)
    return "disconnected";
  return tokenStore.getWebSocketStatus(tokenStore.selectedToken.id);
});

const presetTeamRaw = computed(() => tokenStore.gameData?.presetTeam ?? null);

function normalizePresetTeam(raw: any) {
  if (!raw) {
    return {
      useTeamId: 1,
      teams: {} as Record<number, { teamInfo: Record<string, any> }>,
    };
  }
  const root = raw.presetTeamInfo ?? raw;
  const findUseIdRec = (obj: any): number | null => {
    if (!obj || typeof obj !== "object")
      return null;
    if (typeof obj.useTeamId === "number")
      return obj.useTeamId;
    for (const k of Object.keys(obj)) {
      const v = findUseIdRec(obj[k]);
      if (v)
        return v;
    }
    return null;
  };
  const useTeamId
    = root.useTeamId ?? root.presetTeamInfo?.useTeamId ?? findUseIdRec(root) ?? 1;

  const dict = root.presetTeamInfo ?? root;
  const teams: Record<number, { teamInfo: Record<string, any> }> = {};
  const ids = Object.keys(dict || {}).filter((k) => /^\d+$/.test(k));
  for (const idStr of ids) {
    const id = Number(idStr);
    const node = dict[idStr];
    if (!node) {
      teams[id] = { teamInfo: {} };
      continue;
    }
    if (node.teamInfo) {
      teams[id] = { teamInfo: node.teamInfo };
    } else if (node.heroes) {
      const ti: Record<string, any> = {};
      node.heroes.forEach((h: any, idx: number) => {
        ti[String(idx + 1)] = h;
      });
      teams[id] = { teamInfo: ti };
    } else if (typeof node === "object") {
      const hasHero = Object.values(node).some(
        (v: any) => v && typeof v === "object" && "heroId" in v,
      );
      teams[id] = { teamInfo: hasHero ? node : {} };
    } else {
      teams[id] = { teamInfo: {} };
    }
  }
  return { useTeamId: Number(useTeamId) || 1, teams };
}

const presetTeam = computed(() => normalizePresetTeam(presetTeamRaw.value));

const currentTeamHeroes = computed(() => {
  const team = (presetTeam.value.teams as any)[currentTeam.value]?.teamInfo;
  console.log("🚀 ~ team:", team);
  if (!team)
    return [] as any[];
  const heroes: any[] = [];
  for (const [pos, hero] of Object.entries(team)) {
    const hid = (hero as any)?.heroId ?? (hero as any)?.id;
    if (!hid)
      continue;
    const meta = HERO_DICT[Number(hid)];
    const avatarPath = meta?.avatar;
    const fullAvatarPath = avatarPath
      ? import.meta.env.BASE_URL + avatarPath.replace(/^\//, "")
      : undefined;
    heroes.push({
      id: Number(hid),
      name: meta?.name ?? `英雄${hid}`,
      type: meta?.type ?? "",
      position: Number(pos),
      level: (hero as any)?.level ?? 1,
      avatar: fullAvatarPath,
    });
  }
  heroes.sort((a, b) => a.position - b.position);
  console.log("🚀 ~ heroes:", heroes);
  return heroes;
});

const executeGameCommand = async (
  tokenId: string | number,
  cmd: string,
  params = {},
  description = "",
  timeout = 8000,
) => {
  try {
    return await tokenStore.sendMessageWithPromise(
      String(tokenId),
      cmd,
      params,
      timeout,
    );
  } catch (error: any) {
    if (description)
      message.error(`${description}失败：${error?.message ?? error}`);
    throw error;
  }
};

const getTeamInfoWithCache = async (force = false) => {
  if (!tokenStore.selectedToken) {
    message.warning("请先选择Token");
    return null;
  }
  const tokenId = tokenStore.selectedToken.id;
  if (!force) {
    const cached = (tokenStore.gameData as any)?.presetTeam?.presetTeamInfo;
    if (cached)
      return cached;
  }
  loading.value = true;
  try {
    const result = await executeGameCommand(
      tokenId,
      "presetteam_getinfo",
      {},
      "获取阵容信息",
    );
    tokenStore.$patch((state: any) => {
      state.gameData = { ...(state.gameData ?? {}), presetTeam: result };
    });
    return result?.presetTeamInfo ?? null;
  } catch (e) {
    console.error("获取阵容信息失败:", e);
    return null;
  } finally {
    loading.value = false;
  }
};

const updateAvailableTeams = () => {
  const ids = Object.keys(presetTeam.value.teams)
    .map(Number)
    .filter((n) => !Number.isNaN(n))
    .sort((a, b) => a - b);
  availableTeams.value = ids.length ? ids : [1, 2, 3, 4];
};
const updateCurrentTeam = () => {
  currentTeam.value = (presetTeam.value as any).useTeamId || 1;
};

const selectTeam = async (teamId: number) => {
  if (switching.value || loading.value)
    return;
  if (!tokenStore.selectedToken) {
    message.warning("请先选择Token");
    return;
  }
  const prev = currentTeam.value;
  switching.value = true;
  try {
    await executeGameCommand(
      tokenStore.selectedToken.id,
      "presetteam_saveteam",
      { teamId },
      `切换到阵容 ${teamId}`,
    );
    currentTeam.value = teamId;
    message.success(`已切换到阵容 ${teamId}`);
    await refreshTeamData(true);
  } catch {
    currentTeam.value = prev;
  } finally {
    switching.value = false;
  }
};

const refreshTeamData = async (force = false) => {
  await getTeamInfoWithCache(force);
};

onMounted(async () => {
  if (tokenStore.selectedToken && wsStatus.value === "connected") {
    await refreshTeamData(false);
    updateAvailableTeams();
    updateCurrentTeam();
    if (!presetTeamRaw.value) {
      await refreshTeamData(true);
      updateAvailableTeams();
      updateCurrentTeam();
    }
  }
});

watch(wsStatus, (newStatus, oldStatus) => {
  if (
    newStatus === "connected"
    && oldStatus !== "connected"
    && tokenStore.selectedToken
  ) {
    setTimeout(async () => {
      await refreshTeamData(false);
      updateAvailableTeams();
      updateCurrentTeam();
      if (!presetTeamRaw.value) {
        await refreshTeamData(true);
        updateAvailableTeams();
        updateCurrentTeam();
      }
    }, 1000);
  }
});

watch(
  () => tokenStore.selectedToken,
  async (newToken, oldToken) => {
    if (newToken && newToken.id !== (oldToken as any)?.id) {
      const status = tokenStore.getWebSocketStatus(newToken.id);
      if (status === "connected") {
        await refreshTeamData(true);
        updateAvailableTeams();
        updateCurrentTeam();
      }
    }
  },
);

watch(
  () => presetTeamRaw.value,
  () => {
    updateAvailableTeams();
    updateCurrentTeam();
  },
  { deep: true },
);
</script>

<style scoped lang="scss">
.team-formation-card {
  min-height: 220px;
}

.card-header {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.icon {
  width: 32px;
  height: 32px;
  object-fit: contain;
  flex-shrink: 0;
}

.info h3 {
  margin: 0 0 2px 0;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
}

.info p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.team-selector {
  display: flex;
  gap: var(--spacing-xs);
}

.team-button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.team-button:hover {
  background: var(--bg-secondary);
}

.team-button.active {
  background: var(--primary-color);
  color: white;
}

.team-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.refresh-button {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 8px;
  background: var(--bg-primary, #ffffff);
  color: var(--text-secondary, #6b7280);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast, 0.15s ease);
}

.refresh-button:hover {
  background: var(--bg-secondary, #f9fafb);
  border-color: var(--border-hover, #d1d5db);
  color: var(--text-primary, #374151);
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.refresh-button:active {
  transform: translateY(0);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.refresh-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.refresh-icon {
  width: 14px;
  height: 14px;
  transition: transform var(--transition-fast, 0.15s ease);
}

.refresh-button:not(:disabled):hover .refresh-icon {
  transform: rotate(180deg);
}

.refresh-button:disabled .refresh-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.card-content .current-team-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.card-content .label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.card-content .team-number {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
}

.heroes-container {
  background: var(--bg-tertiary);
  border-radius: var(--border-radius-medium);
  padding: var(--spacing-sm);
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.heroes-formation {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  align-items: center;
  width: 100%;
}

.formation-row {
  display: flex;
  gap: var(--spacing-lg);
  justify-content: center;
  width: 100%;
}

.hero-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 64px;
}

.hero-circle {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.hero-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero-placeholder {
  font-size: 12px;
  color: var(--text-secondary);
}

.hero-name {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  min-width: 90px;
  max-width: 140px;
  white-space: nowrap;
}

.empty-team {
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

@media (max-width: 768px) {
  .card-header {
    flex-direction: column;
    gap: var(--spacing-sm);
    text-align: center;
    align-items: center;
  }

  .team-selector {
    justify-content: center;
    flex-wrap: wrap;
    gap: var(--spacing-xs);
  }

  .heroes-container {
    padding: var(--spacing-sm);
  }

  .heroes-formation {
    gap: var(--spacing-sm);
  }

  .formation-row {
    gap: var(--spacing-sm);
  }

  .hero-item {
    min-width: 45px;
  }

  .hero-circle {
    width: 40px;
    height: 40px;
  }

  .hero-name {
    font-size: 10px;
    min-width: 0;
    max-width: 60px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
</style>
