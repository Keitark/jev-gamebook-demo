# The Decision Library

**Jev × Gamebook** — 古い本をめくりながら、decision model の選択を見届ける実験室。

紙の質感、古い活字、赤茶の装丁、曲がるページ、紙と筆記の音を備えたローカルブラウザUIです。元のPython CLIもそのまま使えます。

> **Navigation edition:** 分岐をたどる実験版です。戦闘・所持品の更新・前提条件の強制・乱数表はまだ実装していません。「ゴール節に到達」と「原作のルールどおりにクリア」は区別してください。

## すぐ開く

Python 3.10以降。リポジトリのフォルダで実行します。

```bash
git pull
python -m pip install -r requirements.txt
python web_app.py --open
```

ブラウザで **http://127.0.0.1:8000** が開きます。`--open`なしで起動して手で開いても構いません。別ポートは `--port 8080`。終了はターミナルで `Ctrl+C` です。

**キーなしでも起動します。** 最初は同梱のオリジナル短編 **The Ashen Gate** と Random コントローラーで、手動選択・ページめくり・音・履歴を試せます。短編も挿絵もこのデモ用のオリジナルで、Project Aonの本文は同梱していません。

## Jev のキーは `.env` に

すでに `.env` がある場合はそのまま使います。未作成の場合だけテンプレートをコピーします。

PowerShell:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

macOS / Linux:

```bash
test -e .env || cp .env.example .env
```

使うプロバイダーの行だけ記入します。

```dotenv
JEV_API_KEY=your_typesafe_key
OPENROUTER_API_KEY=your_openrouter_key
```

サーバーを再起動すると、画面左のコントローラー選択で設定済みのプロバイダーを選べます。既存の環境変数は `.env` より優先されます。必要なら `JEV_MODEL` / `OPENROUTER_MODEL` も指定できます。

**キーはブラウザへ送信しません。** APIへの問い合わせはPython側で行い、UIには設定の有無だけを返します。`.env` はGit除外済みです。キーを本文・profile・GitHubに貼り付けないでください。

## 操作

| 操作 | 動き |
|---|---|
| 本文中の選択肢 | 人が選んで次の節へ。`MANUAL / HUMAN` と記録 |
| 次の一手 / Space | 選択中のコントローラーが1手進める |
| 連続実行 / A | 設定した間隔で繰り返す。再度押すと停止 |
| 1〜9 | 対応する選択肢を手動で選ぶ |
| Escape | 自動実行の停止。設定画面ではダイアログを閉じる |
| 右上の音ボタン | 紙の擦れ・短い筆記音・終了音をON/OFF |
| 右上の設定 | 本、参考profile、seed、間隔、音量、文字サイズ、動きの軽減 |
| 記録を保存 | 実際の遷移・選択確率・応答時間をJSON保存 |

音は初期状態ではOFFです。最初にユーザー操作でONにすると鳴ります。外部音声ファイルやBGMを読み込まず、Web Audioで生成しています。

長い本文や選択肢は**右ページの中をスクロール**できます。狭い画面では1ページ表示になります。本文は静止中もDOMのテキストなので、選択・コピーできます。

自動実行は結末・6回の同一節訪問・200手・通信エラー・タブが非表示になったときに止まります。停止ボタンは**処理中の1手が完了してから**停止し、すでに送ったAPI要求を取り消すものではありません。自動リトライはしません。Jevを選んだ自動実行は、プロバイダー側の課金を伴う場合があります。

## 本とコントローラー

### The Ashen Gate

9節のオリジナル短編。外部ダウンロード不要です。正解経路をコントローラーへ教えるコードは入れていません。Randomは本当に均等抽選で、Jevの推論結果と取り違えないよう表示しています。手動や分岐のない続きには、架空のconfidenceを表示しません。

### Project Aon / Flight from the Dark

