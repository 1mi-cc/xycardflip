<template>
  <div class="docs-page">
    <section class="docs-hero">
      <div class="hero-copy">
        <span class="hero-kicker">Card Flip Manual</span>
        <h1>卡片倒卖使用文档</h1>
        <p>
          这是一份给第一次接触系统的人看的后台手册。建议的顺序是：
          先看模拟盘，再进入操作台调参，最后才考虑切到实战盘。
        </p>
        <div class="hero-tags">
          <n-tag round size="small" type="info">先模拟，再实战</n-tag>
          <n-tag round size="small" type="warning">先 dry-run，再 live</n-tag>
          <n-tag round size="small" type="success">按数字顺序一步一步做</n-tag>
        </div>
      </div>

      <div class="hero-actions">
        <n-button type="primary" @click="router.push('/admin/card-flip/sim')">
          打开模拟盘
        </n-button>
        <n-button secondary @click="router.push('/admin/card-flip-ops')">
          打开操作台
        </n-button>
        <n-button tertiary @click="router.push('/admin/card-flip/live')">
          打开实战盘
        </n-button>
      </div>
    </section>

    <div class="docs-layout">
      <aside class="docs-sidebar">
        <div class="sidebar-card toc-card">
          <div class="sidebar-title">目录</div>
          <button
            v-for="section in sectionLinks"
            :key="section.id"
            class="sidebar-link"
            type="button"
            :class="{ active: activeSection === section.id }"
            @click="scrollToSection(section.id)"
          >
            {{ section.title }}
          </button>
        </div>

        <div class="sidebar-card">
          <div class="sidebar-title">新手建议</div>
          <p>
            第一次使用时，只在“模拟盘”和“操作台”里活动。只要你还没完整走通一遍
            <code>dry-run</code>，就不要直接点任何带“实战”“live”“应用”的动作。
          </p>
        </div>

        <div class="sidebar-card warn-card">
          <div class="sidebar-title">一句话原则</div>
          <p>先看懂数据，再点按钮。先单次执行，再开后台循环。先小量验证，再放量。</p>
        </div>
      </aside>

      <article class="docs-content">
        <section id="what-is-card-flip" class="doc-section">
          <div class="section-kicker">01</div>
          <h2>卡片倒卖是干什么用的</h2>
          <p class="section-lead">
            它不是“保证你赚钱”的机器，而是把原本靠手工做的几件事放进一个后台：
            找机会、算利润、做演练、做执行、看日志、补失败。
          </p>

          <div class="card-grid two">
            <article v-for="item in coreJobs" :key="item.title" class="info-card">
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </article>
          </div>

          <n-alert show-icon class="doc-alert" type="warning" :bordered="false">
            这套系统负责辅助判断和执行流程，不替你承担市场风险。只要你还没完全看懂参数含义，
            就先待在模拟盘。
          </n-alert>
        </section>

        <section id="page-map" class="doc-section">
          <div class="section-kicker">02</div>
          <h2>三个页面分别怎么用</h2>

          <div class="card-grid three">
            <article v-for="page in pageCards" :key="page.title" class="info-card">
              <div class="page-head">
                <h3>{{ page.title }}</h3>
                <n-tag size="small" :type="page.tagType">{{ page.tag }}</n-tag>
              </div>
              <p>{{ page.description }}</p>
              <div class="bullet-list">
                <div v-for="point in page.points" :key="point" class="bullet-row">
                  {{ point }}
                </div>
              </div>
            </article>
          </div>
        </section>

        <section id="newbie-flow" class="doc-section">
          <div class="section-kicker">03</div>
          <h2>给新手的推荐使用流程</h2>
          <div class="step-list">
            <article v-for="step in newbieFlow" :key="step.index" class="step-card">
              <div class="step-index">{{ step.index }}</div>
              <div>
                <h3>{{ step.title }}</h3>
                <p>{{ step.description }}</p>
              </div>
            </article>
          </div>
        </section>

        <section id="sim-walkthrough" class="doc-section">
          <div class="section-kicker">04</div>
          <h2>模拟盘从零示范一遍</h2>
          <p class="section-lead">
            下列 4 步就是给完全不懂的人走的。数字就是建议的操作顺序，先照着做一遍，再去碰实战盘。
          </p>

          <div class="manual-list">
            <article v-for="step in simulationManual" :key="step.number" class="manual-card">
              <div class="manual-head">
                <div class="manual-index">{{ step.number }}</div>
                <div>
                  <h3>{{ step.title }}</h3>
                  <p>{{ step.description }}</p>
                </div>
              </div>

              <div class="shot-shell">
                <img class="shot-image" :alt="step.title" :src="step.image">
                <div
                  v-for="marker in step.markers"
                  :key="`${step.number}-${marker.label}`"
                  class="shot-marker"
                  :class="marker.tone ? `is-${marker.tone}` : ''"
                  :style="{ top: marker.top, left: marker.left }"
                >
                  {{ marker.label }}
                </div>
              </div>

              <div class="callout-grid">
                <div
                  v-for="callout in step.callouts"
                  :key="`${step.number}-${callout.label}`"
                  class="callout-card"
                >
                  <div class="callout-index">{{ callout.label }}</div>
                  <p>{{ callout.text }}</p>
                </div>
              </div>

              <div v-if="step.tip" class="step-tip">
                <strong>这一段最重要：</strong>
                <span>{{ step.tip }}</span>
              </div>
            </article>
          </div>
        </section>

        <section id="sim-to-live" class="doc-section">
          <div class="section-kicker">05</div>
          <h2>模拟盘转换成实战盘，需要改什么</h2>
          <p class="section-lead">
            从模拟盘切到实战盘，不是“换个页面”这么简单，而是要把几组关键参数从演练状态改成真实执行状态。
          </p>

          <n-alert show-icon class="doc-alert" type="error" :bordered="false">
            不要一次把所有开关全打开。正确做法是：先把真实执行条件配齐，再用“运行一次”只验证 1 条，
            最后才考虑开启后台循环。
          </n-alert>

          <div class="dictionary-table transition-table">
            <div class="dictionary-row header">
              <div>项目</div>
              <div>模拟盘时</div>
              <div>切实战前改成</div>
              <div>说明</div>
            </div>
            <div
              v-for="item in liveTransitionRows"
              :key="item.name"
              class="dictionary-row"
            >
              <div class="term">{{ item.name }}</div>
              <div>{{ item.simulation }}</div>
              <div>{{ item.live }}</div>
              <div>{{ item.tip }}</div>
            </div>
          </div>

          <div class="card-grid two">
            <article
              v-for="item in transitionWarnings"
              :key="item.title"
              class="info-card warning-card"
            >
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </article>
          </div>
        </section>

        <section id="key-params" class="doc-section">
          <div class="section-kicker">06</div>
          <h2>主要参数是什么意思</h2>
          <div
            v-for="group in parameterGroups"
            :key="group.title"
            class="dictionary-section"
          >
            <div class="dictionary-head">
              <h3>{{ group.title }}</h3>
              <p>{{ group.description }}</p>
            </div>

            <div class="dictionary-table">
              <div class="dictionary-row header">
                <div>参数</div>
                <div>它控制什么</div>
                <div>新手怎么理解</div>
              </div>
              <div
                v-for="item in group.items"
                :key="`${group.title}-${item.name}`"
                class="dictionary-row"
              >
                <div class="term">{{ item.name }}</div>
                <div>{{ item.meaning }}</div>
                <div>{{ item.tip }}</div>
              </div>
            </div>
          </div>
        </section>

        <section id="button-guide" class="doc-section">
          <div class="section-kicker">07</div>
          <h2>常用按钮是什么意思</h2>
          <div
            v-for="group in buttonGroups"
            :key="group.title"
            class="dictionary-section"
          >
            <div class="dictionary-head">
              <h3>{{ group.title }}</h3>
              <p>{{ group.description }}</p>
            </div>

            <div class="dictionary-table">
              <div class="dictionary-row header">
                <div>按钮</div>
                <div>作用</div>
                <div>什么时候点</div>
              </div>
              <div
                v-for="item in group.items"
                :key="`${group.title}-${item.name}`"
                class="dictionary-row"
              >
                <div class="term">{{ item.name }}</div>
                <div>{{ item.meaning }}</div>
                <div>{{ item.tip }}</div>
              </div>
            </div>
          </div>
        </section>

        <section id="faq" class="doc-section">
          <div class="section-kicker">08</div>
          <h2>注意事项与常见问题</h2>
          <div class="card-grid two">
            <article v-for="item in faqItems" :key="item.question" class="info-card">
              <h3>{{ item.question }}</h3>
              <p>{{ item.answer }}</p>
            </article>
          </div>
        </section>
      </article>
    </div>

    <button class="floating-toc-btn" type="button" @click="tocDrawerOpen = true">
      目录
    </button>

    <n-drawer placement="right" v-model:show="tocDrawerOpen" :width="320">
      <div class="drawer-toc">
        <div class="sidebar-title">目录</div>
        <button
          v-for="section in sectionLinks"
          :key="`drawer-${section.id}`"
          class="sidebar-link"
          type="button"
          :class="{ active: activeSection === section.id }"
          @click="handleDrawerJump(section.id)"
        >
          {{ section.title }}
        </button>
      </div>
    </n-drawer>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const tocDrawerOpen = ref(false);
