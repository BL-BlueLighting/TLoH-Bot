<div align="center">
    <img src="./README.Logo.jpg" style="width: 128px;">
</div>


<h1 align="center">TLoH Bot</h1>

<p align="center">
    <a href="#">
        <img src="https://img.shields.io/badge/Version-1.4.0-blue">
    </a>
    <a href="#">
        <img src="https://img.shields.io/badge/OneBot-v11-blue">
    </a>
</p>

<div align="center">
    <a href="README.md">中文</a> | <a href="README.en.md">English</a>
</div>

<p align="center"><i>优秀的 QQ Bot 实例</i></p>

<hr/>

> [!Warning]
> 
> TLoH Bot 更新了配置文件格式，此次更新前，请先备份您的旧版 `configuration.toml`，改为 `configuration.toml.toolsbot_data` (旧版存档数据)
> ，来避免 git 认为您的 `configuration.toml` 属于更改，导致无法正常 `git pull`。更新完之后，请对照您的旧版 `configuration.toml` 对新版 `configuration.toml` 进行修改。

> [!Warning]
> 
> ToolsBot 已更新，请在 git pull 下来后，执行 python ./scripts/quickmove.py 来迁移用户数据

## 如何使用
先 git clone 下来整个项目。

`
git clone https://github.com/BL-BlueLighting/RE-ToolsBot.git
`

以下操作二选一

<details>
<summary>安装依赖(主环境内)</summary>

使用下面这行命令安装所有依赖。

`
python ./scripts/install/installTB.py
`

或者，直接通过 pip 安装：

`
pip install -r ./scripts/install/requirements.txt
`

</details>

<details>
<summary>安装依赖(虚拟环境)</summary>

1.安装版本>=3.10的python

2.运行`pip install poetry`

3.运行`poetry install`

(备注:真的有人会想把这个项目部署在主环境里吗)

</details>

(只创建一个空项目，选择全局安装)

在所有的事情干完后，修改 `.env.prod` `bot.py` 中的 SUPERUSER 为你自己的 QQ号码。

接下来，打开 `data/configuration_template.toml`，修改其中的 api_key 项目为你的服务提供商 API Key。随后重命名为 `configuration.toml`。
若不需要，请直接重命名为 `configuration.toml`。

随后，运行 `nb run --reload` 来启动 bot.

## 这个 bot 怎么链接到 QQ？

先安装NapCat并登录Bot的QQ账号 https://github.com/NapNeko/NapCatQQ.

随后在“网络配置” --> 新建 --> Websocket客户端 中填写名称，URL和token

![Napcat1](./README.NAPCAT.1.png)
![Napcat2](./README.NAPCAT.2.png)

## 使用教程？
在 Bot 上线之后，用 ^help，或者参考这个图片：

<img src="./helpdocuments/PNG/HelpDocument v2.png">

## 感谢
> [!Note]
>
> 感谢以下项目，我参考了以下项目的部分代码。

<a href="https://github.com/yzyyz1387/nonebot_plugin_admin/">NoneBot Plugin Admin</a>
*致歉：引入了 SCP 基金会 TypeSense CROM 的 API Key，对其开发者致以歉意。若需要进行删除，请联系本人。*

## 警告

> [!Warning]
>
> 该项目目前并不稳定。请不要直接克隆该项目，我没办法做到自检查代码的每一处角落。
>
> 如果你发现了任何问题，请在 `Github Issues` 中发表一个 Issue。
