# coding=utf-8
import requests
import time
import random
import re
import threading
import configparser

config = configparser.ConfigParser()
config.read('config.ini')
print(config['mastodon']['domain'])
meu = ["か゛ら゛出゛て゛く゛る゛め゛う゛〜゛〜゛〜゛！゛！゛","に゛入゛っ゛て゛く゛る゛め゛う゛ー゛！゛！゛！゛！゛！゛"]
pass_rules = [
    ["接頭辞", "名詞"],
    ["形容詞", "名詞"],  # ~なxxx
    ["名詞", "特殊", "名詞"],
    ["助動詞,助動詞する", "名詞"],  # ~するxxx
    ["動詞", "名詞"],  # ~するxxx
    ["助詞,助詞連体化", "名詞"],  # のxxx
    ["形容詞,形容,連用テ接続", "動詞", "助動詞,助動詞た", "名詞"],  # ~な-したxxx
    ["名詞", "助詞,格助詞,*,と,と,と", "動詞", "名詞"],  # xxxと~するyyy
    ["名詞", "助詞,格助詞,*,と,と,と", "名詞"],  # xxxとyyy
    ["形容動詞,形動", "助動詞,助動詞だ,体言接続,な,な,だ", "名詞"],  # ~なxxx
    ["名詞", "助詞,並立助詞"],  # xxxとか
]
URL = "https://jlp.yahooapis.jp/MAService/V2/parse"

def normalizeText(text):
    # メンション/RT除去
    if "@" in text:
        return False
    p = re.compile(r"<[^>]*?>")
    text = p.sub("", text)
    # URL除去
    return re.sub("http(|s)://.+?(\s|$)", r"\2", text)


def getAPI(text, appid):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Yahoo AppID: {}".format(appid),
    }
    param_dic = {
      "id": "1234-1",
      "jsonrpc": "2.0",
      "method": "jlp.maservice.parse",
      "params": {
        "q": text
      }
    }
    response = requests.post(URL, json=param_dic, headers=headers)
    if response.status_code != 200:
        return False

    result = response.json()
    # 新しいレスポンス形式に基づいて、必要なデータを抽出
    tokens = result.get("result", {}).get("tokens", [])
    
    # トークンのリストを辞書のリストに変換
    words = []
    for token in tokens:
        word = {
            "surface": token[0],  # 表層形
            "reading": token[1],  # 読み
            "base": token[2],     # 基本形
            "pos": token[3],      # 品詞
            "pos1": token[4],     # 品詞細分類1
            "pos2": token[5],     # 品詞細分類2
            "pos3": token[6]      # 品詞細分類3
        }
        words.append(word)

    return words



def checkStrict(i, data):
    for patterns in pass_rules:
        # 前後の単語を含めた範囲でnodesを作成
        nodes = data[max(0, i - len(patterns) + 1):i + 1] + data[i + 1:min(len(data), i + len(patterns) + 1)]

        for j, node in enumerate(nodes):
            # 最初のパターンとマッチするかチェック
            if node["pos"].startswith(patterns[0]):
                # 残りのパターンともマッチするかチェック
                for x, y in zip(nodes[j + 1:], patterns[1:]):
                    if not x["pos"].startswith(y):
                        break
                else:
                    return True
            # "feature" キーの比較は不要なので、削除または修正
            # if len([k for k in ["surface", "reading", "pos"] if node[k] == data[i][k]]) == 3:
            #     break
    return False



def filterWords(data, text):
    words = []

    for i, node in enumerate(data):
        # 名詞でないなら前後の関係も厳密に吟味するワードフィルターにかける
        if node["pos"] != "名詞" and not checkStrict(i, data):
            continue

        # ワードフィルターを通過した単語を追加
        words.append(node["surface"])

    if not words:
        return False

    # 1文字なら破棄し, ハッシュタグの条件を満たす
    return [x for x in words if len(x) > 1]



def choose(words):
    return random.choice(words) + 'はめうのお尻に入らないめう…' if random.randint(1,4) == 1 else '゛'.join(list(max(words, key=len))) + '゛が゛め゛う゛の゛お゛尻゛'+ random.choice(meu)

def post_toot(domain, access_token, params):
    headers = {'Authorization': 'Bearer {}'.format(access_token)}
    url = "https://{}/api/v1/statuses".format(domain)
    response = requests.post(url, headers=headers, json=params)
    if response.status_code != 200:
        raise Exception('リクエストに失敗しました。')
    return response

def get_toot(domain, access_token, params):
    headers = {'Authorization': 'Bearer {}'.format(access_token)}
    url = "https://{}//api/v1/timelines/public".format(domain)
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception('リクエストに失敗しました。')
    return response

def worker():
    t = get_toot(config['mastodon']['domain'], config['mastodon']['access_token'], {'limit': 100})
    #random.shuffle(t)
    t = t.json()
    for tweet in t:
        if tweet["favourited"]:
            continue

        text = normalizeText(tweet["content"])
        if not text:
            continue
        data = getAPI(text, config['yahoo']['access_token'])
        if not data:
            continue
        words = filterWords(data, text)
        if not words:
            continue
        toot = choose(words)
        print(toot)
        print(tweet["id"])
        # mastodon.status_favourite(tweet["id"])
        # mastodon.status_post(toot, in_reply_to_id=None, media_ids=None, sensitive=False, visibility='unlisted', spoiler_text=None)
        post_toot(config['mastodon']['domain'], config['mastodon']['access_token'], {'status': toot, 'visibility': 'unlisted'})
        break

def schedule(f, interval=1200, wait=True):
    base_time = time.time()
    next_time = 0
    while True:
        t = threading.Thread(target=f)
        t.start()
        if wait:
            t.join()
        next_time = ((base_time - time.time()) % interval) or interval
        time.sleep(next_time)

if __name__ == "__main__":
    # 定期実行部分
    schedule(worker)