const activeSection = ref("what-is-card-flip");
let observer;

const sectionLinks = [
  { id: "what-is-card-flip", title: "01 卡片倒卖是干什么的" },
  { id: "page-map", title: "02 三个页面怎么分工" },
  { id: "newbie-flow", title: "03 新手推荐流程" },
  { id: "sim-walkthrough", title: "04 模拟盘从零示范" },
  { id: "sim-to-live", title: "05 模拟转实战要改什么" },
  { id: "key-params", title: "06 参数解释" },
  { id: "button-guide", title: "07 按钮解释" },
  { id: "faq", title: "08 注意事项" },
];

const coreJobs = [
  {
    title: "找机会",
    description: "从候选卡片里找出可能有利润空间的机会，减少你盲目翻找的时间。",
  },
  {
    title: "做审批",
    description: "按你设定的评分、ROI、风险分和利润率，把不合格机会挡掉，只留下能继续走的。",
  },
  {
    title: "做演练",
    description: "先用 dry-run 和 mock 方式走流程，确认逻辑没问题，再决定是否转到真实执行。",
  },
  {
    title: "做追踪",
    description: "把执行日志、失败重试、待审核机会和进行中交易集中放在后台里统一查看。",
  },
];

const pageCards = [
  {
    title: "模拟盘",
    tag: "练习区",
    tagType: "info",
    description: "用来练手，看趋势、看策略是否持续触发。适合第一次接触系统的人。",
    points: [
      "看最近有没有模拟买入、模拟卖出。",
      "看数据趋势是否稳定，不要一开始就追求速度。",
      "这里最适合先观察，再学习参数。",
    ],
  },
  {
    title: "实战盘",
    tag: "复盘区",
    tagType: "error",
    description: "用来观察真实执行链路的结果。只有在你确认实盘链路安全后才建议长期使用。",
    points: [
      "看真实买入次数、卖出次数和成功率。",
      "看待审核机会是否堆积。",
      "看审批引擎是否持续运行。",
    ],
  },
  {
    title: "操作台",
    tag: "中控室",
    tagType: "warning",
    description: "用来发命令、调参数、审批买入、处理风控、重试失败记录，是整个系统最核心的页面。",
    points: [
      "扫描机会、审批机会、处理进行中交易。",
      "调整 AutoTrade、Automation、Retry 参数。",
      "查看执行日志，排查失败原因。",
    ],
  },
];

