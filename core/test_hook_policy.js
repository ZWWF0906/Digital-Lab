// 测试钩子启用策略（生产安全边界，DL-SEC-02-B）
// 约定：只有“非打包环境 + 显式测试标志”才允许启用测试钩子。
// 该模块保持纯函数，便于在 Node 中直接验证打包/非打包两种条件。
function isTestHooksEnabled(isPackaged, flag) {
  return isPackaged !== true && flag === '1';
}

module.exports = { isTestHooksEnabled };
