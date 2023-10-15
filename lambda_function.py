import os, json, hmac, hashlib, base64, urllib
import urllib.request
import urllib.parse

def add_reaction(slack_token, channel_id, thread_ts):
    ##################
    ## リアクション付与
    ##################
    api_url = "https://slack.com/api/reactions.add"

    # 追加したいリアクション
    reaction = "white_check_mark"

    # Slack APIリクエストボディ
    params = {
        "token": slack_token,
        "channel": channel_id,
        "timestamp": thread_ts,
        "name": reaction
    }

    # パラメータをエンコード
    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request(api_url, data=data, method='POST')
    
    # Slack APIにPOSTリクエストを送信
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
    
    # メッセージの投稿に成功したかどうかを確認
    if data["ok"]:
        print("リアクションを付与しました。")
    else:
        print(f"エラー: {data['error']}")

def get_approval_count(api_url,token):
    # 承認済みのレビューコメントを取得
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    req = urllib.request.Request(api_url + "/reviews", headers=headers)
    response = urllib.request.urlopen(req)

    if response.getcode() == 200:
        reviews = json.loads(response.read().decode('utf-8'))
        approval_count = sum(1 for review in reviews if review["state"] == "APPROVED")
        return approval_count
    else:
        return None  # エラーが発生した場合に None を返す


def lambda_handler(event, context):
    ##################
    ## 環境変数定義
    ##################
    # Slack Webhook URL
    slack_webhook_url = os.environ.get('WebHookURL')  # SlackのWebhook URLを設定
   
    # Channel ID
    channel_id = os.environ.get('ChannelID')
    
    # Slack APIトークンを設定
    SLACK_USER_OAUTH_TOKEN = os.environ.get('UserOAuthToken')
    SLACK_BOT_USER_OAUTH_TOKEN = os.environ.get('BotUserOAuthToken')
    
    # 送信者と受信者で秘密情報であるSecretの値
    secret = os.environ.get('Secrets')
    
    ##################
    ## HMAC認証
    ##################
    # GitHubから送られてきた情報にあったHMAC値
    signature = event['headers']['X-Hub-Signature']
    
    # 「Secret + メッセージ + ハッシュ関数」でHMAC値を作る
    signedBody = "sha1=" + hmac.new(bytes(secret, 'utf-8'), bytes(event['body'], 'utf-8'), hashlib.sha1).hexdigest()
    
    # 2つのHMAC値が同じであったら改竄されていないと判断
    if(signature != signedBody):
        print('HMAC認証失敗')
        return {"statusCode": 401, "body": "Unauthorized" }
    else:
        print('HMAC認証成功')


    ##################
    ## メッセージ検索
    ##################
    # GitHubのWebhookからのデータを取得
    github_event = json.loads(event['body'])
    
    # Slack APIエンドポイントを定義
    api_url = "https://slack.com/api/search.messages"

    # 検索クエリを設定（pr_urlが含まれるメッセージを検索）
    search_query = github_event["pull_request"]["html_url"]

    # パラメータをエンコード
    params = {
        "query": search_query,
        "count": 1
    }
    
    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request(api_url, data)

    req.add_header("Authorization", f"Bearer {SLACK_USER_OAUTH_TOKEN}")

    # Slack APIにGETリクエストを送信
    with urllib.request.urlopen(req) as response:
        slack_logs = json.loads(response.read().decode('utf-8'))

    # メッセージを出力
    if slack_logs["ok"]:
        messages = slack_logs["messages"]["matches"]
        if messages:
            thread_ts = (messages[0]["ts"])
            print("該当するメッセージが見つかりました。")
        else:
            print("該当するメッセージが見つかりませんでした。")
            return {"statusCode": 404, "body": "Not Found" }
    else:
        print(f"エラー: {slack_logs['error']}")


    ##################
    ## メッセージ投稿
    ##################
    # Slack APIエンドポイントを定義
    api_url = "https://slack.com/api/chat.postMessage"

    # スレッドメッセージのテキスト、Slack APIにPOSTリクエストを送信する際のパラメータを設定
    if github_event["review"]["state"] == "approved":
        message_text = "approveされましたよ!"

        pr_url = github_event['pull_request']['url']
        token = os.environ.get('GitHub_Token')
        if (get_approval_count(pr_url,token) >= 2):    
            add_reaction(SLACK_BOT_USER_OAUTH_TOKEN, channel_id, thread_ts)

    elif github_event["review"]["state"] == "commented":
        message_text = "レビューコメントが来ましたよ！\n " + github_event["review"]["html_url"]

    # Slack APIにPOSTリクエストを送信する際のパラメータを設定
    params = {
        "token": SLACK_BOT_USER_OAUTH_TOKEN,
        "channel": channel_id,
        "text": message_text,
        "thread_ts": thread_ts
    }
    
    # パラメータをエンコード
    data = urllib.parse.urlencode(params).encode('utf-8')
    
    # POSTリクエストを作成
    req = urllib.request.Request(api_url, data=data, method='POST')
    
    # Slack APIにPOSTリクエストを送信
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))

    # メッセージの投稿に成功したかどうかを確認
    if data["ok"]:
        print("スレッドに返信しました。")
    else:
        print(f"エラー: {data['error']}")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Success"})  # Lambdaのレスポンスを返す
    }