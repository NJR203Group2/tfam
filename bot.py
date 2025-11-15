import os
from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 建立 Flask app
app = Flask(__name__)

# 從環境變數讀取 LINE 憑證
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")

if CHANNEL_ACCESS_TOKEN is None or CHANNEL_SECRET is None:
    raise ValueError("須在環境變數中設定 LINE_CHANNEL_ACCESS_TOKEN 與 LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)


@app.route("/", methods=['GET'])
def index():
    return "TFAM bot is running."


# LINE Webhook 入口
@app.route("/callback", methods=['POST'])
def callback():
    # 1. 取得簽章
    signature = request.headers.get('X-Line-Signature', '')

    # 2. 取得 body
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 3. 驗證簽章並處理事件
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.warning("Invalid signature. Please check channel secret / access token.")
        # 開發階段你也可以暫時回 200，讓 Verify 通過：
        # return "OK"
        abort(400)

    # 4. 一切正常回 200
    return "OK"


# 收到文字訊息時，回 Echo（同樣的文字）
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event: MessageEvent):
    user_text = event.message.text
    reply = f"你說：{user_text}"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )


if __name__ == "__main__":
    # 本機測試用，Railway 上會用 gunicorn 啟動
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
