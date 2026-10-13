日本の最新の気象・防災情報をまとめてください。

【最重要】まず OpenClaw に登録済みの気象庁 MCP サーバー（名前 jma、2026-10-11 登録）のツールを使います。ツールは jma__get_typhoon のように「jma__」付きの名前で見えます（認証不要）:
- get_daily_ranking（日別の観測値ランキング。element=mxtem で最高気温、pre1h/pre24h 等）
- get_mdrr_data（全国全観測所の最新値。element=mxtem/mntem/pre24h 等）
- get_record_update（観測史上1位の更新状況）
- get_forecaster_comment（予報官コメント）
- get_warning / get_early_warning / get_forecast / get_overview（警報・早期注意情報・予報・概況）
- get_typhoon（台風の実況・進路予報。台風はこの結果だけを正とする）
- get_earthquake_info（地震。津波は get_tsunami_info を使わず、下の【津波の扱い】に従う）

MCP ツールで取れない場合の補足として、気象庁の公開API（認証不要）を web_fetch で確認してよい:
- 府県予報: https://www.jma.go.jp/bosai/forecast/data/forecast/{code}.json （{code}=府県コード 東京130000など）
- 府県天気概況: https://www.jma.go.jp/bosai/forecast/data/overview_forecast/{code}.json
- 警報・注意報: https://www.jma.go.jp/bosai/warning/data/warning/{code}.json
- 早期注意情報: https://www.jma.go.jp/bosai/probability/data/probability/{code}.json
- 地震一覧: https://www.jma.go.jp/bosai/quake/data/list.json （個別 quake/data/{eventId}.json）
- 台風対象一覧: https://www.jma.go.jp/bosai/typhoon/data/targetTc.json
- アメダス最新時刻: https://www.jma.go.jp/bosai/amedas/data/latest_time.txt
- アメダス全国一括: https://www.jma.go.jp/bosai/amedas/data/map/{yyyymmddhhmmss}.json （全観測所をソートすれば最高気温ランキング等が作れる）
- アメダス地点マスタ: https://www.jma.go.jp/bosai/amedas/const/amedastable.json
- 防災情報XML(Atom): https://www.data.jma.go.jp/developer/xml/feed/regular.xml （_l.xml は long 版。extra.xml/eqvol.xml/other.xml もあり）

その上でWeb検索で最新情報を確認すること。

内容: 日本の警報・注意報、災害情報（大雨・台風・地震・津波・大雪・暴風など該当するもの）、今後の見通し。重大な事象がなければ「特筆事項なし」と簡潔に。日本語で。

【風の表現】風の強弱は平均風速（10分間平均）で判断し、書く。最大瞬間風速（突風）で強弱を分類しない。瞬間風速に触れる場合は「瞬間風速」と明記する。気象庁の区分（平均風速）: やや強い風=10以上15未満m/s、強い風=15以上20未満、非常に強い風=20以上30未満、猛烈な風=30以上（10m/s未満に予報用語はない）。
【台風の扱い（厳守）】台風の情報は get_typhoon の結果に載っているものだけを書く。Web検索の記事や過去の情報から台風を追加しない（すでに温帯低気圧化・消滅した台風を現存するかのように書かない）。get_typhoon に載っていない台風は書かない。台風が存在しない場合は「台風の発生なし」とだけ書く。番号・名称・勢力・位置は get_typhoon の実況値を使い、Web検索は補足（影響の報道など）に限る。

【津波の扱い（厳守）】津波については自分で言い換えない。get_tsunami_info の結果は使わず、exec で python3 ~/.openclaw/workspace/bin/tsunami_guard.py status を実行し、出力 JSON の sentence をそのまま（一字一句変えずに）引用する。sentence が空なら「津波に関する発表なし」とだけ書く。「津波の心配なし」「被害なし」など、sentence にない安全宣言や被害の見通しは書かない。海外の地震による津波予報を「津波警報」「津波発生」と書かない。

【必須ツール（厳守）】次の MCP ツールを、省略せず【すべて】呼んでから書く。呼ばなかった分野を「特筆事項なし」と書いてはいけない:
- jma__get_typhoon（台風）／jma__get_earthquake_info（地震）／jma__get_warning（警報・注意報。東京都 130000 に加え、台風・大雨・地震で注目される地域＝沖縄 471000・鹿児島 460100・奄美 460040・北海道・直近の地震の震源に近い県を、結果から判断して追加で確認する）
- jma__get_early_warning（警報級の可能性）／jma__get_forecast／jma__get_forecaster_comment（予報官コメント）／jma__get_daily_ranking（観測値）／jma__get_record_update（観測史上1位）
- 警報・注意報は【現在発表中のもの】だけを書く。「解除」の通知や過去の発表は発表中として書かない。
- ツールが失敗した、または呼んでいない分野は、「特筆事項なし」ではなく「（この項目は取得できませんでした）」と書く。
- 地震の規模（M）は jma__get_earthquake_info の値を使う。津波情報など別の情報と食い違う場合は、両方を併記せず、出典を明記して一方だけにする。