const newbieFlow = [
  {
    index: "1",
    title: "先确认 Token 和基础服务都正常",
    description: "先去 Token 管理页确认账户可用，然后再进入模拟盘和操作台。",
  },
  {
    index: "2",
    title: "先盯模拟盘，不急着做真实动作",
    description: "看最近 7 天或 14 天的数据，让自己知道系统到底在做什么。",
  },
  {
    index: "3",
    title: "去操作台把开关放在 dry-run / mock",
    description: "这一步是演练，不是赚钱，先学会看参数和日志。",
  },
  {
    index: "4",
    title: "先点一次运行，再看日志和待审核机会",
    description: "只有单次执行跑通、日志可读、结果合理，才考虑自动循环。",
  },
];

const simulationManual = [
  {
    number: "1",
    title: "先打开模拟盘看总趋势",
    description: "第一步先确认最近窗口内有没有模拟执行数据，以及买入次数是否持续触发。",
    image: "/docs/card-flip/sim-dashboard-overview.png",
    markers: [
      { label: "1", top: "12%", left: "22%" },
      { label: "2", top: "13%", left: "78%", tone: "info" },
      { label: "3", top: "78%", left: "20%", tone: "amber" },
    ],
    callouts: [
      { label: "1", text: "先看页面标题，确认你现在在“模拟盘”，不是实战盘。" },
      { label: "2", text: "看 KPI 卡片里的执行总次数、成功率、模拟买入次数。" },
      { label: "3", text: "如果图表完全没有数据，先别急着调实战参数，先回操作台做一次单次执行。" },
    ],
    tip: "模拟盘的作用是先看系统会不会动、怎么动，不是为了立刻做真实买卖。",
  },
  {
    number: "2",
    title: "进入操作台，先看总览和主操作",
    description: "第二步进入操作台，只看页头总览、健康提示和主操作，不要先展开所有参数。",
    image: "/docs/card-flip/ops-main-actions.png",
    markers: [
      { label: "1", top: "12%", left: "20%" },
      { label: "2", top: "16%", left: "72%", tone: "info" },
      { label: "3", top: "57%", left: "19%", tone: "amber" },
    ],
    callouts: [
      { label: "1", text: "先看总览卡和状态条，确认系统有没有明显的健康告警。" },
      { label: "2", text: "主按钮区优先用“运行一次”和局部刷新，不要一上来就启动后台循环。" },
      { label: "3", text: "服务卡下面的折叠区默认是低频调参区，不看懂前不要乱改。" },
    ],
    tip: "第一次用时，最重要的是“看状态 + 单次执行 + 看日志”，不是把每个按钮都点一遍。",
  },
  {
    number: "3",
    title: "把 AutoTrade 放在安全模式",
    description: "第三步检查审批引擎参数，确认仍然是 mock / dry-run / 自动买入关闭 这一类安全组合。",
    image: "/docs/card-flip/ops-autotrade-settings.png",
    markers: [
      { label: "1", top: "28%", left: "12%" },
      { label: "2", top: "28%", left: "39%", tone: "info" },
      { label: "3", top: "55%", left: "67%", tone: "amber" },
    ],
    callouts: [
      { label: "1", text: "执行通道先保持 mock，代表只演练，不走真实外部执行。" },
      { label: "2", text: "买入模式、上架模式先保持 dry-run，表示只试跑流程。" },
      { label: "3", text: "自动买入、自动上架一类开关先保持关闭，等你确认结果可靠后再说。" },
    ],
    tip: "如果你还在模拟盘阶段，宁可保守，也不要为了“看起来更像实战”过早打开真实动作。",
  },
  {
    number: "4",
    title: "执行一次，回看模拟盘和日志",
    description: "最后一步点击运行一次，然后返回模拟盘、执行日志和待审核机会，看系统到底做了什么。",
    image: "/docs/card-flip/ops-main-actions.png",
    markers: [
      { label: "1", top: "16%", left: "73%" },
      { label: "2", top: "88%", left: "15%", tone: "info" },
      { label: "3", top: "88%", left: "40%", tone: "amber" },
    ],
    callouts: [
      { label: "1", text: "点一次主操作后，不要马上重复点击，先等状态更新和日志返回。" },
      { label: "2", text: "到执行日志里看是否有成功、失败、busy 或风控拦截记录。" },
      { label: "3", text: "回到模拟盘看趋势有没有新增数据，再决定是否继续调参。" },
    ],
    tip: "如果一次运行后你仍然说不清系统刚刚做了什么，那就先别进入实战盘。",
  },
];

