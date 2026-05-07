# 启动命令
批量账号：

```bash
python3 -m ygmc.cli daily accounts.batch.txt
python3 -m ygmc.cli daily-self accounts.batch.txt
```

PowerShell：

```powershell
py -m ygmc.cli daily .\accounts.batch.txt
$env:YGMC_LABEL='shwaige'; $env:YGMC_LOGIN_ACCOUNT='shwaige'; $env:YGMC_LOGIN_PASSWORD='shwaige'; py -m ygmc.cli daily
```

Bash / Git Bash / Linux / macOS：

```bash
env YGMC_LABEL='shwaige' YGMC_LOGIN_ACCOUNT='shwaige' YGMC_LOGIN_PASSWORD='shwaige' python3 -m ygmc.cli daily
```

只执行自己农场/畜牧场的一键操作、收获和铲除：

```powershell
$env:YGMC_LABEL='shwaige'; $env:YGMC_LOGIN_ACCOUNT='shwaige'; $env:YGMC_LOGIN_PASSWORD='shwaige'; py -m ygmc.cli self-op
```

强制跳过本地缓存并重新登录：

```powershell
$env:YGMC_FORCE_LOGIN='1'; $env:YGMC_LABEL='shwaige1'; $env:YGMC_LOGIN_ACCOUNT='shwaige1'; $env:YGMC_LOGIN_PASSWORD='shwaige'; py -m ygmc.cli daily
```

请求间隔默认 0.3 秒，可临时覆盖：

```powershell
$env:YGMC_REQUEST_INTERVAL='0.5'
```


# YGMC Scripts

这个目录现在是一个可扩展的阳光牧场自动化工具，而不是单个临时脚本。

## 结构

- `ygmc/cli.py`: 统一命令行入口
- `ygmc/accounts.py`: 账号加载
- `ygmc/http.py`: HTTP 会话和请求
- `ygmc/sign.py`: 签到逻辑
- `ygmc/output.py`: 页面摘要解析与输出
- `ygmc_sign.py`: 兼容旧用法的包装脚本

## 用法

单账号：

```bash
export YGMC_OPEN_ID='...'
export YGMC_SID='...'
python3 ygmc_sign.py
```

或：

```bash
python3 -m ygmc.cli sign
```

也支持账号密码登录后自动进入老服并解析牧场凭证：

```bash
export YGMC_LOGIN_ACCOUNT='...'
export YGMC_LOGIN_PASSWORD='...'
python3 ygmc_sign.py
```

如果同时使用账号密码模式，脚本会优先尝试本地缓存的 `openId/sid` 直接进入牧场；只有缓存失效时，才会重新走登录链路并刷新缓存。缓存文件默认在项目根目录：

```text
.ygmc_cache.json
```

批量账号：

```bash
python3 -m ygmc.cli daily accounts.batch.txt
```


批量登录账号支持两种写法：

```txt
label,login_account,login_password,login
pwd_account,shwaige1,shwaige,login
```

```txt
label_prefix,login_prefix,start,end,password,login_range
range_account_,shwaige,1,6,shwaige,login_range
```

已经提供一份可直接改用的批量文件：
[accounts.batch.txt](/Users/zhangyong/Desktop/SunFrame/accounts.batch.txt)

## 扩展建议

以后新增能力时，优先按这个结构加：

- `ygmc/farm.py`: 播种
- `ygmc/pet.py`: 宠物相关
- `ygmc/activity.py`: 活动入口和领奖
- `ygmc/cli.py`: 增加对应子命令

尽量把页面解析、网络请求、命令行参数分开，不要重新堆回单文件。
