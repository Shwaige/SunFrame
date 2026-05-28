# YGMC 自动化工具

面向阳光牧场的命令行自动化工具，支持：

- 签到与奖励领取
- 活动处理
- 阳光任务检查与VIP奖励领取
- 自己农场/畜牧场操作
- 好友农场/畜牧场操作
- 单账号与批量账号运行

## 快速开始

### 批量命令

```bash
python3 -m ygmc.cli daily accounts.example.txt
python3 -m ygmc.cli daily-self accounts.batch.txt
python3 -m ygmc.cli self-op accounts.batch.txt
python3 -m ygmc.cli sign accounts.batch.txt
python3 -m ygmc.cli sunshine accounts.batch.txt
```

### 单账号命令

```bash
# 使用登录凭证
env YGMC_LABEL='shwaige' YGMC_LOGIN_ACCOUNT='shwaige' YGMC_LOGIN_PASSWORD='shwaige' python3 -m ygmc.cli daily

# 使用游戏凭证
env YGMC_OPEN_ID='...' YGMC_SID='...' python3 -m ygmc.cli sunshine
```

### PowerShell 示例

```powershell
py -m ygmc.cli daily-self .\accounts.batch.txt
py -m ygmc.cli daily .\accounts.example.txt
$env:YGMC_LABEL='shwaige'; $env:YGMC_LOGIN_ACCOUNT='shwaige'; $env:YGMC_LOGIN_PASSWORD='shwaige'; py -m ygmc.cli daily
```

## 账号配置

支持两种凭证来源。

### 直接使用游戏凭证

```bash
export YGMC_OPEN_ID='...'
export YGMC_SID='...'
python3 -m ygmc.cli sign
```

### 使用家园账号密码自动登录

```bash
export YGMC_LABEL='shwaige'
export YGMC_LOGIN_ACCOUNT='shwaige'
export YGMC_LOGIN_PASSWORD='shwaige'
python3 -m ygmc.cli daily
```

账号密码模式下，工具会：

- 优先读取本地缓存 `.ygmc_cache.json`
- 缓存可用时直接进入牧场
- 缓存异常时自动重新登录并刷新凭证

## 批量文件格式

### 单账号登录

```txt
label,login_account,login_password,login
shwaige_1,shwaige1,shwaige,login
```

### 连续区间账号

```txt
label_prefix,login_prefix,start,end,password,login_range
shwaige_,shwaige,1,6,shwaige,login_range
```

### 示例文件

- `accounts.batch.txt` - 批量账号配置
- `accounts.example.txt` - 格式示例

## 命令总览

### 组合命令

| 命令 | 说明 |
|------|------|
| `daily` | 签到 + 活动 + 阳光任务 + 自己农场/牧场 + 好友操作 |
| `daily-self` | 签到 + 活动 + 阳光任务 + 自己农场/牧场，不处理好友 |

### 单模块命令

| 命令 | 说明 |
|------|------|
| `sign` | 签到、累签奖励、月累签奖励 |
| `activity` | 活动逻辑（新人红包等） |
| `sunshine` | 阳光任务状态检查与VIP奖励领取 |
| `self-op` | 自己农场/畜牧场操作 |
| `friends-op` | 好友农场/畜牧场操作 |
| `status` | 查看状态，不做操作 |

## 模块行为说明

### sign

签到模块会：

1. 进入签到页
2. 完成当天签到
3. 自动领取可领的累签奖励和月累签奖励

已签到时输出：

```text
凭证来源=缓存
今日签到状态=已签
```

### activity

活动模块包含：

- **新人红包**：从主页找入口，若有免费领取则点击一次

### sunshine

阳光任务模块会：

1. 解析阳光任务页面，提取任务列表
2. 显示今日阳光值
3. 列出未完成的任务（排除充值/消费/转动风车/刷新稻草人）
4. 通过VIP一键领取所有奖励

输出示例：

