/** Black Horse 2.0 — PM2 process map (Windows: pm2 start deploy_ops/pm2.ecosystem.config.cjs) */
const root = process.env.GOLDENSHIELD_OFFICIAL_ROOT || "C:\\GoldenShield_Binance";
const py = process.env.GS_PYTHON || "python";

module.exports = {
  apps: [
    {
      name: "GS-Gateway",
      script: "gateway_api/fast_router.py",
      interpreter: py,
      cwd: root,
      max_memory_restart: "500M",
      autorestart: true,
      env: {
        GOLDENSHIELD_OFFICIAL_ROOT: root,
        GATEWAY_API_PORT: process.env.GATEWAY_API_PORT || "8792",
        GS_ULTRA_LIVE_STREAM: process.env.GS_ULTRA_LIVE_STREAM || "true",
        GS_LIVE_INTERVAL_MS: process.env.GS_LIVE_INTERVAL_MS || "50",
      },
    },
    {
      name: "GS-NeuralCore",
      script: "core_engine/neural_matrix.py",
      interpreter: py,
      cwd: root,
      max_memory_restart: "500M",
      autorestart: true,
      env: {
        GOLDENSHIELD_OFFICIAL_ROOT: root,
        GS_SNAP_TTL_SEC: process.env.GS_SNAP_TTL_SEC || "8",
      },
    },
    {
      name: "GS-Tunnel",
      script: "deploy_ops/tunnel.py",
      interpreter: py,
      cwd: root,
      max_memory_restart: "500M",
      autorestart: true,
      env: { GOLDENSHIELD_OFFICIAL_ROOT: root },
    },
    {
      name: "GS-MobileApi",
      script: "-m",
      args: "terminal_app.server",
      interpreter: py,
      cwd: root,
      max_memory_restart: "500M",
      autorestart: true,
      env: {
        GOLDENSHIELD_OFFICIAL_ROOT: root,
        MOBILE_API_PORT: process.env.MOBILE_API_PORT || "8790",
        GS_ULTRA_LIVE_STREAM: process.env.GS_ULTRA_LIVE_STREAM || "true",
        GS_LIVE_INTERVAL_MS: process.env.GS_LIVE_INTERVAL_MS || "50",
        LIVE_PANEL_INTERVAL_SEC: process.env.LIVE_PANEL_INTERVAL_SEC || "0.05",
      },
    },
  ],
};
