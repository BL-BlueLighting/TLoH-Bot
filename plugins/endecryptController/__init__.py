import base64

import Crypto.Cipher.AES as AES
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.params import CommandArg

# 假设 User 和 TITLE 已经从 userInfoController 中导入
from plugins.userInfoController import TITLE, User

"""
AES 加密解密功能

@author: BL-BlueLighting
"""

# --- AES 加密/解密函数 ---

def _pad_to_16(message: str) -> bytes:
    """Pads a string to be a multiple of 16 bytes for AES."""
    while len(message.encode('utf-8')) % 16 != 0:
        message += '\0'
    return message.encode('utf-8')

def _unpad_from_16(message: bytes) -> str:
    """Removes null padding and decodes a bytes object."""
    return message.decode('utf-8').rstrip('\0')

def encrypt_aes(message: str, key_pri: str) -> str:
    """Encrypts a string using AES in ECB mode."""
    key_bytes = _pad_to_16(key_pri)
    aes = AES.new(key_bytes, AES.MODE_ECB)
    message_bytes = _pad_to_16(message)
    encrypted_bytes = aes.encrypt(message_bytes)
    return base64.b64encode(encrypted_bytes).decode('utf-8')

def decrypt_aes(message: str, key_pri: str) -> str:
    """Decrypts a base64 encoded string using AES in ECB mode."""
    try:
        key_bytes = _pad_to_16(key_pri)
        aes = AES.new(key_bytes, AES.MODE_ECB)
        decoded_bytes = base64.b64decode(message)
        decrypted_bytes = aes.decrypt(decoded_bytes)
        return _unpad_from_16(decrypted_bytes)
    except (ValueError, TypeError, UnicodeDecodeError) as e:
        print(f"Decryption error: {e}")
        return "解密失败：可能是密钥错误或密文不合法。"

# --- NoneBot 命令处理函数 ---

aes_eventer = on_command("aes", aliases={"加密", "解密"}, priority=5, block=True)

@aes_eventer.handle()
async def _(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    user = User(str(event.get_user_id()))

    if user.isBanned():
        await aes_eventer.finish(f"{TITLE} AES 加密解密\n    - 您的账号已被封禁，无法执行此操作。")

    params = args.extract_plain_text().strip()

    # 如果没有提供参数，输出帮助信息
    if not params:
        await aes_eventer.finish(f"{TITLE} AES 加密解密\n"
                                 "    - 用法: *aes [encrypt|decrypt] [内容] [密钥]\n"
                                 "    - 示例: *aes encrypt Hello my_key")

    params_list = params.split(" ", 2)

    # 检查参数数量
    if len(params_list) < 3:
        await aes_eventer.finish(f"{TITLE} AES 加密解密\n"
                                 "    - 错误: 参数不足。用法: *aes [encrypt|decrypt] [内容] [密钥]")

    action, content, key = params_list

    # 异步操作通常不使用 sleep，但为了模拟原代码的延迟效果，这里保留
    # 在实际项目中，应避免使用 sleep，因为它会阻塞事件循环
    # await asyncio.sleep(random.uniform(0.5, 0.9))

    msg = f"{TITLE} AES 加密解密"

    if action == "encrypt":
        result = encrypt_aes(content, key)
        msg += f"\n    - 内容: {content}\n    - 密钥: {key}\n    - 加密结果:\n{result}"
    elif action == "decrypt":
        result = decrypt_aes(content, key)
        msg += f"\n    - 内容: {content}\n    - 密钥: {key}\n    - 解密结果:\n{result}"
    else:
        msg += f"\n    - 错误: 未知操作 '{action}'。\n    - 用法: *aes [encrypt|decrypt] [内容] [密钥]"

    await aes_eventer.finish(msg)