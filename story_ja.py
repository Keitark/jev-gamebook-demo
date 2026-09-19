"""Original Japanese gamebook: 灰鐘の港と、名前のない朝.

Canonical, editable story source; no borrowed gamebook text. Run this module
to export portable JSON plus a human-readable, linked Markdown edition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rpg_engine import RPGBook

TITLE = '灰鐘の港と、名前のない朝'
OBJECTIVE = '最後の灰鐘が鳴る前に煤汐の港を救い、奪われた名前を取り戻す。可能なら誰も新しい犠牲にしない。'


def F(name): return {'flag': name}
def I(name): return {'item': name}
def K(name): return {'clue': name}
def A(*parts): return {'all': list(parts)}
def O(*parts): return {'any': list(parts)}


def build_spec():
    s = {
        'format': 'decision-gamebook/v1', 'id': 'ashbell', 'version': '1.0.0',
        'title': TITLE, 'language': 'ja', 'objective': OBJECTIVE,
        'start': '1', 'death': '56', 'deadline': '55', 'tide_limit': 16,
        'author_note': 'オリジナル作品。既存作品の翻訳ではありません。',
        'initial': {'inventory': {'sword': 1, 'coat': 1, 'tonic': 2, 'ration': 2, 'bandage': 1, 'saltbomb': 1},
                    'equipment': {'weapon': 'sword', 'armor': 'coat'}},
        'items': {}, 'clues': {}, 'enemies': {}, 'sections': {},
    }
    def item(key, name, kind, description, **stats):
        s['items'][key] = {'name': name, 'kind': kind, 'description': description, **stats}
    item('sword', '欠けた短剣', 'weapon', '父の製本刀を打ち直した刃。威力2、命中補正0。', power=2, accuracy=0)
    item('hammer', '歯車工の槌', 'weapon', '短い柄に鉛の芯。威力3、命中補正0。装備は戦闘外のみ。', power=3, accuracy=0)
    item('silverblade', '月銀の細剣', 'weapon', '古い鐘の合金で鍛えた刃。威力4、命中＋1。', power=4, accuracy=1)
    item('coat', '旅人の外套', 'armor', '濡れた革の防具。被ダメージを1軽減。', armor=1)
    item('oilcoat', '油布の防護服', 'armor', '厚い帆布と革の二重縫い。被ダメージを2軽減。', armor=2)
    item('guardcoat', '鐘守の補強服', 'armor', '胸に薄い金属板を縫い込んだ服。被ダメージを3軽減。', armor=3)
    item('tonic', '琥珀の回復薬', 'heal', '体力10回復。戦闘中に使うと敵の手番も進む。', heal=10, combat=True)
    item('bandage', '清め布', 'heal', '体力6回復。鏡の煤を拭う用途にも使える。', heal=6, combat=True)
    item('ration', '黒麦の携帯食', 'heal', '戦闘外で体力6、集中1回復。生き物の囮にも。', heal=6, focus=1, combat=False)
    item('saltbomb', '鳴塩の小瓶', 'bomb', '敵に固定8ダメージ。装甲を無視する。', damage=8)
    item('smoke', '煙玉', 'smoke', '退路のある戦闘から確実に逃げる。戦利品は得られない。')
    item('seal', '銅の通行印', 'quest', '税関の裏口で使う。持っているだけでは道は開かない。')
    item('rope', '青い船綱', 'quest', '船の修理か、崩れた足場の横断に使える。使用すると失う。')
    item('ledger', '消された帰船簿', 'quest', '消された人々の名前と、鐘の契約の原本。売らずに持ち帰りたい。')
    item('lens', '潮見のレンズ', 'quest', '鐘の音の流れが細い光として見える。失われた装置の焦点。')
    item('bellshard', '灰鐘の欠片', 'quest', '小さな鐘であり、共鳴を壊す楔でもある。')
    item('letter', '凪の書き置き', 'quest', '妹の筆跡。救われることと、戻されることは同じではない。')
    def clue(key, title, body):
        s['clues'][key] = {'title': title, 'text': body}
    clue('water', '水門の順序', '海輪を先に閉め、街輪を後に開く。逆順は水圧を街へ向ける。揚水成功で潮位が3下がる。')
    clue('gears', '整備屋の合図', '揚水場の番兵は工具を三度鳴らすと整備姿勢になる。灯を助けていれば戦わず通れる。')
    clue('contract', '鐘の契約', '灰鐘は海を退ける代わりに人の名前を徴収する。帰船簿は徴収の台帳であり、契約の原本でもある。')
    clue('score', '返し歌', '鐘を黙らせるのでなく、返し歌で声を分ける。原本、焦点となるレンズ、街の排水、調律の助手が必要だ。')
    clue('sister', '凪が残した意思', '凪は海に消えた人々の名前を守るため、自分の名を差し出した。「私一人を取り出さず、みんなを岸へ」。')
    clue('keeper', '鐘守の名前', '鐘守の本名は榛。彼も契約の犠牲者で、最初に忘れたのは自分の子の名だった。')
    clue('mirror', '焦点の役割', '潮見のレンズは眠る人を映すのではない。海へ流れる声を街中に分け直す。返し歌の儀式で必要。')
    clue('bell', 'ひびの読み方', '灰鐘の欠片を主鐘のひびへ打ち込めば鐘は砕ける。街は解放されるが、未回収の名前も失われる。')
    clue('warning', '街の排水', '鐘を止める前に揚水場を動かさないと、押し留めていた海が戻る。舟だけでは街を救えない。')
    def enemy(key, name, hp, skill, guard, armor, power, pattern, loot):
        s['enemies'][key] = dict(name=name, hp=hp, skill=skill, guard=guard, armor=armor, power=power, pattern=pattern, loot=loot)
    enemy('hound', '針金の猟犬', 13, 3, 7, 0, 1, ['charge', 'heavy', 'recover', 'attack'], {'gold': 2})
    enemy('eel', '塩喰いの大鰻', 17, 4, 7, 0, 1, ['attack', 'charge', 'heavy', 'recover'], {'gold': 2})
    enemy('paper', '紙守の鎧', 18, 4, 8, 1, 1, ['guard', 'attack', 'charge', 'heavy'], {'gold': 3})
    enemy('pump', '揚水場の番兵', 23, 4, 8, 2, 2, ['guard', 'charge', 'heavy', 'recover'], {'gold': 4})
    enemy('echo', '鐘打ちの残響', 20, 4, 8, 1, 1, ['attack', 'recover', 'charge', 'heavy'], {'focus': 2})
    enemy('drowned', '落水の門番', 18, 4, 7, 1, 1, ['attack', 'charge', 'heavy', 'recover'], {'gold': 2})
    enemy('keeper', '鐘守・榛', 28, 5, 8, 1, 2, ['guard', 'charge', 'heavy', 'recover', 'attack'], {'items': {'bellshard': 1}, 'flags': ['keeper_defeated']})
    enemy('nameless', '名前のない潮', 32, 5, 9, 2, 2, ['charge', 'heavy', 'attack', 'recover'], {'flags': ['tide_defeated']})
    def C(key, text, to, *, requires=None, effects=None, once=False, locked=None, test=None, hidden=False):
        c = {'id': key, 'text': text, 'to': str(to)}
        if requires: c['requires'] = requires
        if effects: c['effects'] = effects
        if once: c['once'] = True
        if locked: c['locked'] = locked
        if test: c['test'] = test
        if hidden: c['hidden'] = True
        return c
    def N(number, title, text, choices=(), *, enter=None, combat=None, ending=None):
        node = {'title': title, 'text': text.split('\n\n'), 'choices': list(choices)}
        if enter: node['enter'] = enter
        if combat: node['combat'] = combat
        if ending: node['ending'] = ending
        s['sections'][str(number)] = node
    def fight(enemy, win, flee=None, modifiers=()):
        return {'enemy': enemy, 'win': str(win), 'flee': str(flee) if flee else None, 'modifiers': list(modifiers)}
    def end(tag, status, label): return {'id': tag, 'status': status, 'label': label}

    N(1, '封蝋のない手紙',
      '妹が死んでから七年目の朝、妹の筆跡で手紙が届いた。\n\n「夕方の鐘が鳴る前に、煤汐へ。私の名前を、まだ覚えているなら」\n\nあなたは名簿を修復する名綴り師だ。妹の名は凪。その二文字だけが、戸籍からも墓石からも消えている。鞄に製本刀を打ち直した短剣と薬を詰め、干潟の先に浮かぶ港へ向かった。',
      [C('gate', '干潟を渡り、煤汐の門へ', 2)])
    N(2, '名前を預かる門',
      '門番は通行料でなく、あなたの姓を尋ねた。答えかけると、背後の老婆が袖を引く。「ここでは名前を安く渡すものじゃない」\n\n門の上に、煤色の鐘が見える。街を取り巻く海面は門より高いのに、水は見えない壁に押し留められていた。十六目盛の潮位計が、ゆっくりと上がっている。',
      [C('harbor', '名を伏せたまま港へ入る', 3, effects={'tide': 1}), C('leave', '不吉な手紙を海へ返し、引き返す', 57)])
    N(3, '声の薄い波止場',
      '魚売りの呼び声は聞こえるのに、誰も客の名を呼ばない。看板には店の種類だけが書かれ、人の名前のあった場所は長い空白になっている。\n\n路地の奥で、金属を引きずる音と子どもの叫びが重なった。市にはまだ明かりがある。波止場では船大工が、半ば沈んだ舟を一人で引いている。税関の先が旧記録院だ。',
      [C('alley', '路地の叫びを確かめる', 4), C('market', '糸雨の市で旅支度を整える', 7), C('doctor', '薬屋を訪ねる', 10), C('boat', '船大工に話を聞く', 11), C('archive', '税関を抜けて記録院へ', 16, effects={'tide': 1})])
    N(4, '逆さの路地',
      '水たまりに空ではなく街の底が映っている。工具袋を抱えた少女が、行き止まりで針金の猟犬に追い詰められていた。犬の腹には徴名局の封印がある。\n\n「盗んだんじゃない。修理代を払ってくれないから、道具を返してもらっただけ！」\n\n犬は一度身を沈め、それから大きく跳ぶ。動きは激しいが、予備動作は読めそうだ。',
      [C('save', '少女を背にかばい、猟犬を引き受ける', 5, effects={'tide': 1}), C('back', 'ここで消耗するわけにはいかない。港へ戻る', 3)])
    N(5, '針金の歯',
      '犬の歯は一本の針金を何度も折り返したものだった。街の誰かが、歯でなく道具を作ろうとした名残にも見える。\n\n少女が低く叫ぶ。「跳ぶ前に腰が落ちる。そのときだけは、ちゃんと見て！」大振りに備えるか、溜めている間に攻めるか。判断するのはあなただ。',
      combat=fight('hound', 6, 3))
    N(6, '灯の工具袋',
      '犬は短いばねの音を立てて動かなくなった。少女はあなたの手を両手で握る。「灯。あかり、っていう。まだ取られてない名前」\n\n灯は揚水場の合図を工具の柄で教えた。三度、間を置いて一度。別れる前に、彼女は空を指す。「灯台まで行くなら、あとで追いつく。あそこの鐘、ひとりでは直せないから」',
      [C('return', '灯を安全な通りへ送り、波止場へ戻る', 3)],
      enter={'flags': ['helped_child'], 'clues': ['gears'], 'items': {'tonic': 1}})
    N(7, '糸雨の市',
      '天幕から落ちる雨は糸のように細い。商人たちは釣銭を盆に落とし、決して客の掌に触れない。\n\n油布の服にはまだ海の匂いがする。細い銀の剣は、鐘の破片から鍛えたという。「よく切れるよ。何を切ったか忘れたくなるほどには」店主は値札を指した。買った装備は、荷物欄から身につける必要がある。',
      [C('coat', '油布の防護服を買う／銀貨6', 7, effects={'gold': -6, 'items': {'oilcoat': 1}}, once=True, locked='銀貨6が必要。'),
       C('blade', '月銀の細剣を買う／銀貨8', 7, effects={'gold': -8, 'items': {'silverblade': 1}}, once=True, locked='銀貨8が必要。'),
       C('bomb', '鳴塩の小瓶を買う／銀貨3', 7, effects={'gold': -3, 'items': {'saltbomb': 1}}, locked='銀貨3が必要。'),
       C('smoke', '煙玉を買う／銀貨2', 7, effects={'gold': -2, 'items': {'smoke': 1}}, locked='銀貨2が必要。'),
       C('rumor', '片眼の行商に、記録院の裏口を尋ねる', 8), C('back', '波止場へ戻る', 3)])
    N(8, '空欄の値段',
      '行商は通行印を示す。印面に名前はなく、わざと削った銅の傷だけがある。\n\n「何も書いていない印なら、誰のものでもある。三枚でいい。記録院で探すなら、生まれた人の帳簿より、帰らなかった船の帳簿を見な」\n\n値引きの余地はなさそうだが、買わずに去ることはできる。',
      [C('buy', '銅の通行印を買う／銀貨3', 9, effects={'gold': -3}, once=True, locked='銀貨3が必要。'), C('back', '市へ戻る', 7)])
    N(9, '誰でもない者の印',
      '冷たい銅を握ると、あなたの名を呼ぼうとした門番の声が遠のいた。行商は包み紙に揚水場の注意書きを写してくれた。\n\n「海を閉めてから、街を開ける。順番を違えると港が裏返る。覚えておきな」名もない助言だけが、正規の通行証より頼もしく感じられた。',
      [C('back', '通行印をしまい、市へ戻る', 7)], enter={'items': {'seal': 1}, 'clues': ['water']})
    N(10, '薬屋の帳場',
      '薬師の机には、名前のない処方箋が山になっている。「忘れたことが痛む、という患者ばかりさ。痛む場所がないから治しにくい」\n\nあなたの傷なら、まだ手当てのしようがあるという。椅子に腰かければ時間も進む。瓶を買い、危ないところまで持っていく手もある。',
      [C('rest', '手当てを受ける／銀貨3、体力12回復・一度限り', 10, effects={'gold': -3, 'hp': 12, 'tide': 1}, once=True, locked='銀貨3が必要。'),
       C('tonic', '回復薬を買う／銀貨3', 10, effects={'gold': -3, 'items': {'tonic': 1}}, locked='銀貨3が必要。'),
       C('cloth', '清め布を買う／銀貨1', 10, effects={'gold': -1, 'items': {'bandage': 1}}, locked='銀貨1が必要。'),
       C('back', '波止場へ戻る', 3)])
    N(11, '舟を離さない男',
      '船大工の槙は、腰まで水に浸かって舟を支えていた。「娘を乗せた舟と同じ型だ。あの子の名は思い出せない。舟の形なら覚えている」\n\n丈夫な青い綱が、奥の倉庫に残っているという。取ってくれば舟を直せる。槙は見返りの代わりに水門の順序を教えた。「海輪を閉めて、それから街輪だ。鐘を止めるなら、なおさらな」',
      [C('warehouse', '倉庫で青い綱を探す', 12, effects={'tide': 1}),
       C('repair', '青い綱を渡して舟を直す', 15, requires=I('rope'), effects={'items': {'rope': -1}}, once=True, locked='青い船綱が必要。'),
       C('back', '波止場へ戻る', 3)], enter={'clues': ['water', 'warning']})
    N(12, '水を噛む倉庫',
      '割れた床板の向こうに、青い綱が巻かれている。その真下で白い大鰻がゆっくりと身をねじった。鰻は綱でなく、綱に染みた塩を舐めている。\n\n足場は狭い。戦ってどかすことも、携帯食の塩気で水路へ誘い出すこともできそうだ。',
      [C('lure', '携帯食を一つ使い、鰻を水路へ誘う', 14, requires=I('ration'), effects={'items': {'ration': -1}}, locked='黒麦の携帯食が必要。'),
       C('fight', '大鰻を倒して綱を取る', 13), C('back', '槙のもとへ引き返す', 11)])
    N(13, '塩喰い',
      '大鰻の背が床板を持ち上げた。口の奥には、人が落とした銅貨が歯のように並んでいる。\n\n水を吸い込むときは動きが止まる。その後の突進をまともに受けるのは危険だ。', combat=fight('eel', 14, 11))
    N(14, '青い船綱',
      '綱はまだ乾いた芯を残していた。脇の道具箱には銀貨と小さな薬瓶がある。持ち主の名札は白紙だ。\n\nこの綱は槙の舟にも、自分の足場にも使える。ひとつの道具が二つの用途を持つとき、選ばなかった方にも行き先が残る。',
      [C('maki', '槙のもとへ綱を持ち帰る', 11), C('keep', '綱を自分の旅に残し、波止場へ', 3)],
      enter={'items': {'rope': 1, 'tonic': 1}, 'gold': 4})
    N(15, '舟板の誓い',
      '槙は綱を渡されても、すぐには礼を言わなかった。舟が岸から離れるのを見届けてから、ようやく深く息をついた。\n\n「防潮堤まで来れば乗せよう。料金はいらない。あんたが誰かにしたことを、海だけが知っているのは惜しい」\n\n灯台へ続く水路が、ひとつあなたの味方になった。',
      [C('back', '波止場へ戻る', 3)], enter={'flags': ['helped_maki']})
    N(16, '徴名局の税関',
      '役人は机に並べた印を数え続けている。あなたには目を向けない。奥が記録院、右手が防潮堤へ抜ける道だ。\n\n「記録院は紹介か印が必要。堤へ出るだけなら、雑費三枚」\n\n灯台へ急ぐなら帳簿を探さず進める。しかし妹の手紙には、鐘を壊せとは一度も書かれていなかった。',
      [C('reading', '記録院への通用門を調べる', 17),
       C('bribe', '銀貨3を払い、防潮堤へ抜ける', 25, effects={'gold': -3}, locked='銀貨3が必要。'), C('back', '波止場へ戻る', 3)])
    N(17, '無署名の閲覧票',
      '通用門には複雑な鍵と、銅の印を押す窪みがある。扉の向こうでは、誰かが紙を繰る音がする。\n\n助けた少女なら、この鍵を開けられるかもしれない。印も助手もなければ、自分の道具で挑戦するしかない。失敗すれば見張りが来るだろう。',
      [C('seal', '銅の通行印を示して入る', 18, requires=I('seal'), locked='銅の通行印が必要。'),
       C('child', '灯の教えた工具の使い方で開錠する', 18, requires=F('helped_child'), locked='灯を助けて道具の使い方を教わっていない。'),
       C('pick', '製本道具で開錠を試みる', 18, effects={'tide': 1}, test={'stat': 'skill', 'dc': 8, 'success': '18', 'failure': '19'}), C('back', '税関へ戻る', 16)])
    N(18, '誰も借りない記録院',
      '書架は天井まで続いているのに、閲覧席は一脚しかない。窓辺の司書が、あなたの手紙を見ただけで立ち上がった。\n\n「その字を、知っているわ。消す側にいたから」\n\n司書は砂緒と名乗った。名前を奪う街で本名を差し出す、その無謀さがかえって信用できた。', [C('sao', '砂緒の話を聞く', 20)])
    N(19, '紙守の鎧',
      '鍵が鳴ると、書架の陰から鎧が歩いてきた。金属の代わりに、何千枚もの帳簿が幾重にも重なっている。\n\n剣を受ければ表紙を固めるが、綴じ目は細い。集中を使った精密攻撃なら、分厚い紙を貫けるはずだ。', combat=fight('paper', 18, 16))
    N(20, '消した者の証言',
      '「鐘は街を守っている。でも、海を消しているのではない。海の負債を、人の名前で払い続けているの」\n\n砂緒は凪の名を紙に書こうとした。ペン先が途中で止まる。「七年前、妹さんは徴収に反対した。最後には自分で署名した。何を守ったのか、私は確かめなかった」\n\n帰らなかった船の帳簿が、地下にあるという。',
      [C('ledger', '地下の帰船簿を探す', 21, effects={'tide': 1}), C('score', '鐘を戻す方法だけでも聞く', 23, effects={'tide': 1}), C('outside', '話を覚え、防潮堤へ急ぐ', 25, effects={'tide': 1})], enter={'clues': ['contract']})
    N(21, '帰らなかった船',
      '帰船簿に記されていたのは、遭難した船ではなかった。岸へ戻ったのに、荷役の途中で名前を取られ、家へ帰れなくなった人々だ。\n\n最後の頁の欄外に、あなたの修復した綴じ跡がある。七年前、理由も尋ねず妹の頼みで直した帳簿だった。\n\n凪はこの帳簿を海の側へ持っていかなかった。誰かが読める場所に残した。', [C('take', '最後の頁を開く', 22)], enter={'hp': 4})
    N(22, '原本と釣銭',
      '欄外には契約の条項が綴じ込まれている。街を救うための契約は、街に拒否する権利がないよう書き換えられていた。これが原本だ。\n\n砂緒は帳簿を抱えるあなたに、逃走資金の銀貨八枚を差し出す。「原本を預けてくれれば保管する。でも、鐘に突きつけるなら自分で運んで」\n\n両方は持てない。砂緒にも逃げる金が必要なのだ。',
      [C('keep', '銀貨を断り、原本を持っていく', 23, effects={'items': {'ledger': 1}, 'focus': 1}, once=True),
       C('money', '砂緒に原本を預け、銀貨8を受け取る', 23, effects={'gold': 8, 'flags': ['left_ledger']}, once=True)], enter={'flags': ['read_ledger']})
    N(23, '返し歌',
      '砂緒は歌う代わりに、机を四拍、指で叩いた。最後の一拍だけが、窓から届く鐘の音と逆に響く。\n\n「ひとりの名で海を押し返すから、ひとりずつ失う。原本を解き、レンズで声を分け、街の水を逃がす。それから二人で調律するの。ひとりが歌い、ひとりが拍を外す」\n\n楽譜の余白には、灯台から届いたまま開かれていない手紙が挟まっていた。',
      [C('letter', '凪の書き置きを読む', 24), C('go', '返し歌を覚え、防潮堤へ', 25, effects={'tide': 1})], enter={'clues': ['score', 'warning']})
    N(24, '戻してはいけない人',
      '「あなたなら、きっと迎えに来てしまうと思うから、これだけは書いておきます。私は閉じ込められたのではありません。岸で呼ばれなくなった人たちを、一人にしないために残りました」\n\n「私だけを元に戻さないで。全員を岸へ渡す方法を、探してください」\n\n筆圧の強い最後の一行に、よく知る意地が残っている。救出だと思っていた旅が、約束の引き継ぎに変わった。',
      [C('go', '書き置きをしまい、防潮堤へ', 25, effects={'tide': 1})], enter={'items': {'letter': 1}, 'clues': ['sister']})
    N(25, '防潮堤の分かれ道',
      '街の端で、海は青い壁になっていた。頭上を魚が泳ぎ、鐘の音が届くたび壁面に幾つもの人影が浮かぶ。\n\n左には止まった揚水場。右には小舟の桟橋。礼拝堂へ続く歩道は、ところどころ波に呑まれている。灯台へは進める。しかし鐘を止めたあとの街にも、逃げ道を作っておくべきだろう。',
      [C('pump', '揚水場を動かしに行く', 26, effects={'tide': 1}), C('ferry', '桟橋の舟を利用する', 33), C('chapel', '冠水した歩道から礼拝堂へ', 35, effects={'tide': 2}), C('return', 'まだ支度が必要だ。波止場へ戻る', 3, effects={'tide': 1})])
    N(26, '眠る揚水場',
      '大きな歯車の下で、番兵が腕を組んでいる。胸の銘板に「整備中は三打、一休止、一打」と刻まれていたが、叩く場所まではわからない。\n\n整備屋の合図を知っていれば戦わず通れそうだ。知らなければ厚い装甲を相手にする。背後の海壁が、一段高くなる音がした。',
      [C('signal', '灯から教わった整備の合図を送る', 28, requires=K('gears'), effects={'tide': 1}, locked='灯を助け、整備の合図を教わる必要がある。'),
       C('fight', '番兵を破壊して奥へ', 27, effects={'tide': 1}), C('back', '防潮堤へ戻る', 25)])
    N(27, '噛み合わない番兵',
      '番兵はあなたを侵入者と呼ばなかった。「整備員の名前を確認できません」。その一言だけを繰り返し、槌を持ち上げる。\n\n装甲は厚いが、槌を振り上げたあとに長い溜めがある。精密攻撃か鳴塩の小瓶なら装甲を無視できる。', combat=fight('pump', 28, 26))
    N(28, '整備室の置き土産',
      '整備室に、柄の短い槌と補強服が残っていた。壁の釘には従業員の名札が何十枚も掛かっている。すべて裏返しだ。\n\n道具を持っていくと、揚水機の動きが少し想像できるようになった。良い道具は、何をすべきかまで教えてくれる。装備を整えてから水門盤に向かおう。',
      [C('panel', '水門の操作盤へ', 29), C('back', '防潮堤へ戻る', 25)], enter={'items': {'hammer': 1, 'guardcoat': 1}, 'clues': ['water']})
    N(29, '二つの輪',
      '操作盤には「海輪」と「街輪」。どちらも人の力で回せる大きさだ。\n\n海輪は沖の取水口、街輪は低地の排水路につながる。順番を間違えれば街へ海を流し込むことになる。潮は待ってはくれないが、急いでよい問題でもない。',
      [C('sea', '先に海輪を閉める', 30, effects={'flags': ['sea_closed']}),
       C('city_safe', '街輪を開く', 31, requires=F('sea_closed'), effects={'tide': 1}, hidden=True),
       C('city_wrong', '先に街輪を開く', 32, requires={'not': F('sea_closed')}, hidden=True), C('back', '操作せず戻る', 26)])
    N(30, '海を閉める',
      '海輪は二度目に回したところで重くなった。外から押していた潮が、太い鉄管の奥で足止めされる。\n\nあとは街輪を開けば低地の水を落とせる。読んだ注意書きを思い出す。「海を閉めてから、街だ」',
      [C('drain', '街輪を開き、揚水機を始動する', 31, effects={'tide': 1}), C('back', 'いったん操作盤へ戻る', 29)])
    N(31, '街が息をする',
      '長い吸気のような音がして、低地の水が石畳から剥がれた。海壁の目盛が三つ下がる。あなたは初めて、この街を救うとは水をどかすことでもあるのだと気づく。\n\n水路の向こうに、礼拝堂へ続く乾いた敷石が現れた。揚水機は一度始動すれば自律で動く。何度操作しても潮をさらに下げることはできない。',
      [C('chapel', '開いた水路から礼拝堂へ', 35, effects={'tide': 1}), C('back', '防潮堤へ戻る', 25)],
      enter={'flags': ['sluice_open'], 'tide': -3})
    N(32, '水圧の返事',
      '街輪を回した瞬間、鉄管が悲鳴を上げた。低地へ向けて水が噴き出し、あなたを壁に叩きつける。\n\n必死に輪を戻すと、噴流は止まった。体力を4失い、潮位は2進む。盤の横の注意書きが、濡れて初めて読める。「取水側を先に閉鎖せよ」',
      [C('return', '息を整え、操作盤へ戻る', 29)], enter={'hp': -4, 'tide': 2, 'clues': ['water']})
    N(33, '約束の渡し',
      '桟橋に小舟が揺れている。直しておいた舟なら槙がいるはずだ。そうでなければ、顔を布で覆った渡し守が料金を求める。\n\n舟は危ない歩道を避けて礼拝堂まで行ける。ただし街の排水まで代わりにやってくれるわけではない。救う範囲を、自分の足元だけに狭めてはいけない。',
      [C('friend', '槙の舟で渡る', 34, requires=F('helped_maki'), effects={'tide': 1}, locked='槙の舟を青い綱で直していない。'),
       C('pay', '渡し守に銀貨4を払い、渡る', 34, effects={'gold': -4, 'tide': 1}, locked='銀貨4が必要。'), C('back', '防潮堤へ戻る', 25)])
    N(34, '船底に残った光',
      '渡し舟の船底に、丸いガラスが挟まっていた。拾い上げると、海壁の人影から灯台へ伸びる光の糸が見える。潮見のレンズだ。\n\n舟を助けていたなら、槙はその向きを直してくれる。「見るためだけの道具じゃない。向きを変えれば、光も帰る」\n\n船は礼拝堂の石段へ着いた。',
      [C('chapel', '石段を登って礼拝堂へ', 35)], enter={'items': {'lens': 1}, 'clues': ['mirror']})
    N(35, '潮の礼拝堂',
      '礼拝堂の尖塔には、鐘を吊るす輪だけが残っている。扉に身を寄せた老いた鐘打ちが、あなたの足音で顔を上げた。\n\n「みんな、灯台の鐘を壊しに行く。壊した後で、誰の声が残るかは聞かない」\n\n灯台へはこの先の桟道を渡る。建物の中には、同じ鐘の小さな模型があるらしい。',
      [C('inside', '礼拝堂で鐘の仕組みを調べる', 36), C('shadow', '小鐘から漏れる人影を調べる', 39, effects={'tide': 1}), C('bridge', '灯台への桟道へ急ぐ', 41, effects={'tide': 1}), C('back', '防潮堤へ戻る', 25, effects={'tide': 1})])
    N(36, '止まった歌',
      '老鐘打ちは息を吸うたび、小さく胸を鳴らした。「榛も、初めは人を救いたかっただけだ。自分の子の名を思い出せなくなってから、鐘を止めるのを怖がるようになった」\n\n奥の祭壇には煤に覆われたレンズ。清め布か寄進で手入れしてもらえそうだ。老鐘打ちを先に薬で助ければ、残っている小鐘の欠片をくれるという。',
      [C('aid', '老鐘打ちに回復薬を一つ渡す', 36, requires=I('tonic'), effects={'items': {'tonic': -1, 'bellshard': 1}, 'flags': ['helped_ringer'], 'clues': ['bell']}, once=True, locked='琥珀の回復薬が必要。'),
       C('clean', '清め布を一枚使い、祭壇のレンズを磨く', 37, requires=I('bandage'), effects={'items': {'bandage': -1}, 'tide': 1}, once=True, locked='清め布が必要。'),
       C('donate', '銀貨3を寄進してレンズを修復してもらう', 37, effects={'gold': -3, 'tide': 1}, once=True, locked='銀貨3が必要。'),
       C('score', 'レンズより、祭壇の楽譜を調べる', 38, effects={'tide': 1}), C('back', '礼拝堂の外へ', 35)], enter={'clues': ['keeper']})
    N(37, '光を返す鏡',
      '煤が剥がれると、レンズにはあなたでない誰かの顔が映った。怯える人、怒る人、誰かを待つ人。見つめ続けると、顔は細い光の糸になって窓へ広がった。\n\nこれは一人を取り戻す窓ではない。沢山の声を分けて返すための焦点だ。傷の手当てにも使えた布の代わりに、別の修復の道具を手にした。',
      [C('score', '祭壇の裏の楽譜を読む', 38)], enter={'items': {'lens': 1}, 'clues': ['mirror']})
    N(38, '聖歌の裏面',
      '楽譜の裏に、正式な聖歌とは逆向きに拍が刻まれている。返し歌。声を一つの鐘に集めるのでなく、街へ分け戻す歌だ。\n\n欄外には必要なものが四つある。契約の原本。声の焦点。水の逃げ道。そして、主旋律とは別の拍を刻む助手。\n\n剣で街を救うことはできるかもしれない。しかし名前を返すには、もっと沢山の手がいる。',
      [C('bridge', '楽譜を覚え、桟道へ', 41, effects={'tide': 1}), C('outside', '礼拝堂の外へ戻る', 35)], enter={'clues': ['score', 'warning']})
    N(39, '鐘打ちの残響',
      '小鐘の輪から、人のかたちをした震えが剥がれ落ちた。長い腕を振るたび、あなたの名前の最初の音が耳から抜けかける。\n\n「返し歌を知っているなら、音を外せ」と老鐘打ちが叫ぶ。技術として覚えた知識が、今は盾にもなる。',
      combat=fight('echo', 40, 35, [{'requires': K('score'), 'stats': {'hp': -6, 'armor': -1}, 'text': '返し歌で残響の輪郭が崩れた。敵体力−6、装甲−1。'}]))
    N(40, 'ひびの音程',
      '人影は鐘へ戻らず、銀色のひびに変わった。残った小さな欠片には、主鐘を割るのにちょうどよい音程が閉じ込められている。\n\n壊す方法は手に入った。直す方法が足りなくなったときにも、これがあれば最後の選択肢が残る。',
      [C('bridge', '欠片を包み、桟道へ', 41, effects={'tide': 1}), C('outside', '礼拝堂の外へ戻る', 35)], enter={'items': {'bellshard': 1}, 'clues': ['bell']})
    N(41, '戻らない足場',
      '灯台への桟道が一部崩れている。排水に成功していれば、下の保守路を歩ける。青い綱が残っていれば、支柱に結んで渡れるだろう。\n\nどちらもなければ、濡れた石を跳ぶしかない。失敗すれば下の門番に見つかる。灯台まで来ても、道中で誰に何を渡したかが、足元を変えている。',
      [C('dry', '排水された保守路を渡る', 43, requires=F('sluice_open'), effects={'tide': 1}, locked='揚水場を正しい順序で動かす必要がある。'),
       C('rope', '青い船綱を使って渡る', 43, requires=I('rope'), effects={'items': {'rope': -1}, 'tide': 1}, locked='青い船綱が必要。'),
       C('jump', '石から石へ跳んで渡る', 43, effects={'tide': 1}, test={'stat': 'agility', 'dc': 8, 'success': '43', 'failure': '42'}), C('back', '礼拝堂へ戻って考え直す', 35)])
    N(42, '落水の門番',
      '着地した石が割れ、あなたは浅い水へ落ちた。体力を3失う。水底から、古い潜水服を着た門番が立ち上がる。顔の窓の中は海そのものだ。\n\n上の梯子へ行くには門番を退かさなければならない。逃げるなら、礼拝堂まで戻れる。', enter={'hp': -3}, combat=fight('drowned', 43, 35))
    N(43, '螺旋の喉',
      '灯台の階段は、巨大な管の喉を登るようだった。外から聞こえた鐘は内側で低い呼吸になっている。\n\n踊り場には整備室と見張り窓。奥へ進めば、もう街まで戻る時間はない。ここで道具と体力を確かめておくべきだ。',
      [C('window', '潮見の窓を調べる', 44), C('prepare', '整備室で最後の支度をする', 58), C('lookout', '見張り窓を探る', 59, effects={'tide': 1}),
       C('child', '下から聞こえる工具の音を待つ', 60, requires=F('helped_child'), once=True, locked='灯を助けていない。'), C('keeper', '鐘守のいる最上階へ', 45)])
    N(44, '声の流れ',
      '窓の向こうに海ではなく、重なった声の流れが見える。レンズがあれば一本ずつを分けて読めそうだ。\n\n何もない掌をかざしても、声は焦点を結ばない。手紙の言葉だけを頼りに、先へ進むこともできる。',
      [C('focus', '潮見のレンズで声の道を確かめる', 45, requires=I('lens'), effects={'clues': ['mirror'], 'focus': 1}, once=True, locked='潮見のレンズが必要。'), C('go', '最上階へ進む', 45), C('back', '踊り場へ戻る', 43)])
    N(45, '鐘守の食卓',
      '最上階には武器庫でなく、小さな食卓があった。三人分の椅子と一人分の皿。老人が、冷えたスープに匙を入れている。\n\n「迎えに来たのか。忘れに来たのか」\n\n老人の背後で灰鐘が揺れる。剣を抜けば戦いになる。しかし食卓の空いた二つの椅子を見てからでは、単なる怪物として扱うのは難しかった。',
      [C('speak', '鐘守と話す', 46), C('fight', 'これ以上の犠牲を止めるため、剣を抜く', 48), C('back', '踊り場で支度を整え直す', 43)])
    N(46, '榛の告白',
      'あなたが榛という名を知っていれば、老人は目を伏せる。知らなくても、自分からその名を教えた。「最後まで覚えているつもりだった。妻も、子も」\n\n最初の嵐で街を失うはずだった夜、彼は海と契約した。その夜だけのはずが七十年になった。凪は契約の中へ入り、人々の名をばらばらにしないよう守っているという。\n\n原本があれば、いまも契約は書き換えられるかもしれない。',
      [C('contract', '消された帰船簿を机に置く', 47, requires=I('ledger'), locked='記録院の帰船簿を持っている必要がある。'),
       C('name', '自分の名前を代価にする契約を聞く', 47, requires=K('contract'), locked='記録院で鐘の契約を知っている必要がある。'),
       C('fight', '代価を選ばせる仕組みごと止める', 48), C('accept', '今年だけは続けるよう頼む', 54)], enter={'clues': ['keeper']})
    N(47, '契約の空白',
      '榛は署名用の紙を机へ置いた。余白には、新しい契約を書き込むだけの白がある。\n\n「新しい名を一つ渡せば、今年の徴収は止まる。ただ、海にある名前は返らない。すべて返すなら契約を破るだけでは足りない。潮そのものに道を作る必要がある」\n\n彼は剣を下ろした。しかし鐘の底では、もう別の何かがあなたを見ている。',
      [C('unmake', '原本とレンズを合わせ、名前のない潮を呼び出す', 49, requires=A(I('ledger'), I('lens'), K('score')), effects={'tide': 1}, locked='帰船簿・潮見のレンズ・返し歌の三つが必要。'),
       C('sacrifice', '自分の名を署名欄へ書き込み、今年の徴収を止める', 52, requires=K('contract'), locked='鐘の契約を理解する必要がある。'),
       C('fight', '猶予では足りない。鐘を破壊するため戦う', 48), C('return', '踊り場へ戻り、足りないものを確かめる', 43)])
    N(48, '最後の徴名人',
      '榛の剣は重く、振り上げるたびに体が軋んだ。それでも鐘の前から退こうとしない。\n\n「俺が悪者で済むなら、そうしてくれ。その方が、街も眠りやすい」\n\nあなたは切り捨てるのでなく、剣を置かせるために間合いへ入る。彼が言葉を探している瞬間だけ、構えが揺れる。',
      combat=fight('keeper', 50, None, [{'requires': K('keeper'), 'stats': {'skill': -1}, 'text': '榛の名を呼ぶと剣が鈍る。敵技量−1。'}]))
    N(49, '名前のない潮',
      '灰鐘の内側が海になった。顔のない巨大な人影が身を起こし、街から奪った言葉を雨のようにこぼす。\n\nあなたが原本を開くと、影は形を失いかける。レンズで光を分け、返し歌の一拍を入れるたびに、海がいくらか人へ戻る。\n\nこれは倒して消す相手ではない。声を岸へ送り出すまで、輪郭を崩し続ける戦いだ。',
      combat=fight('nameless', 50, None, [
          {'requires': I('lens'), 'stats': {'guard': -1}, 'text': '潮見のレンズが輪郭を捉えた。敵回避−1。'},
          {'requires': K('score'), 'stats': {'hp': -8, 'armor': -2}, 'text': '返し歌が潮をほどく。敵体力−8、装甲−2。'},
          {'requires': F('helped_child'), 'stats': {'skill': -1}, 'text': '追いついた灯が裏拍を刻む。敵技量−1。'}]))
    N(50, '鐘を鳴らす手',
      '激しい音が止んだ。榛は食卓の椅子に腰を下ろし、あなたに最後の操作を委ねる。\n\n鐘を砕けば、この街の徴収は終わる。自分の名を渡せば、ひとまず今年を越せる。原本、焦点、排水、調律を手伝う灯、返し歌が揃っていれば、声を街へ返すこともできる。\n\n何を守るかは、剣の届く範囲だけでは決まらない。あなたがここへ持ってきたものが、いま選べる未来だ。',
      [C('restore', '灯と返し歌を奏で、街へすべての名前を返す', 51,
         requires=A(I('ledger'), I('lens'), K('score'), F('sluice_open'), F('helped_child')),
         effects={'flags': ['restored_names']},
         locked='帰船簿・レンズ・返し歌・揚水場の始動・灯の救助がすべて必要。'),
       C('sacrifice', '自分の名を渡し、今年の徴収を止める', 52, requires=K('contract'), locked='鐘の契約を理解していない。'),
       C('break', '灰鐘を砕き、徴収を終わらせる', 53, requires=O(I('bellshard'), F('keeper_defeated'), F('tide_defeated')), locked='灰鐘の欠片、または鐘の守りを破ることが必要。'),
       C('repeat', '装置を止められず、もう一度だけ鐘を鳴らす', 54)])
    N(51, '誰のものでもない朝',
      '灯が一拍を外す。あなたは返し歌を重ね、レンズを港へ向けた。揚水場が海を受け止め、帰船簿の文字が一つずつ紙を離れる。街の窓が、誰かを呼ぶ声で開いた。\n\n凪は岸へ帰ってこなかった。七年をなかったことにはできない。それでもあなたは、凪と呼んで泣くことができた。槙は娘の名を叫び、榛は二つの空いた椅子を、初めて片づけた。\n\n翌朝、門番が通行票を差し出す。「名前は、書きたければ」あなたは自分の名前を書いた。今度は預けるためでなく、ここへ来たと残すために。',
      ending=end('names_returned', 'success', '終幕 I · 誰も新しい代価にしない朝'))
    N(52, '空欄に座る人',
      'あなたが名を書き終えると、インクは紙へ沈まず海へ落ちた。街の今年の徴収が止まる。凪の名も、まだ遠くに守られている。\n\n門を出るとき、門番はあなたの来たことを覚えていなかった。あなた自身は、凪を覚えていた。帰る場所の名も、覚えていた。それだけを頼りに歩く。\n\n名簿の片隅には白い余白が残った。いつか誰かが、そこにも人がいたと気づくだろう。',
      ending=end('name_given', 'success', '終幕 II · 一年の猶予、その代価'))
    N(53, '鐘を砕いた街',
      '灰鐘が割れた音は、驚くほど小さかった。街を縛っていた徴収の仕組みが終わり、海は海として戻ってきた。\n\n排水が動いていれば低地の水は流れ、動いていなければ人々は高台へ逃げた。街は傷ついても、次の犠牲を選ぶ必要はなくなった。だが、鐘に残っていた幾つもの名前は、最後の響きと一緒に消えた。\n\nあなたは凪の墓に、新しい石を置いた。救えたものを数える日と、救えなかったものを忘れない日。その二つを分けて、生きていく。',
      ending=end('bell_broken', 'success', '終幕 III · 解放と、取り戻せなかったもの'))
    N(54, 'もう一度だけ',
      '鐘を鳴らすと、海壁は元の位置へ戻った。市の灯りがともり、明日の荷揚げの予定が組まれる。誰かが支払った一日だ。\n\n帰りの税関で、役人が一枚の通行票を破った。誰の名が書かれていたか、あなたには読めなかった。\n\n街は今日も無事だった。手紙が届く前と、同じ意味で。', ending=end('contract_renewed', 'ending', '終幕 IV · 何も終わらなかった夜'))
    N(55, '潮に閉じた頁',
      '潮位計の十六番目の目盛が海に沈んだ。最後の鐘が鳴り、街の音が一斉に薄くなる。\n\n鞄の中の道具は残っている。読んだことも、助けた人も、なかったことにはならない。けれど今夜の鐘には届かなかった。\n\nこの旅の頁はここで閉じる。次の旅では、何を寄り道と呼ぶべきか、もう少しわかるだろう。', ending=end('too_late', 'deadend', '終幕 V · 潮位16／時間切れ'))
    N(56, '剣の届かない朝',
      '膝が石畳に触れた。持ち直そうとした刃より先に、鞄から一枚の紙が滑り出る。\n\n凪、と書いた二文字。忘れないために、あなたが何度も書き直してきた字だ。\n\n最後に見えたそれだけは、空欄にはならなかった。あなたの旅はここで終わる。', ending=end('fallen', 'deadend', '終幕 VI · 体力0'))
    N(57, '別れの桟橋',
      'あなたは港に背を向けた。妹の筆跡を真似た悪戯かもしれない。街ひとつの仕組みを、自分一人が引き受ける理由はない。\n\n干潟の終わりで、遠くの鐘が鳴った。手紙を開き直すと、署名のあった場所が少し白くなっていた。\n\nこの選択にも、続く暮らしはある。ただ、この本には書かれていない。', ending=end('departed', 'ending', '終幕 VII · 選ばなかった港'))
    N(58, '最後の整備室',
      '棚に残っている品は少ない。整備員用の防護服には銀貨五枚、緊急用の薬には三枚と書かれている。料金箱は開いているが、中には次の整備員の食費が入っている。\n\nここは最後に落ち着いて装備を替えられる場所だ。食料は戦闘外でしか食べられない。体力と集中を確かめてから階段へ戻ろう。',
      [C('coat', '油布の防護服を買う／銀貨5', 58, effects={'gold': -5, 'items': {'oilcoat': 1}}, once=True, locked='銀貨5が必要。'),
       C('tonic', '回復薬を買う／銀貨3', 58, effects={'gold': -3, 'items': {'tonic': 1}}, once=True, locked='銀貨3が必要。'),
       C('back', '踊り場へ戻る', 43)])
    N(59, '見張りのいない窓',
      '窓辺の引き出しに鳴塩の小瓶と銀貨がある。小さな文字で「徴名人ではなく、修理人が来たときのため」と書き添えてあった。\n\n見張りは誰を待っていたのだろう。あなたは余計な推測をやめ、使える道具を持った。待つ人の望みを、勝手に物語にしてしまわないために。',
      [C('back', '道具を持って踊り場へ', 43)], enter={'items': {'saltbomb': 1}, 'gold': 4})
    N(60, 'もう一人の調律師',
      '階段を駆け上がってきた灯は、息を切らしたまま工具袋を床に置いた。「間に合った？　まだ直せる？」\n\nあなたが頷くと、灯は余った布で腕の傷を巻いた。体力が6回復する。\n\n「歌は下手。でも、ずらして叩くのは得意」灯の名は、今も灯のものだった。それだけで、今夜の最後の一拍を任せる理由になる。',
      [C('back', '灯とともに踊り場へ', 43)], enter={'hp': 6, 'focus': 1})
    # Mutual exclusion survives revisits; purchasing the same alternative twice
    # must not grant both the original ledger and the escape money.
    for choice in s['sections']['22']['choices']:
        choice['requires'] = {'not': F('ledger_decided')}
        choice.setdefault('effects', {}).setdefault('flags', []).append('ledger_decided')
    s['sections']['22']['choices'].append(C('continue', '選んだものを持ち、砂緒のもとへ', 23, requires=F('ledger_decided')))
    # Hazard damage repeats; rewards and discoveries remain first-entry-only.
    s['sections']['32']['repeat'] = {'hp': -4, 'tide': 2}
    s['sections']['32']['enter'] = {'clues': ['water']}
    s['sections']['42']['repeat'] = {'hp': -3}
    s['sections']['42'].pop('enter')
    before, _, after = s['sections']['53']['text']
    s['sections']['53']['variants'] = [
        {'requires': F('sluice_open'), 'text': [before, '揚水場の歯車が回り、低地の水を海へ送り返した。人々は濡れた石畳に立ち、次の犠牲を選ばなくてよいと知った。だが、鐘に残っていた幾つもの名前は、最後の響きと一緒に消えた。', after]},
        {'requires': {'not': F('sluice_open')}, 'text': [before, '止まったままの揚水場を越え、海が低地に流れ込む。人々は高台へ逃げ、朝まで助け合った。街は失った家屋を数えた。鐘に残っていた幾つもの名前も、最後の響きと一緒に消えていた。', after]},
    ]
    return s


def make_story() -> RPGBook:
    return RPGBook(build_spec())


def export_story(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    spec = build_spec(); RPGBook(spec)
    (directory / 'ashbell-ja.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [f'# {TITLE}', '', '> 日本語オリジナル・60節・7つの結末。以下には全分岐と結末が含まれます。', '',
             '## はじめに', '', OBJECTIVE, '', '本書はアプリ実装用の原稿です。戦闘、道具使用、装備変更は rpg_engine.py が処理します。', '']
    for sid, node in spec['sections'].items():
        lines += [f'<a id="s{sid}"></a>', f'## {sid}　{node["title"]}', '', *[p + '\n' for p in node['text']]]
        if node.get('enter'):
            lines += ['初回到達時：`' + json.dumps(node['enter'], ensure_ascii=False) + '`', '']
        if node.get('repeat'):
            lines += ['到達のたびに：`' + json.dumps(node['repeat'], ensure_ascii=False) + '`', '']
        for v in node.get('variants', []):
            lines += ['条件別本文：`' + json.dumps(v['requires'], ensure_ascii=False) + '`', '', *[p + '\n' for p in v['text']]]
        if node.get('combat'):
            c = node['combat']; e = spec['enemies'][c['enemy']]
            lines += [f'**戦闘：{e["name"]}**（体力{e["hp"]}、技量{e["skill"]}、回避{e["guard"]}、装甲{e["armor"]}）',
                      f'勝利 → [{c["win"]}](#s{c["win"]})' + (f'／撤退 → [{c["flee"]}](#s{c["flee"]})' if c['flee'] else '／撤退不可'), '']
            if c.get('modifiers'):
                lines += ['戦闘への影響：`' + json.dumps(c['modifiers'], ensure_ascii=False) + '`', '']
        for c in node['choices']:
            lines += [f'- {c["text"]} → [{c["to"]}](#s{c["to"]})']
            meta = {k: v for k, v in c.items() if k not in ('id', 'text', 'to')}
            if meta:
                lines += ['  - 処理条件：`' + json.dumps(meta, ensure_ascii=False) + '`']
        if node.get('ending'):
            lines += ['**' + node['ending']['label'] + '**']
        lines += ['']
    lines += ['## 付録・初期状態', '', '```json', json.dumps(spec['initial'], ensure_ascii=False, indent=2), '```', '']
    for label, key in [('道具一覧', 'items'), ('敵一覧', 'enemies'), ('手がかり一覧', 'clues')]:
        lines += ['## 付録・' + label, '']
        for ident, value in spec[key].items():
            lines += ['### ' + ident, '', '```json', json.dumps(value, ensure_ascii=False, indent=2), '```', '']
    (directory / '灰鐘の港と名前のない朝.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export the original Japanese gamebook to JSON and Markdown')
    parser.add_argument('--output', type=Path, default=Path('story-export'))
    export_story(parser.parse_args().output)
