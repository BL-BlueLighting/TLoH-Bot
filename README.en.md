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

<p align="center"><i>Perfect Bot for QQ.</i></p>

## How to use it?
First, clone this project.

`
git clone https://github.com/BL-BlueLighting/RE-ToolsBot.git
`

Choose one of the following two actions

<details>
<summary>Install dependencies(Main Environment)</summary>
Install requirements using this python script:

`
python ./installTB.py
`

Or, install requirements directly

`
pip install -r ./install/requirements.txt
`

</details>

<details>
<summary>Install dependencies(Virtual Environment)</summary>
1.Install Python version 3.10 or higher

2.Run `pip install poetry`

3.Run `poetry install`

(Note: Are there really people who would want to deploy this project in the main environment?)

</details>

(Only create a blank project, use global install)

After all actions, edit `.env.prod` `.env.dev` `bot.py` 'SUPERUSER' configure section to your qq Number.

Then, open `data/configuration_template.toml`, edit `AI-ApiKEY`. Rename it to `data/configuration.toml`
If you do not need AI skill, just `data/configuration_template.toml` to `data/configuration.toml` is best choice.

Run `nb run --reload` to boot this bot.

## How to connect bot to QQ?

First install NapCat and login with the Bot's QQ account. https://github.com/NapNeko/NapCatQQ.

Then, in "Network Configuration" --> New --> WebSocket Client, fill in the name, URL, and token

![Napcat1](./README.NAPCAT.1.png)
![Napcat2](./README.NAPCAT.2.png)

## Thanks
> [!Note]
>
> Thanks for project under. I used some code from them.

<a href="https://github.com/yzyyz1387/nonebot_plugin_admin/">NoneBot Plugin Admin</a>

## Tips
> [!Warning]
>
> This project is **not** stable.
>
> Please don't direct clone this repo.
>
> I can't do check my code anytime.
>
> If you found a issue, please make a issue context in `Github Issues` !
