# FitHero Setup Guide
## 環境構築

1. **リポジトリのクローン**
    ```bash
    git clone https://github.com/kanonnon/FitHero
    cd FitHero
    ```

2. **Python仮想環境の作成と有効化**
    ```bash
    pyenv virtualenv 3.8.10 fithero
    pyenv local fithero
    ```

4. **ライブラリのインストール**
    ```bash
    pip install -r requirements.txt
    ```

5. **staticディレクトリの作成**
    ```bash
    mkdir static
    ```

6. **.envファイルの配置**
   - `.env`ファイルをKanonから受け取り、プロジェクトのルートディレクトリに配置

  
7. **動作確認** 
    ```bash
    python app.py
    ```
   - http://127.0.0.1:5000 にアクセスして"hello world!"と表示されればOK

## ngrokの導入

1. **ユーザ登録**
   - [ngrok公式サイト](https://dashboard.ngrok.com/user/signup)でユーザ登録する
  
2. **セットアップ**
   - [セットアップのページ](https://dashboard.ngrok.com/get-started/setup/macos)に従って以下を実行
    ```bash
    brew install ngrok/ngrok/ngrok
    ```
   - 出力されたリンクを押してzipファイルをダウンロード後解凍
    ```bash
    ngrok config add-authtoken [自分のトークン]
    ```

3. **動作確認**
    ```bash
    python app.py
    ngrok http 5000
    ```
   - 出力されたリンクを押して"hello world!"と表示されればOK
   - URLを控えておく
  
4. **LINEの動作確認**
   - [LINE DevelopersのMessaging APIの設定画面](https://developers.line.biz/console/channel/2005676928/messaging-api)にアクセス
   - Webhook URLの設定について、先ほど控えたURLを貼る
     - URLの後に```/callback```をつけることに注意
   - LINEを追加して画像を送ってみる
   - 返信が来ればOK
    
