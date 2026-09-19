# The Decision Library

**Jev × Gamebook** — 古い本をめくりながら、decision model の選択を見届ける実験室。

紙の質感、古い活字、赤茶の装丁、曲がるページ、紙と筆記の音を備えたローカルブラウザUIです。元のPython CLIもそのまま使えます。

> **v0.3 — 日本語RPG版:** オリジナル作品『灰鐘の港と、名前のない朝』に、戦闘・所持品・装備・手がかり・所持金・条件付き選択肢を実装しました。**Project Aon版は従来の分岐探索版のまま**です。原作Lone Wolfの戦闘ルールを実装したものではありません。

## すぐ開く

Python 3.10以降。リポジトリのフォルダで実行します。

```bash
git pull
python -m pip install -r requirements.txt
python web_app.py --open
```

ブラウザで **http://127.0.0.1:8000** が開きます。`--open`なしで起動して手で開いても構いません。別ポートは `--port 8080`。終了はターミナルで `Ctrl+C` です。

**キーなしでも起動します。** 初回は日本語のオリジナル作品 **『灰鐘の港と、名前のない朝』** と Random コントローラーを開きます。以前の本が選ばれたままの場合は、設定の本棚から切り替えてください。短編も挿絵もこのデモ用のオリジナルで、Project Aonの本文は同梱していません。

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
| 本文中の選択肢 | 人が選んで進む。戦闘中は攻撃・防御・薬などを選択。`MANUAL / HUMAN` と記録 |
| 荷物・装備 | 数量・効果を確認し、道具を使う／装備する |
| 手がかり / ? | 実際に得た情報・協力者／戦闘ルールを確認 |
| 次の一手 / Space | 選択中のコントローラーが1手進める |
| 連続実行 / A | 設定した間隔で繰り返す。再度押すと停止 |
| 1〜9 | 対応する選択肢を手動で選ぶ |
| Escape | 自動実行の停止。設定画面ではダイアログを閉じる |
| 右上の音ボタン | 紙・筆記・剣戟・防御・回復・ダイス・終了音をON/OFF |
| 右上の設定 | 本、参考profile、seed、間隔、音量、文字サイズ、動きの軽減 |
| 記録を保存 | 遷移・選択確率・ダイス・戦闘結果・状態変化をJSON保存 |

音は初期状態ではOFFです。最初にユーザー操作でONにすると鳴ります。外部音声ファイルやBGMを読み込まず、Web Audioで生成しています。

長い本文や選択肢は**右ページの中をスクロール**できます。狭い画面では1ページ表示になります。本文は静止中もDOMのテキストなので、選択・コピーできます。

自動実行は結末・200手・通信エラー・タブが非表示になったときに止まります。旧navigation版には6回の同一節訪問の停止条件もあります。RPGの戦闘ラウンドをループと誤判定しません。停止ボタンは**処理中の1手が完了してから**停止し、すでに送ったAPI要求を取り消すものではありません。自動リトライはしません。Jevを選んだ自動実行は、プロバイダー側の課金を伴う場合があります。

## 本とコントローラー

### 灰鐘の港と、名前のない朝

**日本語オリジナル・60節・8種類の敵・17種類の道具・9つの手がかり・7つの結末。** 既存作品の翻訳ではありません。

> 七年前に消えた妹から手紙が届いた。「最後の鐘が鳴る前に、私の名前を取りに来て」。人の名前を代価に海を押し留める港で、あなたは修復した覚えのある帳簿と、誰も覚えていない帰船記録を見つける。

港での救助、交易、記録院の調査、揚水場の操作、礼拝堂の調律、灯台の対話と戦いを組み合わせる短編です。情報や協力者は終盤の敵の数値・選べる解決法・結末の本文に反映されます。すべての戦闘を通る必要はありません。船綱、食料、清め布には探索と戦闘をまたぐ用途があります。

**戦闘:** 体力、集中、技量、敏捷、武器、装甲をサーバー側で管理。敵の予備動作を見て、通常攻撃／必中の精密攻撃／防御／回復／道具／撤退を選びます。薬を飲む手にも敵は動きます。倒した敵は反撃せず、戦利品は一度きりです。

**探索:** 銀貨の支払い、消耗品消費、装備変更、手がかりの取得、条件付き選択肢、d6の成功判定、潮位による時間切れが実際に働きます。潮位は移動ごと一律ではなく、明示された選択や危険で増減します。ルールの詳細は [RPG_RULES.md](RPG_RULES.md)。

**Jev:** 同じAPIで探索と戦闘を選択します。渡すのは現在の本文、実際の所持品・状態、取得済みの手がかり、直近の結果、現在可能な行動だけです。全シナリオ、未読の節、隠しフラグ、正解経路、乱数の内部状態は渡しません。参考profileに「体力999」と書いても実際の状態は変わりません。

