import os
import json
import requests
import random
import hashlib
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict

# ===================== 【配置区】 =====================
# 从环境变量读取（GitHub Secrets 传递进来）
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK", "")

# GitHub Actions 手动触发参数
SPECIFIC_PET = os.environ.get("SPECIFIC_PET", "")  # 指定生成的宠物品种
SKIP_FEISHU = os.environ.get("SKIP_FEISHU", "false").lower() == "true"  # 跳过飞书推送
FORCE_REGENERATE = os.environ.get("FORCE_REGENERATE", "false").lower() == "true"  # 强制重新生成

MINIMAX_API_URL = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
MINIMAX_MODELS = ["MiniMax-M2.7-highspeed", "MiniMax-M2.5-highspeed"]
MINIMAX_TIMEOUT = (20, 180)
MINIMAX_MAX_COMPLETION_TOKENS = 1800
MINIMAX_RETRY_DELAY_SECONDS = 3
FEISHU_CHUNK_SIZE = 2500

# 数据文件
HISTORY_FILE = "sent_pets_history.json"
PET_DATABASE_FILE = "pet_database.json"

# 搜索关键词配置
SEARCH_KEYWORDS = [
    "2024最受欢迎宠物品种",
    "热门宠物狗品种排行",
    "网红宠物猫品种",
    "小型宠物犬推荐",
    "大型宠物犬品种",
    "适合家养的宠物"
]
# ==============================================================

