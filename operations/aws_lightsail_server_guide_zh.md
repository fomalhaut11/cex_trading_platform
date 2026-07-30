# AWS Lightsail 服务器租用与操作指南

Status: Funding Carry MVP 服务器准备基线。

Date: 2026-07-30.

本指南用于准备开发、离线验收、Testnet 和生产 Shadow 主机。它不授权
Binance Testnet、真实资金交易或自动化生产运行。

## 1. 合规前置条件

服务器地区和 VPN 出口不能改变账户持有人的所在地、KYC 信息或产品资格。
在配置生产 API 前，项目负责人必须通过 Binance 账户页面或官方客服确认：

- 当前真实居住地和 KYC 信息准确；
- 账户可以合法使用 Binance Spot、USD-M Futures 和相关 API；
- 账户没有依靠 VPN 或服务器地区绕过产品或地域限制；
- 账户能够正常创建所需的只读/Testnet/交易 API 权限。

如果无法确认，工作只能继续到离线验收和官方 Testnet，不得进入 A021
真实资金验收。

Binance 当前条款要求用户满足所在地法律和产品资格条件，并保持身份、
法定住所和居住地址信息真实、准确、最新：

`https://www.binance.com/en/terms`

## 2. 推荐服务器

推荐第一台主机：

| 项目 | 选择 |
|---|---|
| 云厂商 | Amazon Lightsail |
| Region | Asia Pacific (Singapore), `ap-southeast-1` |
| 系统 | Ubuntu 24.04 LTS，纯操作系统镜像 |
| 规格 | 2 vCPU / 4 GB RAM / 80 GB SSD |
| 网络 | Public IPv4 bundle + attached Static IPv4 |
| 月费 | USD 24/month，税费和快照另计 |
| 实例名 | `cex-quant-sg1` |
| Static IP 名 | `cex-quant-sg1-ip` |
| 自动快照 | 开启，保留平台默认最近七份 |

选择理由：

- 对单账户、单 BTC Carry MVP 足够；
- 价格简单，没有必要先建设 EC2、NAT Gateway、负载均衡或托管数据库；
- Singapore Region 可用；
- 固定 IP 随实例套餐提供，绑定实例时不另收费；
- 可以通过 Lightsail 防火墙分别限制 IPv4 和 IPv6 入站访问。

官方价格和功能：

- `https://aws.amazon.com/lightsail/pricing/`
- `https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-static-ip-addresses-in-amazon-lightsail.html`
- `https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html`

自动快照按实际存储计费，目前为 USD 0.05/GB-month。固定 IP 从实例解绑
超过免费宽限时间后可能产生费用，因此不要保留未绑定的闲置 Static IP。

## 3. 购买边界

云账号注册、实名/企业验证、付款方式、MFA 和最终付费确认必须由项目负责人
完成。Codex 可以在账号登录后协助页面选择、服务器加固和项目部署，但不得：

- 保存支付卡信息；
- 接收 AWS root 密码或 MFA 恢复码；
- 接收 Binance API Secret；
- 在没有价格确认时创建额外付费资源；
- 把生产服务器当作已经获得真实交易授权。

当前建议预算：

```text
Lightsail instance        USD 24/month
Attached static IPv4      included
Snapshot storage          usage based
Expected initial total    about USD 25-30/month before tax
```

## 4. AWS 账号准备

1. 使用项目负责人自己的邮箱注册 AWS Global 账号。
2. 给 root 用户开启 MFA。
3. 不共享 root 密码、MFA 种子或恢复码。
4. 设置月度预算告警，建议第一档 USD 35，第二档 USD 50。
5. 日常操作使用受限 IAM 管理身份，不长期使用 root。
6. 记录 AWS Account ID，但不要把它提交到公开文档。

## 5. 创建 Lightsail 实例

进入：

`https://lightsail.aws.amazon.com/`

按以下顺序选择：

1. Create instance。
2. Region 选择 `Asia Pacific (Singapore)`。
3. Platform 选择 `Linux/Unix`。
4. Blueprint 选择 `OS Only`。
5. 选择当前控制台提供的 `Ubuntu 24.04 LTS`；如果暂时没有，选择当前受支持
   的 Ubuntu LTS，不使用预装 WordPress、LAMP 或其他应用镜像。
6. 选择 Public IPv4、2 vCPU、4 GB、80 GB、USD 24/month 套餐。
7. 实例名使用 `cex-quant-sg1`。
8. 创建实例。

不要创建：

- Load Balancer；
- Managed Database；
- CDN；
- 域名；
- WordPress；
- Windows Server；
- Spot/Preemptible instance。

## 6. 创建并绑定固定 IP

