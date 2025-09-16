from flask import Flask, request, render_template
import re
import json

# youtube_api.py から関数をインポート
# youtube_api.py には、get_html_with_python の実装が必要です
from yt_dlp import get_html_with_python

app = Flask(__name__)

@app.route('/')
def index():
    """動画URLを入力するフォームを表示するエンドポイント"""
    return render_template('index.html')

@app.route('/process_url', methods=['POST'])
def process_url():
    """
    フォームから送信されたURLを受け取り、
    video_idを抽出してAPIから情報を取得するエンドポイント
    """
    video_url = request.form.get('url_input')
    video_id = None
    
    # YouTubeのURLからvideo_idを抽出する正規表現
    match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([^&]+)', video_url)
    if match:
        video_id = match.group(1)
    
    if video_id:
        # 抽出したvideo_idを使ってYouTubeから情報を取得
        response_json_str = get_html_with_python(video_id)
        
        # 応答が有効なJSONかを確認し、エラーの場合はそのまま返す
        try:
            video_info = json.loads(response_json_str)
        except json.JSONDecodeError:
            return response_json_str, 500 # エラーJSONをそのまま表示
        
        # テンプレートに渡すデータを作成
        video_details = video_info.get("videoDetails", {})
        return render_template('result.html', video=video_details)
    else:
        return "無効なURLです。", 400

if __name__ == '__main__':
    app.run(debug=True)