class PetContentManager:
    """宠物内容管理器"""
    
    def __init__(self):
        self.history = self._load_history()
        self.pet_database = self._load_pet_database()
    
    def _load_history(self) -> List[Dict]:
        """加载历史记录"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_history(self):
        """保存历史记录"""
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def _load_pet_database(self) -> List[str]:
        """加载宠物数据库"""
        if os.path.exists(PET_DATABASE_FILE):
            try:
                with open(PET_DATABASE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("pets", [])
            except:
                return self._get_default_pets()
        return self._get_default_pets()
    
    def _save_pet_database(self):
        """保存宠物数据库"""
        data = {
            "pets": self.pet_database,
            "last_updated": datetime.now().isoformat(),
            "total_count": len(self.pet_database)
        }
        with open(PET_DATABASE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _get_default_pets(self) -> List[str]:
        """获取默认宠物列表"""
        return [
            "拉布拉多","金毛","柯基","泰迪","比熊","萨摩耶","哈士奇","德牧","柴犬","法斗",
            "边牧","阿拉斯加","博美","吉娃娃","雪纳瑞","巴哥","约克夏","马尔济斯","贵宾犬","秋田犬",
            "布偶猫","英短猫","美短猫","暹罗猫","加菲猫","蓝猫","缅因猫","金渐层","银渐层","无毛猫",
            "波斯猫","俄罗斯蓝猫","挪威森林猫","苏格兰折耳猫","孟加拉豹猫","狸花猫","橘猫","奶牛猫"
        ]
    
    def fetch_trending_pets_from_web(self) -> List[str]:
        """从网络搜索热门宠物品种"""
        print("🔍 正在从网络搜索最新热门宠物品种...")
        
        new_pets = set(self.pet_database)
        
        # 使用简单的网络抓取逻辑（实际应用中可以用API）
        try:
            # 模拟从搜索引擎获取热门宠物
            # 在实际使用中，这里可以接入真实的搜索API
            
            # 添加一些2024-2025年流行的新品种
            trending_pets = [
                "柯基","法斗","柴犬","布偶猫","金毛","边牧",
                "德文卷毛猫","曼基康猫","威尔士柯基","迷你杜宾",
                "茶杯犬","小鹿犬","西高地白梗","苏牧","喜乐蒂",
                "拿破仑猫","矮脚猫","无毛猫","豹猫","土猫"
            ]
            
            for pet in trending_pets:
                new_pets.add(pet)
            
            self.pet_database = list(new_pets)
            self._save_pet_database()
            
            print(f"✅ 宠物数据库已更新，当前共有 {len(self.pet_database)} 个品种")
            return self.pet_database
            
        except Exception as e:
            print(f"⚠️ 网络搜索失败：{e}，使用现有数据库")
            return self.pet_database
    
    def is_recently_generated(self, pet_name: str, days: int = 30) -> bool:
        """检查是否在指定天数内生成过"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for record in self.history:
            if record.get("pet_name") == pet_name:
                generated_date = datetime.fromisoformat(record.get("generated_at", "2020-01-01"))
                if generated_date > cutoff_date:
                    return True
        return False
    
    def get_content_hash(self, content: str) -> str:
        """生成内容哈希值用于去重"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def select_today_pet(self) -> str:
        """智能选择今日宠物"""
        # 更新宠物数据库
        self.fetch_trending_pets_from_web()
        
        # 获取未生成或很久未生成的宠物
        available_pets = []
        
        for pet in self.pet_database:
            if not self.is_recently_generated(pet, days=30):
                available_pets.append(pet)
        
        # 如果所有宠物都生成过，选择最久未生成的
        if not available_pets:
            print("ℹ️ 所有宠物近期都已生成，选择最久未生成的...")
            
            pet_last_gen = {}
            for pet in self.pet_database:
                last_date = None
                for record in self.history:
                    if record.get("pet_name") == pet:
                        gen_date = datetime.fromisoformat(record.get("generated_at", "2020-01-01"))
                        if last_date is None or gen_date > last_date:
                            last_date = gen_date
                
                pet_last_gen[pet] = last_date or datetime(2020, 1, 1)
            
            # 选择最久未生成的
            selected_pet = min(pet_last_gen.items(), key=lambda x: x[1])[0]
        else:
            selected_pet = random.choice(available_pets)
        
        print(f"📌 今日选择品种：{selected_pet}")
        return selected_pet
    
    def save_generation_record(self, pet_name: str, prompt: str, content_summary: str = ""):
        """保存生成记录"""
        record = {
            "pet_name": pet_name,
            "generated_at": datetime.now().isoformat(),
            "content_hash": self.get_content_hash(prompt),
            "summary": content_summary[:200]  # 保存前200字符作为摘要
        }
        self.history.append(record)
        self._save_history()
        print(f"💾 已保存 {pet_name} 的生成记录")


def extract_generated_text(data: Dict) -> str:
    """兼容不同返回结构，提取模型文本"""
    generated_text = ""
    if isinstance(data, dict):
        generated_text = (data.get("reply") or "").strip()
        if not generated_text:
            choices = data.get("choices") or []
            if choices and isinstance(choices, list):
                first = choices[0] if isinstance(choices[0], dict) else {}
                message = first.get("message") if isinstance(first, dict) else {}
                if isinstance(message, dict):
                    generated_text = (message.get("content") or "").strip()
                if not generated_text:
                    generated_text = (first.get("text") or "").strip() if isinstance(first, dict) else ""
        if not generated_text:
            generated_text = (data.get("output_text") or "").strip()
    return generated_text


def build_image_generation_prompt(pet_name: str) -> str:
    """固定生成独立图片Prompt，避免模型漏掉图片部分"""
    return f"""【图片生成Prompt】

请为【{pet_name}】输出 3 组可直接用于图片模型的写实风格图片生成 Prompt。

通用要求：
- 所有图片都必须是写实摄影风格
- 所有画面中禁止出现任何文字、字母、logo、水印、贴纸、海报字
- 画面干净、自然、温暖、真实，有宠物摄影质感
- 每组都必须包含：图X用途、中文提示词、English prompt、Negative prompt

图1用途：封面图
中文提示词：超高清写实照片，可爱的{pet_name}幼宠特写，毛发纤毫毕现，温柔眼神看向镜头，柔和自然光，浅景深背景虚化，专业摄影质感，暖色调，治愈氛围，16:9横版构图，画面干净，无任何文字、字母、logo、水印、贴纸
English prompt: ultra realistic pet photography, cute young {pet_name}, close-up portrait, detailed fur, gentle eye contact, soft natural light, shallow depth of field, warm tone, healing atmosphere, clean background, 16:9 composition, no text, no letters, no logo, no watermark, no sticker
Negative prompt: text, letters, logo, watermark, sticker, blurry, low resolution, distorted anatomy, duplicate limbs, messy background, oversaturated

