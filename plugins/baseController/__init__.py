import base64
from random import uniform as wrd
from time import sleep as wait

import base58
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg

import plugins.userInfoController as dc

"""
TLoH Bot
Tools Bot 的第二版。

@author: BL-BlueLighting

baseController
"""

"""
BaseXX Function
迁移自旧版 Tools Bot

用于编解码 BaseXX 字符串
"""
base64_eventer = on_command("base64", aliases={"b64"}, priority=10)

@base64_eventer.handle()
async def _(event: MessageEvent,args: Message = CommandArg()):
    user = dc.User(event.get_user_id())
    if not user.isBanned():
        msg = ""
        if params := args.extract_plain_text():
            msg += "\nTLoH Bot Base64 编解码"
            params_l = params.split(" ")
            if params_l[0] == "encode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n编码为：\n{base64.b64encode(params_l[1].encode()).decode()}"
            elif params_l[0] == "decode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n解码为：\n{base64.b64decode(params_l[1].encode()).decode()}"
            else:
                wait(wrd(0.5,0.9))
                msg += "\n    - 使用方法："
                wait(wrd(0.5,0.9))
                msg += "\n    - ^base64 encode\\decode [内容]"
        else:
            msg += "\nBase64 加密解密"
            wait(wrd(0.5,0.9))
            msg += "\n    - 使用方法："
            wait(wrd(0.5,0.9))
            msg += "\n    - ^base64 encode\\decode [内容]"
        await base64_eventer.finish(msg)
    else:
        await base64_eventer.finish("TLoH Bot Base64 编解码\n  您的账号已被封禁，无法使用此功能")

base32_eventer = on_command("base32", aliases={"b32"}, priority=10)

@base32_eventer.handle()
async def _(event: MessageEvent,args: Message = CommandArg()):
    user = dc.User(event.get_user_id())
    if not user.isBanned():
        msg = ""
        if params := args.extract_plain_text():
            msg += "\nTLoH Bot Base32 编解码"
            params_l = params.split(" ")
            if params_l[0] == "encode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n编码为：\n{base64.b32encode(params_l[1].encode()).decode()}"
            elif params_l[0] == "decode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n解码为：\n{base64.b32decode(params_l[1].encode()).decode()}"
            else:
                msg += "\n    - 使用方法："
                wait(wrd(0.5,0.9))
                msg += "\n    - ^base32 encode*decode [内容]"
        else:
            msg += "\nTLoH Bot Base64 编解码"
            wait(wrd(0.5,0.9))
            msg += "\n    - 使用方法："
            wait(wrd(0.5,0.9))
            msg += "\n    - ^base32 encode*decode [内容]"
        await base32_eventer.finish(msg)
    else:
        await base32_eventer.finish("TLoH Bot Base32 编解码\n  您的账号已被封禁，无法使用此功能")

base16_eventer = on_command("base16", aliases={"b16"}, priority=10)

@base16_eventer.handle()
async def _(event: MessageEvent,args: Message = CommandArg()):
    user = dc.User(event.get_user_id())
    if not user.isBanned():
        msg = ""
        if params := args.extract_plain_text():
            msg += "\nTLoH Bot Base16 编解码"
            params_l = params.split(" ")
            if params_l[0] == "encode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n编码为：\n{base64.b16encode(params_l[1].encode()).decode()}"
            elif params_l[0] == "decode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n解码为：\n{base64.b16decode(params_l[1].encode()).decode()}"
            else:
                wait(wrd(0.5,0.9))
                msg += "\n    - 使用方法："
                wait(wrd(0.5,0.9))
                msg += "\n    - ^base16 encode*decode [内容]"
        else:
            msg += "\nTLoH Bot Base16 编解码"
            wait(wrd(0.5,0.9))
            msg += "\n    - 使用方法："
            wait(wrd(0.5,0.9))
            msg += "\n    - ^base16 encode*decode [内容]"
        await base16_eventer.finish(msg)
    else:
        await base16_eventer.finish("TLoH Bot Base16 编解码\n  您的账号已被封禁，无法使用此功能")

base85_eventer = on_command("base85", aliases={"b85"}, priority=10)