設定で本を選び、[Project Aonの利用条件](https://www.projectaon.org/en/Main/License)を確認してから、明示的にダウンロードしてください。既に持っている `01fftd.xml` を `web_app.py` と同じフォルダに置くこともできます。

公式取得先: `https://www.projectaon.org/data/trunk/en/xml/01fftd.xml`

XMLの本文・choiceリンク・deadendを表示します。profileはJevに渡す**固定の参考情報**で、ゲーム内の体力・所持品が自動更新されるわけではありません。絵は原作の挿絵ではなく、このUIの装飾画です。

### Jev / OpenRouter

プロバイダーの `choice / confidence / probabilities` を表示します。確率やconfidenceは冒険のクリア率ではありません。キー未設定やAPIエラーをRandomへ黙って置き換えることはありません。

既存の接続先は次のとおりです。実アクセスは契約・キー・モデルへのアクセス権が必要です。

- TypeSafe: `POST https://api.typesafe.ai/v1/systemone`
- OpenRouter: `POST https://openrouter.ai/api/alpha/decisions`

この実装作業では実キーを使用しておらず、**ライブJev・OpenRouterでの推論は未検証**です。

## ページの描画

WebGL2とCDNが使える場合は、固定バージョン **Three.js 0.180.0** を読み込み、56×12分割メッシュを曲げます。GPUやCDNが使えない場合は、**56本の細片を曲面に沿って動かすCSS 3D版**へ切り替わります。単なる平面の回転ではありません。使用中の描画方式は画面下部に表示します。

ページの表裏には実際のDOM本文から作ったテクスチャを使います。設定の「動きを控えめにする」と狭い画面では短いフェードに切り替えます。待機中に3Dの描画ループを回し続けません。

装飾字体はGoogle Fontsから任意で読み込み、ネットワーク不通時はローカルのセリフ字体へフォールバックします。フォントファイル・Three.js本体をリポジトリには含めていません。**短編・基本UI・音・CSSページめくりは依存Pythonパッケージ導入後なら外部通信なしで動きます。**

## CLI

```bash
python gamebook_jev.py --download --backend random --runs 100 --jsonl random.jsonl
python gamebook_jev.py --download --backend jev --profile-file profile.example.txt --runs 1
python gamebook_jev.py --download --backend openrouter --runs 1
```

CLIもnavigation版です。`--max-steps 0` はコントローラーを一度も呼びません。

## テスト・動画の再生成

```bash
python -m pytest -q
```

ブラウザテストと動画生成は開発用の任意機能です。

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tools/smoke_browser.py
# ffmpegがPATHにある環境で実行
python tools/capture_demo.py
```

`artifacts/` に画面と15秒のMP4を出力します。動画は**実UIのフレームキャプチャ**に、同じWeb Audioシンセサイザーを記録時刻で鳴らした音を付けます。最初の1手はseed付きRandom、残りは手動選択です。Jevが解いた映像ではありません。

この作業環境では管理されたChromiumがlocalhostへのページ遷移とWebGLを制限していたため、`--memory --browser /usr/bin/chromium` で**実HTML/CSS/JS + 実ローカルHTTP APIのブリッジ**を用いてUIを確認しました。ブラウザのポリシーは変更していません。プレビュー映像はCSS 3D版です。通常のHTTPページ遷移、CDNの取得、Three.jsのGPU描画、実Jev呼び出しをこの環境で確認済みとはしていません。詳しくは [TESTING.md](TESTING.md)。

## 構成

```text
web_app.py             localhost専用APIと静的ファイル配信（Python標準ライブラリ）
gamebook_jev.py         既存XMLパーサ・CLI・プロバイダーアダプター
demo_book.py           オリジナル短編
web/index.html         読書画面と設定
web/style.css          装丁・字体・レスポンシブレイアウト
web/page-turn.js        Three.js / CSS 3Dページめくり
web/sound.js            紙・筆記・短い終了音
web/app.js              操作・状態更新・自動実行・ログ
web/engraving.svg       オリジナルの装飾挿絵
tests/                 オフライン自動テスト
tools/                 ブラウザチェックと動画キャプチャ
```

NodeのビルドやFlaskは不要です。サーバーは `127.0.0.1` のみにバインドし、Host/Origin・JSON・トークンを検証します。**公開ホスティング用ではありません。** セッションはメモリー内で、サーバー再起動で消えるため必要な記録はJSON保存してください。

参考: [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html) / [Web Audio](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices) / [TypeSafe API](https://docs.typesafe.ai/api)