图2用途：正文配图-日常互动
中文提示词：{pet_name}幼宠和主人在客厅玩耍，温馨家庭氛围，抓拍感，写实摄影风格，自然光线，构图干净，生活化场景，画面中无任何文字元素
English prompt: realistic lifestyle pet photography, young {pet_name} playing with owner in living room, warm family atmosphere, candid shot, natural lighting, clean composition, cozy home scene, no text, no letters, no logo, no watermark
Negative prompt: text, letters, logo, watermark, poster text, blurry, low resolution, distorted hands, distorted paws, duplicate limbs, cluttered scene

图3用途：正文配图-护理训练
中文提示词：{pet_name}幼宠在接受喂食、基础训练或健康检查，生活化真实场景，写实摄影风格，光线柔和，主体清晰，画面干净，无任何文字、字母、logo、水印
English prompt: realistic pet care photography, young {pet_name} during feeding or basic training or health check, natural lifestyle scene, soft lighting, sharp subject, clean frame, no text, no letters, no logo, no watermark
Negative prompt: text, letters, logo, watermark, sticker, blurry, low resolution, distorted anatomy, duplicate limbs, messy background, artificial props overload
"""


# ===================== Minimax 生成超高质量Prompt =====================
def generate_ultra_high_quality_prompt(pet_name: str) -> str:
    """生成文案Prompt，并拼接固定图片Prompt"""
    
    system_prompt = """
你是顶级宠物自媒体AI策划总监，拥有10年+小红书、知乎、公众号三平台运营经验。
你的任务不是直接写内容，而是输出一段可直接复制给 Codex 使用的【文案Prompt】。
不要输出任何解释、备注、前言，只输出文案Prompt本体。
"""

    user_prompt = f"""
请只生成【文案Prompt】部分，不要生成图片Prompt，不要输出别的章节。

文案目标：
- 宠物品种：{pet_name}
- 平台：小红书、知乎、公众号
- 目标人群：准备养宠、新手铲屎官、宠物爱好者
- 核心目标：高互动、高转化、强种草

文案Prompt必须要求 Codex 输出以下模块：
- 创作背景
- 小红书爆款标题（5选1）
- 开头钩子（3选1）
- 正文核心内容（1500-2000字，分5大模块）
- 互动引导话术
- 小红书标签（15个）
- 知乎专属优化
- 公众号排版建议

正文核心内容必须覆盖：
1. 品种真相与避坑指南
2. 性格特点与真实体验
3. 科学饲养攻略
4. 养宠成本大公开
5. 高频问答环节（10个）

风格要求：
- 语言生活化、有网感，像朋友聊天一样真诚
- 避免广告腔、避免假大空
- 用真实案例和数据说话
- 必须包含具体场景、具体问题、具体建议