1. 在 Lightsail 左侧进入 `Networking`。
2. 选择 `Create static IP`。
3. Region 选择 Singapore。
4. 绑定 `cex-quant-sg1`。
5. 名称使用 `cex-quant-sg1-ip`。
6. 创建后记录固定 IPv4。
7. 不要解绑、删除或重新创建该 IP。

该地址以后用于：

- Binance Testnet/Production API 白名单；
- 运维审计；
- 出口健康检查；
- API rate-limit 和异常来源识别。

固定出口 IP 不是对公网开放 Dashboard 的理由。

## 7. 第一时间收紧防火墙

Lightsail 的 Ubuntu 基础镜像可能默认允许公网访问 SSH 22 和 HTTP 80。
创建完成后立即检查 IPv4 和 IPv6 两套防火墙。

目标状态：

```text
TCP 80       closed
TCP 443      closed
Database     closed
Application  closed
ICMP         optional
TCP 22       temporary, restricted to one administrator IP
```

禁止：

```text
SSH 22 from 0.0.0.0/0
SSH 22 from ::/0
HTTP/HTTPS open to all
Database open to all
Operations UI open to all
```

AWS 官方说明 IPv4 和 IPv6 防火墙互相独立；两边都必须检查。SSH 应只允许
管理员当前 IP，而不是所有地址：

`https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-firewall-and-port-mappings-in-amazon-lightsail.html`

项目负责人在中国大陆使用的 VPN 出口可能变化。VPN IP 变化时不要临时把
SSH 开放给全网。推荐完成初始化后使用 Tailscale/WireGuard 等仅出站建立的
管理网络，然后关闭公网 SSH；如果该管理网络不可用，则每次只为当前管理
IP 临时开放 SSH。

## 8. 首次系统初始化

首次通过 Lightsail 控制台或受限 SSH 登录。先更新系统：

```bash
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y
sudo apt-get install -y \
  ca-certificates \
  chrony \
  curl \
  fail2ban \
  git \
  jq \
  python3 \
  python3-pip \
  python3-venv \
  rsync
sudo timedatectl set-timezone UTC
sudo systemctl enable --now chrony
sudo systemctl enable --now fail2ban
```

重启前确认没有交易进程或仓位：

```bash
sudo reboot
```

重新登录后检查：

```bash
uname -a
python3 --version
timedatectl status
chronyc tracking
chronyc sources -v
systemctl --failed
```

要求：

- Python >= 3.11；
- 时区为 UTC；
- clock synchronized 为 yes；
- chrony 有有效来源；
- leap status 为 Normal；
- 没有无法解释的 failed service。

AWS 提供 link-local Time Sync 地址 `169.254.169.123`。在 T045/A018
主机验收时再根据实际 Ubuntu 镜像确认 chrony 配置，不要同时混用不兼容的
时间源：

`https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-ec2-ntp.html`

## 9. 创建专用服务账户和目录

不要使用 root 运行交易程序：

```bash
sudo adduser --disabled-password --gecos "" cexquant
sudo install -d -o cexquant -g cexquant -m 0750 /opt/cex-quant
sudo install -d -o cexquant -g cexquant -m 0750 /var/lib/cex-quant
sudo install -d -o cexquant -g cexquant -m 0750 /var/log/cex-quant
sudo install -d -o root -g cexquant -m 0750 /etc/cex-quant
```

目录职责：

```text
/opt/cex-quant       reviewed source/artifact and virtual environment
/var/lib/cex-quant   OMS/Risk/Accounting/Carry/operator durable state
/var/log/cex-quant   bounded service logs
/etc/cex-quant       root-owned non-secret deployment configuration
```

API Secret 不得写入这些目录、Git、shell history、命令参数或普通日志。

## 10. 安装当前项目

在没有 GitHub 写权限和 Token 的服务器上使用只读 HTTPS clone。不要把
GitHub Personal Access Token 写进 clone URL。

```bash
sudo -u cexquant git clone \
  https://github.com/fomalhaut11/cex_trading_platform.git \
  /opt/cex-quant/repo

sudo -u cexquant python3 -m venv /opt/cex-quant/venv

sudo -u cexquant /opt/cex-quant/venv/bin/python \
  -m pip install --upgrade pip

sudo -u cexquant bash -lc \
  'cd /opt/cex-quant/repo && ../venv/bin/python -m pip install -e ".[dev]"'
```

记录并核对版本：

```bash
sudo -u cexquant bash -lc \
  'cd /opt/cex-quant/repo && git rev-parse HEAD && git status --short'
```

工作区必须干净，HEAD 必须等于批准部署的 commit。

## 11. 在服务器上运行验收