ゲーム終了後に荷物や手がかりを読むことはできますが、道具使用などの状態変更は止まります。保存ボタンのJSONは **実行記録** であり、再開用セーブデータではありません。

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

日本語は「しっぽり明朝」、英語の装飾字体とともにGoogle Fontsから任意で読み込み、ネットワーク不通時はローカルのセリフ字体へフォールバックします。フォントファイル・Three.js本体をリポジトリには含めていません。**短編・基本UI・音・CSSページめくりは依存Pythonパッケージ導入後なら外部通信なしで動きます。**

## 日本語シナリオをテキスト／JSONで取り出す

```bash
python story_ja.py --output story-export
```

`ashbell-ja.json`（条件・戦闘データも含む機械可読版）と `灰鐘の港と名前のない朝.md`（節リンク付き原稿）を生成します。**全分岐・結末のネタバレを含みます。** 作者向けのルール定義は [RPG_RULES.md](RPG_RULES.md)。テキストだけ別の本へ差し替える場合も、条件を数値・IDで定義してエンジンに任せる方式です。

## 日本語RPGを自動評価する

```bash
python run_rpg.py --backend random --runs 20 --seed 17 --jsonl rpg-random.jsonl
python run_rpg.py --backend jev --runs 1 --jsonl rpg-jev.jsonl
python run_rpg.py --backend openrouter --runs 1 --jsonl rpg-openrouter.jsonl
```

ブラウザと同じルール・状態管理を使います。実行記録v2にはシナリオバージョンとSHA-256、seed、選択肢、選択結果、ダイス、前後の状態、結末IDを残します。モデルの推論自体の再現性をseedで保証するものではありません。

## 旧Project Aon CLI

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
python tools/rpg_browser.py
python tools/smoke_browser.py  # 旧英語デモの回帰確認
python tools/rpg_scenarios.py # 正解経路を与えた到達可能性の回帰確認
# ffmpegがPATHにある環境で実行
python tools/capture_rpg.py   # 日本語の戦闘・回復・勝利
python tools/capture_demo.py  # 旧英語デモ
```

`artifacts/` に画面とMP4を出力します。日本語戦闘動画は16秒・手動入力、旧英語動画は15秒・Random＋手動入力です。動画は**実UIのフレームキャプチャ**に、同じWeb Audioシンセサイザーを記録時刻で鳴らした音を付けます。Jevが解いた映像ではありません。

この作業環境では管理されたChromiumがlocalhostへのページ遷移とWebGLを制限していたため、`--memory --browser /usr/bin/chromium` で**実HTML/CSS/JS + 実ローカルHTTP APIのブリッジ**を用いてUIを確認しました。ブラウザのポリシーは変更していません。プレビュー映像はCSS 3D版です。通常のHTTPページ遷移、CDNの取得、Three.jsのGPU描画、実Jev呼び出しをこの環境で確認済みとはしていません。詳しくは [TESTING.md](TESTING.md)。

## 構成

```text
web_app.py             localhost専用APIと静的ファイル配信（Python標準ライブラリ）
gamebook_jev.py         既存XMLパーサ・CLI・プロバイダーアダプター
rpg_engine.py          戦闘・所持品・条件・seed付きd6・トランザクション
story_ja.py            日本語60節の正本・JSON/Markdown出力
run_rpg.py             ブラウザと同じエンジンの自動評価CLI
demo_book.py           旧英語オリジナル短編
web/index.html         読書画面と設定
web/style.css          装丁・字体・レスポンシブレイアウト
web/rpg.css            日本語活字・体力と荷物・戦闘の表示
web/page-turn.js        Three.js / CSS 3Dページめくり
web/sound.js            紙・筆記・短い終了音
web/app.js              操作・状態更新・自動実行・ログ
web/rpg-ui.js           体力・敵・戦闘ログ・荷物・手がかり・ルール
web/engraving.svg       オリジナルの装飾挿絵
tests/                 オフライン自動テスト
tools/                 ブラウザチェックと動画キャプチャ
```

NodeのビルドやFlaskは不要です。サーバーは `127.0.0.1` のみにバインドし、Host/Origin・JSON・トークンを検証します。**公開ホスティング用ではありません。** セッションはメモリー内で、サーバー再起動で消えるため必要な記録はJSON保存してください。

参考: [Three.js WebGLRenderer](https://threejs.org/docs/pages/WebGLRenderer.html) / [Web Audio](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API/Best_practices) / [TypeSafe API](https://docs.typesafe.ai/api)
