/**
 * xyzw-token-manager 库入口
 *
 * 将核心工具以 ESM / UMD 包的形式导出，
 * 方便其他项目直接 import 使用，无需引入完整 SPA。
 *
 * @example
 * // ESM
 * import { bon, GameMessages, g_utils, XyzwWebSocketClient } from 'xyzw-token-manager'
 *
 * // 编码 BON 消息
 * const encoded = bon.encode({ hello: 'world' })
 * const decoded = bon.decode(encoded)
 *
 * // 创建 WebSocket 客户端
 * const client = new XyzwWebSocketClient({ url: 'wss://...', g_utils })
 */

// ---- BON 协议 ----
export {
  bon,
  BonDecoder,
  BonEncoder,
  bonProtocol,
  DataReader,
  DataWriter,
  encode,
  g_utils,
  GameMessages,
  getEnc,
  Int64,
  LXCrypto,
  parse,
  ProtoMsg,
  XCrypto,
  XTMCrypto,
} from "./utils/bonProtocol.js";

// ---- 游戏指令 ----
export {
  GameCommands,
  gameCommands,
  studyQuestions,
} from "./utils/gameCommands.js";

// ---- 日志 ----
export {
  createLogger,
  enableVerboseLogging,
  gameLogger,
  LOG_LEVELS,
  setGlobalLogLevel,
  tokenLogger,
  wsLogger,
} from "./utils/logger.js";

// ---- 低层级 WebSocket Agent ----
export { WsAgent } from "./utils/wsAgent.js";

// ---- WebSocket 客户端 ----
export {
  CommandRegistry,
  registerDefaultCommands,
  XyzwWebSocketClient,
} from "./utils/xyzwWebSocket.js";
