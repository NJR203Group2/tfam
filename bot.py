# ===在 bot.py 裡「載入 CSV」===
# bot.py
import csv
import os

# 取得專案目錄
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "tfam_exhibitions.csv")

# 啟動時讀一次 CSV 到記憶體
def load_exhibitions():
    rows = []
    with open(CSV_PATH, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

EXHIBITIONS = load_exhibitions()


# ===讓Bot 可以用關鍵字查展覽，例如查「美術館」、「兒童」之類。===
def search_exhibitions(keyword: str, limit: int = 5):
    keyword = keyword.strip()
    if not keyword:
        return []

    result = []
    for row in EXHIBITIONS:
        name = row.get("展覽名稱", "")
        desc = row.get("展區說明", "")
        addr = row.get("地址", "")
        if (keyword in name) or (keyword in desc) or (keyword in addr):
            result.append(row)
        if len(result) >= limit:
            break
    return result


def format_exhibitions_message(records):
    if not records:
        return "找不到符合的展覽，可以試試其他關鍵字～"

    lines = []
    for r in records:
        line = (
            f"《{r.get('展覽名稱', '未命名展覽')}》\n"
            f"📍 地址：{r.get('地址', '無資料')}\n"
            f"⏰ 開放時間：{r.get('開放時間', '無資料')}\n"
            f"📝 展區說明：{r.get('展區說明', '無資料')}\n"
            "－－－－－－"
        )
        lines.append(line)

    return "\n".join(lines)


# ===接到 Line Bot 的文字訊息事件===
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

# 建議用環境變數存，以後部署比較安全
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "你的access token")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "你的secret")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event: MessageEvent):
    user_text = event.message.text

    # Step 1: 用使用者訊息當關鍵字查 CSV
    records = search_exhibitions(user_text)

    # Step 2: 把查到的資料格式化成文字
    reply_text = format_exhibitions_message(records)

    # Step 3: 回覆給使用者
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )


if __name__ == "__main__":
    # 本機測試用
    app.run(host="0.0.0.0", port=8000)