const liveTransitionRows = [
  {
    name: "执行通道",
    simulation: "mock",
    live: "webhook 或真实执行通道",
    tip: "mock 代表演练；切实战前要改成真实通道。",
  },
  {
    name: "买入模式",
    simulation: "dry-run",
    live: "live",
    tip: "dry-run 只演练；live 才会真的执行买入。",
  },
  {
    name: "上架模式",
    simulation: "dry-run",
    live: "live 或你的实盘模式",
    tip: "如果买入后要自动上架，这一项也要和真实链路一致。",
  },
  {
    name: "自动买入",
    simulation: "关闭",
    live: "视情况开启",
    tip: "第一次转实战时建议仍先关闭，先跑单次执行验证。",
  },
  {
    name: "自动上架",
    simulation: "关闭",
    live: "视情况开启",
    tip: "只有你确认卖出流程没问题，再考虑自动上架。",
  },
  {
    name: "ROI / 风险分",
    simulation: "可偏宽松，用于观察",
    live: "应更严格",
    tip: "实战阈值通常要更保守，避免把边缘机会也放过去。",
  },
];

const transitionWarnings = [
  {
    title: "先做一次单次执行",
    description: "参数改成实战后，不要立刻开自动循环，先单次执行验证 1 条链路是否正常。",
  },
  {
    title: "实战阈值要更保守",
    description: "评分、ROI、风险分、利润率下限都建议比模拟阶段更严格，减少误判。",
  },
];

