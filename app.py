from flask import Flask, request, render_template_string, jsonify
import subprocess
import re
import json
import execjs
from bs4 import BeautifulSoup

# Flaskアプリのインスタンスを作成
app = Flask(__name__)

# --- HTMLテンプレート ---
HTML_HOME = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ホームページ - pokemoguプロジェクト</title>
    <link rel="apple-touch-icon" sizes="180x180" href="https://kakaomames.github.io/Minecraft-flask-app/static/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="https://kakaomames.github.io/Minecraft-flask-app/static/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="https://kakaomames.github.io/Minecraft-flask-app/static/favicon-16x16.png">
<link rel="manifest" href="https://kakaomames.github.io/Minecraft-flask-app/static/site.webmanifest">
    <link rel="stylesheet" href="https://kakaomames.github.io/Minecraft-flask-app/static/style.css">
</head>
<body>
    <header>
        <h1>HOME🏠</h1>
        <nav>
            <ul>
                <li><a href="/home">ホーム</a></li>
            </ul>
        </nav>
    </header>
    <main>
    </main>
    <footer>
        <p>&copy; 2025  pokemoguプロジェクト</p>
    </footer>
</body>
</html>
"""
HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Downloader</title>
</head>
<body>
    <h1>YouTube Downloader</h1>
    <form method="POST">
        <label for="youtube_url">YouTubeのURL:</label>
        <input type="text" id="youtube_url" name="youtube_url" required>
        <input type="submit" value="送信">
    </form>
    <hr>
    {% if result %}
    <h2>処理結果</h2>
    <pre>{{ result }}</pre>
    {% endif %}
</body>
</html>
"""

# --- ユーティリティ関数 ---
def get_html_with_curl(url):
    try:
        cmd = ['curl', '-sL', url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        return None

def extract_player_js_url(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    js_url_pattern = re.compile(r"(/s/player/.*/base\.js)")
    for script in soup.find_all('script'):
        if 'src' in script.attrs:
            match = js_url_pattern.search(script['src'])
            if match:
                return "https://www.youtube.com" + match.group(1)
    return None

def download_js_code(js_url):
    try:
        cmd = ['curl', '-sL', js_url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        return None

def decipher_signature(ciphered_signature, js_code):
    try:
        ctx = execjs.compile(js_code)
        func_name = 'decipher' # 仮の関数名
        deciphered_sig = ctx.call(func_name, ciphered_signature)
        return deciphered_sig
    except execjs.ProgramError as e:
        print(f"JavaScript実行エラー: {e}")
        return None

def extract_video_id(url):
    pattern = re.compile(
        r"(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    )
    match = pattern.search(url)
    if match:
        return match.group(1)
    return None

# --- APIのロジックを担う内部関数 ---
def get_video_data_internal(video_id):
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    html_content = get_html_with_curl(youtube_url)
    js_url = extract_player_js_url(html_content)
    if not js_url:
        return jsonify({"error": "プレイヤーJavaScriptファイルが見つかりませんでした。"}), 500

    js_code = download_js_code(js_url)
    if not js_code:
        return jsonify({"error": "JSファイルのダウンロードに失敗しました。"}), 500

    try:
        match = re.search(r"var ytInitialPlayerResponse = (\{.*?\});", html_content, re.DOTALL)
        if not match:
            return jsonify({"error": "ytInitialPlayerResponseが見つかりませんでした。"}), 500
        player_response = json.loads(match.group(1))
    except (re.error, json.JSONDecodeError) as e:
        return jsonify({"error": f"JSONデータの解析に失敗しました: {e}"}), 500

    stream_data = {}
    formats = player_response.get('streamingData', {}).get('formats', [])
    adaptive_formats = player_response.get('streamingData', {}).get('adaptiveFormats', [])
    
    for stream in formats + adaptive_formats:
        itag = stream.get('itag')
        if itag:
            stream_info = {"itag": str(itag)}
            if 'url' in stream:
                stream_info["download_url"] = stream['url']
            elif 'cipher' in stream:
                params = {p.split('=', 1)[0]: p.split('=', 1)[1] for p in stream['cipher'].split('&')}
                ciphered_s = params.get('s')
                if ciphered_s:
                    # 署名復号化
                    deciphered_s = decipher_signature(ciphered_s, js_code)
                    if deciphered_s:
                        url_with_sig = f"{params.get('url')}&signature={deciphered_s}"
                        stream_info["download_url"] = url_with_sig
            stream_data[str(itag)] = stream_info

    response_data = {
        "data": {
            "id": video_id,
            "formats": stream_data
        }
    }
    
    return jsonify(response_data)

# --- エンドポイント ---
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template_string(HTML_HOME)
@app.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        youtube_url = request.form.get('youtube_url')
        if not youtube_url:
            return render_template_string(HTML_FORM, result="URLが入力されていません。")

        video_id = extract_video_id(youtube_url)
        if not video_id:
            return render_template_string(HTML_FORM, result="無効なYouTube URLです。")

        data_response = get_video_data_internal(video_id)
        json_data = data_response.get_data(as_text=True)
        
        return render_template_string(HTML_FORM, result=json_data)
    
    return render_template_string(HTML_FORM)

@app.route('/data')
def get_video_data():
    video_id = request.args.get('id')
    if not video_id:
        return jsonify({"error": "動画IDが指定されていません"}), 400
    return get_video_data_internal(video_id)

if __name__ == '__main__':
    app.run(debug=True)
