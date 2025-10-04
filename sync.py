import tweepy
import requests
import os
from datetime import datetime
from dotenv import load_dotenv
import re

# 加载环境变量
load_dotenv()

# ======================
# 初始化 API 客户端
# ======================

# X API Client
client = tweepy.Client(bearer_token=os.getenv("BEARER_TOKEN"))

# Notion Headers
NOTION_HEADERS = {
    "Authorization": f"Bearer {os.getenv('NOTION_API_KEY')}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ======================
# 工具函数
# ======================

def extract_urls(text):
    return re.findall(r'https?://[^\s]+', text)

def find_first_http_link(text):
    urls = extract_urls(text)
    return urls[0] if urls else None

def is_tool_related(text):
    keywords = [
        'ai', '人工智能', '大模型', 'llm', 'chatgpt', '工具', '效率', 'productivity',
        'notion', 'obsidian', 'figma', '设计', '学习', '教程', 'workflow', 'automation',
        'app', '软件', '平台', '发布', '更新', '新功能'
    ]
    text_lower = text.lower()
    return any(k in text_lower for k in keywords)

def classify_tweet(text):
    text_lower = text.lower()
    if any(k in text_lower for k in ['ai', '人工智能', '大模型', 'llm', 'chatgpt']):
        return "AI工具"
    elif any(k in text_lower for k in ['notion', 'obsidian', '效率', 'productivity', 'workflow']):
        return "效率工具"
    elif any(k in text_lower for k in ['figma', '设计', 'ui', 'ux']):
        return "设计工具"
    elif any(k in text_lower for k in ['学习', '笔记', '知识管理', 'readwise']):
        return "学习方法"
    else:
        return "其他"

def generate_summary(text, urls=None):
    # 简化版摘要：取前 100 字 + 省略号
    # 进阶版：可接入 Qwen/OpenAI API
    if len(text) <= 100:
        return text
    return text[:100] + "..."

def create_notion_page(tweet_data):
    created_time = tweet_data['created_at'].replace('T', ' ').replace('Z', '+00:00')

    data = {
        "parent": { "database_id": os.getenv("NOTION_DATABASE_ID") },
        "properties": {
            "Name": {
                "title": [{ "text": { "content": tweet_data['title'][:100] } }]
            },
            "类型": {
                "select": { "name": tweet_data['type'] }
            },
            "摘要": {
                "rich_text": [{ "text": { "content": tweet_data['summary'][:200] } }]
            },
            "原文链接": {
                "url": tweet_data['x_url']
            },
            "工具链接": {
                "url": tweet_data.get('tool_url')
            },
            "时间": {
                "date": { "start": created_time }
            },
            "来源": {
                "rich_text": [{ "text": { "content": tweet_data['author'] } }]
            },
            "已读": {
                "checkbox": False
            }
        }
    }

    url = "https://api.notion.com/v1/pages"
    response = requests.post(url, headers=NOTION_HEADERS, json=data)

    if response.status_code == 201:
        print("✅ 成功写入 Notion：", tweet_data['title'])
    else:
        print("❌ 写入失败：", response.status_code, response.text)

# ======================
# 主逻辑
# ======================

def main():
    username = os.getenv("X_USERNAME")
    if not username:
        print("❌ 请在 .env 中设置 X_USERNAME")
        return

    # 获取用户 ID
    try:
        user = client.get_user(username=username)
        user_id = user.data.id
    except Exception as e:
        print("❌ 获取用户失败：", e)
        return

    # 获取最近 50 条喜欢的推文
    try:
        liked_tweets = client.get_liked_tweets(
            id=user_id,
            max_results=50,
            tweet_fields=['created_at', 'author_id', 'entities', 'context_annotations']
        )
    except Exception as e:
        print("❌ 获取喜欢的推文失败：", e)
        return

    if not liked_tweets.data:
        print("📭 没有获取到喜欢的推文")
        return

    print(f"🔍 检测到 {len(liked_tweets.data)} 条喜欢的推文")

    for tweet in liked_tweets.data:
        text = tweet.text
        if not is_tool_related(text):
            continue

        tool_url = find_first_http_link(text)
        title = text.strip().replace('\n', ' ')[:100]
        if len(title) > 97:
            title = title[:97] + "..."

        tweet_data = {
            'title': title,
            'summary': generate_summary(text, [tool_url] if tool_url else []),
            'type': classify_tweet(text),
            'x_url': f"https://x.com/{username}/status/{tweet.id}",
            'tool_url': tool_url,
            'created_at': tweet.created_at.isoformat(),
            'author': f"@{tweet.author_id}"
        }

        create_notion_page(tweet_data)

if __name__ == "__main__":
    main()