const parameterGroups = [
  {
    title: "审批与执行参数",
    description: "这组参数决定系统是否批准一个机会，以及批准后怎么执行。",
    items: [
      {
        name: "最小评分",
        meaning: "机会评分低于这个值时，会被挡掉。",
        tip: "你可以把它理解成“至少要达到几分才值得继续看”。",
      },
      {
        name: "最小 ROI",
        meaning: "投资回报率低于阈值时，不建议继续做。",
        tip: "ROI 越高，说明利润相对成本越好；实战一般会比模拟更严格。",
      },
      {
        name: "最大风险分",
        meaning: "超过这个风险分的机会会被拦住。",
        tip: "风险分越高，说明不确定性越大；新手不要为了多出单而把它放太高。",
      },
      {
        name: "批量上限",
        meaning: "每轮最多处理多少条机会。",
        tip: "批量越大，动作越多，也越容易看不过来。第一次用建议保守。",
      },
    ],
  },
  {
    title: "价格与上架参数",
    description: "这组参数决定买入上限、上架利润率和卖出利润率。",
    items: [
      {
        name: "买入上限",
        meaning: "高于这个价格的机会不买。",
        tip: "你可以把它理解成“我最多肯出多少钱”。",
      },
      {
        name: "上架利润率",
        meaning: "买入后准备按多高的利润率挂出去。",
        tip: "如果太高，可能卖不动；太低，又没利润空间。",
      },
      {
        name: "卖出利润率",
        meaning: "控制何时接受卖出或判断是否值得卖出。",
        tip: "和上架利润率一起看，别只改其中一个。",
      },
      {
        name: "循环间隔",
        meaning: "后台每隔多久跑一次。",
        tip: "间隔太短会让系统一直忙；新手先用慢一点的节奏。",
      },
    ],
  },
];

const buttonGroups = [
  {
    title: "总控与服务按钮",
    description: "这些按钮决定后台服务是否运行，以及你是否要手动触发一次。",
    items: [
      {
        name: "启动",
        meaning: "开启某个服务的后台循环。",
        tip: "只有在参数确认无误、单次执行也跑通后，才建议使用。",
      },
      {
        name: "停止",
        meaning: "立即停止某个服务继续循环。",
        tip: "当你发现参数不对、状态异常或需要暂停排查时使用。",
      },
      {
        name: "刷新状态",
        meaning: "重新拉取当前服务状态和最新数据。",
        tip: "页面显示不确定时先点它，别先连点启动。",
      },
      {
        name: "运行一次",
        meaning: "只跑一轮流程，不进入持续循环。",
        tip: "这是新手最该用的按钮，适合单次验证。",
      },
    ],
  },
  {
    title: "调参与处理按钮",
    description: "这些按钮主要用于调整参数、审批机会和处理异常。",
    items: [
      {
        name: "快速调参",
        meaning: "直接改评分、ROI、风险分、批量等关键阈值。",
        tip: "一次只改一两项，改完就看结果，别一口气全动。",
      },
      {
        name: "单次审批 / 单次重试",
        meaning: "只对一个服务做一次动作，便于验证结果。",
        tip: "排查问题时优先用这一类按钮，不要直接开循环。",
      },
      {
        name: "执行日志",
        meaning: "查看最近执行记录、失败原因和 busy 提示。",
        tip: "页面看不懂时，先回日志，不要靠猜。",
      },
      {
        name: "风控拦截",
        meaning: "查看被风险规则挡掉的机会。",
        tip: "如果你觉得系统“怎么不买”，先看这里。",
      },
    ],
  },
];

