import os
import csv

from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# -----------------------
# Flask app
# -----------------------
app = Flask(__name__)

# -----------------------
# LINE credentials (from Railway Variables)
# -----------------------
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if CHANNEL_ACCESS_TOKEN is None or CHANNEL_SECRET is None:
    raise ValueError("須在環境變數中設定 LINE_CHANNEL_ACCESS_TOKEN 與 LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# -----------------------
# CSV 讀取
# -----------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "tfam_exhibitions.csv")

def load_exhibitions():
    rows = []
    if not os.path.exists(CSV_PATH):
        # 若沒找到檔案，避免整個程式掛掉，先回傳空 list
        app.logger.warning(f"CSV 檔案不存在：{CSV_PATH}")
        return rows

    with open(CSV_PATH, newline='', encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    app.logger.info(f"已載入展覽資料 {len(rows)} 筆")
    return rows

EXHIBITIONS = load_exhibitions()

def search_exhibitions(keyword: str, limit: int = 5):
    """用關鍵字在 CSV 裡找展覽"""
    if not keyword or not EXHIBITIONS:
        return []

    keyword = keyword.strip()
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
    """把查到的展覽組成文字訊息"""
    if not records:
        return "找不到符合的展覽，可以試試其他關鍵字～"

    lines = []
    for r in records:
        line = (
            f"《{r.get('展覽名稱', '未命名展覽')}》\n"
            f"📍 地址：{r.get('地址', '無資料')}\n"
            f"⏰ 開放時間：{r.get('開放時間', '無資料')}\n"
            f"📝 展區說明：{r.get('展區說明', '無資料')}\n"
            "-------------------------"
        )
        lines.append(line)

    return "\n".join(lines)

# -----------------------
# Routes
# -----------------------
@app.route("/", methods=["GET"])
def index():
    return "TFAM bot is running."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.warning("Invalid signature. Please check channel secret / access token.")
        abort(400)

    return "OK"

# -----------------------
# LINE event handler
# -----------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event: MessageEvent):
    user_text = event.message.text.strip()

    # 1) 如果使用者打「echo xxx」就原文回覆
    if user_text.lower().startswith("echo "):
        reply_text = "你說：" + user_text[5:]
    else:
        # 2) 否則當作關鍵字查 CSV
        records = search_exhibitions(user_text)
        reply_text = format_exhibitions_message(records)

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