@base85_eventer.handle()
async def _(event: MessageEvent,args: Message = CommandArg()):
    user = dc.User(event.get_user_id())
    if not user.isBanned():
        msg = ""
        if params := args.extract_plain_text():
            msg += "\nTLoH Bot Base85 编解码"
            params_l = params.split(" ")
            if params_l[0] == "encode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n编码为：\n{base64.b85encode(params_l[1].encode()).decode()}"
            elif params_l[0] == "decode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n解码为：\n{base64.b85decode(params_l[1].encode()).decode()}"
            else:
                msg += "\n    - 使用方法："
                wait(wrd(0.5,0.9))
                msg += "\n    - ^base85 encode*decode [内容]"
        else:
            msg += "\nTLoH Bot Base85 编解码"
            wait(wrd(0.5,0.9))
            msg += "\n    - 使用方法："
            wait(wrd(0.5,0.9))
            msg += "\n    - ^base85 encode*decode [内容]"
        await base85_eventer.finish(msg)
    else:
        await base85_eventer.finish("TLoH Bot Base85 编解码\n  您的账号已被封禁，无法使用此功能")

base58_eventer = on_command("base58", aliases={"b58"}, priority=10)

@base58_eventer.handle()
async def _(event: MessageEvent,args: Message = CommandArg()):
    user = dc.User(event.get_user_id())
    if not user.isBanned():
        msg = ""
        if params := args.extract_plain_text():
            msg += "\nTLoH Bot Base58 编解码"
            params_l = params.split(" ")
            if params_l[0] == "encode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n编码为：\n{base58.b58encode(params_l[1].encode()).decode()}"
            elif params_l[0] == "decode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1]} \n解码为：\n{base58.b58decode(params_l[1].encode()).decode()}"
            else:
                wait(wrd(0.5,0.9))
                msg += "\n    - 使用方法："
                wait(wrd(0.5,0.9))
                msg += "\n    - ^base58 encode*decode [内容]"
        else:
            msg += "\nTLoH Bot Base58 编解码"
            wait(wrd(0.5,0.9))
            msg += "\n    - 使用方法："
            wait(wrd(0.5,0.9))
            msg += "\n    - ^base58 encode*decode [内容]"
        await base58_eventer.finish(msg)
    else:
        await base58_eventer.finish("TLoH Bot Base58 编解码\n  您的账号已被封禁，无法使用此功能")

# 神经病用的 base64
# 凉菜64编码表
liangcai64 = [
    "退群", "手抄", "鳝丝", "解析", "消息", "回应", "原来", "国人",
    "烦人", "英语", "T3", "出行", "哎哎", "是你", "扁。", "时间",
    "模因", "收藏", "拆家", "瞎搞", "刷屏", "MC", "资助", "两百",
    "劳达", "写诗", "门口", "午睡", "视力", "ai", "解密", "格式",
    "煞笔", "抄错", "漏抄", "评分", "文档", "荣耀", "瓶颈", "凉菜",
    "奇才", "群u", "赞助", "进群", "苹果", "管理", "按钮", "奇异",
    "w。", "推流", "剪辑", "啊及", "群友", "瞎镐", "你们", "抽象",
    "松柏", "神经", "站点", "观察", "跑酷", "网站", "抓人", "TT"
]

# 创建反向映射表（从词汇到索引）
reverse_map = {word: index for index, word in enumerate(liangcai64)}

def encode_to_liangcai(text: list[str]) -> str:
    """
    编码函数：将文本编码为凉菜64词汇

    :param text: 要编码的文本

    :return: 凉菜64编码字符串
    """
    if not text:
        return ""

    _text = ""
    for _t in text:
        _text += _t

    # 将文本转换为UTF-8字节
    bytes_data = _text.encode('utf-8')

    binary = ''
    # 将每个字节转换为8位二进制字符串
    for byte in bytes_data:
        binary += format(byte, '08b')

    # 计算需要补零的数量，使总位数是6的倍数
    padding = (6 - (len(binary) % 6)) % 6
    binary += '0' * padding

    encoded_list = []
    # 每6位二进制对应一个凉菜64词汇
    for i in range(0, len(binary), 6):
        chunk = binary[i:i+6]
        index = int(chunk, 2)
        encoded_list.append(liangcai64[index])

    return ' '.join(encoded_list)