const faqItems = [
  {
    question: "为什么模拟盘有数据，实战盘却没有？",
    answer: "因为模拟盘通常走 dry-run，实战盘只看真实执行结果。你还没切到真实执行链路时，实战盘为空很正常。",
  },
  {
    question: "为什么我不建议第一次就开自动买入？",
    answer: "因为你还没验证完整链路。先用 mock、dry-run 和单次执行看清楚系统在做什么，再决定是否开自动动作。",
  },
  {
    question: "看到 busy 提示怎么办？",
    answer: "说明当前已有任务在跑。不要连续狂点，等这轮执行结束，再刷新状态确认结果。",
  },
  {
    question: "参数太多，看不懂怎么办？",
    answer: "只先抓 4 个：最小评分、最小 ROI、最大风险分、循环间隔。其他的等你看懂基本流程后再慢慢加。",
  },
];

const scrollToSection = (id) => {
  const target = document.getElementById(id);
  if (!target)
    return;
  activeSection.value = id;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
};

const handleDrawerJump = (id) => {
  tocDrawerOpen.value = false;
  scrollToSection(id);
};

const setupSectionObserver = async () => {
  await nextTick();
  const root = document.querySelector(".page-container");
  const sections = sectionLinks
    .map((item) => document.getElementById(item.id))
    .filter(Boolean);

  if (!sections.length)
    return;
  observer?.disconnect();
  observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible[0]?.target?.id) {
        activeSection.value = visible[0].target.id;
      }
    },
    {
      root,
      rootMargin: "-12% 0px -55% 0px",
      threshold: [0.15, 0.35, 0.6],
    },
  );

  sections.forEach((section) => observer.observe(section));
};

onMounted(() => {
  void setupSectionObserver();
});

onBeforeUnmount(() => {
  observer?.disconnect();
});
</script>

<style scoped lang="scss">
.docs-page {
  display: grid;
  gap: 18px;
}

.docs-hero,
.doc-section,
.sidebar-card {
  border: 1px solid var(--border-light);
  background: var(--panel-bg);
  box-shadow: var(--shadow-light);
}

.docs-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 28px 30px;
  border-radius: 18px;
}

.hero-kicker,
.section-kicker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--primary-color-light);
  color: var(--primary-color);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.hero-copy h1 {
  margin: 14px 0 10px;
  font-size: clamp(30px, 3.2vw, 42px);
  line-height: 1.08;
  color: var(--text-primary);
}

.hero-copy p {
  max-width: 820px;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.85;
}

.hero-tags,
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-tags {
  margin-top: 16px;
}

.hero-actions {
  justify-content: flex-end;
}

.docs-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.docs-sidebar {
  position: sticky;
  top: 12px;
  display: grid;
  gap: 14px;
}

.sidebar-card {
  padding: 18px;
  border-radius: 16px;
}

.toc-card {
  max-height: calc(100vh - 110px);
  overflow: auto;
}

.sidebar-title {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-card p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.8;
}

