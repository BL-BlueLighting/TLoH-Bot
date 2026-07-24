import datetime
import json
import os
import random
import re
import sqlite3
from collections import Counter
from typing import Any, Dict, Literal, Callable, List

import nonebot
import requests
import toml
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import (Bot, GroupMessageEvent,
                                         PrivateMessageEvent)
from nonebot.exception import ActionFailed
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

from toolsbot.configs import DATA_PATH
from toolsbot.services import _error, _info
import plugins.userInfoController as uic

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

undefiendControllers.killers
DEVIL ROUNDS
"""

TITLE = "TLoH Bot"

devil_rounds = on_command("devilrounds", aliases={"恶魔轮盘", "轮盘赌"}, priority=5, block=True)

# 游戏状态管理
games: Dict[str, Dict] = {}  # 存储所有游戏实例

class DevilRoundsGame:
    def __init__(self, group_id: str, players: List[uic.User]):
        self.group_id = group_id
        self.players = players  # 4个玩家
        self.current_player_index = 0
        self.shells = []  # 子弹列表，1为实弹，0为空包弹
        self.current_shell_index = 0
        self.items = {}  # 玩家道具
        self.turn_count = 0
        self.game_over = False
        self.round = 1
        self.max_rounds = 5  # 最大回合数
        
        # 初始化每个玩家的道具
        for player in self.players:
            self.items[player.id] = []
    
    def load_shells(self, live_count: int, blank_count: int):
        """装填子弹"""
        self.shells = [1] * live_count + [0] * blank_count
        random.shuffle(self.shells)
        self.current_shell_index = 0
        _info(f"装填子弹: {live_count}实弹, {blank_count}空包弹")
    
    def get_current_player(self) -> uic.User:
        """获取当前玩家"""
        return self.players[self.current_player_index]
    
    def next_player(self):
        """切换到下一个玩家"""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        if self.current_player_index == 0:
            self.round += 1
    
    def use_item(self, player: uic.User, item: str) -> str:
        """使用道具"""
        if item not in self.items[player.id]:
            return "你没有这个道具！"
        
        self.items[player.id].remove(item)
        
        if item == "啤酒":
            if self.current_shell_index >= len(self.shells):
                return "枪膛里已经没有子弹了！"
            shell = self.shells.pop(self.current_shell_index)
            if shell == 1:
                return "你用啤酒退出了一发实弹！"
            else:
                return "你用啤酒退出了一发空包弹！"
        
        elif item == "手铐":
            next_player = self.players[(self.current_player_index + 1) % len(self.players)]
            self.items[next_player.id].append("被手铐")
            return f"你用手铐铐住了 {next_player.name}！"
        
        elif item == "手锯":
            self.items[player.id].append("手锯激活")
            return "你使用了手锯，下次射击伤害翻倍！"
        
        elif item == "香烟":
            player.addScore(100)  # 恢复生命值
            return "你使用了香烟，恢复了100点生命值！"
        
        elif item == "放大镜":
            if self.current_shell_index >= len(self.shells):
                return "枪膛里已经没有子弹了！"
            shell_type = "实弹" if self.shells[self.current_shell_index] == 1 else "空包弹"
            return f"你用放大镜看到了下一发是{shell_type}！"
        
        return "未知道具！"
    
    def shoot(self, target: uic.User, self_shoot: bool = False) -> str:
        """射击"""
        if self.current_shell_index >= len(self.shells):
            return "枪膛里已经没有子弹了！"
        
        shell = self.shells[self.current_shell_index]
        self.current_shell_index += 1
        
        damage = 2 if "手锯激活" in self.items[target.id] else 1
        
        # 检查是否被手铐
        if "被手铐" in self.items[target.id]:
            self.items[target.id].remove("被手铐")
            return f"{target.name} 被手铐铐住了，无法行动！"
        
        if self_shoot:
            # 向自己开枪
            if shell == 0:
                # 空包弹
                self.next_player()
                return f"{target.name} 向自己开枪，是空包弹！获得额外回合！"
            else:
                # 实弹
                target.subtScore(damage * 100)  # 扣除生命值
                if target.getScore() <= 0:
                    self.game_over = True
                    return f"{target.name} 向自己开枪，是实弹！受到{damage*100}点伤害，被淘汰了！"
                self.next_player()
                return f"{target.name} 向自己开枪，是实弹！受到{damage*100}点伤害！"
        else:
            # 向目标开枪
            if shell == 0:
                # 空包弹
                self.next_player()
                return f"{target.name} 向 {self.get_current_player().name} 开枪，是空包弹！"
            else:
                # 实弹
                target.subtScore(damage * 100)  # 扣除生命值
                if target.getScore() <= 0:
                    self.game_over = True
                    return f"{target.name} 向 {self.get_current_player().name} 开枪，是实弹！受到{damage*100}点伤害，被淘汰了！"
                self.next_player()
                return f"{target.name} 向 {self.get_current_player().name} 开枪，是实弹！受到{damage*100}点伤害！"
    
    def check_game_over(self) -> bool:
        """检查游戏是否结束"""
        alive_players = [p for p in self.players if p.getScore() > 0]
        if len(alive_players) <= 1:
            self.game_over = True
            return True
        if self.round > self.max_rounds:
            self.game_over = True
            return True
        return False
    
    def get_alive_players(self) -> List[uic.User]:
        """获取存活玩家"""
        return [p for p in self.players if p.getScore() > 0]
    
    def get_game_status(self) -> str:
        """获取游戏状态"""
        status = f"=== devilrounds (第{self.round}回合) ===\n"
        status += f"当前玩家: {self.get_current_player().name}\n"
        status += f"剩余子弹: {len(self.shells) - self.current_shell_index}发\n"
        status += "存活玩家:\n"
        for player in self.get_alive_players():
            status += f"- {player.name}: {player.getScore()}分\n"
        return status

@devil_rounds.handle()
async def handle_devil_rounds(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    
    # 检查是否已有游戏
    if group_id in games:
        game = games[group_id]
        if not game.game_over:
            await devil_rounds.finish("TLoH Bot - DEVILROUNDS\n    - 当前已有进行中的游戏！")
    
    # 解析命令参数
    msg = args.extract_plain_text().strip()
    if msg == "开始":
        # 开始新游戏
        if len(uic.At(event.json())) < 4:
            await devil_rounds.finish("TLoH Bot - DEVILROUNDS\n    - 至少需要4个玩家参与游戏！")
        
        player_ids = uic.At(event.json())
        players = []
        for pid in player_ids:
            user = uic.User(pid)
            if user.isBanned():
                await devil_rounds.finish(f"TLoH Bot - DEVILROUNDS\n    - 玩家 {user.name} 已被封禁，无法参与游戏！")
            players.append(user)
        
        # 创建新游戏
        game = DevilRoundsGame(group_id, players)
        games[group_id] = game
        
        # 随机装填第一轮子弹
        game.load_shells(random.randint(2, 4), random.randint(2, 4))
        
        await devil_rounds.send(f"TLoH Bot - DEVILROUNDS\n    - DEVILROUNDS 开始！\n{game.get_game_status()}\n请 {game.get_current_player().name} 选择行动：\n1. 向自己开枪\n2. 向其他人开枪\n3. 使用道具")
    
    elif msg.startswith("射击"):
        # 射击命令
        if group_id not in games:
            await devil_rounds.finish("当前没有进行中的游戏！")
        
        game = games[group_id]
        current_player = game.get_current_player()
        
        if user_id != current_player.id:
            await devil_rounds.finish(f"TLoH Bot - DEVILROUNDS\n    - 现在不是你的回合！当前是 {current_player.name} 的回合。")
        
        # 解析射击目标
        parts = msg.split()
        if len(parts) < 2:
            await devil_rounds.finish("TLoH Bot - DEVILROUNDS\n    - 请指定射击目标！例如：射击 自己 或 射击 玩家名")
        
        target_name = parts[1]
        if target_name == "自己":
            result = game.shoot(current_player, self_shoot=True)
        else:
            # 查找目标玩家
            target = None
            for player in game.players:
                if player.name == target_name:
                    target = player
                    break
            
            if not target:
                await devil_rounds.finish(f"TLoH Bot - DEVILROUNDS\n    - 找不到玩家 {target_name}！")
            
            result = game.shoot(target, self_shoot=False)
        
        await devil_rounds.send(f"{result}\n{game.get_game_status()}")
        
        # 检查游戏是否结束
        if game.check_game_over():
            alive_players = game.get_alive_players()
            if len(alive_players) == 1:
                winner = alive_players[0]
                winner.addScore(1000)  # 胜利奖励
                await devil_rounds.send(f"TLoH Bot - DEVILROUNDS\n    - 游戏结束！{winner.name} 获胜！获得1000分奖励！")
            else:
                await devil_rounds.send("TLoH Bot - DEVILROUNDS\n    - 游戏结束！没有玩家存活！")
            
            # 保存玩家数据
            for player in game.players:
                player.save()
            
            # 移除游戏
            del games[group_id]
    
    elif msg.startswith("道具"):
        # 使用道具命令
        if group_id not in games:
            await devil_rounds.finish("TLoH Bot - DEVILROUNDS\n    - 当前没有进行中的游戏！")
        
        game = games[group_id]
        current_player = game.get_current_player()
        
        if user_id != current_player.id:
            await devil_rounds.finish(f"TLoH Bot - DEVILROUNDS\n    - 现在不是你的回合！当前是 {current_player.name} 的回合。")
        
        parts = msg.split()
        if len(parts) < 2:
            await devil_rounds.finish("TLoH Bot - DEVILROUNDS\n    - 请指定要使用的道具！例如：道具 啤酒")
        
        item_name = parts[1]
        result = game.use_item(current_player, item_name)
        await devil_rounds.send(f"{result}\n{game.get_game_status()}")
    
    elif msg == "状态":
        # 查看游戏状态
        if group_id not in games:
            await devil_rounds.finish("TLoH Bot - DEVILROUNDS\n    - 当前没有进行中的游戏！")
        
        game = games[group_id]
        await devil_rounds.send(game.get_game_status())
    
    elif msg == "退出":
        # 退出游戏
        if group_id not in games:
            await devil_rounds.finish("TLoH Bot - DEVILROUNDS\n    - 当前没有进行中的游戏！")
        
        game = games[group_id]
        current_player = game.get_current_player()
        
        if user_id != current_player.id:
            await devil_rounds.finish(f"TLoH Bot - DEVILROUNDS\n    - 现在不是你的回合！当前是 {current_player.name} 的回合。")
        
        # 保存玩家数据
        for player in game.players:
            player.save()
        
        # 移除游戏
        del games[group_id]
        await devil_rounds.send("TLoH Bot - DEVILROUNDS\n    - 退出游戏")
    
    else:
        # 显示帮助信息
        await devil_rounds.send(
            "TLoH Bot - DEVILROUNDS 游戏帮助\n"
            "    - devilrounds 开始 <玩家1> <玩家2> <玩家3> <玩家4> - 开始新游戏\n"
            "    - devilrounds 射击 <目标> - 向目标开枪（目标可以是'自己'或其他玩家名）\n"
            "    - devilrounds 道具 <道具名> - 使用道具（啤酒、手铐、手锯、香烟、放大镜）\n"
            "    - devilrounds 状态 - 查看游戏状态\n"
            "    - devilrounds 退出 - 退出当前游戏"
        )