输出格式要求：
- 第一行必须是【文案Prompt】
- 后面直接输出可给 Codex 使用的文案指令
- 不要输出【图片生成Prompt】
"""

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json"
    }

    last_error = None

    for index, model_name in enumerate(MINIMAX_MODELS, start=1):
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "name": "Prompt Architect", "content": system_prompt},
                {"role": "user", "name": "用户", "content": user_prompt}
            ],
            "temperature": 0.7,
            "top_p": 0.9,
            "max_completion_tokens": MINIMAX_MAX_COMPLETION_TOKENS,
            "stream": False
        }

        try:
            print(f"🤖 正在调用Minimax生成高质量Prompt... model={model_name}")
            response = requests.post(
                MINIMAX_API_URL,
                json=payload,
                headers=headers,
                timeout=MINIMAX_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            base_resp = data.get("base_resp") if isinstance(data, dict) else None
            if isinstance(base_resp, dict) and base_resp.get("status_code") not in (None, 0):
                raise ValueError(
                    f"MiniMax业务错误：status_code={base_resp.get('status_code')}, "
                    f"status_msg={base_resp.get('status_msg', '')}"
                )

            copy_prompt = extract_generated_text(data)

            if not copy_prompt:
                preview = str(data)[:500]
                raise ValueError(f"模型返回为空，响应预览：{preview}")

            if not copy_prompt.startswith("【文案Prompt】"):
                copy_prompt = f"【文案Prompt】\n\n{copy_prompt}"

            image_prompt = build_image_generation_prompt(pet_name)
            final_prompt = f"{copy_prompt}\n\n{image_prompt}"

            if "【文案Prompt】" not in final_prompt or "【图片生成Prompt】" not in final_prompt:
                raise ValueError("最终Prompt缺少必要章节")

            print(f"✅ Prompt生成成功，模型：{model_name}，长度：{len(final_prompt)} 字符")
            return final_prompt
        except requests.exceptions.ReadTimeout as e:
            last_error = f"模型 {model_name} 响应超时：{e}"
            print(f"⚠️ {last_error}")
        except Exception as e:
            last_error = f"模型 {model_name} 调用失败：{e}"
            print(f"⚠️ {last_error}")

        if index < len(MINIMAX_MODELS):
            print(f"🔁 {MINIMAX_RETRY_DELAY_SECONDS} 秒后切换到下一个模型重试...")
            time.sleep(MINIMAX_RETRY_DELAY_SECONDS)

    error_msg = f"❌ Minimax调用失败：{last_error}"
    print(error_msg)
    return error_msg


# ===================== 发送到飞书 =====================
def split_text(text: str, chunk_size: int) -> List[str]:
    """按固定大小切分文本，避免单条消息过长被平台拒绝"""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)] or [""]


def send_feishu_text(text: str):
    """发送单条飞书文本消息，并严格校验响应结果"""
    msg_data = {
        "msg_type": "text",
        "content": {"text": text}
    }

    response = requests.post(FEISHU_WEBHOOK, json=msg_data, timeout=20)
    body_preview = response.text[:500]

    if response.status_code != 200:
        raise RuntimeError(f"飞书HTTP异常：status={response.status_code}, body={body_preview}")

    try:
        data = response.json()
    except ValueError:
        print(f"ℹ️ 飞书返回非JSON内容：{body_preview}")
        return

    if isinstance(data, dict):
        code = data.get("code")
        status_code = data.get("StatusCode")
        if code not in (None, 0) or status_code not in (None, 0):
            raise RuntimeError(f"飞书业务返回异常：{json.dumps(data, ensure_ascii=False)}")

    print(f"✅ 飞书发送成功：{body_preview}")


def send_to_feishu(pet: str, final_prompt: str, stats: Dict):
    """发送到飞书，包含统计信息"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 宠物自媒体每日创作Prompt已生成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 生成时间：{now}