```bash
sudo -u cexquant bash -lc \
  'cd /opt/cex-quant/repo && ../venv/bin/python -m compileall -q src'

sudo -u cexquant bash -lc \
  'cd /opt/cex-quant/repo && ../venv/bin/python -m ruff check src tests tools'

sudo -u cexquant bash -lc \
  'cd /opt/cex-quant/repo && ../venv/bin/python -m mypy --strict src'

sudo -u cexquant bash -lc \
  'cd /opt/cex-quant/repo && ../venv/bin/python -m pytest \
    --cov=cex_quant --cov-branch --cov-report=term-missing \
    --cov-fail-under=85'
```

服务器创建后先完成以上离线验证，不要配置生产 Binance Key。

## 12. 凭证规则

当前代码通过 `EnvironmentBinanceCredentialProvider` 读取显式环境变量，
但 environment adapter 不是 Secret Vault。

必须遵守：

- Testnet 和 Production 使用不同账户、Key 和变量；
- API Key 只开最低必要的 Spot/Futures trading 和 account-data 权限；
- 禁止 Withdrawal；
- 禁止不需要的通用转账权限；
- 绑定 `cex-quant-sg1-ip`；
- Secret 不通过聊天、邮件、Git 或文档传递；
- 生产 Secret 通过 OS/orchestrator secret facility 注入；
- 定期轮换，怀疑泄露时立即撤销；
- Operator HMAC Key 与 Binance API Secret 完全分开。

在 T050 选择并验收最终 secret injector 前，不创建生产 secret 文件。

## 13. 当前禁止创建生产服务

仓库当前还没有经过 A018/A019/A020 验收的完整 Funding Carry daemon
入口，因此现在不要自行编造 systemd `ExecStart`，也不要解除：

```text
BASKET_RECORDED_EXTERNAL_BLOCKED
GroupedExecutionBlockedError
```

服务器当前用途：

1. 运行完整离线测试；
2. 执行 T045 组合审计；
3. 执行 T046/A018 故障注入；
4. 在单独授权后执行 A019 Testnet；
5. 运行 T050 生产只读 Shadow；
6. 在 A020 后等待单独的 A021 真实资金授权。

systemd 服务、Secret injector、日志轮转、数据目录绑定和进程恢复命令必须
由 T046/T050 的真实入口决定，不能在入口不存在时提前假设。

## 14. 快照和备份

在 Lightsail 中开启每日自动快照，保留默认最近七份。除此之外：

- 在每次批准部署前创建手工快照；
- Journal/Ledger 另做应用一致性备份；
- 不把实例快照当作唯一 Accounting 备份；
- 不在有活动 Order Group 时直接恢复整机快照；
- 删除实例前先保留所需手工快照；
- 定期验证能够从备份读取 Journal 和 Ledger。

AWS 官方说明自动快照保留最近七份，按实际存储计费：

`https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-snapshots.html`

## 15. 日常操作纪律

每次启动前：

```text
1. 检查系统时间和 venue clock。
2. 检查磁盘、Journal、Ledger 和审计存储。
3. 检查 Binance 公共连接和私有流。
4. 先 REST reconciliation，再允许新风险。
5. 确认 operator mode 为 HALTED。
6. 确认账户、品种、数量和损失边界。
7. 只有对应验收已授权时才 ACTIVATE。
```

每次升级前：

```text
1. STOP ALL NEW EXPOSURE。
2. 解决或记录所有非终态订单。
3. 对账 Spot、Perp、余额和 Ledger。
4. 备份 Journal/Ledger。
5. 记录旧/新 commit。
6. 部署后仍从 HALTED 启动。
```

禁止：

- 有未确认 UNKNOWN 订单时重启后盲目重试；
- 有活动仓位时随意销毁或更换固定 IP；
- 通过消费级 VPN 路由服务器的 Binance API；
- 在公网开放 Operations Lite；
- 把 Testnet 成功解释为真实资金授权；
- 用服务器地区代替账户合规判断。

## 16. 创建完成后返回的信息

可以在当前私有运维任务中提供，但不要提交到公开仓库：

```text
Cloud provider
Region
Instance name
Static public IP
Ubuntu version
Python version
git HEAD
timedatectl status
chronyc tracking
systemctl --failed
```

绝对不要提供：

```text
AWS root password
MFA seed/recovery code
payment card
SSH private key
Binance API Secret
operator HMAC secret
production environment dump
```

## 17. 下一闸门

服务器准备完成不等于可以交易。工程顺序仍是：

```text
T045 -> T046 -> A018
     -> A019 (单独授权 Testnet)
     -> T050 -> A020
     -> A021 (单独授权微资金实盘)
```

当前权威计划：

`development/funding_carry_fast_track_plan.md`
