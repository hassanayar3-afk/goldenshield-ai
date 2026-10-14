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
      env: { GOLDENSHIELD_OFFICIAL_ROOT: root },
    },
    {
      name: "GS-NeuralCore",
      script: "core_engine/neural_matrix.py",
      interpreter: py,
      cwd: root,
      max_memory_restart: "500M",
      autorestart: true,
      env: { GOLDENSHIELD_OFFICIAL_ROOT: root },
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
      env: { GOLDENSHIELD_OFFICIAL_ROOT: root },
    },
  ],
};