def decode_from_liangcai(encoded_text: list[str]) -> str:
    """
    解码函数：将凉菜64编码解码为文本

    :param encoded_text: 凉菜64编码字符串

    :return: 解码后的文本
    """
    if not encoded_text:
        return ""

    words = encoded_text
    binary = ''

    # 将每个词汇转换为对应的6位二进制字符串
    for word in words:
        if word not in reverse_map:
            return "请输入正确的编码字符"
        index = reverse_map[word]
        binary += format(index, '06b')

    # 检查二进制长度是否为8的倍数，并去除末尾的补位零
    num_bytes = len(binary) // 8
    binary = binary[:num_bytes * 8]

    bytes_data = bytearray()
    # 每8位二进制对应一个字节
    for i in range(0, len(binary), 8):
        byte_str = binary[i:i+8]
        if len(byte_str) == 8:
            bytes_data.append(int(byte_str, 2))

    # 将字节数组转换为文本
    return bytes_data.decode('utf-8')

def encode_to_liangcai2(text: list[str]) -> str:
    liangcai64__ = encode_to_liangcai(text)
    # add reverse
    reverse = ""
    for n in [word for word in liangcai64__]:
        _reverse = reverse
        reverse = n + _reverse

    l_lc64 = len(liangcai64__)

    for lcc in [word for word in liangcai64__]:
        if lcc == " ":
            l_lc64 -= 1

    liangcai64__ += " " + reverse

    return liangcai64__ + " " + str(l_lc64)

def decode_from_liangcai2(text: list[str]) -> str:
    # get max length from foot
    try:
        length = int(text [len(text) - 1])
    except Exception as ex:
        print(ex.__str__())
        return "ERROR, Developer please see log."

    # calc real length
    if length % 2 != 0:
        length -= 1

    print(length)
    length = int(length / 2)

    print(length)
    # get source text
    _text = text[0:length]

    print(_text)

    # decode
    return decode_from_liangcai(_text)

"""
LiangCai 64 编码
神经病一般的编码
"""
liangcai64_function = on_command("lc64", aliases={"liangCai64"}, priority=10)

@liangcai64_function.handle()
async def _ (event: MessageEvent,args: Message = CommandArg()):
    user = dc.User(event.get_user_id())
    # for finaleScope

    if not user.isBanned():
        msg = ""
        if params := args.extract_plain_text():
            msg += "\nTLoH Bot LiangCai64 编解码"
            params_l = params.split(" ")
            if params_l[0] == "encode":
                wait(wrd(0.5,0.9))
                params__ = "".join(params_l [1:])
                msg += f"\n{params_l[1:]} \n编码为：\n{encode_to_liangcai(params_l [1:])}"
            elif params_l[0] == "decode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1:]} \n解码为：\n{decode_from_liangcai(params_l [1:])}"
            else:
                wait(wrd(0.5,0.9))
                msg += "\n    - 使用方法："
                wait(wrd(0.5,0.9))
                msg += "\n    - ^lc64 encode*decode [内容]"
        else:
            msg += "\nTLoH Bot LiangCai64 编解码"
            wait(wrd(0.5,0.9))
            msg += "\n    - 使用方法："
            wait(wrd(0.5,0.9))
            msg += "\n    - ^lc64 encode*decode [内容]"
        await liangcai64_function.finish(msg)
    else:
        await liangcai64_function.finish("TLoH Bot LiangCai64 编解码\n  您的账号已被封禁，无法使用此功能")

"""
LiangCai 64/2 编码
神经病一般的的般一病经神
编码码编
"""
liangcai642_function = on_command("lc64_2", aliases={"liangCai64"}, priority=10)

@liangcai642_function.handle()
async def _ (event: MessageEvent,args: Message = CommandArg()):
    user = dc.User(event.get_user_id())
    if not user.isBanned():
        msg = ""
        if params := args.extract_plain_text():
            msg += "\nTLoH Bot LiangCai64/2 编解码"
            params_l = params.split(" ")
            if params_l[0] == "encode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1:]} \n编码为：\n{encode_to_liangcai2(params_l [1:])}"
            elif params_l[0] == "decode":
                wait(wrd(0.5,0.9))
                msg += f"\n{params_l[1:]} \n解码为：\n{decode_from_liangcai2(params_l [1:])}"
            else:
                wait(wrd(0.5,0.9))
                msg += "\n    - 使用方法："
                wait(wrd(0.5,0.9))
                msg += "\n    - ^lc64_2 encode*decode [内容]"
        else:
            msg += "\nTLoH Bot LiangCai64 编解码"
            wait(wrd(0.5,0.9))
            msg += "\n    - 使用方法："
            wait(wrd(0.5,0.9))
            msg += "\n    - ^lc64_2 encode*decode [内容]"
        await liangcai642_function.finish(msg)
    else:
        await liangcai642_function.finish("TLoH Bot LiangCai64 / 2 编解码\n  您的账号已被封禁，无法使用此功能")