.warn-card {
  background: linear-gradient(180deg, #fff9ec 0%, #ffffff 100%);
}

.sidebar-link {
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  text-align: left;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all var(--transition-fast);

  &:hover,
  &.active {
    background: var(--primary-color-light);
    color: var(--primary-color);
  }
}

.docs-content {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.doc-section {
  padding: 28px;
  border-radius: 18px;
}

.doc-section h2 {
  margin: 14px 0 10px;
  font-size: clamp(28px, 3vw, 38px);
  line-height: 1.08;
  color: var(--text-primary);
}

.section-lead {
  margin: 0 0 18px;
  font-size: 16px;
  line-height: 1.9;
  color: var(--text-secondary);
}

.doc-alert {
  margin-top: 20px;
}

.card-grid,
.step-list,
.callout-grid,
.manual-list {
  display: grid;
  gap: 16px;
}

.card-grid.two,
.callout-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.card-grid.three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.info-card,
.step-card,
.manual-card,
.callout-card {
  border: 1px solid var(--border-light);
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
}

.info-card,
.callout-card {
  padding: 18px;
}

.info-card h3,
.manual-card h3,
.step-card h3 {
  margin: 0 0 10px;
  color: var(--text-primary);
  font-size: 22px;
}

.info-card p,
.manual-card p,
.step-card p,
.callout-card p,
.dictionary-head p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.85;
}

.warning-card {
  background: linear-gradient(180deg, #fff8ec 0%, #ffffff 100%);
}

.page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.bullet-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.bullet-row {
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  line-height: 1.7;
}

.step-card {
  display: flex;
  gap: 16px;
  padding: 18px;
}

.step-index,
.manual-index,
.callout-index,
.shot-marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 999px;
  background: linear-gradient(180deg, #6fb8ff, #409eff);
  color: #ffffff;
  font-weight: 800;
  box-shadow: 0 12px 24px rgba(64, 158, 255, 0.24);
  flex: 0 0 auto;
}

.manual-card {
  padding: 22px;
}

.manual-head {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.manual-index {
  width: 52px;
  height: 52px;
  font-size: 16px;
}

.shot-shell {
  position: relative;
  overflow: hidden;
  margin-top: 16px;
  border-radius: 18px;
  border: 1px solid var(--border-light);
}

.shot-image {
  display: block;
  width: 100%;
  height: auto;
}

.shot-marker {
  position: absolute;
  width: 38px;
  height: 38px;
  font-size: 15px;
  transform: translate(-50%, -50%);
  border: 3px solid rgba(255, 255, 255, 0.94);
}

.shot-marker.is-info {
  background: linear-gradient(180deg, #67c23a, #529b2e);
}

.shot-marker.is-amber {
  background: linear-gradient(180deg, #f3c980, #e6a23c);
}

.callout-grid {
  margin-top: 18px;
}

.callout-card {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}

.callout-index {
  width: 34px;
  height: 34px;
  font-size: 14px;
}

.step-tip {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 14px;
  background: #fff7e6;
  color: #ad6800;
  line-height: 1.8;
}

.dictionary-section + .dictionary-section {
  margin-top: 20px;
}

.dictionary-head h3 {
  margin: 0 0 8px;
  font-size: 22px;
  color: var(--text-primary);
}

.dictionary-table {
  margin-top: 16px;
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-radius: 16px;
}

.dictionary-row {
  display: grid;
  grid-template-columns: 1.15fr 1.75fr 1.75fr;
  gap: 16px;
  padding: 16px 18px;
  background: #fff;
}

.transition-table .dictionary-row {
  grid-template-columns: 1fr 1.15fr 1.35fr 1.8fr;
}

.dictionary-row + .dictionary-row {
  border-top: 1px solid var(--border-light);
}

.dictionary-row.header {
  background: #f6f9fd;
  color: var(--text-primary);
  font-weight: 700;
}

.term {
  font-weight: 700;
  color: var(--text-primary);
}

.floating-toc-btn {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 20;
  padding: 12px 18px;
  border-radius: 999px;
  background: linear-gradient(135deg, #409eff, #337ecc);
  color: #fff;
  font-weight: 700;
  box-shadow: 0 18px 30px rgba(64, 158, 255, 0.28);
}

.drawer-toc {
  padding: 24px 20px;
}

code {
  padding: 2px 6px;
  border-radius: 8px;
  background: var(--primary-color-light);
  color: var(--primary-color);
}

@media (max-width: 1200px) {
  .docs-layout {
    grid-template-columns: 1fr;
  }

  .docs-sidebar {
    display: none;
  }

  .card-grid.three,
  .card-grid.two,
  .callout-grid,
  .transition-table .dictionary-row,
  .dictionary-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .docs-hero,
  .doc-section {
    padding: 22px;
  }

  .docs-hero {
    flex-direction: column;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .manual-head,
  .step-card,
  .callout-card {
    flex-direction: column;
  }

  .floating-toc-btn {
    right: 16px;
    bottom: 16px;
  }
}
</style>
