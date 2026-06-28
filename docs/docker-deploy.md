# Docker 上线部署指南

这套部署方式适合一台 Ubuntu 云服务器：Docker 运行应用，Caddy 自动配置 HTTPS。

## 1. 准备服务器

建议配置：

- 最低：2 核 4G，适合只用字幕总结和普通下载。
- 推荐：4 核 8G，如果要启用 Whisper 语音转写会更稳。
- 系统：Ubuntu 22.04 或 Ubuntu 24.04。

先把域名解析到服务器公网 IP：

```text
类型：A
主机记录：video
记录值：你的服务器公网 IP
```

例如最终访问地址是 `https://video.example.com`。

## 2. 安装 Docker

登录服务器后执行：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

退出 SSH 后重新登录，让 Docker 用户组生效。

验证：

```bash
docker version
docker compose version
```

## 3. 上传项目

任选一种方式：

```bash
git clone <你的仓库地址> free_video_downloader
cd free_video_downloader
```

如果还没放到 Git，也可以用压缩包上传到服务器后解压。

## 4. 配置环境变量

复制示例配置：

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
nano .env
```

至少修改这些：

```env
DOMAIN=video.example.com
AUTH_USERNAME=player
AUTH_PASSWORD=295056
AUTH_COOKIE_SECURE=1
DEEPSEEK_API_KEY=你的 DeepSeek Key
```

如果暂时不想启用无字幕转写，可以设置：

```env
ENABLE_ASR=0
```

## 5. 配置 Bilibili cookies

如果需要解析 B 站登录后字幕、高清或会员内容，把 Netscape 格式 cookies 放到：

```bash
backend/cookies.txt
```

如果没有 cookies，也先创建一个空文件，避免 Docker 挂载报错：

```bash
touch backend/cookies.txt
```

## 6. 启动服务

在项目根目录执行：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f app
docker compose logs -f caddy
```

## 7. 验收

打开：

```text
https://你的域名
```

用 `.env` 里的账号密码登录。

接口健康检查：

```bash
curl https://你的域名/api/health
```

正常返回：

```json
{"status":"ok"}
```

## 8. 后续更新

以后代码更新后，在服务器项目目录执行：

```bash
git pull
docker compose up -d --build
```

如果只改了 `.env` 或 cookies：

```bash
docker compose restart app
```

## 常见问题

如果 HTTPS 证书申请失败，先检查：

- 域名 A 记录是否已经解析到服务器 IP。
- 云服务器安全组是否开放 80 和 443 端口。
- 服务器防火墙是否放行 80 和 443。

如果登录后马上又回到登录页，检查：

- 线上必须用 `https://` 访问。
- `.env` 中 `AUTH_COOKIE_SECURE=1` 只允许 HTTPS 发送 Cookie。
- 如果只是用服务器 IP 测试，可以临时设为 `AUTH_COOKIE_SECURE=0` 并重启。

如果无字幕视频总结很慢或失败：

- `ENABLE_ASR=1` 会启用 Whisper，本地 CPU 转写会比较慢。
- 第一次使用会下载模型，国内网络建议保留 `HF_ENDPOINT=https://hf-mirror.com`。
- 服务器内存较小可以把 `WHISPER_MODEL=small` 改成 `base` 或 `tiny`。