```text
今日阳光值=140点
未完成任务=4
  7.在畜牧场饲养8只动物(3/8) 奖励:2000金币
  8.为动物使用罐头3次(0/3) 奖励:20元宝
  9.给好友窝/栏添加5次饲料(2/5) 奖励:精致饲料×50
  11.在好友农场偷取3次(0/3) 奖励:500金币
VIP奖励=已点击
```

### self-op

处理自己的农场和畜牧场。

策略：

1. 判断当前页面是否存在可操作目标
2. 优先尝试一键入口
3. 一键无权限/失败/无效时，回退到单个按钮

农场操作：浇水、除草、捉虫、收获、铲除

畜牧场操作：喂养、喂水、清理、清洁、治疗、帮助、收获、生产、捉取

### friends-op

处理好友农场和好友畜牧场。

策略：

- 自动扫描所有分页
- 只处理列表中带标签的好友
- 优先一键，不可用时回退单次操作
- 整轮扫完后重新从第一页再扫（最多5轮）

畜牧场未开通时输出：

```text
畜牧场=未开通，已跳过
```

## 输出说明

| 输出 | 含义 |
|------|------|
| `凭证来源=缓存` | 使用缓存的 openId/sid |
| `凭证来源=登录` | 重新走了登录链路 |
| `农场链接=...` | 当前牧场首页直链 |
| `自己操作数量` | 自己农场/畜牧场实际执行的动作数 |
| `自己操作跳过数量` | 页面无可操作项，跳过的动作数 |
| `自己操作失败数量` | 自己操作失败数量 |
| `农场好友处理数量` | 好友农场实际处理的好友数 |
| `畜牧场好友处理数量` | 好友畜牧场实际处理的好友数 |
| `好友处理失败数量` | 好友处理失败总数 |

## 代码结构

| 文件 | 说明 |
|------|------|
| `ygmc/cli.py` | 统一命令入口 |
| `ygmc/accounts.py` | 账号加载、批量文件解析 |
| `ygmc/session.py` | 凭证解析、缓存优先、登录刷新 |
| `ygmc/http.py` | HTTP 请求封装、请求节流、超时重试 |
| `ygmc/sign.py` | 签到逻辑 |
| `ygmc/activity.py` | 活动逻辑（新人红包等） |
| `ygmc/sunshine.py` | 阳光任务检查与VIP奖励领取 |
| `ygmc/self_ops.py` | 自己农场/畜牧场操作 |
| `ygmc/friends_ops.py` | 好友农场/畜牧场操作 |
| `ygmc_sign.py` | 旧签到入口兼容脚本 |

## 常见问题

### 1. Connection refused

通常是本机网络环境问题，最常见原因是开了无效代理：

```bash
http_proxy=http://127.0.0.1:7897
https_proxy=http://127.0.0.1:7897
```

先检查代理变量，再重试。

### 2. 缓存凭证失效

现象：

- 页面返回登录页
- 页面内容异常为空
- 无法找到老服跳转入口

处理：

- 账号密码模式下，工具会自动尝试刷新缓存
- 也可以手动删除 `.ygmc_cache.json` 后重试

### 3. 自己没开通畜牧场

好友畜牧场也不会继续处理，输出：

```text
畜牧场=未开通，已跳过
```

### 4. 好友还有残留，为什么没扫完

`friends-op` 会跨分页、多轮回扫，但好友状态是动态变化的：

- 处理完一轮后，新的可操作状态可能又出现
- 某些好友一轮内没有标签，下一轮刷新后才出现

如果仍有残留，可以再次运行一轮。

### 5. git push 被拒绝，提示 non-fast-forward

远端 `main` 比本地多了新提交，先同步再推送：

```bash
git fetch origin
git rebase origin/main
git push origin main
```

## 注意事项

- 不要把真实 `sid`、`openId`、账号密码提交到仓库
- `.ygmc_cache.json` 是本地缓存，不应入库
- 活动逻辑是临时性的，后续活动可能需要随时替换
- 请求间隔默认 `0.3` 秒，可通过环境变量覆盖：

```bash
export YGMC_REQUEST_INTERVAL='0.5'
```