🐾 今日品种：{pet}
📊 数据库统计：
   - 总品种数：{stats.get('total_pets', 0)}
   - 已生成数：{stats.get('generated_count', 0)}
   - 待生成数：{stats.get('pending_count', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 使用说明：
1. 复制下方完整Prompt
2. 粘贴到本地Codex或Claude
3. 一键生成小红书+知乎+公众号三平台内容
4. 配合AI生成图片，完美发布

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⬇️⬇️⬇️ 以下是完整Prompt，直接复制使用 ⬇️⬇️⬇️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    footer_message = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⬆️⬆️⬆️ Prompt结束 ⬆️⬆️⬆️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 提示：
- 此Prompt已针对三平台算法优化
- 包含完整的标题、正文、图片、标签
- 互动引导话术已嵌入，可直接使用
- 建议使用Midjourney/DALL-E生成配图

🔥 下次推送时间：明天同一时间
"""

    send_feishu_text(header_message)

    prompt_chunks = split_text(final_prompt, FEISHU_CHUNK_SIZE)
    for index, chunk in enumerate(prompt_chunks, start=1):
        chunk_message = f"[Prompt {index}/{len(prompt_chunks)}]\n{chunk}"
        send_feishu_text(chunk_message)

    send_feishu_text(footer_message)


# ===================== 主程序 =====================
def main():
    """主程序入口"""
    print("=" * 60)
    print("🚀 宠物自媒体AI创作系统 v2.0")
    print("=" * 60)
    
    # 检查必要的环境变量
    if not MINIMAX_API_KEY:
        print("❌ 错误：未设置 MINIMAX_API_KEY 环境变量")
        return 1
    
    if not FEISHU_WEBHOOK and not SKIP_FEISHU:
        print("❌ 错误：未设置 FEISHU_WEBHOOK，且当前未启用 skip_feishu")
        return 1

    print(f"🔐 FEISHU_WEBHOOK 已配置：{'是' if bool(FEISHU_WEBHOOK) else '否'}")
    
    # 显示运行模式
    if SPECIFIC_PET:
        print(f"🎯 手动模式：指定品种 [{SPECIFIC_PET}]")
    if SKIP_FEISHU:
        print("⏭️  已跳过飞书推送（测试模式）")
    if FORCE_REGENERATE:
        print("⚡ 强制重新生成模式（忽略30天限制）")
    
    # 初始化管理器
    manager = PetContentManager()
    
    # 智能选择今日宠物
    if SPECIFIC_PET:
        # 手动指定品种
        if SPECIFIC_PET in manager.pet_database:
            today_pet = SPECIFIC_PET
            print(f"✅ 使用手动指定的品种：{today_pet}")
        else:
            print(f"⚠️ 品种 [{SPECIFIC_PET}] 不在数据库中，将添加并使用")
            manager.pet_database.append(SPECIFIC_PET)
            manager._save_pet_database()
            today_pet = SPECIFIC_PET
    else:
        # 自动选择
        today_pet = manager.select_today_pet()
    
    # 检查是否需要重新生成
    if not FORCE_REGENERATE and manager.is_recently_generated(today_pet, days=30):
        print(f"ℹ️ 品种 [{today_pet}] 在30天内已生成过")
        print("💡 提示：如需强制重新生成，请在 GitHub Actions 手动触发时勾选 'force_regenerate'")
        
        # 询问是否继续（仅在非自动模式下）
        if SPECIFIC_PET or FORCE_REGENERATE:
            print("⏩ 继续生成...")
        else:
            print("⏭️ 跳过本次生成")
            return 0
    
    # 生成高质量Prompt
    final_prompt = generate_ultra_high_quality_prompt(today_pet)
    
    # 防止空内容或错误信息被继续推送/写入
    if (not final_prompt.strip()) or final_prompt.startswith("❌ Minimax调用失败："):
        print("❌ 本次生成结果无效，已中止后续保存与推送")
        return 1

    # 保存生成记录
    summary = final_prompt[:200] if len(final_prompt) > 200 else final_prompt
    manager.save_generation_record(today_pet, final_prompt, summary)
    
    # 准备统计数据
    stats = {
        'total_pets': len(manager.pet_database),
        'generated_count': len(manager.history),
        'pending_count': len([p for p in manager.pet_database 
                             if not manager.is_recently_generated(p, days=30)])
    }
    
    # 发送到飞书
    if FEISHU_WEBHOOK and not SKIP_FEISHU:
        send_to_feishu(today_pet, final_prompt, stats)
    elif SKIP_FEISHU:
        print("⏭️ 已跳过飞书推送（测试模式）")
    
    # 输出到控制台
    print("\n" + "=" * 60)
    print(f"✅ 任务完成！今日品种：{today_pet}")
    print(f"📊 统计：总{stats['total_pets']}种，已生成{stats['generated_count']}次，待生成{stats['pending_count']}种")
    print("=" * 60)
    
    # 可选：保存到本地文件
    output_file = f"prompt_{today_pet}_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_prompt)
    print(f"💾 Prompt已保存至：{output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
